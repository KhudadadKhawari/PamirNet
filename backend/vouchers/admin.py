from django.contrib import admin

from .models import Voucher, VoucherBatch, VoucherUsageCounter


@admin.register(VoucherBatch)
class VoucherBatchAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "package", "quantity", "enabled", "created_at")
    list_filter = ("enabled", "tenant")
    search_fields = ("name", "package__name", "tenant__name")


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ("username", "tenant", "batch", "package", "status", "activated_at", "expires_at")
    list_filter = ("status", "tenant")
    search_fields = ("username", "batch__name", "package__name")
    exclude = ("password_cipher",)


@admin.register(VoucherUsageCounter)
class VoucherUsageCounterAdmin(admin.ModelAdmin):
    list_display = ("voucher", "scope", "bytes_used", "period_start", "period_end")
    list_filter = ("scope", "tenant")
    search_fields = ("voucher__username",)
