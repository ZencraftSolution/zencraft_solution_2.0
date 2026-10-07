"""Cross-cutting tests: helpers, template tags, rate limiting, uploads and scanning, middleware, error pages,
sitemap/robots, the public core pages and the seed command. App-specific behaviour lives in each app's tests.py."""
import io
import json
import logging
import re
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.utils import OperationalError
from django.http import HttpResponse
from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.blog.models import BlogPost
from apps.careers.models import JobApplication, JobOpening
from apps.core import uploads
from apps.core.mail import send_templated_email, send_transactional_email
from apps.core.models import ConsultationBooking, ContactSubmission, Feedback, NewsletterSubscriber, PageView, ScannedUpload, SiteSettings
from apps.core.testing import CLAMAV_SCAN, NOOP_SCAN, docx_bytes, make_application, make_job, make_product, pdf_upload
from apps.core.uploads import get_private_storage
from apps.core.utils import client_ip, format_npr, format_usd, log_action, make_reference, npr_to_usd, rate_limit
from apps.services.models import Service


class FormattingTests(TestCase):
    def test_south_asian_grouping(self):
        self.assertEqual(format_npr(800000), "Rs. 8,00,000")
        self.assertEqual(format_npr(12345678), "Rs. 1,23,45,678")
        self.assertEqual(format_npr(Decimal("999.5")), "Rs. 1,000")
        self.assertEqual(format_npr(950), "Rs. 950")
        self.assertEqual(format_npr(-150000), "Rs. -1,50,000")
        self.assertEqual(format_npr(100000, with_symbol=False), "1,00,000")
        self.assertEqual((format_npr(None), format_npr("")), ("", ""))

    def test_usd_helpers_and_reference(self):
        self.assertEqual(npr_to_usd(134250, Decimal("134.25")), Decimal("1000"))
        self.assertIsNone(npr_to_usd(None, 134))
        self.assertIsNone(npr_to_usd(100, 0))
        self.assertEqual((format_usd(Decimal("1234")), format_usd(None)), ("$1,234", ""))
        self.assertRegex(make_reference("ZC"), r"^ZC-[0-9A-F]{6}$")


class TemplateTagTests(TestCase):
    def render(self, source, **ctx):
        return Template("{% load zc %}" + source).render(Context(ctx))

    def test_price_tags_render_both_currencies(self):
        html = self.render("{% price amount 'per month' %}", amount=Decimal("134250"), site=SiteSettings(exchange_rate_npr_per_usd=Decimal("134.25")))
        self.assertIn("Rs. 1,34,250", html)
        self.assertIn("$1,000", html)
        self.assertIn("per month", html)
        self.assertEqual(self.render("{% price amount %}", amount=None), "")
        ranged = self.render("{% price_range low high %}", low=100000, high=250000)
        self.assertIn("Rs. 1,00,000 to 2,50,000", ranged)
        self.assertIn("$", self.render("{% usd 134250 %}"))

    def test_filters(self):
        self.assertEqual(self.render("{{ v|npr }}", v=250000), "Rs. 2,50,000")
        self.assertEqual(self.render("{% for l in v|lines %}[{{ l }}]{% endfor %}", v="a\n\n b \n"), "[a][b]")
        self.assertEqual(self.render("{% for p in v|paragraphs %}[{{ p }}]{% endfor %}", v="one\n\ntwo"), "[one][two]")
        self.assertEqual(self.render("{{ d|get_item:'k' }}|{{ n|get_item:'k' }}", d={"k": "v"}, n=5), "v|None")
        self.assertEqual(self.render("{{ 3|pad2 }}|{{ 'x'|pad2 }}", ), "03|x")
        self.assertEqual(self.render("{% for _ in 3|star_range %}*{% endfor %}{% for _ in 'x'|star_range %}!{% endfor %}"), "***")

    def test_json_ld_escapes_script_breakout(self):
        html = self.render("{% json_ld data %}", data={"name": "</script><script>alert(1)</script>"})
        self.assertEqual(html.count("</script>"), 1)
        self.assertIn("<\\/script>", html)

    def test_network_svg_and_active(self):
        svg = self.render("{% network_svg seed=3 nodes=10 %}")
        self.assertEqual(svg.count("<circle"), 10)
        request = RequestFactory().get("/services/web/")
        self.assertEqual(self.render("{% active '/services/' %}|{% active '/work/' %}", request=request), "is-active|")


class RateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

        @rate_limit("unit-test", limit=2, window=60)
        def view(request):
            return HttpResponse("ok")

        self.view = view

    def test_blocks_after_limit_with_plain_and_json_responses(self):
        for _ in range(2):
            self.assertEqual(self.view(self.factory.post("/")).status_code, 200)
        blocked = self.view(self.factory.post("/"))
        self.assertEqual((blocked.status_code, blocked["Content-Type"].split(";")[0]), (429, "text/html"))
        as_json = self.view(self.factory.post("/", HTTP_X_REQUESTED_WITH="fetch"))
        self.assertEqual(as_json.status_code, 429)
        self.assertFalse(json.loads(as_json.content)["ok"])

    def test_get_and_other_ips_not_limited(self):
        for _ in range(3):
            self.view(self.factory.post("/"))
        self.assertEqual(self.view(self.factory.get("/")).status_code, 200)
        self.assertEqual(self.view(self.factory.post("/", REMOTE_ADDR="10.9.9.9")).status_code, 200)

    def test_expired_counter_recovers(self):
        self.view(self.factory.post("/"))
        with mock.patch.object(cache, "incr", side_effect=ValueError):
            self.assertEqual(self.view(self.factory.post("/")).status_code, 200)


class ClientIpTests(TestCase):
    def test_forwarded_header_ignored_unless_proxies_trusted(self):
        request = RequestFactory().get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="1.1.1.1, 2.2.2.2, 3.3.3.3")
        self.assertEqual(client_ip(request), "10.0.0.1")
        with override_settings(TRUSTED_PROXY_COUNT=1):
            self.assertEqual(client_ip(request), "3.3.3.3")
        with override_settings(TRUSTED_PROXY_COUNT=2):
            self.assertEqual(client_ip(request), "2.2.2.2")
        with override_settings(TRUSTED_PROXY_COUNT=5):
            self.assertEqual(client_ip(request), "10.0.0.1")

    def test_a_spoofed_header_cannot_change_the_address_we_key_on(self):
        """One proxy, as on Render: only the entry that proxy appended counts."""
        with override_settings(TRUSTED_PROXY_COUNT=1):
            for spoof in ["9.9.9.9", "9.9.9.9, 8.8.8.8", "not-an-ip", "", "::1"]:
                request = RequestFactory().get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR=f"{spoof}, 203.0.113.7")
                self.assertEqual(client_ip(request), "203.0.113.7", spoof)

    def test_junk_in_the_trusted_position_falls_back_to_the_socket_address(self):
        with override_settings(TRUSTED_PROXY_COUNT=1):
            request = RequestFactory().get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="203.0.113.7, unknown")
            self.assertEqual(client_ip(request), "10.0.0.1")

    def test_ports_and_ipv6_are_normalised(self):
        with override_settings(TRUSTED_PROXY_COUNT=1):
            cases = {
                "203.0.113.7:51324": "203.0.113.7",
                "[2001:db8::1]:443": "2001:db8::1",
                "2001:db8::1": "2001:db8::1",
            }
            for raw, expected in cases.items():
                request = RequestFactory().get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR=raw)
                self.assertEqual(client_ip(request), expected, raw)

    def test_rate_limiting_is_per_visitor_behind_one_proxy(self):
        cache.clear()
        with override_settings(TRUSTED_PROXY_COUNT=1):
            first = self.client.post("/contact/", {}, HTTP_X_FORWARDED_FOR="203.0.113.7")
            self.assertNotEqual(first.status_code, 429)
            # A different visitor through the same proxy must not inherit the first one's count.
            for _ in range(8):
                self.client.post("/contact/", {}, HTTP_X_FORWARDED_FOR="203.0.113.7")
            blocked = self.client.post("/contact/", {}, HTTP_X_FORWARDED_FOR="203.0.113.7")
            other = self.client.post("/contact/", {}, HTTP_X_FORWARDED_FOR="198.51.100.4")
            self.assertEqual(blocked.status_code, 429)
            self.assertNotEqual(other.status_code, 429)

    def test_log_action_for_anonymous_request(self):
        request = RequestFactory().post("/somewhere/")
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()
        log_action(request, "test action", None, detail="x")
        from apps.core.models import AuditLog

        entry = AuditLog.objects.get()
        self.assertEqual((entry.user, entry.path, entry.object_repr), (None, "/somewhere/", ""))


