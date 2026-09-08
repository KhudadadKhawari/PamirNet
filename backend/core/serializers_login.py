from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Q
from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=False, allow_blank=False, max_length=254)
    email = serializers.EmailField(required=False, write_only=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    tenant_id = serializers.UUIDField(required=False)

    def validate(self, attrs):
        identifier = str(attrs.get("identifier") or attrs.get("email") or "").strip()
        if not identifier:
            raise serializers.ValidationError(
                {"identifier": "Username or email is required."}
            )

        matching_users = list(
            User.objects.filter(
                Q(username__iexact=identifier) | Q(email__iexact=identifier)
            ).distinct()[:2]
        )
        if len(matching_users) != 1:
            raise serializers.ValidationError("Invalid username/email or password.")

        user = matching_users[0]
        authenticated = authenticate(username=user.username, password=attrs["password"])
        if not authenticated or not authenticated.is_active:
            raise serializers.ValidationError("Invalid username/email or password.")

        attrs["user"] = authenticated
        return attrs
