from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.services import create_tenant_with_owner
from networking.models import Router
from subscribers.models import Package, UsagePolicy, UsagePolicyStage

from .models import Voucher
from .policy import record_voucher_usage_delta


@override_settings(RADIUS_INTERNAL_TOKEN="test-radius-token")
class VoucherPhaseTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant, self.owner, _ = create_tenant_with_owner(
            name="AWKH",
            slug="awkh-vouchers",
            owner_email="voucher-owner@awkh.test",
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
            name="Voucher 5M",
            duration_value=1,
            duration_unit=Package.DurationUnit.WEEK,
            download_speed_mbps=5,
            upload_speed_mbps=2,
        )
        login = self.client.post(
            "/api/auth/login/",
            {"email": self.owner.email, "password": "StrongPassword-123!"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    def create_batch(self, quantity=3, sessions=1):
        response = self.client.post(
            "/api/voucher-batches/",
            {
                "name": f"Batch-{Voucher.objects.count()}",
                "package_id": str(self.package.id),
                "quantity": quantity,
                "simultaneous_sessions": sessions,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def radius_authorize(self, username):
        return self.client.post(
            "/api/internal/radius/authorize/",
            {"packet_src_ip": self.router.tunnel_ip, "username": username},
            format="json",
            HTTP_X_PAMIRNET_RADIUS_TOKEN="test-radius-token",
        )

    def radius_post_auth(self, username):
        return self.client.post(
            "/api/internal/radius/post-auth/",
            {"packet_src_ip": self.router.tunnel_ip, "username": username},
            format="json",
            HTTP_X_PAMIRNET_RADIUS_TOKEN="test-radius-token",
        )

    def test_batch_generates_numeric_credentials(self):
        batch = self.create_batch(quantity=5)
        vouchers = Voucher.objects.filter(batch_id=batch["id"])
        self.assertEqual(vouchers.count(), 5)
        for voucher in vouchers:
            self.assertRegex(voucher.username, r"^\d{8}$")
            self.assertRegex(voucher.get_password(), r"^\d{6}$")
            self.assertEqual(voucher.status, Voucher.Status.GENERATED)

    def test_first_successful_login_activates_voucher(self):
        batch = self.create_batch(quantity=1)
        voucher = Voucher.objects.get(batch_id=batch["id"])
        response = self.radius_authorize(voucher.username)
        self.assertEqual(response.data["control:Cleartext-Password"], voucher.get_password())
        self.assertEqual(response.data["reply:Mikrotik-Rate-Limit"], "2M/5M")
        voucher.refresh_from_db()
        self.assertEqual(voucher.status, Voucher.Status.GENERATED)

        response = self.radius_post_auth(voucher.username)
        self.assertEqual(response.status_code, 204)
        voucher.refresh_from_db()
        self.assertEqual(voucher.status, Voucher.Status.ACTIVE)
        self.assertIsNotNone(voucher.activated_at)
        self.assertIsNotNone(voucher.expires_at)

    def test_unlimited_batch_omits_simultaneous_use(self):
        batch = self.create_batch(quantity=1, sessions=None)
        voucher = Voucher.objects.get(batch_id=batch["id"])
        response = self.radius_authorize(voucher.username)
        self.assertNotIn("control:Simultaneous-Use", response.data)

    def test_disable_batch_disables_vouchers_and_rejects_radius(self):
        batch = self.create_batch(quantity=2)
        voucher = Voucher.objects.filter(batch_id=batch["id"]).first()
        response = self.client.post(f"/api/voucher-batches/{batch['id']}/disable/")
        self.assertEqual(response.status_code, 200, response.data)
        voucher.refresh_from_db()
        self.assertEqual(voucher.status, Voucher.Status.DISABLED)
        radius = self.radius_authorize(voucher.username)
        self.assertEqual(radius.data["control:Auth-Type"], "Reject")

    def test_csv_export_contains_plain_voucher_credentials(self):
        batch = self.create_batch(quantity=1)
        voucher = Voucher.objects.get(batch_id=batch["id"])
        response = self.client.get(f"/api/voucher-batches/{batch['id']}/export/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("username,password,package,status", body)
        self.assertIn(voucher.username, body)
        self.assertIn(voucher.get_password(), body)

    def test_subscription_quota_block_marks_voucher_consumed(self):
        policy = UsagePolicy.objects.create(
            tenant=self.tenant,
            package=self.package,
            scope=UsagePolicy.Scope.SUBSCRIPTION,
        )
        UsagePolicyStage.objects.create(
            policy=policy,
            threshold_gb="1.000",
            action=UsagePolicyStage.Action.BLOCK,
        )
        batch = self.create_batch(quantity=1)
        voucher = Voucher.objects.get(batch_id=batch["id"])
        self.radius_post_auth(voucher.username)
        voucher.refresh_from_db()
        record_voucher_usage_delta(voucher, input_bytes=1_100_000_000)

        response = self.radius_authorize(voucher.username)
        self.assertEqual(response.data["control:Auth-Type"], "Reject")
        voucher.refresh_from_db()
        self.assertEqual(voucher.status, Voucher.Status.CONSUMED)

    def test_subscriber_cannot_reuse_voucher_username(self):
        batch = self.create_batch(quantity=1)
        voucher = Voucher.objects.get(batch_id=batch["id"])
        response = self.client.post(
            "/api/subscribers/",
            {
                "name": "Collision",
                "username": voucher.username,
                "password": "SubscriberPass1",
                "package_id": str(self.package.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
