import csv
import io
import json
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms.models import model_to_dict
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from apps.blog.models import BlogCategory
from apps.careers.models import JobApplication
from apps.commerce.models import Order
from apps.core.models import AuditLog, NewsletterSubscriber, SiteSettings
from apps.core.testing import PASSWORD, docx_bytes, image_upload, make_application, make_job, make_staff, make_user, release_file_response
from apps.dashboard.crud import REGISTRY
from apps.estimator.models import EstimatorConfig, ProjectInquiry
from apps.portfolio.models import TeamMember
from apps.services.models import Technology

DASH_LOGIN = reverse("dashboard:login")
ADMIN_LOGIN = f"/{settings.DASHBOARD_PATH}django-admin/login/"


def audit(action, **filters):
    return AuditLog.objects.filter(action=action, **filters)


class LoginThrottleTests(TestCase):
    """Both staff login surfaces share one IP-keyed lockout (apps.core.throttle)."""

    def setUp(self):
        cache.clear()
        self.staff = make_staff(is_superuser=True)

    def fail(self, url, times):
        for _ in range(times):
            response = self.client.post(url, {"username": "hq-staff", "password": "wrong"})
            self.assertEqual(response.status_code, 200)

    def good_login(self, url, **extra):
        return self.client.post(url, {"username": "hq-staff", "password": PASSWORD}, **extra)

    def assert_throttled(self, url):
        self.fail(url, settings.LOGIN_MAX_FAILURES)
        response = self.good_login(url)  # even the correct password is refused while locked
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)
        return response

    def test_dashboard_login_locks_after_max_failures(self):
        self.assertContains(self.assert_throttled(DASH_LOGIN), "Too many failed attempts", status_code=429)

    def test_django_admin_login_locks_identically(self):
        self.assertEqual(ADMIN_LOGIN, reverse("admin:login"))
        self.assert_throttled(ADMIN_LOGIN)

    def test_failures_are_shared_across_both_login_pages(self):
        half = settings.LOGIN_MAX_FAILURES // 2
        self.fail(ADMIN_LOGIN, half)
        self.fail(DASH_LOGIN, settings.LOGIN_MAX_FAILURES - half)
        self.assertEqual(self.good_login(ADMIN_LOGIN).status_code, 429)
        self.assertEqual(self.good_login(DASH_LOGIN).status_code, 429)

    def test_lockout_expires_after_cooldown(self):
        with freeze_time(timezone.now()) as frozen:
            self.fail(DASH_LOGIN, settings.LOGIN_MAX_FAILURES)
            self.assertEqual(self.good_login(DASH_LOGIN).status_code, 429)
            frozen.tick(timedelta(seconds=settings.LOGIN_LOCKOUT_SECONDS - 60))
            self.assertEqual(self.good_login(DASH_LOGIN).status_code, 429)
            frozen.tick(timedelta(seconds=120))
            response = self.good_login(DASH_LOGIN)
        self.assertRedirects(response, reverse("dashboard:overview"), fetch_redirect_response=False)
        self.assertTrue(audit("signed in").exists())

    def test_get_requests_are_never_throttled(self):
        self.fail(DASH_LOGIN, settings.LOGIN_MAX_FAILURES)
        self.assertEqual(self.client.get(DASH_LOGIN).status_code, 200)
        self.assertEqual(self.client.get(ADMIN_LOGIN).status_code, 200)

    def test_spoofed_forwarded_for_header_does_not_reset_lockout(self):
        self.fail(ADMIN_LOGIN, settings.LOGIN_MAX_FAILURES)
        self.assertEqual(self.good_login(ADMIN_LOGIN, HTTP_X_FORWARDED_FOR="203.0.113.99").status_code, 429)

    def test_successful_login_resets_counter(self):
        self.fail(ADMIN_LOGIN, settings.LOGIN_MAX_FAILURES - 1)
        self.assertEqual(self.client.post(ADMIN_LOGIN, {"username": "hq-staff", "password": PASSWORD, "next": "/hq/django-admin/"}).status_code, 302)
        self.client.logout()
        self.fail(ADMIN_LOGIN, settings.LOGIN_MAX_FAILURES - 1)
        self.assertEqual(self.good_login(ADMIN_LOGIN).status_code, 302)

    def test_non_staff_credentials_count_as_failures(self):
        make_user("customer")
        for _ in range(settings.LOGIN_MAX_FAILURES):
            response = self.client.post(DASH_LOGIN, {"username": "customer", "password": PASSWORD})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.good_login(DASH_LOGIN).status_code, 429)

    def test_lockout_is_audit_logged(self):
        self.fail(DASH_LOGIN, settings.LOGIN_MAX_FAILURES)
        self.assertEqual(audit("login locked out").count(), 1)

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_trusted_proxy_uses_rightmost_forwarded_address(self):
        self.fail(DASH_LOGIN, settings.LOGIN_MAX_FAILURES)
        response = self.good_login(DASH_LOGIN, HTTP_X_FORWARDED_FOR="spoofed, 198.51.100.7")
        self.assertEqual(response.status_code, 302)

    def test_framing_denied_everywhere_except_cv_preview(self):
        self.assertEqual(self.client.get("/").headers["X-Frame-Options"], "DENY")
        self.assertEqual(self.client.get(DASH_LOGIN).headers["X-Frame-Options"], "DENY")
        app = make_application(cv=SimpleUploadedFile("cv.pdf", b"%PDF-1.4 test"), cv_original_name="cv.pdf")
        self.client.force_login(self.staff)
        response = self.client.get(reverse("dashboard:application_cv", args=[app.pk]))
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")
        release_file_response(response)
        self.assertEqual(self.client.get(reverse("dashboard:application_detail", args=[app.pk])).headers["X-Frame-Options"], "DENY")
        app.cv.delete()

    def test_logout_requires_post_and_is_logged(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("dashboard:logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("dashboard:logout")), DASH_LOGIN)
        self.assertTrue(audit("signed out").exists())


class DashboardTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = make_staff()
        self.client.force_login(self.staff)


class AccessControlTests(DashboardTestCase):
    def all_urls(self):
        job = make_job()
        app = make_application(job)
        lead = ProjectInquiry.objects.create(
            reference="PI-ACCESS", project_type_label="Web", timeline="standard", team_preference="unsure", design_needs="existing",
            name="Lead", email="lead@example.com", estimate_low_npr=1, estimate_high_npr=2, estimate_weeks_low=1,
            estimate_weeks_high=2, exchange_rate=Decimal("134"),
        )
        order = Order.objects.create(reference="ZC-ACCESS", customer_name="C", email="c@example.com", phone="1",
                                     exchange_rate=Decimal("134"), total_usd=Decimal("1"))
        names = ["overview", "leads", "applications", "applications_list", "orders", "estimator_config", "settings", "analytics", "audit"]
        urls = [reverse(f"dashboard:{n}") for n in names]
        urls += [reverse("dashboard:lead_detail", args=[lead.pk]), reverse("dashboard:application_detail", args=[app.pk]),
                 reverse("dashboard:order_detail", args=[order.pk])]
        for slug, cfg in REGISTRY.items():
            urls += [reverse("dashboard:crud_list", args=[slug]), reverse("dashboard:crud_create", args=[slug])]
            obj = cfg["model"].objects.first()
            if obj:
                urls.append(reverse("dashboard:crud_edit", args=[slug, obj.pk]))
        return urls

    def test_staff_can_open_every_page(self):
        for url in self.all_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:analytics") + "?days=5000").context["days"], 180)
        self.assertEqual(self.client.get(reverse("dashboard:analytics") + "?days=abc").context["days"], 30)

    def test_anonymous_redirected_and_non_staff_gets_404(self):
        urls = self.all_urls()
        anonymous = Client()
        visitor = Client()
        visitor.force_login(make_user("visitor"))
        for url in urls:
            with self.subTest(url=url):
                response = anonymous.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(DASH_LOGIN))
                self.assertEqual(visitor.get(url).status_code, 404)

    def test_unknown_crud_slug_404(self):
        self.assertEqual(self.client.get(reverse("dashboard:crud_list", args=["users"])).status_code, 404)


class PrivateFileTests(DashboardTestCase):
    def tearDown(self):
        for app in JobApplication.objects.exclude(cv=""):
            app.cv.delete(save=False)
        for lead in ProjectInquiry.objects.exclude(document=""):
            lead.document.delete(save=False)

    def test_pdf_cv_inline_preview_and_download_logged(self):
        app = make_application(cv=SimpleUploadedFile("cv.pdf", b"%PDF-1.4 x"), cv_original_name="Sita CV.pdf")
        url = reverse("dashboard:application_cv", args=[app.pk])
        response = self.client.get(url)
        self.assertEqual((response.status_code, response["Content-Type"]), (200, "application/pdf"))
        self.assertTrue(response["Content-Disposition"].startswith("inline"))
        self.assertEqual(response["Cache-Control"], "no-store")
        release_file_response(response)
        download = self.client.get(url + "?download=1")
        self.assertTrue(download["Content-Disposition"].startswith("attachment"))
        self.assertIn("Sita CV.pdf", download["Content-Disposition"])
        release_file_response(download)
        self.assertEqual(audit("opened CV", object_id=str(app.pk), user=self.staff).count(), 1)
        self.assertEqual(audit("downloaded CV", object_id=str(app.pk)).count(), 1)

    def test_docx_cv_always_downloads(self):
        app = make_application(cv=SimpleUploadedFile("cv.docx", docx_bytes()), cv_original_name="cv.docx")
        response = self.client.get(reverse("dashboard:application_cv", args=[app.pk]))
        self.assertTrue(response["Content-Disposition"].startswith("attachment"))
        release_file_response(response)
        self.assertContains(self.client.get(reverse("dashboard:application_detail", args=[app.pk])), "cannot be previewed")

    def test_cv_access_denied_for_anonymous_and_non_staff(self):
        app = make_application(cv=SimpleUploadedFile("cv.pdf", b"%PDF-1.4 x"))
        url = reverse("dashboard:application_cv", args=[app.pk])
        self.assertEqual(Client().get(url).status_code, 302)
        visitor = Client()
        visitor.force_login(make_user("visitor"))
        self.assertEqual(visitor.get(url).status_code, 404)
        self.assertFalse(audit("opened CV").exists())

    def test_missing_cv_or_file_404(self):
        job = make_job()
        no_cv = make_application(job, email="nocv@example.com")
        self.assertEqual(self.client.get(reverse("dashboard:application_cv", args=[no_cv.pk])).status_code, 404)
        gone = make_application(job, email="gone@example.com", cv=SimpleUploadedFile("cv.pdf", b"%PDF-1.4 x"))
        gone.cv.storage.delete(gone.cv.name)
        self.assertEqual(self.client.get(reverse("dashboard:application_cv", args=[gone.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("dashboard:application_cv", args=[999999])).status_code, 404)

    def test_requirement_document_download(self):
        lead = ProjectInquiry.objects.create(
            reference="PI-DOC", project_type_label="Web", timeline="standard", team_preference="unsure", design_needs="existing",
            name="Lead", email="lead@example.com", estimate_low_npr=1, estimate_high_npr=2, estimate_weeks_low=1,
            estimate_weeks_high=2, exchange_rate=Decimal("134"),
        )
        url = reverse("dashboard:lead_document", args=[lead.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        lead.document = SimpleUploadedFile("brief.pdf", b"%PDF-1.4 x")
        lead.document_name = "brief.pdf"
        lead.save()
        response = self.client.get(url)
        self.assertTrue(response["Content-Disposition"].startswith("attachment"))
        release_file_response(response)
        self.assertTrue(audit("downloaded requirement document", object_id=str(lead.pk)).exists())


class PipelineTests(DashboardTestCase):
    def make_lead(self, **kwargs):
        defaults = dict(
            reference="PI-TEST01", project_type_label="Web", timeline="standard", team_preference="unsure", design_needs="existing",
            name="Lead", company="Acme Traders", email="lead@example.com", estimate_low_npr=100000, estimate_high_npr=200000,
            estimate_weeks_low=4, estimate_weeks_high=6, exchange_rate=Decimal("134"), platforms=["web"],
            suggested_team=[{"role": "Developer", "allocation": 1.0}],
        )
        defaults.update(kwargs)
        return ProjectInquiry.objects.create(**defaults)

    def test_lead_update_and_note_are_audited(self):
        lead = self.make_lead()
        url = reverse("dashboard:lead_detail", args=[lead.pk])
        response = self.client.post(url, {"status": "qualified", "assigned_to": self.staff.pk, "internal_notes": "Budget ok"})
        self.assertRedirects(response, url)
        lead.refresh_from_db()
        self.assertEqual((lead.status, lead.assigned_to), ("qualified", self.staff))
        self.assertTrue(audit("updated lead", object_id=str(lead.pk)).exists())
        self.client.post(url, {"add_note": "1", "body": "Called them"})
        self.assertEqual(lead.notes.get().author, self.staff)
        self.assertTrue(audit("noted lead").exists())
        self.assertContains(self.client.get(reverse("dashboard:leads") + "?mine=1"), "Acme Traders")

    def test_kanban_api(self):
        lead = self.make_lead()
        url = reverse("dashboard:api_lead_status", args=[lead.pk])
        response = self.client.patch(url, json.dumps({"status": "won"}), content_type="application/json")
        self.assertEqual(response.json(), {"ok": True, "status": "won", "label": "Won"})
        self.assertTrue(audit("moved lead", object_id=str(lead.pk), detail="new to won").exists())
        self.assertEqual(self.client.patch(url, json.dumps({"status": "bribed"}), content_type="application/json").status_code, 400)
        self.assertEqual(self.client.patch(url, json.dumps({}), content_type="application/json").status_code, 400)
        missing = reverse("dashboard:api_application_status", args=[999999])
        self.assertEqual(self.client.patch(missing, json.dumps({"status": "hired"}), content_type="application/json").status_code, 404)

    def test_kanban_api_requires_staff_and_csrf(self):
        app = make_application()
        url = reverse("dashboard:api_application_status", args=[app.pk])
        body = json.dumps({"status": "hired"})
        self.assertEqual(Client().patch(url, body, content_type="application/json").status_code, 403)
        visitor = Client()
        visitor.force_login(make_user("visitor"))
        self.assertEqual(visitor.patch(url, body, content_type="application/json").status_code, 403)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.staff)
        self.assertEqual(strict.patch(url, body, content_type="application/json").status_code, 403)
        app.refresh_from_db()
        self.assertEqual(app.status, "received")

    def test_application_detail_update_note_and_view_logged(self):
        app = make_application(application_mode="manual", headline="Junior dev", skills="Python")
        app.experience.create(company="Shop", title="Intern", start_date="2024-01")
        url = reverse("dashboard:application_detail", args=[app.pk])
        self.assertContains(self.client.get(url), "Junior dev")
        self.assertTrue(audit("viewed application", object_id=str(app.pk)).exists())
        self.assertRedirects(self.client.post(url, {"status": "interview", "rating": "4"}), url)
        app.refresh_from_db()
        self.assertEqual((app.status, app.rating), ("interview", 4))
        self.assertTrue(audit("updated application").exists())
        self.client.post(url, {"add_note": "1", "body": "Strong portfolio"})
        self.assertEqual(app.notes.get().body, "Strong portfolio")

    def test_bulk_update_filters_and_export(self):
        job = make_job()
        junior = make_application(job, full_name="Junior Person", email="j@example.com", years_experience=Decimal("0.5"), skills="Flutter")
        senior = make_application(job, full_name="Senior Person", email="s@example.com", years_experience=Decimal("7"))
        list_url = reverse("dashboard:applications_list")
        self.assertContains(self.client.get(list_url + "?exp=0-1"), "Junior Person")
        self.assertNotContains(self.client.get(list_url + "?exp=6%2B"), "Junior Person")
        self.assertContains(self.client.get(list_url + "?q=flutter"), "Junior Person")
        self.assertContains(self.client.get(reverse("dashboard:applications") + f"?job={job.pk}&status=received"), "Senior Person")

        response = self.client.post(list_url, {"ids": [junior.pk, senior.pk], "bulk_status": "shortlisted"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(set(JobApplication.objects.values_list("status", flat=True)), {"shortlisted"})
        self.assertTrue(audit("bulk updated applications").exists())
        self.client.post(list_url, {"ids": [junior.pk], "bulk_status": "not-a-status"})
        junior.refresh_from_db()
        self.assertEqual(junior.status, "shortlisted")

        export = self.client.get(reverse("dashboard:applications_export") + "?exp=3-6")
        rows = list(csv.reader(io.StringIO(export.content.decode())))
        self.assertEqual(rows[0][:3], ["Reference", "Name", "Email"])
        self.assertEqual(len(rows), 1)  # nobody has 3 to 6 years
        self.assertTrue(audit("exported applications").exists())

    def test_order_update_and_filter(self):
        order = Order.objects.create(reference="ZC-DASH01", customer_name="Customer", email="c@example.com", phone="1",
                                     exchange_rate=Decimal("134"), total_usd=Decimal("10"), payment_status="awaiting")
        self.assertContains(self.client.get(reverse("dashboard:orders") + "?status=awaiting"), "ZC-DASH01")
        self.assertNotContains(self.client.get(reverse("dashboard:orders") + "?status=paid"), "ZC-DASH01")
        url = reverse("dashboard:order_detail", args=[order.pk])
        self.assertRedirects(self.client.post(url, {"payment_status": "paid", "fulfilment_status": "scheduled"}), url)
        order.refresh_from_db()
        self.assertEqual((order.payment_status, order.fulfilment_status), ("paid", "scheduled"))
        self.assertTrue(audit("updated order", object_id=str(order.pk)).exists())

    def test_newsletter_export_and_audit_search(self):
        NewsletterSubscriber.objects.create(email="reader@example.com")
        export = self.client.get(reverse("dashboard:newsletter_export"))
        self.assertIn("reader@example.com", export.content.decode())
        self.assertContains(self.client.get(reverse("dashboard:audit") + "?q=newsletter"), "exported newsletter list")


class CrudRegistryTests(DashboardTestCase):
    def test_technology_round_trip(self):
        create = reverse("dashboard:crud_create", args=["technologies"])
        data = {"name": "Svelte", "slug": "svelte", "category": "frontend", "logo_url": "https://cdn.simpleicons.org/svelte",
                "proficiency": 4, "years_used": 2, "order": 1}
        self.assertRedirects(self.client.post(create, data), reverse("dashboard:crud_list", args=["technologies"]))
        tech = Technology.objects.get(slug="svelte")
        self.assertTrue(audit("created", object_id=str(tech.pk)).exists())

        edit = reverse("dashboard:crud_edit", args=["technologies", tech.pk])
        response = self.client.post(edit, {**data, "name": "SvelteKit", "save_continue": "1"})
        self.assertRedirects(response, edit)
        tech.refresh_from_db()
        self.assertEqual(tech.name, "SvelteKit")
        self.assertTrue(audit("updated", object_id=str(tech.pk), detail__contains="name").exists())
        self.assertContains(self.client.get(reverse("dashboard:crud_list", args=["technologies"]) + "?q=kit"), "SvelteKit")

        delete = reverse("dashboard:crud_delete", args=["technologies", tech.pk])
        self.assertContains(self.client.get(delete), "Delete SvelteKit?")
        self.assertRedirects(self.client.post(delete), reverse("dashboard:crud_list", args=["technologies"]))
        self.assertFalse(Technology.objects.filter(pk=tech.pk).exists())
        self.assertTrue(audit("deleted", detail="Technologies: SvelteKit").exists())

    def test_blog_category_round_trip_and_validation(self):
        create = reverse("dashboard:crud_create", args=["blog-categories"])
        self.assertEqual(self.client.post(create, {"name": "", "slug": "bad slug!"}).status_code, 200)
        self.client.post(create, {"name": "Security", "slug": "security", "order": 3})
        category = BlogCategory.objects.get(slug="security")
        self.client.post(reverse("dashboard:crud_edit", args=["blog-categories", category.pk]), {"name": "Security notes", "slug": "security", "order": 3})
        category.refresh_from_db()
        self.assertEqual(category.name, "Security notes")
        self.client.post(reverse("dashboard:crud_delete", args=["blog-categories", category.pk]))
        self.assertFalse(BlogCategory.objects.exists())
        self.assertEqual(audit("created").count() + audit("updated").count() + audit("deleted").count(), 3)

    def test_protected_delete_is_refused(self):
        job = make_job()
        response = self.client.post(reverse("dashboard:crud_delete", args=["departments", job.department.pk]), follow=True)
        self.assertContains(response, "still referenced")
        self.assertTrue(job.department.__class__.objects.filter(pk=job.department.pk).exists())
        self.assertFalse(audit("deleted").exists())


class ConfigurationTests(DashboardTestCase):
    def form_data(self, instance, **overrides):
        data = {}
        for key, value in model_to_dict(instance).items():
            if key == "id" or value is None:
                continue
            data[key] = json.dumps(value) if isinstance(value, (dict, list)) else value
        data.update(overrides)
        return data

    def test_estimator_config_saves_and_validates_maps(self):
        config = EstimatorConfig.load()
        url = reverse("dashboard:estimator_config")
        bad = self.client.post(url, self.form_data(config, design_multipliers=json.dumps({"existing": 1})))
        self.assertContains(bad, "Missing key: uiux")
        bad = self.client.post(url, self.form_data(config, team_multipliers=json.dumps({"fixed": "x", "dedicated": 1, "unsure": 1})))
        self.assertContains(bad, "must be numbers")
        bad = self.client.post(url, self.form_data(config, urgency_multipliers=json.dumps([1, 2])))
        self.assertContains(bad, "JSON object")
        self.assertRedirects(self.client.post(url, self.form_data(config, blended_hourly_rate_npr="2500")), url)
        self.assertEqual(EstimatorConfig.load().blended_hourly_rate_npr, Decimal("2500"))
        self.assertTrue(audit("updated estimator config").exists())

    def test_site_settings_update_clears_cache(self):
        settings_obj = SiteSettings.load()
        url = reverse("dashboard:settings")
        response = self.client.post(url, self.form_data(settings_obj, exchange_rate_npr_per_usd="140.5000", phone="+977 9800000001"))
        self.assertRedirects(response, url)
        self.assertEqual(SiteSettings.load().exchange_rate_npr_per_usd, Decimal("140.5000"))
        self.assertContains(self.client.get("/contact/"), "+977 9800000001")
        self.assertTrue(audit("updated site settings", detail__contains="exchange_rate_npr_per_usd").exists())


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="zc-media-"))
class TeamPhotoUploadTests(DashboardTestCase):
    """Staff can attach a photo file in the dashboard instead of pasting an image URL."""

    CREATE = reverse("dashboard:crud_create", args=["team"])

    def form_data(self, **overrides):
        data = {"name": "Shankar Adhikari", "role": "Co-founder", "bio": "", "photo_url": "", "linkedin_url": "",
                "github_url": "", "order": 0}
        data.update(overrides)
        return data

    def test_form_accepts_files_and_offers_a_file_input(self):
        response = self.client.get(self.CREATE)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'type="file"')
        self.assertContains(response, 'name="photo"')

    def test_uploaded_photo_is_stored_and_preferred_over_the_url(self):
        response = self.client.post(self.CREATE, self.form_data(photo=image_upload("Shankar Photo.png")))
        self.assertRedirects(response, reverse("dashboard:crud_list", args=["team"]))
        member = TeamMember.objects.get()
        self.assertTrue(member.photo.name.startswith("team/"))
        self.assertNotIn("Shankar", member.photo.name)  # stored under an unguessable name
        self.assertEqual(member.photo_src, member.photo.url)
        self.assertTrue(audit("created", object_id=str(member.pk)).exists())

        member.photo_url = "https://example.com/hosted.jpg"
        member.save()
        self.assertEqual(member.photo_src, member.photo.url)  # the upload still wins

    def test_photo_url_alone_is_still_allowed(self):
        self.client.post(self.CREATE, self.form_data(photo_url="https://example.com/a.jpg"))
        member = TeamMember.objects.get()
        self.assertFalse(member.photo)
        self.assertEqual(member.photo_src, "https://example.com/a.jpg")

    def test_a_photo_is_required_in_one_form_or_the_other(self):
        response = self.client.post(self.CREATE, self.form_data())
        self.assertContains(response, "either upload an image or paste a photo URL")
        self.assertFalse(TeamMember.objects.exists())

    def test_rejects_non_images_and_oversized_files(self):
        bad_type = SimpleUploadedFile("cv.pdf", b"%PDF-1.4 not an image", content_type="application/pdf")
        response = self.client.post(self.CREATE, self.form_data(photo=bad_type))
        self.assertContains(response, "valid image")
        with override_settings(IMAGE_UPLOAD_MAX_BYTES=100):
            response = self.client.post(self.CREATE, self.form_data(photo=image_upload(size=(300, 300))))
            self.assertContains(response, "image is too large")
        response = self.client.post(self.CREATE, self.form_data(photo=image_upload("photo.gif", fmt="GIF")))
        self.assertContains(response, "JPG, PNG or WebP")
        self.assertFalse(TeamMember.objects.exists())

    def test_uploaded_photo_shows_on_the_public_about_page(self):
        self.client.post(self.CREATE, self.form_data(is_leadership="on", photo=image_upload()))
        member = TeamMember.objects.get()
        self.assertContains(Client().get(reverse("core:about")), member.photo.url)
