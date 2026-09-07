from django.contrib import admin

from .models import AuditLog, ImpersonationSession, PamirPermission, Role, Tenant, TenantMembership


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "tenant", "actor", "target_type", "target_id")
    list_filter = ("action", "tenant")
    search_fields = ("action", "actor__email", "target_type", "target_id")
    readonly_fields = (
        "tenant",
        "actor",
        "impersonation",
        "action",
        "target_type",
        "target_id",
        "source_ip",
        "before",
        "after",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Tenant)
admin.site.register(PamirPermission)
admin.site.register(Role)
admin.site.register(TenantMembership)
admin.site.register(ImpersonationSession)
