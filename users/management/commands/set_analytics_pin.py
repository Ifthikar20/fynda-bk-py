"""
Management command to set or reset a staff user's analytics PIN.

Usage:
    python manage.py set_analytics_pin --email admin@outfi.ai --pin 123456
    python manage.py set_analytics_pin --email admin@outfi.ai  # prompts for PIN
"""

import hashlib
import getpass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


def _hash_pin(pin):
    """Hash a PIN using SHA-256 with a static salt."""
    return hashlib.sha256(f"outfi_analytics_{pin}".encode()).hexdigest()


class Command(BaseCommand):
    help = "Set or reset a staff user's analytics dashboard PIN."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            required=True,
            help="Email of the staff user to set the PIN for.",
        )
        parser.add_argument(
            "--pin",
            required=False,
            help="6-digit PIN. If not provided, you will be prompted.",
        )

    def handle(self, *args, **options):
        email = options["email"]
        pin = options.get("pin")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise CommandError(f"No user found with email: {email}")

        if not user.is_staff:
            raise CommandError(
                f"{email} is not a staff user. "
                f"Promote them first: user.is_staff = True"
            )

        if not pin:
            pin = getpass.getpass("Enter 6-digit analytics PIN: ")
            confirm = getpass.getpass("Confirm PIN: ")
            if pin != confirm:
                raise CommandError("PINs do not match.")

        # Validate PIN format
        pin = pin.strip()
        if not pin.isdigit() or len(pin) != 6:
            raise CommandError("PIN must be exactly 6 digits.")

        user.analytics_pin = _hash_pin(pin)
        user.save(update_fields=["analytics_pin"])

        self.stdout.write(
            self.style.SUCCESS(f"✅ Analytics PIN set for {user.email}")
        )
