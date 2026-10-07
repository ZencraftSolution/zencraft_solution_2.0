import csv
import json
import mimetypes
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from apps.careers.models import ApplicationNote, JobApplication, JobOpening
from apps.careers.privacy import erase_application, export_application
from apps.commerce.models import Order
from apps.core.models import AuditLog, ConsultationBooking, ContactSubmission, Feedback, PageView, ScannedUpload, SiteSettings
from apps.core.throttle import throttle_login
from apps.core.uploads import upload_is_servable
from apps.core.utils import log_action
from apps.estimator.models import EstimatorConfig, EstimatorEvent, LeadNote, ProjectInquiry

from .forms import ApplicationUpdateForm, EstimatorConfigForm, LeadUpdateForm, NoteForm, OrderUpdateForm, SiteSettingsForm
from .mixins import SESSION_STARTED_KEY, needs_second_factor, staff_required

# A cell a spreadsheet would treat as a formula rather than as text. Applicant-supplied values
# end up in these exports, so "=HYPERLINK(...)" in a name field must not run when staff open it.
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_cell(value):
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(CSV_FORMULA_PREFIXES) else text


def write_csv_row(writer, values):
    writer.writerow([csv_cell(value) for value in values])


ESTIMATOR_STEPS = ["Project type", "Scope", "Platforms", "Timeline and team", "Design", "Contact details", "Estimate shown", "Lead submitted"]


def _dashboard_locked(request):
    return render(request, "dashboard/login.html", {"form": AuthenticationForm(request), "locked": True}, status=429)


@method_decorator(throttle_login(locked_response=_dashboard_locked), name="dispatch")
class DashboardLoginView(LoginView):
    """Staff sign-in. Lockout is shared with the Django admin login via apps.core.throttle."""

    template_name = "dashboard/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        if not user.is_staff:
            form.add_error(None, "Please enter a correct username and password.")
            return self.form_invalid(form)
        # django.contrib.auth.login() cycles the session key for us, so a session fixed before
        # sign-in cannot be reused afterwards. Stamp the start for the staff session timeout.
        response = super().form_valid(form)
        self.request.session[SESSION_STARTED_KEY] = timezone.now().timestamp()
        log_action(self.request, "signed in", user)
        return response

    def get_success_url(self):
        if needs_second_factor(self.request):
            return reverse("dashboard:two_factor")
        return super().get_success_url()


@require_POST
def dashboard_logout(request):
    if request.user.is_authenticated:
        log_action(request, "signed out", request.user)
    logout(request)
    return redirect("dashboard:login")


@staff_required
def overview(request):
    now = timezone.now()
    week = now - timedelta(days=7)
    paid = Order.objects.filter(payment_status="paid")
    leads = ProjectInquiry.objects.all()
    context = {
        "kpis": [
            ("New leads this week", leads.filter(created_at__gte=week).count(), "dashboard:leads"),
            ("Open pipeline", leads.exclude(status__in=["won", "lost"]).count(), "dashboard:leads"),
            ("Applications this week", JobApplication.objects.filter(created_at__gte=week).count(), "dashboard:applications"),
            ("Consultations requested", ConsultationBooking.objects.filter(status="requested").count(), None),
        ],
        "revenue_npr": paid.aggregate(total=Sum("total_npr"))["total"] or 0,
        "paid_orders": paid.count(),
        "unread_contacts": ContactSubmission.objects.filter(is_read=False).count(),
        "unread_feedback": Feedback.objects.filter(is_read=False).count(),
        "recent_leads": leads.select_related("assigned_to")[:6],
        "recent_applications": JobApplication.objects.select_related("job")[:6],
        "views_14": _daily_views(14),
    }
    return render(request, "dashboard/overview.html", context)


def _daily_views(days):
    start = timezone.now() - timedelta(days=days - 1)
    rows = (
        PageView.objects.filter(created_at__gte=start.replace(hour=0, minute=0, second=0))
        .annotate(day=TruncDate("created_at")).values("day").annotate(n=Count("id"))
    )
    counts = {r["day"]: r["n"] for r in rows}
    series = []
    for i in range(days):
        day = (start + timedelta(days=i)).date()
        series.append({"day": day, "n": counts.get(day, 0)})
    peak = max([s["n"] for s in series] + [1])
    for s in series:
        s["pct"] = round(s["n"] * 100 / peak)
    return series


