import functools
import secrets
from decimal import ROUND_HALF_UP, Decimal

from django.core.cache import cache
from django.http import HttpResponse, JsonResponse


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


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
