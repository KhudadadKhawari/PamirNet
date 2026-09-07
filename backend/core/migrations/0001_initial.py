import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="PamirPermission",
            fields=[
                ("code", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=120)),
                ("category", models.CharField(max_length=40)),
            ],
            options={"ordering": ["category", "code"]},
        ),
        migrations.CreateModel(
            name="Tenant",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=160)),
                ("slug", models.SlugField(max_length=80, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("suspended", "Suspended")],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("timezone", models.CharField(default="Asia/Kabul", max_length=64)),
                ("currency", models.CharField(default="AFN", max_length=3)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Role",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=80)),
                ("is_system", models.BooleanField(default=False)),
                ("is_owner", models.BooleanField(default=False)),
                (
                    "permissions",
                    models.ManyToManyField(blank=True, related_name="roles", to="core.pamirpermission"),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="roles",
                        to="core.tenant",
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="TenantMembership",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "roles",
                    models.ManyToManyField(blank=True, related_name="memberships", to="core.role"),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="core.tenant",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pamirnet_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["user__email"]},
        ),
        migrations.CreateModel(
            name="ImpersonationSession",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("source_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                (
                    "actor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="impersonation_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="impersonation_sessions",
                        to="core.tenant",
                    ),
                ),
            ],
            options={"ordering": ["-started_at"]},
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("action", models.CharField(max_length=100)),
                ("target_type", models.CharField(blank=True, max_length=80)),
                ("target_id", models.CharField(blank=True, max_length=100)),
                ("source_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("before", models.JSONField(blank=True, default=dict)),
                ("after", models.JSONField(blank=True, default=dict)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="pamirnet_audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "impersonation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="audit_logs",
                        to="core.impersonationsession",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="audit_logs",
                        to="core.tenant",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="role",
            constraint=models.UniqueConstraint(
                fields=("tenant", "name"), name="unique_role_name_per_tenant"
            ),
        ),
        migrations.AddConstraint(
            model_name="tenantmembership",
            constraint=models.UniqueConstraint(
                fields=("tenant", "user"), name="unique_user_membership_per_tenant"
            ),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["tenant", "-created_at"], name="audit_tenant_created_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["action", "-created_at"], name="audit_action_created_idx"),
        ),
    ]
