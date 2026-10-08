"""The scroll-controlled animation behind the home-page hero.

Like apps/core/exploded.py, this is the one place that knows whether the frames exist and what
their URLs are (manifest storage renames every file with a content hash in production). When the
artwork is missing the hero still renders its headline and buttons on plain navy; only the
picture is gone.

Build the frames with scripts/build_hero_frames.py, which writes the manifest this reads.
"""

import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.templatetags.static import static

logger = logging.getLogger(__name__)

MANIFEST_PATH = settings.BASE_DIR / "static" / "img" / "hero-anim" / "manifest.json"
CACHE_KEY = "hero-anim-manifest"
CACHE_SECONDS = 300
MIN_FRAMES = 2

# The five chapters, in the order the video reaches them. "at" is the second at which the
# chapter's scene starts in the final video, measured on the frames rather than taken from the
# prompt (which asked for 0, 2, 4, 6.5, 9 and 11.5 s; the model did not keep to it). The script
# turns these into scroll positions by dividing by the video's length.
CHAPTERS = [
    {
        "title": "Software Development",
        "text": "Custom systems built around how your business actually runs.",
        "service": "custom-software-development",
        "at": 0.0,
    },
    {
        "title": "Web Development",
        "text": "Fast, accessible web platforms, from the first wireframe to launch.",
        "service": "web-development",
        "at": 4.5,
    },
    {
        "title": "Mobile App Development",
        "text": "iOS and Android apps that stay in sync with everything else you run.",
        "service": "mobile-application-development",
        "at": 6.83,
    },
    {
        "title": "Application Services",
        "text": "APIs, integrations, payments and monitoring, wired together and kept running.",
        "service": "application-services",
        "at": 9.0,
    },
    {
        "title": "Testing & Quality Assurance",
        "text": "Automated and manual testing, so problems are caught before customers see them.",
        "service": "testing-qa",
        "at": 12.17,
    },
]


def _variant(raw):
    frames = [static(path) for path in raw["frames"]]
    if len(frames) < MIN_FRAMES:
        raise ValueError(f"a hero variant needs at least {MIN_FRAMES} frames")
    return {
        "width": int(raw["width"]),
        "height": int(raw["height"]),
        "duration": float(raw["duration"]),
        "frames": frames,
        "poster": static(raw["poster"]),
        "end": static(raw["end"]),
    }


def _read_manifest():
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        logger.warning("The hero animation manifest exists but could not be read.", exc_info=True)
        return None
    try:
        return {"desktop": _variant(data["desktop"]), "mobile": _variant(data["mobile"])}
    except (KeyError, TypeError, ValueError):
        logger.warning("The hero animation frames are incomplete; the hero shows no animation.", exc_info=True)
        return None


def manifest():
    cached = cache.get(CACHE_KEY)
    if cached is None:
        cached = {"value": _read_manifest()}
        cache.set(CACHE_KEY, cached, CACHE_SECONDS)
    return cached["value"]


def context():
    """The frames (or None) and the chapters; the chapters render either way."""
    found = manifest()
    chapters = []
    for chapter in CHAPTERS:
        progress = chapter["at"] / found["desktop"]["duration"] if found else 0
        chapters.append({**chapter, "progress": round(progress, 4)})
    return {"hero_anim": found, "hero_chapters": chapters}
