from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from networking.models import Router

from .models import Subscriber, SubscriberCredential, Subscription
from .policy import calculate_effective_policy
from .services import normalize_mac


@dataclass
class RadiusAuthorization:
    password: str
    rate_limit: str
    session_timeout: int
    simultaneous_sessions: int


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


def authorize_radius(
    *,
    packet_src_ip: str,
    username: str,
    calling_station_id: str = "",
) -> RadiusAuthorization:
    expired = False
    quota_blocked = False
    authorization = None

    with transaction.atomic():
        router = _router_for_source(packet_src_ip)
        try:
            credential = (
                SubscriberCredential.objects.select_related("subscriber")
                .select_for_update()
                .get(tenant=router.tenant, username=username)
            )
        except SubscriberCredential.DoesNotExist as exc:
            raise RadiusReject("Unknown subscriber") from exc

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
            expired = True
        elif not subscription.package.enabled:
            raise RadiusReject("Package disabled")
        else:
            effective = calculate_effective_policy(subscription, at=now)
            if effective.blocked:
                if subscriber.status != Subscriber.Status.QUOTA_EXHAUSTED:
                    subscriber.status = Subscriber.Status.QUOTA_EXHAUSTED
                    subscriber.save(update_fields=["status", "updated_at"])
                quota_blocked = True
            else:
                if subscriber.status == Subscriber.Status.QUOTA_EXHAUSTED:
                    subscriber.status = Subscriber.Status.ACTIVE
                    subscriber.save(update_fields=["status", "updated_at"])

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

                seconds_remaining = int((subscription.expires_at - now).total_seconds())
                authorization = RadiusAuthorization(
                    password=credential.get_password(),
                    rate_limit=_rate_limit(
                        effective.upload_speed_mbps,
                        effective.download_speed_mbps,
                    ),
                    session_timeout=seconds_remaining,
                    simultaneous_sessions=subscription.package.simultaneous_sessions,
                )

    if expired:
        raise RadiusReject("Subscription expired")
    if quota_blocked:
        raise RadiusReject("Usage quota exhausted")
    if authorization is None:  # pragma: no cover - defensive
        raise RadiusReject("Unable to authorize subscriber")
    return authorization


def freeradius_success_payload(authorization: RadiusAuthorization) -> dict:
    return {
        "control:Cleartext-Password": authorization.password,
        "control:Simultaneous-Use": str(authorization.simultaneous_sessions),
        "reply:Mikrotik-Rate-Limit": authorization.rate_limit,
        "reply:Session-Timeout": str(authorization.session_timeout),
        "reply:Acct-Interim-Interval": "60",
    }


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
    try:
        credential = SubscriberCredential.objects.select_related("subscriber").get(
            tenant=router.tenant,
            username=username,
        )
    except SubscriberCredential.DoesNotExist as exc:
        raise RadiusReject("Unknown subscriber") from exc
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
