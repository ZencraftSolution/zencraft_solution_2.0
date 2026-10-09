from django.conf import settings

from . import display_cache
from .models import SiteSettings


def site(request):
    from apps.services.models import Service

    nav_services = display_cache.cached(display_cache.NAV_SERVICES, lambda: list(
        Service.objects.filter(is_published=True).only("name", "slug", "icon", "nav_blurb").order_by("order")
    ))

    cart = request.session.get("cart", {}) if hasattr(request, "session") else {}
    return {
        "site": SiteSettings.load(),
        "nav_services": nav_services,
        "cart_count": sum(int(q) for q in cart.values()) if cart else 0,
        "SITE_URL": settings.SITE_URL,
        "store_enabled": settings.STORE_ENABLED,
    }
