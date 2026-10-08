"""The scroll-driven exploded-view section on the home page.

The frames are generated art, not code, so they are not in the repository by default. This module
is the single place that answers "are the assets there?", and the home page renders the section
only when they are. Until then the page is exactly as it was: no empty band, no broken canvas, no
request for a file that does not exist.

Every frame URL is resolved here rather than built in JavaScript from a pattern. In production
WhiteNoise's manifest storage renames each file with a content hash, so "frame_0007.webp" is not
a URL the browser can guess; the server is the only thing that knows.

Build the frames with scripts/build_exploded_frames.py, which writes the manifest this reads.
"""

import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.templatetags.static import static

logger = logging.getLogger(__name__)

MANIFEST_PATH = settings.BASE_DIR / "static" / "img" / "exploded" / "manifest.json"
CACHE_KEY = "exploded-manifest"
CACHE_SECONDS = 300
MIN_FRAMES = 2

# The five layers, in the order they separate, top of the stack first. Each links to the service
# page that covers it; these are the real slugs, checked against the seeded services.
LAYERS = [
    {
        "title": "UI/UX Design",
        "text": "Research, wireframes and a design system before a line of code.",
        "service": "custom-software-development",
        "side": "left",
    },
    {
        "title": "Frontend Development",
        "text": "Interfaces that stay fast on the networks your customers actually use.",
        "service": "web-development",
        "side": "right",
    },
    {
        "title": "Backend & APIs",
        "text": "Services, integrations and the rules that keep your data correct.",
        "service": "application-services",
        "side": "left",
    },
    {
        "title": "Database & Data",
        "text": "Schemas that hold up, migrations that are safe, reporting you can trust.",
        "service": "data-analytics",
        "side": "right",
    },
    {
        "title": "Cloud & DevOps",
        "text": "Infrastructure as code, staged releases and monitoring from day one.",
        "service": "infrastructure-services",
        "side": "left",
    },
]


def _variant(raw):
    """One screen size's frames, turned into URLs the browser can actually request."""
    frames = [static(path) for path in raw["frames"]]
    if len(frames) < MIN_FRAMES:
        raise ValueError(f"an exploded-view variant needs at least {MIN_FRAMES} frames")
    return {"width": int(raw["width"]), "height": int(raw["height"]), "frames": frames}


def _read_manifest():
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        logger.warning("The exploded-view manifest exists but could not be read.", exc_info=True)
        return None

    try:
        return {
            "desktop": _variant(data["desktop"]),
            "mobile": _variant(data["mobile"]),
            "still": static(data["still"]),
            "still_mobile": static(data["still_mobile"]),
        }
    except (KeyError, TypeError, ValueError):
        # A missing file raises here too: manifest storage refuses to invent a URL for it.
        logger.warning("The exploded-view frames are incomplete; the section is hidden.", exc_info=True)
        return None


def manifest():
    """The frame manifest, or None when the artwork has not been generated yet.

    Cached, because this is a filesystem read plus a few hundred lookups on the busiest page on
    the site. The cache holds a wrapper dict so that "no artwork" is itself cacheable.
    """
    cached = cache.get(CACHE_KEY)
    if cached is None:
        cached = {"value": _read_manifest()}
        cache.set(CACHE_KEY, cached, CACHE_SECONDS)
    return cached["value"]


def context():
    """What the home page needs: the frames and the labels, or nothing at all."""
    found = manifest()
    if not found:
        return {"exploded": None}
    return {"exploded": found, "exploded_layers": LAYERS}
