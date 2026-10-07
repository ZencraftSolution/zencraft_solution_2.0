"""Sitemaps.

Everything that can carry a lastmod does, because a crawler that can tell what changed spends
its budget on those pages rather than re-reading the rest. Nothing noindex appears here: a page
in the sitemap that asks not to be indexed is a contradiction Search Console reports as an error.
"""

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.db.models import Max
from django.urls import reverse

from apps.blog.models import BlogPost
from apps.careers.models import JobOpening
from apps.portfolio.models import CaseStudy
from apps.services.models import Industry, Service


class StaticSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    # The pages a visitor can reach that are not driven by a single record. Cart, checkout, order,
    # search and the application steps are deliberately absent: they are all noindex.
    PAGES = [
        "core:home", "services:list", "services:industries", "services:technologies", "portfolio:list",
        "estimator:start", "careers:landing", "careers:jobs",
        "blog:list", "core:about", "core:contact", "core:consultation", "core:privacy", "core:terms", "core:cookies",
    ]
    # Offered only while the shop is open; closed, these answer 404.
    STORE_PAGES = ["commerce:pricing", "commerce:store"]

    def items(self):
        return self.PAGES + (self.STORE_PAGES if settings.STORE_ENABLED else [])

    def location(self, item):
        return reverse(item)

    def priority_for(self, item):
        return 1.0 if item == "core:home" else self.priority

    def lastmod(self, item):
        """Listing pages change when their content does, which is the only honest date here."""
        if item in {"services:list", "services:industries"}:
            return Service.objects.aggregate(latest=Max("updated_at"))["latest"]
        if item == "portfolio:list":
            return CaseStudy.objects.filter(is_published=True).aggregate(latest=Max("updated_at"))["latest"]
        if item == "blog:list":
            return BlogPost.objects.filter(is_published=True).aggregate(latest=Max("published_at"))["latest"]
        if item in {"careers:landing", "careers:jobs"}:
            return JobOpening.objects.filter(is_active=True).aggregate(latest=Max("posted_at"))["latest"]
        return None


class ServiceSitemap(Sitemap):
    priority = 0.9

    def items(self):
        return Service.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at


class IndustrySitemap(Sitemap):
    priority = 0.6

    def items(self):
        return Industry.objects.all()


class CaseStudySitemap(Sitemap):
    """The cover image is emitted by templates/sitemap.xml, so this work reaches image search too."""

    priority = 0.8

    def items(self):
        return CaseStudy.objects.filter(is_published=True).select_related("industry")

    def lastmod(self, obj):
        return obj.updated_at


class JobSitemap(Sitemap):
    priority = 0.6
    changefreq = "daily"  # a role that has closed should stop being offered quickly

    def items(self):
        return [job for job in JobOpening.objects.filter(is_active=True) if job.is_open]

    def lastmod(self, obj):
        return obj.posted_at


class BlogSitemap(Sitemap):
    priority = 0.6

    def items(self):
        return BlogPost.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.published_at


SITEMAPS = {
    "static": StaticSitemap,
    "services": ServiceSitemap,
    "industries": IndustrySitemap,
    "work": CaseStudySitemap,
    "jobs": JobSitemap,
    "insights": BlogSitemap,
}
