"""Copies private files (CVs, requirement documents) from local disk into the configured backend.

Run this once after switching PRIVATE_STORAGE_BACKEND from "local" to "s3", with the local
directory still in place. Nothing is deleted: the source files stay where they are until you
have checked the copies, which is what --verify is for.
"""

from django.apps import apps
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from apps.core.uploads import PrivateStorage, get_private_storage

# Every field holding a private file. Keep this in step when a new one is added.
PRIVATE_FIELDS = [
    ("careers", "JobApplication", "cv"),
    ("estimator", "ProjectInquiry", "document"),
]


class Command(BaseCommand):
    help = "Copies private uploads from PRIVATE_MEDIA_ROOT into the configured private storage."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="List what would be copied.")
        parser.add_argument("--verify", action="store_true", help="Check sizes afterwards instead of copying.")
        parser.add_argument("--overwrite", action="store_true", help="Copy again even when the target already exists.")

    def handle(self, *args, **options):
        target = get_private_storage()
        source = PrivateStorage()
        if isinstance(target, PrivateStorage):
            raise CommandError(
                "PRIVATE_STORAGE_BACKEND is still 'local', so there is nowhere to copy to. "
                "Set it to 's3' with the PRIVATE_S3_* settings first."
            )

        copied = skipped = missing = mismatched = 0
        for app_label, model_name, field_name in PRIVATE_FIELDS:
            model = apps.get_model(app_label, model_name)
            rows = model.objects.exclude(**{field_name: ""}).exclude(**{f"{field_name}__isnull": True})
            for row in rows.only("pk", field_name):
                name = getattr(row, field_name).name
                if not name:
                    continue
                if not source.exists(name):
                    self.stderr.write(f"missing locally: {name}")
                    missing += 1
                    continue
                if options["verify"]:
                    if not target.exists(name):
                        self.stderr.write(f"not in the new storage: {name}")
                        mismatched += 1
                    elif target.size(name) != source.size(name):
                        self.stderr.write(f"size differs: {name}")
                        mismatched += 1
                    continue
                if target.exists(name) and not options["overwrite"]:
                    skipped += 1
                    continue
                if options["dry_run"]:
                    self.stdout.write(f"would copy {name} ({source.size(name)} bytes)")
                    copied += 1
                    continue
                with source.open(name, "rb") as handle:
                    saved = target.save(name, ContentFile(handle.read()))
                if saved != name:
                    # The storage renamed it, so the database row has to follow or the file is lost.
                    model.objects.filter(pk=row.pk).update(**{field_name: saved})
                copied += 1

        if options["verify"]:
            if mismatched or missing:
                raise CommandError(f"{mismatched} file(s) not copied correctly, {missing} missing locally.")
            self.stdout.write(self.style.SUCCESS("Every private file is present in the new storage."))
            return

        verb = "Would copy" if options["dry_run"] else "Copied"
        self.stdout.write(self.style.SUCCESS(f"{verb} {copied} file(s), skipped {skipped} already there, {missing} missing."))
        if not options["dry_run"] and copied:
            self.stdout.write("Run again with --verify, then delete PRIVATE_MEDIA_ROOT by hand once you are satisfied.")
