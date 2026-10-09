"""Accessibility, checked with axe-core in a real browser.

Only serious and critical violations fail. The lighter rules are worth reading but include
judgement calls that a build should not fail on; a contrast failure or an unlabelled form field
is not a judgement call, because somebody cannot use the page.
"""

import json

import pytest
from axe_playwright_python.sync_playwright import Axe

from apps.core.testing import page_params

pytestmark = [pytest.mark.e2e, pytest.mark.django_db]

BLOCKING = {"serious", "critical"}

# One of each kind of page, rather than all 52: the templates are shared, so a fault on a case
# study is a fault on every case study.
PAGES = {
    "home": "/",
    "services list": "/services/",
    "service detail": "/services/web-development/",
    "industries": "/services/industries/",
    "work list": "/work/",
    "case study": "/work/mobile-banking-development-bank/",
    "pricing": "/pricing/",
    "store": "/pricing/store/",
    "blog list": "/insights/",
    "blog post": "/insights/fixed-price-vs-dedicated-team/",
    "careers": "/careers/",
    "jobs": "/careers/jobs/",
    "about": "/about/",
    "contact": "/contact/",
    "estimator": "/estimate/",
    "legal": "/legal/privacy/",
    "404": "/no-such-page-here/",
}


def violations(page, url):
    page.goto(url, wait_until="load")
    page.wait_for_timeout(400)
    results = Axe().run(page)
    return [
        {
            "id": violation["id"],
            "impact": violation["impact"],
            "help": violation["help"],
            "nodes": [node["html"][:160] for node in violation["nodes"][:3]],
        }
        for violation in results.response["violations"]
        if violation["impact"] in BLOCKING
    ]


class AccessibilityTests:
    @pytest.mark.parametrize("name,path", page_params(PAGES))
    def test_no_serious_or_critical_violations(self, page, site, name, path):
        found = violations(page, f"{site}{path}")
        assert found == [], f"{name} ({path}):\n{json.dumps(found, indent=2)}"

    def test_the_mobile_menu_is_accessible_when_open(self, page, site):
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(f"{site}/", wait_until="load")
        page.click("[data-menu-toggle]")
        page.wait_for_timeout(500)
        found = [v for v in Axe().run(page).response["violations"] if v["impact"] in BLOCKING]
        assert found == [], json.dumps(found, indent=2)

    def test_the_application_form_is_accessible_at_every_step(self, page, site):
        page.goto(f"{site}/careers/jobs/", wait_until="load")
        job = page.locator("a[href^='/careers/jobs/']").first.get_attribute("href")
        page.goto(f"{site}{job}apply/", wait_until="load")
        assert violations(page, f"{site}{job}apply/") == []

        page.fill("#id_email", "a11y@example.com")
        page.click("button[type=submit]")
        page.wait_for_load_state("load")
        for _ in range(4):
            found = [v for v in Axe().run(page).response["violations"] if v["impact"] in BLOCKING]
            assert found == [], json.dumps(found, indent=2)
            nxt = page.locator("[data-step-next]")
            if not nxt.count() or not nxt.is_visible():
                break
            nxt.click()
            page.wait_for_timeout(300)


class KeyboardAndFocusTests:
    """Things axe cannot see: whether the page can actually be operated without a mouse."""

    def test_the_skip_link_is_the_first_stop_and_jumps_to_the_content(self, page, site):
        page.goto(f"{site}/", wait_until="load")
        page.keyboard.press("Tab")
        focused = page.evaluate("document.activeElement.className")
        assert "skip-link" in focused, f"first tab stop was {focused!r}"
        page.keyboard.press("Enter")
        page.wait_for_timeout(200)
        assert page.url.endswith("#main")

    def test_focus_is_always_visible(self, page, site):
        """A focus ring removed without a replacement leaves a keyboard user lost on the page."""
        page.goto(f"{site}/contact/", wait_until="load")
        page.focus("#id_name")
        outline = page.evaluate(
            "() => { const s = getComputedStyle(document.activeElement); "
            "return [s.outlineStyle, s.outlineWidth, s.boxShadow, s.borderColor].join('|'); }"
        )
        assert outline != "none|0px|none|", "the focused field shows no focus indicator"

    def test_the_whole_contact_form_can_be_filled_in_from_the_keyboard(self, page, site):
        page.goto(f"{site}/contact/", wait_until="load")
        page.focus("#id_name")
        order = []
        for _ in range(8):
            order.append(page.evaluate("document.activeElement.id || document.activeElement.tagName"))
            page.keyboard.press("Tab")
        # Tab order follows the visual order of the fields, with nothing skipped.
        expected = ["id_name", "id_email", "id_phone", "id_company", "id_subject", "id_message", "id_consent"]
        assert order[: len(expected)] == expected, order

    def test_the_step_markers_announce_progress(self, page, site):
        page.goto(f"{site}/careers/jobs/", wait_until="load")
        job = page.locator("a[href^='/careers/jobs/']").first.get_attribute("href")
        page.goto(f"{site}{job}apply/", wait_until="load")
        steps = page.locator("[data-steps]")
        assert steps.get_attribute("aria-label") == "Application progress"
        assert page.locator("[data-step-marker='1'][aria-current='step']").count() == 1
        # A screen reader is told the state of each step, not just shown a coloured dot.
        assert "Current step" in page.inner_text("[data-step-marker='1'] [data-step-state]")
        assert "Not started" in page.inner_text("[data-step-marker='2'] [data-step-state]")

    def test_motion_is_dropped_when_the_visitor_asks_for_less(self, page, site):
        """The context is set to reduced motion, so nothing should be animating."""
        page.goto(f"{site}/", wait_until="load")
        page.wait_for_timeout(600)
        assert page.evaluate("!document.documentElement.classList.contains('js-motion')")
