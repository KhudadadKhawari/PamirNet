from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .auth import (
    REFRESH_COOKIE,
    clear_refresh_cookie,
    issue_login_tokens,
    select_tenant_for_user,
    set_refresh_cookie,
)
from .context import resolve_tenant_context
from .serializers_login import LoginSerializer
from .services import permission_codes_for_membership
from .throttles import LoginRateThrottle


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        requested_tenant_id = serializer.validated_data.get("tenant_id")
        tenant, memberships = select_tenant_for_user(user, requested_tenant_id)

        if requested_tenant_id and tenant is None:
            return Response({"detail": "You do not have access to that tenant."}, status=403)

        if not user.is_superuser and tenant is None:
            return Response(
                {
                    "detail": "Tenant selection is required.",
                    "tenants": [
                        {"id": str(m.tenant_id), "name": m.tenant.name, "slug": m.tenant.slug}
                        for m in memberships
                    ],
                },
                status=status.HTTP_409_CONFLICT,
            )

        access, refresh = issue_login_tokens(user, tenant)
        response = Response({"access": access})
        set_refresh_cookie(response, refresh)
        return response


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw = request.COOKIES.get(REFRESH_COOKIE)
        if not raw:
            return Response({"detail": "Refresh token is missing."}, status=401)
        try:
            refresh = RefreshToken(raw)
            user = User.objects.filter(id=refresh["user_id"], is_active=True).first()
            if not user:
                return Response({"detail": "User is unavailable."}, status=401)
            access = refresh.access_token
            return Response({"access": str(access)})
        except TokenError:
            return Response({"detail": "Refresh token is invalid or expired."}, status=401)


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw = request.COOKIES.get(REFRESH_COOKIE)
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except TokenError:
                pass
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        token = request.auth
        data = {
            "id": request.user.id,
            "email": request.user.email,
            "name": request.user.get_full_name() or request.user.email,
            "is_platform_admin": request.user.is_superuser,
            "tenant": None,
            "permissions": [],
            "impersonating": bool(token.get("impersonation_id")) if token else False,
        }
        if token and token.get("tenant_id"):
            tenant = resolve_tenant_context(request)
            data["tenant"] = {
                "id": str(tenant.id),
                "name": tenant.name,
                "slug": tenant.slug,
                "status": tenant.status,
                "timezone": tenant.timezone,
                "currency": tenant.currency,
            }
            if getattr(request, "pamirnet_impersonation", None):
                data["permissions"] = ["*"]
            else:
                data["permissions"] = sorted(
                    permission_codes_for_membership(request.pamirnet_membership)
                )
        return Response(data)
