"""Crawls every URL in the sitemap and holds each page to the same standard.

One test class, one page type at a time, so a failure names the page and the rule it broke
rather than "SEO is wrong somewhere". The seed content is loaded once, because these checks are
only meaningful against the pages a visitor would actually land on.
"""

import json
import re

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core import seo
from apps.core.sitemaps import SITEMAPS
from apps.core.testing import make_job


def open_role():
    """A live, salaried, hybrid job. The seed ships no vacancies, so tests that need one make it."""
    from datetime import timedelta
    from decimal import Decimal

    from django.utils import timezone

    return make_job(salary_min_npr=Decimal("110000"), salary_max_npr=Decimal("170000"), show_salary=True,
                    closing_date=timezone.localdate() + timedelta(days=30))

SITE = "https://zencraftsolution.com"


def sitemap_paths():
    """Every path the sitemap offers search engines, which is the set that has to be right."""
    paths = []
    for sitemap_class in SITEMAPS.values():
        sitemap = sitemap_class()
        for item in sitemap.items():
            paths.append(sitemap.location(item) if hasattr(sitemap, "location") else item.get_absolute_url())
    return sorted(set(paths))


@override_settings(SITE_URL=SITE)
class SitemapCrawlTests(TestCase):
    """The rules every indexable page has to satisfy."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_zencraft", verbosity=0)

    def setUp(self):
        self.pages = {}
        for path in sitemap_paths():
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, f"{path} is in the sitemap but returns {response.status_code}")
            self.pages[path] = seo.parse(response.content.decode())

    def test_the_sitemap_is_not_empty(self):
        self.assertGreater(len(self.pages), 20, "the crawl is not actually covering the site")

    def test_every_page_has_exactly_one_h1(self):
        for path, page in self.pages.items():
            h1s = [text for level, text in page.headings if level == 1]
            with self.subTest(path=path):
                self.assertEqual(len(h1s), 1, f"{path} has {len(h1s)} h1 headings: {h1s}")
                self.assertTrue(h1s[0].strip(), f"{path} has an empty h1")

    def test_no_page_skips_a_heading_level(self):
        for path, page in self.pages.items():
            with self.subTest(path=path):
                gaps = page.heading_gaps()
                self.assertEqual(gaps, [], f"{path} jumps from h{gaps[0][0]} to h{gaps[0][1]} at {gaps[0][2]!r}" if gaps else "")

    def test_titles_are_within_the_length_a_search_result_shows(self):
        for path, page in self.pages.items():
            with self.subTest(path=path):
                length = len(page.title)
                self.assertGreaterEqual(length, seo.TITLE_MIN, f"{path}: title is only {length} characters: {page.title!r}")
                self.assertLessEqual(length, seo.TITLE_MAX, f"{path}: title is {length} characters: {page.title!r}")

    def test_descriptions_are_within_the_length_a_search_result_shows(self):
        for path, page in self.pages.items():
            with self.subTest(path=path):
                length = len(page.description)
                self.assertGreaterEqual(
                    length, seo.DESCRIPTION_MIN, f"{path}: description is only {length} characters: {page.description!r}"
                )
                self.assertLessEqual(
                    length, seo.DESCRIPTION_MAX, f"{path}: description is {length} characters: {page.description!r}"
                )

    def test_every_title_is_unique(self):
        seen = {}
        for path, page in self.pages.items():
            seen.setdefault(page.title, []).append(path)
        duplicates = {title: paths for title, paths in seen.items() if len(paths) > 1}
        self.assertEqual(duplicates, {}, f"pages sharing a title: {duplicates}")

    def test_every_description_is_unique(self):
        seen = {}
        for path, page in self.pages.items():
            seen.setdefault(page.description, []).append(path)
        duplicates = {description: paths for description, paths in seen.items() if len(paths) > 1}
        self.assertEqual(duplicates, {}, f"pages sharing a description: {duplicates}")

    def test_every_image_has_alt_text_and_its_own_dimensions(self):
        """Missing dimensions are what makes a page jump about as it loads, which Google measures."""
        for path, page in self.pages.items():
            for image in page.images:
                src = image.get("src", "")[:80]
                with self.subTest(path=path, src=src):
                    self.assertIn("alt", image, f"{path}: <img src={src}> has no alt attribute")
                    self.assertIn("width", image, f"{path}: <img src={src}> has no width")
                    self.assertIn("height", image, f"{path}: <img src={src}> has no height")

    def test_canonical_is_present_and_absolute(self):
        for path, page in self.pages.items():
            with self.subTest(path=path):
                self.assertTrue(page.canonical, f"{path} has no canonical link")
                self.assertTrue(page.canonical.startswith(f"{SITE}/"), f"{path}: canonical is {page.canonical!r}")
                self.assertEqual(page.canonical, f"{SITE}{path}")

    def test_the_page_language_is_declared(self):
        for path, page in self.pages.items():
            with self.subTest(path=path):
                self.assertEqual(page.html_lang, "en")

    def test_indexable_pages_are_not_marked_noindex(self):
        for path, page in self.pages.items():
            with self.subTest(path=path):
                self.assertNotIn("noindex", page.robots, f"{path} is in the sitemap but asks not to be indexed")

    def test_every_structured_data_block_is_valid_json_with_a_type(self):
        for path, page in self.pages.items():
            for block in page.json_ld:
                with self.subTest(path=path):
                    data = json.loads(block)
                    self.assertEqual(data.get("@context"), "https://schema.org", f"{path}: missing @context")
                    self.assertTrue(data.get("@type"), f"{path}: structured data with no @type")


@override_settings(SITE_URL=SITE)
class CanonicalUrlTests(TestCase):
    def test_tracking_parameters_are_dropped(self):
        response = self.client.get("/work/?utm_source=newsletter&utm_campaign=october&fbclid=abc")
        page = seo.parse(response.content.decode())
        self.assertEqual(page.canonical, f"{SITE}/work/")

    def test_parameters_that_change_the_page_are_kept(self):
        page = seo.parse(self.client.get("/work/?industry=healthcare").content.decode())
        self.assertEqual(page.canonical, f"{SITE}/work/?industry=healthcare")

    def test_a_tracked_link_to_a_filtered_page_keeps_only_the_filter(self):
        page = seo.parse(self.client.get("/work/?industry=healthcare&utm_source=x&ref=y").content.decode())
        self.assertEqual(page.canonical, f"{SITE}/work/?industry=healthcare")

    def test_an_empty_parameter_is_not_kept(self):
        page = seo.parse(self.client.get("/work/?industry=").content.decode())
        self.assertEqual(page.canonical, f"{SITE}/work/")

    @override_settings(DEBUG=False, SITE_URL="http://127.0.0.1:8000")
    def test_a_localhost_canonical_is_refused_by_the_deploy_check(self):
        """The failure mode this guards against: a whole site canonicalised to a dev machine."""
        from apps.core.checks import check_site_url

        errors = check_site_url(None)
        self.assertTrue(errors)
        self.assertIn("zencraft.E002", {error.id for error in errors})

    def test_the_host_header_cannot_change_where_the_page_is_canonicalised(self):
        page = seo.parse(self.client.get("/work/", HTTP_HOST="testserver").content.decode())
        self.assertTrue(page.canonical.startswith(SITE))


@override_settings(SITE_URL=SITE)
class NoindexTests(TestCase):
    """Pages that must never appear in a search result."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_zencraft", verbosity=0)
        open_role()

    def assert_noindex(self, path, **kwargs):
        response = self.client.get(path, **kwargs)
        self.assertIn(response.status_code, (200, 302), path)
        if response.status_code == 200:
            page = seo.parse(response.content.decode())
            self.assertIn("noindex", page.robots, f"{path} should not be indexable")

    def test_search_results_are_not_indexed(self):
        self.assert_noindex(reverse("core:search") + "?q=django")

    @override_settings(STORE_ENABLED=True)
    def test_the_cart_and_checkout_are_not_indexed(self):
        self.assert_noindex(reverse("commerce:cart"))
        self.assert_noindex(reverse("commerce:checkout"))

    def test_the_closed_shop_is_gone_rather_than_hidden(self):
        """With STORE_ENABLED off these answer 404, so nothing can index or link to them."""
        for name in ["commerce:pricing", "commerce:store", "commerce:cart", "commerce:checkout"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 404, name)

    @override_settings(STORE_ENABLED=True)
    def test_turning_the_shop_back_on_needs_no_code_change(self):
        for name in ["commerce:pricing", "commerce:store"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_the_application_steps_and_thank_you_pages_are_not_indexed(self):
        from apps.careers.models import JobOpening

        job = JobOpening.objects.filter(is_active=True).first()
        self.assert_noindex(reverse("careers:apply", args=[job.slug]))
        self.assert_noindex(reverse("careers:applied"))

    def test_none_of_them_are_in_the_sitemap(self):
        paths = set(sitemap_paths())
        for path in [reverse("core:search"), reverse("commerce:cart"), reverse("commerce:checkout"),
                     reverse("careers:applied")]:
            self.assertNotIn(path, paths)


@override_settings(SITE_URL=SITE)
class StructuredDataTests(TestCase):
    """The JSON-LD each page type publishes, parsed rather than grepped."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_zencraft", verbosity=0)
        open_role()

    def blocks(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return [json.loads(block) for block in seo.parse(response.content.decode()).json_ld]

    def of_type(self, path, type_name):
        found = [block for block in self.blocks(path) if block.get("@type") == type_name]
        self.assertEqual(len(found), 1, f"{path} should have exactly one {type_name} block, found {len(found)}")
        return found[0]

    def test_every_page_carries_the_organization_and_website(self):
        for path in ["/", "/about/", "/work/", "/insights/"]:
            types = {block.get("@type") for block in self.blocks(path)}
            self.assertIn("Organization", types, path)
            self.assertIn("WebSite", types, path)

    def test_the_organization_links_to_the_social_profiles(self):
        org = self.of_type("/", "Organization")
        self.assertEqual(org["name"], "Zencraft Solution")
        self.assertEqual(org["url"], SITE)
        self.assertTrue(org["logo"].startswith(SITE))
        self.assertEqual(org["address"]["addressCountry"], "NP")
        same_as = org["sameAs"]
        self.assertIn("https://www.facebook.com/share/1GpaRpTZJy/", same_as)
        self.assertIn("https://www.instagram.com/zencraftsolution", same_as)
        self.assertTrue(all(url for url in same_as), "an empty profile URL was published")

    def test_the_website_offers_a_search_action(self):
        website = self.of_type("/", "WebSite")
        action = website["potentialAction"]
        self.assertEqual(action["@type"], "SearchAction")
        self.assertEqual(action["target"]["urlTemplate"], f"{SITE}/search/?q={{search_term_string}}")
        self.assertEqual(action["query-input"], "required name=search_term_string")

    def test_breadcrumbs_match_the_trail_on_the_page(self):
        crumbs = self.of_type("/services/web-development/", "BreadcrumbList")
        names = [item["name"] for item in crumbs["itemListElement"]]
        self.assertEqual(names, ["Home", "Services", "Web Development"])
        positions = [item["position"] for item in crumbs["itemListElement"]]
        self.assertEqual(positions, [1, 2, 3])
        self.assertTrue(crumbs["itemListElement"][0]["item"].startswith(SITE))
        # The page you are on carries no link, which is what the spec asks for.
        self.assertNotIn("item", crumbs["itemListElement"][-1])

    def test_a_service_page_describes_its_service(self):
        service = self.of_type("/services/web-development/", "Service")
        self.assertEqual(service["name"], "Web Development")
        self.assertEqual(service["url"], f"{SITE}/services/web-development/")
        self.assertEqual(service["provider"]["@id"], f"{SITE}/#organization")
        self.assertTrue(service["description"])

    def test_a_service_page_with_questions_publishes_them_as_an_faq(self):
        faq = self.of_type("/services/web-development/", "FAQPage")
        self.assertTrue(faq["mainEntity"])
        first = faq["mainEntity"][0]
        self.assertEqual(first["@type"], "Question")
        self.assertTrue(first["name"])
        self.assertTrue(first["acceptedAnswer"]["text"])

    def test_an_empty_faq_is_not_published_at_all(self):
        """An FAQPage with no questions is a structured-data error, not a neutral one."""
        from apps.services.models import FAQ, Service

        service = Service.objects.get(slug="web-development")
        FAQ.objects.filter(object_id=service.pk).delete()
        types = {block.get("@type") for block in self.blocks("/services/web-development/")}
        self.assertNotIn("FAQPage", types)

    def test_a_blog_post_publishes_its_author_and_dates(self):
        from apps.blog.models import BlogPost

        post = BlogPost.objects.filter(is_published=True).first()
        article = self.of_type(post.get_absolute_url(), "BlogPosting")
        self.assertEqual(article["headline"], post.title)
        self.assertEqual(article["author"]["name"], post.author.name)
        self.assertTrue(article["datePublished"].startswith(str(post.published_at.year)))
        self.assertEqual(article["publisher"]["@id"], f"{SITE}/#organization")
        self.assertEqual(article["mainEntityOfPage"]["@id"], f"{SITE}{post.get_absolute_url()}")

    def test_a_case_study_publishes_as_an_article(self):
        from apps.portfolio.models import CaseStudy
        from apps.services.models import Industry

        case = CaseStudy.objects.filter(is_published=True).first()
        case.industry = Industry.objects.order_by("order").first()
        case.save(update_fields=["industry"])
        article = self.of_type(case.get_absolute_url(), "Article")
        self.assertEqual(article["headline"], case.title)
        self.assertTrue(article["image"].startswith("http"))
        self.assertEqual(article["about"], case.industry.name)

    def test_a_case_study_with_no_industry_simply_omits_it(self):
        from apps.portfolio.models import CaseStudy

        case = CaseStudy.objects.filter(is_published=True).first()
        case.industry = None
        case.save(update_fields=["industry"])
        self.assertNotIn("about", self.of_type(case.get_absolute_url(), "Article"))

    def test_an_office_based_job_publishes_a_location_and_salary(self):
        from apps.careers.models import JobOpening

        job = JobOpening.objects.filter(is_active=True, work_mode="hybrid", show_salary=True).first()
        posting = self.of_type(job.get_absolute_url(), "JobPosting")
        self.assertEqual(posting["title"], job.title)
        self.assertEqual(posting["@context"], "https://schema.org")  # not "https://schema.org/"
        self.assertEqual(posting["employmentType"], "FULL_TIME")
        self.assertEqual(posting["jobLocation"]["address"]["addressLocality"], "Rupandehi")
        self.assertNotIn("jobLocationType", posting)
        salary = posting["baseSalary"]["value"]
        self.assertEqual(salary["unitText"], "MONTH")
        self.assertEqual(salary["minValue"], float(job.salary_min_npr))
        self.assertTrue(posting["datePosted"])
        self.assertTrue(posting["validThrough"])

    def test_a_remote_job_uses_the_shape_google_requires(self):
        from apps.careers.models import JobOpening

        job = JobOpening.objects.filter(is_active=True).first()
        job.work_mode = "remote"
        job.save(update_fields=["work_mode"])
        posting = self.of_type(job.get_absolute_url(), "JobPosting")
        self.assertEqual(posting["jobLocationType"], "TELECOMMUTE")
        self.assertEqual(posting["applicantLocationRequirements"]["name"], "Nepal")
        self.assertNotIn("jobLocation", posting)

    def test_a_job_with_a_hidden_salary_publishes_none(self):
        from apps.careers.models import JobOpening

        job = JobOpening.objects.filter(is_active=True).first()
        job.show_salary = False
        job.save(update_fields=["show_salary"])
        self.assertNotIn("baseSalary", self.of_type(job.get_absolute_url(), "JobPosting"))

    @override_settings(STORE_ENABLED=True)
    def test_a_store_product_publishes_its_price_as_an_offer(self):
        from apps.commerce.models import ProductizedService

        product = ProductizedService.objects.filter(is_active=True).first()
        data = self.of_type(product.get_absolute_url(), "Product")
        self.assertEqual(data["name"], product.name)
        offer = data["offers"]
        self.assertEqual(offer["priceCurrency"], "NPR")
        self.assertEqual(offer["price"], f"{product.price_npr:.0f}")
        self.assertEqual(offer["availability"], "https://schema.org/InStock")

    def test_empty_fields_are_left_out_rather_than_published_as_null(self):
        from apps.core.structured_data import _clean

        self.assertEqual(_clean({"a": 1, "b": "", "c": None, "d": [], "e": {"f": ""}}), {"a": 1, "e": {}})


@override_settings(SITE_URL=SITE)
class SitemapContentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_zencraft", verbosity=0)
        open_role()

    def body(self):
        return self.client.get("/sitemap.xml").content.decode()

    def test_entries_carry_a_last_modified_date(self):
        """Every record-driven entry is dated: each service, case study, article and open role."""
        from apps.blog.models import BlogPost
        from apps.careers.models import JobOpening
        from apps.portfolio.models import CaseStudy
        from apps.services.models import Service

        records = (Service.objects.filter(is_published=True).count() + CaseStudy.objects.filter(is_published=True).count()
                   + BlogPost.objects.filter(is_published=True).count() + JobOpening.objects.filter(is_active=True).count())
        self.assertGreaterEqual(self.body().count("<lastmod>"), records)

    def test_case_studies_and_articles_offer_their_image(self):
        body = self.body()
        self.assertGreater(body.count("<image:image>"), 10)
        self.assertIn('xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"', body)

    def test_a_closed_role_drops_out(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.careers.models import JobOpening

        job = JobOpening.objects.filter(is_active=True).first()
        self.assertIn(job.get_absolute_url(), self.body())
        job.closing_date = timezone.localdate() - timedelta(days=1)
        job.save(update_fields=["closing_date"])
        self.assertNotIn(job.get_absolute_url(), self.body())

    def test_an_unpublished_case_study_is_not_offered(self):
        from apps.portfolio.models import CaseStudy

        case = CaseStudy.objects.filter(is_published=True).first()
        case.is_published = False
        case.save(update_fields=["is_published"])
        self.assertNotIn(case.get_absolute_url(), self.body())

    def test_robots_points_at_the_sitemap_using_the_real_site_url(self):
        body = self.client.get("/robots.txt").content.decode()
        self.assertIn(f"Sitemap: {SITE}/sitemap.xml", body)


@override_settings(SITE_URL=SITE)
class FrontEndPerformanceTests(TestCase):
    """Core Web Vitals are a ranking factor, so the things that move them are tested, not assumed."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_zencraft", verbosity=0)

    def head(self, path="/"):
        return self.client.get(path).content.decode()

    def test_no_stylesheet_comes_from_another_origin(self):
        """Each extra origin is a DNS lookup and a TLS handshake before any text can be painted."""
        for path in ["/", "/work/", "/insights/", reverse("dashboard:login")]:
            html = self.head(path)
            external = re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="(https?://[^"]+)"', html)
            self.assertEqual(external, [], f"{path} loads a stylesheet from {external}")

    def test_the_fonts_are_served_from_this_site_and_not_preloaded(self):
        html = self.head()
        self.assertNotIn("fonts.googleapis.com", html)
        self.assertNotIn("fonts.gstatic.com", html)
        self.assertIn("css/fonts", html)
        # fonts.css is the first stylesheet and asks for font-display: swap, so text is never
        # invisible. A font preload was reported by Firefox as unused whenever the main stylesheet
        # arrived late, so there is none.
        self.assertEqual(re.findall(r'<link rel="preload"[^>]*as="font"', html), [])

    def test_every_preloaded_font_is_one_the_stylesheet_uses(self):
        """A preload that no @font-face asks for is downloaded for nothing, and browsers warn that
        it was "not used within a few seconds of the load event"."""
        css = (settings.BASE_DIR / "static" / "css" / "fonts.css").read_text(encoding="utf-8")
        used = {name for name in re.findall(r"url\('\.\./fonts/([^']+)'\)", css)}
        preloads = re.findall(r'<link rel="preload" href="[^"]*/fonts/([^"/]+?)(?:\.[0-9a-f]{12})?\.woff2"', self.head())
        self.assertEqual(len(preloads), len(set(preloads)), "a font is preloaded twice")
        for name in preloads:
            self.assertIn(f"{name}.woff2", used, f"{name}.woff2 is preloaded but no @font-face uses it")

    def test_no_font_file_is_shipped_twice(self):
        """The fonts are variable: one file serves every weight. A copy per weight under another
        name made a first visit download the same bytes up to four times."""
        import hashlib

        seen = {}
        for path in sorted((settings.BASE_DIR / "static" / "fonts").glob("*.woff2")):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertNotIn(digest, seen, f"{path.name} is a copy of {seen.get(digest)}")
            seen[digest] = path.name

    def test_the_self_hosted_font_css_asks_for_swap_so_text_is_never_invisible(self):
        css = (settings.BASE_DIR / "static" / "css" / "fonts.css").read_text(encoding="utf-8")
        self.assertIn("font-display: swap", css)
        self.assertNotIn("fonts.gstatic.com", css)
        # Latin subsets only: a visitor in Nepal should not download Cyrillic and Vietnamese.
        self.assertNotIn("U+0460-052F", css)

    def test_the_icon_font_is_served_from_this_site(self):
        css = (settings.BASE_DIR / "static" / "css" / "icons.css").read_text(encoding="utf-8")
        self.assertIn("../fonts/Phosphor.woff2", css)
        self.assertNotIn("cdn.jsdelivr.net", css)
        self.assertIn("font-display: swap", css)

    def test_every_script_is_deferred(self):
        """A blocking script in the head stops the parser, which shows up directly in LCP."""
        html = self.head()
        for tag in re.findall(r"<script[^>]+src=[^>]*>", html):
            self.assertRegex(tag, r"\b(defer|async)\b", tag)

    def test_every_image_declares_its_size(self):
        """Without width and height the page reflows as images arrive, which is measured as CLS."""
        for path in ["/", "/work/", "/insights/", "/careers/", "/about/"]:
            for image in seo.parse(self.head(path)).images:
                with self.subTest(path=path, src=image.get("src", "")[:60]):
                    self.assertIn("width", image)
                    self.assertIn("height", image)

    def test_images_below_the_first_screen_are_lazy_and_the_hero_is_not(self):
        # The seed ships a single post, so add two to put something below the fold.
        from apps.blog.models import BlogPost

        seeded = BlogPost.objects.get()
        for n in (2, 3):
            BlogPost.objects.create(slug=f"{seeded.slug}-{n}", title=f"{seeded.title} {n}", category=seeded.category,
                                    excerpt=seeded.excerpt, body=seeded.body, hero_image_url=seeded.hero_image_url,
                                    is_published=True, published_at=seeded.published_at)
        html = self.head("/insights/")
        # data-seed marks content imagery. The small logo in the header is above the fold and
        # correctly carries neither hint: lazy would delay it, high would outrank the real hero.
        tags = [tag for tag in re.findall(r"<img[^>]+>", html) if "data-seed=" in tag]
        self.assertTrue(any('fetchpriority="high"' in tag for tag in tags), "no image is marked as the one to load first")
        later = [tag for tag in tags if 'fetchpriority="high"' not in tag]
        self.assertTrue(later, "nothing below the fold to check")
        self.assertTrue(all('loading="lazy"' in tag for tag in later), "an image below the fold is not lazy")

    def test_resizable_images_offer_smaller_versions(self):
        html = self.head("/work/")
        srcsets = re.findall(r'srcset="([^"]+)"', html)
        self.assertTrue(srcsets, "no image offers a smaller version for a phone")
        for value in srcsets:
            self.assertIn("480w", value)
            self.assertIn("1200w", value)

    def test_an_image_host_that_cannot_resize_gets_no_srcset(self):
        """A srcset that offers the same large file at four widths makes the page slower."""
        from apps.core.templatetags.zc import srcset

        self.assertEqual(srcset("https://example.com/photo.jpg"), "")
        self.assertEqual(srcset(""), "")
        self.assertIn("480w", srcset("https://images.unsplash.com/photo-1?w=1200"))


class TemplateHygieneTests(TestCase):
    """Django's {# #} comment only works on one line; a multi-line one is printed to the page."""

    def test_no_template_comment_reaches_the_browser(self):
        for path in ["/", "/work/", "/insights/", "/careers/", "/contact/", "/about/"]:
            html = self.client.get(path).content.decode()
            with self.subTest(path=path):
                self.assertNotIn("{#", html)
                self.assertNotIn("{% comment", html)
                self.assertNotIn("{%", html)
