from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    DashboardView,
    IdentityUsageView,
    RadiusAccountingView,
    SessionViewSet,
    UsageSeriesView,
)

router = DefaultRouter()
router.register("sessions", SessionViewSet, basename="accounting-session")

urlpatterns = [
    path("internal/radius/accounting/", RadiusAccountingView.as_view(), name="radius-accounting"),
    path("dashboard/", DashboardView.as_view(), name="accounting-dashboard"),
    path("analytics/usage/", UsageSeriesView.as_view(), name="usage-series"),
    path("analytics/identities/", IdentityUsageView.as_view(), name="identity-usage"),
]
urlpatterns += router.urls
