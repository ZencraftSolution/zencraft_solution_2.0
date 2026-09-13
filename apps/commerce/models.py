from decimal import Decimal

from django.db import models
from django.urls import reverse


class EngagementModel(models.Model):
    KIND_CHOICES = [
        ("dedicated", "Dedicated team"),
        ("tm", "Time and materials"),
        ("fixed", "Fixed price"),
        ("retainer", "Retainer and support"),
    ]
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    icon = models.CharField(max_length=40, default="users-three")
    summary = models.CharField(max_length=240)
    best_for = models.CharField(max_length=240)
    how_it_works = models.TextField()
    advantages = models.JSONField(default=list, blank=True, help_text="List of short strings")
    billing_note = models.CharField(max_length=160)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name


class RoleRate(models.Model):
    role = models.CharField(max_length=80)
    experience_band = models.CharField(max_length=40)
    hourly_rate_npr = models.DecimalField(max_digits=12, decimal_places=2)
    monthly_rate_npr = models.DecimalField(max_digits=12, decimal_places=2)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.role} ({self.experience_band})"


class FixedPriceRange(models.Model):
    project_type = models.CharField(max_length=120)
    description = models.CharField(max_length=240)
    min_npr = models.DecimalField(max_digits=12, decimal_places=2)
    max_npr = models.DecimalField(max_digits=12, decimal_places=2)
    typical_timeline = models.CharField(max_length=60)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.project_type


class ProductizedService(models.Model):
    CATEGORY_CHOICES = [
        ("helpdesk", "Help desk plans"),
        ("maintenance", "Website maintenance"),
        ("audit", "Audits"),
        ("assessment", "Assessments"),
        ("consultation", "Discovery and consultation"),
    ]
    BILLING_CHOICES = [("one_time", "One-time"), ("monthly", "Per month")]

    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    tier_label = models.CharField(max_length=40, blank=True)
    icon = models.CharField(max_length=40, default="package")
    summary = models.CharField(max_length=240)
    description = models.TextField()
    price_npr = models.DecimalField(max_digits=12, decimal_places=2)
    billing = models.CharField(max_length=10, choices=BILLING_CHOICES, default="one_time")
    deliverables = models.JSONField(default=list, blank=True, help_text="List of short strings")
    duration = models.CharField(max_length=60, blank=True)
    sla = models.CharField(max_length=80, blank=True)
    featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["category", "order"]

    def __str__(self):
        return f"{self.name} {self.tier_label}".strip()

    def get_absolute_url(self):
        return reverse("commerce:product_detail", args=[self.slug])


class Order(models.Model):
    PAYMENT_METHODS = [
        ("esewa", "eSewa"),
        ("khalti", "Khalti"),
        ("fonepay", "Fonepay"),
        ("stripe", "Card (Stripe, USD)"),
        ("bank", "Bank transfer"),
        ("invoice", "Invoice (enterprise)"),
    ]
    PAYMENT_STATUS = [("pending", "Pending"), ("awaiting", "Awaiting transfer"), ("paid", "Paid"), ("failed", "Failed"), ("refunded", "Refunded")]
    FULFILMENT_STATUS = [("new", "New"), ("scheduled", "Scheduled"), ("in_progress", "In progress"), ("delivered", "Delivered"), ("cancelled", "Cancelled")]

    reference = models.CharField(max_length=20, unique=True)
    customer_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40)
    company = models.CharField(max_length=160, blank=True)
    country = models.CharField(max_length=80, default="Nepal")
    billing_address = models.CharField(max_length=255, blank=True)
    pan_vat = models.CharField("PAN / VAT number", max_length=40, blank=True)
    notes = models.TextField(blank=True)
    subtotal_npr = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    vat_npr = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    total_npr = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4)
    total_usd = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, blank=True)
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS, default="pending")
    fulfilment_status = models.CharField(max_length=12, choices=FULFILMENT_STATUS, default="new")
    consent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(ProductizedService, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=160)
    billing = models.CharField(max_length=10)
    unit_price_npr = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    line_total_npr = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.name}"


class Payment(models.Model):
    STATUS = [("initiated", "Initiated"), ("success", "Success"), ("failed", "Failed")]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    gateway = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="NPR")
    status = models.CharField(max_length=10, choices=STATUS, default="initiated")
    transaction_id = models.CharField(max_length=120, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.gateway} {self.amount} {self.currency}"
