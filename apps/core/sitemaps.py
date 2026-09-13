from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.blog.models import BlogPost
from apps.careers.models import JobOpening
from apps.portfolio.models import CaseStudy
from apps.services.models import Industry, Service


class StaticSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return [
            "core:home", "services:list", "services:industries", "services:technologies", "portfolio:list",
            "commerce:pricing", "commerce:store", "estimator:start", "careers:landing", "careers:jobs",
            "blog:list", "core:about", "core:contact", "core:consultation", "core:privacy", "core:terms", "core:cookies",
        ]

    def location(self, item):
        return reverse(item)


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
    priority = 0.8

    def items(self):
        return CaseStudy.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at


class JobSitemap(Sitemap):
    priority = 0.6

    def items(self):
        return [job for job in JobOpening.objects.filter(is_active=True) if job.is_open]


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
