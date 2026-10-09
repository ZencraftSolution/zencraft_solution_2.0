"""End-to-end journeys in a real browser.

Each test walks a path a visitor or a member of staff actually takes, and fails on a JavaScript
error as well as on a wrong outcome. Run them with `pytest -m e2e`, or skip them with
`pytest -m "not e2e"` when you only want the fast suite.
"""

import re

import pytest
from django.urls import reverse

pytestmark = [pytest.mark.e2e, pytest.mark.django_db]


def goto(page, site, path, console_errors=None):
    page.goto(f"{site}{path}", wait_until="load")
    page.wait_for_timeout(300)
    if console_errors is not None:
        assert console_errors == [], f"{path} logged: {console_errors}"


# =================================================================================================
# 4.1 journeys
# =================================================================================================
class PublicPagesTests:
    def test_the_home_page_loads_without_a_single_browser_error(self, page, site, console_errors):
        goto(page, site, "/", console_errors)
        assert page.locator("h1").count() == 1
        assert page.title()

    @pytest.mark.parametrize("path", ["/services/", "/work/", pytest.param("/pricing/", marks=pytest.mark.store),
                                      "/insights/", "/careers/", "/about/", "/contact/"])
    def test_every_main_page_loads_cleanly(self, page, site, console_errors, path):
        goto(page, site, path, console_errors)
        assert page.locator("h1").is_visible()

    def test_the_404_page_is_the_real_one(self, page, site):
        response = page.goto(f"{site}/this-page-does-not-exist/")
        assert response.status == 404
        assert "does not exist" in page.inner_text("h1").lower()
        page.click("text=Go to home")
        page.wait_for_url(f"{site}/")

    def test_the_main_navigation_works(self, page, site):
        goto(page, site, "/")
        # The exact link, not any text containing "Work": the mega menu copy matches too.
        page.click("nav.nav > a.nav__link[href='/work/']")
        page.wait_for_url(re.compile(r"/work/$"))
        assert page.locator("h1").is_visible()

    def test_the_services_menu_opens_on_hover_and_leads_somewhere(self, page, site):
        """Hover is the desktop interaction. Clicking the trigger while hovering closes it again,
        which is what a toggle does, so the test does what a person with a mouse actually does."""
        goto(page, site, "/")
        page.hover("button.nav__trigger")
        first = page.locator(".mega a[href^='/services/']").first
        first.wait_for(state="visible", timeout=5000)
        href = first.get_attribute("href")
        first.click()
        page.wait_for_url(f"{site}{href}")

    def test_the_services_menu_also_opens_from_the_keyboard(self, page, site):
        """Somebody tabbing through the header has no hover, so the trigger must respond to Enter."""
        goto(page, site, "/")
        page.focus("button.nav__trigger")
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)
        assert page.get_attribute("button.nav__trigger", "aria-expanded") == "true"
        assert page.locator(".mega a[href^='/services/']").first.is_visible()


class MobileMenuTests:
    def test_it_opens_shows_the_links_and_closes(self, page, site):
        page.set_viewport_size({"width": 390, "height": 844})
        goto(page, site, "/")
        menu = page.locator("#mobile-menu")
        assert not menu.is_visible()

        page.click("[data-menu-toggle]")
        menu.wait_for(state="visible", timeout=5000)
        assert page.locator("#mobile-menu a:has-text('Careers')").is_visible()
        assert page.locator("#mobile-menu a[href^='mailto:']").is_visible()

        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        assert not menu.is_visible()

    def test_a_link_in_it_navigates(self, page, site):
        page.set_viewport_size({"width": 390, "height": 844})
        goto(page, site, "/")
        page.click("[data-menu-toggle]")
        page.locator("#mobile-menu a:has-text('Contact')").first.click()
        page.wait_for_url(re.compile(r"/contact/$"))