class UploadValidationTests(TestCase):
    def test_sniffing(self):
        self.assertEqual(uploads.sniff_document_type(pdf_upload()), "pdf")
        self.assertEqual(uploads.sniff_document_type(SimpleUploadedFile("a.docx", docx_bytes())), "docx")
        self.assertIsNone(uploads.sniff_document_type(SimpleUploadedFile("a.docx", docx_bytes(valid=False))))
        self.assertIsNone(uploads.sniff_document_type(SimpleUploadedFile("a.docx", b"PK\x03\x04 broken zip")))
        self.assertIsNone(uploads.sniff_document_type(SimpleUploadedFile("a.pdf", b"GIF89a")))

    @override_settings(UPLOAD_SCAN_HOOK=NOOP_SCAN)
    def test_validate_document_rules(self):
        self.assertEqual(uploads.validate_document(pdf_upload()), "pdf")
        with self.assertRaisesMessage(ValidationError, "PDF or DOCX"):
            uploads.validate_document(pdf_upload(name="cv.exe"))
        with self.assertRaisesMessage(ValidationError, "too large"):
            uploads.validate_document(pdf_upload(), max_bytes=10)
        with self.assertRaisesMessage(ValidationError, "does not look like"):
            uploads.validate_document(SimpleUploadedFile("cv.pdf", docx_bytes()))

    def test_private_storage_has_no_public_url_and_random_names(self):
        with self.assertRaises(ValueError):
            uploads.get_private_storage().url("cvs/x.pdf")
        name = uploads.RandomisedPath("cvs")(None, "My CV (final).PDF")
        self.assertRegex(name, r"^cvs/[0-9a-f]{32}\.pdf$")
        self.assertTrue(uploads.noop_scan(pdf_upload()))


@override_settings(UPLOAD_SCAN_HOOK=CLAMAV_SCAN, CLAMAV_UNIX_SOCKET="", CLAMAV_HOST="clamav.test", CLAMAV_PORT=3310)
class ClamAVScanTests(TestCase):
    def fake_client(self, response=None, error=None):
        client = mock.Mock()
        if error is not None:
            client.instream.side_effect = error
        else:
            client.instream.return_value = response
        return mock.patch("apps.core.uploads._clamd_client", return_value=client), client

    def test_clean_file_is_accepted_and_stream_rewound(self):
        patcher, client = self.fake_client({"stream": ("OK", None)})
        f = pdf_upload()
        with patcher:
            self.assertEqual(uploads.validate_document(f), "pdf")
        client.instream.assert_called_once()
        self.assertEqual(f.tell(), 0)

    def test_infected_file_is_rejected(self):
        patcher, _ = self.fake_client({"stream": ("FOUND", "Eicar-Test-Signature")})
        with patcher, self.assertRaisesMessage(ValidationError, "security scan"):
            uploads.validate_document(pdf_upload())

    def test_unreachable_daemon_fails_closed(self):
        import clamd

        patcher, _ = self.fake_client(error=clamd.ConnectionError("Connection refused"))
        with patcher, self.assertLogs("apps.core.uploads", "ERROR"), self.assertRaisesMessage(ValidationError, "could not scan"):
            uploads.validate_document(pdf_upload())

    def test_daemon_error_or_empty_response_fails_closed(self):
        for response in ({"stream": ("ERROR", "INSTREAM size limit exceeded")}, None):
            patcher, _ = self.fake_client(response)
            with self.subTest(response=response), patcher, self.assertLogs("apps.core.uploads", "ERROR"), self.assertRaises(ValidationError):
                uploads.clamav_scan(pdf_upload())

    def test_client_uses_network_or_unix_socket_from_settings(self):
        import clamd

        client = uploads._clamd_client()
        self.assertIsInstance(client, clamd.ClamdNetworkSocket)
        self.assertEqual((client.host, client.port), ("clamav.test", 3310))
        with override_settings(CLAMAV_UNIX_SOCKET="/run/clamav/clamd.ctl"):
            self.assertIsInstance(uploads._clamd_client(), clamd.ClamdUnixSocket)

    def test_noop_scanner_refused_when_debug_is_false(self):
        import os
        import subprocess
        import sys

        from django.conf import settings

        env = {**os.environ, "DEBUG": "False", "UPLOAD_SCAN_HOOK": NOOP_SCAN, "SECRET_KEY": "x" * 60}
        result = subprocess.run([sys.executable, "-c", "import config.settings"], cwd=settings.BASE_DIR, env=env,
                                capture_output=True, text=True, timeout=180)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("only allowed when DEBUG=True", result.stderr)


class MiddlewareAndContextTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_page_views_recorded_for_public_html_only(self):
        self.client.get("/legal/privacy/")
        self.client.get("/robots.txt")
        self.client.get("/does-not-exist/")
        self.client.get(reverse("dashboard:login"))
        self.client.get(reverse("estimator:config_api"))
        self.assertEqual(list(PageView.objects.values_list("path", flat=True)), ["/legal/privacy/"])

    def test_security_headers(self):
        public = self.client.get("/legal/terms/")
        self.assertIn("camera=()", public["Permissions-Policy"])
        self.assertEqual(public["X-Content-Type-Options"], "nosniff")
        self.assertNotIn("X-Robots-Tag", public)
        dash = self.client.get(reverse("dashboard:login"))
        self.assertEqual((dash["X-Robots-Tag"], dash["Cache-Control"]), ("noindex, nofollow", "no-store"))

    @override_settings(STORE_ENABLED=True)
    def test_cart_count_and_site_settings_cache(self):
        product = make_product()
        self.client.post(reverse("commerce:cart_add", args=[product.pk]), {"quantity": 3})
        self.assertEqual(self.client.get("/legal/cookies/").context["cart_count"], 3)
        site = SiteSettings.load()
        self.assertIsNotNone(cache.get(SiteSettings.CACHE_KEY))  # load() populates the cache
        site.phone = "+977 9811111111"
        site.save()
        self.assertEqual(SiteSettings.load().phone, "+977 9811111111")
        self.assertEqual(site.pk, 1)


