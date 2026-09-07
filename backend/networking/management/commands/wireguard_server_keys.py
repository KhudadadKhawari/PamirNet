from django.core.management.base import BaseCommand

from networking.wireguard import generate_keypair


class Command(BaseCommand):
    help = "Generate a WireGuard key pair for the PamirNet VPS. The private key is never persisted."

    def handle(self, *args, **options):
        pair = generate_keypair()
        self.stdout.write("Store these securely; the private key is shown only now:\n")
        self.stdout.write(f"WIREGUARD_SERVER_PRIVATE_KEY={pair.private_key}")
        self.stdout.write(f"WIREGUARD_SERVER_PUBLIC_KEY={pair.public_key}")
