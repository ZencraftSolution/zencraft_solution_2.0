import io
from datetime import timedelta

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.careers.models import JobApplication
from apps.core.testing import (
    NOOP_SCAN,
    PDF_BYTES,
    docx_upload,
    make_application,
    make_department,
    make_job,
    pdf_upload,
)

FORMSET_MGMT = {
    "edu-TOTAL_FORMS": "1", "edu-INITIAL_FORMS": "0", "edu-MIN_NUM_FORMS": "0", "edu-MAX_NUM_FORMS": "6",
    "exp-TOTAL_FORMS": "1", "exp-INITIAL_FORMS": "0", "exp-MIN_NUM_FORMS": "0", "exp-MAX_NUM_FORMS": "8",
    "prj-TOTAL_FORMS": "1", "prj-INITIAL_FORMS": "0", "prj-MIN_NUM_FORMS": "0", "prj-MAX_NUM_FORMS": "6",
}


def base_data(mode="cv", email="asmita@example.com", **extra):
    data = {
        "application_mode": mode, "full_name": "Asmita Gurung", "email": email, "phone": "9800000000",
        "current_location": "Butwal", "years_experience": "1.5", "notice_period": "1-month", "source": "website",
        "consent": "on", **FORMSET_MGMT,
    }
    data.update(extra)
    return data


MANUAL_PROFILE = {"headline": "Final-year BSc CSIT student", "professional_summary": "I build Django apps.", "skills": "Python, Django, React"}


class CareersViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.job = make_job()

    def test_landing_groups_open_roles_by_department(self):
        make_job(slug="closed-role", title="Closed Role", closing_date=timezone.localdate() - timedelta(days=1))
        make_job(slug="qa-role", title="QA Role", department=make_department("qa", "Quality assurance"))
        response = self.client.get(reverse("careers:landing"))
        self.assertContains(response, "Backend Developer")
        self.assertContains(response, "Quality assurance")
        self.assertNotContains(response, "Closed Role")
        self.assertEqual(response.context["job_count"], 2)

    def test_landing_empty_state(self):
        self.job.is_active = False
        self.job.save()
        self.assertContains(self.client.get(reverse("careers:landing")), "No open roles right now")

    def test_job_list_filters(self):
        make_job(slug="intern", title="Intern Role", experience_level="intern", employment_type="internship", work_mode="onsite",
                 department=make_department("design", "Design"))
        url = reverse("careers:jobs")
        cases = {
            "?level=intern": ("Intern Role", "Backend Developer"),
            "?type=full-time": ("Backend Developer", "Intern Role"),
            "?mode=onsite": ("Intern Role", "Backend Developer"),
            "?department=engineering": ("Backend Developer", "Intern Role"),
        }
        for query, (shown, hidden) in cases.items():
            with self.subTest(query=query):
                response = self.client.get(url + query)
                self.assertContains(response, shown)
                self.assertNotContains(response, hidden)
        self.assertContains(self.client.get(url + "?level=lead"), "No roles match these filters")

    def test_job_detail_json_ld_and_inactive_404(self):
        response = self.client.get(self.job.get_absolute_url())
        self.assertContains(response, '"@type": "JobPosting"')
        self.assertContains(response, "Apply for this role")
        self.job.is_active = False
        self.job.save()
        self.assertEqual(self.client.get(self.job.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(reverse("careers:apply", args=[self.job.slug])).status_code, 404)

    def test_closed_job_apply_returns_410(self):
        self.job.closing_date = timezone.localdate() - timedelta(days=1)
        self.job.save()
        self.assertEqual(self.client.get(reverse("careers:apply_details", args=[self.job.slug])).status_code, 410)
        response = self.client.get(reverse("careers:apply", args=[self.job.slug]))
        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "have closed", status_code=410)

    def test_applied_page_with_and_without_session(self):
        self.assertContains(self.client.get(reverse("careers:applied")), "Thank you for applying")

    def test_model_helpers(self):
        self.assertTrue(self.job.is_open)
        self.assertEqual(self.job.responsibility_list, ["Build", "Review"])
        self.assertEqual(self.job.requirement_list, ["Python", "Django"])
        self.assertEqual(self.job.nice_list, ["Docker"])
        app = make_application(self.job, skills="Python, , Django")
        self.assertEqual(app.skill_list, ["Python", "Django"])
        self.assertFalse(app.cv_is_pdf)


