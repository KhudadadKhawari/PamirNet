from rest_framework.routers import DefaultRouter

from .views import VoucherBatchViewSet, VoucherViewSet

router = DefaultRouter()
router.register("voucher-batches", VoucherBatchViewSet, basename="voucher-batch")
router.register("vouchers", VoucherViewSet, basename="voucher")

urlpatterns = router.urls
