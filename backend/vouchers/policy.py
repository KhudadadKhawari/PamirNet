import calendar
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from subscribers.models import UsagePolicy, UsagePolicyStage
from subscribers.policy import EffectivePolicy

from .models import Voucher, VoucherUsageCounter

GB_BYTES = Decimal("1000000000")


def _tenant_zone(voucher: Voucher) -> ZoneInfo:
    try:
        return ZoneInfo(voucher.tenant.timezone)
    except Exception:
        return ZoneInfo("UTC")


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def period_bounds(voucher: Voucher, scope: str, at: datetime | None = None):
    at = at or timezone.now()
    if not voucher.activated_at or not voucher.expires_at:
        raise ValueError("Voucher must be activated before usage periods can be calculated.")
    start = voucher.activated_at
    end = voucher.expires_at

    if scope == UsagePolicy.Scope.SUBSCRIPTION:
        return start, end
    if scope == UsagePolicy.Scope.WEEKLY:
        elapsed = max(0, int((at - start).total_seconds()))
        index = elapsed // int(timedelta(weeks=1).total_seconds())
        period_start = start + timedelta(weeks=index)
        return period_start, min(period_start + timedelta(weeks=1), end)

    zone = _tenant_zone(voucher)
    local_at = at.astimezone(zone)
    local_start = start.astimezone(zone)
    if scope == UsagePolicy.Scope.DAILY:
        period_start_local = datetime.combine(local_at.date(), time.min, tzinfo=zone)
        period_end_local = datetime.combine(
            local_at.date() + timedelta(days=1),
            time.min,
            tzinfo=zone,
        )
        return (
            max(period_start_local.astimezone(UTC), start),
            min(period_end_local.astimezone(UTC), end),
        )
    if scope == UsagePolicy.Scope.MONTHLY:
        months = (local_at.year - local_start.year) * 12 + local_at.month - local_start.month
        months = max(months, 0)
        candidate = _add_months(local_start, months)
        if candidate > local_at and months:
            months -= 1
        period_start_local = _add_months(local_start, months)
        period_end_local = _add_months(local_start, months + 1)
        return (
            max(period_start_local.astimezone(UTC), start),
            min(period_end_local.astimezone(UTC), end),
        )
    raise ValueError(f"Unsupported usage policy scope: {scope}")


def _counter_for(voucher: Voucher, scope: str, *, at=None, lock=False):
    period_start, period_end = period_bounds(voucher, scope, at)
    queryset = VoucherUsageCounter.objects
    if lock:
        queryset = queryset.select_for_update()
    counter, _ = queryset.get_or_create(
        voucher=voucher,
        scope=scope,
        defaults={
            "tenant": voucher.tenant,
            "period_start": period_start,
            "period_end": period_end,
            "bytes_used": 0,
        },
    )
    if counter.period_start != period_start or counter.period_end != period_end:
        counter.period_start = period_start
        counter.period_end = period_end
        counter.bytes_used = 0
        counter.save(update_fields=["period_start", "period_end", "bytes_used", "updated_at"])
    return counter


@transaction.atomic
def record_voucher_usage_delta(voucher: Voucher, *, input_bytes=0, output_bytes=0, at=None):
    if input_bytes < 0 or output_bytes < 0:
        raise ValueError("Usage deltas cannot be negative.")
    delta = input_bytes + output_bytes
    if not delta:
        return 0
    voucher = Voucher.objects.select_for_update().select_related("tenant").get(pk=voucher.pk)
    for scope in UsagePolicy.Scope.values:
        counter = _counter_for(voucher, scope, at=at, lock=True)
        counter.bytes_used += delta
        counter.save(update_fields=["bytes_used", "updated_at"])
    return delta


def calculate_voucher_effective_policy(voucher: Voucher, *, at=None) -> EffectivePolicy:
    at = at or timezone.now()
    voucher = (
        Voucher.objects.select_related("tenant", "package")
        .prefetch_related("package__usage_policies__stages")
        .get(pk=voucher.pk)
    )
    result = EffectivePolicy(
        download_speed_mbps=voucher.package.download_speed_mbps,
        upload_speed_mbps=voucher.package.upload_speed_mbps,
    )
    if not voucher.activated_at or not voucher.expires_at:
        return result

    for policy in voucher.package.usage_policies.all():
        if not policy.enabled:
            continue
        counter = _counter_for(voucher, policy.scope, at=at)
        result.usage[policy.scope] = {
            "bytes_used": counter.bytes_used,
            "gb_used": str((Decimal(counter.bytes_used) / GB_BYTES).quantize(Decimal("0.001"))),
            "period_start": counter.period_start,
            "period_end": counter.period_end,
        }
        matched = None
        for stage in policy.stages.all():
            if counter.bytes_used >= int(stage.threshold_gb * GB_BYTES):
                matched = stage
            else:
                break
        if not matched:
            continue
        match = {
            "scope": policy.scope,
            "stage_id": str(matched.id),
            "threshold_gb": str(matched.threshold_gb),
            "action": matched.action,
        }
        if matched.action == UsagePolicyStage.Action.BLOCK:
            result.blocked = True
        else:
            down = matched.download_speed_mbps or result.download_speed_mbps
            up = matched.upload_speed_mbps or result.upload_speed_mbps
            result.download_speed_mbps = min(result.download_speed_mbps, down)
            result.upload_speed_mbps = min(result.upload_speed_mbps, up)
            match["download_speed_mbps"] = down
            match["upload_speed_mbps"] = up
        result.matches.append(match)
    return result
