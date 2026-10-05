"""Fills in the Facebook and LinkedIn links on a site settings row that predates them.

Adding the Instagram and TikTok fields backfills their defaults automatically.
These two already existed and are empty on the deployed row, so they need
setting here. A link someone has already edited is left alone.
"""

from django.db import migrations

PROFILES = {
    "facebook_url": "https://www.facebook.com/share/1GpaRpTZJy/",
    "linkedin_url": "https://www.linkedin.com/in/zencraft-solution-pvt-ltd-93ab8143b",
}


def add_profile_links(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    for field, url in PROFILES.items():
        SiteSettings.objects.filter(**{field: ""}).update(**{field: url})


class Migration(migrations.Migration):
    dependencies = [("core", "0008_sitesettings_instagram_url_sitesettings_tiktok_url_and_more")]

    operations = [migrations.RunPython(add_profile_links, migrations.RunPython.noop)]
