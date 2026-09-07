import subprocess

from django.db import models
from django.utils import timezone

from subscribers.models import Subscriber, UsagePolicy, UsagePolicyStage
from subscribers.policy import calculate_effective_policy
from vouchers.models import Voucher
from vouchers.policy import calculate_voucher_effective_policy

from .models import RadiusSession


class RadiusControlError(RuntimeError):
    pass


def _quoted(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _attributes(session: RadiusSession, *, rate_limit: str = "") -> str:
    values = [
        f'User-Name = "{_quoted(session.username)}"',
        f'Acct-Session-Id = "{_quoted(session.acct_session_id)}"',
    ]
    if session.framed_ip_address:
        values.append(f"Framed-IP-Address = {session.framed_ip_address}")
    if session.calling_station_id:
        values.append(
            f'Calling-Station-Id = "{_quoted(session.calling_station_id)}"'
        )
    if rate_limit:
        values.append(f'Mikrotik-Rate-Limit = "{_quoted(rate_limit)}"')
    return "\n".join(values) + "\n"


def _run_radclient(
    session: RadiusSession,
    *,
    packet_type: str,
    rate_limit: str = "",
) -> str:
    router = session.router
    command = [
        "radclient",
        "-x",
        f"{router.tunnel_ip}:3799",
        packet_type,
        router.get_radius_secret(),
    ]
    try:
        result = subprocess.run(
            command,
            input=_attributes(session, rate_limit=rate_limit),
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RadiusControlError(f"Unable to execute radclient: {exc}") from exc
    output = "\n".join(part for part in [result.stdout, result.stderr] if part).strip()
    if result.returncode != 0:
        raise RadiusControlError(output or f"radclient exited with {result.returncode}")
    return output


def _record_control(
    session: RadiusSession,
    *,
    action: str,
    error: str = "",
    rate_limit: str | None = None,
):
    session.last_control_action = action
    session.last_control_at = timezone.now()
    session.last_control_error = error[:2000]
    fields = [
        "last_control_action",
        "last_control_at",
        "last_control_error",
        "updated_at",
    ]
    if rate_limit is not None:
        session.last_rate_limit = rate_limit
        fields.append("last_rate_limit")
    if action == "disconnect" and not error:
        session.disconnect_requested_at = session.last_control_at
        fields.append("disconnect_requested_at")
    session.save(update_fields=fields)


def send_coa(session: RadiusSession, *, rate_limit: str) -> str:
    session = RadiusSession.objects.select_related("router").get(pk=session.pk)
    try:
        output = _run_radclient(session, packet_type="coa", rate_limit=rate_limit)
    except RadiusControlError as exc:
        _record_control(session, action="coa", error=str(exc))
        raise
    _record_control(session, action="coa", rate_limit=rate_limit)
    return output


def send_disconnect(session: RadiusSession) -> str:
    session = RadiusSession.objects.select_related("router").get(pk=session.pk)
    try:
        output = _run_radclient(session, packet_type="disconnect")
    except RadiusControlError as exc:
        _record_control(session, action="disconnect", error=str(exc))
        raise
    _record_control(session, action="disconnect")
    return output


def _effective_policy(session: RadiusSession):
    if session.subscriber_id and session.subscription_id:
        return calculate_effective_policy(session.subscription)
    if session.voucher_id:
        return calculate_voucher_effective_policy(session.voucher)
    return None


def _sync_identity_state(session: RadiusSession, policy):
    if session.subscriber_id and session.subscriber:
        subscriber = session.subscriber
        desired = (
            Subscriber.Status.QUOTA_EXHAUSTED
            if policy.blocked
            else Subscriber.Status.ACTIVE
        )
        if subscriber.status in {
            Subscriber.Status.ACTIVE,
            Subscriber.Status.QUOTA_EXHAUSTED,
        } and subscriber.status != desired:
            subscriber.status = desired
            subscriber.save(update_fields=["status", "updated_at"])

    if session.voucher_id and session.voucher and policy.blocked:
        permanently_consumed = any(
            match.get("scope") == UsagePolicy.Scope.SUBSCRIPTION
            and match.get("action") == UsagePolicyStage.Action.BLOCK
            for match in policy.matches
        )
        if permanently_consumed and session.voucher.status == Voucher.Status.ACTIVE:
            session.voucher.status = Voucher.Status.CONSUMED
            session.voucher.save(update_fields=["status", "updated_at"])


def refresh_session_policy(session_id) -> dict:
    session = (
        RadiusSession.objects.select_related(
            "router",
            "subscriber",
            "subscription__package",
            "voucher__package",
        )
        .filter(pk=session_id, status=RadiusSession.Status.ACTIVE)
        .first()
    )
    if not session:
        return {"action": "none", "reason": "session_not_active"}
    policy = _effective_policy(session)
    if not policy:
        return {"action": "none", "reason": "identity_not_resolved"}

    _sync_identity_state(session, policy)
    if policy.blocked:
        try:
            send_disconnect(session)
            return {"action": "disconnect", "reason": "policy_blocked"}
        except RadiusControlError as exc:
            return {"action": "error", "reason": str(exc)}

    rate_limit = f"{policy.upload_speed_mbps}M/{policy.download_speed_mbps}M"
    if rate_limit == session.last_rate_limit:
        return {"action": "none", "rate_limit": rate_limit}
    try:
        send_coa(session, rate_limit=rate_limit)
        return {"action": "coa", "rate_limit": rate_limit}
    except RadiusControlError as coa_error:
        # RouterOS deployments vary in how they apply rate updates. Falling
        # back to Disconnect forces a clean re-authentication with the new policy.
        try:
            send_disconnect(session)
            return {
                "action": "disconnect",
                "reason": "coa_failed",
                "coa_error": str(coa_error),
            }
        except RadiusControlError as disconnect_error:
            return {
                "action": "error",
                "reason": str(disconnect_error),
                "coa_error": str(coa_error),
            }


def disconnect_subscriber_sessions(subscriber) -> int:
    sessions = list(
        RadiusSession.objects.filter(
            tenant=subscriber.tenant,
            subscriber=subscriber,
            status=RadiusSession.Status.ACTIVE,
        ).select_related("router")
    )
    sent = 0
    for session in sessions:
        try:
            send_disconnect(session)
            sent += 1
        except RadiusControlError:
            continue
    return sent


def refresh_package_sessions(package) -> int:
    sessions = RadiusSession.objects.filter(
        tenant=package.tenant,
        status=RadiusSession.Status.ACTIVE,
    ).filter(
        models.Q(subscription__package=package) | models.Q(voucher__package=package)
    )
    refreshed = 0
    for session_id in sessions.values_list("id", flat=True):
        result = refresh_session_policy(session_id)
        if result.get("action") in {"coa", "disconnect"}:
            refreshed += 1
    return refreshed
