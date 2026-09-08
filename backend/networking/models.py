import uuid

from django.db import models

from core.models import Tenant


class Router(models.Model):
    class APIProtocol(models.TextChoices):
        API = "api", "RouterOS API (WireGuard)"
        API_SSL = "api_ssl", "RouterOS API SSL"
        REST = "rest", "RouterOS REST"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ONLINE = "online", "Online"
        OFFLINE = "offline", "Offline"
        DISABLED = "disabled", "Disabled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="routers")
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)

    tunnel_ip = models.GenericIPAddressField(protocol="IPv4", unique=True)
    wireguard_public_key = models.CharField(max_length=64, unique=True)

    api_protocol = models.CharField(
        max_length=16,
        choices=APIProtocol.choices,
        default=APIProtocol.API,
    )
    api_port = models.PositiveIntegerField(default=8728)
    api_username = models.CharField(max_length=120)
    api_password_cipher = models.TextField()
    api_tls_verify = models.BooleanField(default=False)
    radius_secret_cipher = models.TextField()

    enabled = models.BooleanField(default=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    routeros_version = models.CharField(max_length=80, blank=True)
    last_seen_at = models.DateTimeField(blank=True, null=True)
    latency_ms = models.FloatField(blank=True, null=True)
    packet_loss_percent = models.FloatField(blank=True, null=True)
    uptime_seconds = models.BigIntegerField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="unique_router_name_per_tenant",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "enabled"]),
            models.Index(fields=["tenant", "status"]),
        ]

    def __str__(self):
        return f"{self.tenant.name}: {self.name}"

    def set_api_password(self, value: str):
        from .crypto import encrypt_secret

        self.api_password_cipher = encrypt_secret(value)

    def get_api_password(self) -> str:
        from .crypto import decrypt_secret

        return decrypt_secret(self.api_password_cipher)

    def set_radius_secret(self, value: str):
        from .crypto import encrypt_secret

        self.radius_secret_cipher = encrypt_secret(value)

    def get_radius_secret(self) -> str:
        from .crypto import decrypt_secret

        return decrypt_secret(self.radius_secret_cipher)


class RouterHealthSample(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="router_health_samples",
    )
    router = models.ForeignKey(
        Router,
        on_delete=models.CASCADE,
        related_name="health_samples",
    )
    sampled_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=16, choices=Router.Status.choices)
    latency_ms = models.FloatField(blank=True, null=True)
    packet_loss_percent = models.FloatField(blank=True, null=True)
    uptime_seconds = models.BigIntegerField(blank=True, null=True)

    class Meta:
        ordering = ["-sampled_at"]
        indexes = [
            models.Index(fields=["tenant", "-sampled_at"]),
            models.Index(fields=["router", "-sampled_at"]),
        ]

    def __str__(self):
        return f"{self.router.name}: {self.status} @ {self.sampled_at}"
