from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from .models import ImpersonationSession, Tenant, TenantMembership


def resolve_tenant_context(request):
    if hasattr(request, "pamirnet_tenant"):
        return request.pamirnet_tenant

    token = getattr(request, "auth", None)
    if not token:
        raise AuthenticationFailed("Tenant context is unavailable.")

    tenant_id = token.get("tenant_id")
    if not tenant_id:
        raise PermissionDenied("This access token is not scoped to a tenant.")

    tenant = Tenant.objects.filter(id=tenant_id, status=Tenant.Status.ACTIVE).first()
    if not tenant:
        raise PermissionDenied("Tenant is unavailable.")

    impersonation_id = token.get("impersonation_id")
    if impersonation_id:
        if not request.user.is_superuser:
            raise PermissionDenied("Invalid impersonation context.")
        session = ImpersonationSession.objects.filter(
            id=impersonation_id,
            actor=request.user,
            tenant=tenant,
            ended_at__isnull=True,
        ).first()
        if not session:
            raise PermissionDenied("Impersonation session is no longer active.")
        request.pamirnet_impersonation = session
        request.pamirnet_membership = None
    else:
        membership = (
            TenantMembership.objects.filter(user=request.user, tenant=tenant, is_active=True)
            .prefetch_related("roles__permissions")
            .first()
        )
        if not membership:
            raise PermissionDenied("You are not an active member of this tenant.")
        request.pamirnet_membership = membership
        request.pamirnet_impersonation = None

    request.pamirnet_tenant = tenant
    return tenant
