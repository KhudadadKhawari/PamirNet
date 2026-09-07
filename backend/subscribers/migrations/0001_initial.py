import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [("core", "0002_seed_permissions")]

    operations = [
        migrations.CreateModel(
            name="Package",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=120)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("duration_value", models.PositiveIntegerField(default=1)),
                ("duration_unit", models.CharField(choices=[("day", "Day"), ("week", "Week"), ("month", "Month")], default="month", max_length=16)),
                ("download_speed_mbps", models.PositiveIntegerField()),
                ("upload_speed_mbps", models.PositiveIntegerField()),
                ("price", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("simultaneous_sessions", models.PositiveSmallIntegerField(default=1)),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="packages", to="core.tenant")),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Subscriber",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("address", models.CharField(blank=True, max_length=255)),
                ("notes", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("active", "Active"), ("disabled", "Disabled"), ("expired", "Expired"), ("suspended", "Suspended"), ("quota_exhausted", "Quota Exhausted")], default="active", max_length=24)),
                ("mac_lock_mode", models.CharField(choices=[("none", "No MAC lock"), ("manual", "Manual MAC"), ("first_login", "Bind on first login")], default="none", max_length=16)),
                ("mac_address", models.CharField(blank=True, max_length=17)),
                ("last_mac_address", models.CharField(blank=True, max_length=17)),
                ("last_authenticated_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="subscribers", to="core.tenant")),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="SubscriberCredential",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("username", models.CharField(max_length=120)),
                ("password_cipher", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("subscriber", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="credential", to="subscribers.subscriber")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="subscriber_credentials", to="core.tenant")),
            ],
            options={"ordering": ["username"]},
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("duration_value", models.PositiveIntegerField()),
                ("duration_unit", models.CharField(choices=[("day", "Day"), ("week", "Week"), ("month", "Month")], max_length=16)),
                ("started_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("status", models.CharField(choices=[("active", "Active"), ("expired", "Expired"), ("closed", "Closed")], default="active", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("package", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subscriptions", to="subscribers.package")),
                ("subscriber", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="subscriptions", to="subscribers.subscriber")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="subscriptions", to="core.tenant")),
            ],
            options={"ordering": ["-started_at"]},
        ),
        migrations.AddConstraint(
            model_name="package",
            constraint=models.UniqueConstraint(fields=("tenant", "name"), name="unique_package_name_per_tenant"),
        ),
        migrations.AddIndex(model_name="package", index=models.Index(fields=["tenant", "enabled"], name="subscribers__tenant__4aa2db_idx")),
        migrations.AddIndex(model_name="subscriber", index=models.Index(fields=["tenant", "status"], name="subscribers__tenant__b82689_idx")),
        migrations.AddIndex(model_name="subscriber", index=models.Index(fields=["tenant", "name"], name="subscribers__tenant__9a1762_idx")),
        migrations.AddConstraint(
            model_name="subscribercredential",
            constraint=models.UniqueConstraint(fields=("tenant", "username"), name="unique_radius_username_per_tenant"),
        ),
        migrations.AddIndex(model_name="subscribercredential", index=models.Index(fields=["tenant", "username"], name="subscribers__tenant__0eaef6_idx")),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "active")), fields=("subscriber",), name="one_active_subscription_per_subscriber"),
        ),
        migrations.AddIndex(model_name="subscription", index=models.Index(fields=["tenant", "status"], name="subscribers__tenant__a6a2f0_idx")),
        migrations.AddIndex(model_name="subscription", index=models.Index(fields=["subscriber", "status"], name="subscribers__subscri_5ee021_idx")),
        migrations.AddIndex(model_name="subscription", index=models.Index(fields=["expires_at", "status"], name="subscribers__expires_9e9f41_idx")),
    ]
