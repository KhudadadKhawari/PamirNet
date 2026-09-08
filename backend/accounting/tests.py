from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.services import create_tenant_with_owner
from networking.models import Router
from subscribers.models import (
    Package,
    Subscriber,
    SubscriptionUsageCounter,
    UsagePolicy,
    UsagePolicyStage,
)
from subscribers.services import create_subscriber
from vouchers.models import Voucher, VoucherUsageCounter
from vouchers.services import generate_voucher_batch

from .models import RadiusAccountingEvent, RadiusSession, UsageAggregate


@override_settings(RADIUS_INTERNAL_TOKEN="test-radius-token")
class PhaseSixAccountingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant, self.owner, _ = create_tenant_with_owner(
            name="AWKH",
            slug="awkh-phase6",
            owner_email="phase6-owner@awkh.test",
            owner_name="AWKH Owner",
            owner_password="StrongPassword-123!",
            timezone_name="Asia/Kabul",
            currency="AFN",
        )
        self.router = Router(
            tenant=self.tenant,
            name="AWKH Core",
            tunnel_ip="10.250.0.10",
            wireguard_public_key="A" * 43,
            api_username="pamirnet",
        )
        self.router.set_api_password("api-password")
        self.router.set_radius_secret("radius-secret")
        self.router.save()
        self.package = Package.objects.create(
            tenant=self.tenant,
            name="Home 10M",
            duration_value=1,
            duration_unit=Package.DurationUnit.MONTH,
            download_speed_mbps=10,
            upload_speed_mbps=5,
        )
        self.subscriber, _ = create_subscriber(
            tenant=self.tenant,
            data={
                "name": "Customer One",
                "username": "10000001",
                "password": "RadiusPass123",
                "package": self.package,
            },
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

    def accounting(
        self,
        status_type,
        *,
        username="10000001",
        input_bytes=0,
        output_bytes=0,
        session_time=0,
        session_id="session-1",
        terminate_cause="",
    ):
        return self.client.post(
            "/api/internal/radius/accounting/",
            {
                "packet_src_ip": self.router.tunnel_ip,
                "username": username,
                "acct_status_type": status_type,
                "acct_session_id": session_id,
                "acct_unique_session_id": f"unique-{session_id}",
                "framed_ip_address": "10.5.50.100",
                "calling_station_id": "AA:BB:CC:DD:EE:01",
                "nas_port_id": "hotspot1",
                "service_type": "Framed-User",
                "acct_input_octets": input_bytes,
                "acct_output_octets": output_bytes,
                "acct_session_time": session_time,
                "acct_terminate_cause": terminate_cause,
            },
            format="json",
            HTTP_X_PAMIRNET_RADIUS_TOKEN="test-radius-token",
        )

    def test_start_interim_stop_updates_session_counters_and_aggregates(self):
        self.assertEqual(self.accounting("Start").status_code, 204)
        session = RadiusSession.objects.get(username="10000001")
        self.assertEqual(session.status, RadiusSession.Status.ACTIVE)
        self.assertEqual(session.last_rate_limit, "5M/10M")

        self.assertEqual(
            self.accounting(
                "Interim-Update",
                input_bytes=1000,
                output_bytes=2000,
                session_time=60,
            ).status_code,
            204,
        )
        session.refresh_from_db()
        self.assertEqual(session.total_bytes, 3000)
        self.assertEqual(session.session_seconds, 60)
        counters = SubscriptionUsageCounter.objects.filter(
            subscription=session.subscription
        )
        self.assertEqual(counters.count(), 4)
        self.assertTrue(all(counter.bytes_used == 3000 for counter in counters))

        # A retransmitted interim record is idempotent.
        self.accounting(
            "Interim-Update",
            input_bytes=1000,
            output_bytes=2000,
            session_time=60,
        )
        self.assertEqual(RadiusAccountingEvent.objects.count(), 2)
        hourly = UsageAggregate.objects.get(granularity=UsageAggregate.Granularity.HOUR)
        daily = UsageAggregate.objects.get(granularity=UsageAggregate.Granularity.DAY)
        self.assertEqual(hourly.total_bytes, 3000)
        self.assertEqual(daily.total_bytes, 3000)

        self.accounting(
            "Stop",
            input_bytes=1500,
            output_bytes=2500,
            session_time=120,
            terminate_cause="User-Request",
        )
        session.refresh_from_db()
        self.assertEqual(session.status, RadiusSession.Status.STOPPED)
        self.assertEqual(session.total_bytes, 4000)
        self.assertEqual(session.terminate_cause, "User-Request")
        self.assertEqual(RadiusAccountingEvent.objects.count(), 3)
        hourly.refresh_from_db()
        self.assertEqual(hourly.total_bytes, 4000)
        self.assertEqual(hourly.session_seconds, 120)

    def test_voucher_accounting_activates_and_updates_usage(self):
        batch = generate_voucher_batch(
            tenant=self.tenant,
            package=self.package,
            name="Cafe Cards",
            quantity=1,
            simultaneous_sessions=1,
            generated_by=self.owner,
        )
        voucher = batch.vouchers.get()
        response = self.accounting(
            "Start",
            username=voucher.username,
            session_id="voucher-session",
        )
        self.assertEqual(response.status_code, 204)
        voucher.refresh_from_db()
        self.assertEqual(voucher.status, Voucher.Status.ACTIVE)
        self.assertIsNotNone(voucher.activated_at)

        self.accounting(
            "Interim-Update",
            username=voucher.username,
            input_bytes=4000,
            output_bytes=6000,
            session_time=60,
            session_id="voucher-session",
        )
        counters = VoucherUsageCounter.objects.filter(voucher=voucher)
        self.assertEqual(counters.count(), 4)
        self.assertTrue(all(counter.bytes_used == 10000 for counter in counters))

    @patch("accounting.control.subprocess.run")
    def test_disconnect_action_uses_radius_disconnect_request(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = "Received Disconnect-ACK"
        run.return_value.stderr = ""
        self.accounting("Start")
        session = RadiusSession.objects.get(username="10000001")
        response = self.client.post(
            f"/api/sessions/{session.id}/disconnect/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        session.refresh_from_db()
        self.assertIsNotNone(session.disconnect_requested_at)
        command = run.call_args.args[0]
        self.assertIn("disconnect", command)
        self.assertIn("10.250.0.10:3799", command)

    @patch("accounting.control.subprocess.run")
    def test_fup_threshold_sends_coa_and_updates_subscriber_state(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = "Received CoA-ACK"
        run.return_value.stderr = ""
        policy = UsagePolicy.objects.create(
            tenant=self.tenant,
            package=self.package,
            scope=UsagePolicy.Scope.DAILY,
        )
        UsagePolicyStage.objects.create(
            policy=policy,
            threshold_gb=Decimal("0.001"),
            action=UsagePolicyStage.Action.THROTTLE,
            download_speed_mbps=1,
            upload_speed_mbps=1,
        )
        self.accounting("Start")
        self.accounting(
            "Interim-Update",
            input_bytes=600000,
            output_bytes=600000,
            session_time=60,
        )
        session = RadiusSession.objects.get(username="10000001")
        self.assertEqual(session.last_rate_limit, "1M/1M")
        self.assertEqual(session.last_control_action, "coa")
        self.subscriber.refresh_from_db()
        self.assertEqual(self.subscriber.status, Subscriber.Status.ACTIVE)

    def test_dashboard_and_custom_range_analytics(self):
        self.accounting("Start")
        self.accounting(
            "Interim-Update",
            input_bytes=2000,
            output_bytes=3000,
            session_time=60,
        )
        dashboard = self.client.get("/api/dashboard/")
        self.assertEqual(dashboard.status_code, 200, dashboard.data)
        self.assertEqual(dashboard.data["online_sessions"], 1)
        self.assertEqual(dashboard.data["today_total_bytes"], 5000)

        identities = self.client.get(
            "/api/analytics/identities/"
            "?ordering=-total_bytes&identity_type=subscriber"
        )
        self.assertEqual(identities.status_code, 200, identities.data)
        self.assertEqual(identities.data[0]["username"], "10000001")
        self.assertEqual(identities.data[0]["total_bytes"], 5000)

        series = self.client.get("/api/analytics/usage/?granularity=hour")
        self.assertEqual(series.status_code, 200, series.data)
        self.assertEqual(series.data[-1]["total_bytes"], 5000)

    def test_sessions_are_tenant_scoped(self):
        self.accounting("Start")
        other, _, _ = create_tenant_with_owner(
            name="Other ISP",
            slug="phase6-other",
            owner_email="phase6-other@test.invalid",
            owner_name="Other Owner",
            owner_password="StrongPassword-123!",
            timezone_name="Asia/Kabul",
            currency="AFN",
        )
        other_router = Router(
            tenant=other,
            name="Other Router",
            tunnel_ip="10.250.0.20",
            wireguard_public_key="B" * 43,
            api_username="pamirnet",
        )
        other_router.set_api_password("api")
        other_router.set_radius_secret("secret")
        other_router.save()
        RadiusSession.objects.create(
            tenant=other,
            router=other_router,
            identity_type=RadiusSession.IdentityType.SUBSCRIBER,
            identity_key="subscriber:00000000-0000-0000-0000-000000000001",
            username="other-user",
            acct_session_id="other-session",
            status=RadiusSession.Status.ACTIVE,
        )
        response = self.client.get("/api/sessions/?online=true")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["username"], "10000001")
