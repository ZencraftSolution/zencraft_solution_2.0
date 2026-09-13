from itertools import groupby

from django.shortcuts import get_object_or_404, render

from apps.commerce.models import EngagementModel

from .models import Industry, Service, Technology


def service_list(request):
    services = Service.objects.filter(is_published=True).select_related("category").prefetch_related("technologies")
    return render(request, "services/list.html", {"services": services, "engagement_models": EngagementModel.objects.all()})


def service_detail(request, slug):
    service = get_object_or_404(
        Service.objects.prefetch_related("steps", "technologies", "industries", "engagement_models", "related", "faqs"),
        slug=slug, is_published=True,
    )
    case_studies = service.case_studies.filter(is_published=True).select_related("industry")[:3]
    return render(request, "services/detail.html", {
        "service": service,
        "case_studies": case_studies,
        "faqs": service.faqs.all(),
        "related_services": service.related.filter(is_published=True)[:3],
    })


def industry_list(request):
    return render(request, "services/industries.html", {"industries": Industry.objects.prefetch_related("services")})


def industry_detail(request, slug):
    industry = get_object_or_404(Industry.objects.prefetch_related("services", "faqs"), slug=slug)
    return render(request, "services/industry_detail.html", {
        "industry": industry,
        "case_studies": industry.case_studies.filter(is_published=True)[:3],
        "others": Industry.objects.exclude(pk=industry.pk),
    })


def technology_list(request):
    techs = Technology.objects.all().order_by("category", "order", "name")
    labels = dict(Technology.CATEGORY_CHOICES)
    groups = [(key, labels.get(key, key), list(items)) for key, items in groupby(techs, key=lambda t: t.category)]
    return render(request, "services/technologies.html", {"groups": groups, "total": techs.count()})