@override_settings(UPLOAD_SCAN_HOOK=NOOP_SCAN)
class ApplicationFormTests(TestCase):
    def setUp(self):
        cache.clear()
        self.job = make_job()
        self.email_url = reverse("careers:apply", args=[self.job.slug])
        self.url = reverse("careers:apply_details", args=[self.job.slug])

    def tearDown(self):
        for app in JobApplication.objects.exclude(cv=""):
            app.cv.delete(save=False)

    def start(self, email="asmita@example.com", job=None):
        """Step 1: confirm the email, which is what unlocks the rest of the form."""
        url = reverse("careers:apply", args=[(job or self.job).slug])
        return self.client.post(url, {"email": email})

    def post(self, data, job=None):
        target = reverse("careers:apply_details", args=[job.slug]) if job else self.url
        if not self.client.session.get("apply_email", {}).get((job or self.job).slug):
            self.start(data.get("email", "asmita@example.com"), job=job)
        return self.client.post(target, data)

    def test_email_step_comes_first_and_the_rest_is_locked_until_it_is_given(self):
        first = self.client.get(self.email_url)
        self.assertContains(first, "Step 1 of 5")
        self.assertNotContains(first, "edu-TOTAL_FORMS")  # nothing else is asked for yet
        self.assertRedirects(self.client.get(self.url), self.email_url)

        self.assertRedirects(self.start(), self.url)
        self.assertEqual(self.client.session["apply_email"][self.job.slug], "asmita@example.com")

    def test_form_renders_both_paths_after_the_email_step(self):
        self.start()
        response = self.client.get(self.url)
        self.assertContains(response, "Upload my CV")
        self.assertContains(response, "Fill in my CV manually")
        self.assertContains(response, "edu-TOTAL_FORMS")

    def test_every_step_is_marked_through_to_the_confirmation(self):
        self.assertContains(self.client.get(self.email_url), 'data-step-marker="5"')
        self.start()
        details = self.client.get(self.url).content.decode()
        self.assertIn('class="step is-done" data-step-marker="1"', details)  # the email step is behind them
        self.assertIn('class="step is-current" data-step-marker="2"', details)
        for step in ["2", "3", "4", "5"]:
            self.assertIn('data-step-panel="%s"' % step, details)
        self.post(base_data(cv=pdf_upload()))
        done = self.client.get(reverse("careers:applied")).content.decode()
        self.assertEqual(done.count("step is-done"), 5)  # all five, once the application is in

    def test_email_confirmed_in_step_one_is_used_even_if_the_field_is_edited(self):
        self.start("asmita@example.com")
        self.client.post(self.url, base_data(email="someone.else@example.com", cv=pdf_upload()))
        self.assertEqual(JobApplication.objects.get().email, "asmita@example.com")

    def test_cv_upload_docx_accepted_and_stored_privately(self):
        mail.outbox.clear()
        response = self.post(base_data(cv=docx_upload("Asmita CV.docx")))
        self.assertRedirects(response, reverse("careers:applied"))
        app = JobApplication.objects.get()
        self.assertTrue(app.cv.name.startswith("cvs/"))
        self.assertNotIn("Asmita", app.cv.name)
        self.assertEqual(app.cv_original_name, "Asmita CV.docx")
        self.assertIsNotNone(app.consent_at)
        self.assertTrue(str(app.cv.path).startswith(str(settings.PRIVATE_MEDIA_ROOT)))
        with self.assertRaises(ValueError):
            app.cv.url  # private files have no public URL
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ["asmita@example.com"])
        self.assertContains(self.client.get(reverse("careers:applied")), app.reference)

    def test_cv_upload_pdf_accepted(self):
        self.assertRedirects(self.post(base_data(cv=pdf_upload())), reverse("careers:applied"))
        self.assertTrue(JobApplication.objects.get().cv_is_pdf)

    def assert_rejected(self, response, message):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, message)
        self.assertFalse(JobApplication.objects.exists())

    def test_cv_required_in_cv_mode(self):
        self.assert_rejected(self.post(base_data()), "Please attach your CV")

    def test_fake_pdf_rejected(self):
        self.assert_rejected(self.post(base_data(cv=pdf_upload(content=b"MZ\x90\x00 really an exe"))), "does not look like a valid PDF")

    def test_pdf_content_with_docx_extension_rejected(self):
        self.assert_rejected(self.post(base_data(cv=pdf_upload(name="cv.docx"))), "does not look like a valid PDF or DOCX")

    def test_zip_without_word_document_rejected(self):
        self.assert_rejected(self.post(base_data(cv=docx_upload(valid=False))), "does not look like a valid PDF or DOCX")

    def test_disallowed_extension_rejected(self):
        self.assert_rejected(self.post(base_data(cv=pdf_upload(name="cv.txt"))), "Please upload a PDF or DOCX file")

    @override_settings(UPLOAD_MAX_BYTES=1024)
    def test_oversized_file_rejected(self):
        big = pdf_upload(content=PDF_BYTES + b"0" * 2048)
        self.assert_rejected(self.post(base_data(cv=big)), "File is too large")

    def test_consent_and_honeypot_required(self):
        self.assert_rejected(self.post(base_data(cv=pdf_upload(), consent="")), "This field is required")
        self.assert_rejected(self.post(base_data(cv=pdf_upload(), website="http://spam")), "Please fix the highlighted fields")

    def test_manual_mode_with_full_history(self):
        data = base_data("manual", **MANUAL_PROFILE, **{
            "edu-0-institution": "Tribhuvan University", "edu-0-degree": "BSc CSIT", "edu-0-end_year": "2026",
            "exp-0-company": "Local startup", "exp-0-title": "Intern", "exp-0-start_date": "2025-06",
            "prj-0-name": "Bus ticket app", "prj-0-tech_used": "Flutter",
        })
        self.assertRedirects(self.post(data), reverse("careers:applied"))
        app = JobApplication.objects.get()
        self.assertEqual(app.application_mode, "manual")
        self.assertFalse(app.cv)
        self.assertEqual((app.education.count(), app.experience.count(), app.projects.count()), (1, 1, 1))

    def test_manual_mode_experience_only_is_enough(self):
        data = base_data("manual", **MANUAL_PROFILE, **{"exp-0-company": "Shop", "exp-0-title": "Cashier", "exp-0-start_date": "2024-01"})
        self.assertRedirects(self.post(data), reverse("careers:applied"))
        self.assertEqual(JobApplication.objects.get().education.count(), 0)

    def test_manual_mode_ignores_uploaded_cv(self):
        data = base_data("manual", cv=pdf_upload(), **MANUAL_PROFILE, **{"edu-0-institution": "TU", "edu-0-degree": "BBS"})
        self.assertRedirects(self.post(data), reverse("careers:applied"))
        self.assertFalse(JobApplication.objects.get().cv)

    def test_manual_mode_requires_profile_fields(self):
        self.assert_rejected(self.post(base_data("manual", **{"edu-0-institution": "TU", "edu-0-degree": "BBS"})),
                             "This field is required when filling in your CV manually")

    def test_manual_mode_requires_education_or_experience(self):
        self.assert_rejected(self.post(base_data("manual", **MANUAL_PROFILE, **{"prj-0-name": "Only a project"})),
                             "Add at least one education or work experience entry")

    def test_manual_mode_invalid_formset_row_rejected(self):
        # Education row started but missing the required degree.
        self.assert_rejected(self.post(base_data("manual", **MANUAL_PROFILE, **{"edu-0-institution": "TU"})), "Please fix the highlighted fields")

    def test_additional_formset_rows_are_saved(self):
        data = base_data("manual", **MANUAL_PROFILE, **{
            "exp-TOTAL_FORMS": "2",
            "exp-0-company": "A", "exp-0-title": "Dev", "exp-0-start_date": "2023-01",
            "exp-1-company": "B", "exp-1-title": "Dev", "exp-1-start_date": "2024-01", "exp-1-is_current": "on",
        })
        self.assertRedirects(self.post(data), reverse("careers:applied"))
        self.assertEqual(JobApplication.objects.get().experience.filter(is_current=True).count(), 1)

    def test_second_application_for_the_same_role_is_stopped_at_the_email_step(self):
        self.assertRedirects(self.post(base_data(cv=pdf_upload())), reverse("careers:applied"))
        response = self.client.post(self.email_url, {"email": "ASMITA@example.com"})  # case does not matter
        self.assertContains(response, "already been used to apply for this role")
        self.assertNotIn(self.job.slug, self.client.session.get("apply_email", {}))
        self.assertEqual(JobApplication.objects.count(), 1)

    def test_duplicate_is_still_refused_at_submit_and_sends_the_applicant_back(self):
        self.start()  # email confirmed while no application existed yet
        make_application(self.job, email="asmita@example.com", reference="ZA-DUPL")
        response = self.client.post(self.url, base_data(cv=pdf_upload()))
        self.assertRedirects(response, self.email_url, fetch_redirect_response=False)
        self.assertContains(self.client.get(self.email_url), "already been used to apply for this role")
        self.assertEqual(JobApplication.objects.count(), 1)

    def test_time_does_not_reopen_a_role_but_other_roles_stay_open(self):
        self.assertRedirects(self.post(base_data(cv=pdf_upload())), reverse("careers:applied"))
        other = make_job(slug="frontend", title="Frontend")
        self.assertRedirects(self.post(base_data(cv=pdf_upload()), job=other), reverse("careers:applied"))
        JobApplication.objects.filter(job=self.job).update(created_at=timezone.now() - timedelta(days=400))
        self.assertContains(self.client.post(self.email_url, {"email": "asmita@example.com"}),
                            "already been used to apply for this role")
        self.assertEqual(JobApplication.objects.filter(job=self.job).count(), 1)


