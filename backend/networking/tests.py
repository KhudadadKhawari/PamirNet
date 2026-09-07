import base64
import os
import tempfile
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.services import create_tenant_with_owner

from .models import Router
from .services import parse_uptime_seconds, render_radius_clients

TEST_WG_KEY = base64.b64encode(b"P" * 32).decode()


@override_settings(
    WIREGUARD_SERVER_PUBLIC_KEY=TEST_WG_KEY,
    WIREGUARD_ENDPOINT="vpn.example.test",
    WIREGUARD_CLIENT_SUBNET="10.250.0.0/24",
    WIREGUARD_SERVER_ADDRESS="10.250.0.1/24",
)
class PhaseTwoRouterTests(TestCase):
    def setUp(self):
        self.radius_file = tempfile.NamedTemporaryFile(delete=False)
        self.radius_file.close()
        self.settings_override = override_settings(
            RADIUS_CLIENTS_FILE=self.radius_file.name
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self._remove_radius_file)

        self.client = APIClient()
        self.tenant, _, _ = create_tenant_with_owner(
            name="AWKH",
            slug="awkh",
            owner_email="owner@awkh.test",
            owner_name="AWKH Owner",
            owner_password="StrongPassword-123!",
            timezone_name="Asia/Kabul",
            currency="AFN",
        )
        response = self.client.post(
            "/api/auth/login/",
            {"email": "owner@awkh.test", "password": "StrongPassword-123!"},
            format="json",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {response.data['access']}"
        )

    def _remove_radius_file(self):
        if os.path.exists(self.radius_file.name):
            os.unlink(self.radius_file.name)

    def create_router(self, name="Core Router"):
        return self.client.post(
            "/api/network/routers/",
            {
                "name": name,
                "api_protocol": "api",
                "api_username": "pamirnet",
                "api_password": "router-secret",
            },
            format="json",
        )

    def test_router_create_allocates_tunnel_and_returns_one_time_config(self):
        response = self.create_router()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["router"]["tunnel_ip"], "10.250.0.10")
        self.assertIn("wireguard_private_key", response.data["provisioning"])
        self.assertIn("/radius add", response.data["provisioning"]["routeros_script"])
        self.assertNotIn("api_password_cipher", response.data["router"])
        self.assertNotIn("radius_secret_cipher", response.data["router"])

    def test_router_list_is_tenant_scoped(self):
        response = self.create_router()
        self.assertEqual(response.status_code, 201)
        other, _, _ = create_tenant_with_owner(
            name="Other ISP",
            slug="other",
            owner_email="other@test.invalid",
            owner_name="Other",
            owner_password="StrongPassword-123!",
            timezone_name="Asia/Kabul",
            currency="AFN",
        )
        other_router = Router(
            tenant=other,
            name="Other Router",
            tunnel_ip="10.250.0.20",
            wireguard_public_key=base64.b64encode(b"Q" * 32).decode(),
            api_username="x",
        )
        other_router.set_api_password("x")
        other_router.set_radius_secret("x")
        other_router.save()
        listed = self.client.get("/api/network/routers/")
        self.assertEqual(len(listed.data), 1)
        hidden = self.client.get(f"/api/network/routers/{other_router.id}/")
        self.assertEqual(hidden.status_code, 404)

    def test_radius_client_renderer_contains_only_enabled_router_secret(self):
        response = self.create_router()
        router = Router.objects.get(id=response.data["router"]["id"])
        content = render_radius_clients()
        self.assertIn(router.tunnel_ip, content)
        self.assertIn(router.get_radius_secret(), content)
        router.enabled = False
        router.save(update_fields=["enabled"])
        self.assertNotIn(router.tunnel_ip, render_radius_clients())

    @patch("networking.services.MikroTikClient")
    def test_connectivity_action_updates_health(self, client_class):
        response = self.create_router()
        router_id = response.data["router"]["id"]
        client_class.return_value.resource.return_value = {
            "version": "7.20",
            "uptime": "1d2h3m4s",
        }
        result = self.client.post(
            f"/api/network/routers/{router_id}/test-connectivity/"
        )
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data["status"], "online")
        self.assertEqual(result.data["routeros_version"], "7.20")
        self.assertEqual(result.data["packet_loss_percent"], 0.0)

    def test_uptime_parser(self):
        self.assertEqual(parse_uptime_seconds("1w2d3h4m5s"), 788645)
        self.assertEqual(parse_uptime_seconds("2d03:04:05"), 183845)
