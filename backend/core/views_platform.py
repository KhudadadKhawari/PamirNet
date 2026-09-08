from django.contrib.auth.models import User
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import issue_impersonation_access
from .models import AuditLog, ImpersonationSession, Role, Tenant, TenantMembership
from .permissions import IsPlatformAdmin
from .serializers import (
    AuditLogSerializer,
    PlatformTenantCreateSerializer,
    PlatformUserCreateSerializer,
    PlatformUserSerializer,
    PlatformUserTenantRemoveSerializer,
    PlatformUserTenantSerializer,
    PlatformUserUpdateSerializer,
    RoleSerializer,
    TenantSerializer,
)
from .services import (
    audit,
    client_ip,
    create_tenant_with_owner,
    end_impersonation,
    ensure_owner_change_is_safe,
    ensure_user_deactivation_is_safe,
    serialize_membership,
    serialize_tenant,
    serialize_user,
)


class PlatformTenantViewSet(viewsets.GenericViewSet):
    serializer_class = TenantSerializer
    permission_classes = [IsPlatformAdmin]
    queryset = Tenant.objects.all()
    http_method_names = ["get", "post", "patch", "head", "options"]

    def list(self, request):
        return Response(TenantSerializer(self.get_queryset(), many=True).data)

    def retrieve(self, request, pk=None):
        tenant = self.get_queryset().filter(pk=pk).first()
        if not tenant:
            return Response({"detail": "Not found."}, status=404)
        return Response(TenantSerializer(tenant).data)

    @transaction.atomic
    def create(self, request):
        serializer = PlatformTenantCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            tenant, owner, membership = create_tenant_with_owner(
                name=data["name"],
                slug=data["slug"],
                owner_email=data["owner_email"],
                owner_name=data.get("owner_name", ""),
                owner_password=data.get("owner_password", ""),
                timezone_name=data["timezone"],
                currency=data["currency"],
            )
        except DjangoValidationError as exc:
            return Response({"detail": exc.message}, status=409)
        audit(
            request,
            "platform.tenant.created",
            tenant=tenant,
            target=tenant,
            after=serialize_tenant(tenant),
            metadata={"owner_user_id": owner.id, "owner_membership_id": str(membership.id)},
        )
        return Response(TenantSerializer(tenant).data, status=201)

    def partial_update(self, request, pk=None):
        tenant = self.get_queryset().filter(pk=pk).first()
        if not tenant:
            return Response({"detail": "Not found."}, status=404)
        before = serialize_tenant(tenant)
        serializer = TenantSerializer(tenant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.save()
        audit(
            request,
            "platform.tenant.updated",
            tenant=tenant,
            target=tenant,
            before=before,
            after=serialize_tenant(tenant),
        )
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def roles(self, request, pk=None):
        tenant = self.get_queryset().filter(pk=pk).first()
        if not tenant:
            return Response({"detail": "Not found."}, status=404)
        roles = Role.objects.filter(tenant=tenant).prefetch_related("permissions")
        return Response(RoleSerializer(roles, many=True).data)

    @action(detail=True, methods=["post"])
    def impersonate(self, request, pk=None):
        tenant = self.get_queryset().filter(pk=pk, status=Tenant.Status.ACTIVE).first()
        if not tenant:
            return Response({"detail": "Active tenant not found."}, status=404)
        reason = str(request.data.get("reason", "")).strip()[:255]
        session = ImpersonationSession.objects.create(
            actor=request.user,
            tenant=tenant,
            reason=reason,
            source_ip=client_ip(request),
        )
        audit(
            request,
            "platform.impersonation.started",
            tenant=tenant,
            target=session,
            metadata={"reason": reason},
        )
        return Response(
            {
                "access": issue_impersonation_access(request.user, session),
                "tenant": TenantSerializer(tenant).data,
                "impersonation_id": str(session.id),
            }
        )


class PlatformUserViewSet(viewsets.GenericViewSet):
    serializer_class = PlatformUserSerializer
    permission_classes = [IsPlatformAdmin]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return (
            User.objects.filter(is_superuser=False)
            .prefetch_related("pamirnet_memberships__tenant", "pamirnet_memberships__roles")
            .order_by("email")
        )

    def list(self, request):
        return Response(PlatformUserSerializer(self.get_queryset(), many=True).data)

    def retrieve(self, request, pk=None):
        user = self.get_queryset().filter(pk=pk).first()
        if not user:
            return Response({"detail": "Not found."}, status=404)
        return Response(PlatformUserSerializer(user).data)

    @transaction.atomic
    def create(self, request):
        serializer = PlatformUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        audit(
            request,
            "platform.user.created",
            target=user,
            after=serialize_user(user),
        )
        return Response(PlatformUserSerializer(user).data, status=201)

    @transaction.atomic
    def partial_update(self, request, pk=None):
        user = self.get_queryset().filter(pk=pk).first()
        if not user:
            return Response({"detail": "Not found."}, status=404)
        serializer = PlatformUserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        before = serialize_user(user)
        requested_active = serializer.validated_data.get("is_active", user.is_active)
        if user.is_active and not requested_active:
            try:
                ensure_user_deactivation_is_safe(user)
            except DjangoValidationError as exc:
                return Response({"detail": exc.message}, status=409)
        if "name" in serializer.validated_data:
            user.first_name = serializer.validated_data["name"].strip()
        if "is_active" in serializer.validated_data:
            user.is_active = serializer.validated_data["is_active"]
        user.save(update_fields=["first_name", "is_active"])
        audit(
            request,
            "platform.user.updated",
            target=user,
            before=before,
            after=serialize_user(user),
        )
        return Response(PlatformUserSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="assign-tenant")
    @transaction.atomic
    def assign_tenant(self, request, pk=None):
        user = self.get_queryset().filter(pk=pk).first()
        if not user:
            return Response({"detail": "User not found."}, status=404)
        serializer = PlatformUserTenantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = Tenant.objects.filter(id=serializer.validated_data["tenant_id"]).first()
        if not tenant:
            return Response({"detail": "Tenant not found."}, status=404)
        role_ids = serializer.validated_data["role_ids"]
        roles = list(Role.objects.filter(tenant=tenant, id__in=role_ids))
        if len(roles) != len(set(role_ids)):
            return Response(
                {"detail": "One or more roles are invalid for this tenant."},
                status=400,
            )

        membership, _ = TenantMembership.objects.get_or_create(tenant=tenant, user=user)
        before = serialize_membership(membership)
        membership.is_active = True
        membership.save(update_fields=["is_active", "updated_at"])
        membership.roles.set(roles)
        membership.refresh_from_db()
        audit(
            request,
            "platform.user.tenant_assigned",
            tenant=tenant,
            target=membership,
            before=before,
            after=serialize_membership(membership),
        )
        return Response(PlatformUserSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="remove-tenant")
    @transaction.atomic
    def remove_tenant(self, request, pk=None):
        user = self.get_queryset().filter(pk=pk).first()
        if not user:
            return Response({"detail": "User not found."}, status=404)
        serializer = PlatformUserTenantRemoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = (
            TenantMembership.objects.filter(
                user=user,
                tenant_id=serializer.validated_data["tenant_id"],
            )
            .select_related("tenant")
            .prefetch_related("roles")
            .first()
        )
        if not membership:
            return Response({"detail": "Tenant membership not found."}, status=404)
        try:
            ensure_owner_change_is_safe(membership, deactivate=True)
        except DjangoValidationError as exc:
            return Response({"detail": exc.message}, status=409)
        before = serialize_membership(membership)
        membership.is_active = False
        membership.save(update_fields=["is_active", "updated_at"])
        audit(
            request,
            "platform.user.tenant_removed",
            tenant=membership.tenant,
            target=membership,
            before=before,
            after=serialize_membership(membership),
        )
        return Response(PlatformUserSerializer(user).data)


class StopImpersonationView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request):
        token = request.auth
        impersonation_id = token.get("impersonation_id") if token else None
        if not impersonation_id:
            return Response({"detail": "This token is not impersonating a tenant."}, status=400)
        session = ImpersonationSession.objects.filter(
            id=impersonation_id,
            actor=request.user,
            ended_at__isnull=True,
        ).select_related("tenant").first()
        if not session:
            return Response({"detail": "Impersonation session is not active."}, status=404)
        end_impersonation(session)
        audit(
            request,
            "platform.impersonation.ended",
            tenant=session.tenant,
            target=session,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlatformAuditViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [IsPlatformAdmin]

    def get_queryset(self):
        queryset = AuditLog.objects.select_related("actor", "tenant")
        tenant_id = self.request.query_params.get("tenant_id")
        action_name = self.request.query_params.get("action")
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if action_name:
            queryset = queryset.filter(action=action_name)
        return queryset
