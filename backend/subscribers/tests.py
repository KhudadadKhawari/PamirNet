from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.services import create_tenant_with_owner
from networking.models import Router

from .models import Package, Subscriber, SubscriberCredential, Subscription
from .services import create_subscriber


@override_settings(RADIUS_INTERNAL_TOKEN="test-radius-token")
class PhaseThreeApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant, self.owner, _ = create_tenant_with_owner(
            name="AWKH",
            slug="awkh-phase3",
            owner_email="phase3-owner@awkh.test",
            owner_name="AWKH Owner",
            owner_password="StrongPassword-123!",
            timezone_name="Asia/Kabul",
            currency="AFN",
        )
        self.router = Router.objects.create(
            tenant=self.tenant,
            name="AWKH Core",
            tunnel_ip="10.250.0.10",
            wireguard_public_key="A" * 43,
            api_username="pamirnet",
            api_password_cipher="unused",
            radius_secret_cipher="unused",
        )
        self.package = Package.objects.create(
            tenant=self.tenant,
            name="Home 10M",
            duration_value=1,
            duration_unit=Package.DurationUnit.MONTH,
            download_speed_mbps=10,
            upload_speed_mbps=5,
            price="900.00",
        )
        self.login()

    def login(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": self.owner.email, "password": "StrongPassword-123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def create_manual_subscriber(self, username="10000001", password="RadiusPass123"):
        response = self.client.post(
            "/api/subscribers/",
            {
                "name": "Customer One",
                "username": username,
                "password": password,
                "package_id": str(self.package.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return Subscriber.objects.get(id=response.data["subscriber"]["id"])

    def radius_authorize(self, router_ip, username, mac="AA:BB:CC:DD:EE:01"):
        return self.client.post(
            "/api/internal/radius/authorize/",
            {
                "packet_src_ip": router_ip,
                "username": username,
                "calling_station_id": mac,
            },
            format="json",
            HTTP_X_PAMIRNET_RADIUS_TOKEN="test-radius-token",
        )

    def test_package_crud_is_tenant_scoped(self):
        response = self.client.post(
            "/api/packages/",
            {
                "name": "Weekly 5M",
                "duration_value": 1,
                "duration_unit": "week",
                "download_speed_mbps": 5,
                "upload_speed_mbps": 2,
                "price": "250.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["currency"], "AFN")

        other, _, _ = create_tenant_with_owner(
            name="Other ISP",
            slug="other-phase3",
            owner_email="other-phase3@test.invalid",
            owner_name="Other",
            owner_password="StrongPassword-123!",
            timezone_name="Asia/Kabul",
            currency="AFN",
        )
        other_package = Package.objects.create(
            tenant=other,
            name="Hidden",
            duration_value=1,
            duration_unit="month",
            download_speed_mbps=2,
            upload_speed_mbps=1,
        )
        response = self.client.get(f"/api/packages/{other_package.id}/")
        self.assertEqual(response.status_code, 404)

    def test_auto_credentials_are_generated_and_password_is_not_listed(self):
        response = self.client.post(
            "/api/subscribers/",
            {"name": "Generated User", "package_id": str(self.package.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertRegex(response.data["subscriber"]["username"], r"^\d{8}$")
        self.assertEqual(len(response.data["generated_password"]), 12)
        subscriber_id = response.data["subscriber"]["id"]
        response = self.client.get(f"/api/subscribers/{subscriber_id}/")
        self.assertNotIn("password", response.data)
        credential = SubscriberCredential.objects.get(subscriber_id=subscriber_id)
        self.assertNotEqual(credential.password_cipher, response.data.get("generated_password"))

    def test_radius_authorization_returns_tenant_package_policy(self):
        subscriber = self.create_manual_subscriber()
        response = self.radius_authorize("10.250.0.10", subscriber.credential.username)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["control:Cleartext-Password"], "RadiusPass123")
        self.assertEqual(response.data["reply:Mikrotik-Rate-Limit"], "5M/10M")
        self.assertGreater(int(response.data["reply:Session-Timeout"]), 0)
        self.assertEqual(response.data["reply:Acct-Interim-Interval"], "60")

    def test_duplicate_username_isolated_by_nas_tenant(self):
        self.create_manual_subscriber(username="42424242", password="AWKHPass123")
        other, _, _ = create_tenant_with_owner(
            name="Other ISP",
            slug="other-radius",
            owner_email="other-radius@test.invalid",
            owner_name="Other",
            owner_password="StrongPassword-123!",
            timezone_name="Asia/Kabul",
            currency="AFN",
        )
        other_router = Router.objects.create(
            tenant=other,
            name="Other Router",
            tunnel_ip="10.250.0.20",
            wireguard_public_key="B" * 43,
            api_username="pamirnet",
            api_password_cipher="unused",
            radius_secret_cipher="unused",
        )
        other_package = Package.objects.create(
            tenant=other,
            name="Other 4M",
            duration_value=1,
            duration_unit="month",
            download_speed_mbps=4,
            upload_speed_mbps=2,
        )
        create_subscriber(
            tenant=other,
            data={
                "name": "Other Customer",
                "username": "42424242",
                "password": "OtherPass123",
                "package": other_package,
            },
        )

        awkh = self.radius_authorize("10.250.0.10", "42424242")
        other_response = self.radius_authorize(other_router.tunnel_ip, "42424242")
        self.assertEqual(awkh.data["control:Cleartext-Password"], "AWKHPass123")
        self.assertEqual(other_response.data["control:Cleartext-Password"], "OtherPass123")
        self.assertEqual(other_response.data["reply:Mikrotik-Rate-Limit"], "2M/4M")

    def test_expired_subscription_is_rejected_and_status_updated(self):
        subscriber = self.create_manual_subscriber()
        subscription = subscriber.subscriptions.get(status=Subscription.Status.ACTIVE)
        subscription.expires_at = timezone.now() - timedelta(seconds=1)
        subscription.save(update_fields=["expires_at"])
        response = self.radius_authorize("10.250.0.10", subscriber.credential.username)
        self.assertEqual(response.data["control:Auth-Type"], "Reject")
        subscriber.refresh_from_db()
        self.assertEqual(subscriber.status, Subscriber.Status.EXPIRED)

    def test_first_login_mac_binding_happens_only_after_post_auth(self):
        response = self.client.post(
            "/api/subscribers/",
            {
                "name": "MAC User",
                "username": "33334444",
                "password": "MacPass123",
                "package_id": str(self.package.id),
                "mac_lock_mode": "first_login",
            },
            format="json",
        )
        subscriber = Subscriber.objects.get(id=response.data["subscriber"]["id"])
        authorize = self.radius_authorize(
            "10.250.0.10",
            "33334444",
            "AA-BB-CC-DD-EE-11",
        )
        self.assertIn("control:Cleartext-Password", authorize.data)
        subscriber.refresh_from_db()
        self.assertEqual(subscriber.mac_address, "")

        response = self.client.post(
            "/api/internal/radius/post-auth/",
            {
                "packet_src_ip": "10.250.0.10",
                "username": "33334444",
                "calling_station_id": "AA-BB-CC-DD-EE-11",
            },
            format="json",
            HTTP_X_PAMIRNET_RADIUS_TOKEN="test-radius-token",
        )
        self.assertEqual(response.status_code, 204)
        subscriber.refresh_from_db()
        self.assertEqual(subscriber.mac_address, "AA:BB:CC:DD:EE:11")
        rejected = self.radius_authorize(
            "10.250.0.10",
            "33334444",
            "AA:BB:CC:DD:EE:12",
        )
        self.assertEqual(rejected.data["control:Auth-Type"], "Reject")

    def test_package_change_and_renew_create_subscription_history(self):
        subscriber = self.create_manual_subscriber()
        old_subscription = subscriber.subscriptions.get(status=Subscription.Status.ACTIVE)
        second = Package.objects.create(
            tenant=self.tenant,
            name="Home 20M",
            duration_value=2,
            duration_unit="week",
            download_speed_mbps=20,
            upload_speed_mbps=10,
        )
        response = self.client.post(
            f"/api/subscribers/{subscriber.id}/assign-package/",
            {"package_id": str(second.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        old_subscription.refresh_from_db()
        self.assertEqual(old_subscription.status, Subscription.Status.CLOSED)
        active = subscriber.subscriptions.get(status=Subscription.Status.ACTIVE)
        self.assertEqual(active.package_id, second.id)

        response = self.client.post(
            f"/api/subscribers/{subscriber.id}/renew/",
            {"duration_value": 1, "duration_unit": "month"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            subscriber.subscriptions.filter(status=Subscription.Status.ACTIVE).count(),
            1,
        )
        self.assertGreaterEqual(subscriber.subscriptions.count(), 3)

    def test_radius_internal_endpoint_requires_shared_token(self):
        response = self.client.post(
            "/api/internal/radius/authorize/",
            {"packet_src_ip": "10.250.0.10", "username": "anything"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
