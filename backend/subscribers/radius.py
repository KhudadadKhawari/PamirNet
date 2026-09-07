from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from networking.models import Router
from vouchers.models import Voucher
from vouchers.policy import calculate_voucher_effective_policy
from vouchers.services import activate_voucher

from .models import Subscriber, SubscriberCredential, Subscription, UsagePolicyStage
from .policy import calculate_effective_policy
from .services import add_calendar_duration, normalize_mac


@dataclass
class RadiusAuthorization:
    password: str
    rate_limit: str
    session_timeout: int
    simultaneous_sessions: int | None


class RadiusReject(Exception):
    pass


def _router_for_source(packet_src_ip: str) -> Router:
    try:
        return Router.objects.select_related("tenant").get(
            tunnel_ip=packet_src_ip,
            enabled=True,
        )
    except Router.DoesNotExist as exc:
        raise RadiusReject("Unknown NAS") from exc


def _rate_limit(upload_speed_mbps: int, download_speed_mbps: int) -> str:
    return f"{upload_speed_mbps}M/{download_speed_mbps}M"


def _subscriber_authorization(credential: SubscriberCredential) -> RadiusAuthorization:
    subscriber = credential.subscriber
    if subscriber.status not in {
        Subscriber.Status.ACTIVE,
        Subscriber.Status.QUOTA_EXHAUSTED,
    }:
        raise RadiusReject("Subscriber is not active")

    subscription = (
        Subscription.objects.select_related("package", "tenant")
        .select_for_update()
        .filter(subscriber=subscriber, status=Subscription.Status.ACTIVE)
        .order_by("-started_at")
        .first()
    )
    now = timezone.now()
    if not subscription:
        raise RadiusReject("No active subscription")
    if subscription.expires_at <= now:
        subscription.status = Subscription.Status.EXPIRED
        subscription.save(update_fields=["status", "updated_at"])
        subscriber.status = Subscriber.Status.EXPIRED
        subscriber.save(update_fields=["status", "updated_at"])
        raise RadiusReject("Subscription expired")
    if not subscription.package.enabled:
        raise RadiusReject("Package disabled")

    effective = calculate_effective_policy(subscription, at=now)
    if effective.blocked:
        if subscriber.status != Subscriber.Status.QUOTA_EXHAUSTED:
            subscriber.status = Subscriber.Status.QUOTA_EXHAUSTED
            subscriber.save(update_fields=["status", "updated_at"])
        raise RadiusReject("Usage quota exhausted")
    if subscriber.status == Subscriber.Status.QUOTA_EXHAUSTED:
        subscriber.status = Subscriber.Status.ACTIVE
        subscriber.save(update_fields=["status", "updated_at"])

    return RadiusAuthorization(
        password=credential.get_password(),
        rate_limit=_rate_limit(
            effective.upload_speed_mbps,
            effective.download_speed_mbps,
        ),
        session_timeout=int((subscription.expires_at - now).total_seconds()),
        simultaneous_sessions=subscription.package.simultaneous_sessions,
    )


def _voucher_authorization(voucher: Voucher) -> RadiusAuthorization:
    now = timezone.now()
    if not voucher.batch.enabled or not voucher.package.enabled:
        raise RadiusReject("Voucher package or batch disabled")
    if voucher.status not in {Voucher.Status.GENERATED, Voucher.Status.ACTIVE}:
        raise RadiusReject("Voucher is not active")

    if voucher.status == Voucher.Status.ACTIVE:
        if not voucher.expires_at or voucher.expires_at <= now:
            voucher.status = Voucher.Status.EXPIRED
            voucher.save(update_fields=["status", "updated_at"])
            raise RadiusReject("Voucher expired")
        effective = calculate_voucher_effective_policy(voucher, at=now)
        if effective.blocked:
            permanently_consumed = any(
                match["scope"] == "subscription"
                and match["action"] == UsagePolicyStage.Action.BLOCK
                for match in effective.matches
            )
            if permanently_consumed:
                voucher.status = Voucher.Status.CONSUMED
                voucher.save(update_fields=["status", "updated_at"])
            raise RadiusReject("Voucher usage quota exhausted")
        expires_at = voucher.expires_at
    else:
        effective = calculate_voucher_effective_policy(voucher, at=now)
        expires_at = add_calendar_duration(
            now,
            voucher.package.duration_value,
            voucher.package.duration_unit,
        )

    return RadiusAuthorization(
        password=voucher.get_password(),
        rate_limit=_rate_limit(
            effective.upload_speed_mbps,
            effective.download_speed_mbps,
        ),
        session_timeout=max(1, int((expires_at - now).total_seconds())),
        simultaneous_sessions=voucher.batch.simultaneous_sessions,
    )


