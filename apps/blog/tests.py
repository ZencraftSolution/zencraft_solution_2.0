from django.test import TestCase
from django.urls import reverse

from apps.blog.models import BlogCategory, BlogPost


class BlogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.engineering = BlogCategory.objects.create(name="Engineering", slug="engineering")
        cls.culture = BlogCategory.objects.create(name="Culture", slug="culture")
        cls.post = BlogPost.objects.create(
            title="Scaling PostgreSQL for results day", slug="scaling-postgresql", category=cls.engineering, tags="postgres, caching",
            excerpt="Read replicas and caching.", body="<p>" + "replication " * 450 + "</p>", hero_image_url="https://example.com/a.jpg",
        )
        cls.culture_post = BlogPost.objects.create(
            title="How we hire juniors", slug="hiring-juniors", category=cls.culture, excerpt="Take-home tasks.",
            body="<p>We read every application.</p>", hero_image_url="https://example.com/b.jpg",
        )
        cls.draft = BlogPost.objects.create(
            title="Unpublished draft about kubernetes", slug="draft", category=cls.engineering, excerpt="Draft.",
            body="<p>kubernetes secrets</p>", hero_image_url="https://example.com/c.jpg", is_published=False,
        )

    def test_list_shows_published_only(self):
        response = self.client.get(reverse("blog:list"))
        self.assertContains(response, "Scaling PostgreSQL")
        self.assertContains(response, "How we hire juniors")
        self.assertNotContains(response, "Unpublished draft")

    def test_detail_published_only(self):
        response = self.client.get(self.post.get_absolute_url())
        self.assertContains(response, '"@type":"BlogPosting"')
        self.assertContains(response, "postgres")
        self.assertEqual(self.client.get(self.draft.get_absolute_url()).status_code, 404)

    def test_category_filter(self):
        response = self.client.get(reverse("blog:category", args=["culture"]))
        self.assertContains(response, "How we hire juniors")
        self.assertNotContains(response, "Scaling PostgreSQL")
        self.assertEqual(self.client.get(reverse("blog:category", args=["missing"])).status_code, 404)

    def test_full_text_search_ranks_and_excludes_drafts(self):
        response = self.client.get(reverse("blog:list") + "?q=replication")
        self.assertEqual([p.slug for p in response.context["page"].object_list], ["scaling-postgresql"])
        self.assertIsNone(response.context["lead"])
        self.assertContains(self.client.get(reverse("blog:list") + "?q=kubernetes"), "No articles found")

    def test_pagination(self):
        for i in range(12):
            BlogPost.objects.create(title=f"Post {i}", slug=f"post-{i}", category=self.culture, excerpt="x", body="<p>x</p>",
                                    hero_image_url="https://example.com/x.jpg")
        page2 = self.client.get(reverse("blog:list") + "?page=2")
        self.assertEqual(page2.context["page"].number, 2)
        self.assertEqual(len(page2.context["page"].object_list), 5)

    def test_reading_time_and_tags(self):
        self.assertEqual(self.post.reading_minutes, 3)  # 450 words / 220 wpm, rounded up
        self.assertEqual(self.post.tag_list, ["postgres", "caching"])
        self.assertEqual(str(self.post), self.post.title)
