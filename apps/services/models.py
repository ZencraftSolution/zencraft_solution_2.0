from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse


class FAQ(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    question = models.CharField(max_length=255)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "FAQ"
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return self.question


class ServiceCategory(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        verbose_name_plural = "Service categories"

    def __str__(self):
        return self.name


class Technology(models.Model):
    CATEGORY_CHOICES = [
        ("frontend", "Frontend"),
        ("backend", "Backend"),
        ("mobile", "Mobile"),
        ("desktop", "Desktop"),
        ("database", "Databases"),
        ("cloud", "Cloud and DevOps"),
        ("data", "Data and AI"),
        ("testing", "Testing"),
    ]
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    logo_url = models.URLField(help_text="Simple Icons or Devicon SVG URL")
    proficiency = models.PositiveSmallIntegerField(default=4, help_text="1 to 5")
    years_used = models.PositiveSmallIntegerField(default=3)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["category", "order", "name"]
        verbose_name_plural = "Technologies"

    def __str__(self):
        return self.name


class Industry(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=40, default="buildings", help_text="Phosphor icon name")
    tagline = models.CharField(max_length=200)
    description = models.TextField()
    challenges = models.TextField(help_text="One challenge per line")
    solutions = models.TextField(help_text="One solution per line")
    image_url = models.URLField()
    order = models.PositiveIntegerField(default=0)
    faqs = GenericRelation(FAQ)

    class Meta:
        ordering = ["order"]
        verbose_name_plural = "Industries"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("services:industry_detail", args=[self.slug])

    @property
    def challenge_list(self):
        return [c.strip() for c in self.challenges.splitlines() if c.strip()]

    @property
    def solution_list(self):
        return [c.strip() for c in self.solutions.splitlines() if c.strip()]


class Service(models.Model):
    category = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT, related_name="services")
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=40, default="code", help_text="Phosphor icon name")
    nav_blurb = models.CharField(max_length=90, help_text="Short line for menus")
    outcome_headline = models.CharField(max_length=160, help_text="Hero headline framed as a business outcome")
    summary = models.CharField(max_length=260)
    intro = models.TextField()
    hero_image_url = models.URLField()
    deliverables = models.JSONField(default=list, blank=True, help_text='List of {"title": "...", "text": "..."}')
    technologies = models.ManyToManyField(Technology, blank=True, related_name="services")
    industries = models.ManyToManyField(Industry, blank=True, related_name="services")
    engagement_models = models.ManyToManyField("commerce.EngagementModel", blank=True, related_name="services")
    related = models.ManyToManyField("self", blank=True, symmetrical=False)
    seo_title = models.CharField(max_length=70, blank=True)
    seo_description = models.CharField(max_length=160, blank=True)
    order = models.PositiveIntegerField(default=0)
    featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    faqs = GenericRelation(FAQ)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("services:detail", args=[self.slug])


class ProcessStep(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="steps")
    order = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=80)
    description = models.TextField()
    duration_hint = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.service}: {self.title}"