# Leads -----------------------------------------------------------------

@staff_required
def leads_board(request):
    qs = ProjectInquiry.objects.select_related("assigned_to", "project_type")
    mine = request.GET.get("mine") == "1"
    if mine:
        qs = qs.filter(assigned_to=request.user)
    columns = [(code, label, [lead for lead in qs if lead.status == code]) for code, label in ProjectInquiry.STATUS_CHOICES]
    total = qs.count()
    won = qs.filter(status="won").count()
    return render(request, "dashboard/leads_board.html", {
        "columns": columns, "mine": mine, "total": total,
        "conversion": round(won * 100 / total, 1) if total else 0,
    })


@staff_required
def lead_detail(request, pk):
    lead = get_object_or_404(ProjectInquiry.objects.select_related("assigned_to", "project_type"), pk=pk)
    form = LeadUpdateForm(instance=lead)
    note_form = NoteForm()
    if request.method == "POST":
        if "add_note" in request.POST:
            note_form = NoteForm(request.POST)
            if note_form.is_valid():
                LeadNote.objects.create(inquiry=lead, author=request.user, body=note_form.cleaned_data["body"])
                log_action(request, "noted lead", lead)
                return redirect("dashboard:lead_detail", pk=pk)
        else:
            form = LeadUpdateForm(request.POST, instance=lead)
            if form.is_valid():
                form.save()
                log_action(request, "updated lead", lead, detail=", ".join(form.changed_data))
                messages.success(request, "Lead updated.")
                return redirect("dashboard:lead_detail", pk=pk)
    return render(request, "dashboard/lead_detail.html", {"lead": lead, "form": form, "note_form": note_form, "notes": lead.notes.select_related("author")})


@staff_required
def lead_document(request, pk):
    lead = get_object_or_404(ProjectInquiry, pk=pk)
    if not lead.document:
        raise Http404
    log_action(request, "downloaded requirement document", lead)
    return _private_file_response(lead.document, lead.document_name or "requirements", inline=False)


# Recruitment -------------------------------------------------------------

def _filtered_applications(request):
    qs = JobApplication.objects.select_related("job", "job__department").filter(purged_at__isnull=True)
    job = request.GET.get("job")
    if job:
        qs = qs.filter(job_id=job)
    exp = request.GET.get("exp")
    if exp == "0-1":
        qs = qs.filter(years_experience__lt=1)
    elif exp == "1-3":
        qs = qs.filter(years_experience__gte=1, years_experience__lt=3)
    elif exp == "3-6":
        qs = qs.filter(years_experience__gte=3, years_experience__lt=6)
    elif exp == "6+":
        qs = qs.filter(years_experience__gte=6)
    status = request.GET.get("status")
    if status:
        qs = qs.filter(status=status)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(full_name__icontains=q) | Q(email__icontains=q) | Q(skills__icontains=q) | Q(reference__iexact=q))
    return qs


@staff_required
def applications_board(request):
    qs = _filtered_applications(request)
    columns = [(code, label, [a for a in qs if a.status == code]) for code, label in JobApplication.STATUS_CHOICES]
    return render(request, "dashboard/applications_board.html", {
        "columns": columns, "jobs": JobOpening.objects.all(), "params": request.GET,
        "by_role": JobOpening.objects.annotate(n=Count("applications")).filter(n__gt=0).order_by("-n")[:6],
    })


@staff_required
def applications_list(request):
    qs = _filtered_applications(request)
    if request.method == "POST":
        ids = request.POST.getlist("ids")
        new_status = request.POST.get("bulk_status")
        if ids and new_status in dict(JobApplication.STATUS_CHOICES):
            updated = JobApplication.objects.filter(pk__in=ids).update(status=new_status, updated_at=timezone.now())
            log_action(request, "bulk updated applications", None, detail=f"{updated} set to {new_status}: {','.join(ids)}")
            messages.success(request, f"Updated {updated} applications.")
        return redirect(request.get_full_path())
    return render(request, "dashboard/applications_list.html", {
        "applications": qs[:500], "jobs": JobOpening.objects.all(), "params": request.GET,
        "statuses": JobApplication.STATUS_CHOICES,
    })


