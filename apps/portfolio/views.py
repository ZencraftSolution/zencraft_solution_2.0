from django.shortcuts import get_object_or_404, render

from apps.services.models import Industry

from .models import CaseStudy


def case_study_list(request):
    cases = CaseStudy.objects.filter(is_published=True).select_related("industry").prefetch_related("services", "technologies")
    industry = request.GET.get("industry")
    if industry:
        cases = cases.filter(industry__slug=industry)
    return render(request, "portfolio/list.html", {
        "cases": cases,
        "industries": Industry.objects.filter(case_studies__is_published=True).distinct(),
        "active_industry": industry,
    })


def case_study_detail(request, slug):
    case = get_object_or_404(
        CaseStudy.objects.select_related("industry").prefetch_related("services", "technologies", "images", "testimonials"),
        slug=slug, is_published=True,
    )
    more = CaseStudy.objects.filter(is_published=True).exclude(pk=case.pk).select_related("industry")[:2]
    return render(request, "portfolio/detail.html", {"case": case, "more": more, "testimonial": case.testimonials.first()})
