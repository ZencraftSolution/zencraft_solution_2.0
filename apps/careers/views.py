from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from apps.core.utils import make_reference, rate_limit
from apps.portfolio.models import GalleryImage

from .forms import EducationFormSet, ExperienceFormSet, JobApplicationForm, ProjectFormSet
from .models import Department, JobApplication, JobOpening

BENEFITS = [
    ("heartbeat", "Health cover for you and your family", "Group medical insurance from day one, including parents on request."),
    ("graduation-cap", "Yearly learning budget", "Rs. 60,000 a year for courses, certifications and conference tickets."),
    ("house-line", "Hybrid by default", "Most teams work from the Jhamsikhel office three days a week."),
    ("airplane-tilt", "Leave that is actually taken", "18 days of paid leave plus Dashain and Tihar festival leave."),
    ("chart-line-up", "Clear levels and reviews", "Published engineering levels and salary reviews every six months."),
    ("bowl-food", "Lunch on the house", "Daily team lunch in the office and snacks that are not an afterthought."),
]

VALUES = [
    ("Write it down", "Decisions, designs and trade-offs live in docs anyone can read. Nobody has to be in the right meeting."),
    ("Own the outcome", "You ship it, you watch it in production, you improve it. Tickets are not the finish line."),
    ("Review with care", "Every pull request gets a real review. We explain the why, not just the what."),
    ("Stay curious", "Friday afternoons are for learning sessions, internal tools and trying the thing you read about."),
]


def _open_jobs():
    today = timezone.localdate()
    return (
        JobOpening.objects.filter(is_active=True)
        .exclude(closing_date__lt=today)
        .select_related("department")
        .prefetch_related("tech_stack")
    )


def landing(request):
    jobs = _open_jobs()
    departments = []
    for dept in Department.objects.all():
        dept_jobs = [j for j in jobs if j.department_id == dept.pk]
        if dept_jobs:
            departments.append((dept, dept_jobs))
    return render(request, "careers/landing.html", {
        "departments": departments,
        "job_count": len(jobs),
        "benefits": BENEFITS,
        "values": VALUES,
        "gallery": GalleryImage.objects.filter(category__in=["team", "office", "events"])[:5],
    })


def job_list(request):
    jobs = _open_jobs()
    filters = {
        "department": request.GET.get("department", ""),
        "level": request.GET.get("level", ""),
        "type": request.GET.get("type", ""),
        "mode": request.GET.get("mode", ""),
    }
    if filters["department"]:
        jobs = jobs.filter(department__slug=filters["department"])
    if filters["level"]:
        jobs = jobs.filter(experience_level=filters["level"])
    if filters["type"]:
        jobs = jobs.filter(employment_type=filters["type"])
    if filters["mode"]:
        jobs = jobs.filter(work_mode=filters["mode"])
    return render(request, "careers/jobs.html", {
        "jobs": jobs,
        "filters": filters,
        "departments": Department.objects.all(),
        "levels": JobOpening.LEVEL_CHOICES,
        "types": JobOpening.TYPE_CHOICES,
        "modes": JobOpening.MODE_CHOICES,
    })


def job_detail(request, slug):
    job = get_object_or_404(JobOpening.objects.select_related("department").prefetch_related("tech_stack"), slug=slug, is_active=True)
    similar = _open_jobs().filter(department=job.department).exclude(pk=job.pk)[:3]
    return render(request, "careers/job_detail.html", {"job": job, "similar": similar})


@rate_limit("apply", limit=6, window=1800)
def apply(request, slug):
    job = get_object_or_404(JobOpening, slug=slug, is_active=True)
    if not job.is_open:
        return render(request, "careers/closed.html", {"job": job}, status=410)

    data = request.POST or None
    files = request.FILES or None
    form = JobApplicationForm(data, files, job=job)
    edu = EducationFormSet(data, prefix="edu", instance=JobApplication())
    exp = ExperienceFormSet(data, prefix="exp", instance=JobApplication())
    prj = ProjectFormSet(data, prefix="prj", instance=JobApplication())
    manual_error = ""

    if request.method == "POST":
        form_ok = form.is_valid()
        manual = form.cleaned_data.get("application_mode") == "manual" if form_ok else request.POST.get("application_mode") == "manual"
        sets_ok = True
        if manual:
            sets_ok = all([edu.is_valid(), exp.is_valid(), prj.is_valid()])
            if sets_ok:
                has_history = any(f.has_changed() for f in edu.forms) or any(f.has_changed() for f in exp.forms)
                if not has_history:
                    sets_ok = False
                    manual_error = "Add at least one education or work experience entry."
        if form_ok and sets_ok:
            with transaction.atomic():
                application = form.save(commit=False)
                application.job = job
                application.reference = make_reference("ZA")
                application.consent_at = timezone.now()
                if application.application_mode == "cv" and form.cleaned_data.get("cv"):
                    application.cv_original_name = form.cleaned_data["cv"].name[:255]
                else:
                    application.cv = ""
                application.save()
                if application.application_mode == "manual":
                    for formset in (edu, exp, prj):
                        formset.instance = application
                        formset.save()
            send_mail(
                f"We received your application for {job.title}",
                render_to_string("emails/application_ack.txt", {"application": application, "job": job}),
                settings.DEFAULT_FROM_EMAIL, [application.email], fail_silently=True,
            )
            send_mail(
                f"New application: {application.full_name} for {job.title}",
                f"{application.full_name} <{application.email}>, {application.years_experience} years, {application.get_application_mode_display()}",
                settings.DEFAULT_FROM_EMAIL, [settings.INTERNAL_NOTIFY_EMAIL], fail_silently=True,
            )
            request.session["last_application"] = {"ref": application.reference, "job": job.title, "name": application.full_name.split(" ")[0]}
            return redirect("careers:applied")

    return render(request, "careers/apply.html", {
        "job": job, "form": form, "edu": edu, "exp": exp, "prj": prj, "manual_error": manual_error,
    })


def applied(request):
    info = request.session.get("last_application")
    return render(request, "careers/applied.html", {"info": info})
