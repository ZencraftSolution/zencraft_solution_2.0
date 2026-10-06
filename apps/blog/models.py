import math
import re

from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.html import sanitise_html


class BlogCategory(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        verbose_name_plural = "Blog categories"

    def __str__(self):
        return self.name


class BlogPost(models.Model):
    title = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    author = models.ForeignKey("portfolio.TeamMember", on_delete=models.SET_NULL, null=True, blank=True)
    category = models.ForeignKey(BlogCategory, on_delete=models.SET_NULL, null=True, related_name="posts")
    tags = models.CharField(max_length=200, blank=True, help_text="Comma separated")
    excerpt = models.CharField(max_length=300)
    body = models.TextField(help_text="HTML content written by staff. Scripts and event handlers are stripped on save.")
    hero_image_url = models.URLField()
    reading_minutes = models.PositiveSmallIntegerField(default=1, editable=False)
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(default=timezone.now)
    seo_title = models.CharField(max_length=70, blank=True)
    seo_description = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Cleaned here rather than in a form, so the admin, the dashboard, the seed command and
        # any future import all go through it.
        self.body = sanitise_html(self.body)
        words = len(re.sub(r"<[^>]+>", " ", self.body).split())
        self.reading_minutes = max(1, math.ceil(words / 220))
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("blog:detail", args=[self.slug])

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]
