"""Team photos that ship in the repo rather than coming from a third-party URL."""

from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile

TEAM_PHOTO_DIR = Path(settings.BASE_DIR) / "static" / "img"


def attach_static_photo(member, filename):
    """Copy static/img/<filename> into member.photo so hosted media serves it.

    Returns False when the image is missing, so a checkout without the photos
    still seeds instead of failing halfway through.
    """
    source = TEAM_PHOTO_DIR / filename
    if not source.exists():
        return False
    member.photo.save(filename, ContentFile(source.read_bytes()), save=True)
    return True
