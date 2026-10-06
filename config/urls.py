from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.core import health as core_health
from apps.core import views as core_views
from apps.core.sitemaps import SITEMAPS
from apps.core.throttle import throttle_login

DASH = settings.DASHBOARD_PATH

admin.site.site_header = "Zencraft Solution"

if settings.STAFF_2FA_REQUIRED:
    # Staff accounts are managed in the Django admin, so it has to be behind the same second
    # factor as the dashboard. OTPAdminSite asks for the code at its own login and refuses a
    # session that has not passed it.
    from django_otp.admin import OTPAdminSite

    admin.site.__class__ = OTPAdminSite

urlpatterns = [
    # Django admin is kept because staff user accounts are only manageable there. Its login is
    # routed through the same IP lockout as the HQ login; this pattern must stay above admin.site.urls
    # so it shadows the unthrottled admin:login route at the same path.
    path(f"{DASH}django-admin/login/", throttle_login(admin.site.login), name="admin_login_throttled"),
    path(f"{DASH}django-admin/", admin.site.urls),
    path(DASH, include("apps.dashboard.urls")),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("robots.txt", core_views.robots_txt, name="robots"),
    path("healthz/", core_health.healthz, name="healthz"),
    path("services/", include("apps.services.urls")),
    path("work/", include("apps.portfolio.urls")),
    path("pricing/", include("apps.commerce.urls")),
    path("estimate/", include("apps.estimator.urls")),
    path("careers/", include("apps.careers.urls")),
    path("insights/", include("apps.blog.urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"
