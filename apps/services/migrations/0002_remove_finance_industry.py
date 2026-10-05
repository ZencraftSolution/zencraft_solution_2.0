"""Removes the 'Banking and finance' industry page at the owner's request.

Industries are editable content, so this runs on deploy to take the page off the live site too.
Case studies point at an industry with on_delete=SET_NULL, so the banking case study survives and
simply loses its industry label. Service links are plain M2M rows and go with it.
"""
from django.db import migrations

SLUG = "finance"


def remove_industry(apps, schema_editor):
    Industry = apps.get_model("services", "Industry")
    FAQ = apps.get_model("services", "FAQ")
    ContentType = apps.get_model("contenttypes", "ContentType")
    industry = Industry.objects.filter(slug=SLUG).first()
    if industry is None:
        return
    content_type = ContentType.objects.filter(app_label="services", model="industry").first()
    if content_type:
        FAQ.objects.filter(content_type=content_type, object_id=industry.pk).delete()
    industry.delete()


def noop(apps, schema_editor):
    """Not reversible: re-running seed_zencraft is the way back, and it no longer ships this industry."""


class Migration(migrations.Migration):
    dependencies = [
        ("services", "0001_initial"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [migrations.RunPython(remove_industry, noop)]
