import json

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from .models import (
    AuditLog,
    ImpersonationSession,
    PamirPermission,
    Role,
    Tenant,
    TenantMembership,
)


TENANT_ADMIN_ROLE_NAME = "Tenant Admin"


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or None


def serialize_tenant(tenant):
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "status": tenant.status,
        "timezone": tenant.timezone,
        "currency": tenant.currency,
    }


def serialize_role(role):
    return {
        "id": str(role.id),
        "name": role.name,
        "is_system": role.is_system,
        "is_owner": role.is_owner,
        "permission_codes": list(role.permissions.order_by("code").values_list("code", flat=True)),
    }


def serialize_membership(membership):
    return {
        "id": str(membership.id),
        "email": membership.user.email,
        "name": membership.user.get_full_name(),
        "is_active": membership.is_active,
        "role_ids": [str(value) for value in membership.roles.values_list("id", flat=True)],
    }


def serialize_user(user):
    return {
        "id": user.id,
        "email": user.email,
        "name": user.get_full_name() or user.email,
        "is_active": user.is_active,
        "is_platform_admin": user.is_superuser,
    }


def _json_safe(value):
    if value in (None, ""):
        return {}
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def audit(request, action, *, tenant=None, target=None, before=None, after=None, metadata=None):
    token = getattr(request, "auth", None)
    impersonation = None
    if token:
        impersonation_id = token.get("impersonation_id")
        if impersonation_id:
            impersonation = ImpersonationSession.objects.filter(id=impersonation_id).first()

    AuditLog.objects.create(
        tenant=tenant,
        actor=(
            request.user
            if getattr(request, "user", None) and request.user.is_authenticated
            else None
        ),
        impersonation=impersonation,
        action=action,
        target_type=target.__class__.__name__ if target else "",
        target_id=str(target.pk) if target else "",
        source_ip=client_ip(request),
        before=_json_safe(before),
        after=_json_safe(after),
        metadata=_json_safe(metadata),
    )


def active_memberships(user):
    return (
        TenantMembership.objects.filter(
            user=user,
            is_active=True,
            tenant__status=Tenant.Status.ACTIVE,
        )
        .select_related("tenant")
        .prefetch_related("roles__permissions")
    )


def membership_for(user, tenant):
    return (
        TenantMembership.objects.filter(user=user, tenant=tenant, is_active=True)
        .prefetch_related("roles__permissions")
        .first()
    )


def permission_codes_for_membership(membership):
    if not membership:
        return set()
    return set(
        PamirPermission.objects.filter(roles__memberships=membership).values_list("code", flat=True)
    )


def membership_is_owner(membership):
    return bool(membership and membership.roles.filter(is_owner=True).exists())


def ensure_tenant_admin_role(tenant):
    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name=TENANT_ADMIN_ROLE_NAME,
        defaults={"is_system": True, "is_owner": False},
    )
    changed_fields = []
    if not role.is_system:
        role.is_system = True
        changed_fields.append("is_system")
    if role.is_owner:
        role.is_owner = False
        changed_fields.append("is_owner")
    if changed_fields:
        role.save(update_fields=[*changed_fields, "updated_at"])
    role.permissions.set(PamirPermission.objects.all())
    return role


def ensure_owner_change_is_safe(membership, *, new_roles=None, deactivate=False):
    if not membership_is_owner(membership):
        return

    remains_owner = not deactivate
    if new_roles is not None:
        remains_owner = remains_owner and any(role.is_owner for role in new_roles)

    if remains_owner:
        return

    other_owner_exists = (
        TenantMembership.objects.filter(
            tenant=membership.tenant,
            is_active=True,
            roles__is_owner=True,
            user__is_active=True,
        )
        .exclude(pk=membership.pk)
        .exists()
    )
    if not other_owner_exists:
        raise ValidationError("A tenant must always have at least one active Owner.")


def ensure_user_deactivation_is_safe(user):
    owner_memberships = (
        TenantMembership.objects.filter(
            user=user,
            is_active=True,
            roles__is_owner=True,
            tenant__status=Tenant.Status.ACTIVE,
        )
        .select_related("tenant")
        .distinct()
    )
    for membership in owner_memberships:
        other_owner_exists = (
            TenantMembership.objects.filter(
                tenant=membership.tenant,
                is_active=True,
                roles__is_owner=True,
                user__is_active=True,
            )
            .exclude(user=user)
            .exists()
        )
        if not other_owner_exists:
            raise ValidationError(
                f"{membership.tenant.name} must always have at least one active Owner."
            )


def find_unique_user_by_email(email):
    matches = list(User.objects.filter(email__iexact=email.strip().lower())[:2])
    if len(matches) > 1:
        raise ValidationError(
            "Multiple users share this email; resolve the duplicate accounts first."
        )
    return matches[0] if matches else None


@transaction.atomic
def create_tenant_with_owner(
    *,
    name,
    slug,
    owner_email,
    owner_name="",
    owner_password="",
    timezone_name,
    currency,
):
    email = owner_email.strip().lower()
    user = find_unique_user_by_email(email)
    if user and user.is_superuser:
        raise ValidationError("Platform administrator accounts cannot be tenant members.")
    if user and not user.is_active:
        raise ValidationError("The selected owner account is disabled.")
    if not user and (not owner_name.strip() or not owner_password):
        raise ValidationError("Owner name and password are required when creating a new user.")

    tenant = Tenant.objects.create(
        name=name,
        slug=slug,
        timezone=timezone_name,
        currency=currency.upper(),
    )
    if not user:
        user = User.objects.create_user(
            username=email,
            email=email,
            password=owner_password,
            first_name=owner_name.strip(),
        )

    owner_role = Role.objects.create(tenant=tenant, name="Owner", is_system=True, is_owner=True)
    owner_role.permissions.set(PamirPermission.objects.all())
    ensure_tenant_admin_role(tenant)
    membership = TenantMembership.objects.create(tenant=tenant, user=user)
    membership.roles.add(owner_role)
    return tenant, user, membership


def end_impersonation(session):
    if session.ended_at is None:
        session.ended_at = timezone.now()
        session.save(update_fields=["ended_at"])
