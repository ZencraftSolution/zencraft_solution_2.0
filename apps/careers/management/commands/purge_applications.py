"""Enforces the retention periods the privacy policy promises. Schedule this daily.

Two kinds of record expire:
  * Unsuccessful job applications, CV_RETENTION_DAYS after the decision.
  * Project inquiries that never became projects, INQUIRY_RETENTION_DAYS after they arrived.

Neither row is deleted. The personal details are erased and the row stays, so "applications this
quarter" and the lead funnel do not quietly change shape every time the purge runs.
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.careers.models import JobApplication
from apps.careers.privacy import erase_application
from apps.estimator.models import ProjectInquiry

# A lead that reached one of these was not won, so there is no reason to keep the contact details.
CLOSED_INQUIRY_STATUSES = ["lost", "new", "contacted", "qualified", "proposal"]


class Command(BaseCommand):
    help = "Erases the personal data of expired job applications and project inquiries. Schedule daily."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        applications = self.expired_applications()
        inquiries = self.expired_inquiries()

        if options["dry_run"]:
            self.stdout.write(f"{applications.count()} applications and {inquiries.count()} inquiries would be purged.")
            return

        app_count = 0
        for application in applications:
            erase_application(application)
            app_count += 1

        inquiry_count = 0
        for inquiry in inquiries:
            if inquiry.document:
                inquiry.document.delete(save=False)
            inquiry.name = "Purged lead"
            inquiry.email = f"purged-{inquiry.pk}@invalid.local"
            inquiry.phone = ""
            inquiry.company = ""
            inquiry.description = ""
            inquiry.document_name = ""
            inquiry.purged_at = timezone.now()
            inquiry.save()
            inquiry_count += 1

        self.stdout.write(self.style.SUCCESS(f"Purged {app_count} applications and {inquiry_count} inquiries."))

    def expired_applications(self):
        cutoff = timezone.now() - timedelta(days=settings.CV_RETENTION_DAYS)
        return JobApplication.objects.filter(status="rejected", updated_at__lt=cutoff, purged_at__isnull=True)

    def expired_inquiries(self):
        cutoff = timezone.now() - timedelta(days=settings.INQUIRY_RETENTION_DAYS)
        return ProjectInquiry.objects.filter(
            status__in=CLOSED_INQUIRY_STATUSES, created_at__lt=cutoff, purged_at__isnull=True
        )
