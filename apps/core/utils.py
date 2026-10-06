import functools
import ipaddress
import secrets
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils.http import url_has_allowed_host_and_scheme


def _clean_ip(value):
    """Returns a valid IP address, or None. Anything else in the header is not trusted."""
    candidate = (value or "").strip()
    if not candidate:
        return None
    if candidate.startswith("["):  # [2001:db8::1]:443
        candidate = candidate.partition("]")[0].lstrip("[")
    elif candidate.count(":") == 1:  # 203.0.113.9:443, but never a bare IPv6
        candidate = candidate.rpartition(":")[0]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def client_ip(request):
    """Client IP for rate limiting, login lockouts and audit logs.

    X-Forwarded-For is only honoured when TRUSTED_PROXY_COUNT says how many reverse proxies
    append to it; otherwise any visitor could spoof the header and dodge IP-keyed lockouts.
    Each proxy appends the address it received the request from, so with N trusted proxies
    the real client is the Nth entry counted from the right. Entries to the left of that are
    whatever the client sent and are ignored.

    Getting this wrong is not cosmetic: too low and every visitor shares one proxy address, so
    one failed login locks out the world; too high and the value is attacker-controlled.
    """
    remote = _clean_ip(request.META.get("REMOTE_ADDR")) or ""
    proxies = getattr(settings, "TRUSTED_PROXY_COUNT", 0)
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if proxies > 0 and forwarded:
        parts = [p for p in (p.strip() for p in forwarded.split(",")) if p]
        if len(parts) >= proxies:
            trusted = _clean_ip(parts[-proxies])
            if trusted:
                return trusted
    return remote


def safe_referer(request, fallback):
    """The page to return to after a form post, but only when it is one of ours.

    The Referer header is set by the client, so sending someone back to it unchecked turns any
    form on the site into an open redirect that phishing can borrow the domain's good name for.
    """
    referer = request.META.get("HTTP_REFERER") or ""
    allowed = url_has_allowed_host_and_scheme(
        referer, allowed_hosts={request.get_host(), *settings.ALLOWED_HOSTS}, require_https=request.is_secure()
    )
    return referer if allowed else fallback


def rate_limit(key, limit=5, window=600, methods=("POST",)):
    """Simple fixed-window rate limiter keyed by client IP. Returns HTTP 429 when exceeded."""

    def decorator(view):
        @functools.wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method in methods:
                cache_key = f"rl:{key}:{client_ip(request)}"
                added = cache.add(cache_key, 1, window)
                if not added:
                    try:
                        count = cache.incr(cache_key)
                    except ValueError:
                        cache.set(cache_key, 1, window)
                        count = 1
                    if count > limit:
                        message = "Too many submissions. Please wait a few minutes and try again."
                        if request.headers.get("x-requested-with") == "fetch" or request.content_type == "application/json":
                            return JsonResponse({"ok": False, "error": message}, status=429)
                        return HttpResponse(message, status=429)
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


def make_reference(prefix):
    return f"{prefix}-{secrets.token_hex(3).upper()}"


def format_npr(value, with_symbol=True):
    """South Asian digit grouping: 800000 -> 8,00,000."""
    if value is None or value == "":
        return ""
    amount = Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    negative = amount < 0
    digits = str(abs(int(amount)))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups) + "," + tail
    text = ("-" if negative else "") + digits
    return f"Rs. {text}" if with_symbol else text


def npr_to_usd(value, rate):
    if value is None or not rate:
        return None
    return (Decimal(value) / Decimal(rate)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def format_usd(value):
    if value is None:
        return ""
    return f"${int(value):,}"


def log_action(request, action, obj=None, detail=""):
    from .models import AuditLog

    user = getattr(request, "user", None)
    AuditLog.objects.create(
        user=user if user and user.is_authenticated else None,
        action=action,
        object_type=obj.__class__.__name__ if obj is not None else "",
        object_id=str(getattr(obj, "pk", "") or ""),
        object_repr=str(obj)[:255] if obj is not None else "",
        detail=detail,
        path=request.path[:255],
        ip_address=client_ip(request),
    )
