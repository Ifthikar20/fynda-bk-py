"""
Create a test user and verify login.

Usage:
    python manage.py create_test_user
    python manage.py create_test_user --email admin@outfi.ai --password MyPass123
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model, authenticate

User = get_user_model()

DEFAULT_EMAIL = "test@outfi.ai"
DEFAULT_PASSWORD = "Outfi2024!"
DEFAULT_FIRST = "Test"
DEFAULT_LAST = "User"


class Command(BaseCommand):
    help = "Create a test user and verify login works"

    def add_arguments(self, parser):
        parser.add_argument("--email", default=DEFAULT_EMAIL, help="Email address")
        parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Password")
        parser.add_argument("--first", default=DEFAULT_FIRST, help="First name")
        parser.add_argument("--last", default=DEFAULT_LAST, help="Last name")
        parser.add_argument("--superuser", action="store_true", help="Create as superuser (admin access)")

    def handle(self, *args, **options):
        email = options["email"]
        password = options["password"]
        first_name = options["first"]
        last_name = options["last"]
        is_super = options["superuser"]

        self.stdout.write("")

        # 1. Create user
        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f"  User '{email}' already exists — skipping creation."))
            user = User.objects.get(email=email)
            # Reset password so login test works
            user.set_password(password)
            user.save()
            self.stdout.write(f"  Password reset to the one provided.")
        else:
            if is_super:
                user = User.objects.create_superuser(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )
                self.stdout.write(self.style.SUCCESS(f"  ✓ Superuser created: {email}"))
            else:
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )
                self.stdout.write(self.style.SUCCESS(f"  ✓ User created: {email}"))

        # 2. Verify login
        auth_user = authenticate(email=email, password=password)
        if auth_user is not None:
            self.stdout.write(self.style.SUCCESS(f"  ✓ Login verified — authentication works!"))
        else:
            self.stdout.write(self.style.ERROR(f"  ✗ Login FAILED — check auth backend config."))

        # 3. Summary
        self.stdout.write("")
        self.stdout.write("  ─────────────────────────────────")
        self.stdout.write(f"  Email:    {email}")
        self.stdout.write(f"  Password: {password}")
        self.stdout.write(f"  Name:     {first_name} {last_name}")
        self.stdout.write(f"  Admin:    {'Yes' if user.is_staff else 'No'}")
        self.stdout.write("  ─────────────────────────────────")
        self.stdout.write("")
