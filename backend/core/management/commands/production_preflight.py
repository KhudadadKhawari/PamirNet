import base64
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Validate PamirNet production configuration before deployment."

    def handle(self, *args, **options):
        errors = []
        warnings = []

        if settings.ENVIRONMENT != "production":
            errors.append("PAMIRNET_ENV must be set to production.")
        if settings.DEBUG:
            errors.append("DJANGO_DEBUG must be disabled in production.")
        if len(settings.SECRET_KEY) < 32 or settings.SECRET_KEY == "dev-only-secret-key":
            errors.append(
                "DJANGO_SECRET_KEY must be a unique random value of at least "
                "32 characters."
            )
        if not settings.ALLOWED_HOSTS or "*" in settings.ALLOWED_HOSTS:
            errors.append(
                "DJANGO_ALLOWED_HOSTS must contain explicit production hostnames "
                "and must not use '*'."
            )
        if not settings.CSRF_TRUSTED_ORIGINS:
            errors.append("CSRF_TRUSTED_ORIGINS must include the production HTTPS origin.")
        elif any(
            not origin.startswith("https://")
            for origin in settings.CSRF_TRUSTED_ORIGINS
        ):
            errors.append("All production CSRF_TRUSTED_ORIGINS entries must use https://.")
        if not settings.SECURE_SSL_REDIRECT:
            errors.append("DJANGO_SECURE_SSL_REDIRECT must be enabled.")
        if settings.SECURE_HSTS_SECONDS < 3600:
            warnings.append("HSTS is below one hour; use 31536000 after TLS has been validated.")

        database = settings.DATABASES["default"]
        if database["ENGINE"] != "django.db.backends.postgresql":
            errors.append("Production must use PostgreSQL, not SQLite.")

        redis = urlparse(settings.REDIS_URL)
        if redis.scheme not in {"redis", "rediss"} or not redis.hostname:
            errors.append("REDIS_URL is invalid.")

        key = settings.PAMIRNET_ENCRYPTION_KEY.strip()
        if not key:
            errors.append(
                "PAMIRNET_ENCRYPTION_KEY is required and must be backed up "
                "separately from the database."
            )
        else:
            try:
                decoded = base64.urlsafe_b64decode(key.encode())
                if len(decoded) != 32:
                    raise ValueError
            except Exception:
                errors.append(
                    "PAMIRNET_ENCRYPTION_KEY must be a Fernet-compatible key "
                    "decoding to 32 bytes."
                )

        token = settings.RADIUS_INTERNAL_TOKEN.strip()
        if len(token) < 32 or token == "dev-radius-internal-token":
            errors.append(
                "RADIUS_INTERNAL_TOKEN must be a unique random value of at least "
                "32 characters."
            )

        if not settings.WIREGUARD_SERVER_PUBLIC_KEY:
            errors.append("WIREGUARD_SERVER_PUBLIC_KEY is required.")
        if not settings.WIREGUARD_ENDPOINT:
            errors.append("WIREGUARD_ENDPOINT is required.")
        if settings.ACCOUNTING_RAW_RETENTION_DAYS < 30:
            warnings.append("ACCOUNTING_RAW_RETENTION_DAYS is below 30 days.")

        for warning in warnings:
            self.stdout.write(self.style.WARNING(f"WARNING: {warning}"))
        if errors:
            for error in errors:
                self.stderr.write(self.style.ERROR(f"ERROR: {error}"))
            raise CommandError(f"Production preflight failed with {len(errors)} error(s).")

        self.stdout.write(self.style.SUCCESS("PamirNet production preflight passed."))
