from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views_auth import LoginView, LogoutView, MeView, RefreshView
from .views_platform import PlatformAuditViewSet, PlatformTenantViewSet, StopImpersonationView
from .views_tenant import (
    AuditLogViewSet,
    PermissionViewSet,
    RoleViewSet,
    TenantDetailView,
    TenantUserViewSet,
)

router = DefaultRouter()
router.register("permissions", PermissionViewSet, basename="permission")
router.register("roles", RoleViewSet, basename="role")
router.register("users", TenantUserViewSet, basename="tenant-user")
router.register("audit", AuditLogViewSet, basename="audit")

platform_router = DefaultRouter()
platform_router.register("tenants", PlatformTenantViewSet, basename="platform-tenant")
platform_router.register("audit", PlatformAuditViewSet, basename="platform-audit")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", RefreshView.as_view(), name="refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("tenant/", TenantDetailView.as_view(), name="tenant-detail"),
    path(
        "platform/impersonation/stop/",
        StopImpersonationView.as_view(),
        name="stop-impersonation",
    ),
    path("platform/", include(platform_router.urls)),
    path("", include(router.urls)),
]
