from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import AuditLog, PamirPermission, Role, Tenant, TenantMembership
from .services import find_unique_user_by_email, membership_is_owner


def validate_timezone_name(value):
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise serializers.ValidationError("Unknown timezone.") from exc
    return value


def normalize_currency(value):
    currency = value.strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise serializers.ValidationError("Currency must be a 3-letter code such as AFN or USD.")
    return currency


def validate_account_password(value):
    try:
        validate_password(value)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages)) from exc
    return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    tenant_id = serializers.UUIDField(required=False)

    def validate(self, attrs):
        email = attrs["email"].strip().lower()
        matching_users = list(User.objects.filter(email__iexact=email)[:2])
        if len(matching_users) != 1:
            raise serializers.ValidationError("Invalid email or password.")

        user = matching_users[0]
        authenticated = authenticate(username=user.username, password=attrs["password"])
        if not authenticated or not authenticated.is_active:
            raise serializers.ValidationError("Invalid email or password.")

        attrs["user"] = authenticated
        return attrs


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PamirPermission
        fields = ["code", "name", "category"]


class RoleSerializer(serializers.ModelSerializer):
    permission_codes = serializers.ListField(
        child=serializers.CharField(max_length=64), write_only=True, required=False
    )
    permissions = PermissionSerializer(many=True, read_only=True)

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "is_system",
            "is_owner",
            "permission_codes",
            "permissions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_system", "is_owner", "created_at", "updated_at"]

    def validate_permission_codes(self, codes):
        unique_codes = list(dict.fromkeys(codes))
        existing = set(
            PamirPermission.objects.filter(code__in=unique_codes).values_list(
                "code", flat=True
            )
        )
        missing = sorted(set(unique_codes) - existing)
        if missing:
            raise serializers.ValidationError(f"Unknown permissions: {', '.join(missing)}")
        return unique_codes

    def create(self, validated_data):
        codes = validated_data.pop("permission_codes", [])
        tenant = self.context["tenant"]
        role = Role.objects.create(tenant=tenant, **validated_data)
        role.permissions.set(PamirPermission.objects.filter(code__in=codes))
        return role

    def update(self, instance, validated_data):
        if instance.is_system:
            raise serializers.ValidationError("System roles cannot be modified.")
        codes = validated_data.pop("permission_codes", None)
        instance = super().update(instance, validated_data)
        if codes is not None:
            instance.permissions.set(PamirPermission.objects.filter(code__in=codes))
        return instance


class TenantMembershipSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    name = serializers.SerializerMethodField()
    roles = RoleSerializer(many=True, read_only=True)

    class Meta:
        model = TenantMembership
        fields = ["id", "email", "name", "is_active", "roles", "created_at", "updated_at"]

    def get_name(self, obj):
        return obj.user.get_full_name() or obj.user.email


class TenantUserCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        required=False,
        allow_blank=True,
    )
    role_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)

    def validate_email(self, value):
        return value.strip().lower()

    def validate_password(self, value):
        if value:
            return validate_account_password(value)
        return value

    def validate_role_ids(self, role_ids):
        tenant = self.context["tenant"]
        roles = list(Role.objects.filter(tenant=tenant, id__in=role_ids))
        if len(roles) != len(set(role_ids)):
            raise serializers.ValidationError("One or more roles are invalid for this tenant.")
        actor_membership = self.context.get("actor_membership")
        if any(role.is_owner for role in roles) and not membership_is_owner(actor_membership):
            raise serializers.ValidationError("Only an Owner can grant the Owner role.")
        self.context["validated_roles"] = roles
        return role_ids

    def validate(self, attrs):
        email = attrs["email"]
        try:
            user = find_unique_user_by_email(email)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"email": exc.message}) from exc

        tenant = self.context["tenant"]
        if user:
            if user.is_superuser:
                raise serializers.ValidationError(
                    {"email": "Platform administrator accounts cannot be tenant members."}
                )
            if TenantMembership.objects.filter(tenant=tenant, user=user).exists():
                raise serializers.ValidationError(
                    {"email": "This user already has a membership in this tenant."}
                )
        else:
            if not attrs.get("name", "").strip():
                raise serializers.ValidationError(
                    {"name": "Name is required when creating a new user."}
                )
            if not attrs.get("password"):
                raise serializers.ValidationError(
                    {"password": "Password is required when creating a new user."}
                )

        self.context["existing_user"] = user
        return attrs

    def create(self, validated_data):
        tenant = self.context["tenant"]
        roles = self.context["validated_roles"]
        user = self.context.get("existing_user")
        if not user:
            email = validated_data["email"]
            user = User.objects.create_user(
                username=email,
                email=email,
                password=validated_data["password"],
                first_name=validated_data["name"].strip(),
            )
        membership = TenantMembership.objects.create(tenant=tenant, user=user)
        membership.roles.set(roles)
        return membership


class TenantUserUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    is_active = serializers.BooleanField(required=False)
    role_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        required=False,
    )

    def validate_role_ids(self, role_ids):
        tenant = self.context["tenant"]
        roles = list(Role.objects.filter(tenant=tenant, id__in=role_ids))
        if len(roles) != len(set(role_ids)):
            raise serializers.ValidationError("One or more roles are invalid for this tenant.")
        actor_membership = self.context.get("actor_membership")
        instance = self.context["membership"]
        owner_change = instance.roles.filter(is_owner=True).exists() != any(
            role.is_owner for role in roles
        )
        if owner_change and not membership_is_owner(actor_membership):
            raise serializers.ValidationError("Only an Owner can grant or remove the Owner role.")
        self.context["validated_roles"] = roles
        return role_ids


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "slug",
            "status",
            "timezone",
            "currency",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def validate_timezone(self, value):
        return validate_timezone_name(value)

    def validate_currency(self, value):
        return normalize_currency(value)


class TenantSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "slug",
            "status",
            "timezone",
            "currency",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "status", "created_at", "updated_at"]

    def validate_timezone(self, value):
        return validate_timezone_name(value)

    def validate_currency(self, value):
        return normalize_currency(value)


class PlatformTenantCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160)
    slug = serializers.SlugField(max_length=80)
    timezone = serializers.CharField(max_length=64, default="Asia/Kabul")
    currency = serializers.CharField(max_length=3, default="AFN")
    owner_email = serializers.EmailField()
    owner_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    owner_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        required=False,
        allow_blank=True,
    )

    def validate_slug(self, value):
        if Tenant.objects.filter(slug=value).exists():
            raise serializers.ValidationError("Tenant slug already exists.")
        return value

    def validate_timezone(self, value):
        return validate_timezone_name(value)

    def validate_currency(self, value):
        return normalize_currency(value)

    def validate_owner_password(self, value):
        if value:
            return validate_account_password(value)
        return value

    def validate(self, attrs):
        email = attrs["owner_email"].strip().lower()
        attrs["owner_email"] = email
        try:
            user = find_unique_user_by_email(email)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"owner_email": exc.message}) from exc
        if user and user.is_superuser:
            raise serializers.ValidationError(
                {"owner_email": "Platform administrator accounts cannot be tenant members."}
            )
        if not user:
            if not attrs.get("owner_name", "").strip():
                raise serializers.ValidationError(
                    {"owner_name": "Owner name is required for a new user."}
                )
            if not attrs.get("owner_password"):
                raise serializers.ValidationError(
                    {"owner_password": "Owner password is required for a new user."}
                )
        return attrs


class PlatformUserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    memberships = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "name", "is_active", "memberships", "date_joined"]

    def get_name(self, obj):
        return obj.get_full_name() or obj.email

    def get_memberships(self, obj):
        memberships = obj.pamirnet_memberships.select_related("tenant").prefetch_related("roles")
        return [
            {
                "id": str(membership.id),
                "tenant_id": str(membership.tenant_id),
                "tenant_name": membership.tenant.name,
                "tenant_slug": membership.tenant.slug,
                "tenant_status": membership.tenant.status,
                "is_active": membership.is_active,
                "roles": [
                    {
                        "id": str(role.id),
                        "name": role.name,
                        "is_owner": role.is_owner,
                    }
                    for role in membership.roles.all()
                ],
            }
            for membership in memberships
        ]


class PlatformUserCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def validate_password(self, value):
        return validate_account_password(value)

    def create(self, validated_data):
        email = validated_data["email"]
        return User.objects.create_user(
            username=email,
            email=email,
            password=validated_data["password"],
            first_name=validated_data["name"].strip(),
        )


class PlatformUserUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    is_active = serializers.BooleanField(required=False)


class PlatformUserTenantSerializer(serializers.Serializer):
    tenant_id = serializers.UUIDField()
    role_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)


class PlatformUserTenantRemoveSerializer(serializers.Serializer):
    tenant_id = serializers.UUIDField()


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True)
    tenant_id = serializers.UUIDField(source="tenant.id", read_only=True, allow_null=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "tenant_id",
            "tenant_name",
            "action",
            "actor_email",
            "target_type",
            "target_id",
            "source_ip",
            "before",
            "after",
            "metadata",
            "created_at",
        ]
