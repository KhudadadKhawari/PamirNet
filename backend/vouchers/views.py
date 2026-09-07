import csv

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.context import resolve_tenant_context
from core.permissions import TenantScopedPermission
from core.services import audit
from subscribers.models import Package

from .models import Voucher, VoucherBatch
from .serializers import VoucherBatchCreateSerializer, VoucherBatchSerializer, VoucherSerializer
from .services import disable_batch, generate_voucher_batch


def _error(exc):
    messages = getattr(exc, "messages", None)
    return Response(
        {"detail": messages[0] if messages else str(exc)},
        status=status.HTTP_400_BAD_REQUEST,
    )


class VoucherBatchViewSet(viewsets.GenericViewSet):
    permission_classes = [TenantScopedPermission]
    required_permissions = {
        "GET": "voucher.view",
        "POST": "voucher.generate",
        "DELETE": "voucher.disable",
    }
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        tenant = resolve_tenant_context(self.request)
        return VoucherBatch.objects.filter(tenant=tenant).select_related("package", "generated_by")

    def list(self, request):
        queryset = self.get_queryset()
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(name__icontains=search)
        return Response(VoucherBatchSerializer(queryset, many=True).data)

    def retrieve(self, request, pk=None):
        return Response(VoucherBatchSerializer(self.get_object()).data)

    def create(self, request):
        tenant = resolve_tenant_context(request)
        serializer = VoucherBatchCreateSerializer(data=request.data, context={"tenant": tenant})
        serializer.is_valid(raise_exception=True)
        package = Package.objects.get(tenant=tenant, id=serializer.validated_data["package_id"])
        try:
            batch = generate_voucher_batch(
                tenant=tenant,
                package=package,
                name=serializer.validated_data["name"],
                quantity=serializer.validated_data["quantity"],
                simultaneous_sessions=serializer.validated_data.get("simultaneous_sessions", 1),
                generated_by=request.user,
            )
        except (ValidationError, IntegrityError) as exc:
            return _error(exc)
        audit(
            request,
            "voucher.batch_generated",
            tenant=tenant,
            target=batch,
            metadata={"quantity": batch.quantity, "package_id": str(package.id)},
        )
        return Response(VoucherBatchSerializer(batch).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        batch = self.get_object()
        if batch.vouchers.exclude(status=Voucher.Status.GENERATED).exists():
            return Response(
                {"detail": "Used or disabled batches must be retained; disable them instead."},
                status=status.HTTP_409_CONFLICT,
            )
        tenant = batch.tenant
        batch_id = str(batch.id)
        batch.delete()
        audit(
            request,
            "voucher.batch_deleted",
            tenant=tenant,
            metadata={"batch_id": batch_id},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["post"],
        url_path="disable",
        required_permissions={"POST": "voucher.disable"},
    )
    def disable(self, request, pk=None):
        batch = self.get_object()
        changed = disable_batch(batch)
        audit(
            request,
            "voucher.batch_disabled",
            tenant=batch.tenant,
            target=batch,
            metadata={"vouchers_disabled": changed},
        )
        batch.refresh_from_db()
        return Response(VoucherBatchSerializer(batch).data)

    @action(
        detail=True,
        methods=["get"],
        url_path="export",
        required_permissions={"GET": "voucher.export"},
    )
    def export(self, request, pk=None):
        batch = self.get_object()
        response = HttpResponse(content_type="text/csv")
        safe_name = "".join(char if char.isalnum() or char in "-_" else "_" for char in batch.name)
        response["Content-Disposition"] = f'attachment; filename="{safe_name or "vouchers"}.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "username",
                "password",
                "package",
                "status",
                "activated_at",
                "expires_at",
                "batch",
            ]
        )
        for voucher in batch.vouchers.select_related("package").order_by("username"):
            writer.writerow(
                [
                    voucher.username,
                    voucher.get_password(),
                    voucher.package.name,
                    voucher.status,
                    voucher.activated_at.isoformat() if voucher.activated_at else "",
                    voucher.expires_at.isoformat() if voucher.expires_at else "",
                    batch.name,
                ]
            )
        audit(
            request,
            "voucher.batch_exported",
            tenant=batch.tenant,
            target=batch,
            metadata={"quantity": batch.quantity, "exported_at": timezone.now().isoformat()},
        )
        return response


class VoucherViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = VoucherSerializer
    permission_classes = [TenantScopedPermission]
    required_permissions = {"GET": "voucher.view"}

    def get_queryset(self):
        tenant = resolve_tenant_context(self.request)
        queryset = Voucher.objects.filter(tenant=tenant).select_related("batch", "package")
        batch_id = self.request.query_params.get("batch", "").strip()
        status_filter = self.request.query_params.get("status", "").strip()
        search = self.request.query_params.get("search", "").strip()
        if batch_id:
            queryset = queryset.filter(batch_id=batch_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if search:
            queryset = queryset.filter(username__icontains=search)
        return queryset
