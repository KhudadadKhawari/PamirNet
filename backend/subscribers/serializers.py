from django.db import transaction
from rest_framework import serializers

from .models import (
    Package,
    Subscriber,
    Subscription,
    UsagePolicy,
    UsagePolicyStage,
)
from .services import normalize_mac


class UsagePolicyStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsagePolicyStage
        fields = [
            "id",
            "threshold_gb",
            "action",
            "download_speed_mbps",
            "upload_speed_mbps",
        ]
        read_only_fields = ["id"]

    def validate_threshold_gb(self, value):
        if value <= 0:
            raise serializers.ValidationError("Threshold must be greater than 0 GB.")
        return value

    def validate(self, attrs):
        action = attrs.get("action")
        download = attrs.get("download_speed_mbps")
        upload = attrs.get("upload_speed_mbps")
        if action == UsagePolicyStage.Action.THROTTLE:
            if not download or not upload:
                raise serializers.ValidationError(
                    "Throttle stages require both download and upload speeds."
                )
        elif action == UsagePolicyStage.Action.BLOCK:
            attrs["download_speed_mbps"] = None
            attrs["upload_speed_mbps"] = None
        return attrs


class UsagePolicySerializer(serializers.ModelSerializer):
    stages = UsagePolicyStageSerializer(many=True, allow_empty=False)

    class Meta:
        model = UsagePolicy
        fields = ["id", "scope", "enabled", "stages"]
        read_only_fields = ["id"]

    def validate_stages(self, stages):
        thresholds = [stage["threshold_gb"] for stage in stages]
        if len(thresholds) != len(set(thresholds)):
            raise serializers.ValidationError("Stage thresholds must be unique.")
        return stages


class PackageSerializer(serializers.ModelSerializer):
    currency = serializers.SerializerMethodField()
    usage_policies = UsagePolicySerializer(many=True, required=False)

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
            "usage_policies",
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

    def validate(self, attrs):
        policies = attrs.get("usage_policies")
        if policies is None:
            return attrs
        scopes = [policy["scope"] for policy in policies]
        if len(scopes) != len(set(scopes)):
            raise serializers.ValidationError(
                {"usage_policies": "Only one policy per usage scope is allowed."}
            )
        download = attrs.get(
            "download_speed_mbps",
            getattr(self.instance, "download_speed_mbps", None),
        )
        upload = attrs.get(
            "upload_speed_mbps",
            getattr(self.instance, "upload_speed_mbps", None),
        )
        for policy in policies:
            for stage in policy["stages"]:
                if stage["action"] != UsagePolicyStage.Action.THROTTLE:
                    continue
                if download and stage["download_speed_mbps"] > download:
                    raise serializers.ValidationError(
                        {"usage_policies": "FUP download speed cannot exceed package speed."}
                    )
                if upload and stage["upload_speed_mbps"] > upload:
                    raise serializers.ValidationError(
                        {"usage_policies": "FUP upload speed cannot exceed package speed."}
                    )
        return attrs

    @staticmethod
    def _replace_usage_policies(package, policies):
        package.usage_policies.all().delete()
        for policy_data in policies:
            stages = policy_data.pop("stages")
            policy = UsagePolicy.objects.create(
                tenant=package.tenant,
                package=package,
                **policy_data,
            )
            UsagePolicyStage.objects.bulk_create(
                [UsagePolicyStage(policy=policy, **stage) for stage in stages]
            )

    @transaction.atomic
    def create(self, validated_data):
        policies = validated_data.pop("usage_policies", [])
        package = super().create(validated_data)
        self._replace_usage_policies(package, policies)
        return package

    @transaction.atomic
    def update(self, instance, validated_data):
        policies = validated_data.pop("usage_policies", None)
        package = super().update(instance, validated_data)
        if policies is not None:
            self._replace_usage_policies(package, policies)
        return package


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
