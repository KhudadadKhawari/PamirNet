import secrets
import string

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from subscribers.models import SubscriberCredential
from subscribers.services import add_calendar_duration

from .models import Voucher, VoucherBatch

USERNAME_LENGTH = 8
PASSWORD_LENGTH = 6


def _numeric(length: int) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


def _existing_usernames(tenant) -> set[str]:
    subscribers = SubscriberCredential.objects.filter(tenant=tenant).values_list(
        "username", flat=True
    )
    vouchers = Voucher.objects.filter(tenant=tenant).values_list("username", flat=True)
    return set(subscribers).union(vouchers)


@transaction.atomic
def generate_voucher_batch(
    *,
    tenant,
    package,
    name: str,
    quantity: int,
    simultaneous_sessions: int | None,
    generated_by=None,
) -> VoucherBatch:
    if package.tenant_id != tenant.id:
        raise ValidationError("Package does not belong to this tenant.")
    if not package.enabled:
        raise ValidationError("The selected package is disabled.")
    if quantity < 1:
        raise ValidationError("Quantity must be at least 1.")

    batch = VoucherBatch.objects.create(
        tenant=tenant,
        name=name.strip(),
        package=package,
        quantity=quantity,
        username_length=USERNAME_LENGTH,
        password_length=PASSWORD_LENGTH,
        simultaneous_sessions=simultaneous_sessions,
        generated_by=generated_by,
    )

    used = _existing_usernames(tenant)
    vouchers = []
    attempts = 0
    while len(vouchers) < quantity:
        attempts += 1
        if attempts > quantity * 100 + 1000:
            raise ValidationError("Unable to generate enough unique voucher usernames.")
        username = _numeric(USERNAME_LENGTH)
        if username in used:
            continue
        used.add(username)
        voucher = Voucher(
            tenant=tenant,
            batch=batch,
            package=package,
            username=username,
        )
        voucher.set_password(_numeric(PASSWORD_LENGTH))
        vouchers.append(voucher)
    Voucher.objects.bulk_create(vouchers, batch_size=1000)
    return batch


@transaction.atomic
def activate_voucher(voucher: Voucher) -> Voucher:
    voucher = Voucher.objects.select_for_update().select_related("package").get(pk=voucher.pk)
    now = timezone.now()
    if voucher.status == Voucher.Status.GENERATED:
        voucher.status = Voucher.Status.ACTIVE
        voucher.activated_at = now
        voucher.expires_at = add_calendar_duration(
            now,
            voucher.package.duration_value,
            voucher.package.duration_unit,
        )
        voucher.last_authenticated_at = now
        voucher.save(
            update_fields=[
                "status",
                "activated_at",
                "expires_at",
                "last_authenticated_at",
                "updated_at",
            ]
        )
    elif voucher.status == Voucher.Status.ACTIVE:
        if voucher.expires_at and voucher.expires_at <= now:
            voucher.status = Voucher.Status.EXPIRED
            voucher.save(update_fields=["status", "updated_at"])
            raise ValidationError("Voucher expired.")
        voucher.last_authenticated_at = now
        voucher.save(update_fields=["last_authenticated_at", "updated_at"])
    else:
        raise ValidationError("Voucher is not active.")
    return voucher


@transaction.atomic
def disable_batch(batch: VoucherBatch) -> int:
    batch = VoucherBatch.objects.select_for_update().get(pk=batch.pk)
    batch.enabled = False
    batch.save(update_fields=["enabled", "updated_at"])
    return batch.vouchers.filter(
        status__in=[Voucher.Status.GENERATED, Voucher.Status.ACTIVE]
    ).update(status=Voucher.Status.DISABLED, updated_at=timezone.now())
