from django.conf import settings
from django.core.cache import cache

from .models import SiteSettings


def site(request):
    from apps.services.models import Service

    nav_services = cache.get("nav-services")
    if nav_services is None:
        nav_services = list(Service.objects.filter(is_published=True).only("name", "slug", "icon", "nav_blurb").order_by("order"))
        cache.set("nav-services", nav_services, 120)

    cart = request.session.get("cart", {}) if hasattr(request, "session") else {}
    return {
        "site": SiteSettings.load(),
        "nav_services": nav_services,
        "cart_count": sum(int(q) for q in cart.values()) if cart else 0,
        "SITE_URL": settings.SITE_URL,
    }
