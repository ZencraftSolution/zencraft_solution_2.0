import json

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.core import seo
from apps.services.models import FAQ, Industry, ProcessStep, Service, ServiceCategory, Technology


class ServicesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = ServiceCategory.objects.create(name="Services", slug="services")
        cls.industry = Industry.objects.create(
            slug="healthcare", name="Healthcare", tagline="Clinical systems", description="d",
            challenges="Paper records\n\nSlow labs", solutions="HIS\nLab integration", image_url="https://example.com/i.jpg",
        )
        cls.tech = Technology.objects.create(name="Django", slug="django", category="backend", logo_url="https://example.com/d.svg")
        Technology.objects.create(name="Flutter", slug="flutter", category="mobile", logo_url="https://example.com/f.svg")
        cls.web = Service.objects.create(
            category=category, name="Web Development", slug="web-development", nav_blurb="Web platforms", outcome_headline="Fast web",
            summary="Web summary", intro="First paragraph.\n\nSecond paragraph.", hero_image_url="https://example.com/w.jpg",
            deliverables=[{"title": "Design system", "text": "Components"}], order=1,
        )
        cls.web.technologies.add(cls.tech)
        cls.web.industries.add(cls.industry)
        ProcessStep.objects.create(service=cls.web, order=1, title="Discovery", description="Workshops", duration_hint="2 weeks")
        FAQ.objects.create(content_type=ContentType.objects.get_for_model(Service), object_id=cls.web.pk,
                           question="Will the site be fast?", answer="Yes, Lighthouse 90+.")
        cls.hidden = Service.objects.create(
            category=category, name="Blockchain Consulting", slug="blockchain", nav_blurb="Hidden", outcome_headline="x",
            summary="x", intro="x", hero_image_url="https://example.com/b.jpg", is_published=False, order=2,
        )
        cls.web.related.add(cls.hidden)

    def setUp(self):
        cache.clear()

    def test_list_and_navigation_show_published_only(self):
        response = self.client.get(reverse("services:list"))
        self.assertContains(response, "Web Development")
        self.assertNotContains(response, "Blockchain Consulting")
        self.assertEqual([s.slug for s in response.context["nav_services"]], ["web-development"])

    def test_detail_depth_and_structured_data(self):
        response = self.client.get(self.web.get_absolute_url())
        for text in ("Fast web", "Design system", "Discovery", "2 weeks", "Django", "Healthcare", "Will the site be fast?", "Second paragraph."):
            self.assertContains(response, text)
        types = {json.loads(block).get("@type") for block in seo.parse(response.content.decode()).json_ld}
        self.assertIn("FAQPage", types)
        self.assertIn("Service", types)
        self.assertEqual(list(response.context["related_services"]), [])  # unpublished related service is hidden

    def test_unpublished_detail_404(self):
        self.assertEqual(self.client.get(self.hidden.get_absolute_url()).status_code, 404)

    def test_industries_and_detail(self):
        self.assertContains(self.client.get(reverse("services:industries")), "Clinical systems")
        response = self.client.get(self.industry.get_absolute_url())
        self.assertContains(response, "Lab integration")
        self.assertEqual(self.industry.challenge_list, ["Paper records", "Slow labs"])
        self.assertEqual(self.client.get(reverse("services:industry_detail", args=["nope"])).status_code, 404)

    def test_technologies_grouped_by_category(self):
        response = self.client.get(reverse("services:technologies"))
        self.assertEqual([(key, label) for key, label, _ in response.context["groups"]], [("backend", "Backend"), ("mobile", "Mobile")])
        self.assertEqual(response.context["total"], 2)
