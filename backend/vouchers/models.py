import uuid

from django.conf import settings
from django.db import models

from core.crypto import decrypt_secret, encrypt_secret
from core.models import Tenant
from subscribers.models import Package, UsagePolicy


class VoucherBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="voucher_batches")
    name = models.CharField(max_length=120)
    package = models.ForeignKey(
        Package,
        on_delete=models.PROTECT,
        related_name="voucher_batches",
    )
    quantity = models.PositiveIntegerField()
    username_length = models.PositiveSmallIntegerField(default=8)
    password_length = models.PositiveSmallIntegerField(default=6)
    simultaneous_sessions = models.PositiveSmallIntegerField(blank=True, null=True, default=1)
    enabled = models.BooleanField(default=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="generated_voucher_batches",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="unique_voucher_batch_name_per_tenant",
            )
        ]
        indexes = [models.Index(fields=["tenant", "enabled", "-created_at"])]

    def __str__(self):
        return f"{self.tenant.name}: {self.name}"


class Voucher(models.Model):
    class Status(models.TextChoices):
        GENERATED = "generated", "Generated"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        CONSUMED = "consumed", "Consumed"
        DISABLED = "disabled", "Disabled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="vouchers")
    batch = models.ForeignKey(
        VoucherBatch,
        on_delete=models.CASCADE,
        related_name="vouchers",
    )
    package = models.ForeignKey(
        Package,
        on_delete=models.PROTECT,
        related_name="vouchers",
    )
    username = models.CharField(max_length=32)
    password_cipher = models.TextField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.GENERATED,
    )
    activated_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    last_authenticated_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["username"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "username"],
                name="unique_voucher_username_per_tenant",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["batch", "status"]),
            models.Index(fields=["tenant", "username"]),
        ]

    def set_password(self, password: str):
        self.password_cipher = encrypt_secret(password)

    def get_password(self) -> str:
        return decrypt_secret(self.password_cipher)

    def __str__(self):
        return self.username


class VoucherUsageCounter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="voucher_usage_counters",
    )
    voucher = models.ForeignKey(
        Voucher,
        on_delete=models.CASCADE,
        related_name="usage_counters",
    )
    scope = models.CharField(max_length=16, choices=UsagePolicy.Scope.choices)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    bytes_used = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scope"]
        constraints = [
            models.UniqueConstraint(
                fields=["voucher", "scope"],
                name="unique_voucher_usage_counter_scope",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "scope"]),
            models.Index(fields=["period_end"]),
        ]

    def __str__(self):
        return f"{self.voucher.username}: {self.scope} {self.bytes_used} bytes"
