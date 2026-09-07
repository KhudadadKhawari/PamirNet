import calendar
import secrets
import string
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Package, Subscriber, SubscriberCredential, Subscription

USERNAME_DIGITS = 8
PASSWORD_LENGTH = 12


def normalize_mac(value: str | None) -> str:
    if not value:
        return ""
    compact = "".join(char for char in value if char.isalnum()).upper()
    if len(compact) != 12 or any(char not in string.hexdigits.upper() for char in compact):
        raise ValidationError("MAC address must contain 12 hexadecimal digits.")
    return ":".join(compact[index : index + 2] for index in range(0, 12, 2))


def add_calendar_duration(start, value: int, unit: str):
    if value < 1:
        raise ValidationError("Duration must be at least one unit.")
    if unit == Package.DurationUnit.DAY:
        return start + timedelta(days=value)
    if unit == Package.DurationUnit.WEEK:
        return start + timedelta(weeks=value)
    if unit == Package.DurationUnit.MONTH:
        month_index = start.month - 1 + value
        year = start.year + month_index // 12
        month = month_index % 12 + 1
        day = min(start.day, calendar.monthrange(year, month)[1])
        return start.replace(year=year, month=month, day=day)
    raise ValidationError("Unsupported duration unit.")


def _generate_username(tenant) -> str:
    for _ in range(100):
        username = "".join(secrets.choice(string.digits) for _ in range(USERNAME_DIGITS))
        if not SubscriberCredential.objects.filter(tenant=tenant, username=username).exists():
            return username
    raise ValidationError("Unable to generate a unique subscriber username.")


def generate_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(PASSWORD_LENGTH))


def _validate_mac_fields(mac_lock_mode: str, mac_address: str | None) -> str:
    normalized = normalize_mac(mac_address)
    if mac_lock_mode == Subscriber.MacLockMode.MANUAL and not normalized:
        raise ValidationError("A MAC address is required for manual MAC locking.")
    if mac_lock_mode == Subscriber.MacLockMode.NONE:
        return ""
    return normalized


@transaction.atomic
def create_subscriber(*, tenant, data: dict):
    username = str(data.pop("username", "") or "").strip()
    password = str(data.pop("password", "") or "")
    package = data.pop("package", None)
    duration_value = data.pop("duration_value", None)
    duration_unit = data.pop("duration_unit", None)

    if not username:
        username = _generate_username(tenant)
    generated_password = ""
    if not password:
        password = generate_password()
        generated_password = password

    if SubscriberCredential.objects.filter(tenant=tenant, username=username).exists():
        raise ValidationError("This subscriber username already exists for the tenant.")

    mac_mode = data.get("mac_lock_mode", Subscriber.MacLockMode.NONE)
    data["mac_address"] = _validate_mac_fields(mac_mode, data.get("mac_address"))
    subscriber = Subscriber.objects.create(tenant=tenant, **data)
    credential = SubscriberCredential(tenant=tenant, subscriber=subscriber, username=username)
    credential.set_password(password)
    credential.save()

    if package is not None:
        assign_package(
            subscriber=subscriber,
            package=package,
            duration_value=duration_value,
            duration_unit=duration_unit,
        )
    return subscriber, generated_password


@transaction.atomic
def assign_package(
    *,
    subscriber: Subscriber,
    package: Package,
    duration_value: int | None = None,
    duration_unit: str | None = None,
):
    subscriber = Subscriber.objects.select_for_update().get(pk=subscriber.pk)
    if package.tenant_id != subscriber.tenant_id:
        raise ValidationError("Package does not belong to this tenant.")
    if not package.enabled:
        raise ValidationError("The selected package is disabled.")

    value = duration_value or package.duration_value
    unit = duration_unit or package.duration_unit
    if unit not in Package.DurationUnit.values:
        raise ValidationError("Invalid duration unit.")

    now = timezone.now()
    Subscription.objects.filter(
        subscriber=subscriber,
        status=Subscription.Status.ACTIVE,
    ).update(status=Subscription.Status.CLOSED, updated_at=now)
    subscription = Subscription.objects.create(
        tenant=subscriber.tenant,
        subscriber=subscriber,
        package=package,
        duration_value=value,
        duration_unit=unit,
        started_at=now,
        expires_at=add_calendar_duration(now, value, unit),
        status=Subscription.Status.ACTIVE,
    )
    if subscriber.status != Subscriber.Status.ACTIVE:
        subscriber.status = Subscriber.Status.ACTIVE
        subscriber.save(update_fields=["status", "updated_at"])
    return subscription


@transaction.atomic
def renew_subscription(
    *,
    subscriber: Subscriber,
    duration_value: int | None = None,
    duration_unit: str | None = None,
):
    locked = Subscriber.objects.select_for_update().get(pk=subscriber.pk)
    latest = locked.subscriptions.select_related("package").order_by("-started_at").first()
    if not latest:
        raise ValidationError("Subscriber has no package to renew.")
    return assign_package(
        subscriber=locked,
        package=latest.package,
        duration_value=duration_value,
        duration_unit=duration_unit,
    )


def active_subscription(subscriber: Subscriber):
    subscription = (
        subscriber.subscriptions.select_related("package")
        .filter(status=Subscription.Status.ACTIVE)
        .order_by("-started_at")
        .first()
    )
    if subscription and subscription.expires_at <= timezone.now():
        expire_subscription(subscription)
        return None
    return subscription


@transaction.atomic
def expire_subscription(subscription: Subscription):
    subscription = Subscription.objects.select_for_update().select_related("subscriber").get(
        pk=subscription.pk
    )
    if subscription.status != Subscription.Status.ACTIVE:
        return subscription
    if subscription.expires_at > timezone.now():
        return subscription
    subscription.status = Subscription.Status.EXPIRED
    subscription.save(update_fields=["status", "updated_at"])
    subscriber = subscription.subscriber
    if subscriber.status == Subscriber.Status.ACTIVE:
        subscriber.status = Subscriber.Status.EXPIRED
        subscriber.save(update_fields=["status", "updated_at"])
    return subscription


def expire_due_subscriptions() -> int:
    due = list(
        Subscription.objects.filter(
            status=Subscription.Status.ACTIVE,
            expires_at__lte=timezone.now(),
        ).values_list("id", flat=True)
    )
    for subscription_id in due:
        subscription = Subscription.objects.get(pk=subscription_id)
        expire_subscription(subscription)
    return len(due)


@transaction.atomic
def update_subscriber(*, subscriber: Subscriber, data: dict):
    subscriber = Subscriber.objects.select_for_update().get(pk=subscriber.pk)
    mac_mode = data.get("mac_lock_mode", subscriber.mac_lock_mode)
    mac_value = data.get("mac_address", subscriber.mac_address)
    if "mac_lock_mode" in data or "mac_address" in data:
        data["mac_address"] = _validate_mac_fields(mac_mode, mac_value)
    for field, value in data.items():
        setattr(subscriber, field, value)
    subscriber.save()
    return subscriber


@transaction.atomic
def change_password(*, subscriber: Subscriber, password: str | None = None):
    password = password or generate_password()
    credential = SubscriberCredential.objects.select_for_update().get(subscriber=subscriber)
    credential.set_password(password)
    try:
        credential.save(update_fields=["password_cipher", "updated_at"])
    except IntegrityError as exc:  # pragma: no cover - defensive
        raise ValidationError("Unable to update subscriber password.") from exc
    return password
