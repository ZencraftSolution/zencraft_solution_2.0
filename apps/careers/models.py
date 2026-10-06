from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.uploads import RandomisedPath, get_private_storage


class Department(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name


class JobOpening(models.Model):
    TYPE_CHOICES = [("full-time", "Full-time"), ("part-time", "Part-time"), ("contract", "Contract"), ("internship", "Internship")]
    LEVEL_CHOICES = [("intern", "Intern"), ("junior", "Junior"), ("mid", "Mid-level"), ("senior", "Senior"), ("lead", "Lead")]
    MODE_CHOICES = [("onsite", "On-site, Rupandehi"), ("hybrid", "Hybrid, Rupandehi"), ("remote", "Remote, Nepal")]

    title = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="jobs")
    work_mode = models.CharField(max_length=10, choices=MODE_CHOICES, default="hybrid")
    employment_type = models.CharField(max_length=12, choices=TYPE_CHOICES, default="full-time")
    experience_level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    experience_years = models.CharField(max_length=60, blank=True, help_text="e.g. 2 to 4 years")
    summary = models.CharField(max_length=260)
    description = models.TextField()
    responsibilities = models.TextField(help_text="One per line")
    requirements = models.TextField(help_text="One per line")
    nice_to_haves = models.TextField(blank=True, help_text="One per line")
    growth_path = models.TextField(blank=True)
    tech_stack = models.ManyToManyField("services.Technology", blank=True, related_name="jobs")
    salary_min_npr = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    salary_max_npr = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    show_salary = models.BooleanField(default=True)
    openings = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    posted_at = models.DateField(default=timezone.localdate)
    closing_date = models.DateField(null=True, blank=True)

    # Optional overrides for what a search result shows. Left empty, one is built from the
    # content above, trimmed to the length Google actually displays.
    seo_title = models.CharField(max_length=60, blank=True, help_text="Overrides the search-result title.")
    seo_description = models.CharField(max_length=160, blank=True, help_text="Overrides the search-result description. Aim for 70 to 160 characters.")

    class Meta:
        ordering = ["department__order", "-posted_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("careers:job_detail", args=[self.slug])

    @property
    def is_open(self):
        return self.is_active and (self.closing_date is None or self.closing_date >= timezone.localdate())

    def _lines(self, text):
        return [line.strip() for line in text.splitlines() if line.strip()]

    @property
    def responsibility_list(self):
        return self._lines(self.responsibilities)

    @property
    def requirement_list(self):
        return self._lines(self.requirements)

    @property
    def nice_list(self):
        return self._lines(self.nice_to_haves)


class JobApplication(models.Model):
    MODE_CHOICES = [("cv", "Uploaded CV"), ("manual", "Filled in manually")]
    STATUS_CHOICES = [
        ("received", "Received"),
        ("screening", "Screening"),
        ("shortlisted", "Shortlisted"),
        ("interview", "Interview"),
        ("offer", "Offer"),
        ("hired", "Hired"),
        ("rejected", "Rejected"),
    ]
    NOTICE_CHOICES = [
        ("immediate", "Immediately"),
        ("2-weeks", "Within 2 weeks"),
        ("1-month", "1 month"),
        ("2-months", "2 months or more"),
    ]
    SOURCE_CHOICES = [
        ("website", "Zencraft website"),
        ("linkedin", "LinkedIn"),
        ("merojob", "Merojob or Kumarijob"),
        ("referral", "Referral from a Zencraft employee"),
        ("event", "Meetup, college or event"),
        ("other", "Other"),
    ]

    reference = models.CharField(max_length=20, unique=True)
    job = models.ForeignKey(JobOpening, on_delete=models.PROTECT, related_name="applications")
    application_mode = models.CharField(max_length=10, choices=MODE_CHOICES, default="cv")

    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40)
    current_location = models.CharField(max_length=120)
    years_experience = models.DecimalField(max_digits=4, decimal_places=1)
    cv = models.FileField(upload_to=RandomisedPath("cvs"), storage=get_private_storage, blank=True)
    cv_original_name = models.CharField(max_length=255, blank=True)
    cover_letter = models.TextField(blank=True)
    portfolio_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    expected_salary_npr = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    notice_period = models.CharField(max_length=12, choices=NOTICE_CHOICES)
    source = models.CharField(max_length=12, choices=SOURCE_CHOICES, default="website")

    # Manual CV fields
    headline = models.CharField(max_length=160, blank=True)
    professional_summary = models.TextField(blank=True)
    skills = models.TextField(blank=True, help_text="Comma separated")

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="received", db_index=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    consent = models.BooleanField(default=False)
    consent_at = models.DateTimeField(null=True, blank=True)
    purged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} for {self.job}"

    @property
    def skill_list(self):
        return [s.strip() for s in self.skills.split(",") if s.strip()]

    @property
    def cv_is_pdf(self):
        return bool(self.cv) and self.cv.name.lower().endswith(".pdf")


class EducationEntry(models.Model):
    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name="education")
    institution = models.CharField(max_length=160)
    degree = models.CharField(max_length=120)
    field_of_study = models.CharField(max_length=120, blank=True)
    start_year = models.PositiveSmallIntegerField(null=True, blank=True)
    end_year = models.PositiveSmallIntegerField(null=True, blank=True)
    grade = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["-end_year"]

    def __str__(self):
        return f"{self.degree}, {self.institution}"


class ExperienceEntry(models.Model):
    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name="experience")
    company = models.CharField(max_length=160)
    title = models.CharField(max_length=120)
    start_date = models.CharField(max_length=20, help_text="e.g. 2022-06")
    end_date = models.CharField(max_length=20, blank=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-is_current", "-start_date"]

    def __str__(self):
        return f"{self.title} at {self.company}"


class ProjectEntry(models.Model):
    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=160)
    url = models.URLField(blank=True)
    tech_used = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class ApplicationNote(models.Model):
    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note on {self.application_id} by {self.author or 'system'}"
