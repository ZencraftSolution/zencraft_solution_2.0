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


class BodySanitisingTests(TestCase):
    """The blog body is the one field printed with |safe, so it is cleaned on the way in."""

    def make(self, body, slug="xss"):
        return BlogPost.objects.create(
            title="Post", slug=slug, excerpt="x", body=body,
            hero_image_url="https://example.com/h.jpg", is_published=True,
        )

    def test_a_script_tag_does_not_survive_a_save(self):
        post = self.make("<p>Real content</p><script>alert('xss')</script>")
        self.assertEqual(post.body, "<p>Real content</p>")
        self.assertNotContains(self.client.get(post.get_absolute_url()), "alert(")

    def test_event_handler_attributes_are_stripped(self):
        post = self.make('<img src="/x.png" onerror="alert(1)"><p onclick="steal()">text</p>', slug="handlers")
        self.assertNotIn("onerror", post.body)
        self.assertNotIn("onclick", post.body)
        self.assertIn('<img src="/x.png">', post.body)
        page = self.client.get(post.get_absolute_url()).content.decode()
        self.assertNotIn("onerror", page)
        self.assertNotIn("steal()", page)

    def test_javascript_urls_and_frames_are_removed(self):
        post = self.make('<a href="javascript:alert(1)">click</a><iframe src="https://evil.test"></iframe>', slug="jsurl")
        self.assertNotIn("javascript:", post.body)
        self.assertNotIn("<iframe", post.body)

    def test_the_markup_an_article_actually_uses_is_kept(self):
        body = (
            '<h2>Heading</h2><p>Text with <strong>bold</strong> and a '
            '<a href="https://example.com">link</a>.</p><ul><li>one</li></ul>'
            '<pre><code class="language-python">x = 1</code></pre>'
        )
        post = self.make(body, slug="kept")
        for fragment in ["<h2>Heading</h2>", "<strong>bold</strong>", "<li>one</li>", 'class="language-python"']:
            self.assertIn(fragment, post.body)
        self.assertIn('rel="noopener noreferrer"', post.body)  # added to outbound links

    def test_reading_time_is_still_calculated_after_cleaning(self):
        post = self.make("<p>" + " ".join(["word"] * 440) + "</p><script>x</script>", slug="reading")
        self.assertEqual(post.reading_minutes, 2)
