from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.careers.models import JobApplication


class Command(BaseCommand):
    help = "Deletes CV files and personal data of rejected applications older than CV_RETENTION_DAYS. Schedule daily."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=settings.CV_RETENTION_DAYS)
        qs = JobApplication.objects.filter(status="rejected", updated_at__lt=cutoff, purged_at__isnull=True)
        count = qs.count()
        if options["dry_run"]:
            self.stdout.write(f"{count} applications would be purged.")
            return
        for app in qs:
            if app.cv:
                app.cv.delete(save=False)
            app.education.all().delete()
            app.experience.all().delete()
            app.projects.all().delete()
            app.notes.all().delete()
            app.full_name = "Purged applicant"
            app.email = f"purged-{app.pk}@invalid.local"
            app.phone = ""
            app.current_location = ""
            app.cover_letter = app.headline = app.professional_summary = app.skills = ""
            app.portfolio_url = app.github_url = app.linkedin_url = ""
            app.cv_original_name = ""
            app.purged_at = timezone.now()
            app.save()
        self.stdout.write(self.style.SUCCESS(f"Purged {count} applications."))
