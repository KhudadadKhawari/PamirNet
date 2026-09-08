import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("networking", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="RouterHealthSample",
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
                ("sampled_at", models.DateTimeField(auto_now_add=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("online", "Online"),
                            ("offline", "Offline"),
                            ("disabled", "Disabled"),
                        ],
                        max_length=16,
                    ),
                ),
                ("latency_ms", models.FloatField(blank=True, null=True)),
                ("packet_loss_percent", models.FloatField(blank=True, null=True)),
                ("uptime_seconds", models.BigIntegerField(blank=True, null=True)),
                (
                    "router",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="health_samples",
                        to="networking.router",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="router_health_samples",
                        to="core.tenant",
                    ),
                ),
            ],
            options={
                "ordering": ["-sampled_at"],
                "indexes": [
                    models.Index(
                        fields=["tenant", "-sampled_at"],
                        name="networking__tenant__2b59fa_idx",
                    ),
                    models.Index(
                        fields=["router", "-sampled_at"],
                        name="networking__router__266208_idx",
                    ),
                ],
            },
        )
    ]
