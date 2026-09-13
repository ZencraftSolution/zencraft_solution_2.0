import io
import json
import zipfile

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.blog.models import BlogPost
from apps.careers.models import JobApplication, JobOpening
from apps.commerce.models import Order, ProductizedService
from apps.core.utils import format_npr
from apps.dashboard.crud import REGISTRY
from apps.estimator.models import EstimatorEvent, ProjectInquiry
from apps.portfolio.models import CaseStudy
from apps.services.models import Industry, Service

PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def docx_bytes():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<w:document/>")
    return buf.getvalue()


class SeededTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_zencraft", stdout=io.StringIO())

    def setUp(self):
        cache.clear()


class FormattingTests(TestCase):
    def test_south_asian_grouping(self):
        self.assertEqual(format_npr(800000), "Rs. 8,00,000")
        self.assertEqual(format_npr(12345678), "Rs. 1,23,45,678")
        self.assertEqual(format_npr(950), "Rs. 950")


class PublicPageTests(SeededTestCase):
    def test_public_pages_render(self):
        urls = [
            reverse("core:home"), reverse("core:about"), reverse("core:contact"), reverse("core:consultation"),
            reverse("core:search") + "?q=cloud", reverse("core:privacy"), reverse("core:terms"), reverse("core:cookies"),
            reverse("services:list"), reverse("services:industries"), reverse("services:technologies"),
            reverse("portfolio:list"), reverse("commerce:pricing"), reverse("commerce:store"), reverse("commerce:cart"),
            reverse("estimator:start"), reverse("careers:landing"), reverse("careers:jobs") + "?level=senior",
            reverse("blog:list"), reverse("blog:list") + "?q=cloud", "/robots.txt", "/sitemap.xml",
        ]
        urls += [s.get_absolute_url() for s in Service.objects.all()]
        urls += [i.get_absolute_url() for i in Industry.objects.all()]
        urls += [c.get_absolute_url() for c in CaseStudy.objects.all()]
        urls += [j.get_absolute_url() for j in JobOpening.objects.all()]
        urls += [reverse("careers:apply", args=[j.slug]) for j in JobOpening.objects.all()[:2]]
        urls += [p.get_absolute_url() for p in BlogPost.objects.all()]
        urls += [p.get_absolute_url() for p in ProductizedService.objects.all()]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_nine_services_with_depth(self):
        self.assertEqual(Service.objects.count(), 9)
        for s in Service.objects.all():
            self.assertEqual(s.steps.count(), 6)
            self.assertGreaterEqual(len(s.deliverables), 6)
            self.assertGreaterEqual(s.faqs.count(), 4)

    def test_404_uses_terminal_page(self):
        response = self.client.get("/does-not-exist/")
        self.assertEqual(response.status_code, 404)

    def test_job_posting_json_ld(self):
        job = JobOpening.objects.first()
        self.assertContains(self.client.get(job.get_absolute_url()), '"@type": "JobPosting"')

    def test_contact_form(self):
        response = self.client.post(reverse("core:contact"), {
            "name": "Sita Sharma", "email": "sita@example.com", "subject": "Hello", "message": "We need an app.", "consent": "on",
        })
        self.assertEqual(response.status_code, 302)

    def test_honeypot_blocks_bots(self):
        response = self.client.post(reverse("core:contact"), {
            "name": "Bot", "email": "bot@example.com", "subject": "x", "message": "x", "consent": "on", "website": "http://spam",
        })
        self.assertEqual(response.status_code, 200)


