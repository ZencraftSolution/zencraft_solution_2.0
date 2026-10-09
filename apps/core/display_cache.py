"""A short-lived, per-process cache for what every public page displays.

The shared cache (CACHES["default"]) is the database in production, so even a cache *hit* is a
round trip to PostgreSQL. That is the right place for login lockouts and rate limits, which must be
shared by every worker. It is the wrong place for the navigation menu, the site settings and the
home page's content: they change a few times a week and are read on every request, and each read
cost as much as the query it was meant to save.

This keeps them in the worker's own memory (CACHES["local"], LocMemCache) for LOCAL_SECONDS. Saving
or deleting one of the models below clears it in the worker that handled the save at once; the
other workers pick the change up within LOCAL_SECONDS.
"""

from django.core.cache import caches
from django.db.models.signals import post_delete, post_save

LOCAL_SECONDS = 60

NAV_SERVICES = "display:nav-services"
SITE_SETTINGS = "display:site-settings"
HOME_CONTENT = "display:home-content"
KEYS = (NAV_SERVICES, SITE_SETTINGS, HOME_CONTENT)

# Saving any of these can change what the keys above hold.
WATCHED = (
    "core.SiteSettings",
    "services.Service", "services.Technology", "services.Industry",
    "portfolio.CaseStudy", "portfolio.Testimonial",
    "commerce.EngagementModel",
    "blog.BlogPost",
)


def local():
    return caches["local"]


def cached(key, build, seconds=LOCAL_SECONDS):
    """The value under `key`, built and stored on a miss. `build` must return something not None."""
    value = local().get(key)
    if value is None:
        value = build()
        local().set(key, value, seconds)
    return value


def clear(*args, **kwargs):
    """Drops everything this module caches. Usable as a signal receiver."""
    local().delete_many(KEYS)


def connect_signals():
    from django.apps import apps

    for label in WATCHED:
        model = apps.get_model(label)
        post_save.connect(clear, sender=model, dispatch_uid=f"display-cache-save-{label}")
        post_delete.connect(clear, sender=model, dispatch_uid=f"display-cache-delete-{label}")
