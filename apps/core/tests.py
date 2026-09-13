"""Cross-cutting tests: helpers, template tags, rate limiting, uploads and scanning, middleware, error pages,
sitemap/robots, the public core pages and the seed command. App-specific behaviour lives in each app's tests.py."""
import io
import json
import re
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.http import HttpResponse
from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.blog.models import BlogPost
from apps.careers.models import JobOpening
from apps.core import uploads
from apps.core.models import ConsultationBooking, ContactSubmission, NewsletterSubscriber, PageView, SiteSettings
from apps.core.testing import CLAMAV_SCAN, NOOP_SCAN, docx_bytes, make_job, make_product, pdf_upload
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
            uploads.private_storage.url("cvs/x.pdf")
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
    def test_robots(self):
        body = self.client.get("/robots.txt").content.decode()
        self.assertIn("Disallow: /hq/", body)
        self.assertRegex(body, r"Sitemap: http://testserver/sitemap\.xml")

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


class DeployCheckSmokeTests(TestCase):
    """Boots a fresh process with DEBUG=False and runs `check --deploy`, so security-setting regressions fail CI."""

    PRODUCTION_ENV = {
        "DEBUG": "False",
        "SECRET_KEY": "k7Rq2vX9mZp4Lw8Ns3Tb6Yc1Hd5Fg0Jj-e_uQaWoPiUyTrEsDxCvBnM",  # 56 chars, test-only
        "ALLOWED_HOSTS": "zencraftsolution.com",
    }

    def run_in_production_mode(self, code):
        import os
        import subprocess
        import sys

        from django.conf import settings

        env = {**os.environ, **self.PRODUCTION_ENV}
        env.pop("UPLOAD_SCAN_HOOK", None)  # must default to ClamAV in production
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
        self.assertEqual(len(home.context["hero_slides"]), 5)
        self.assertContains(home, "data-hero-slider")
        self.assertContains(home, '"@type":"Organization"')

    def test_site_search_spans_services_case_studies_and_posts(self):
        response = self.client.get(reverse("core:search") + "?q=banking")
        self.assertGreater(response.context["total"], 0)
        self.assertTrue(response.context["cases"])
        self.assertEqual(self.client.get(reverse("core:search")).context["total"], 0)
        empty = self.client.get(reverse("core:search") + "?q=zzzxqvnonexistent")
        self.assertContains(empty, "Nothing found")
        self.assertTrue(re.search(r"\d+ results?", empty.content.decode()))
