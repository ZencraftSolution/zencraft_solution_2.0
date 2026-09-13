from django.conf import settings

from .models import PageView

SKIP_PREFIXES = ("/static/", "/media/", "/favicon", "/robots.txt", "/sitemap.xml")


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.dash_prefix = "/" + settings.DASHBOARD_PATH

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(self)")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if request.path.startswith(self.dash_prefix):
            response["X-Robots-Tag"] = "noindex, nofollow"
            response["Cache-Control"] = "no-store"
        return response


class PageViewMiddleware:
    """Records lightweight first-party page views for the dashboard analytics screen."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.dash_prefix = "/" + settings.DASHBOARD_PATH

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path
        if (
            request.method == "GET"
            and response.status_code == 200
            and "text/html" in response.get("Content-Type", "")
            and not path.startswith(SKIP_PREFIXES)
            and not path.startswith(self.dash_prefix)
            and "/api/" not in path
        ):
            try:
                PageView.objects.create(
                    path=path[:255],
                    referrer=request.META.get("HTTP_REFERER", "")[:255],
                    session_key=(request.session.session_key or "")[:64],
                )
            except Exception:  # analytics must never break a page
                pass
        return response
