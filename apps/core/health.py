"""Liveness endpoint for the host's health check.

It touches the two things the site cannot serve a page without: the database and the cache.
Anything heavier (sending email, reaching a payment gateway) belongs in monitoring, not here;
a health check that calls a third party takes the site down whenever that third party blinks.
"""

import logging

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache

logger = logging.getLogger(__name__)
CACHE_PROBE_KEY = "healthz-probe"


def _check_database():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


def _check_cache():
    cache.set(CACHE_PROBE_KEY, "ok", 30)
    if cache.get(CACHE_PROBE_KEY) != "ok":
        raise RuntimeError("the cache accepted a write but did not return it")


@never_cache
def healthz(request):
    """200 with {"status": "ok"} while both work, 503 and the failing component otherwise."""
    results = {}
    for name, probe in (("database", _check_database), ("cache", _check_cache)):
        try:
            probe()
        except Exception as exc:
            logger.error("Health check failed for %s: %s", name, exc, exc_info=True)
            results[name] = "error"
        else:
            results[name] = "ok"

    healthy = all(value == "ok" for value in results.values())
    payload = {"status": "ok" if healthy else "degraded", "checks": results}
    return JsonResponse(payload, status=200 if healthy else 503)
