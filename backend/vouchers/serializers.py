from rest_framework import serializers

from subscribers.models import Package

from .models import Voucher, VoucherBatch


class VoucherSerializer(serializers.ModelSerializer):
    package_name = serializers.CharField(source="package.name", read_only=True)

    class Meta:
        model = Voucher
        fields = [
            "id",
            "batch",
            "package",
            "package_name",
            "username",
            "status",
            "activated_at",
            "expires_at",
            "last_authenticated_at",
            "created_at",
        ]
        read_only_fields = fields


class VoucherBatchSerializer(serializers.ModelSerializer):
    package_name = serializers.CharField(source="package.name", read_only=True)
    generated_by_email = serializers.CharField(source="generated_by.email", read_only=True)
    generated_count = serializers.SerializerMethodField()
    active_count = serializers.SerializerMethodField()
    expired_count = serializers.SerializerMethodField()
    consumed_count = serializers.SerializerMethodField()
    disabled_count = serializers.SerializerMethodField()

    class Meta:
        model = VoucherBatch
        fields = [
            "id",
            "name",
            "package",
            "package_name",
            "quantity",
            "username_length",
            "password_length",
            "simultaneous_sessions",
            "enabled",
            "generated_by_email",
            "generated_count",
            "active_count",
            "expired_count",
            "consumed_count",
            "disabled_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def _count(self, obj, status):
        return obj.vouchers.filter(status=status).count()

    def get_generated_count(self, obj):
        return self._count(obj, Voucher.Status.GENERATED)

    def get_active_count(self, obj):
        return self._count(obj, Voucher.Status.ACTIVE)

    def get_expired_count(self, obj):
        return self._count(obj, Voucher.Status.EXPIRED)

    def get_consumed_count(self, obj):
        return self._count(obj, Voucher.Status.CONSUMED)

    def get_disabled_count(self, obj):
        return self._count(obj, Voucher.Status.DISABLED)


class VoucherBatchCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    package_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)
    simultaneous_sessions = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Batch name is required.")
        return value

    def validate_package_id(self, value):
        tenant = self.context["tenant"]
        if not Package.objects.filter(tenant=tenant, id=value, enabled=True).exists():
            raise serializers.ValidationError("Package not found or disabled.")
        return value
