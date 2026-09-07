from rest_framework import serializers

from .models import Package, Subscriber, Subscription
from .services import normalize_mac


class PackageSerializer(serializers.ModelSerializer):
    currency = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            "id",
            "name",
            "description",
            "duration_value",
            "duration_unit",
            "download_speed_mbps",
            "upload_speed_mbps",
            "price",
            "currency",
            "simultaneous_sessions",
            "enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "currency", "created_at", "updated_at"]

    def get_currency(self, obj):
        return obj.tenant.currency

    def validate_duration_value(self, value):
        if value < 1:
            raise serializers.ValidationError("Duration must be at least 1.")
        return value

    def validate_download_speed_mbps(self, value):
        if value < 1:
            raise serializers.ValidationError("Download speed must be at least 1 Mbps.")
        return value

    def validate_upload_speed_mbps(self, value):
        if value < 1:
            raise serializers.ValidationError("Upload speed must be at least 1 Mbps.")
        return value

    def validate_simultaneous_sessions(self, value):
        if value < 1:
            raise serializers.ValidationError("At least one simultaneous session is required.")
        return value


class SubscriptionSerializer(serializers.ModelSerializer):
    package_name = serializers.CharField(source="package.name", read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "package",
            "package_name",
            "duration_value",
            "duration_unit",
            "started_at",
            "expires_at",
            "status",
        ]
        read_only_fields = fields


class SubscriberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="credential.username", read_only=True)
    active_subscription = serializers.SerializerMethodField()

    class Meta:
        model = Subscriber
        fields = [
            "id",
            "name",
            "phone",
            "address",
            "notes",
            "status",
            "mac_lock_mode",
            "mac_address",
            "last_mac_address",
            "last_authenticated_at",
            "username",
            "active_subscription",
            "created_at",
            "updated_at",
        ]

    def get_active_subscription(self, obj):
        subscription = next(
            (
                item
                for item in obj.subscriptions.all()
                if item.status == Subscription.Status.ACTIVE
            ),
            None,
        )
        if not subscription:
            return None
        return SubscriptionSerializer(subscription).data


class SubscriberCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160)
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(
        choices=Subscriber.Status.choices,
        default=Subscriber.Status.ACTIVE,
    )
    mac_lock_mode = serializers.ChoiceField(
        choices=Subscriber.MacLockMode.choices,
        default=Subscriber.MacLockMode.NONE,
    )
    mac_address = serializers.CharField(max_length=32, required=False, allow_blank=True)
    username = serializers.CharField(max_length=120, required=False, allow_blank=True)
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )
    package_id = serializers.UUIDField(required=False, allow_null=True)
    duration_value = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    duration_unit = serializers.ChoiceField(
        choices=Package.DurationUnit.choices,
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        mode = attrs.get("mac_lock_mode", Subscriber.MacLockMode.NONE)
        mac = attrs.get("mac_address", "")
        if mode == Subscriber.MacLockMode.MANUAL and not mac:
            raise serializers.ValidationError(
                {"mac_address": "MAC address is required for manual locking."}
            )
        if mac:
            try:
                normalize_mac(mac)
            except Exception as exc:
                raise serializers.ValidationError({"mac_address": str(exc)}) from exc
        return attrs


class SubscriberUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160, required=False)
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Subscriber.Status.choices, required=False)
    mac_lock_mode = serializers.ChoiceField(
        choices=Subscriber.MacLockMode.choices,
        required=False,
    )
    mac_address = serializers.CharField(max_length=32, required=False, allow_blank=True)


class PackageAssignmentSerializer(serializers.Serializer):
    package_id = serializers.UUIDField()
    duration_value = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    duration_unit = serializers.ChoiceField(
        choices=Package.DurationUnit.choices,
        required=False,
        allow_null=True,
    )


class RenewalSerializer(serializers.Serializer):
    duration_value = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    duration_unit = serializers.ChoiceField(
        choices=Package.DurationUnit.choices,
        required=False,
        allow_null=True,
    )


class PasswordChangeSerializer(serializers.Serializer):
    password = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )
