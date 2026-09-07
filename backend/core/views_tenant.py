from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .context import resolve_tenant_context
from .models import AuditLog, PamirPermission, Role, TenantMembership
from .permissions import TenantScopedPermission
from .serializers import (
    AuditLogSerializer,
    PermissionSerializer,
    RoleSerializer,
    TenantMembershipSerializer,
    TenantSettingsSerializer,
    TenantUserCreateSerializer,
    TenantUserUpdateSerializer,
)
from .services import (
    audit,
    ensure_owner_change_is_safe,
    serialize_membership,
    serialize_role,
    serialize_tenant,
)


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PermissionSerializer
    permission_classes = [TenantScopedPermission]
    queryset = PamirPermission.objects.all()

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        resolve_tenant_context(request)


class RoleViewSet(viewsets.ModelViewSet):
    serializer_class = RoleSerializer
    permission_classes = [TenantScopedPermission]
    required_permissions = {
        "GET": "role.manage",
        "POST": "role.manage",
        "PATCH": "role.manage",
        "PUT": "role.manage",
        "DELETE": "role.manage",
    }
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        tenant = resolve_tenant_context(self.request)
        return Role.objects.filter(tenant=tenant).prefetch_related("permissions")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["tenant"] = resolve_tenant_context(self.request)
        return context

    def perform_create(self, serializer):
        tenant = resolve_tenant_context(self.request)
        role = serializer.save()
        audit(
            self.request,
            "role.created",
            tenant=tenant,
            target=role,
            after=serialize_role(role),
        )

    def perform_update(self, serializer):
        role = self.get_object()
        before = serialize_role(role)
        updated = serializer.save()
        audit(
            self.request,
            "role.updated",
            tenant=updated.tenant,
            target=updated,
            before=before,
            after=serialize_role(updated),
        )

    def destroy(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system:
            return Response({"detail": "System roles cannot be deleted."}, status=409)
        if role.memberships.exists():
            return Response(
                {"detail": "Remove this role from all users before deleting it."},
                status=409,
            )
        before = serialize_role(role)
        tenant = role.tenant
        role_id = str(role.id)
        role.delete()
        audit(
            request,
            "role.deleted",
            tenant=tenant,
            before=before,
            metadata={"role_id": role_id},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class TenantUserViewSet(viewsets.GenericViewSet):
    serializer_class = TenantMembershipSerializer
    permission_classes = [TenantScopedPermission]
    required_permissions = {"*": "user.manage"}
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        tenant = resolve_tenant_context(self.request)
        return (
            TenantMembership.objects.filter(tenant=tenant)
            .select_related("user", "tenant")
            .prefetch_related("roles__permissions")
        )

    def list(self, request):
        serializer = TenantMembershipSerializer(self.get_queryset(), many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        membership = self.get_queryset().filter(pk=pk).first()
        if not membership:
            return Response({"detail": "Not found."}, status=404)
        return Response(TenantMembershipSerializer(membership).data)

    @transaction.atomic
    def create(self, request):
        tenant = resolve_tenant_context(request)
        serializer = TenantUserCreateSerializer(
            data=request.data,
            context={"tenant": tenant, "actor_membership": request.pamirnet_membership},
        )
        serializer.is_valid(raise_exception=True)
        membership = serializer.save()
        audit(
            request,
            "user.created",
            tenant=tenant,
            target=membership,
            after=serialize_membership(membership),
        )
        return Response(TenantMembershipSerializer(membership).data, status=201)

    @transaction.atomic
    def partial_update(self, request, pk=None):
        tenant = resolve_tenant_context(request)
        membership = self.get_queryset().filter(pk=pk).first()
        if not membership:
            return Response({"detail": "Not found."}, status=404)
        before = serialize_membership(membership)
        serializer = TenantUserUpdateSerializer(
            data=request.data,
            partial=True,
            context={
                "tenant": tenant,
                "membership": membership,
                "actor_membership": request.pamirnet_membership,
            },
        )
        serializer.is_valid(raise_exception=True)

        roles = serializer.context.get("validated_roles")
        requested_active = serializer.validated_data.get("is_active", membership.is_active)
        try:
            ensure_owner_change_is_safe(
                membership,
                new_roles=roles if "role_ids" in serializer.validated_data else None,
                deactivate=not requested_active,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.message) from exc

        if "name" in serializer.validated_data:
            membership.user.first_name = serializer.validated_data["name"].strip()
            membership.user.save(update_fields=["first_name"])
        if "is_active" in serializer.validated_data:
            membership.is_active = serializer.validated_data["is_active"]
            membership.save(update_fields=["is_active", "updated_at"])
        if roles is not None:
            membership.roles.set(roles)

        membership.refresh_from_db()
        audit(
            request,
            "user.updated",
            tenant=tenant,
            target=membership,
            before=before,
            after=serialize_membership(membership),
        )
        return Response(TenantMembershipSerializer(membership).data)

    def destroy(self, request, pk=None):
        tenant = resolve_tenant_context(request)
        membership = self.get_queryset().filter(pk=pk).first()
        if not membership:
            return Response({"detail": "Not found."}, status=404)
        if membership.user_id == request.user.id:
            return Response(
                {"detail": "You cannot disable your own tenant membership here."},
                status=409,
            )
        try:
            ensure_owner_change_is_safe(membership, deactivate=True)
        except DjangoValidationError as exc:
            return Response({"detail": exc.message}, status=409)
        before = serialize_membership(membership)
        membership.is_active = False
        membership.save(update_fields=["is_active", "updated_at"])
        audit(
            request,
            "user.disabled",
            tenant=tenant,
            target=membership,
            before=before,
            after=serialize_membership(membership),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class TenantDetailView(APIView):
    permission_classes = [TenantScopedPermission]
    required_permissions = {"PATCH": "settings.manage"}

    def get(self, request):
        tenant = resolve_tenant_context(request)
        return Response(TenantSettingsSerializer(tenant).data)

    def patch(self, request):
        tenant = resolve_tenant_context(request)
        before = serialize_tenant(tenant)
        serializer = TenantSettingsSerializer(tenant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.save()
        audit(
            request,
            "tenant.settings.updated",
            tenant=tenant,
            target=tenant,
            before=before,
            after=serialize_tenant(tenant),
        )
        return Response(serializer.data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [TenantScopedPermission]
    required_permissions = {"*": "audit.view"}

    def get_queryset(self):
        tenant = resolve_tenant_context(self.request)
        queryset = AuditLog.objects.filter(tenant=tenant).select_related("actor")
        action_name = self.request.query_params.get("action")
        if action_name:
            queryset = queryset.filter(action=action_name)
        return queryset
