"""One-shot, idempotent superuser bootstrap for automated deploys.

Render (and most PaaS platforms) give no clean way to run an interactive command
exactly once. Wiring Django's own `createsuperuser --noinput` straight into the
build command works on the very first deploy and then breaks every deploy after
it, since the username already exists and the command errors out and fails the
build.

This does the same job but exits quietly if the account already exists, so it is
safe to leave in the build command permanently - every deploy after the first is
a no-op.

Reads credentials from the same DJANGO_SUPERUSER_* environment variables
Django's built-in createsuperuser --noinput already respects.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the initial superuser from DJANGO_SUPERUSER_* env vars, unless it already exists."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

        if not username or not password:
            self.stdout.write(
                "DJANGO_SUPERUSER_USERNAME/PASSWORD not set - skipping superuser bootstrap."
            )
            return

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write("Superuser '%s' already exists - nothing to do." % username)
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS("Superuser '%s' created." % username))
