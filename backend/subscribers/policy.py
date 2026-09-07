import calendar
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from .models import (
    Subscription,
    SubscriptionUsageCounter,
    UsagePolicy,
    UsagePolicyStage,
)

GB_BYTES = Decimal("1000000000")


@dataclass
class EffectivePolicy:
    download_speed_mbps: int
    upload_speed_mbps: int
    blocked: bool = False
    matches: list[dict] = field(default_factory=list)
    usage: dict[str, dict] = field(default_factory=dict)


def _tenant_zone(subscription: Subscription) -> ZoneInfo:
    try:
        return ZoneInfo(subscription.tenant.timezone)
    except Exception:
        return ZoneInfo("UTC")


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def period_bounds(
    subscription: Subscription,
    scope: str,
    at: datetime | None = None,
) -> tuple[datetime, datetime]:
    at = at or timezone.now()
    start = subscription.started_at
    end = subscription.expires_at
    if at < start:
        at = start

    if scope == UsagePolicy.Scope.SUBSCRIPTION:
        return start, end

    if scope == UsagePolicy.Scope.WEEKLY:
        elapsed = max(0, int((at - start).total_seconds()))
        period_index = elapsed // int(timedelta(weeks=1).total_seconds())
        period_start = start + timedelta(weeks=period_index)
        return period_start, min(period_start + timedelta(weeks=1), end)

    zone = _tenant_zone(subscription)
    local_at = at.astimezone(zone)
    local_start = start.astimezone(zone)

    if scope == UsagePolicy.Scope.DAILY:
        midnight = datetime.combine(local_at.date(), time.min, tzinfo=zone)
        next_midnight = datetime.combine(
            local_at.date() + timedelta(days=1),
            time.min,
            tzinfo=zone,
        )
        period_start = max(midnight.astimezone(timezone.utc), start)
        period_end = min(next_midnight.astimezone(timezone.utc), end)
        return period_start, period_end

    if scope == UsagePolicy.Scope.MONTHLY:
        months = (local_at.year - local_start.year) * 12 + local_at.month - local_start.month
        months = max(months, 0)
        candidate = _add_months(local_start, months)
        if candidate > local_at and months:
            months -= 1
        period_start_local = _add_months(local_start, months)
        period_end_local = _add_months(local_start, months + 1)
        period_start = max(period_start_local.astimezone(timezone.utc), start)
        period_end = min(period_end_local.astimezone(timezone.utc), end)
        return period_start, period_end

    raise ValueError(f"Unsupported usage policy scope: {scope}")


def _counter_for(
    subscription: Subscription,
    scope: str,
    *,
    at: datetime | None = None,
    lock: bool = False,
) -> SubscriptionUsageCounter:
    period_start, period_end = period_bounds(subscription, scope, at)
    queryset = SubscriptionUsageCounter.objects
    if lock:
        queryset = queryset.select_for_update()
    counter, _ = queryset.get_or_create(
        subscription=subscription,
        scope=scope,
        defaults={
            "tenant": subscription.tenant,
            "period_start": period_start,
            "period_end": period_end,
            "bytes_used": 0,
        },
    )
    if counter.period_start != period_start or counter.period_end != period_end:
        counter.period_start = period_start
        counter.period_end = period_end
        counter.bytes_used = 0
        counter.save(
            update_fields=["period_start", "period_end", "bytes_used", "updated_at"]
        )
    return counter


@transaction.atomic
def record_usage_delta(
    subscription: Subscription,
    *,
    input_bytes: int = 0,
    output_bytes: int = 0,
    at: datetime | None = None,
) -> int:
    if input_bytes < 0 or output_bytes < 0:
        raise ValueError("Usage deltas cannot be negative.")
    delta = input_bytes + output_bytes
    if not delta:
        return 0
    subscription = (
        Subscription.objects.select_for_update()
        .select_related("tenant")
        .get(pk=subscription.pk)
    )
    for scope in UsagePolicy.Scope.values:
        counter = _counter_for(subscription, scope, at=at, lock=True)
        counter.bytes_used += delta
        counter.save(update_fields=["bytes_used", "updated_at"])
    return delta


def _threshold_bytes(stage: UsagePolicyStage) -> int:
    return int(stage.threshold_gb * GB_BYTES)


def calculate_effective_policy(
    subscription: Subscription,
    *,
    at: datetime | None = None,
) -> EffectivePolicy:
    at = at or timezone.now()
    subscription = (
        Subscription.objects.select_related("tenant", "package")
        .prefetch_related("package__usage_policies__stages")
        .get(pk=subscription.pk)
    )
    result = EffectivePolicy(
        download_speed_mbps=subscription.package.download_speed_mbps,
        upload_speed_mbps=subscription.package.upload_speed_mbps,
    )

    for policy in subscription.package.usage_policies.all():
        if not policy.enabled:
            continue
        counter = _counter_for(subscription, policy.scope, at=at)
        result.usage[policy.scope] = {
            "bytes_used": counter.bytes_used,
            "gb_used": str((Decimal(counter.bytes_used) / GB_BYTES).quantize(Decimal("0.001"))),
            "period_start": counter.period_start,
            "period_end": counter.period_end,
        }
        matched_stage = None
        for stage in policy.stages.all():
            if counter.bytes_used >= _threshold_bytes(stage):
                matched_stage = stage
            else:
                break
        if matched_stage is None:
            continue

        match = {
            "scope": policy.scope,
            "stage_id": str(matched_stage.id),
            "threshold_gb": str(matched_stage.threshold_gb),
            "action": matched_stage.action,
        }
        if matched_stage.action == UsagePolicyStage.Action.BLOCK:
            result.blocked = True
        else:
            result.download_speed_mbps = min(
                result.download_speed_mbps,
                matched_stage.download_speed_mbps,
            )
            result.upload_speed_mbps = min(
                result.upload_speed_mbps,
                matched_stage.upload_speed_mbps,
            )
            match["download_speed_mbps"] = matched_stage.download_speed_mbps
            match["upload_speed_mbps"] = matched_stage.upload_speed_mbps
        result.matches.append(match)

    return result


def effective_policy_payload(policy: EffectivePolicy) -> dict:
    return {
        "blocked": policy.blocked,
        "download_speed_mbps": policy.download_speed_mbps,
        "upload_speed_mbps": policy.upload_speed_mbps,
        "matches": policy.matches,
        "usage": policy.usage,
    }
