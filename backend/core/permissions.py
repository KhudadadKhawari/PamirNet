from rest_framework.permissions import BasePermission

from .context import resolve_tenant_context
from .services import permission_codes_for_membership


class IsPlatformAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class TenantScopedPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        resolve_tenant_context(request)
        if getattr(request, "pamirnet_impersonation", None):
            return True

        required = getattr(view, "required_permissions", {})
        permission_code = required.get(request.method) or required.get("*")
        if not permission_code:
            return True

        granted = permission_codes_for_membership(request.pamirnet_membership)
        if isinstance(permission_code, (list, tuple, set, frozenset)):
            return any(code in granted for code in permission_code)
        return permission_code in granted
