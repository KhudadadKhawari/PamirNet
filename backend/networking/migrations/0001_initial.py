import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [("core", "0002_seed_permissions")]

    operations = [
        migrations.CreateModel(
            name="Router",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=120)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("tunnel_ip", models.GenericIPAddressField(protocol="IPv4", unique=True)),
                ("wireguard_public_key", models.CharField(max_length=64, unique=True)),
                (
                    "api_protocol",
                    models.CharField(
                        choices=[
                            ("api", "RouterOS API (WireGuard)"),
                            ("api_ssl", "RouterOS API SSL"),
                            ("rest", "RouterOS REST"),
                        ],
                        default="api",
                        max_length=16,
                    ),
                ),
                ("api_port", models.PositiveIntegerField(default=8728)),
                ("api_username", models.CharField(max_length=120)),
                ("api_password_cipher", models.TextField()),
                ("api_tls_verify", models.BooleanField(default=False)),
                ("radius_secret_cipher", models.TextField()),
                ("enabled", models.BooleanField(default=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("online", "Online"),
                            ("offline", "Offline"),
                            ("disabled", "Disabled"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("routeros_version", models.CharField(blank=True, max_length=80)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                ("latency_ms", models.FloatField(blank=True, null=True)),
                ("packet_loss_percent", models.FloatField(blank=True, null=True)),
                ("uptime_seconds", models.BigIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="routers",
                        to="core.tenant",
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddConstraint(
            model_name="router",
            constraint=models.UniqueConstraint(
                fields=("tenant", "name"), name="unique_router_name_per_tenant"
            ),
        ),
        migrations.AddIndex(
            model_name="router",
            index=models.Index(fields=["tenant", "enabled"], name="networking_r_tenant__99921b_idx"),
        ),
        migrations.AddIndex(
            model_name="router",
            index=models.Index(fields=["tenant", "status"], name="networking_r_tenant__75fb10_idx"),
        ),
    ]
