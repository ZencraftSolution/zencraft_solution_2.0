from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse


class CaseStudy(models.Model):
    title = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    client_name = models.CharField(max_length=120)
    is_anonymized = models.BooleanField(default=False)
    industry = models.ForeignKey("services.Industry", on_delete=models.SET_NULL, null=True, related_name="case_studies")
    services = models.ManyToManyField("services.Service", blank=True, related_name="case_studies")
    technologies = models.ManyToManyField("services.Technology", blank=True, related_name="case_studies")
    summary = models.CharField(max_length=260)
    challenge = models.TextField()
    solution = models.TextField()
    results = models.JSONField(default=list, blank=True, help_text='List of {"value": "38%", "label": "..."}')
    architecture_note = models.TextField(blank=True)
    code_language = models.CharField(max_length=30, blank=True, default="python")
    code_snippet = models.TextField(blank=True)
    cover_image_url = models.URLField()
    duration = models.CharField(max_length=60)
    team_size = models.PositiveSmallIntegerField(default=4)
    year = models.PositiveSmallIntegerField(default=2025)
    featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "-year"]
        verbose_name_plural = "Case studies"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("portfolio:detail", args=[self.slug])


class CaseStudyImage(models.Model):
    case_study = models.ForeignKey(CaseStudy, on_delete=models.CASCADE, related_name="images")
    image_url = models.URLField()
    caption = models.CharField(max_length=160, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]


class Testimonial(models.Model):
    VERIFICATION = [("pending", "Pending"), ("verified", "Verified"), ("rejected", "Rejected")]
    client_name = models.CharField(max_length=120)
    company = models.CharField(max_length=120)
    role = models.CharField(max_length=120)
    photo_url = models.URLField(blank=True)
    rating = models.PositiveSmallIntegerField(default=5)
    content = models.TextField()
    case_study = models.ForeignKey(CaseStudy, on_delete=models.SET_NULL, null=True, blank=True, related_name="testimonials")
    verification = models.CharField(max_length=10, choices=VERIFICATION, default="verified")
    featured = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.client_name}, {self.company}"


class TeamMember(models.Model):
    name = models.CharField(max_length=120)
    role = models.CharField(max_length=120)
    bio = models.TextField(blank=True)
    photo_url = models.URLField()
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    is_leadership = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name


class GalleryImage(models.Model):
    CATEGORY_CHOICES = [("office", "Office"), ("team", "Team"), ("events", "Events"), ("projects", "Projects")]
    image_url = models.URLField()
    caption = models.CharField(max_length=160, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="office")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.caption or self.image_url