class ContactFormTests:
    def test_a_message_is_accepted_and_confirmed(self, page, site, console_errors):
        goto(page, site, "/contact/", console_errors)
        page.fill("#id_name", "Asmita Gurung")
        page.fill("#id_email", "asmita@example.com")
        page.fill("#id_phone", "9800000000")
        page.fill("#id_company", "Example Ltd")
        page.fill("#id_subject", "A new internal tool")
        page.fill("#id_message", "We need a tool for our dispatch team. Roughly forty users to begin with.")
        page.check("#id_consent")
        page.click("button[type=submit]")
        page.wait_for_url(re.compile(r"/contact/$"))
        assert "Thanks" in page.inner_text("body")

    def test_an_invalid_form_says_what_is_wrong_and_keeps_what_was_typed(self, page, site):
        goto(page, site, "/contact/")
        page.fill("#id_name", "Asmita Gurung")
        page.fill("#id_email", "not-an-email")
        page.click("button[type=submit]")
        page.wait_for_load_state("load")
        assert "fix the highlighted fields" in page.inner_text("body")
        assert page.input_value("#id_name") == "Asmita Gurung"


class ConsultationBookingTests:
    def test_a_booking_reaches_the_confirmation(self, page, site, console_errors):
        from datetime import date, timedelta

        goto(page, site, reverse("core:consultation"), console_errors)
        day = date.today() + timedelta(days=4)
        if day.weekday() == 5:  # the office is closed on Saturdays
            day += timedelta(days=1)
        page.fill("#id_name", "Asmita Gurung")
        page.fill("#id_email", "asmita@example.com")
        page.fill("#id_phone", "9800000000")
        page.fill("#id_company", "Example Ltd")
        page.select_option("#id_topic", "new-project")
        page.fill("#id_preferred_date", day.isoformat())
        page.select_option("#id_preferred_slot", "morning")
        page.fill("#id_message", "We would like to talk about a dispatch tool.")
        page.check("#id_consent")
        page.click("button[type=submit]")
        page.wait_for_load_state("load")
        assert "Thanks" in page.inner_text("h1")


class EstimatorTests:
    def test_the_first_steps_advance_and_show_a_range(self, page, site, console_errors):
        goto(page, site, "/estimate/", console_errors)
        # The Continue button, not the first button in the form: that is "Back", which is hidden
        # on step one, so waiting for it to become visible timed out.
        continue_button = page.locator("[data-estimator] [data-next]")
        continue_button.wait_for(state="visible", timeout=10_000)
        # Project types arrive from the config API; the tiles replace a "Loading options" note.
        page.locator("[data-types] .tile").first.wait_for(state="visible", timeout=10_000)
        progress = page.locator("[data-progress-text]")
        for step in range(1, 6):
            assert progress.inner_text() == f"Step {step} of 6"
            current = page.locator(f"[data-step='{step}']")
            # Steps 1 (project type) and 3 (platform) refuse to advance until something is chosen;
            # the rest have defaults. Choosing the first tile is the default path forward.
            if step in (1, 3):
                current.locator(".tile").first.click()
            continue_button.click()
            page.locator(f"[data-step='{step + 1}']").wait_for(state="visible")
        assert progress.inner_text() == "Step 6 of 6"
        assert console_errors == [], console_errors


@pytest.mark.store
class StoreAndCheckoutTests:
    def test_currency_switches_between_npr_and_usd(self, page, site, console_errors):
        goto(page, site, "/pricing/", console_errors)
        assert "Rs." in page.inner_text("body")
        page.click("button[data-currency='usd']")
        page.wait_for_timeout(500)
        assert page.get_attribute("html", "data-currency") == "usd"
        assert "$" in page.inner_text("body")

    def test_a_product_can_be_added_and_reaches_payment_selection(self, page, site, console_errors):
        goto(page, site, "/pricing/store/", console_errors)
        # The add-to-cart form on the first product card, not any link that happens to be under
        # /pricing/store/ (the cart itself is one of those).
        page.locator("form[action*='/cart/add/'] button[type=submit]").first.click()
        page.wait_for_load_state("load")

        goto(page, site, "/pricing/store/cart/")
        assert page.locator("a[href$='/checkout/']").count() == 1, "the cart is empty"
        page.locator("a[href$='/checkout/']").first.click()
        page.wait_for_url(re.compile(r"/checkout/"))

        page.fill("#id_customer_name", "Asmita Gurung")
        page.fill("#id_email", "asmita@example.com")
        page.fill("#id_phone", "9800000000")
        page.fill("#id_company", "Example Ltd")
        page.fill("#id_billing_address", "Tilottama Municipality-3, Rupandehi")
        page.check("#id_consent")
        page.locator("form button[type=submit]").first.click()
        page.wait_for_load_state("load")
        assert "/pay/" in page.url, page.inner_text("body")[:400]
        # The payment step offers the gateways, which is as far as a test should go: the next
        # click leaves for eSewa, Khalti or Stripe.
        assert page.locator("form[action*='/pay/'] button[type=submit]").count() >= 1


