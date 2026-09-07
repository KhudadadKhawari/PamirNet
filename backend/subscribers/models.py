import uuid

from django.db import models

from core.models import Tenant
from core.crypto import decrypt_secret, encrypt_secret


class Package(models.Model):
    class DurationUnit(models.TextChoices):
        DAY = "day", "Day"
        WEEK = "week", "Week"
        MONTH = "month", "Month"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="packages")
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)
    duration_value = models.PositiveIntegerField(default=1)
    duration_unit = models.CharField(
        max_length=16,
        choices=DurationUnit.choices,
        default=DurationUnit.MONTH,
    )
    download_speed_mbps = models.PositiveIntegerField()
    upload_speed_mbps = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    simultaneous_sessions = models.PositiveSmallIntegerField(default=1)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="unique_package_name_per_tenant",
            )
        ]
        indexes = [models.Index(fields=["tenant", "enabled"])]

    def __str__(self):
        return f"{self.tenant.name}: {self.name}"


class Subscriber(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DISABLED = "disabled", "Disabled"
        EXPIRED = "expired", "Expired"
        SUSPENDED = "suspended", "Suspended"
        QUOTA_EXHAUSTED = "quota_exhausted", "Quota Exhausted"

    class MacLockMode(models.TextChoices):
        NONE = "none", "No MAC lock"
        MANUAL = "manual", "Manual MAC"
        FIRST_LOGIN = "first_login", "Bind on first login"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="subscribers")
    name = models.CharField(max_length=160)
    phone = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    mac_lock_mode = models.CharField(
        max_length=16,
        choices=MacLockMode.choices,
        default=MacLockMode.NONE,
    )
    mac_address = models.CharField(max_length=17, blank=True)
    last_mac_address = models.CharField(max_length=17, blank=True)
    last_authenticated_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "name"]),
        ]

    def __str__(self):
        return f"{self.tenant.name}: {self.name}"


class SubscriberCredential(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="subscriber_credentials",
    )
    subscriber = models.OneToOneField(
        Subscriber,
        on_delete=models.CASCADE,
        related_name="credential",
    )
    username = models.CharField(max_length=120)
    password_cipher = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["username"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "username"],
                name="unique_radius_username_per_tenant",
            )
        ]
        indexes = [models.Index(fields=["tenant", "username"])]

    def set_password(self, password: str):
        self.password_cipher = encrypt_secret(password)

    def get_password(self) -> str:
        return decrypt_secret(self.password_cipher)

    def __str__(self):
        return self.username


class Subscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="subscriptions")
    subscriber = models.ForeignKey(
        Subscriber,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    package = models.ForeignKey(
        Package,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    duration_value = models.PositiveIntegerField()
    duration_unit = models.CharField(max_length=16, choices=Package.DurationUnit.choices)
    started_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["subscriber"],
                condition=models.Q(status="active"),
                name="one_active_subscription_per_subscriber",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["subscriber", "status"]),
            models.Index(fields=["expires_at", "status"]),
        ]

    def __str__(self):
        return f"{self.subscriber.name}: {self.package.name}"
