import secrets
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import F, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.context import resolve_tenant_context
from core.permissions import TenantScopedPermission
from core.services import audit
from networking.models import Router
from subscribers.models import Subscriber
from vouchers.models import Voucher

from .control import RadiusControlError, refresh_session_policy, send_disconnect
from .models import RadiusAccountingEvent, RadiusSession, UsageAggregate
from .serializers import RadiusAccountingEventSerializer, RadiusSessionSerializer
from .services import AccountingReject, ingest_accounting


def _parse_at(value: str | None, default: datetime) -> datetime:
    if not value:
        return default
    parsed = parse_datetime(value)
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return default
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, UTC)
    return parsed


def _tenant_midnight(tenant) -> datetime:
    try:
        zone = ZoneInfo(tenant.timezone)
    except Exception:
        zone = ZoneInfo("UTC")
    local_now = timezone.now().astimezone(zone)
    return datetime.combine(local_now.date(), time.min, tzinfo=zone).astimezone(UTC)


class SessionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RadiusSessionSerializer
    permission_classes = [TenantScopedPermission]
    required_permissions = {
        "GET": "session.view",
        "POST": "session.disconnect",
    }

    def get_queryset(self):
        tenant = resolve_tenant_context(self.request)
        queryset = RadiusSession.objects.filter(tenant=tenant).select_related(
            "router",
            "subscriber",
            "subscription__package",
            "voucher__batch",
            "voucher__package",
        )
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(subscriber__name__icontains=search)
                | Q(voucher__batch__name__icontains=search)
                | Q(framed_ip_address__icontains=search)
                | Q(calling_station_id__icontains=search)
            )
        identity_type = self.request.query_params.get("identity_type", "").strip()
        if identity_type:
            queryset = queryset.filter(identity_type=identity_type)
        router_id = self.request.query_params.get("router", "").strip()
        if router_id:
            queryset = queryset.filter(router_id=router_id)
        online = self.request.query_params.get("online", "").strip().lower()
        if online in {"1", "true", "yes"}:
            queryset = queryset.filter(status=RadiusSession.Status.ACTIVE)
        elif online in {"0", "false", "no"}:
            queryset = queryset.filter(status=RadiusSession.Status.STOPPED)

        ordering = self.request.query_params.get("ordering", "-last_update_at")
        allowed = {
            "username": "username",
            "started_at": "started_at",
            "last_update_at": "last_update_at",
            "session_seconds": "session_seconds",
            "input_bytes": "input_bytes",
            "output_bytes": "output_bytes",
            "total_bytes": "_total_bytes",
        }
        descending = ordering.startswith("-")
        key = ordering[1:] if descending else ordering
        field = allowed.get(key, "last_update_at")
        queryset = queryset.annotate(_total_bytes=F("input_bytes") + F("output_bytes"))
        return queryset.order_by(("-" if descending else "") + field)

    @action(detail=True, methods=["get"], url_path="events")
    def events(self, request, pk=None):
        session = self.get_object()
        events = RadiusAccountingEvent.objects.filter(session=session).order_by("-event_at")[:200]
        return Response(RadiusAccountingEventSerializer(events, many=True).data)

    @action(detail=True, methods=["post"], url_path="disconnect")
    def disconnect(self, request, pk=None):
        session = self.get_object()
        if session.status != RadiusSession.Status.ACTIVE:
            return Response(
                {"detail": "Session is not online."},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            output = send_disconnect(session)
        except RadiusControlError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        audit(
            request,
            "session.disconnect_requested",
            tenant=session.tenant,
            target=session,
            metadata={"username": session.username},
        )
        return Response({"status": "disconnect_requested", "radclient": output[-500:]})

    @action(detail=True, methods=["post"], url_path="refresh-policy")
    def refresh_policy(self, request, pk=None):
        session = self.get_object()
        result = refresh_session_policy(session.id)
        if result.get("action") == "error":
            return Response(result, status=status.HTTP_502_BAD_GATEWAY)
        audit(
            request,
            "session.policy_refreshed",
            tenant=session.tenant,
            target=session,
            metadata=result,
        )
        return Response(result)


class RadiusAccountingView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def _authorized(self, request) -> bool:
        expected = settings.RADIUS_INTERNAL_TOKEN
        supplied = request.headers.get("X-PamirNet-Radius-Token", "")
        return bool(expected and supplied and secrets.compare_digest(expected, supplied))

    def post(self, request):
        if not self._authorized(request):
            return Response(status=status.HTTP_403_FORBIDDEN)
        payload = {key: value for key, value in request.query_params.items()}
        payload.update({key: value for key, value in request.data.items()})
        try:
            ingest_accounting(payload)
        except AccountingReject:
            # Accounting must never interrupt access. Invalid/unknown records are
            # ignored here and can be diagnosed from FreeRADIUS logs.
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DashboardView(APIView):
    permission_classes = [TenantScopedPermission]
    required_permissions = {"GET": "dashboard.view"}

    def get(self, request):
        tenant = resolve_tenant_context(request)
        today_start = _tenant_midnight(tenant)
        last_24h = timezone.now() - timedelta(hours=24)
        today = UsageAggregate.objects.filter(
            tenant=tenant,
            granularity=UsageAggregate.Granularity.HOUR,
            period_start__gte=today_start,
        ).aggregate(input=Sum("input_bytes"), output=Sum("output_bytes"))
        today_input = today["input"] or 0
        today_output = today["output"] or 0

        series = list(
            UsageAggregate.objects.filter(
                tenant=tenant,
                granularity=UsageAggregate.Granularity.HOUR,
                period_start__gte=last_24h,
            )
            .values("period_start")
            .annotate(input_bytes=Sum("input_bytes"), output_bytes=Sum("output_bytes"))
            .order_by("period_start")
        )
        routers = list(
            Router.objects.filter(tenant=tenant)
            .values(
                "id",
                "name",
                "status",
                "latency_ms",
                "packet_loss_percent",
                "uptime_seconds",
                "last_seen_at",
            )
            .order_by("name")
        )
        return Response(
            {
                "online_sessions": RadiusSession.objects.filter(
                    tenant=tenant,
                    status=RadiusSession.Status.ACTIVE,
                ).count(),
                "active_subscribers": Subscriber.objects.filter(
                    tenant=tenant,
                    status__in=[
                        Subscriber.Status.ACTIVE,
                        Subscriber.Status.QUOTA_EXHAUSTED,
                    ],
                ).count(),
                "active_vouchers": Voucher.objects.filter(
                    tenant=tenant,
                    status=Voucher.Status.ACTIVE,
                ).count(),
                "today_input_bytes": today_input,
                "today_output_bytes": today_output,
                "today_total_bytes": today_input + today_output,
                "traffic_24h": series,
                "routers": routers,
            }
        )


class UsageSeriesView(APIView):
    permission_classes = [TenantScopedPermission]
    required_permissions = {"GET": "analytics.view"}

    def get(self, request):
        tenant = resolve_tenant_context(request)
        now = timezone.now()
        start = _parse_at(request.query_params.get("start"), now - timedelta(days=7))
        end = _parse_at(request.query_params.get("end"), now)
        if end <= start:
            return Response(
                {"detail": "end must be after start"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        granularity = request.query_params.get("granularity", "hour")
        if granularity not in UsageAggregate.Granularity.values:
            return Response(
                {"detail": "granularity must be hour or day"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queryset = UsageAggregate.objects.filter(
            tenant=tenant,
            granularity=granularity,
            period_start__gte=start,
            period_start__lt=end,
        )
        identity_type = request.query_params.get("identity_type", "").strip()
        identity_key = request.query_params.get("identity_key", "").strip()
        router_id = request.query_params.get("router", "").strip()
        if identity_type:
            queryset = queryset.filter(identity_type=identity_type)
        if identity_key:
            queryset = queryset.filter(identity_key=identity_key)
        if router_id:
            queryset = queryset.filter(router_id=router_id)
        rows = list(
            queryset.values("period_start")
            .annotate(
                input_bytes=Sum("input_bytes"),
                output_bytes=Sum("output_bytes"),
                session_seconds=Sum("session_seconds"),
            )
            .order_by("period_start")
        )
        for row in rows:
            row["total_bytes"] = (row["input_bytes"] or 0) + (row["output_bytes"] or 0)
        return Response(rows)


class IdentityUsageView(APIView):
    permission_classes = [TenantScopedPermission]
    required_permissions = {"GET": "analytics.view"}

    def get(self, request):
        tenant = resolve_tenant_context(request)
        now = timezone.now()
        start = _parse_at(request.query_params.get("start"), now - timedelta(days=7))
        end = _parse_at(request.query_params.get("end"), now)
        queryset = UsageAggregate.objects.filter(
            tenant=tenant,
            granularity=UsageAggregate.Granularity.HOUR,
            period_start__gte=start,
            period_start__lt=end,
        )
        identity_type = request.query_params.get("identity_type", "").strip()
        router_id = request.query_params.get("router", "").strip()
        if identity_type:
            queryset = queryset.filter(identity_type=identity_type)
        if router_id:
            queryset = queryset.filter(router_id=router_id)
        rows = list(
            queryset.values("identity_type", "identity_key", "identity_name", "username")
            .annotate(
                input_bytes=Sum("input_bytes"),
                output_bytes=Sum("output_bytes"),
                session_seconds=Sum("session_seconds"),
            )
        )
        for row in rows:
            row["total_bytes"] = (row["input_bytes"] or 0) + (row["output_bytes"] or 0)
        ordering = request.query_params.get("ordering", "-total_bytes")
        allowed = {"total_bytes", "input_bytes", "output_bytes", "session_seconds", "username"}
        descending = ordering.startswith("-")
        key = ordering[1:] if descending else ordering
        if key not in allowed:
            key = "total_bytes"
            descending = True
        rows.sort(key=lambda item: item.get(key) or 0, reverse=descending)
        limit = min(500, max(1, int(request.query_params.get("limit", "100") or 100)))
        return Response(rows[:limit])