@staff_required
def applications_export(request):
    qs = _filtered_applications(request)
    log_action(request, "exported applications", None, detail=f"{qs.count()} rows")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="applications.csv"'
    writer = csv.writer(response)
    writer.writerow(["Reference", "Name", "Email", "Phone", "Role", "Mode", "Years", "Location", "Notice", "Expected salary", "Status", "Rating", "Applied"])
    for a in qs:
        write_csv_row(writer, [a.reference, a.full_name, a.email, a.phone, a.job.title, a.get_application_mode_display(), a.years_experience,
                               a.current_location, a.get_notice_period_display(), a.expected_salary_npr or "", a.get_status_display(), a.rating or "",
                               timezone.localtime(a.created_at).strftime("%Y-%m-%d")])
    return response


@staff_required
def application_detail(request, pk):
    app = get_object_or_404(JobApplication.objects.select_related("job"), pk=pk)
    log_action(request, "viewed application", app)
    form = ApplicationUpdateForm(instance=app)
    note_form = NoteForm()
    if request.method == "POST":
        if "add_note" in request.POST:
            note_form = NoteForm(request.POST)
            if note_form.is_valid():
                ApplicationNote.objects.create(application=app, author=request.user, body=note_form.cleaned_data["body"])
                return redirect("dashboard:application_detail", pk=pk)
        else:
            form = ApplicationUpdateForm(request.POST, instance=app)
            if form.is_valid():
                form.save()
                log_action(request, "updated application", app, detail=", ".join(form.changed_data))
                messages.success(request, "Application updated.")
                return redirect("dashboard:application_detail", pk=pk)
    return render(request, "dashboard/application_detail.html", {
        "app": app, "form": form, "note_form": note_form, "notes": app.notes.select_related("author"),
        "cv_scan": ScannedUpload.objects.filter(path=app.cv.name).first() if app.cv else None,
    })


@staff_required
def application_export(request, pk):
    """Everything held about one applicant, as a JSON file, for a subject access request."""
    app = get_object_or_404(JobApplication.objects.select_related("job"), pk=pk)
    log_action(request, "exported applicant data", app)
    payload = json.dumps(export_application(app), indent=2, ensure_ascii=False)
    response = HttpResponse(payload, content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="{app.reference}-data.json"'
    response["Cache-Control"] = "no-store"
    return response


# staff_required first, so a signed-out visitor is sent to the login page rather than being told
# which methods this endpoint accepts.
@staff_required
@require_POST
def application_erase(request, pk):
    """Erases one applicant's personal data on request, keeping the row for hiring statistics."""
    app = get_object_or_404(JobApplication.objects.select_related("job"), pk=pk)
    if app.purged_at:
        messages.info(request, "This application has already been erased.")
        return redirect("dashboard:application_detail", pk=pk)
    reference = app.reference
    erase_application(app)
    log_action(request, "erased applicant data", app, detail=f"on request, {reference}")
    messages.success(request, f"The personal data on {reference} has been erased. The role and outcome are kept.")
    return redirect("dashboard:application_detail", pk=pk)


@xframe_options_sameorigin  # framed by dashboard/application_detail.html for in-browser PDF preview
@staff_required
def application_cv(request, pk):
    app = get_object_or_404(JobApplication, pk=pk)
    if not app.cv:
        raise Http404
    inline = request.GET.get("download") != "1" and app.cv_is_pdf
    log_action(request, "opened CV" if inline else "downloaded CV", app)
    return _private_file_response(app.cv, app.cv_original_name or "cv", inline=inline)


def _private_file_response(field_file, filename, inline):
    if not upload_is_servable(field_file.name):
        # Taken in under quarantine and not cleared yet, or found to be infected. Either way it
        # does not go anywhere near a member of staff's machine.
        raise Http404("This file has not been released by the virus scan yet.")
    try:
        handle = field_file.open("rb")
    except FileNotFoundError:
        raise Http404("File missing from private storage") from None
    content_type = mimetypes.guess_type(field_file.name)[0] or "application/octet-stream"
    response = FileResponse(handle, content_type=content_type, as_attachment=not inline, filename=filename)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "no-store"
    return response


# Orders ------------------------------------------------------------------

@staff_required
def orders_list(request):
    orders = Order.objects.prefetch_related("items")
    status = request.GET.get("status")
    if status:
        orders = orders.filter(payment_status=status)
    return render(request, "dashboard/orders_list.html", {"orders": orders[:300], "statuses": Order.PAYMENT_STATUS, "status": status})


@staff_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related("items", "payments"), pk=pk)
    form = OrderUpdateForm(request.POST or None, instance=order)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "updated order", order, detail=", ".join(form.changed_data))
        messages.success(request, "Order updated.")
        return redirect("dashboard:order_detail", pk=pk)
    return render(request, "dashboard/order_detail.html", {"order": order, "form": form})


