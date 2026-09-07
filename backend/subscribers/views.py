import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.context import resolve_tenant_context
from core.permissions import TenantScopedPermission
from core.services import audit

from .models import Package, Subscriber
from .radius import (
    RadiusReject,
    authorize_radius,
    freeradius_reject_payload,
    freeradius_success_payload,
    record_successful_authentication,
)
from .serializers import (
    PackageAssignmentSerializer,
    PackageSerializer,
    PasswordChangeSerializer,
    RenewalSerializer,
    SubscriberCreateSerializer,
    SubscriberSerializer,
    SubscriberUpdateSerializer,
)
from .services import (
    assign_package,
    change_password,
    create_subscriber,
    renew_subscription,
    update_subscriber,
)


def _validation_response(exc):
    if hasattr(exc, "message_dict"):
        return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
    messages = getattr(exc, "messages", None)
    detail = messages[0] if messages else str(exc)
    return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)


class PackageViewSet(viewsets.ModelViewSet):
    serializer_class = PackageSerializer
    permission_classes = [TenantScopedPermission]
    required_permissions = {
        "GET": "package.view",
        "POST": "package.manage",
        "PATCH": "package.manage",
        "PUT": "package.manage",
        "DELETE": "package.manage",
    }
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        tenant = resolve_tenant_context(self.request)
        return Package.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        tenant = resolve_tenant_context(self.request)
        package = serializer.save(tenant=tenant)
        audit(
            self.request,
            "package.created",
            tenant=tenant,
            target=package,
            after=PackageSerializer(package).data,
        )

    def partial_update(self, request, *args, **kwargs):
        package = self.get_object()
        before = PackageSerializer(package).data
        response = super().partial_update(request, *args, **kwargs)
        package.refresh_from_db()
        audit(
            request,
            "package.updated",
            tenant=package.tenant,
            target=package,
            before=before,
            after=PackageSerializer(package).data,
        )
        return response

    def destroy(self, request, *args, **kwargs):
        package = self.get_object()
        tenant = package.tenant
        before = PackageSerializer(package).data
        try:
            package.delete()
        except ProtectedError:
            return Response(
                {"detail": "Package has subscription history; disable it instead."},
                status=status.HTTP_409_CONFLICT,
            )
        audit(request, "package.deleted", tenant=tenant, before=before)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SubscriberViewSet(viewsets.GenericViewSet):
    permission_classes = [TenantScopedPermission]
    required_permissions = {
        "GET": "subscriber.view",
        "POST": "subscriber.create",
        "PATCH": "subscriber.edit",
    }
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        tenant = resolve_tenant_context(self.request)
        return (
            Subscriber.objects.filter(tenant=tenant)
            .select_related("credential")
            .prefetch_related("subscriptions__package")
        )

    def list(self, request):
        queryset = self.get_queryset()
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(credential__username__icontains=search)
            )
        status_filter = request.query_params.get("status", "").strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return Response(SubscriberSerializer(queryset.distinct(), many=True).data)

    def retrieve(self, request, pk=None):
        return Response(SubscriberSerializer(self.get_object()).data)

    def create(self, request):
        tenant = resolve_tenant_context(request)
        serializer = SubscriberCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        package_id = data.pop("package_id", None)
        package = None
        if package_id:
            package = Package.objects.filter(tenant=tenant, id=package_id).first()
            if not package:
                return Response(
                    {"package_id": "Package not found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        data["package"] = package
        try:
            subscriber, generated_password = create_subscriber(tenant=tenant, data=data)
        except (ValidationError, IntegrityError) as exc:
            return _validation_response(exc)
        audit(
            request,
            "subscriber.created",
            tenant=tenant,
            target=subscriber,
            after=SubscriberSerializer(subscriber).data,
        )
        payload = {"subscriber": SubscriberSerializer(subscriber).data}
        if generated_password:
            payload["generated_password"] = generated_password
        return Response(payload, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        subscriber = self.get_object()
        before = SubscriberSerializer(subscriber).data
        serializer = SubscriberUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            subscriber = update_subscriber(
                subscriber=subscriber,
                data=dict(serializer.validated_data),
            )
        except ValidationError as exc:
            return _validation_response(exc)
        audit(
            request,
            "subscriber.updated",
            tenant=subscriber.tenant,
            target=subscriber,
            before=before,
            after=SubscriberSerializer(subscriber).data,
        )
        return Response(SubscriberSerializer(subscriber).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="assign-package",
        required_permissions={"POST": "subscriber.edit"},
    )
    def assign_package_action(self, request, pk=None):
        subscriber = self.get_object()
        serializer = PackageAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        package = Package.objects.filter(
            tenant=subscriber.tenant,
            id=serializer.validated_data["package_id"],
        ).first()
        if not package:
            return Response(
                {"package_id": "Package not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            subscription = assign_package(
                subscriber=subscriber,
                package=package,
                duration_value=serializer.validated_data.get("duration_value"),
                duration_unit=serializer.validated_data.get("duration_unit"),
            )
        except ValidationError as exc:
            return _validation_response(exc)
        audit(
            request,
            "subscriber.package_assigned",
            tenant=subscriber.tenant,
            target=subscriber,
            metadata={
                "subscription_id": str(subscription.id),
                "package_id": str(package.id),
            },
        )
        return Response(SubscriberSerializer(self.get_queryset().get(pk=subscriber.pk)).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="renew",
        required_permissions={"POST": "subscriber.edit"},
    )
    def renew(self, request, pk=None):
        subscriber = self.get_object()
        serializer = RenewalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            subscription = renew_subscription(
                subscriber=subscriber,
                duration_value=serializer.validated_data.get("duration_value"),
                duration_unit=serializer.validated_data.get("duration_unit"),
            )
        except ValidationError as exc:
            return _validation_response(exc)
        audit(
            request,
            "subscriber.renewed",
            tenant=subscriber.tenant,
            target=subscriber,
            metadata={"subscription_id": str(subscription.id)},
        )
        return Response(SubscriberSerializer(self.get_queryset().get(pk=subscriber.pk)).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="change-password",
        required_permissions={"POST": "subscriber.edit"},
    )
    def change_password_action(self, request, pk=None):
        subscriber = self.get_object()
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password = change_password(
            subscriber=subscriber,
            password=serializer.validated_data.get("password") or None,
        )
        audit(
            request,
            "subscriber.password_changed",
            tenant=subscriber.tenant,
            target=subscriber,
        )
        return Response(
            {
                "password": password,
                "notice": "The password is returned only in this response.",
            }
        )


class RadiusInternalView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def _authorized(self, request) -> bool:
        expected = settings.RADIUS_INTERNAL_TOKEN
        supplied = request.headers.get("X-PamirNet-Radius-Token", "")
        return bool(expected and supplied and secrets.compare_digest(expected, supplied))

    def _value(self, request, key: str) -> str:
        return str(request.query_params.get(key) or request.data.get(key) or "")


@extend_schema(exclude=True)
class RadiusAuthorizeView(RadiusInternalView):
    def post(self, request):
        if not self._authorized(request):
            return Response(status=status.HTTP_403_FORBIDDEN)
        try:
            authorization = authorize_radius(
                packet_src_ip=self._value(request, "packet_src_ip"),
                username=self._value(request, "username"),
                calling_station_id=self._value(request, "calling_station_id"),
            )
        except RadiusReject:
            return Response(freeradius_reject_payload())
        return Response(freeradius_success_payload(authorization))


@extend_schema(exclude=True)
class RadiusPostAuthView(RadiusInternalView):
    def post(self, request):
        if not self._authorized(request):
            return Response(status=status.HTTP_403_FORBIDDEN)
        try:
            record_successful_authentication(
                packet_src_ip=self._value(request, "packet_src_ip"),
                username=self._value(request, "username"),
                calling_station_id=self._value(request, "calling_station_id"),
            )
        except RadiusReject:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)