class FooterSocialLinkTests(TestCase):
    """The footer shows a brand logo for each network that has a link, and nothing for the rest."""

    def setUp(self):
        cache.clear()  # site settings are cached, and that cache outlives the test transaction

    def test_configured_profiles_are_linked_and_empty_ones_are_skipped(self):
        page = self.client.get("/legal/privacy/").content.decode()
        for url in ["https://www.facebook.com/share/1GpaRpTZJy/", "https://www.instagram.com/zencraftsolution",
                    "https://www.tiktok.com/@zencraft.solution",
                    "https://www.linkedin.com/in/zencraft-solution-pvt-ltd-93ab8143b"]:
            self.assertIn(url, page)
        for logo in ["facebook.svg", "instagram-icon.svg", "tiktok-icon.svg", "linkedin-icon.svg"]:
            self.assertIn(logo, page)
        self.assertEqual(page.count('class="social"'), 4)  # GitHub and X have no account yet
        self.assertNotIn("github-icon.svg", page)

    def test_clearing_a_link_removes_its_logo(self):
        site = SiteSettings.load()
        site.tiktok_url = ""
        site.save()
        page = self.client.get("/legal/privacy/").content.decode()
        self.assertNotIn("tiktok-icon.svg", page)
        self.assertEqual(page.count('class="social"'), 3)


class OpenRedirectTests(TestCase):
    """A form that returns the visitor to the Referer must not return them off-site."""

    def setUp(self):
        cache.clear()

    def test_newsletter_returns_to_our_own_page(self):
        response = self.client.post(reverse("core:newsletter"), {"email": "reader@example.com"}, HTTP_REFERER="/about/")
        self.assertEqual(response["Location"], "/about/")

    def test_an_external_referer_is_ignored(self):
        for hostile in ["https://evil.example/phish", "//evil.example/phish", "http://testserver.evil.example/"]:
            response = self.client.post(
                reverse("core:newsletter"), {"email": f"r{len(hostile)}@example.com"}, HTTP_REFERER=hostile
            )
            self.assertEqual(response["Location"], reverse("core:home"), hostile)

    def test_safe_referer_helper(self):
        from apps.core.utils import safe_referer

        request = RequestFactory().post("/newsletter/", HTTP_REFERER="https://evil.example/")
        self.assertEqual(safe_referer(request, "/fallback/"), "/fallback/")
        request = RequestFactory().post("/newsletter/", HTTP_REFERER="/work/")
        self.assertEqual(safe_referer(request, "/fallback/"), "/work/")
        self.assertEqual(safe_referer(RequestFactory().post("/newsletter/"), "/fallback/"), "/fallback/")


class ContentSecurityPolicyTests(TestCase):
    """Scripts are allow-listed by nonce, so injected markup cannot execute."""

    def directives(self, response, header="Content-Security-Policy"):
        return {
            part.split(" ")[0]: part.split(" ")[1:]
            for part in (p.strip() for p in response[header].split(";"))
            if part
        }

    def test_policy_is_sent_on_public_and_dashboard_pages(self):
        for url in ["/", "/legal/privacy/", reverse("dashboard:login")]:
            response = self.client.get(url)
            self.assertIn("Content-Security-Policy", response, url)
            directives = self.directives(response)
            self.assertEqual(directives["object-src"], ["'none'"])
            self.assertEqual(directives["frame-ancestors"], ["'none'"])
            self.assertEqual(directives["base-uri"], ["'self'"])
            self.assertEqual(directives["default-src"], ["'self'"])

    def test_scripts_need_a_nonce_rather_than_unsafe_inline(self):
        response = self.client.get("/")
        script_src = self.directives(response)["script-src"]
        self.assertNotIn("'unsafe-inline'", script_src)
        self.assertNotIn("'unsafe-eval'", script_src)
        self.assertEqual(len([s for s in script_src if s.startswith("'nonce-")]), 1)

    def test_the_nonce_in_the_header_is_the_one_the_page_uses(self):
        response = self.client.get("/")
        nonce = next(s for s in self.directives(response)["script-src"] if s.startswith("'nonce-"))[7:-1]
        html = response.content.decode()
        self.assertIn(f'nonce="{nonce}"', html)
        # Every executable inline script carries it; JSON data blocks are not executed.
        executable = re.findall(r"<script(?![^>]*(?:src=|type=\"application/json\"))[^>]*>", html)
        self.assertTrue(executable)
        for tag in executable:
            self.assertIn(f'nonce="{nonce}"', tag)

    def test_a_fresh_nonce_per_request(self):
        first = self.directives(self.client.get("/"))["script-src"]
        second = self.directives(self.client.get("/"))["script-src"]
        self.assertNotEqual(first, second)

    def test_payment_redirect_hosts_are_the_only_extra_form_targets(self):
        form_action = self.directives(self.client.get("/"))["form-action"]
        self.assertEqual(form_action[0], "'self'")
        self.assertIn("https://epay.esewa.com.np", form_action)
        self.assertNotIn("*", form_action)

    @override_settings(CSP_REPORT_ONLY=True)
    def test_report_only_mode_can_be_switched_on_for_a_safe_rollout(self):
        # The middleware reads the flag when it is built, so rebuild it the way Django would.
        from apps.core.middleware import ContentSecurityPolicyMiddleware

        middleware = ContentSecurityPolicyMiddleware(lambda request: HttpResponse("ok"))
        response = middleware(RequestFactory().get("/"))
        self.assertIn("Content-Security-Policy-Report-Only", response)
        self.assertNotIn("Content-Security-Policy", response)

    @override_settings(CSP_REPORT_URI="https://example.report/csp")
    def test_a_report_endpoint_is_appended_when_configured(self):
        from apps.core.middleware import ContentSecurityPolicyMiddleware

        middleware = ContentSecurityPolicyMiddleware(lambda request: HttpResponse("ok"))
        response = middleware(RequestFactory().get("/"))
        self.assertTrue(response["Content-Security-Policy"].endswith("report-uri https://example.report/csp"))


class SettingsHelperTests(TestCase):
    """The two settings helpers that would silently misconfigure the site if they drifted."""

    def test_dashboard_path_is_normalised_however_it_is_written(self):
        from config.settings import normalise_url_prefix

        for raw in ["zen", "zen/", "/zen/", "  /zen  ", "//zen//"]:
            self.assertEqual(normalise_url_prefix(raw), "zen/", raw)
        self.assertEqual(normalise_url_prefix("hq/admin"), "hq/admin/")
        for empty in ["", "   ", "/", None]:
            with self.assertRaises(ImproperlyConfigured):
                normalise_url_prefix(empty)

    def test_the_running_dashboard_path_has_that_shape(self):
        self.assertFalse(settings.DASHBOARD_PATH.startswith("/"))
        self.assertTrue(settings.DASHBOARD_PATH.endswith("/"))
        self.assertEqual(self.client.get(f"/{settings.DASHBOARD_PATH}").status_code, 302)  # to the login page

    def test_production_never_falls_back_to_a_per_worker_cache(self):
        from config.settings import cache_config

        self.assertEqual(cache_config("", debug=True)["BACKEND"], "django.core.cache.backends.locmem.LocMemCache")
        # Lockout counters have to be shared between gunicorn workers and survive a restart.
        self.assertEqual(cache_config("", debug=False)["BACKEND"], "django.core.cache.backends.db.DatabaseCache")
        for url in ["redis://127.0.0.1:6379/1", "rediss://cache.example.com:6380/0"]:
            config = cache_config(url, debug=False)
            self.assertEqual(config["BACKEND"], "django.core.cache.backends.redis.RedisCache")
            self.assertEqual(config["LOCATION"], url)


