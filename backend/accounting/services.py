import hashlib
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from networking.models import Router
from subscribers.models import SubscriberCredential, Subscription
from subscribers.policy import calculate_effective_policy, record_usage_delta
from vouchers.models import Voucher
from vouchers.policy import calculate_voucher_effective_policy, record_voucher_usage_delta
from vouchers.services import activate_voucher

from .models import RadiusAccountingEvent, RadiusSession, UsageAggregate

GIGAWORD_BYTES = 2**32


class AccountingReject(Exception):
    pass


def _int(value, default: int = 0) -> int:
    try:
        return max(0, int(str(value or default).strip()))
    except (TypeError, ValueError):
        return default


def _counter_bytes(octets, gigawords) -> int:
    return _int(octets) + (_int(gigawords) * GIGAWORD_BYTES)


def _event_time(payload: dict) -> datetime:
    now = timezone.now()
    raw = str(payload.get("event_timestamp") or "").strip()
    parsed = None
    if raw:
        parsed = parse_datetime(raw)
        if parsed is None:
            try:
                parsed = datetime.fromtimestamp(float(raw), tz=UTC)
            except (TypeError, ValueError, OSError):
                parsed = None
    if parsed is None:
        parsed = now - timedelta(seconds=_int(payload.get("acct_delay_time")))
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, UTC)
    return parsed


def _router_for_source(packet_src_ip: str) -> Router:
    try:
        return Router.objects.select_related("tenant").get(
            tunnel_ip=packet_src_ip,
            enabled=True,
        )
    except Router.DoesNotExist as exc:
        raise AccountingReject("Unknown NAS") from exc


def _resolve_identity(router: Router, username: str):
    credential = (
        SubscriberCredential.objects.select_related("subscriber")
        .filter(tenant=router.tenant, username=username)
        .first()
    )
    if credential:
        subscription = (
            Subscription.objects.select_related("package")
            .filter(
                subscriber=credential.subscriber,
                status=Subscription.Status.ACTIVE,
            )
            .order_by("-started_at")
            .first()
        )
        return {
            "identity_type": RadiusSession.IdentityType.SUBSCRIBER,
            "identity_key": f"subscriber:{credential.subscriber_id}",
            "subscriber": credential.subscriber,
            "subscription": subscription,
            "voucher": None,
            "identity_name": credential.subscriber.name,
        }

    voucher = (
        Voucher.objects.select_related("batch", "package")
        .filter(tenant=router.tenant, username=username)
        .first()
    )
    if voucher:
        if voucher.status == Voucher.Status.GENERATED:
            voucher = activate_voucher(voucher)
        return {
            "identity_type": RadiusSession.IdentityType.VOUCHER,
            "identity_key": f"voucher:{voucher.id}",
            "subscriber": None,
            "subscription": None,
            "voucher": voucher,
            "identity_name": voucher.batch.name,
        }
    raise AccountingReject("Unknown RADIUS identity")


def _rate_limit(identity: dict, at: datetime) -> str:
    if identity["identity_type"] == RadiusSession.IdentityType.SUBSCRIBER:
        subscription = identity.get("subscription")
        if not subscription:
            return ""
        policy = calculate_effective_policy(subscription, at=at)
    else:
        voucher = identity.get("voucher")
        if not voucher or not voucher.activated_at:
            return ""
        policy = calculate_voucher_effective_policy(voucher, at=at)
    if policy.blocked:
        return ""
    return f"{policy.upload_speed_mbps}M/{policy.download_speed_mbps}M"


def _identity_name(session: RadiusSession) -> str:
    if session.subscriber_id and session.subscriber:
        return session.subscriber.name
    if session.voucher_id and session.voucher:
        return session.voucher.batch.name
    return session.username


def _bucket_start(tenant, at: datetime, granularity: str) -> datetime:
    try:
        zone = ZoneInfo(tenant.timezone)
    except Exception:
        zone = ZoneInfo("UTC")
    local = at.astimezone(zone)
    if granularity == UsageAggregate.Granularity.HOUR:
        local = local.replace(minute=0, second=0, microsecond=0)
    else:
        local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return local.astimezone(UTC)


