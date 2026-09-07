from django.db import IntegrityError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.context import resolve_tenant_context
from core.permissions import TenantScopedPermission
from core.services import audit

from .models import Router
from .serializers import RouterCreateSerializer, RouterSerializer, RouterUpdateSerializer
from .services import (
    check_router_health,
    provision_router,
    render_radius_clients,
    rotate_radius_secret,
    rotate_wireguard,
)
from .wireguard import WireGuardConfigurationError


class RouterViewSet(viewsets.ModelViewSet):
    permission_classes = [TenantScopedPermission]
    required_permissions = {
        "GET": "router.view",
        "POST": "router.manage",
        "PATCH": "router.manage",
        "PUT": "router.manage",
        "DELETE": "router.manage",
    }
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        tenant = resolve_tenant_context(self.request)
        return Router.objects.filter(tenant=tenant)

    def get_serializer_class(self):
        if self.action == "create":
            return RouterCreateSerializer
        if self.action in {"partial_update", "update"}:
            return RouterUpdateSerializer
        return RouterSerializer

    def create(self, request, *args, **kwargs):
        tenant = resolve_tenant_context(request)
        serializer = RouterCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            router, provisioning = provision_router(
                tenant=tenant,
                data=serializer.validated_data,
            )
        except WireGuardConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except IntegrityError:
            return Response(
                {"detail": "A router with this name already exists."},
                status=status.HTTP_409_CONFLICT,
            )
        audit(
            request,
            "router.created",
            tenant=tenant,
            target=router,
            after=RouterSerializer(router).data,
        )
        return Response(
            {
                "router": RouterSerializer(router).data,
                "provisioning": provisioning,
            },
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        router = self.get_object()
        tenant = router.tenant
        before = RouterSerializer(router).data
        serializer = RouterUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        password = values.pop("api_password", None)
        for field, value in values.items():
            setattr(router, field, value)
        if password is not None:
            router.set_api_password(password)
        if "enabled" in values:
            router.status = (
                Router.Status.PENDING if router.enabled else Router.Status.DISABLED
            )
        router.save()
        render_radius_clients()
        audit(
            request,
            "router.updated",
            tenant=tenant,
            target=router,
            before=before,
            after=RouterSerializer(router).data,
        )
        return Response(RouterSerializer(router).data)

    def destroy(self, request, *args, **kwargs):
        router = self.get_object()
        tenant = router.tenant
        before = RouterSerializer(router).data
        router_id = router.id
        router.delete()
        render_radius_clients()
        audit(
            request,
            "router.deleted",
            tenant=tenant,
            before=before,
            metadata={"router_id": str(router_id)},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="test-connectivity")
    def test_connectivity(self, request, pk=None):
        router = self.get_object()
        result = check_router_health(router)
        metadata_result = {
            key: str(value) if value is not None else None
            for key, value in result.items()
        }
        audit(
            request,
            "router.connectivity_tested",
            tenant=router.tenant,
            target=router,
            metadata={"result": metadata_result},
        )
        payload = RouterSerializer(router).data | {
            "test_error": result.get("error", "")
        }
        return Response(payload)

    @action(detail=True, methods=["post"], url_path="rotate-radius-secret")
    def rotate_radius(self, request, pk=None):
        router = self.get_object()
        secret = rotate_radius_secret(router)
        audit(
            request,
            "router.radius_secret_rotated",
            tenant=router.tenant,
            target=router,
        )
        return Response(
            {
                "radius_secret": secret,
                "routeros_command": (
                    f'/radius set [find comment="PamirNet"] secret="{secret}"'
                ),
                "notice": "The new RADIUS secret is returned only in this response.",
            }
        )

    @action(detail=True, methods=["post"], url_path="rotate-wireguard")
    def rotate_wg(self, request, pk=None):
        router = self.get_object()
        try:
            provisioning = rotate_wireguard(router)
        except WireGuardConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        audit(
            request,
            "router.wireguard_rotated",
            tenant=router.tenant,
            target=router,
        )
        return Response(
            {
                "router": RouterSerializer(router).data,
                "provisioning": provisioning,
            }
        )
