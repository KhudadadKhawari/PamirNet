from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import issue_impersonation_access
from .models import AuditLog, ImpersonationSession, Tenant
from .permissions import IsPlatformAdmin
from .serializers import AuditLogSerializer, PlatformTenantCreateSerializer, TenantSerializer
from .services import (
    audit,
    client_ip,
    create_tenant_with_owner,
    end_impersonation,
    serialize_tenant,
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
                owner_name=data["owner_name"],
                owner_password=data["owner_password"],
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
    queryset = AuditLog.objects.select_related("actor", "tenant")