def _update_aggregates(
    session: RadiusSession,
    *,
    input_delta: int,
    output_delta: int,
    seconds_delta: int,
    at: datetime,
):
    if not input_delta and not output_delta and not seconds_delta:
        return
    name = _identity_name(session)
    for granularity in UsageAggregate.Granularity.values:
        period_start = _bucket_start(session.tenant, at, granularity)
        aggregate, _ = UsageAggregate.objects.select_for_update().get_or_create(
            tenant=session.tenant,
            router=session.router,
            granularity=granularity,
            period_start=period_start,
            identity_key=session.identity_key,
            defaults={
                "identity_type": session.identity_type,
                "identity_name": name,
                "username": session.username,
            },
        )
        UsageAggregate.objects.filter(pk=aggregate.pk).update(
            input_bytes=F("input_bytes") + input_delta,
            output_bytes=F("output_bytes") + output_delta,
            session_seconds=F("session_seconds") + seconds_delta,
            sample_count=F("sample_count") + 1,
            identity_name=name,
            username=session.username,
        )


def _usage_time(session: RadiusSession, event_at: datetime) -> datetime:
    if session.subscription_id and session.subscription:
        end = session.subscription.expires_at
        if event_at >= end:
            return end - timedelta(microseconds=1)
    if session.voucher_id and session.voucher and session.voucher.expires_at:
        end = session.voucher.expires_at
        if event_at >= end:
            return end - timedelta(microseconds=1)
    return event_at


def _record_identity_usage(
    session: RadiusSession,
    *,
    input_delta: int,
    output_delta: int,
    at: datetime,
):
    if not input_delta and not output_delta:
        return
    usage_at = _usage_time(session, at)
    if session.identity_type == RadiusSession.IdentityType.SUBSCRIBER:
        if session.subscription_id and session.subscription:
            record_usage_delta(
                session.subscription,
                input_bytes=input_delta,
                output_bytes=output_delta,
                at=usage_at,
            )
    elif session.voucher_id and session.voucher:
        record_voucher_usage_delta(
            session.voucher,
            input_bytes=input_delta,
            output_bytes=output_delta,
            at=usage_at,
        )


def _event_key(
    router: Router,
    username: str,
    acct_session_id: str,
    status_type: str,
    input_bytes: int,
    output_bytes: int,
    session_seconds: int,
    terminate_cause: str,
) -> str:
    material = "|".join(
        [
            str(router.id),
            username,
            acct_session_id,
            status_type,
            str(input_bytes),
            str(output_bytes),
            str(session_seconds),
            terminate_cause,
        ]
    )
    return hashlib.sha256(material.encode()).hexdigest()


def _delta(current: int, previous: int) -> int:
    if current >= previous:
        return current - previous
    # A NAS counter reset should count the new post-reset bytes instead of
    # turning into a massive negative delta.
    return current


