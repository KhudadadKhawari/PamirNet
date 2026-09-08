from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from .services import create_tenant_with_owner


class LoginIdentifierTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant, self.owner, _ = create_tenant_with_owner(
            name="AWKH",
            slug="awkh-login-identifiers",
            owner_email="owner-login@awkh.test",
            owner_name="AWKH Owner",
            owner_password="StrongPassword-123!",
            timezone_name="Asia/Kabul",
            currency="AFN",
        )
        self.owner.username = "awkhowner"
        self.owner.save(update_fields=["username"])

    def test_tenant_user_can_login_with_username(self):
        response = self.client.post(
            "/api/auth/login/",
            {"identifier": "awkhowner", "password": "StrongPassword-123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access", response.data)

    def test_email_login_remains_supported_with_identifier(self):
        response = self.client.post(
            "/api/auth/login/",
            {
                "identifier": "owner-login@awkh.test",
                "password": "StrongPassword-123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

    def test_legacy_email_payload_remains_supported(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": "owner-login@awkh.test", "password": "StrongPassword-123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

    def test_platform_admin_can_login_with_username(self):
        User.objects.create_superuser(
            username="platformadmin",
            email="platform-login@pamirnet.test",
            password="PlatformStrong-123!",
        )
        response = self.client.post(
            "/api/auth/login/",
            {"identifier": "platformadmin", "password": "PlatformStrong-123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access", response.data)

    def test_unknown_identifier_uses_generic_error(self):
        response = self.client.post(
            "/api/auth/login/",
            {"identifier": "does-not-exist", "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid username/email or password.", str(response.data))
