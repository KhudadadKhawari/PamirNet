import uuid

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Tenant(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=80, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    timezone = models.CharField(max_length=64, default="Asia/Kabul")
    currency = models.CharField(max_length=3, default="AFN")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PamirPermission(models.Model):
    code = models.CharField(primary_key=True, max_length=64)
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=40)

    class Meta:
        ordering = ["category", "code"]

    def __str__(self):
        return self.code


class Role(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="roles")
    name = models.CharField(max_length=80)
    is_system = models.BooleanField(default=False)
    is_owner = models.BooleanField(default=False)
    permissions = models.ManyToManyField(PamirPermission, blank=True, related_name="roles")

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="unique_role_name_per_tenant")
        ]

    def __str__(self):
        return f"{self.tenant.slug}:{self.name}"


class TenantMembership(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pamirnet_memberships")
    is_active = models.BooleanField(default=True)
    roles = models.ManyToManyField(Role, blank=True, related_name="memberships")

    class Meta:
        ordering = ["user__email"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "user"],
                name="unique_user_membership_per_tenant",
            )
        ]

    def __str__(self):
        return f"{self.user_id}@{self.tenant.slug}"


class ImpersonationSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="impersonation_sessions")
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="impersonation_sessions",
    )
    reason = models.CharField(max_length=255, blank=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]


class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.PROTECT, related_name="audit_logs", null=True, blank=True
    )
    actor = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="pamirnet_audit_logs", null=True, blank=True
    )
    impersonation = models.ForeignKey(
        ImpersonationSession,
        on_delete=models.PROTECT,
        related_name="audit_logs",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=80, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "-created_at"], name="audit_tenant_created_idx"),
            models.Index(fields=["action", "-created_at"], name="audit_action_created_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Audit logs are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit logs are append-only.")