def ingest_accounting(payload: dict) -> tuple[RadiusSession, bool]:
    packet_src_ip = str(payload.get("packet_src_ip") or "").strip()
    username = str(payload.get("username") or "").strip()
    acct_session_id = str(payload.get("acct_session_id") or "").strip()
    status_type = str(payload.get("acct_status_type") or "").strip()
    if not packet_src_ip or not username or not acct_session_id:
        raise AccountingReject("Missing required accounting identity fields")
    if status_type not in RadiusAccountingEvent.StatusType.values:
        raise AccountingReject("Unsupported Acct-Status-Type")

    event_at = _event_time(payload)
    input_bytes = _counter_bytes(
        payload.get("acct_input_octets"),
        payload.get("acct_input_gigawords"),
    )
    output_bytes = _counter_bytes(
        payload.get("acct_output_octets"),
        payload.get("acct_output_gigawords"),
    )
    session_seconds = _int(payload.get("acct_session_time"))
    terminate_cause = str(payload.get("acct_terminate_cause") or "")[:120]

    should_evaluate_policy = False
    with transaction.atomic():
        router = _router_for_source(packet_src_ip)
        identity = _resolve_identity(router, username)
        session = (
            RadiusSession.objects.select_for_update()
            .select_related(
                "tenant",
                "router",
                "subscriber",
                "subscription",
                "voucher__batch",
            )
            .filter(
                tenant=router.tenant,
                router=router,
                acct_session_id=acct_session_id,
                username=username,
            )
            .first()
        )
        if not session:
            started_at = event_at
            if status_type != RadiusAccountingEvent.StatusType.START and session_seconds:
                started_at = event_at - timedelta(seconds=session_seconds)
            session = RadiusSession.objects.create(
                tenant=router.tenant,
                router=router,
                subscriber=identity["subscriber"],
                subscription=identity["subscription"],
                voucher=identity["voucher"],
                identity_type=identity["identity_type"],
                identity_key=identity["identity_key"],
                username=username,
                acct_session_id=acct_session_id,
                acct_unique_session_id=str(payload.get("acct_unique_session_id") or "")[:128],
                framed_ip_address=str(payload.get("framed_ip_address") or "") or None,
                calling_station_id=str(payload.get("calling_station_id") or "")[:64],
                nas_port_id=str(payload.get("nas_port_id") or "")[:128],
                service_type=str(payload.get("service_type") or "")[:64],
                started_at=started_at,
                last_update_at=event_at,
                last_rate_limit=_rate_limit(identity, event_at),
            )

        key = _event_key(
            router,
            username,
            acct_session_id,
            status_type,
            input_bytes,
            output_bytes,
            session_seconds,
            terminate_cause,
        )
        if RadiusAccountingEvent.objects.filter(event_key=key).exists():
            return session, False

        input_delta = _delta(input_bytes, session.input_bytes)
        output_delta = _delta(output_bytes, session.output_bytes)
        seconds_delta = _delta(session_seconds, session.session_seconds)

        session.acct_unique_session_id = (
            str(payload.get("acct_unique_session_id") or session.acct_unique_session_id)[:128]
        )
        session.framed_ip_address = str(payload.get("framed_ip_address") or "") or None
        session.calling_station_id = str(payload.get("calling_station_id") or "")[:64]
        session.nas_port_id = str(payload.get("nas_port_id") or "")[:128]
        session.service_type = str(payload.get("service_type") or "")[:64]
        session.input_bytes = input_bytes
        session.output_bytes = output_bytes
        session.session_seconds = session_seconds
        session.last_update_at = event_at
        if status_type == RadiusAccountingEvent.StatusType.START:
            session.status = RadiusSession.Status.ACTIVE
            session.started_at = session.started_at or event_at
            session.stopped_at = None
            session.terminate_cause = ""
        elif status_type == RadiusAccountingEvent.StatusType.STOP:
            session.status = RadiusSession.Status.STOPPED
            session.stopped_at = event_at
            session.terminate_cause = terminate_cause
        session.save()

        try:
            RadiusAccountingEvent.objects.create(
                tenant=router.tenant,
                router=router,
                session=session,
                event_key=key,
                status_type=status_type,
                event_at=event_at,
                input_bytes=input_bytes,
                output_bytes=output_bytes,
                session_seconds=session_seconds,
                terminate_cause=terminate_cause,
                raw_payload={str(key): str(value) for key, value in payload.items()},
            )
        except IntegrityError:
            return session, False

        _record_identity_usage(
            session,
            input_delta=input_delta,
            output_delta=output_delta,
            at=event_at,
        )
        _update_aggregates(
            session,
            input_delta=input_delta,
            output_delta=output_delta,
            seconds_delta=seconds_delta,
            at=event_at,
        )
        should_evaluate_policy = (
            session.status == RadiusSession.Status.ACTIVE
            and (input_delta > 0 or output_delta > 0)
        )

    if should_evaluate_policy:
        from .control import refresh_session_policy

        refresh_session_policy(session.id)
    return session, True


def cleanup_old_accounting_data(*, raw_days: int = 365, health_days: int = 30) -> dict:
    from networking.models import RouterHealthSample

    now = timezone.now()
    events_deleted, _ = RadiusAccountingEvent.objects.filter(
        received_at__lt=now - timedelta(days=raw_days)
    ).delete()
    health_deleted, _ = RouterHealthSample.objects.filter(
        sampled_at__lt=now - timedelta(days=health_days)
    ).delete()
    return {
        "accounting_events_deleted": events_deleted,
        "health_samples_deleted": health_deleted,
    }
