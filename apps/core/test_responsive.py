"""Layout at the three widths that matter, and the one failure that ruins a phone: side-scroll.

A page that scrolls sideways on a phone is the most common responsive fault and the easiest to
miss on a desktop, because one over-wide element anywhere on the page does it.
"""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db]

WIDTHS = {"phone": 375, "tablet": 768, "desktop": 1440}

PAGES = {
    "home": "/",
    "services": "/services/",
    "service": "/services/web-development/",
    "work": "/work/",
    "case-study": "/work/mobile-banking-development-bank/",
    "pricing": "/pricing/",
    "store": "/pricing/store/",
    "insights": "/insights/",
    "post": "/insights/fixed-price-vs-dedicated-team/",
    "careers": "/careers/",
    "about": "/about/",
    "contact": "/contact/",
}


def overflow(page):
    """How many pixels the document is wider than the window, and what is sticking out."""
    return page.evaluate(
        """() => {
            const doc = document.documentElement;
            const over = doc.scrollWidth - doc.clientWidth;
            if (over <= 1) return {over: 0, culprits: []};
            const culprits = [];
            for (const el of document.querySelectorAll('body *')) {
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || getComputedStyle(el).position === 'fixed') continue;
                if (rect.right > doc.clientWidth + 1 || rect.left < -1) {
                    culprits.push(el.tagName.toLowerCase() + '.' + (el.className || '').toString().slice(0, 60)
                                  + ' right=' + Math.round(rect.right));
                }
            }
            return {over, culprits: culprits.slice(0, 5)};
        }"""
    )


class NoHorizontalScrollTests:
    @pytest.mark.parametrize("name,path", PAGES.items(), ids=list(PAGES))
    def test_the_page_does_not_scroll_sideways_on_a_phone(self, page, site, name, path):
        page.set_viewport_size({"width": WIDTHS["phone"], "height": 812})
        response = page.goto(f"{site}{path}", wait_until="load")
        # Without this, a page whose content failed to seed would 404, lay out narrowly and
        # pass. The test would be measuring the error page.
        assert response.status == 200, f"{path} returned {response.status}"
        page.wait_for_timeout(400)
        result = overflow(page)
        assert result["over"] == 0, f"{path} is {result['over']}px too wide: {result['culprits']}"

    @pytest.mark.parametrize("width", [WIDTHS["tablet"], WIDTHS["desktop"]], ids=["tablet", "desktop"])
    def test_the_home_page_fits_at_the_other_widths(self, page, site, width):
        page.set_viewport_size({"width": width, "height": 900})
        page.goto(f"{site}/", wait_until="load")
        page.wait_for_timeout(400)
        result = overflow(page)
        assert result["over"] == 0, f"{width}px: {result['over']}px too wide: {result['culprits']}"

    def test_the_mobile_menu_does_not_overflow_when_open(self, page, site):
        page.set_viewport_size({"width": WIDTHS["phone"], "height": 812})
        page.goto(f"{site}/", wait_until="load")
        page.click("[data-menu-toggle]")
        page.wait_for_timeout(500)
        result = overflow(page)
        assert result["over"] == 0, f"the open menu is {result['over']}px too wide: {result['culprits']}"


class LayoutShapeTests:
    def test_the_desktop_navigation_stays_on_one_row(self, page, site):
        """Seven items plus the actions once overflowed at 1140px, which wrapped the header."""
        for width in [1140, 1280, 1440, 1920]:
            page.set_viewport_size({"width": width, "height": 900})
            page.goto(f"{site}/", wait_until="load")
            rows = page.evaluate(
                """() => {
                    const items = [...document.querySelectorAll('.site-header__inner > *')];
                    return new Set(items.map(el => Math.round(el.getBoundingClientRect().top))).size;
                }"""
            )
            assert rows == 1, f"the header wrapped onto {rows} rows at {width}px"

    def test_the_mobile_menu_replaces_the_navigation_below_the_breakpoint(self, page, site):
        page.set_viewport_size({"width": 1024, "height": 800})
        page.goto(f"{site}/", wait_until="load")
        assert page.locator("[data-menu-toggle]").is_visible()

        page.set_viewport_size({"width": 1440, "height": 900})
        page.wait_for_timeout(300)
        assert not page.locator("[data-menu-toggle]").is_visible()
        assert page.locator("nav.nav").is_visible()

    def test_the_application_steps_stack_on_a_phone(self, page, site):
        page.set_viewport_size({"width": WIDTHS["phone"], "height": 812})
        page.goto(f"{site}/careers/jobs/", wait_until="load")
        job = page.locator("a[href^='/careers/jobs/']").first.get_attribute("href")
        page.goto(f"{site}{job}apply/", wait_until="load")
        tops = page.evaluate(
            "() => [...document.querySelectorAll('[data-step-marker]')]"
            ".map(el => Math.round(el.getBoundingClientRect().top))"
        )
        assert len(set(tops)) == len(tops), "the five steps are side by side on a phone"


@pytest.mark.parametrize("name,path", [("home", "/"), ("service", "/services/web-development/"),
                                       ("case-study", "/work/mobile-banking-development-bank/"),
                                       ("contact", "/contact/")], ids=["home", "service", "case-study", "contact"])
class ScreenshotTests:
    """Writes a screenshot per page per width, for a human to look at after a change.

    Not compared against a baseline: a pixel comparison on a site whose content is edited daily
    fails for reasons that have nothing to do with the layout. The value is in the artefacts CI
    uploads, which make a layout break obvious at a glance.
    """

    @pytest.mark.parametrize("width", WIDTHS.values(), ids=list(WIDTHS))
    def test_screenshot(self, page, site, name, path, width, tmp_path_factory):
        out = tmp_path_factory.getbasetemp().parent / "screenshots"
        out.mkdir(parents=True, exist_ok=True)
        page.set_viewport_size({"width": width, "height": 900})
        page.goto(f"{site}{path}", wait_until="load")
        page.wait_for_timeout(500)
        page.screenshot(path=str(out / f"{name}-{width}.png"), full_page=True)
        assert (out / f"{name}-{width}.png").exists()