class JobApplicationTests:
    """The five-step application, both paths through it."""

    def job_path(self, site, page):
        goto(page, site, "/careers/jobs/")
        return page.locator("a[href^='/careers/jobs/']").first.get_attribute("href")

    def start(self, page, site, email):
        path = self.job_path(site, page)
        goto(page, site, f"{path}apply/")
        page.fill("#id_email", email)
        page.click("button[type=submit]")
        page.wait_for_url(re.compile(r"/apply/details/$"))

    def fill_about_you(self, page):
        page.fill("#id_full_name", "Asmita Gurung")
        page.fill("#id_phone", "9800000000")
        page.fill("#id_current_location", "Butwal")
        page.fill("#id_years_experience", "2")
        page.select_option("#id_notice_period", "1-month")

    def test_the_email_step_comes_first_and_is_then_locked(self, page, site, console_errors):
        self.start(page, site, "wizard@example.com")
        assert console_errors == [], console_errors
        assert page.input_value("#id_email") == "wizard@example.com"
        assert page.get_attribute("#id_email", "readonly") is not None

    def test_the_steps_are_marked_and_next_and_back_move_between_them(self, page, site):
        self.start(page, site, "steps@example.com")
        assert page.locator("[data-step-marker='1'].is-done").count() == 1
        assert page.locator("[data-step-marker='2'].is-current").count() == 1

        self.fill_about_you(page)
        page.click("[data-step-next]")
        page.wait_for_timeout(400)
        assert page.locator("[data-step-marker='3'].is-current").count() == 1

        page.click("[data-step-back]")
        page.wait_for_timeout(400)
        assert page.locator("[data-step-marker='2'].is-current").count() == 1

    def test_the_cv_step_refuses_to_advance_with_no_file(self, page, site):
        self.start(page, site, "nocv@example.com")
        self.fill_about_you(page)
        page.click("[data-step-next]")
        page.wait_for_timeout(400)
        page.click("[data-step-next]")
        page.wait_for_timeout(400)
        assert page.locator("[data-step-panel='3']").is_visible()
        assert "Attach your CV" in page.inner_text("[data-client-error]")

    def test_an_application_with_a_cv_goes_through(self, page, site, tmp_path):
        from apps.core.testing import PDF_BYTES

        cv = tmp_path / "asmita-cv.pdf"
        cv.write_bytes(PDF_BYTES + b"\n% a real enough pdf\n")

        self.start(page, site, "withcv@example.com")
        self.fill_about_you(page)
        page.click("[data-step-next]")
        page.wait_for_timeout(300)
        page.set_input_files("#id_cv", str(cv))
        page.click("[data-step-next]")
        page.wait_for_timeout(300)
        page.click("[data-step-next]")
        page.wait_for_timeout(300)
        page.check("#id_consent")
        page.click("[data-apply-submit]")
        page.wait_for_url(re.compile(r"/application-received/"))
        assert "Thank you" in page.inner_text("h1")

    def test_the_manual_path_goes_through_without_a_file(self, page, site):
        self.start(page, site, "manual@example.com")
        self.fill_about_you(page)
        page.click("[data-step-next]")
        page.wait_for_timeout(300)

        page.click("label.tile:has-text('Fill in my CV manually')")
        page.wait_for_timeout(400)
        page.fill("#id_headline", "Django developer with two shipped projects")
        page.fill("#id_professional_summary", "I build Django back ends and have shipped two production apps.")
        page.fill("#id_skills", "Python, Django, PostgreSQL")
        page.fill("#id_exp-0-company", "Local startup")
        page.fill("#id_exp-0-title", "Backend developer")
        page.fill("#id_exp-0-start_date", "2025-06")
        page.click("[data-step-next]")
        page.wait_for_timeout(300)
        page.click("[data-step-next]")
        page.wait_for_timeout(300)
        page.check("#id_consent")
        page.click("[data-apply-submit]")
        page.wait_for_url(re.compile(r"/application-received/"))

    def test_a_rejected_form_reopens_on_the_step_that_needs_fixing(self, page, site):
        """Submitting without consent must land back on step 5, not at the top of the form."""
        self.start(page, site, "noconsent@example.com")
        self.fill_about_you(page)
        page.click("[data-step-next]")  # to step 3
        page.wait_for_timeout(300)
        page.click("label.tile:has-text('Fill in my CV manually')")  # no file needed to move on
        page.wait_for_timeout(300)
        page.fill("#id_headline", "Django developer")
        page.fill("#id_professional_summary", "I build Django back ends.")
        page.fill("#id_skills", "Python, Django")
        page.fill("#id_exp-0-company", "Local startup")
        page.fill("#id_exp-0-title", "Developer")
        page.fill("#id_exp-0-start_date", "2025-06")
        page.click("[data-step-next]")  # to step 4
        page.wait_for_timeout(300)
        page.click("[data-step-next]")  # to step 5
        page.wait_for_timeout(300)
        page.click("[data-apply-submit]")  # without ticking consent
        page.wait_for_load_state("load")
        page.wait_for_timeout(400)
        assert page.locator("[data-step-panel='5']").is_visible()
        assert page.locator("[data-step-marker='5'].is-current").count() == 1


