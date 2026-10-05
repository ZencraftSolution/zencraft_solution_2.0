"""Replaces the seeded placeholder team with the three founders.

Runs as a migration, not only in the seed command, because the deployed
database is never re-seeded. Photos are copied out of static/img/ into the
configured media storage so they keep working after a redeploy.
"""

from django.db import migrations

from apps.portfolio.photos import attach_static_photo

FOUNDERS = [
    ("Shankar Poudel", "Co-founder and CEO", "shankar.jpeg",
     "Shankar leads Zencraft and is the person clients call when something matters. He starts every engagement by sitting with the people who will actually use the software, and he will tell you honestly when a smaller build will serve you better."),
    ("Khem Bahadur Lodh", "Co-founder, CTO and Software Engineer", "khem.jpeg",
     "Khem designs the systems behind our work and still writes code on every project. He keeps releases boring: reviewed by a second engineer, covered by tests and safe to roll back, so your platform stays up while it keeps growing."),
    ("Birendra Kumar Chaudhary", "Co-founder and CPO", "birendra.jpeg",
     "Birendra turns business goals into a product plan you can hold us to, with a clear scope, schedule and first release. He tests every design with real users, including people opening a digital service for the first time."),
]

# Posts written under a placeholder byline move to the founder who owns that subject.
POST_AUTHORS = {
    "fixed-price-vs-dedicated-team": "Shankar Poudel",
    "how-we-hire-junior-engineers": "Shankar Poudel",
    "core-web-vitals-nepal-mobile": "Khem Bahadur Lodh",
    "legacy-modernization-without-rewrite": "Khem Bahadur Lodh",
    "cloud-costs-five-quick-wins": "Khem Bahadur Lodh",
    "discovery-workshop-what-to-expect": "Birendra Kumar Chaudhary",
}


def install_founders(apps, schema_editor):
    TeamMember = apps.get_model("portfolio", "TeamMember")
    BlogPost = apps.get_model("blog", "BlogPost")

    TeamMember.objects.exclude(name__in=[name for name, *_ in FOUNDERS]).delete()
    members = {}
    for order, (name, role, photo, bio) in enumerate(FOUNDERS):
        member, _ = TeamMember.objects.update_or_create(
            name=name,
            defaults=dict(role=role, bio=bio, is_leadership=True, order=order, photo_url=""),
        )
        if not member.photo:
            attach_static_photo(member, photo)
        members[name] = member

    for slug, author in POST_AUTHORS.items():
        BlogPost.objects.filter(slug=slug).update(author=members[author])


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0003_teammember_photo_alter_teammember_photo_url"),
        ("blog", "0002_initial"),
    ]

    operations = [migrations.RunPython(install_founders, migrations.RunPython.noop)]
