from rest_framework import serializers

from .models import Router


class RouterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Router
        fields = [
            "id",
            "name",
            "description",
            "tunnel_ip",
            "wireguard_public_key",
            "api_protocol",
            "api_port",
            "api_username",
            "api_tls_verify",
            "enabled",
            "status",
            "routeros_version",
            "last_seen_at",
            "latency_ms",
            "packet_loss_percent",
            "uptime_seconds",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class RouterCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)
    api_protocol = serializers.ChoiceField(choices=Router.APIProtocol.choices, default=Router.APIProtocol.API)
    api_port = serializers.IntegerField(min_value=1, max_value=65535, required=False, allow_null=True)
    api_username = serializers.CharField(max_length=120)
    api_password = serializers.CharField(write_only=True, trim_whitespace=False)
    api_tls_verify = serializers.BooleanField(required=False, default=False)


class RouterUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, required=False)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)
    api_protocol = serializers.ChoiceField(choices=Router.APIProtocol.choices, required=False)
    api_port = serializers.IntegerField(min_value=1, max_value=65535, required=False)
    api_username = serializers.CharField(max_length=120, required=False)
    api_password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)
    api_tls_verify = serializers.BooleanField(required=False)
    enabled = serializers.BooleanField(required=False)
