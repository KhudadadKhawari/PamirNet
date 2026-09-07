from rest_framework.routers import DefaultRouter

from .views import RouterViewSet

router = DefaultRouter()
router.register("routers", RouterViewSet, basename="router")

urlpatterns = router.urls