class StaffDashboardTests:
    def sign_in(self, page, site, username, password):
        from django.conf import settings

        goto(page, site, f"/{settings.DASHBOARD_PATH}login/")
        page.fill("#id_username", username)
        page.fill("#id_password", password)
        page.click("button[type=submit]")
        page.wait_for_load_state("load")

    @pytest.fixture
    def staff(self, site):
        """Depends on site, not db: the account has to be committed for the server thread,
        which runs in a different thread, to be able to authenticate it."""
        from apps.core.testing import PASSWORD, make_staff

        user = make_staff()
        return user.get_username(), PASSWORD

    def test_a_member_of_staff_can_sign_in_and_see_the_overview(self, page, site, staff, console_errors):
        self.sign_in(page, site, *staff)
        assert "Overview" in page.inner_text("body")
        assert console_errors == [], console_errors

    def test_the_wrong_password_five_times_locks_the_address_out(self, page, site, staff):
        from django.conf import settings
        from django.core.cache import cache

        cache.clear()
        username, _ = staff
        for _ in range(5):
            self.sign_in(page, site, username, "definitely-the-wrong-password")
        goto(page, site, f"/{settings.DASHBOARD_PATH}login/")
        page.fill("#id_username", username)
        page.fill("#id_password", "definitely-the-wrong-password")
        page.click("button[type=submit]")
        page.wait_for_load_state("load")
        assert "Too many failed attempts" in page.inner_text("body")
        cache.clear()

    def test_a_case_study_can_be_created_from_the_dashboard(self, page, site, staff):
        from django.conf import settings

        self.sign_in(page, site, *staff)
        goto(page, site, f"/{settings.DASHBOARD_PATH}manage/case-studies/new/")
        page.fill("#id_title", "A browser test case study")
        page.fill("#id_slug", "browser-test-case-study")
        page.fill("#id_client_name", "Example Ltd")
        page.fill("#id_summary", "Written by the end-to-end test.")
        page.fill("#id_challenge", "There was a problem.")
        page.fill("#id_solution", "We solved it.")
        page.fill("#id_cover_image_url", "https://example.com/cover.jpg")
        page.fill("#id_duration", "4 months")
        page.fill("#id_team_size", "5")
        page.fill("#id_year", "2026")
        page.fill("#id_order", "0")
        page.select_option("#id_industry", index=1)
        page.click("form.panel button[type=submit]:has-text('Save')")
        page.wait_for_load_state("load")
        assert "browser test case study" in page.inner_text("body").lower()

    def test_a_team_member_can_be_created_with_a_photo(self, page, site, staff, tmp_path):
        from django.conf import settings

        from apps.core.testing import image_bytes

        photo = tmp_path / "member.png"
        photo.write_bytes(image_bytes())

        self.sign_in(page, site, *staff)
        goto(page, site, f"/{settings.DASHBOARD_PATH}manage/team/new/")
        page.fill("#id_name", "Browser Test Person")
        page.fill("#id_role", "Engineer")
        page.set_input_files("#id_photo", str(photo))
        page.click("form.panel button[type=submit]:has-text('Save')")
        page.wait_for_load_state("load")
        assert "Browser Test Person" in page.inner_text("body")
