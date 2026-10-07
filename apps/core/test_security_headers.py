"""What a browser is told about this site, checked against production settings.

These run with the settings a real deployment uses, not the development ones, because that is
the only configuration whose headers matter. A missing header here is not a style problem: it is
the difference between a stolen session cookie being usable and not.
"""

from django.test import Client, TestCase, override_settings
from django.urls import reverse

PRODUCTION = {
    "DEBUG": False,
    "ALLOWED_HOSTS": ["zencraftsolution.com"],
    "SECURE_SSL_REDIRECT": True,
    "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
    "SESSION_COOKIE_SECURE": True,
    "CSRF_COOKIE_SECURE": True,
    "SECURE_HSTS_SECONDS": 60 * 60 * 24 * 365,
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
    "SECURE_HSTS_PRELOAD": True,
}


@override_settings(**PRODUCTION)
class SecurityHeaderTests(TestCase):
    """Every header a deployment is supposed to send, on a real response."""

    def get(self, path="/legal/privacy/"):
        # Over https, because SECURE_SSL_REDIRECT would otherwise answer with a redirect.
        return Client(headers={"host": "zencraftsolution.com"}).get(path, secure=True)

    def test_strict_transport_security_is_a_year_and_covers_subdomains(self):
        header = self.get()["Strict-Transport-Security"]
        self.assertIn("max-age=31536000", header)
        self.assertIn("includeSubDomains", header)
        self.assertIn("preload", header)

    def test_the_page_cannot_be_framed(self):
        response = self.get()
        self.assertEqual(response["X-Frame-Options"], "DENY")
        policy = self.policy(response)
        self.assertEqual(policy["frame-ancestors"], ["'none'"])

    def test_content_type_is_never_guessed(self):
        self.assertEqual(self.get()["X-Content-Type-Options"], "nosniff")

    def test_the_referrer_is_trimmed_when_leaving_the_site(self):
        self.assertEqual(self.get()["Referrer-Policy"], "strict-origin-when-cross-origin")

    def test_hardware_access_is_refused(self):
        header = self.get()["Permissions-Policy"]
        for feature in ["camera=()", "microphone=()", "geolocation=()"]:
            self.assertIn(feature, header)

    def test_the_browsing_context_is_isolated(self):
        self.assertEqual(self.get()["Cross-Origin-Opener-Policy"], "same-origin")

    def policy(self, response):
        return {
            part.split(" ")[0]: part.split(" ")[1:]
            for part in (p.strip() for p in response["Content-Security-Policy"].split(";"))
            if part
        }

    def test_the_content_security_policy_is_sent_and_strict(self):
        policy = self.policy(self.get())
        self.assertEqual(policy["default-src"], ["'self'"])
        self.assertEqual(policy["object-src"], ["'none'"])
        self.assertEqual(policy["base-uri"], ["'self'"])
        self.assertNotIn("'unsafe-inline'", policy["script-src"])
        self.assertNotIn("'unsafe-eval'", policy["script-src"])
        self.assertIn("upgrade-insecure-requests", policy)
        # Nothing may load a stylesheet or font from somewhere else.
        self.assertEqual(policy["style-src"], ["'self'", "'unsafe-inline'"])
        self.assertEqual(policy["font-src"], ["'self'", "data:"])

    def test_plain_http_is_redirected_to_https(self):
        response = Client(headers={"host": "zencraftsolution.com"}).get("/legal/privacy/")
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].startswith("https://"))

    def test_the_dashboard_is_never_cached_or_indexed(self):
        from django.conf import settings

        response = Client(headers={"host": "zencraftsolution.com"}).get(
            f"/{settings.DASHBOARD_PATH}", secure=True, follow=True
        )
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(response["Cache-Control"], "no-store")


@override_settings(**PRODUCTION)
class CookieSecurityTests(TestCase):
    def test_the_session_cookie_is_secure_and_hidden_from_javascript(self):
        from django.conf import settings

        self.assertTrue(settings.SESSION_COOKIE_SECURE)
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)

    def test_the_csrf_cookie_is_secure(self):
        from django.conf import settings

        self.assertTrue(settings.CSRF_COOKIE_SECURE)
        # Not HttpOnly on purpose: the newsletter form reads it to post with fetch().
        self.assertFalse(settings.CSRF_COOKIE_HTTPONLY)

    def test_a_session_handed_out_in_production_carries_the_secure_flag(self):
        client = Client(headers={"host": "zencraftsolution.com"})
        client.get("/contact/", secure=True)  # any page that starts a session
        cookie = client.cookies.get("sessionid")
        if cookie is not None:  # only set once something goes into the session
            self.assertTrue(cookie["secure"])
            self.assertTrue(cookie["httponly"])


class DefaultPathsAreNotThereTests(TestCase):
    """The paths a scanner tries first should look like they do on a site that is not Django."""

    def test_the_usual_admin_paths_are_404(self):
        for path in ["/admin/", "/admin/login/", "/django-admin/", "/wp-admin/", "/wp-login.php",
                     "/.env", "/.git/config", "/phpmyadmin/"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404, path)

    def test_the_real_admin_is_only_under_the_secret_prefix(self):
        from django.conf import settings

        response = self.client.get(f"/{settings.DASHBOARD_PATH}django-admin/")
        self.assertIn(response.status_code, (301, 302))  # exists, and redirects to its login

    def test_the_dashboard_login_does_not_say_whether_a_username_exists(self):
        from apps.core.testing import make_staff

        staff = make_staff()
        url = reverse("dashboard:login")
        real = self.client.post(url, {"username": staff.get_username(), "password": "wrong-password"})
        fake = self.client.post(url, {"username": "nobody-at-all", "password": "wrong-password"})
        self.assertContains(real, "Please enter a correct username and password")
        self.assertContains(fake, "Please enter a correct username and password")
        self.assertEqual(real.status_code, fake.status_code)
