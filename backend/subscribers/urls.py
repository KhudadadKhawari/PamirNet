from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    PackageViewSet,
    RadiusAuthorizeView,
    RadiusPostAuthView,
    SubscriberViewSet,
)

router = DefaultRouter()
router.register("packages", PackageViewSet, basename="package")
router.register("subscribers", SubscriberViewSet, basename="subscriber")

urlpatterns = [
    path("internal/radius/authorize/", RadiusAuthorizeView.as_view()),
    path("internal/radius/post-auth/", RadiusPostAuthView.as_view()),
]
urlpatterns += router.urls
