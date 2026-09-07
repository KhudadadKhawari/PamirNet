import uuid

from django.db import models

from core.models import Tenant
from networking.models import Router


class RadiusSession(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        STOPPED = "stopped", "Stopped"

    class IdentityType(models.TextChoices):
        SUBSCRIBER = "subscriber", "Subscriber"
        VOUCHER = "voucher", "Voucher"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="radius_sessions")
    router = models.ForeignKey(Router, on_delete=models.CASCADE, related_name="radius_sessions")
    subscriber = models.ForeignKey(
        "subscribers.Subscriber",
        on_delete=models.SET_NULL,
        related_name="radius_sessions",
        blank=True,
        null=True,
    )
    subscription = models.ForeignKey(
        "subscribers.Subscription",
        on_delete=models.SET_NULL,
        related_name="radius_sessions",
        blank=True,
        null=True,
    )
    voucher = models.ForeignKey(
        "vouchers.Voucher",
        on_delete=models.SET_NULL,
        related_name="radius_sessions",
        blank=True,
        null=True,
    )
    identity_type = models.CharField(max_length=16, choices=IdentityType.choices)
    identity_key = models.CharField(max_length=160)
    username = models.CharField(max_length=120)

    acct_session_id = models.CharField(max_length=128)
    acct_unique_session_id = models.CharField(max_length=128, blank=True)
    framed_ip_address = models.GenericIPAddressField(blank=True, null=True)
    calling_station_id = models.CharField(max_length=64, blank=True)
    nas_port_id = models.CharField(max_length=128, blank=True)
    service_type = models.CharField(max_length=64, blank=True)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField(blank=True, null=True)
    last_update_at = models.DateTimeField(blank=True, null=True)
    stopped_at = models.DateTimeField(blank=True, null=True)
    input_bytes = models.PositiveBigIntegerField(default=0)
    output_bytes = models.PositiveBigIntegerField(default=0)
    session_seconds = models.PositiveBigIntegerField(default=0)
    terminate_cause = models.CharField(max_length=120, blank=True)

    last_rate_limit = models.CharField(max_length=64, blank=True)
    last_control_action = models.CharField(max_length=32, blank=True)
    last_control_at = models.DateTimeField(blank=True, null=True)
    last_control_error = models.TextField(blank=True)
    disconnect_requested_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_update_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "router", "acct_session_id", "username"],
                name="unique_radius_session_per_router_identity",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "-last_update_at"]),
            models.Index(fields=["tenant", "username"]),
            models.Index(fields=["router", "status"]),
            models.Index(fields=["identity_type", "identity_key"]),
        ]

    @property
    def total_bytes(self) -> int:
        return self.input_bytes + self.output_bytes

    def __str__(self):
        return f"{self.username} @ {self.router.name}: {self.status}"


class RadiusAccountingEvent(models.Model):
    class StatusType(models.TextChoices):
        START = "Start", "Start"
        INTERIM = "Interim-Update", "Interim-Update"
        STOP = "Stop", "Stop"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="radius_accounting_events",
    )
    router = models.ForeignKey(
        Router,
        on_delete=models.CASCADE,
        related_name="radius_accounting_events",
    )
    session = models.ForeignKey(
        RadiusSession,
        on_delete=models.CASCADE,
        related_name="accounting_events",
    )
    event_key = models.CharField(max_length=64, unique=True)
    status_type = models.CharField(max_length=24, choices=StatusType.choices)
    event_at = models.DateTimeField()
    input_bytes = models.PositiveBigIntegerField(default=0)
    output_bytes = models.PositiveBigIntegerField(default=0)
    session_seconds = models.PositiveBigIntegerField(default=0)
    terminate_cause = models.CharField(max_length=120, blank=True)
    raw_payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["tenant", "-received_at"]),
            models.Index(fields=["session", "-event_at"]),
            models.Index(fields=["router", "-received_at"]),
        ]

    def __str__(self):
        return f"{self.status_type}: {self.session.username} @ {self.event_at}"


class UsageAggregate(models.Model):
    class Granularity(models.TextChoices):
        HOUR = "hour", "Hour"
        DAY = "day", "Day"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="usage_aggregates")
    router = models.ForeignKey(Router, on_delete=models.CASCADE, related_name="usage_aggregates")
    granularity = models.CharField(max_length=8, choices=Granularity.choices)
    period_start = models.DateTimeField()
    identity_type = models.CharField(max_length=16, choices=RadiusSession.IdentityType.choices)
    identity_key = models.CharField(max_length=160)
    identity_name = models.CharField(max_length=160, blank=True)
    username = models.CharField(max_length=120)
    input_bytes = models.PositiveBigIntegerField(default=0)
    output_bytes = models.PositiveBigIntegerField(default=0)
    session_seconds = models.PositiveBigIntegerField(default=0)
    sample_count = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_start"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "tenant",
                    "router",
                    "granularity",
                    "period_start",
                    "identity_key",
                ],
                name="unique_usage_aggregate_bucket",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "granularity", "-period_start"]),
            models.Index(fields=["tenant", "identity_type", "identity_key"]),
            models.Index(fields=["router", "granularity", "-period_start"]),
        ]

    @property
    def total_bytes(self) -> int:
        return self.input_bytes + self.output_bytes

    def __str__(self):
        return f"{self.identity_key}: {self.granularity} {self.period_start}"
