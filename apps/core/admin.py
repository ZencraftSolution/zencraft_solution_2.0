from django.contrib import admin

from .models import AuditLog, ConsultationBooking, ContactSubmission, NewsletterSubscriber, SiteSettings

admin.site.register(SiteSettings)
admin.site.register(ContactSubmission)
admin.site.register(NewsletterSubscriber)
admin.site.register(ConsultationBooking)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "user", "action", "object_repr", "ip_address"]
    readonly_fields = [f.name for f in AuditLog._meta.fields]
