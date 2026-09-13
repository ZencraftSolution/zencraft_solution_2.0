import io
import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

ENV = {"DJANGO_SUPERUSER_USERNAME": "render-admin", "DJANGO_SUPERUSER_EMAIL": "ops@example.com", "DJANGO_SUPERUSER_PASSWORD": "a-strong-passphrase-2026"}


class EnsureSuperuserTests(TestCase):
    def run_command(self, env):
        out = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=False):
            for key in set(ENV) - set(env):
                os.environ.pop(key, None)
            call_command("ensure_superuser", stdout=out)
        return out.getvalue()

    def test_creates_superuser_once_and_is_idempotent(self):
        self.assertIn("created", self.run_command(ENV))
        user = get_user_model().objects.get(username="render-admin")
        self.assertTrue(user.is_superuser and user.is_staff)
        self.assertTrue(user.check_password(ENV["DJANGO_SUPERUSER_PASSWORD"]))
        output = self.run_command({**ENV, "DJANGO_SUPERUSER_PASSWORD": "a-different-passphrase-99"})
        self.assertIn("already exists", output)
        user.refresh_from_db()
        self.assertTrue(user.check_password(ENV["DJANGO_SUPERUSER_PASSWORD"]))  # never overwrites an existing password
        self.assertNotIn(ENV["DJANGO_SUPERUSER_PASSWORD"], output)

    def test_skips_quietly_without_credentials(self):
        self.assertIn("skipping", self.run_command({"DJANGO_SUPERUSER_USERNAME": "render-admin"}))
        self.assertFalse(get_user_model().objects.exists())