@override_settings(CV_RETENTION_DAYS=180)
class PurgeApplicationsTests(TestCase):
    def test_purges_only_old_rejected_applications(self):
        job = make_job()
        old_rejected = make_application(job, email="old@example.com", status="rejected", cv=pdf_upload(), cv_original_name="cv.pdf",
                                        skills="Python", cover_letter="Hi")
        old_rejected.notes.create(body="Not a fit")
        old_rejected.education.create(institution="TU", degree="BSc")
        recent_rejected = make_application(job, email="new@example.com", status="rejected")
        old_hired = make_application(job, email="hired@example.com", status="hired")
        JobApplication.objects.filter(pk__in=[old_rejected.pk, old_hired.pk]).update(updated_at=timezone.now() - timedelta(days=200))
        cv_path = old_rejected.cv.path

        out = io.StringIO()
        call_command("purge_applications", "--dry-run", stdout=out)
        self.assertIn("1 applications would be purged", out.getvalue())
        self.assertIsNone(JobApplication.objects.get(pk=old_rejected.pk).purged_at)

        call_command("purge_applications", stdout=io.StringIO())
        old_rejected.refresh_from_db()
        self.assertIsNotNone(old_rejected.purged_at)
        self.assertEqual(old_rejected.full_name, "Purged applicant")
        self.assertFalse(old_rejected.cv)
        self.assertEqual((old_rejected.skills, old_rejected.cover_letter, old_rejected.email), ("", "", f"purged-{old_rejected.pk}@invalid.local"))
        self.assertFalse(old_rejected.education.exists() or old_rejected.notes.exists())
        import os
        self.assertFalse(os.path.exists(cv_path))
        recent_rejected.refresh_from_db()
        old_hired.refresh_from_db()
        self.assertIsNone(recent_rejected.purged_at)
        self.assertIsNone(old_hired.purged_at)
