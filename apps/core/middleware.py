import logging
import secrets

from django.conf import settings

from .models import PageView

logger = logging.getLogger(__name__)

SKIP_PREFIXES = ("/static/", "/media/", "/favicon", "/robots.txt", "/sitemap.xml", "/healthz")


class ContentSecurityPolicyMiddleware:
    """Builds a per-request CSP with a fresh nonce for the few inline scripts the site needs.

    Templates write nonce="{{ request.csp_nonce }}". Anything injected into a page, for example
    through a compromised staff account, has no nonce and is refused by the browser.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.header = (
            "Content-Security-Policy-Report-Only" if settings.CSP_REPORT_ONLY else "Content-Security-Policy"
        )

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)
        response = self.get_response(request)
        response.setdefault(self.header, self.policy(request.csp_nonce))
        return response

    def policy(self, nonce):
        parts = []
        for directive, sources in settings.CSP_DIRECTIVES.items():
            rendered = [source.replace("{nonce}", f"'nonce-{nonce}'") for source in sources]
            parts.append(" ".join([directive, *rendered]).strip())
        if not settings.DEBUG:
            # Anything that slips through as http is fetched over https instead of being blocked.
            parts.append("upgrade-insecure-requests")
        if settings.CSP_REPORT_URI:
            parts.append(f"report-uri {settings.CSP_REPORT_URI}")
        return "; ".join(parts)


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


def is_speculative(request):
    """A page the browser loaded in the background in case the visitor clicks (prefetch or
    prerender, from the speculation rules in base.html). Not a visit; main.js reports one if the
    page is then shown."""
    return "prefetch" in request.headers.get("Sec-Purpose", "") or request.headers.get("Purpose", "") == "prefetch"


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
            and not is_speculative(request)
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
                logger.warning("Could not record a page view for %s", path, exc_info=True)
        return response