def authorize_radius(
    *,
    packet_src_ip: str,
    username: str,
    calling_station_id: str = "",
) -> RadiusAuthorization:
    with transaction.atomic():
        router = _router_for_source(packet_src_ip)
        credential = (
            SubscriberCredential.objects.select_related("subscriber")
            .select_for_update()
            .filter(tenant=router.tenant, username=username)
            .first()
        )
        if credential:
            authorization = _subscriber_authorization(credential)
            subscriber = credential.subscriber
            station = ""
            if calling_station_id:
                try:
                    station = normalize_mac(calling_station_id)
                except Exception as exc:
                    raise RadiusReject("Invalid station MAC") from exc
            if subscriber.mac_lock_mode == Subscriber.MacLockMode.MANUAL:
                if not station or station != subscriber.mac_address:
                    raise RadiusReject("MAC mismatch")
            if (
                subscriber.mac_lock_mode == Subscriber.MacLockMode.FIRST_LOGIN
                and subscriber.mac_address
                and station != subscriber.mac_address
            ):
                raise RadiusReject("MAC mismatch")
            return authorization

        voucher = (
            Voucher.objects.select_related("batch", "package")
            .select_for_update()
            .filter(tenant=router.tenant, username=username)
            .first()
        )
        if voucher:
            return _voucher_authorization(voucher)
        raise RadiusReject("Unknown RADIUS identity")


def freeradius_success_payload(authorization: RadiusAuthorization) -> dict:
    payload = {
        "control:Cleartext-Password": authorization.password,
        "reply:Mikrotik-Rate-Limit": authorization.rate_limit,
        "reply:Session-Timeout": str(authorization.session_timeout),
        "reply:Acct-Interim-Interval": "60",
    }
    if authorization.simultaneous_sessions is not None:
        payload["control:Simultaneous-Use"] = str(authorization.simultaneous_sessions)
    return payload


def freeradius_reject_payload() -> dict:
    return {
        "control:Auth-Type": "Reject",
        "reply:Reply-Message": "Access denied",
    }


@transaction.atomic
def record_successful_authentication(
    *,
    packet_src_ip: str,
    username: str,
    calling_station_id: str = "",
):
    router = _router_for_source(packet_src_ip)
    credential = SubscriberCredential.objects.select_related("subscriber").filter(
        tenant=router.tenant,
        username=username,
    ).first()
    if credential:
        subscriber = Subscriber.objects.select_for_update().get(pk=credential.subscriber_id)
        station = ""
        if calling_station_id:
            try:
                station = normalize_mac(calling_station_id)
            except Exception:
                station = ""
        changed = ["last_authenticated_at", "updated_at"]
        subscriber.last_authenticated_at = timezone.now()
        if station:
            subscriber.last_mac_address = station
            changed.append("last_mac_address")
            if (
                subscriber.mac_lock_mode == Subscriber.MacLockMode.FIRST_LOGIN
                and not subscriber.mac_address
            ):
                subscriber.mac_address = station
                changed.append("mac_address")
        subscriber.save(update_fields=changed)
        return subscriber

    voucher = Voucher.objects.filter(tenant=router.tenant, username=username).first()
    if not voucher:
        raise RadiusReject("Unknown RADIUS identity")
    try:
        return activate_voucher(voucher)
    except ValidationError as exc:
        raise RadiusReject(str(exc)) from exc
