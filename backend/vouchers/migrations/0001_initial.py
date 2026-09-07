import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0002_seed_permissions"),
        ("subscribers", "0002_usage_policy"),
    ]

    operations = [
        migrations.CreateModel(
            name="VoucherBatch",
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
                ("name", models.CharField(max_length=120)),
                ("quantity", models.PositiveIntegerField()),
                ("username_length", models.PositiveSmallIntegerField(default=8)),
                ("password_length", models.PositiveSmallIntegerField(default=6)),
                (
                    "simultaneous_sessions",
                    models.PositiveSmallIntegerField(blank=True, default=1, null=True),
                ),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "generated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="generated_voucher_batches",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "package",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="voucher_batches",
                        to="subscribers.package",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="voucher_batches",
                        to="core.tenant",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Voucher",
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
                ("username", models.CharField(max_length=32)),
                ("password_cipher", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("generated", "Generated"),
                            ("active", "Active"),
                            ("expired", "Expired"),
                            ("consumed", "Consumed"),
                            ("disabled", "Disabled"),
                        ],
                        default="generated",
                        max_length=16,
                    ),
                ),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("last_authenticated_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "batch",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="vouchers",
                        to="vouchers.voucherbatch",
                    ),
                ),
                (
                    "package",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="vouchers",
                        to="subscribers.package",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="vouchers",
                        to="core.tenant",
                    ),
                ),
            ],
            options={"ordering": ["username"]},
        ),
        migrations.CreateModel(
            name="VoucherUsageCounter",
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
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="voucher_usage_counters",
                        to="core.tenant",
                    ),
                ),
                (
                    "voucher",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="usage_counters",
                        to="vouchers.voucher",
                    ),
                ),
            ],
            options={"ordering": ["scope"]},
        ),
        migrations.AddConstraint(
            model_name="voucherbatch",
            constraint=models.UniqueConstraint(
                fields=("tenant", "name"),
                name="unique_voucher_batch_name_per_tenant",
            ),
        ),
        migrations.AddIndex(
            model_name="voucherbatch",
            index=models.Index(
                fields=["tenant", "enabled", "-created_at"],
                name="voucher_bat_tenant_88bd7f_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="voucher",
            constraint=models.UniqueConstraint(
                fields=("tenant", "username"),
                name="unique_voucher_username_per_tenant",
            ),
        ),
        migrations.AddIndex(
            model_name="voucher",
            index=models.Index(fields=["tenant", "status"], name="voucher_tenant_status_idx"),
        ),
        migrations.AddIndex(
            model_name="voucher",
            index=models.Index(fields=["batch", "status"], name="voucher_batch_status_idx"),
        ),
        migrations.AddIndex(
            model_name="voucher",
            index=models.Index(fields=["tenant", "username"], name="voucher_tenant_user_idx"),
        ),
        migrations.AddConstraint(
            model_name="voucherusagecounter",
            constraint=models.UniqueConstraint(
                fields=("voucher", "scope"),
                name="unique_voucher_usage_counter_scope",
            ),
        ),
        migrations.AddIndex(
            model_name="voucherusagecounter",
            index=models.Index(fields=["tenant", "scope"], name="voucher_usage_tenant_idx"),
        ),
        migrations.AddIndex(
            model_name="voucherusagecounter",
            index=models.Index(fields=["period_end"], name="voucher_usage_period_idx"),
        ),
    ]
