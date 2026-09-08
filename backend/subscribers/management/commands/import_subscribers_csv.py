import csv
import os
from datetime import UTC, datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.models import Tenant
from subscribers.models import Package, Subscriber, Subscription
from subscribers.services import create_subscriber


class Command(BaseCommand):
    help = "Import subscribers from a normalized CSV file for Janitor/manual migrations."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="Tenant slug")
        parser.add_argument("--file", required=True, help="CSV file path")
        parser.add_argument("--default-package", help="Package name used when CSV package is empty")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--generate-missing-passwords", action="store_true")
        parser.add_argument(
            "--generated-output",
            help="Write generated credentials to this CSV path (chmod 600).",
        )

    @staticmethod
    def _parse_datetime(value: str):
        value = (value or "").strip()
        if not value:
            return None
        parsed = parse_datetime(value)
        if parsed is None:
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError as exc:
                raise CommandError(f"Invalid datetime: {value}") from exc
        if timezone.is_naive(parsed):
            parsed = parsed.replace(tzinfo=UTC)
        return parsed

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.is_file():
            raise CommandError(f"CSV file not found: {path}")
        if (
            options["generate_missing_passwords"]
            and not options["dry_run"]
            and not options.get("generated_output")
        ):
            raise CommandError(
                "--generated-output is required with --generate-missing-passwords "
                "so generated credentials cannot be lost."
            )

        try:
            tenant = Tenant.objects.get(slug=options["tenant"])
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"Tenant not found: {options['tenant']}") from exc

        default_package = None
        if options.get("default_package"):
            default_package = Package.objects.filter(
                tenant=tenant,
                name=options["default_package"],
            ).first()
            if not default_package:
                raise CommandError(
                    f"Default package not found: {options['default_package']}"
                )

        generated = []
        imported = 0
        skipped = 0
        errors = []

        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            required = {"username", "name"}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise CommandError("CSV must contain at least username,name headers.")

            with transaction.atomic():
                for line_number, row in enumerate(reader, start=2):
                    username = (row.get("username") or "").strip()
                    name = (row.get("name") or "").strip()
                    if not username or not name:
                        errors.append(f"line {line_number}: username and name are required")
                        continue

                    if tenant.subscriber_credentials.filter(username=username).exists():
                        skipped += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"line {line_number}: {username} already exists; skipped"
                            )
                        )
                        continue

                    package_name = (row.get("package") or "").strip()
                    package = default_package
                    if package_name:
                        package = Package.objects.filter(
                            tenant=tenant,
                            name=package_name,
                        ).first()
                        if not package:
                            errors.append(
                                f"line {line_number}: package not found: {package_name}"
                            )
                            continue

                    password = row.get("password") or ""
                    if not password and not options["generate_missing_passwords"]:
                        errors.append(
                            f"line {line_number}: password missing; use --generate-missing-passwords if intentional"
                        )
                        continue

                    status = (row.get("status") or Subscriber.Status.ACTIVE).strip().lower()
                    if status not in Subscriber.Status.values:
                        errors.append(f"line {line_number}: invalid status: {status}")
                        continue

                    mac = (row.get("mac_address") or "").strip()
                    mac_mode = (row.get("mac_lock_mode") or "").strip().lower()
                    if not mac_mode:
                        mac_mode = (
                            Subscriber.MacLockMode.MANUAL
                            if mac
                            else Subscriber.MacLockMode.NONE
                        )
                    if mac_mode not in Subscriber.MacLockMode.values:
                        errors.append(
                            f"line {line_number}: invalid mac_lock_mode: {mac_mode}"
                        )
                        continue

                    try:
                        subscriber, generated_password = create_subscriber(
                            tenant=tenant,
                            data={
                                "name": name,
                                "phone": (row.get("phone") or "").strip(),
                                "address": (row.get("address") or "").strip(),
                                "notes": (row.get("notes") or "").strip(),
                                "status": status,
                                "mac_lock_mode": mac_mode,
                                "mac_address": mac,
                                "username": username,
                                "password": password,
                                "package": package,
                            },
                        )
                    except Exception as exc:
                        errors.append(f"line {line_number}: {exc}")
                        continue

                    started_at = self._parse_datetime(row.get("started_at") or "")
                    expires_at = self._parse_datetime(row.get("expires_at") or "")
                    if package and (started_at or expires_at):
                        subscription = subscriber.subscriptions.filter(
                            status=Subscription.Status.ACTIVE
                        ).first()
                        if subscription:
                            if started_at:
                                subscription.started_at = started_at
                            if expires_at:
                                subscription.expires_at = expires_at
                            if subscription.expires_at <= timezone.now():
                                subscription.status = Subscription.Status.EXPIRED
                                if subscriber.status == Subscriber.Status.ACTIVE:
                                    subscriber.status = Subscriber.Status.EXPIRED
                                    subscriber.save(update_fields=["status", "updated_at"])
                            subscription.save()

                    if generated_password:
                        generated.append((username, generated_password))
                    imported += 1

                if errors:
                    for error in errors:
                        self.stderr.write(self.style.ERROR(error))
                    raise CommandError(
                        f"Import aborted: {len(errors)} invalid row(s). No changes were committed."
                    )

                if options["dry_run"]:
                    transaction.set_rollback(True)

        if generated and not options["dry_run"]:
            output_path = Path(options["generated_output"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["username", "password"])
                writer.writerows(generated)
            os.chmod(output_path, 0o600)
            self.stdout.write(f"Generated credentials: {output_path}")

        mode = "DRY RUN" if options["dry_run"] else "COMMITTED"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: imported={imported}, skipped_existing={skipped}, tenant={tenant.slug}"
            )
        )
