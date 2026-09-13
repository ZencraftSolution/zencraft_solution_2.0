"""Login throttling shared by every staff sign-in surface (the HQ dashboard and Django admin).

Failures are counted per client IP in one shared cache key, so an attacker cannot reset the
counter by switching between login pages.
"""
import functools

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

from .utils import client_ip, log_action

CACHE_PREFIX = "login-fail"


def max_failures():
    return getattr(settings, "LOGIN_MAX_FAILURES", 5)


def lockout_seconds():
    return getattr(settings, "LOGIN_LOCKOUT_SECONDS", 15 * 60)


def _key(request):
    return f"{CACHE_PREFIX}:{client_ip(request)}"


def failure_count(request):
    return cache.get(_key(request), 0)


def is_locked(request):
    return failure_count(request) >= max_failures()


def register_failure(request):
    key = _key(request)
    if cache.add(key, 1, lockout_seconds()):
        return 1
    try:
        return cache.incr(key)
    except ValueError:  # expired between add() and incr()
        cache.set(key, 1, lockout_seconds())
        return 1


def reset(request):
    cache.delete(_key(request))


def default_locked_response(request):
    minutes = max(1, lockout_seconds() // 60)
    return HttpResponse(
        f"Too many failed sign-in attempts. Please wait {minutes} minutes and try again.",
        status=429,
        content_type="text/plain; charset=utf-8",
    )


def throttle_login(view=None, *, locked_response=None):
    """Wraps a login view. POSTs are refused with HTTP 429 once the IP is locked out.

    A POST that ends in a redirect with an authenticated staff user counts as success and clears
    the counter. Any other POST outcome counts as a failure.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapped(request, *args, **kwargs):
            if request.method != "POST":
                return func(request, *args, **kwargs)
            if is_locked(request):
                return (locked_response or default_locked_response)(request)
            response = func(request, *args, **kwargs)
            user = getattr(request, "user", None)
            succeeded = response.status_code in (301, 302, 303) and user is not None and user.is_authenticated and user.is_staff
            if succeeded:
                reset(request)
            elif register_failure(request) == max_failures():
                log_action(request, "login locked out", None, detail=f"{max_failures()} failed attempts on {request.path}")
            return response

        return wrapped

    return decorator(view) if view is not None else decorator
