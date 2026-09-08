import csv
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from core.services import create_tenant_with_owner
from subscribers.models import Package, SubscriberCredential


class ImportSubscribersCsvTests(TestCase):
    def setUp(self):
        self.tenant, _, _ = create_tenant_with_owner(
            name="AWKH",
            slug="awkh-import-test",
            owner_email="owner@awkh-import.test",
            owner_name="AWKH Owner",
            owner_password="StrongPassword-123!",
            timezone_name="Asia/Kabul",
            currency="AFN",
        )
        self.package = Package.objects.create(
            tenant=self.tenant,
            name="Home 10M",
            duration_value=1,
            duration_unit=Package.DurationUnit.MONTH,
            download_speed_mbps=10,
            upload_speed_mbps=5,
        )

    def _csv_file(self):
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            newline="",
            suffix=".csv",
            delete=False,
        )
        writer = csv.writer(handle)
        writer.writerow(
            [
                "username",
                "name",
                "password",
                "phone",
                "status",
                "package",
            ]
        )
        writer.writerow(
            [
                "10000001",
                "Imported Subscriber",
                "RadiusPass123",
                "0700000000",
                "active",
                "Home 10M",
            ]
        )
        handle.close()
        return handle.name

    def test_dry_run_rolls_back(self):
        path = self._csv_file()
        output = StringIO()
        call_command(
            "import_subscribers_csv",
            tenant=self.tenant.slug,
            file=path,
            dry_run=True,
            stdout=output,
        )
        self.assertFalse(
            SubscriberCredential.objects.filter(
                tenant=self.tenant,
                username="10000001",
            ).exists()
        )
        self.assertIn("DRY RUN", output.getvalue())

    def test_import_creates_subscriber_and_subscription(self):
        path = self._csv_file()
        call_command(
            "import_subscribers_csv",
            tenant=self.tenant.slug,
            file=path,
        )
        credential = SubscriberCredential.objects.select_related("subscriber").get(
            tenant=self.tenant,
            username="10000001",
        )
        self.assertEqual(credential.subscriber.name, "Imported Subscriber")
        self.assertEqual(credential.get_password(), "RadiusPass123")
        subscription = credential.subscriber.subscriptions.get()
        self.assertEqual(subscription.package, self.package)
