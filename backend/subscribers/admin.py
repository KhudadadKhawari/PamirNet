from django.contrib import admin

from .models import Package, Subscriber, SubscriberCredential, Subscription


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "tenant",
        "download_speed_mbps",
        "upload_speed_mbps",
        "duration_value",
        "duration_unit",
        "enabled",
    )
    list_filter = ("enabled", "duration_unit", "tenant")
    search_fields = ("name", "tenant__name")


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "status", "mac_lock_mode", "last_authenticated_at")
    list_filter = ("status", "mac_lock_mode", "tenant")
    search_fields = ("name", "phone", "credential__username")


@admin.register(SubscriberCredential)
class SubscriberCredentialAdmin(admin.ModelAdmin):
    list_display = ("username", "tenant", "subscriber")
    search_fields = ("username", "subscriber__name")
    exclude = ("password_cipher",)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("subscriber", "package", "status", "started_at", "expires_at")
    list_filter = ("status", "tenant")
    search_fields = ("subscriber__name", "subscriber__credential__username", "package__name")
