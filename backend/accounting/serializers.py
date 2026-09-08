from rest_framework import serializers

from .models import RadiusAccountingEvent, RadiusSession, UsageAggregate


class RadiusSessionSerializer(serializers.ModelSerializer):
    router_name = serializers.CharField(source="router.name", read_only=True)
    identity_name = serializers.SerializerMethodField()
    package_name = serializers.SerializerMethodField()
    total_bytes = serializers.IntegerField(read_only=True)

    class Meta:
        model = RadiusSession
        fields = [
            "id",
            "router",
            "router_name",
            "identity_type",
            "identity_key",
            "identity_name",
            "username",
            "package_name",
            "acct_session_id",
            "acct_unique_session_id",
            "framed_ip_address",
            "calling_station_id",
            "nas_port_id",
            "service_type",
            "status",
            "started_at",
            "last_update_at",
            "stopped_at",
            "input_bytes",
            "output_bytes",
            "total_bytes",
            "session_seconds",
            "terminate_cause",
            "last_rate_limit",
            "last_control_action",
            "last_control_at",
            "last_control_error",
            "disconnect_requested_at",
        ]
        read_only_fields = fields

    def get_identity_name(self, obj):
        if obj.subscriber_id and obj.subscriber:
            return obj.subscriber.name
        if obj.voucher_id and obj.voucher:
            return obj.voucher.batch.name
        return obj.username

    def get_package_name(self, obj):
        if obj.subscription_id and obj.subscription:
            return obj.subscription.package.name
        if obj.voucher_id and obj.voucher:
            return obj.voucher.package.name
        return ""


class RadiusAccountingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = RadiusAccountingEvent
        fields = [
            "id",
            "status_type",
            "event_at",
            "input_bytes",
            "output_bytes",
            "session_seconds",
            "terminate_cause",
            "received_at",
        ]
        read_only_fields = fields


class UsageAggregateSerializer(serializers.ModelSerializer):
    total_bytes = serializers.IntegerField(read_only=True)
    router_name = serializers.CharField(source="router.name", read_only=True)

    class Meta:
        model = UsageAggregate
        fields = [
            "id",
            "router",
            "router_name",
            "granularity",
            "period_start",
            "identity_type",
            "identity_key",
            "identity_name",
            "username",
            "input_bytes",
            "output_bytes",
            "total_bytes",
            "session_seconds",
            "sample_count",
        ]
        read_only_fields = fields
