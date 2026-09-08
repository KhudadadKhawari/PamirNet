import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0002_seed_permissions"),
        ("networking", "0002_routerhealthsample"),
        ("subscribers", "0002_usage_policy"),
        ("vouchers", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RadiusSession",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "identity_type",
                    models.CharField(
                        choices=[("subscriber", "Subscriber"), ("voucher", "Voucher")],
                        max_length=16,
                    ),
                ),
                ("identity_key", models.CharField(max_length=160)),
                ("username", models.CharField(max_length=120)),
                ("acct_session_id", models.CharField(max_length=128)),
                ("acct_unique_session_id", models.CharField(blank=True, max_length=128)),
                ("framed_ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("calling_station_id", models.CharField(blank=True, max_length=64)),
                ("nas_port_id", models.CharField(blank=True, max_length=128)),
                ("service_type", models.CharField(blank=True, max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("stopped", "Stopped")],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("last_update_at", models.DateTimeField(blank=True, null=True)),
                ("stopped_at", models.DateTimeField(blank=True, null=True)),
                ("input_bytes", models.PositiveBigIntegerField(default=0)),
                ("output_bytes", models.PositiveBigIntegerField(default=0)),
                ("session_seconds", models.PositiveBigIntegerField(default=0)),
                ("terminate_cause", models.CharField(blank=True, max_length=120)),
                ("last_rate_limit", models.CharField(blank=True, max_length=64)),
                ("last_control_action", models.CharField(blank=True, max_length=32)),
                ("last_control_at", models.DateTimeField(blank=True, null=True)),
                ("last_control_error", models.TextField(blank=True)),
                ("disconnect_requested_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "router",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="radius_sessions",
                        to="networking.router",
                    ),
                ),
                (
                    "subscriber",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="radius_sessions",
                        to="subscribers.subscriber",
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="radius_sessions",
                        to="subscribers.subscription",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="radius_sessions",
                        to="core.tenant",
                    ),
                ),
                (
                    "voucher",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="radius_sessions",
                        to="vouchers.voucher",
                    ),
                ),
            ],
            options={"ordering": ["-last_update_at", "-created_at"]},
        ),
        migrations.CreateModel(
            name="RadiusAccountingEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("event_key", models.CharField(max_length=64, unique=True)),
                (
                    "status_type",
                    models.CharField(
                        choices=[
                            ("Start", "Start"),
                            ("Interim-Update", "Interim-Update"),
                            ("Stop", "Stop"),
                        ],
                        max_length=24,
                    ),
                ),
                ("event_at", models.DateTimeField()),
                ("input_bytes", models.PositiveBigIntegerField(default=0)),
                ("output_bytes", models.PositiveBigIntegerField(default=0)),
                ("session_seconds", models.PositiveBigIntegerField(default=0)),
                ("terminate_cause", models.CharField(blank=True, max_length=120)),
                ("raw_payload", models.JSONField(default=dict)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                (
                    "router",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="radius_accounting_events",
                        to="networking.router",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="accounting_events",
                        to="accounting.radiussession",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="radius_accounting_events",
                        to="core.tenant",
                    ),
                ),
            ],
            options={"ordering": ["-received_at"]},
        ),
        migrations.CreateModel(
            name="UsageAggregate",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "granularity",
                    models.CharField(
                        choices=[("hour", "Hour"), ("day", "Day")],
                        max_length=8,
                    ),
                ),
                ("period_start", models.DateTimeField()),
                (
                    "identity_type",
                    models.CharField(
                        choices=[("subscriber", "Subscriber"), ("voucher", "Voucher")],
                        max_length=16,
                    ),
                ),
                ("identity_key", models.CharField(max_length=160)),
                ("identity_name", models.CharField(blank=True, max_length=160)),
                ("username", models.CharField(max_length=120)),
                ("input_bytes", models.PositiveBigIntegerField(default=0)),
                ("output_bytes", models.PositiveBigIntegerField(default=0)),
                ("session_seconds", models.PositiveBigIntegerField(default=0)),
                ("sample_count", models.PositiveBigIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "router",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="usage_aggregates",
                        to="networking.router",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="usage_aggregates",
                        to="core.tenant",
                    ),
                ),
            ],
            options={"ordering": ["-period_start"]},
        ),
        migrations.AddConstraint(
            model_name="radiussession",
            constraint=models.UniqueConstraint(
                fields=("tenant", "router", "acct_session_id", "username"),
                name="unique_radius_session_per_router_identity",
            ),
        ),
        migrations.AddIndex(
            model_name="radiussession",
            index=models.Index(
                fields=["tenant", "status", "-last_update_at"],
                name="acct_session_tenant_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="radiussession",
            index=models.Index(
                fields=["tenant", "username"], name="acct_session_username_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="radiussession",
            index=models.Index(fields=["router", "status"], name="acct_session_router_idx"),
        ),
        migrations.AddIndex(
            model_name="radiussession",
            index=models.Index(
                fields=["identity_type", "identity_key"],
                name="acct_session_identity_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="radiusaccountingevent",
            index=models.Index(
                fields=["tenant", "-received_at"], name="acct_event_tenant_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="radiusaccountingevent",
            index=models.Index(
                fields=["session", "-event_at"], name="acct_event_session_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="radiusaccountingevent",
            index=models.Index(
                fields=["router", "-received_at"], name="acct_event_router_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="usageaggregate",
            constraint=models.UniqueConstraint(
                fields=(
                    "tenant",
                    "router",
                    "granularity",
                    "period_start",
                    "identity_key",
                ),
                name="unique_usage_aggregate_bucket",
            ),
        ),
        migrations.AddIndex(
            model_name="usageaggregate",
            index=models.Index(
                fields=["tenant", "granularity", "-period_start"],
                name="usage_agg_tenant_period_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="usageaggregate",
            index=models.Index(
                fields=["tenant", "identity_type", "identity_key"],
                name="usage_agg_identity_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="usageaggregate",
            index=models.Index(
                fields=["router", "granularity", "-period_start"],
                name="usage_agg_router_period_idx",
            ),
        ),
    ]
