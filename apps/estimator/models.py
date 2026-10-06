from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.uploads import RandomisedPath, get_private_storage


def default_design_multipliers():
    return {"existing": 1.0, "uiux": 1.18, "branding": 1.32}


def default_urgency_multipliers():
    return {"flexible": 0.94, "standard": 1.0, "fast": 1.22, "critical": 1.45}


def default_team_multipliers():
    return {"fixed": 1.0, "dedicated": 0.96, "unsure": 1.0}


def default_platform_coefficients():
    return {"web": 0.30, "ios": 0.32, "android": 0.28, "windows": 0.30, "macos": 0.26, "linux": 0.22}


class EstimatorConfig(models.Model):
    """Admin-tunable pricing engine. Edited from the dashboard, never hardcoded."""

    blended_hourly_rate_npr = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("2150"))
    contingency_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("12"))
    range_low_factor = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("0.85"))
    range_high_factor = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.35"))
    team_hours_per_week = models.PositiveIntegerField(default=30, help_text="Productive hours per full-time person")
    minimum_project_npr = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("60000"))
    design_multipliers = models.JSONField(default=default_design_multipliers)
    urgency_multipliers = models.JSONField(default=default_urgency_multipliers)
    team_multipliers = models.JSONField(default=default_team_multipliers)
    platform_coefficients = models.JSONField(
        default=default_platform_coefficients,
        help_text="Extra effort share added for each platform beyond the first",
    )
    disclaimer = models.TextField(
        default="This range is indicative and based on similar projects we have delivered. Final scope, timeline and pricing are confirmed after a free discovery call."
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Estimator configuration"

    def __str__(self):
        return "Estimator configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ProjectType(models.Model):
    key = models.SlugField(unique=True)
    label = models.CharField(max_length=80)
    description = models.CharField(max_length=200)
    icon = models.CharField(max_length=40, default="browser")
    base_hours = models.PositiveIntegerField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.label


class FeatureOption(models.Model):
    key = models.SlugField(unique=True)
    label = models.CharField(max_length=80)
    help_text = models.CharField(max_length=160, blank=True)
    hours = models.PositiveIntegerField()
    project_types = models.ManyToManyField(ProjectType, related_name="features")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.label} ({self.hours}h)"


class ProjectInquiry(models.Model):
    STATUS_CHOICES = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("qualified", "Qualified"),
        ("proposal", "Proposal sent"),
        ("won", "Won"),
        ("lost", "Lost"),
    ]
    PLATFORM_CHOICES = [("web", "Web"), ("ios", "iOS"), ("android", "Android"), ("windows", "Windows"), ("macos", "macOS"), ("linux", "Linux")]
    TIMELINE_CHOICES = [
        ("flexible", "Flexible, quality first"),
        ("standard", "Standard pace"),
        ("fast", "Faster than usual"),
        ("critical", "Hard deadline"),
    ]
    TEAM_CHOICES = [("fixed", "Fixed-price project"), ("dedicated", "Dedicated team"), ("unsure", "Not sure yet")]
    DESIGN_CHOICES = [("existing", "I have designs"), ("uiux", "Need UI/UX design"), ("branding", "Need full branding and UI/UX")]
    BUDGET_CHOICES = [
        ("under-5l", "Under Rs. 5 lakh"),
        ("5-15l", "Rs. 5 to 15 lakh"),
        ("15-40l", "Rs. 15 to 40 lakh"),
        ("40l-plus", "Above Rs. 40 lakh"),
        ("unknown", "Not decided"),
    ]

    reference = models.CharField(max_length=20, unique=True)
    project_type = models.ForeignKey(ProjectType, on_delete=models.SET_NULL, null=True)
    project_type_label = models.CharField(max_length=80)
    features = models.JSONField(default=list, blank=True)
    platforms = models.JSONField(default=list, blank=True)
    timeline = models.CharField(max_length=20, choices=TIMELINE_CHOICES)
    team_preference = models.CharField(max_length=20, choices=TEAM_CHOICES)
    design_needs = models.CharField(max_length=20, choices=DESIGN_CHOICES)
    budget_band = models.CharField(max_length=20, choices=BUDGET_CHOICES, default="unknown")
    description = models.TextField(blank=True)

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    company = models.CharField(max_length=160, blank=True)
    country = models.CharField(max_length=80, blank=True)
    document = models.FileField(upload_to=RandomisedPath("inquiries"), storage=get_private_storage, blank=True)
    document_name = models.CharField(max_length=255, blank=True)

    estimate_low_npr = models.DecimalField(max_digits=14, decimal_places=2)
    estimate_high_npr = models.DecimalField(max_digits=14, decimal_places=2)
    estimate_weeks_low = models.PositiveIntegerField()
    estimate_weeks_high = models.PositiveIntegerField()
    estimate_hours = models.PositiveIntegerField(default=0)
    suggested_team = models.JSONField(default=list, blank=True)
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new", db_index=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")
    internal_notes = models.TextField(blank=True)
    consent = models.BooleanField(default=False)
    source = models.CharField(max_length=40, default="estimator")
    purged_at = models.DateTimeField(null=True, blank=True, help_text="When the personal details were erased under the retention policy.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Project inquiries"

    def __str__(self):
        return f"{self.reference} {self.company or self.name}"

    @property
    def feature_labels(self):
        labels = dict(FeatureOption.objects.filter(key__in=self.features).values_list("key", "label"))
        return [labels.get(k, k) for k in self.features]

    @property
    def platform_labels(self):
        names = dict(self.PLATFORM_CHOICES)
        return [names.get(p, p) for p in self.platforms]


class LeadNote(models.Model):
    inquiry = models.ForeignKey(ProjectInquiry, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note on {self.inquiry_id} by {self.author or 'system'}"


class EstimatorEvent(models.Model):
    """Step views for drop-off analytics. Step 7 means the result was shown."""

    session_id = models.CharField(max_length=40, db_index=True)
    step = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("session_id", "step")]

    def __str__(self):
        return f"{self.session_id} step {self.step}"
