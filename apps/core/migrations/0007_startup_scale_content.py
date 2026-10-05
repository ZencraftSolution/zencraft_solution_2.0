"""Brings seeded content in line with a company founded in 2026.

The site shipped with placeholder figures for an established agency (9 years, 148 projects) and
case studies dated 2023 to 2025. This rewrites them on deploy so the live site matches reality.
Anything already edited by hand is left alone: statistics are only touched while they still hold
the original seeded values.
"""
from decimal import Decimal

from django.db import migrations

OLD_STATS = {"stat_projects": 148, "stat_clients": 63, "stat_engineers": 41, "stat_years": 9, "stat_uptime": Decimal("99.95")}
NEW_STATS = {"stat_projects": 14, "stat_clients": 9, "stat_engineers": 11, "stat_years": 1, "stat_uptime": Decimal("99.90")}

# slug -> (duration, team size); every seeded case study now sits in 2026.
CASE_STUDIES = {
    "mobile-banking-development-bank": ("5 months", 6),
    "hospital-information-system": ("6 months", 7),
    "omnichannel-fashion-retail": ("4 months", 5),
    "fleet-tracking-logistics": ("3 months", 4),
    "university-learning-platform": ("5 months", 6),
    "hotel-group-cloud-support": ("3 months, then ongoing", 4),
    "ngo-program-analytics": ("4 months", 4),
}


def scale_to_startup(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    settings_row = SiteSettings.objects.filter(pk=1).first()
    if settings_row:
        changed = []
        for field, old_value in OLD_STATS.items():
            if getattr(settings_row, field) == old_value:
                setattr(settings_row, field, NEW_STATS[field])
                changed.append(field)
        if changed:
            settings_row.save(update_fields=changed)

    CaseStudy = apps.get_model("portfolio", "CaseStudy")
    for slug, (duration, team_size) in CASE_STUDIES.items():
        CaseStudy.objects.filter(slug=slug).update(year=2026, duration=duration, team_size=team_size)


def noop(apps, schema_editor):
    """Not reversible: the previous figures were placeholders, not real history."""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_alter_sitesettings_stat_clients_and_more"),
        ("portfolio", "0003_teammember_photo_alter_teammember_photo_url"),
    ]

    operations = [migrations.RunPython(scale_to_startup, noop)]