# Configuration ------------------------------------------------------------

@staff_required
def estimator_config(request):
    config = EstimatorConfig.load()
    form = EstimatorConfigForm(request.POST or None, instance=config)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "updated estimator config", config, detail=", ".join(form.changed_data))
        messages.success(request, "Estimator configuration saved. New estimates use these values immediately.")
        return redirect("dashboard:estimator_config")
    return render(request, "dashboard/estimator_config.html", {"form": form})


@staff_required
def site_settings(request):
    obj = SiteSettings.load()
    obj = SiteSettings.objects.get(pk=obj.pk)
    form = SiteSettingsForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "updated site settings", obj, detail=", ".join(form.changed_data))
        messages.success(request, "Settings saved.")
        return redirect("dashboard:settings")
    return render(request, "dashboard/settings.html", {"form": form})


@staff_required
def analytics(request):
    days = int(request.GET.get("days", 30)) if request.GET.get("days", "30").isdigit() else 30
    days = min(max(days, 7), 180)
    since = timezone.now() - timedelta(days=days)
    views = PageView.objects.filter(created_at__gte=since)

    top_pages = views.values("path").annotate(n=Count("id")).order_by("-n")[:12]
    service_pages = views.filter(path__startswith="/services/").exclude(path__in=["/services/", "/services/industries/", "/services/technologies/"]).values("path").annotate(n=Count("id")).order_by("-n")[:9]

    events = EstimatorEvent.objects.filter(created_at__gte=since)
    step_counts = dict(events.values_list("step").annotate(n=Count("id")))
    first = step_counts.get(1, 0) or 1
    funnel = []
    prev = None
    for i, label in enumerate(ESTIMATOR_STEPS, start=1):
        n = step_counts.get(i, 0)
        funnel.append({
            "step": i, "label": label, "n": n,
            "pct": round(n * 100 / first) if step_counts.get(1) else 0,
            "drop": round((prev - n) * 100 / prev) if prev else 0,
        })
        prev = n or None

    inquiries = ProjectInquiry.objects.filter(created_at__gte=since)
    total_inq = inquiries.count()
    won = inquiries.filter(status="won").count()

    return render(request, "dashboard/analytics.html", {
        "days": days,
        "total_views": views.count(),
        "unique_sessions": views.exclude(session_key="").values("session_key").distinct().count(),
        "daily": _daily_views(min(days, 30)),
        "top_pages": top_pages,
        "service_pages": service_pages,
        "funnel": funnel,
        "inquiries": total_inq,
        "won": won,
        "conversion": round(won * 100 / total_inq, 1) if total_inq else 0,
        "by_status": inquiries.values("status").annotate(n=Count("id")).order_by("status"),
        "apps_by_role": JobOpening.objects.annotate(n=Count("applications", filter=Q(applications__created_at__gte=since))).filter(n__gt=0).order_by("-n"),
    })


@staff_required
def audit_log(request):
    logs = AuditLog.objects.select_related("user")
    q = request.GET.get("q", "").strip()
    if q:
        logs = logs.filter(Q(action__icontains=q) | Q(object_repr__icontains=q) | Q(user__username__icontains=q))
    return render(request, "dashboard/audit_log.html", {"logs": logs[:400], "q": q})


@staff_required
def newsletter_export(request):
    from apps.core.models import NewsletterSubscriber

    log_action(request, "exported newsletter list", None)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="newsletter.csv"'
    writer = csv.writer(response)
    writer.writerow(["Email", "Active", "Subscribed"])
    for s in NewsletterSubscriber.objects.all():
        write_csv_row(writer, [s.email, s.is_active, timezone.localtime(s.created_at).strftime("%Y-%m-%d")])
    return response
