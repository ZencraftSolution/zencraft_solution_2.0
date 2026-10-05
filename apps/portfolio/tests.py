from django.test import TestCase
from django.urls import reverse

from apps.portfolio.models import CaseStudy, TeamMember, Testimonial
from apps.portfolio.photos import attach_static_photo
from apps.services.models import Industry, Technology


def make_industry(slug, name):
    return Industry.objects.create(slug=slug, name=name, tagline="t", description="d", challenges="c", solutions="s",
                                   image_url="https://example.com/i.jpg")


class PortfolioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.finance = make_industry("finance", "Banking and finance")
        cls.health = make_industry("healthcare", "Healthcare")
        make_industry("logistics", "Logistics")
        tech = Technology.objects.create(name="Flutter", slug="flutter", category="mobile", logo_url="https://example.com/f.svg")
        cls.bank = CaseStudy.objects.create(
            title="Mobile banking app", slug="mobile-banking", client_name="A bank", industry=cls.finance, summary="Banking",
            challenge="Old app.\n\nCrowded branches.", solution="New API.", results=[{"value": "38%", "label": "Fewer visits"}],
            cover_image_url="https://example.com/c.jpg", duration="7 months", code_snippet="def transfer(): pass",
            architecture_note="Django API gateway",
        )
        cls.bank.technologies.add(tech)
        Testimonial.objects.create(client_name="Sushma", company="Bank", role="CDO", content="Great work.", case_study=cls.bank)
        cls.hospital = CaseStudy.objects.create(
            title="Hospital system", slug="hospital", client_name="Hospital", industry=cls.health, summary="Health",
            challenge="Paper.", solution="HIS.", cover_image_url="https://example.com/h.jpg", duration="11 months",
        )
        cls.hidden = CaseStudy.objects.create(
            title="Secret NDA project", slug="secret", client_name="NDA", industry=cls.finance, summary="Hidden",
            challenge="x", solution="y", cover_image_url="https://example.com/s.jpg", duration="1 month", is_published=False,
        )

    def test_list_shows_published_only(self):
        response = self.client.get(reverse("portfolio:list"))
        self.assertContains(response, "Mobile banking app")
        self.assertContains(response, "Hospital system")
        self.assertNotContains(response, "Secret NDA project")

    def test_industry_filter_lists_only_industries_with_published_work(self):
        response = self.client.get(reverse("portfolio:list") + "?industry=healthcare")
        self.assertContains(response, "Hospital system")
        self.assertNotContains(response, "Mobile banking app")
        self.assertEqual({i.slug for i in response.context["industries"]}, {"finance", "healthcare"})
        self.assertContains(self.client.get(reverse("portfolio:list") + "?industry=logistics"), "No case studies in this industry yet")

    def test_detail_renders_results_code_and_testimonial(self):
        response = self.client.get(self.bank.get_absolute_url())
        self.assertContains(response, "38%")
        self.assertContains(response, "def transfer()")
        self.assertContains(response, "Great work.")
        self.assertContains(response, "Crowded branches.")
        self.assertNotIn(self.hidden, response.context["more"])

    def test_unpublished_detail_404(self):
        self.assertEqual(self.client.get(self.hidden.get_absolute_url()).status_code, 404)


class FoundingTeamTests(TestCase):
    """The three founders are installed by a migration, so the live site gets them without a reseed."""

    FOUNDERS = ["Shankar Poudel", "Khem Bahadur Lodh", "Birendra Kumar Chaudhary"]

    def test_only_the_founders_exist_and_each_has_a_stored_photo(self):
        self.assertEqual([m.name for m in TeamMember.objects.all()], self.FOUNDERS)
        for member in TeamMember.objects.all():
            self.assertTrue(member.photo, f"{member.name} has no uploaded photo")
            self.assertEqual(member.photo_src, member.photo.url)

    def test_about_page_shows_the_founders_and_no_placeholder_team(self):
        response = self.client.get(reverse("core:about"))
        for name in self.FOUNDERS:
            self.assertContains(response, name)
        self.assertNotContains(response, "Team leads")

    def test_attach_static_photo_reports_a_missing_file_instead_of_raising(self):
        member = TeamMember.objects.first()
        self.assertFalse(attach_static_photo(member, "no-such-photo.jpeg"))