class EstimatorTests(SeededTestCase):
    def answers(self):
        return {
            "project_type": "mobile-app", "features": ["auth", "payments", "notifications"], "platforms": ["ios", "android"],
            "timeline": "fast", "team_preference": "fixed", "design_needs": "uiux", "session_id": "test-session",
        }

    def test_config_api(self):
        data = self.client.get(reverse("estimator:config_api")).json()
        self.assertEqual(len(data["project_types"]), 7)

    def test_preview_range_is_ordered(self):
        response = self.client.post(reverse("estimator:preview_api"), json.dumps(self.answers()), content_type="application/json")
        est = response.json()["estimate"]
        self.assertLess(est["low_npr"], est["high_npr"])
        self.assertTrue(est["low_npr_display"].startswith("Rs. "))

    def test_submit_creates_lead_with_private_document(self):
        doc = SimpleUploadedFile("brief.pdf", PDF_BYTES, content_type="application/pdf")
        response = self.client.post(reverse("estimator:submit_api"), {
            "answers": json.dumps(self.answers()), "name": "Ramesh Koirala", "email": "ramesh@example.com",
            "company": "Koirala Traders", "consent": "on", "document": doc,
        })
        self.assertEqual(response.status_code, 200, response.content)
        lead = ProjectInquiry.objects.get(reference=response.json()["reference"])
        self.assertEqual(lead.platforms, ["ios", "android"])
        self.assertTrue(lead.document.name.startswith("inquiries/"))
        self.assertTrue(EstimatorEvent.objects.filter(session_id="test-session", step=8).exists())
        lead.document.delete()

    def test_submit_requires_consent(self):
        response = self.client.post(reverse("estimator:submit_api"), {"answers": json.dumps(self.answers()), "name": "A", "email": "a@example.com"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("consent", response.json()["errors"])


class CareersTests(SeededTestCase):
    def base_data(self, mode):
        return {
            "application_mode": mode, "full_name": "Asmita Gurung", "email": f"asmita-{mode}@example.com", "phone": "9800000000",
            "current_location": "Pokhara", "years_experience": "1.5", "notice_period": "1-month", "source": "website", "consent": "on",
            "edu-TOTAL_FORMS": "1", "edu-INITIAL_FORMS": "0", "edu-MIN_NUM_FORMS": "0", "edu-MAX_NUM_FORMS": "6",
            "exp-TOTAL_FORMS": "1", "exp-INITIAL_FORMS": "0", "exp-MIN_NUM_FORMS": "0", "exp-MAX_NUM_FORMS": "8",
            "prj-TOTAL_FORMS": "1", "prj-INITIAL_FORMS": "0", "prj-MIN_NUM_FORMS": "0", "prj-MAX_NUM_FORMS": "6",
        }

    def test_apply_with_cv_upload(self):
        job = JobOpening.objects.get(slug="junior-qa-engineer")
        data = self.base_data("cv")
        data["cv"] = SimpleUploadedFile("asmita-cv.docx", docx_bytes(), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        response = self.client.post(reverse("careers:apply", args=[job.slug]), data)
        self.assertRedirects(response, reverse("careers:applied"))
        app = JobApplication.objects.get(email="asmita-cv@example.com")
        self.assertTrue(app.cv.name.startswith("cvs/"))
        self.assertEqual(app.cv_original_name, "asmita-cv.docx")
        app.cv.delete()

    def test_apply_manually_without_cv(self):
        job = JobOpening.objects.get(slug="software-engineering-intern")
        data = self.base_data("manual")
        data.update({
            "headline": "Final-year BSc CSIT student", "professional_summary": "I build Django apps.", "skills": "Python, Django, React",
            "edu-0-institution": "Tribhuvan University", "edu-0-degree": "BSc CSIT", "edu-0-end_year": "2026",
            "exp-0-company": "Local startup", "exp-0-title": "Intern", "exp-0-start_date": "2025-06",
            "prj-0-name": "Bus ticket app", "prj-0-tech_used": "Flutter",
        })
        response = self.client.post(reverse("careers:apply", args=[job.slug]), data)
        self.assertRedirects(response, reverse("careers:applied"))
        app = JobApplication.objects.get(email="asmita-manual@example.com")
        self.assertFalse(app.cv)
        self.assertEqual(app.education.count(), 1)
        self.assertEqual(app.experience.count(), 1)
        self.assertEqual(app.projects.count(), 1)

    def test_manual_requires_history(self):
        job = JobOpening.objects.get(slug="software-engineering-intern")
        data = self.base_data("manual")
        data.update({"headline": "x", "professional_summary": "y", "skills": "z"})
        response = self.client.post(reverse("careers:apply", args=[job.slug]), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add at least one education or work experience entry")

    def test_rejects_fake_pdf(self):
        job = JobOpening.objects.get(slug="junior-qa-engineer")
        data = self.base_data("cv")
        data["cv"] = SimpleUploadedFile("cv.pdf", b"MZ this is really an exe", content_type="application/pdf")
        response = self.client.post(reverse("careers:apply", args=[job.slug]), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "does not look like a valid PDF")


@override_settings(DEBUG=True)
class CommerceTests(SeededTestCase):
    def test_cart_checkout_and_sandbox_payment(self):
        product = ProductizedService.objects.get(slug="discovery-workshop")
        self.client.post(reverse("commerce:cart_add", args=[product.pk]), {"quantity": 1})
        response = self.client.post(reverse("commerce:checkout"), {
            "customer_name": "Bishal Shrestha", "email": "bishal@example.com", "phone": "9811111111", "country": "Nepal", "consent": "on",
        })
        order = Order.objects.get(email="bishal@example.com")
        self.assertRedirects(response, reverse("commerce:payment", args=[order.reference]))
        self.assertEqual(order.total_npr, product.price_npr * 113 / 100)

        response = self.client.post(reverse("commerce:payment_start", args=[order.reference, "fonepay"]))
        self.assertRedirects(response, reverse("commerce:simulate", args=["fonepay", order.reference]))
        response = self.client.get(reverse("commerce:payment_callback", args=["fonepay", order.reference, "success"]))
        self.assertRedirects(response, reverse("commerce:order_done", args=[order.reference]))
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")

    def test_other_sessions_cannot_view_order(self):
        product = ProductizedService.objects.first()
        self.client.post(reverse("commerce:cart_add", args=[product.pk]))
        self.client.post(reverse("commerce:checkout"), {"customer_name": "A B", "email": "ab@example.com", "phone": "1", "country": "Nepal", "consent": "on"})
        order = Order.objects.get(email="ab@example.com")
        self.client.logout()
        self.client.cookies.clear()
        self.assertEqual(self.client.get(reverse("commerce:order_done", args=[order.reference])).status_code, 404)


class DashboardTests(SeededTestCase):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.staff = User.objects.create_user("hq-staff", "staff@example.com", "a-strong-passphrase-2026", is_staff=True)
        self.visitor = User.objects.create_user("visitor", "visitor@example.com", "a-strong-passphrase-2026")

    def test_anonymous_redirects_and_non_staff_gets_404(self):
        url = reverse("dashboard:overview")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.visitor)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_staff_pages_render(self):
        self.client.force_login(self.staff)
        urls = [reverse(n) for n in ["dashboard:overview", "dashboard:leads", "dashboard:applications", "dashboard:applications_list",
                                     "dashboard:applications_export", "dashboard:orders", "dashboard:estimator_config", "dashboard:settings",
                                     "dashboard:analytics", "dashboard:audit", "dashboard:newsletter_export"]]
        for slug in REGISTRY:
            urls.append(reverse("dashboard:crud_list", args=[slug]))
            urls.append(reverse("dashboard:crud_create", args=[slug]))
            obj = REGISTRY[slug]["model"].objects.first()
            if obj:
                urls.append(reverse("dashboard:crud_edit", args=[slug, obj.pk]))
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_kanban_status_api_and_cv_access_logged(self):
        job = JobOpening.objects.first()
        app = JobApplication.objects.create(
            reference="ZA-TEST01", job=job, full_name="Test Person", email="t@example.com", phone="1", current_location="Kathmandu",
            years_experience=2, notice_period="1-month", cv=SimpleUploadedFile("cv.pdf", PDF_BYTES), cv_original_name="cv.pdf",
        )
        self.client.force_login(self.staff)
        response = self.client.patch(reverse("dashboard:api_application_status", args=[app.pk]), json.dumps({"status": "shortlisted"}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, "shortlisted")

        response = self.client.get(reverse("dashboard:application_cv", args=[app.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        # Release the Windows file handle without firing request_finished (which would close the test DB connection)
        for closer in list(response._resource_closers):
            closer()
        from apps.core.models import AuditLog
        self.assertTrue(AuditLog.objects.filter(action="opened CV", object_id=str(app.pk)).exists())
        app.cv.delete()

    def test_estimator_config_is_editable(self):
        self.client.force_login(self.staff)
        from apps.dashboard.forms import EstimatorConfigForm
        from apps.estimator.models import EstimatorConfig
        form = EstimatorConfigForm(instance=EstimatorConfig.load())
        data = {}
        for name, field in form.fields.items():
            value = form.initial.get(name)
            data[name] = json.dumps(value) if isinstance(value, dict) else value
        data["blended_hourly_rate_npr"] = "2500"
        response = self.client.post(reverse("dashboard:estimator_config"), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(EstimatorConfig.load().blended_hourly_rate_npr), 2500)

    def test_login_rate_limited(self):
        url = reverse("dashboard:login")
        for _ in range(5):
            self.client.post(url, {"username": "hq-staff", "password": "wrong"})
        response = self.client.post(url, {"username": "hq-staff", "password": "a-strong-passphrase-2026"})
        self.assertEqual(response.status_code, 429)
