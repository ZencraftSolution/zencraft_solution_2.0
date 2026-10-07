from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.templatetags.static import static

from apps.core.fields import URLField
from apps.core.uploads import RandomisedPath, validate_image_upload


class SiteSettings(models.Model):
    company_name = models.CharField(max_length=120, default="Zencraft Solution")
    tagline = models.CharField(max_length=200, default="Software engineering partner for growing businesses")
    email = models.EmailField(default="info@zencraftsolution.com")
    careers_email = models.EmailField(default="careers@zencraftsolution.com")
    secondary_email = models.EmailField(blank=True, default="", help_text="Shown in the footer in place of the main email. Leave empty to use the main email.")
    phone = models.CharField(max_length=40, default="+977 9857055518")
    secondary_phone = models.CharField(max_length=40, blank=True, default="", help_text="Shown in the footer in place of the main phone number. Leave empty to use the main number.")
    international_phone = models.CharField(
        max_length=40, blank=True, default="+358 414808204",
        help_text="A second number shown in the footer alongside the main one. Leave empty to hide it.",
    )
    whatsapp = models.CharField(max_length=40, blank=True, default="+977 9857055518")
    address = models.CharField(max_length=255, default="Tilottama Municipality-3, Rupandehi, Nepal")
    office_hours = models.CharField(max_length=120, default="Sun to Fri, 9:30 to 18:00 NPT")
    # Only the networks with a link are shown in the footer, so leaving one blank hides it.
    linkedin_url = URLField(blank=True, default="https://www.linkedin.com/in/zencraft-solution-pvt-ltd-93ab8143b")
    facebook_url = URLField(blank=True, default="https://www.facebook.com/share/1GpaRpTZJy/")
    instagram_url = URLField(blank=True, default="https://www.instagram.com/zencraftsolution")
    tiktok_url = URLField(blank=True, default="https://www.tiktok.com/@zencraft.solution")
    github_url = URLField(blank=True)
    x_url = URLField(blank=True)

    # The picture shown when a page is shared and has no image of its own. 1200x630 works best.
    share_image = models.ImageField(
        "Default sharing image", upload_to=RandomisedPath("branding"), blank=True, validators=[validate_image_upload],
        help_text="1200x630 JPG, PNG or WebP. Shown on Facebook, LinkedIn and X when a page has no image of its own.",
    )
    share_image_url = URLField(blank=True, help_text="Used instead of an upload, if you host the image elsewhere.")

    exchange_rate_npr_per_usd = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal("134.2500"),
        help_text="How many NPR equal 1 USD. Snapshotted onto every order and estimate.",
    )

    hero_title = models.CharField(max_length=160, default="Software that runs the business, built to last")
    hero_subtitle = models.CharField(
        max_length=240,
        default="We design, build and support custom platforms for teams in Nepal and abroad, from first workshop to long-term operations.",
    )

    stat_projects = models.PositiveIntegerField(default=14)
    stat_clients = models.PositiveIntegerField(default=9)
    stat_engineers = models.PositiveIntegerField(default=11)
    stat_uptime = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("99.90"))
    stat_years = models.PositiveIntegerField(default=1)

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

    @property
    def share_image_src(self):
        """An uploaded card wins, then a hosted one, then the logo, so sharing never shows nothing."""
        try:
            if self.share_image and self.share_image.name:
                return self.share_image.url
        except ValueError:  # a name with no file behind it, e.g. after a form posted an empty value
            pass
        return self.share_image_url or static("img/logo.png")


class ScannedUpload(models.Model):
    """One row per private file taken in under quarantine, and what a scanner made of it.

    The row is the permission to serve the file. Until the status is "clean" the dashboard
    refuses to stream it, so an unscanned file never reaches a member of staff's machine.
    """

    STATUS_CHOICES = [
        ("pending", "Waiting to be scanned"),
        ("clean", "Scanned, no threat found"),
        ("infected", "Threat found, blocked"),
        ("error", "Scan failed, blocked"),
    ]

    path = models.CharField(max_length=255, unique=True, help_text="Storage path of the private file.")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending", db_index=True)
    signature = models.CharField(max_length=255, blank=True, help_text="What the scanner reported, when it rejected the file.")
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    scanned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.path} ({self.get_status_display()})"


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


class Feedback(models.Model):
    """What a visitor thought of the site or of working with us, left from the home page.

    Separate from ContactSubmission on purpose: a contact message is a question waiting for an
    answer, and feedback is an opinion. Mixing them means the unanswered questions get lost.
    Nothing here is published automatically; a testimonial only goes on the site when somebody
    copies it across deliberately.
    """

    RATING_CHOICES = [(5, "Very good"), (4, "Good"), (3, "Fair"), (2, "Poor"), (1, "Very poor")]

    name = models.CharField(max_length=120)
    email = models.EmailField(blank=True, help_text="Optional. Only needed if they want a reply.")
    company = models.CharField(max_length=160, blank=True)
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, default=5)
    message = models.TextField()
    may_publish = models.BooleanField(
        default=False, help_text="The visitor agreed this may be shown on the site as a testimonial.",
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Feedback"

    def __str__(self):
        return f"{self.name} ({self.get_rating_display()})"


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
