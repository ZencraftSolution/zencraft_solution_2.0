"""One switch for the public shop.

A decorator rather than an unmounted URLconf, so the routes keep resolving. {% url %} in a
template and reverse() in a test still work, the pages simply answer 404, and switching the
shop back on needs no code change.
"""

import functools

from django.conf import settings
from django.http import Http404


def store_enabled():
    return getattr(settings, "STORE_ENABLED", False)


def store_only(view):
    """404s a public shop page while STORE_ENABLED is off."""

    @functools.wraps(view)
    def wrapped(request, *args, **kwargs):
        if not store_enabled():
            raise Http404("The online store is not open.")
        return view(request, *args, **kwargs)

    return wrapped
