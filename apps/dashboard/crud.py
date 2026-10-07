"""Registry-driven CRUD for content the team edits often. One config per model keeps the dashboard consistent."""
from django import forms
from django.contrib import messages
from django.db import models
from django.db.models import Q
from django.forms import modelform_factory
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.blog.models import BlogCategory, BlogPost
from apps.careers.models import Department, JobOpening
from apps.commerce.models import EngagementModel, FixedPriceRange, ProductizedService, RoleRate
from apps.core.models import ConsultationBooking, ContactSubmission, Feedback, NewsletterSubscriber
from apps.core.utils import log_action
from apps.estimator.models import FeatureOption, ProjectType
from apps.portfolio.models import CaseStudy, CaseStudyImage, GalleryImage, TeamMember, Testimonial
from apps.services.models import FAQ, Industry, ProcessStep, Service, ServiceCategory, Technology

from .mixins import staff_required

REGISTRY = {
    "services": dict(model=Service, group="Content", title="Services", columns=["name", "category", "order", "featured", "is_published"], search=["name", "summary"]),
    "service-categories": dict(model=ServiceCategory, group="Content", title="Service categories", columns=["name", "order"], search=["name"]),
    "process-steps": dict(model=ProcessStep, group="Content", title="Process steps", columns=["service", "order", "title"], search=["title", "service__name"]),
    "industries": dict(model=Industry, group="Content", title="Industries", columns=["name", "tagline", "order"], search=["name"]),
    "technologies": dict(model=Technology, group="Content", title="Technologies", columns=["name", "category", "proficiency"], search=["name"]),
    "faqs": dict(model=FAQ, group="Content", title="FAQs", columns=["question", "content_type", "object_id", "order"], search=["question", "answer"]),
    "case-studies": dict(model=CaseStudy, group="Portfolio", title="Case studies", columns=["title", "client_name", "industry", "year", "featured", "is_published"], search=["title", "client_name"]),
    "case-study-images": dict(model=CaseStudyImage, group="Portfolio", title="Case study images", columns=["case_study", "caption", "order"], search=["caption"]),
    "testimonials": dict(model=Testimonial, group="Portfolio", title="Testimonials", columns=["client_name", "company", "rating", "verification", "featured"], search=["client_name", "company", "content"]),
    "team": dict(model=TeamMember, group="Portfolio", title="Team members", columns=["name", "role", "is_leadership", "order"], search=["name", "role"]),
    "gallery": dict(model=GalleryImage, group="Portfolio", title="Gallery", columns=["caption", "category", "order"], search=["caption"]),
    "blog-posts": dict(model=BlogPost, group="Insights", title="Blog posts", columns=["title", "category", "is_published", "published_at"], search=["title", "excerpt"]),
    "blog-categories": dict(model=BlogCategory, group="Insights", title="Blog categories", columns=["name", "order"], search=["name"]),
    "jobs": dict(model=JobOpening, group="Recruitment", title="Job openings", columns=["title", "department", "experience_level", "work_mode", "is_active", "closing_date"], search=["title"]),
    "departments": dict(model=Department, group="Recruitment", title="Departments", columns=["name", "order"], search=["name"]),
    "engagement-models": dict(model=EngagementModel, group="Commercial", title="Engagement models", columns=["name", "kind", "order"], search=["name"]),
    "role-rates": dict(model=RoleRate, group="Commercial", title="Rate card", columns=["role", "experience_band", "hourly_rate_npr", "monthly_rate_npr"], search=["role"]),
    "fixed-ranges": dict(model=FixedPriceRange, group="Commercial", title="Fixed-price ranges", columns=["project_type", "min_npr", "max_npr", "typical_timeline"], search=["project_type"]),
    "products": dict(model=ProductizedService, group="Commercial", title="Productized services", columns=["name", "tier_label", "category", "price_npr", "billing", "is_active"], search=["name"]),
    "project-types": dict(model=ProjectType, group="Estimator", title="Project types", columns=["label", "key", "base_hours", "is_active"], search=["label"]),
    "features": dict(model=FeatureOption, group="Estimator", title="Feature options", columns=["label", "key", "hours", "is_active"], search=["label"]),
    "consultations": dict(model=ConsultationBooking, group="Inbox", title="Consultation bookings", columns=["name", "company", "topic", "preferred_date", "preferred_slot", "status"], search=["name", "company", "email"]),
    "contacts": dict(model=ContactSubmission, group="Inbox", title="Contact messages", columns=["name", "subject", "email", "is_read", "created_at"], search=["name", "email", "subject", "message"]),
    "feedback": dict(model=Feedback, group="Inbox", title="Feedback", columns=["name", "rating", "company", "may_publish", "is_read", "created_at"], search=["name", "email", "company", "message"]),
    "newsletter": dict(model=NewsletterSubscriber, group="Inbox", title="Newsletter subscribers", columns=["email", "is_active", "created_at"], search=["email"]),
}


