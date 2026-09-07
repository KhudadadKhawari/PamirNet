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

    def test_owner_bootstrap_has_all_permissions(self):
        owner_role = self.membership.roles.get(is_owner=True)
        self.assertEqual(owner_role.permissions.count(), PamirPermission.objects.count())

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

    def test_platform_admin_can_impersonate(self):
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
        platform_token = response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {platform_token}")

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
