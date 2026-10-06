"""Scans the private files that were taken in while the web service had no scanner.

Run this wherever ClamAV actually is: a Render cron job or background worker that has the daemon
installed, or a machine in the office. Until a file is cleared here, the dashboard refuses to
stream it, so this command is what releases CVs to the hiring team.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.module_loading import import_string

from apps.core.models import ScannedUpload
from apps.core.uploads import ScannerUnavailable, get_private_storage


class Command(BaseCommand):
    help = "Scans quarantined private uploads and releases the clean ones. Schedule every few minutes."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50, help="Most files to scan in one run.")
        parser.add_argument("--retry-errors", action="store_true", help="Also retry files whose last scan failed.")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        statuses = ["pending", "error"] if options["retry_errors"] else ["pending"]
        queue = ScannedUpload.objects.filter(status__in=statuses)[: options["limit"]]
        if not queue:
            self.stdout.write("Nothing waiting to be scanned.")
            return

        if options["dry_run"]:
            for record in queue:
                self.stdout.write(f"would scan {record.path} ({record.status})")
            return

        scan = import_string("apps.core.uploads.clamav_scan")
        storage = get_private_storage()
        tally = {"clean": 0, "infected": 0, "error": 0, "missing": 0}

        for record in queue:
            record.attempts += 1
            if not storage.exists(record.path):
                # Purged or deleted between upload and scan. Nothing to release.
                record.status = "error"
                record.signature = "file no longer in storage"
                tally["missing"] += 1
            else:
                try:
                    with storage.open(record.path, "rb") as handle:
                        record.status = "clean" if scan(handle) else "infected"
                except ScannerUnavailable as exc:
                    record.status = "error"
                    record.signature = str(exc)[:255]
                except Exception as exc:  # a broken file must not stop the rest of the queue
                    record.status = "error"
                    record.signature = f"{type(exc).__name__}: {exc}"[:255]
                tally[record.status if record.status in tally else "error"] += 1
            record.scanned_at = timezone.now()
            record.save(update_fields=["status", "signature", "attempts", "scanned_at"])

        summary = ", ".join(f"{count} {name}" for name, count in tally.items() if count)
        self.stdout.write(self.style.SUCCESS(f"Scanned {len(queue)} files: {summary}."))
        if tally["infected"]:
            self.stdout.write(self.style.ERROR("Infected files are blocked. Review them in HQ > Audit log."))
