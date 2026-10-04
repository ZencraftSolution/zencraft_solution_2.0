from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db import models


class SiteSettings(models.Model):
    company_name = models.CharField(max_length=120, default="Zencraft Solution")
    tagline = models.CharField(max_length=200, default="Software engineering partner for growing businesses")
    email = models.EmailField(default="zencraftsolutions789@gmail.com")
    careers_email = models.EmailField(default="careers@zencraftsolution.com")
    secondary_email = models.EmailField(blank=True, default="info@zencraftsolution.com", help_text="Shown in the footer in place of the main email. Leave empty to use the main email.")
    phone = models.CharField(max_length=40, default="+977 9823520888")
    secondary_phone = models.CharField(max_length=40, blank=True, default="+977 9857055518", help_text="Shown in the footer in place of the main phone number. Leave empty to use the main number.")
    whatsapp = models.CharField(max_length=40, blank=True, default="+977 9823520888")
    address = models.CharField(max_length=255, default="Tilottama Municipality-3, Rupandehi, Nepal")
    office_hours = models.CharField(max_length=120, default="Sun to Fri, 9:30 to 18:00 NPT")
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    x_url = models.URLField(blank=True)

    exchange_rate_npr_per_usd = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal("134.2500"),
        help_text="How many NPR equal 1 USD. Snapshotted onto every order and estimate.",
    )

    hero_title = models.CharField(max_length=160, default="Software that runs the business, built to last")
    hero_subtitle = models.CharField(
        max_length=240,
        default="We design, build and support custom platforms for teams in Nepal and abroad, from first workshop to long-term operations.",
    )

    stat_projects = models.PositiveIntegerField(default=148)
    stat_clients = models.PositiveIntegerField(default=63)
    stat_engineers = models.PositiveIntegerField(default=41)
    stat_uptime = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("99.95"))
    stat_years = models.PositiveIntegerField(default=9)

    updated_at = models.DateTimeField(auto_now=True)

    CACHE_KEY = "site-settings"

    class Meta:
        verbose_name = "Site settings"
        verbose_name_plural = "Site settings"

    def __str__(self):
        return "Site settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(self.CACHE_KEY)

    @classmethod
    def load(cls):
        obj = cache.get(cls.CACHE_KEY)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls.CACHE_KEY, obj, 300)
        return obj


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=60)
    object_type = models.CharField(max_length=80, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    detail = models.TextField(blank=True)
    path = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} {self.object_repr}"


class ContactSubmission(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    company = models.CharField(max_length=160, blank=True)
    subject = models.CharField(max_length=160)
    message = models.TextField()
    consent = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name}: {self.subject}"


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email


class ConsultationBooking(models.Model):
    SLOT_CHOICES = [
        ("morning", "Morning (10:00 to 12:00 NPT)"),
        ("afternoon", "Afternoon (13:00 to 16:00 NPT)"),
        ("evening", "Evening (17:00 to 19:00 NPT, suits EU/US)"),
    ]
    TOPIC_CHOICES = [
        ("new-project", "New software project"),
        ("modernization", "Modernizing an existing system"),
        ("team", "Dedicated team or staff augmentation"),
        ("support", "Support, maintenance or help desk"),
        ("data", "Data and analytics"),
        ("other", "Something else"),
    ]
    STATUS_CHOICES = [
        ("requested", "Requested"),
        ("confirmed", "Confirmed"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    name = models.CharField(max_length=120)
    company = models.CharField(max_length=160, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    preferred_date = models.DateField()
    preferred_slot = models.CharField(max_length=20, choices=SLOT_CHOICES)
    topic = models.CharField(max_length=30, choices=TOPIC_CHOICES)
    message = models.TextField(blank=True)
    consent = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="requested")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} on {self.preferred_date}"


class PageView(models.Model):
    path = models.CharField(max_length=255, db_index=True)
    referrer = models.CharField(max_length=255, blank=True)
    session_key = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.path
