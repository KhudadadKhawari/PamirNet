from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import AuditLog, PamirPermission, Role, TenantMembership
from .services import create_tenant_with_owner


class HealthEndpointTests(TestCase):
    def test_health_endpoint(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["service"], "pamirnet-api")


class PhaseOneApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant, self.owner, self.membership = create_tenant_with_owner(
            name="AWKH",
            slug="awkh",
            owner_email="owner@awkh.test",
            owner_name="AWKH Owner",
            owner_password="StrongPassword-123!",
            timezone_name="Asia/Kabul",
            currency="AFN",
        )

    def login(self, email="owner@awkh.test", password="StrongPassword-123!"):
        response = self.client.post(
            "/api/auth/login/",
            {"email": email, "password": password},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        token = response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return token

    def platform_login(self):
        admin = User.objects.create_superuser(
            username="platform@pamirnet.test",
            email="platform@pamirnet.test",
            password="PlatformStrong-123!",
        )
        self.client.credentials()
        response = self.client.post(
            "/api/auth/login/",
            {"email": admin.email, "password": "PlatformStrong-123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        token = response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return admin, token

    def test_owner_bootstrap_has_all_permissions(self):
        owner_role = self.membership.roles.get(is_owner=True)
        self.assertEqual(owner_role.permissions.count(), PamirPermission.objects.count())
        tenant_admin_role = Role.objects.get(tenant=self.tenant, name="Tenant Admin")
        self.assertTrue(tenant_admin_role.is_system)
        self.assertFalse(tenant_admin_role.is_owner)
        self.assertEqual(tenant_admin_role.permissions.count(), PamirPermission.objects.count())

    def test_login_and_me_returns_tenant_context(self):
        self.login()
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["tenant"]["id"], str(self.tenant.id))
        self.assertIn("role.manage", response.data["permissions"])

    def test_role_crud_is_tenant_scoped(self):
        self.login()
        response = self.client.post(
            "/api/roles/",
            {"name": "Operator", "permission_codes": ["dashboard.view", "subscriber.view"]},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        role_id = response.data["id"]

        other_tenant, _, _ = create_tenant_with_owner(
            name="Other ISP",
            slug="other-isp",
            owner_email="owner@other.test",
            owner_name="Other Owner",
            owner_password="StrongPassword-123!",
            timezone_name="Asia/Kabul",
            currency="AFN",
        )
        other_role = Role.objects.create(tenant=other_tenant, name="Other")
        response = self.client.get(f"/api/roles/{other_role.id}/")
        self.assertEqual(response.status_code, 404)

        response = self.client.patch(
            f"/api/roles/{role_id}/",
            {"name": "Support"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_last_owner_cannot_be_disabled(self):
        self.login()
        response = self.client.delete(f"/api/users/{self.membership.id}/")
        self.assertEqual(response.status_code, 409)
        self.membership.refresh_from_db()
        self.assertTrue(self.membership.is_active)

    def test_user_creation_and_audit(self):
        self.login()
        role = Role.objects.create(tenant=self.tenant, name="Operator")
        role.permissions.set(PamirPermission.objects.filter(code__in=["dashboard.view"]))
        response = self.client.post(
            "/api/users/",
            {
                "email": "operator@awkh.test",
                "name": "Operator",
                "password": "AnotherStrong-123!",
                "role_ids": [str(role.id)],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(User.objects.filter(email="operator@awkh.test").exists())
        self.assertTrue(AuditLog.objects.filter(tenant=self.tenant, action="user.created").exists())

    def test_existing_user_can_be_assigned_to_tenant(self):
        existing = User.objects.create_user(
            username="shared@example.test",
            email="shared@example.test",
            password="SharedStrong-123!",
            first_name="Shared User",
        )
        self.login()
        role = Role.objects.create(tenant=self.tenant, name="Support")
        role.permissions.set(PamirPermission.objects.filter(code="dashboard.view"))
        response = self.client.post(
            "/api/users/",
            {
                "email": existing.email,
                "role_ids": [str(role.id)],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        membership = TenantMembership.objects.get(tenant=self.tenant, user=existing)
        self.assertTrue(membership.roles.filter(id=role.id).exists())
        self.assertTrue(
            AuditLog.objects.filter(tenant=self.tenant, action="user.assigned").exists()
        )

    def test_platform_admin_can_impersonate(self):
        _, platform_token = self.platform_login()
        response = self.client.post(
            f"/api/platform/tenants/{self.tenant.id}/impersonate/",
            {"reason": "Support"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertTrue(me.data["impersonating"])
        self.assertEqual(me.data["tenant"]["id"], str(self.tenant.id))
        self.assertEqual(me.data["permissions"], ["*"])
        self.assertTrue(platform_token)

    def test_platform_can_create_tenant_with_existing_owner(self):
        existing = User.objects.create_user(
            username="existing-owner@example.test",
            email="existing-owner@example.test",
            password="ExistingStrong-123!",
            first_name="Existing Owner",
        )
        self.platform_login()
        response = self.client.post(
            "/api/platform/tenants/",
            {
                "name": "Second ISP",
                "slug": "second-isp",
                "timezone": "Asia/Dushanbe",
                "currency": "TJS",
                "owner_email": existing.email,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        membership = TenantMembership.objects.get(
            tenant_id=response.data["id"],
            user=existing,
        )
        self.assertTrue(membership.roles.filter(is_owner=True).exists())
        self.assertTrue(
            Role.objects.filter(
                tenant_id=response.data["id"],
                name="Tenant Admin",
            ).exists()
        )

    def test_platform_assignment_automatically_grants_tenant_admin(self):
        self.platform_login()
        response = self.client.post(
            "/api/platform/users/",
            {
                "email": "new-user@example.test",
                "name": "New User",
                "password": "NewUserStrong-123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        user_id = response.data["id"]

        response = self.client.post(
            f"/api/platform/users/{user_id}/assign-tenant/",
            {"tenant_id": str(self.tenant.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        membership = TenantMembership.objects.get(user_id=user_id, tenant=self.tenant)
        self.assertTrue(membership.is_active)
        self.assertEqual(membership.roles.count(), 1)
        tenant_admin_role = membership.roles.get()
        self.assertEqual(tenant_admin_role.name, "Tenant Admin")
        self.assertTrue(tenant_admin_role.is_system)
        self.assertEqual(tenant_admin_role.permissions.count(), PamirPermission.objects.count())

        user = User.objects.get(id=user_id)
        self.client.credentials()
        login = self.client.post(
            "/api/auth/login/",
            {"email": user.email, "password": "NewUserStrong-123!"},
            format="json",
        )
        self.assertEqual(login.status_code, 200, login.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        role_create = self.client.post(
            "/api/roles/",
            {"name": "Technician", "permission_codes": ["router.view"]},
            format="json",
        )
        self.assertEqual(role_create.status_code, 201, role_create.data)

    def test_platform_user_remove_tenant_membership(self):
        self.platform_login()
        user = User.objects.create_user(
            username="remove-user@example.test",
            email="remove-user@example.test",
            password="RemoveStrong-123!",
        )
        tenant_admin = Role.objects.get(tenant=self.tenant, name="Tenant Admin")
        membership = TenantMembership.objects.create(tenant=self.tenant, user=user)
        membership.roles.add(tenant_admin)

        response = self.client.post(
            f"/api/platform/users/{user.id}/remove-tenant/",
            {"tenant_id": str(self.tenant.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        membership.refresh_from_db()
        self.assertFalse(membership.is_active)

    def test_platform_can_suspend_and_reactivate_tenant(self):
        self.platform_login()
        response = self.client.patch(
            f"/api/platform/tenants/{self.tenant.id}/",
            {"status": "suspended"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "suspended")
        response = self.client.patch(
            f"/api/platform/tenants/{self.tenant.id}/",
            {"status": "active"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "active")

    def test_tenant_settings_and_audit_are_functional(self):
        self.login()
        response = self.client.patch(
            "/api/tenant/",
            {"name": "AWKH Networks", "timezone": "Asia/Dushanbe", "currency": "tjs"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["currency"], "TJS")
        audit_response = self.client.get("/api/audit/")
        self.assertEqual(audit_response.status_code, 200)
        self.assertTrue(
            any(item["action"] == "tenant.settings.updated" for item in audit_response.data)
        )

    def test_non_owner_with_user_manage_cannot_grant_owner(self):
        manager_role = Role.objects.create(tenant=self.tenant, name="User Manager")
        manager_role.permissions.set(PamirPermission.objects.filter(code="user.manage"))
        manager = User.objects.create_user(
            username="manager@awkh.test",
            email="manager@awkh.test",
            password="ManagerStrong-123!",
        )
        manager_membership = TenantMembership.objects.create(tenant=self.tenant, user=manager)
        manager_membership.roles.add(manager_role)

        self.client.credentials()
        response = self.client.post(
            "/api/auth/login/",
            {"email": manager.email, "password": "ManagerStrong-123!"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        owner_role = self.membership.roles.get(is_owner=True)
        response = self.client.post(
            "/api/users/",
            {
                "email": "escalated@awkh.test",
                "name": "Escalated",
                "password": "EscalatedStrong-123!",
                "role_ids": [str(owner_role.id)],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
