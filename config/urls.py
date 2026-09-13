from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.core.sitemaps import SITEMAPS
from apps.core import views as core_views

DASH = settings.DASHBOARD_PATH

admin.site.site_header = "Zencraft Solution"

urlpatterns = [
    path(f"{DASH}django-admin/", admin.site.urls),
    path(DASH, include("apps.dashboard.urls")),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("robots.txt", core_views.robots_txt, name="robots"),
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
