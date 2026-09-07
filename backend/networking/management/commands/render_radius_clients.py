from django.core.management.base import BaseCommand

from networking.services import render_radius_clients


class Command(BaseCommand):
    help = "Render the FreeRADIUS client configuration from registered PamirNet routers."

    def handle(self, *args, **options):
        content = render_radius_clients()
        self.stdout.write(self.style.SUCCESS(f"Rendered FreeRADIUS clients ({len(content)} bytes)."))
