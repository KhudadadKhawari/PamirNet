from django.contrib import admin

from .models import Router


@admin.register(Router)
class RouterAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "tenant",
        "tunnel_ip",
        "api_protocol",
        "status",
        "enabled",
        "last_seen_at",
    )
    list_filter = ("status", "enabled", "api_protocol", "tenant")
    search_fields = ("name", "tenant__name", "tunnel_ip")
    readonly_fields = (
        "tunnel_ip",
        "wireguard_public_key",
        "api_password_cipher",
        "radius_secret_cipher",
        "status",
        "routeros_version",
        "last_seen_at",
        "latency_ms",
        "packet_loss_percent",
        "uptime_seconds",
        "created_at",
        "updated_at",
    )
