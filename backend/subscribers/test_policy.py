from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.services import create_tenant_with_owner
from networking.models import Router

from .models import (
    Package,
    Subscriber,
    Subscription,
    UsagePolicy,
    UsagePolicyStage,
)
from .policy import calculate_effective_policy, record_usage_delta
from .radius import RadiusReject, authorize_radius
from .serializers import PackageSerializer
from .services import create_subscriber


class PhaseFourPolicyTests(TestCase):
    def setUp(self):
        self.tenant, _, _ = create_tenant_with_owner(
            name="Policy ISP",
            slug="policy-isp",
            owner_email="policy-owner@test.invalid",
            owner_name="Policy Owner",
            owner_password="StrongPassword-123!",
            timezone_name="Asia/Kabul",
            currency="AFN",
        )
        self.package = Package.objects.create(
            tenant=self.tenant,
            name="Home 20M",
            duration_value=1,
            duration_unit=Package.DurationUnit.MONTH,
            download_speed_mbps=20,
            upload_speed_mbps=10,
        )
        self.subscriber, _ = create_subscriber(
            tenant=self.tenant,
            data={
                "name": "Policy Customer",
                "username": "90909090",
                "password": "RadiusPass123",
                "package": self.package,
            },
        )
        self.subscription = self.subscriber.subscriptions.get(status=Subscription.Status.ACTIVE)

    def add_stage(
        self,
        *,
        scope,
        threshold_gb,
        action="throttle",
        download=5,
        upload=2,
    ):
        policy, _ = UsagePolicy.objects.get_or_create(
            tenant=self.tenant,
            package=self.package,
            scope=scope,
        )
        return UsagePolicyStage.objects.create(
            policy=policy,
            threshold_gb=threshold_gb,
            action=action,
            download_speed_mbps=download if action == "throttle" else None,
            upload_speed_mbps=upload if action == "throttle" else None,
        )

    def test_nested_package_policy_configuration(self):
        package = Package.objects.create(
            tenant=self.tenant,
            name="Editable",
            duration_value=1,
            duration_unit="month",
            download_speed_mbps=50,
            upload_speed_mbps=20,
        )
        serializer = PackageSerializer(
            package,
            data={
                "usage_policies": [
                    {
                        "scope": "daily",
                        "enabled": True,
                        "stages": [
                            {
                                "threshold_gb": "10.000",
                                "action": "throttle",
                                "download_speed_mbps": 10,
                                "upload_speed_mbps": 5,
                            },
                            {
                                "threshold_gb": "20.000",
                                "action": "block",
                            },
                        ],
                    }
                ]
            },
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        policy = package.usage_policies.get(scope=UsagePolicy.Scope.DAILY)
        self.assertEqual(policy.stages.count(), 2)
        self.assertEqual(policy.stages.last().action, UsagePolicyStage.Action.BLOCK)

    def test_most_restrictive_speed_wins_across_scopes(self):
        self.add_stage(
            scope=UsagePolicy.Scope.DAILY,
            threshold_gb="1.000",
            download=8,
            upload=4,
        )
        self.add_stage(
            scope=UsagePolicy.Scope.MONTHLY,
            threshold_gb="1.000",
            download=3,
            upload=1,
        )
        record_usage_delta(self.subscription, input_bytes=1_100_000_000)
        effective = calculate_effective_policy(self.subscription)
        self.assertFalse(effective.blocked)
        self.assertEqual(effective.download_speed_mbps, 3)
        self.assertEqual(effective.upload_speed_mbps, 1)

    def test_daily_counter_resets_but_subscription_counter_does_not(self):
        self.add_stage(scope=UsagePolicy.Scope.DAILY, threshold_gb="10.000")
        self.add_stage(scope=UsagePolicy.Scope.SUBSCRIPTION, threshold_gb="10.000")
        now = timezone.now()
        record_usage_delta(self.subscription, input_bytes=600_000_000, at=now)
        later = now + timedelta(days=1, minutes=5)
        effective = calculate_effective_policy(self.subscription, at=later)
        self.assertEqual(effective.usage[UsagePolicy.Scope.DAILY]["bytes_used"], 0)
        self.assertEqual(
            effective.usage[UsagePolicy.Scope.SUBSCRIPTION]["bytes_used"],
            600_000_000,
        )

    def test_block_stage_rejects_radius_and_marks_quota_exhausted(self):
        Router.objects.create(
            tenant=self.tenant,
            name="Core Router",
            tunnel_ip="10.250.44.10",
            wireguard_public_key="C" * 43,
            api_username="pamirnet",
            api_password_cipher="unused",
            radius_secret_cipher="unused",
        )
        self.add_stage(
            scope=UsagePolicy.Scope.SUBSCRIPTION,
            threshold_gb="1.000",
            action="block",
        )
        record_usage_delta(self.subscription, output_bytes=1_100_000_000)
        with self.assertRaises(RadiusReject):
            authorize_radius(
                packet_src_ip="10.250.44.10",
                username="90909090",
                calling_station_id="AA:BB:CC:DD:EE:44",
            )
        self.subscriber.refresh_from_db()
        self.assertEqual(self.subscriber.status, Subscriber.Status.QUOTA_EXHAUSTED)

    def test_fup_throttle_cannot_exceed_base_package_speed(self):
        serializer = PackageSerializer(
            self.package,
            data={
                "usage_policies": [
                    {
                        "scope": "weekly",
                        "stages": [
                            {
                                "threshold_gb": "1.000",
                                "action": "throttle",
                                "download_speed_mbps": 21,
                                "upload_speed_mbps": 5,
                            }
                        ],
                    }
                ]
            },
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("usage_policies", serializer.errors)