def nav_groups():
    groups = {}
    for slug, cfg in REGISTRY.items():
        groups.setdefault(cfg["group"], []).append((slug, cfg["title"]))
    return groups


def _config(slug):
    cfg = REGISTRY.get(slug)
    if not cfg:
        raise Http404
    return cfg


def _widget_for(field):
    if isinstance(field, models.ManyToManyField):
        return forms.CheckboxSelectMultiple
    if isinstance(field, models.TextField):
        return forms.Textarea(attrs={"rows": 5})
    if isinstance(field, models.JSONField):
        return forms.Textarea(attrs={"rows": 6, "class": "is-code"})
    if isinstance(field, models.DateTimeField):
        return forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")
    if isinstance(field, models.DateField):
        return forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    return None


def _form_class(model):
    names, widgets = [], {}
    for f in model._meta.get_fields():
        if f.auto_created or not getattr(f, "editable", False) or getattr(f, "primary_key", False):
            continue
        if not (getattr(f, "concrete", False) or f.many_to_many):
            continue
        names.append(f.name)
        widget = _widget_for(f)
        if widget:
            widgets[f.name] = widget
    return modelform_factory(model, fields=names, widgets=widgets)


def _cell(obj, name):
    value = getattr(obj, name)
    field = obj._meta.get_field(name)
    if getattr(field, "choices", None):
        return getattr(obj, f"get_{name}_display")()
    return value


@staff_required
def crud_list(request, slug):
    cfg = _config(slug)
    model = cfg["model"]
    qs = model.objects.all()
    q = request.GET.get("q", "").strip()
    if q:
        cond = Q()
        for field in cfg["search"]:
            cond |= Q(**{f"{field}__icontains": q})
        qs = qs.filter(cond)
    rows = [(obj, [_cell(obj, c) for c in cfg["columns"]]) for obj in qs[:300]]
    headers = [model._meta.get_field(c).verbose_name.capitalize() for c in cfg["columns"]]
    return render(request, "dashboard/crud_list.html", {"cfg": cfg, "slug": slug, "rows": rows, "headers": headers, "q": q, "count": qs.count()})


@staff_required
def crud_edit(request, slug, pk=None):
    cfg = _config(slug)
    model = cfg["model"]
    instance = get_object_or_404(model, pk=pk) if pk else None
    FormClass = _form_class(model)
    form = FormClass(request.POST or None, request.FILES or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        log_action(request, "updated" if pk else "created", obj, detail=f"{cfg['title']}: {', '.join(form.changed_data)}")
        messages.success(request, f"Saved {obj}.")
        if "save_continue" in request.POST:
            return redirect("dashboard:crud_edit", slug=slug, pk=obj.pk)
        return redirect("dashboard:crud_list", slug=slug)
    public_url = instance.get_absolute_url() if instance is not None and hasattr(instance, "get_absolute_url") else ""
    return render(request, "dashboard/crud_form.html", {"cfg": cfg, "slug": slug, "form": form, "instance": instance, "public_url": public_url})


@staff_required
def crud_delete(request, slug, pk):
    cfg = _config(slug)
    obj = get_object_or_404(cfg["model"], pk=pk)
    if request.method == "POST":
        label = str(obj)
        try:
            obj.delete()
        except models.ProtectedError:
            messages.error(request, f"{label} is still referenced by other records and cannot be deleted.")
            return redirect("dashboard:crud_list", slug=slug)
        log_action(request, "deleted", None, detail=f"{cfg['title']}: {label}")
        messages.success(request, f"Deleted {label}.")
        return redirect(reverse("dashboard:crud_list", args=[slug]))
    return render(request, "dashboard/crud_delete.html", {"cfg": cfg, "slug": slug, "obj": obj})
