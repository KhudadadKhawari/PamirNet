import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("subscribers", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UsagePolicy",
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
                    "scope",
                    models.CharField(
                        choices=[
                            ("daily", "Daily"),
                            ("weekly", "Weekly"),
                            ("monthly", "Monthly"),
                            ("subscription", "Subscription period"),
                        ],
                        max_length=16,
                    ),
                ),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "package",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="usage_policies",
                        to="subscribers.package",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="usage_policies",
                        to="core.tenant",
                    ),
                ),
            ],
            options={"ordering": ["scope"]},
        ),
        migrations.CreateModel(
            name="UsagePolicyStage",
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
                ("threshold_gb", models.DecimalField(decimal_places=3, max_digits=12)),
                (
                    "action",
                    models.CharField(
                        choices=[("throttle", "Throttle"), ("block", "Block")],
                        max_length=16,
                    ),
                ),
                ("download_speed_mbps", models.PositiveIntegerField(blank=True, null=True)),
                ("upload_speed_mbps", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "policy",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stages",
                        to="subscribers.usagepolicy",
                    ),
                ),
            ],
            options={"ordering": ["threshold_gb"]},
        ),
        migrations.CreateModel(
            name="SubscriptionUsageCounter",
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
                    "scope",
                    models.CharField(
                        choices=[
                            ("daily", "Daily"),
                            ("weekly", "Weekly"),
                            ("monthly", "Monthly"),
                            ("subscription", "Subscription period"),
                        ],
                        max_length=16,
                    ),
                ),
                ("period_start", models.DateTimeField()),
                ("period_end", models.DateTimeField()),
                ("bytes_used", models.PositiveBigIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "subscription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="usage_counters",
                        to="subscribers.subscription",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscription_usage_counters",
                        to="core.tenant",
                    ),
                ),
            ],
            options={"ordering": ["scope"]},
        ),
        migrations.AddConstraint(
            model_name="usagepolicy",
            constraint=models.UniqueConstraint(
                fields=("package", "scope"),
                name="unique_usage_policy_scope_per_package",
            ),
        ),
        migrations.AddIndex(
            model_name="usagepolicy",
            index=models.Index(
                fields=["tenant", "scope", "enabled"],
                name="usage_policy_tenant_scope_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="usagepolicystage",
            constraint=models.UniqueConstraint(
                fields=("policy", "threshold_gb"),
                name="unique_usage_stage_threshold_per_policy",
            ),
        ),
        migrations.AddConstraint(
            model_name="subscriptionusagecounter",
            constraint=models.UniqueConstraint(
                fields=("subscription", "scope"),
                name="unique_usage_counter_scope_per_subscription",
            ),
        ),
        migrations.AddIndex(
            model_name="subscriptionusagecounter",
            index=models.Index(
                fields=["tenant", "scope"],
                name="usage_counter_tenant_scope_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="subscriptionusagecounter",
            index=models.Index(
                fields=["period_end"],
                name="usage_counter_period_end_idx",
            ),
        ),
    ]
