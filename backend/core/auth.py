from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .models import ImpersonationSession
from .services import active_memberships

REFRESH_COOKIE = "pamirnet_refresh"


def _base_claims(user, tenant_id=None):
    claims = {"is_platform_admin": bool(user.is_superuser)}
    if tenant_id:
        claims["tenant_id"] = str(tenant_id)
    return claims


def select_tenant_for_user(user, requested_tenant_id=None):
    memberships = list(active_memberships(user))
    if user.is_superuser and requested_tenant_id is None:
        return None, memberships

    if requested_tenant_id:
        for membership in memberships:
            if str(membership.tenant_id) == str(requested_tenant_id):
                return membership.tenant, memberships
        return None, memberships

    if len(memberships) == 1:
        return memberships[0].tenant, memberships
    return None, memberships


def issue_login_tokens(user, tenant=None):
    refresh = RefreshToken.for_user(user)
    for key, value in _base_claims(user, tenant.id if tenant else None).items():
        refresh[key] = value
    return str(refresh.access_token), str(refresh)


def issue_impersonation_access(user, session: ImpersonationSession):
    token = AccessToken.for_user(user)
    token["is_platform_admin"] = True
    token["tenant_id"] = str(session.tenant_id)
    token["impersonation_id"] = str(session.id)
    token.set_exp(lifetime=timedelta(minutes=15), from_time=timezone.now())
    return str(token)


def set_refresh_cookie(response, refresh_token):
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path="/api/auth/",
    )


def clear_refresh_cookie(response):
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth/", samesite="Lax")