class ErrorPageTests(TestCase):
    def test_404_terminal_page(self):
        response = self.client.get("/definitely/missing/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "HTTP/1.1 404 Not Found", status_code=404)

    def test_500_handler_is_standalone(self):
        from apps.core.views import page_not_found, server_error

        request = RequestFactory().get("/boom/")
        response = server_error(request)
        self.assertEqual(response.status_code, 500)
        self.assertIn(b"Something went wrong on our side", response.content)
        self.assertEqual(page_not_found(RequestFactory().get("/x/"), Exception()).status_code, 404)


class SitemapRobotsTests(TestCase):
    def test_robots_never_names_the_dashboard_path(self):
        body = self.client.get("/robots.txt").content.decode()
        self.assertNotIn(settings.DASHBOARD_PATH, body)  # robots.txt is public; the path is a secret
        self.assertNotIn("hq", body)
        self.assertIn("Disallow: /search/", body)
        self.assertIn(f"Sitemap: {settings.SITE_URL.rstrip('/')}/sitemap.xml", body)

    def test_the_dashboard_is_kept_out_of_search_by_its_header_instead(self):
        response = self.client.get(reverse("dashboard:login"))
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_sitemap_lists_public_content_only(self):
        from apps.services.models import ServiceCategory

        category = ServiceCategory.objects.create(name="S", slug="s")
        Service.objects.create(category=category, name="Live", slug="live-service", nav_blurb="x", outcome_headline="x", summary="x",
                               intro="x", hero_image_url="https://example.com/x.jpg")
        Service.objects.create(category=category, name="Hidden", slug="hidden-service", nav_blurb="x", outcome_headline="x", summary="x",
                               intro="x", hero_image_url="https://example.com/x.jpg", is_published=False)
        make_job(slug="open-job")
        make_job(slug="closed-job", closing_date=timezone.localdate() - timedelta(days=2))
        xml = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("/services/live-service/", xml)
        self.assertIn("/careers/jobs/open-job/", xml)
        self.assertNotIn("hidden-service", xml)
        self.assertNotIn("closed-job", xml)
        self.assertNotIn("/hq/", xml)


class PublicCoreFormTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_contact_form_success_and_honeypot(self):
        data = {"name": "Sita Sharma", "email": "sita@example.com", "subject": "Hello", "message": "We need an app.", "consent": "on"}
        self.assertRedirects(self.client.post(reverse("core:contact"), data), reverse("core:contact"))
        self.assertEqual(ContactSubmission.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 2)
        response = self.client.post(reverse("core:contact"), {**data, "website": "http://spam"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactSubmission.objects.count(), 1)

    def test_contact_is_rate_limited(self):
        for _ in range(5):
            self.client.post(reverse("core:contact"), {"name": ""})
        self.assertEqual(self.client.post(reverse("core:contact"), {"name": ""}).status_code, 429)

    def test_consultation_booking_rules(self):
        url = reverse("core:consultation") + "?topic=data"
        self.assertEqual(self.client.get(url).context["form"].initial["topic"], "data")
        base = {"name": "Hari", "email": "hari@example.com", "topic": "new-project", "preferred_slot": "morning", "consent": "on"}
        past = self.client.post(url, {**base, "preferred_date": (timezone.localdate() - timedelta(days=1)).isoformat()})
        self.assertContains(past, "today or a future date")
        today = timezone.localdate()
        saturday = today + timedelta(days=(5 - today.weekday()) % 7 or 7)
        self.assertContains(self.client.post(url, {**base, "preferred_date": saturday.isoformat()}), "closed on Saturdays")
        weekday = saturday + timedelta(days=2)
        ok = self.client.post(url, {**base, "preferred_date": weekday.isoformat()})
        self.assertContains(ok, "Talk soon")
        self.assertEqual(ConsultationBooking.objects.get().preferred_date, weekday)

    def test_newsletter_json_and_form_posts(self):
        url = reverse("core:newsletter")
        ok = self.client.post(url, {"email": "Reader@Example.com"}, HTTP_X_REQUESTED_WITH="fetch")
        self.assertTrue(ok.json()["ok"])
        again = self.client.post(url, {"email": "reader@example.com"}, HTTP_REFERER="/about/")
        self.assertRedirects(again, "/about/", fetch_redirect_response=False)
        self.assertEqual(NewsletterSubscriber.objects.count(), 1)
        bad = self.client.post(url, {"email": "nope"}, HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(bad.status_code, 400)
        self.assertRedirects(self.client.post(url, {"email": "nope"}), reverse("core:home"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(url).status_code, 405)


@override_settings(UPLOAD_SCAN_MODE="quarantine")
class QuarantineModeTests(TestCase):
    """The mode for hosts where the web process cannot reach a virus scanner."""

    def setUp(self):
        self.job = make_job()

    def test_an_upload_is_accepted_without_a_scanner_being_present(self):
        """validate_document must not call the hook at all, or the whole point is lost."""
        with mock.patch("apps.core.uploads.import_string") as import_string:
            uploads.validate_document(pdf_upload())
        import_string.assert_not_called()

    def test_a_stored_file_is_recorded_as_waiting(self):
        application = make_application(self.job, cv=pdf_upload(), cv_original_name="cv.pdf")
        record = uploads.quarantine(application.cv)
        self.assertEqual((record.path, record.status), (application.cv.name, "pending"))
        self.assertFalse(uploads.upload_is_servable(application.cv.name))

    def test_registering_the_same_file_twice_does_not_reset_a_verdict(self):
        application = make_application(self.job, cv=pdf_upload())
        first = uploads.quarantine(application.cv)
        ScannedUpload.objects.filter(pk=first.pk).update(status="clean")
        again = uploads.quarantine(application.cv)
        self.assertEqual(again.pk, first.pk)
        self.assertEqual(again.status, "clean")

    def test_a_file_becomes_servable_only_once_it_is_clean(self):
        record = ScannedUpload.objects.create(path="cvs/abc.pdf", status="pending")
        self.assertFalse(uploads.upload_is_servable("cvs/abc.pdf"))
        for blocked in ["infected", "error"]:
            ScannedUpload.objects.filter(pk=record.pk).update(status=blocked)
            self.assertFalse(uploads.upload_is_servable("cvs/abc.pdf"), blocked)
        ScannedUpload.objects.filter(pk=record.pk).update(status="clean")
        self.assertTrue(uploads.upload_is_servable("cvs/abc.pdf"))

    @override_settings(UPLOAD_SCAN_MODE="strict")
    def test_switching_back_to_strict_does_not_release_what_was_never_scanned(self):
        ScannedUpload.objects.create(path="cvs/old.pdf", status="pending")
        self.assertFalse(uploads.upload_is_servable("cvs/old.pdf"))
        # A file with no record was scanned during its own upload, so it is fine.
        self.assertTrue(uploads.upload_is_servable("cvs/scanned-at-upload.pdf"))

    def test_nothing_is_recorded_in_the_other_modes(self):
        application = make_application(self.job, cv=pdf_upload())
        with override_settings(UPLOAD_SCAN_MODE="strict"):
            self.assertIsNone(uploads.quarantine(application.cv))
        self.assertFalse(ScannedUpload.objects.exists())


@override_settings(UPLOAD_SCAN_MODE="quarantine")
class ScanQuarantinedUploadsCommandTests(TestCase):
    def setUp(self):
        self.job = make_job()
        self.application = make_application(self.job, cv=pdf_upload(), cv_original_name="cv.pdf")
        self.record = uploads.quarantine(self.application.cv)

    def tearDown(self):
        for app in JobApplication.objects.exclude(cv=""):
            app.cv.delete(save=False)

    def run_command(self, scan_result=True, **options):
        with mock.patch("apps.core.uploads.clamav_scan", return_value=scan_result):
            out = io.StringIO()
            call_command("scan_quarantined_uploads", stdout=out, stderr=io.StringIO(), **options)
        if ScannedUpload.objects.filter(pk=self.record.pk).exists():
            self.record.refresh_from_db()
        return out.getvalue()

    def test_a_clean_file_is_released_to_staff(self):
        output = self.run_command(scan_result=True)
        self.assertEqual(self.record.status, "clean")
        self.assertIsNotNone(self.record.scanned_at)
        self.assertEqual(self.record.attempts, 1)
        self.assertIn("1 clean", output)
        self.assertTrue(uploads.upload_is_servable(self.application.cv.name))

    def test_an_infected_file_stays_blocked(self):
        self.run_command(scan_result=False)
        self.assertEqual(self.record.status, "infected")
        self.assertFalse(uploads.upload_is_servable(self.application.cv.name))

    def test_a_scanner_that_is_down_leaves_the_file_held_and_retryable(self):
        with mock.patch("apps.core.uploads.clamav_scan", side_effect=uploads.ScannerUnavailable("down")):
            call_command("scan_quarantined_uploads", stdout=io.StringIO(), stderr=io.StringIO())
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, "error")
        self.assertFalse(uploads.upload_is_servable(self.application.cv.name))
        self.run_command(scan_result=True, retry_errors=True)
        self.assertEqual(self.record.status, "clean")

    def test_a_file_deleted_before_the_scan_is_not_left_pending_forever(self):
        self.application.cv.delete(save=False)
        self.run_command()
        self.assertEqual(self.record.status, "error")
        self.assertIn("no longer in storage", self.record.signature)

    def test_dry_run_changes_nothing(self):
        output = self.run_command(dry_run=True)
        self.assertIn("would scan", output)
        self.assertEqual(self.record.status, "pending")

    def test_an_empty_queue_is_not_an_error(self):
        ScannedUpload.objects.all().delete()
        self.assertIn("Nothing waiting", self.run_command())


class PrivateStorageSelectionTests(TestCase):
    def setUp(self):
        uploads._private_storage_cache.clear()

    def tearDown(self):
        uploads._private_storage_cache.clear()

    def test_local_disk_is_the_default_and_has_no_public_url(self):
        with override_settings(PRIVATE_STORAGE_BACKEND="local"):
            storage = uploads.get_private_storage()
        self.assertIsInstance(storage, uploads.PrivateStorage)
        with self.assertRaises(ValueError):
            storage.url("cvs/x.pdf")

    def test_s3_is_built_private_with_short_lived_signed_urls(self):
        config = {
            "bucket_name": "zencraft-private", "region_name": "auto", "endpoint_url": "https://example.r2.test",
            "access_key": "key", "secret_key": "secret", "location": "private", "querystring_expire": 300,
        }
        with override_settings(PRIVATE_STORAGE_BACKEND="s3", PRIVATE_S3=config):
            storage = uploads.get_private_storage()
        self.assertEqual(storage.bucket_name, "zencraft-private")
        self.assertEqual(storage.default_acl, "private")
        self.assertTrue(storage.querystring_auth)  # a URL without a signature must not work
        self.assertEqual(storage.querystring_expire, 300)
        self.assertFalse(storage.file_overwrite)  # two CVs must never collide

    def test_a_half_configured_bucket_fails_loudly_instead_of_losing_files(self):
        config = {"bucket_name": "", "region_name": "", "endpoint_url": None, "access_key": "",
                  "secret_key": "", "location": "private", "querystring_expire": 300}
        with override_settings(PRIVATE_STORAGE_BACKEND="s3", PRIVATE_S3=config):
            with self.assertRaises(ImproperlyConfigured) as caught:
                uploads.get_private_storage()
        self.assertIn("bucket_name", str(caught.exception))

    def test_an_unknown_backend_is_refused(self):
        with override_settings(PRIVATE_STORAGE_BACKEND="dropbox"):
            with self.assertRaises(ImproperlyConfigured):
                uploads.get_private_storage()

    def test_the_migration_command_refuses_to_run_against_local_storage(self):
        with override_settings(PRIVATE_STORAGE_BACKEND="local"):
            with self.assertRaises(CommandError) as caught:
                call_command("migrate_private_files", stdout=io.StringIO())
        self.assertIn("nowhere to copy to", str(caught.exception))


class TransactionalEmailTests(TestCase):
    """A mail server that is down must not break the visitor's request, but must not go unnoticed."""

    def setUp(self):
        mail.outbox.clear()

    def test_a_message_goes_out_with_the_configured_sender(self):
        self.assertTrue(send_transactional_email("Subject", "Body", "person@example.com", reference="ZA-1"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["person@example.com"])
        self.assertEqual(mail.outbox[0].from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(mail.outbox[0].body, "Body")

    def test_a_failure_is_logged_with_the_reference_and_does_not_raise(self):
        with mock.patch("apps.core.mail.EmailMultiAlternatives.send", side_effect=OSError("connection refused")):
            with self.assertLogs("apps.core.mail", level="ERROR") as logs:
                sent = send_transactional_email("Your order ZO-77", "Body", "buyer@example.com", reference="ZO-77")
        self.assertFalse(sent)
        self.assertIn("ZO-77", logs.output[0])
        self.assertIn("buyer@example.com", logs.output[0])
        self.assertIn("connection refused", logs.output[0])

    def test_a_backend_that_sends_nothing_is_treated_as_a_failure(self):
        with mock.patch("apps.core.mail.EmailMultiAlternatives.send", return_value=0):
            with self.assertLogs("apps.core.mail", level="ERROR"):
                self.assertFalse(send_transactional_email("Subject", "Body", "a@example.com"))

    def test_a_missing_address_is_reported_rather_than_crashing(self):
        with self.assertLogs("apps.core.mail", level="WARNING"):
            self.assertFalse(send_transactional_email("Subject", "Body", ""))
        self.assertEqual(len(mail.outbox), 0)

    def test_a_plain_text_body_is_the_message_itself(self):
        """Text-only clients must get the real content, not "please view in a browser"."""
        send_templated_email("Hi", "emails/contact_ack.txt", {"submission": ContactSubmission(name="Asmita")}, "a@example.com")
        self.assertEqual(mail.outbox[0].content_subtype, "plain")
        self.assertEqual(mail.outbox[0].alternatives, [])
        self.assertIn("Asmita", mail.outbox[0].body)


def next_working_day(after_days=3):
    """A bookable date. The consultation form refuses Saturdays, so never offer one."""
    date = timezone.localdate() + timedelta(days=after_days)
    return date + timedelta(days=1) if date.weekday() == 5 else date


class EmailFailureDoesNotBreakTheSiteTests(TestCase):
    """Every public form keeps working when the mail server is unreachable."""

    def setUp(self):
        cache.clear()
        mail.outbox.clear()

    def broken_mail(self):
        return mock.patch("apps.core.mail.EmailMultiAlternatives.send", side_effect=OSError("mail server down"))

    def test_the_contact_form_still_saves_and_thanks_the_visitor(self):
        data = {"name": "Asmita", "email": "a@example.com", "phone": "98", "company": "C",
                "subject": "Hello", "message": "A message long enough to pass validation.", "consent": "on"}
        with self.broken_mail(), self.assertLogs("apps.core.mail", level="ERROR"):
            response = self.client.post(reverse("core:contact"), data, follow=True)
        self.assertContains(response, "Thanks. Your message is with our team")
        self.assertTrue(ContactSubmission.objects.filter(email="a@example.com").exists())

    def test_a_consultation_request_is_still_recorded(self):
        data = {"name": "Asmita", "email": "a@example.com", "phone": "9800000000", "company": "C",
                "topic": "new-project", "preferred_date": next_working_day().isoformat(),
                "preferred_slot": "morning", "message": "Hello", "consent": "on"}
        with self.broken_mail(), self.assertLogs("apps.core.mail", level="ERROR"):
            response = self.client.post(reverse("core:consultation"), data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ConsultationBooking.objects.filter(email="a@example.com").exists())


class MigratePrivateFilesTests(TestCase):
    """Moving CVs off the container disk, which is the step that keeps them after a redeploy."""

    def setUp(self):
        self.target_dir = tempfile.mkdtemp(prefix="zc-target-")
        self.target = FileSystemStorage(location=self.target_dir)
        self.job = make_job()
        self.application = make_application(self.job, cv=pdf_upload(), cv_original_name="cv.pdf")

    def tearDown(self):
        for app in JobApplication.objects.exclude(cv=""):
            app.cv.delete(save=False)
        shutil.rmtree(self.target_dir, ignore_errors=True)

    def run_command(self, *args, **options):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("apps.core.management.commands.migrate_private_files.get_private_storage", return_value=self.target):
            call_command("migrate_private_files", *args, stdout=out, stderr=err, **options)
        return out.getvalue() + err.getvalue()

    def test_a_dry_run_reports_without_copying(self):
        output = self.run_command("--dry-run")
        self.assertIn("would copy", output)
        self.assertIn("Would copy 1 file", output)
        self.assertFalse(self.target.exists(self.application.cv.name))

    def test_the_file_is_copied_byte_for_byte(self):
        name = self.application.cv.name
        output = self.run_command()
        self.assertIn("Copied 1 file", output)
        self.assertTrue(self.target.exists(name))
        with self.target.open(name, "rb") as copied, get_private_storage().open(name, "rb") as original:
            self.assertEqual(copied.read(), original.read())

    def test_running_it_twice_does_not_copy_again(self):
        self.run_command()
        self.assertIn("skipped 1 already there", self.run_command())

    def test_verify_passes_once_everything_is_across(self):
        self.run_command()
        self.assertIn("Every private file is present", self.run_command("--verify"))

    def test_verify_fails_loudly_when_a_file_did_not_make_it(self):
        with self.assertRaises(CommandError) as caught:
            self.run_command("--verify")
        self.assertIn("not copied correctly", str(caught.exception))

    def test_a_row_pointing_at_a_file_that_is_gone_is_reported_not_skipped_silently(self):
        get_private_storage().delete(self.application.cv.name)
        output = self.run_command()
        self.assertIn("missing locally", output)
        self.assertIn("1 missing", output)


class SentryInitTests(TestCase):
    def test_it_starts_with_personal_data_switched_off(self):
        fake_sdk = mock.MagicMock()
        modules = {
            "sentry_sdk": fake_sdk,
            "sentry_sdk.integrations.django": mock.MagicMock(DjangoIntegration=mock.MagicMock()),
        }
        with mock.patch.dict("sys.modules", modules):
            from apps.core.observability import init_sentry, scrub

            self.assertTrue(init_sentry("https://key@sentry.test/1", "production", "v1", 0.25))
        kwargs = fake_sdk.init.call_args.kwargs
        self.assertEqual(kwargs["dsn"], "https://key@sentry.test/1")
        self.assertEqual(kwargs["environment"], "production")
        self.assertEqual(kwargs["release"], "v1")
        self.assertEqual(kwargs["traces_sample_rate"], 0.25)
        self.assertFalse(kwargs["send_default_pii"])
        self.assertIs(kwargs["before_send"], scrub)

    def test_a_missing_package_is_a_warning_rather_than_a_crash_on_boot(self):
        from apps.core.observability import init_sentry

        with mock.patch.dict("sys.modules", {"sentry_sdk": None}):
            with self.assertLogs("apps.core.observability", level="WARNING"):
                self.assertFalse(init_sentry("https://key@sentry.test/1", "production"))

    def test_an_event_without_a_request_is_left_alone(self):
        from apps.core.observability import scrub

        self.assertEqual(scrub({"message": "boom"}), {"message": "boom"})


class HealthCheckTests(TestCase):
    URL = "/healthz/"

    def test_reports_ok_when_the_database_and_cache_answer(self):
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "checks": {"database": "ok", "cache": "ok"}})
        self.assertIn("no-cache", response["Cache-Control"])

    def test_a_broken_cache_makes_it_fail_rather_than_quietly_pass(self):
        with mock.patch("apps.core.health.cache.get", return_value=None):
            response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["checks"], {"database": "ok", "cache": "error"})

    def test_a_broken_database_is_named_in_the_response(self):
        with mock.patch("apps.core.health.connection.cursor", side_effect=OperationalError("down")):
            response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["checks"]["database"], "error")

    def test_the_probe_is_not_counted_as_a_page_view(self):
        self.client.get(self.URL)
        self.assertFalse(PageView.objects.filter(path__startswith="/healthz").exists())

    def test_it_is_not_in_the_sitemap(self):
        self.assertNotIn("/healthz", self.client.get("/sitemap.xml").content.decode())


class ProductionCheckTests(TestCase):
    """The deploy checks that catch a configuration which boots but is quietly broken."""

    def run_check(self, func, **overrides):
        from django.core.checks import registry  # noqa: F401 - keeps the registry imported

        with override_settings(DEBUG=False, **overrides):
            return func(None)

    def test_site_url_must_be_a_real_public_https_url(self):
        from apps.core.checks import check_site_url

        self.assertEqual(self.run_check(check_site_url, SITE_URL="https://zencraftsolution.com"), [])
        for bad in ["", "http://127.0.0.1:8000", "http://localhost:8000", "http://zencraftsolution.com"]:
            self.assertTrue(self.run_check(check_site_url, SITE_URL=bad), bad)
        ids = {e.id for e in self.run_check(check_site_url, SITE_URL="http://localhost:8000")}
        self.assertEqual(ids, {"zencraft.E002", "zencraft.E003"})

    def test_media_must_not_be_the_local_disk_in_production(self):
        from apps.core.checks import check_media_storage

        self.assertTrue(self.run_check(check_media_storage, USE_CLOUDINARY=False))
        self.assertEqual(self.run_check(check_media_storage, USE_CLOUDINARY=True), [])

    def test_email_must_actually_send(self):
        from apps.core.checks import check_email_backend

        for backend in ["django.core.mail.backends.console.EmailBackend", "django.core.mail.backends.locmem.EmailBackend"]:
            self.assertTrue(self.run_check(check_email_backend, EMAIL_BACKEND=backend), backend)
        self.assertEqual(self.run_check(check_email_backend, EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend"), [])

    def test_the_cache_must_be_shared_between_workers(self):
        from apps.core.checks import check_cache_backend

        locmem = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
        shared = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "c"}}
        self.assertTrue(self.run_check(check_cache_backend, CACHES=locmem))
        self.assertEqual(self.run_check(check_cache_backend, CACHES=shared), [])

    def test_private_files_must_not_sit_on_a_disk_that_is_wiped(self):
        from apps.core.checks import check_private_storage

        self.assertTrue(self.run_check(check_private_storage, PRIVATE_STORAGE_BACKEND="local", PRIVATE_MEDIA_PERSISTENT=False))
        # Object storage, or a declared persistent disk, are both fine.
        self.assertEqual(self.run_check(check_private_storage, PRIVATE_STORAGE_BACKEND="s3"), [])
        self.assertEqual(
            self.run_check(check_private_storage, PRIVATE_STORAGE_BACKEND="local", PRIVATE_MEDIA_PERSISTENT=True), []
        )

    def test_uploads_must_not_be_waved_through(self):
        from apps.core.checks import check_upload_scanning

        self.assertTrue(self.run_check(check_upload_scanning, UPLOAD_SCAN_HOOK="apps.core.uploads.noop_scan"))
        self.assertEqual(self.run_check(check_upload_scanning, UPLOAD_SCAN_HOOK="apps.core.uploads.clamav_scan"), [])

    def test_none_of_them_fire_during_local_development(self):
        from apps.core import checks

        funcs = [checks.check_site_url, checks.check_media_storage, checks.check_email_backend,
                 checks.check_cache_backend, checks.check_upload_scanning, checks.check_private_storage]
        with override_settings(DEBUG=True, SITE_URL="http://127.0.0.1:8000"):
            for func in funcs:
                self.assertEqual(func(None), [], func.__name__)


class RequestIdTests(TestCase):
    def test_every_response_carries_an_id(self):
        response = self.client.get("/legal/privacy/")
        self.assertRegex(response["X-Request-ID"], r"^[0-9a-f]{32}$")

    def test_each_request_gets_its_own(self):
        first = self.client.get("/legal/privacy/")["X-Request-ID"]
        second = self.client.get("/legal/terms/")["X-Request-ID"]
        self.assertNotEqual(first, second)

    def test_an_id_from_the_proxy_is_kept_so_the_logs_line_up(self):
        response = self.client.get("/legal/privacy/", HTTP_X_REQUEST_ID="abc123def456")
        self.assertEqual(response["X-Request-ID"], "abc123def456")

    def test_a_junk_header_is_replaced_rather_than_logged(self):
        for junk in ["../../etc/passwd", "a b c", "short", "x" * 100, "<script>"]:
            response = self.client.get("/legal/privacy/", HTTP_X_REQUEST_ID=junk)
            self.assertNotEqual(response["X-Request-ID"], junk, junk)

    def test_log_lines_carry_the_id_of_the_request_that_produced_them(self):
        from apps.core.logging import JsonFormatter, RequestIDFilter, set_request_id

        token = set_request_id("deadbeefcafe")
        try:
            record = logging.LogRecord("x", logging.ERROR, "p", 1, "payment failed", None, None)
            RequestIDFilter().filter(record)
            payload = json.loads(JsonFormatter().format(record))
        finally:
            from apps.core.logging import _request_id

            _request_id.reset(token)
        self.assertEqual(payload["request_id"], "deadbeefcafe")
        self.assertEqual((payload["level"], payload["message"], payload["logger"]), ("ERROR", "payment failed", "x"))

    def test_the_formatter_keeps_extra_fields_and_the_traceback(self):
        from apps.core.logging import JsonFormatter

        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            record = logging.LogRecord("x", logging.ERROR, "p", 1, "failed", None, sys.exc_info())
        record.order_reference = "ZO-1234"
        payload = json.loads(JsonFormatter().format(record))
        self.assertEqual(payload["order_reference"], "ZO-1234")
        self.assertIn("ValueError: boom", payload["exception"])


class SentryScrubbingTests(TestCase):
    """Error reports must not become a second copy of the database."""

    def test_the_request_body_cookies_and_user_never_leave(self):
        from apps.core.observability import scrub

        event = scrub({
            "request": {
                "url": "/careers/jobs/x/apply/details/",
                "data": {"full_name": "Asmita Gurung", "cv": "<binary>"},
                "cookies": {"sessionid": "abc"},
                "headers": {"Authorization": "Bearer t", "Cookie": "sessionid=abc", "User-Agent": "Firefox"},
                "query_string": {"email": "a@b.test", "page": "2"},
            },
            "user": {"id": 1, "email": "staff@example.com", "ip_address": "203.0.113.7"},
            "extra": {"phone": "+977 98", "order_count": 3},
        })
        self.assertNotIn("data", event["request"])
        self.assertNotIn("cookies", event["request"])
        self.assertNotIn("user", event)
        self.assertEqual(event["request"]["headers"]["Authorization"], "[redacted]")
        self.assertEqual(event["request"]["headers"]["Cookie"], "[redacted]")
        self.assertEqual(event["request"]["headers"]["User-Agent"], "Firefox")  # useful, not personal
        self.assertEqual(event["request"]["query_string"], {"email": "[redacted]", "page": "2"})
        self.assertEqual(event["extra"], {"phone": "[redacted]", "order_count": 3})
        self.assertEqual(event["request"]["url"], "/careers/jobs/x/apply/details/")

    def test_it_stays_off_without_a_dsn(self):
        from apps.core.observability import init_sentry

        self.assertFalse(init_sentry("", "production"))


class DeployCheckSmokeTests(TestCase):
    """Boots a fresh process with DEBUG=False and runs `check --deploy`, so security-setting regressions fail CI."""

    # A production-shaped environment, because the zencraft.E00x checks refuse a deployment that
    # would lose uploaded media, print email to a log, or share one lockout counter per worker.
    PRODUCTION_ENV = {
        "DEBUG": "False",
        "SECRET_KEY": "k7Rq2vX9mZp4Lw8Ns3Tb6Yc1Hd5Fg0Jj-e_uQaWoPiUyTrEsDxCvBnM",  # 56 chars, test-only
        "ALLOWED_HOSTS": "zencraftsolution.com",
        "SITE_URL": "https://zencraftsolution.com",
        "CLOUDINARY_CLOUD_NAME": "test-placeholder",
        "CLOUDINARY_API_KEY": "test-placeholder",
        "CLOUDINARY_API_SECRET": "test-placeholder",
        "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "CACHE_URL": "",
        "PRIVATE_MEDIA_PERSISTENT": "True",
    }

    def run_in_production_mode(self, code):
        import os
        import subprocess
        import sys

        from django.conf import settings

        env = {**os.environ, **self.PRODUCTION_ENV}
        env.pop("UPLOAD_SCAN_HOOK", None)  # must default to ClamAV in production
        # Set by apps/core/conftest.py so Playwright's sync API can touch the ORM. It is a test
        # harness setting, and Django's own deploy check rightly refuses it in a deployment, so
        # it must not travel into the subprocess that simulates one.
        env.pop("DJANGO_ALLOW_ASYNC_UNSAFE", None)
        return subprocess.run([sys.executable, "-c", code], cwd=settings.BASE_DIR, env=env, capture_output=True, text=True, timeout=300)

    def test_check_deploy_reports_zero_issues(self):
        result = self.run_in_production_mode(
            "import sys; from django.core.management import execute_from_command_line; "
            "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); "
            "execute_from_command_line(['manage.py', 'check', '--deploy', '--fail-level', 'WARNING'])"
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("System check identified no issues", output)

    def test_gate_catches_a_security_regression(self):
        # Reintroduce the pre-fix X_FRAME_OPTIONS value and confirm the same gate fails.
        result = self.run_in_production_mode(
            "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); "
            "from django.conf import settings; settings.X_FRAME_OPTIONS = 'SAMEORIGIN'; "
            "from django.core.management import call_command; call_command('check', deploy=True, fail_level='WARNING')"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("security.W019", result.stdout + result.stderr)

    def test_production_settings_default_to_clamav(self):
        result = self.run_in_production_mode(
            "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); "
            "from django.conf import settings; print(settings.UPLOAD_SCAN_HOOK, settings.X_FRAME_OPTIONS, settings.SESSION_COOKIE_SECURE)"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["apps.core.uploads.clamav_scan", "DENY", "True"])


class SeededSiteSmokeTests(TestCase):
    """Loads the real seed content once and renders the pages that depend on all of it together."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_zencraft", stdout=io.StringIO())

    def test_seed_is_idempotent(self):
        counts = (Service.objects.count(), JobOpening.objects.count(), BlogPost.objects.count())
        call_command("seed_zencraft", stdout=io.StringIO())
        self.assertEqual(counts, (Service.objects.count(), JobOpening.objects.count(), BlogPost.objects.count()))
        self.assertEqual(counts, (9, 7, 6))
        for service in Service.objects.all():
            self.assertEqual(service.steps.count(), 6)
            self.assertGreaterEqual(len(service.deliverables), 6)
            self.assertGreaterEqual(service.faqs.count(), 4)

    def test_core_pages_render(self):
        for url in ["/", "/about/", "/contact/", "/book-consultation/", "/legal/privacy/", "/legal/terms/", "/legal/cookies/", "/sitemap.xml"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        home = self.client.get("/")
        self.assertEqual(len(home.context["hero_slides"]), 4)
        self.assertContains(home, "data-hero-slider")
        self.assertContains(home, '"@type":"Organization"')

    def test_removed_industry_is_gone_everywhere(self):
        from apps.services.models import Industry

        self.assertFalse(Industry.objects.filter(slug="finance").exists())
        self.assertEqual(self.client.get("/services/industries/finance/").status_code, 404)
        listing = self.client.get(reverse("services:industries"))
        self.assertNotContains(listing, "Banking and finance")
        self.assertEqual(len(listing.context["industries"]), 6)
        # Its case study survives without an industry label, and no hero slide links to the dead page.
        case = self.client.get("/work/mobile-banking-development-bank/")
        self.assertEqual(case.status_code, 200)
        self.assertNotContains(case, "/services/industries/finance/")
        self.assertNotContains(self.client.get("/"), "/services/industries/finance/")
        self.assertNotIn("/services/industries/finance/", self.client.get("/sitemap.xml").content.decode())

    def test_site_search_spans_services_case_studies_and_posts(self):
        response = self.client.get(reverse("core:search") + "?q=banking")
        self.assertGreater(response.context["total"], 0)
        self.assertTrue(response.context["cases"])
        self.assertEqual(self.client.get(reverse("core:search")).context["total"], 0)
        empty = self.client.get(reverse("core:search") + "?q=zzzxqvnonexistent")
        self.assertContains(empty, "Nothing found")
        self.assertTrue(re.search(r"\d+ results?", empty.content.decode()))


class FeedbackTests(TestCase):
    """The form on the home page, and what reaches the team."""

    URL = reverse("core:feedback")
    VALID = {
        "name": "Asmita Gurung", "email": "asmita@example.com", "company": "Example Ltd",
        "rating": "5", "message": "They shipped on time and explained the trade-offs clearly.",
    }

    def setUp(self):
        cache.clear()
        mail.outbox.clear()

    def test_the_form_is_on_the_home_page(self):
        response = self.client.get("/")
        self.assertContains(response, 'id="feedback"')
        self.assertContains(response, "Tell us how we are doing")
        self.assertContains(response, self.URL)

    def test_feedback_is_stored_and_the_visitor_is_thanked(self):
        response = self.client.post(self.URL, self.VALID, HTTP_REFERER="/", follow=True)
        entry = Feedback.objects.get()
        self.assertEqual((entry.name, entry.rating, entry.company), ("Asmita Gurung", 5, "Example Ltd"))
        self.assertFalse(entry.is_read)
        self.assertContains(response, "Thank you")

    def test_the_team_is_told(self):
        self.client.post(self.URL, self.VALID, HTTP_REFERER="/")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Asmita Gurung", mail.outbox[0].subject)
        self.assertIn("Very good", mail.outbox[0].subject)
        self.assertIn("shipped on time", mail.outbox[0].body)

    def test_nothing_is_published_unless_the_visitor_says_so(self):
        self.client.post(self.URL, self.VALID, HTTP_REFERER="/")
        self.assertFalse(Feedback.objects.get().may_publish)

        Feedback.objects.all().delete()
        self.client.post(self.URL, {**self.VALID, "may_publish": "on"}, HTTP_REFERER="/")
        self.assertTrue(Feedback.objects.get().may_publish)

    def test_the_email_address_is_optional(self):
        self.client.post(self.URL, {**self.VALID, "email": ""}, HTTP_REFERER="/")
        self.assertEqual(Feedback.objects.get().email, "")

    def test_a_message_of_two_words_is_refused(self):
        response = self.client.post(self.URL, {**self.VALID, "message": "ok"}, HTTP_REFERER="/", follow=True)
        self.assertFalse(Feedback.objects.exists())
        self.assertContains(response, "check the highlighted fields")

    def test_the_honeypot_catches_a_bot(self):
        self.client.post(self.URL, {**self.VALID, "website": "http://spam.test"}, HTTP_REFERER="/")
        self.assertFalse(Feedback.objects.exists())

    def test_it_is_rate_limited(self):
        for _ in range(5):
            self.client.post(self.URL, self.VALID, HTTP_REFERER="/")
        response = self.client.post(self.URL, self.VALID, HTTP_REFERER="/")
        self.assertEqual(response.status_code, 429)

    def test_a_hostile_referer_does_not_become_a_redirect(self):
        response = self.client.post(self.URL, self.VALID, HTTP_REFERER="https://evil.example/")
        self.assertTrue(response["Location"].startswith("/"))

    def test_feedback_never_appears_on_the_public_site_by_itself(self):
        """Even approved, it is a record for the team until somebody copies it across."""
        self.client.post(self.URL, {**self.VALID, "may_publish": "on"}, HTTP_REFERER="/")
        self.assertNotContains(self.client.get("/"), "shipped on time")
