import json

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.core.models import SiteSettings
from apps.core.uploads import validate_document
from apps.core.utils import format_npr, format_usd, make_reference, npr_to_usd, rate_limit

from . import engine
from .models import EstimatorEvent, ProjectInquiry, ProjectType


def start(request):
    return render(request, "estimator/estimator.html", {
        "timeline_choices": ProjectInquiry.TIMELINE_CHOICES,
        "team_choices": ProjectInquiry.TEAM_CHOICES,
        "design_choices": ProjectInquiry.DESIGN_CHOICES,
        "budget_choices": ProjectInquiry.BUDGET_CHOICES,
        "platform_choices": ProjectInquiry.PLATFORM_CHOICES,
    })


@require_GET
def config_api(request):
    types = ProjectType.objects.filter(is_active=True).prefetch_related("features")
    data = {
        "project_types": [
            {
                "key": t.key, "label": t.label, "description": t.description, "icon": t.icon,
                "features": [
                    {"key": f.key, "label": f.label, "help": f.help_text}
                    for f in t.features.all() if f.is_active
                ],
            }
            for t in types
        ],
    }
    return JsonResponse(data)


def _payload_to_estimate(payload):
    return engine.calculate(
        project_type_key=str(payload.get("project_type", "")),
        feature_keys=[str(k) for k in payload.get("features", [])][:60],
        platforms=[str(p) for p in payload.get("platforms", [])][:6],
        timeline=str(payload.get("timeline", "standard")),
        team_preference=str(payload.get("team_preference", "unsure")),
        design_needs=str(payload.get("design_needs", "existing")),
    )


def _serialize(result):
    rate = SiteSettings.load().exchange_rate_npr_per_usd
    return {
        "low_npr": int(result["low"]),
        "high_npr": int(result["high"]),
        "low_npr_display": format_npr(result["low"]),
        "high_npr_display": format_npr(result["high"]),
        "low_usd": int(npr_to_usd(result["low"], rate)),
        "high_usd": int(npr_to_usd(result["high"], rate)),
        "low_usd_display": format_usd(npr_to_usd(result["low"], rate)),
        "high_usd_display": format_usd(npr_to_usd(result["high"], rate)),
        "weeks_low": result["weeks_low"],
        "weeks_high": result["weeks_high"],
        "hours": result["hours"],
        "team": result["team"],
        "disclaimer": result["disclaimer"],
    }


@require_POST
@rate_limit("estimate-preview", limit=60, window=600)
def preview_api(request):
    try:
        payload = json.loads(request.body or "{}")
        result = _payload_to_estimate(payload)
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "Please choose a project type."}, status=400)
    return JsonResponse({"ok": True, "estimate": _serialize(result)})


class InquiryContactForm(forms.Form):
    name = forms.CharField(max_length=120)
    email = forms.EmailField()
    phone = forms.CharField(max_length=40, required=False)
    company = forms.CharField(max_length=160, required=False)
    country = forms.CharField(max_length=80, required=False)
    budget_band = forms.ChoiceField(choices=ProjectInquiry.BUDGET_CHOICES, required=False)
    description = forms.CharField(max_length=4000, required=False)
    document = forms.FileField(required=False)
    consent = forms.BooleanField(required=True)
    website = forms.CharField(required=False)

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise ValidationError("Spam check failed.")
        return ""

    def clean_document(self):
        doc = self.cleaned_data.get("document")
        if doc:
            validate_document(doc)
        return doc


@require_POST
@rate_limit("estimate-submit", limit=6, window=900)
def submit_api(request):
    try:
        answers = json.loads(request.POST.get("answers", "{}"))
        result = _payload_to_estimate(answers)
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "errors": {"project_type": ["Please choose a project type."]}}, status=400)

    form = InquiryContactForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)

    data = form.cleaned_data
    valid_timeline = dict(ProjectInquiry.TIMELINE_CHOICES)
    valid_team = dict(ProjectInquiry.TEAM_CHOICES)
    valid_design = dict(ProjectInquiry.DESIGN_CHOICES)
    inquiry = ProjectInquiry(
        reference=make_reference("PI"),
        project_type=result["project_type"],
        project_type_label=result["project_type"].label,
        features=result["features"],
        platforms=result["platforms"],
        timeline=answers.get("timeline") if answers.get("timeline") in valid_timeline else "standard",
        team_preference=answers.get("team_preference") if answers.get("team_preference") in valid_team else "unsure",
        design_needs=answers.get("design_needs") if answers.get("design_needs") in valid_design else "existing",
        budget_band=data.get("budget_band") or "unknown",
        description=data.get("description", ""),
        name=data["name"], email=data["email"], phone=data.get("phone", ""),
        company=data.get("company", ""), country=data.get("country", ""),
        estimate_low_npr=result["low"], estimate_high_npr=result["high"],
        estimate_weeks_low=result["weeks_low"], estimate_weeks_high=result["weeks_high"],
        estimate_hours=result["hours"], suggested_team=result["team"],
        exchange_rate=SiteSettings.load().exchange_rate_npr_per_usd,
        consent=True,
    )
    if data.get("document"):
        inquiry.document_name = data["document"].name[:255]
        inquiry.document = data["document"]
    inquiry.save()

    session_id = str(answers.get("session_id", ""))[:40]
    if session_id:
        EstimatorEvent.objects.get_or_create(session_id=session_id, step=8)

    send_mail(
        f"Your project estimate {inquiry.reference}",
        render_to_string("emails/inquiry_ack.txt", {"inquiry": inquiry}),
        settings.DEFAULT_FROM_EMAIL, [inquiry.email], fail_silently=True,
    )
    send_mail(
        f"New qualified lead {inquiry.reference}: {inquiry.project_type_label}",
        f"{inquiry.name} ({inquiry.company}) {inquiry.email}\nRange: {format_npr(inquiry.estimate_low_npr)} to {format_npr(inquiry.estimate_high_npr)}",
        settings.DEFAULT_FROM_EMAIL, [settings.INTERNAL_NOTIFY_EMAIL], fail_silently=True,
    )
    return JsonResponse({
        "ok": True,
        "reference": inquiry.reference,
        "estimate": _serialize(result),
        "consultation_url": reverse("core:consultation") + "?topic=new-project",
    })


@require_POST
@rate_limit("estimate-event", limit=120, window=600)
def event_api(request):
    try:
        payload = json.loads(request.body or "{}")
        step = int(payload.get("step", 0))
        session_id = str(payload.get("session_id", ""))[:40]
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({"ok": False}, status=400)
    if session_id and 1 <= step <= 8:
        EstimatorEvent.objects.get_or_create(session_id=session_id, step=step)
    return JsonResponse({"ok": True})
