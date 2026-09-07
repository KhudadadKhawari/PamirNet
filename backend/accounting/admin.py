from django.contrib import admin

from .models import RadiusAccountingEvent, RadiusSession, UsageAggregate


@admin.register(RadiusSession)
class RadiusSessionAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "tenant",
        "router",
        "identity_type",
        "status",
        "started_at",
        "last_update_at",
        "input_bytes",
        "output_bytes",
    )
    list_filter = ("status", "identity_type", "tenant", "router")
    search_fields = ("username", "acct_session_id", "calling_station_id", "framed_ip_address")


@admin.register(RadiusAccountingEvent)
class RadiusAccountingEventAdmin(admin.ModelAdmin):
    list_display = (
        "status_type",
        "tenant",
        "router",
        "session",
        "event_at",
        "input_bytes",
        "output_bytes",
    )
    list_filter = ("status_type", "tenant", "router")
    search_fields = ("session__username", "session__acct_session_id")
    readonly_fields = ("event_key", "raw_payload", "received_at")


@admin.register(UsageAggregate)
class UsageAggregateAdmin(admin.ModelAdmin):
    list_display = (
        "period_start",
        "tenant",
        "router",
        "granularity",
        "identity_type",
        "username",
        "input_bytes",
        "output_bytes",
    )
    list_filter = ("granularity", "identity_type", "tenant", "router")
    search_fields = ("username", "identity_name", "identity_key")
