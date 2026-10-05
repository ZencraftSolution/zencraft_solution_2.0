from django.conf import settings
from django.contrib import messages
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.blog.models import BlogPost
from apps.commerce.models import EngagementModel
from apps.portfolio.models import CaseStudy, TeamMember, Testimonial
from apps.services.models import Industry, Service, Technology

from .forms import ConsultationForm, ContactForm, NewsletterForm
from .models import NewsletterSubscriber
from .utils import rate_limit


def _unsplash(photo_id, w, h, q=75):
    return f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w={w}&h={h}&q={q}"


HERO_SLIDES = [
    {
        "label": "Healthcare", "industry": "healthcare", "tint": "#dfe5ff",
        "image": "photo-1576091160399-112ba8d25d1d", "background": "photo-1519494026892-80bbd2d6fd0d",
        "caption": "Hospital information system", "metric": "63% shorter OPD wait", "link": "Our healthcare work",
    },
    {
        "label": "Retail", "industry": "retail-ecommerce", "tint": "#e3e2ff",
        "image": "photo-1441986300917-64674bd600d8", "background": "photo-1441984904996-e0b6ba687e04",
        "caption": "Omnichannel commerce", "metric": "3.1x online revenue in a year", "link": "Our retail and e-commerce work",
    },
    {
        "label": "Logistics", "industry": "logistics", "tint": "#d9ebf8",
        "image": "photo-1586528116311-ad8dd3c8310d", "background": "photo-1601584115197-04ecc0da31d7",
        "caption": "Fleet tracking and dispatch", "metric": "2,300 deliveries tracked daily", "link": "Our logistics work",
    },
    {
        "label": "More industries", "industry": "education", "tint": "#e6e0ff",
        "image": "photo-1541339907198-e08756dedf3f", "background": "photo-1427504494785-3a9ca7044f45",
        "caption": "University learning platform", "metric": "46,000 students onboarded", "link": "Explore all industries",
    },
]


def _hero_slides():
    slides = []
    for i, s in enumerate(HERO_SLIDES):
        url = reverse("services:industries") if i == len(HERO_SLIDES) - 1 else reverse("services:industry_detail", args=[s["industry"]])
        slides.append({
            **s,
            "image_url": _unsplash(s["image"], 1200, 760),
            "background_url": _unsplash(s["background"], 1920, 1080, 60),
            "url": url,
        })
    return slides


def home(request):
    services = list(Service.objects.filter(is_published=True).order_by("order"))
    technologies = list(Technology.objects.all())
    terminal_lines = (
        [{"t": "prompt", "v": "zencraft --services --verbose"}, {"t": "dim", "v": "resolving capabilities..."}]
        + [{"t": "ok", "v": s.name, "k": s.nav_blurb} for s in services]
        + [
            {"t": "dim", "v": f"{len(services)} services ready. {len(technologies)} technologies in the stack."},
            {"t": "prompt", "v": "zencraft estimate --interactive"},
        ]
    )
    context = {
        "services": services,
        "hero_slides": _hero_slides(),
        "terminal_lines": terminal_lines,
        "case_studies": CaseStudy.objects.filter(is_published=True, featured=True).select_related("industry").prefetch_related("technologies")[:6],
        "testimonials": Testimonial.objects.filter(featured=True, verification="verified")[:6],
        "industries": Industry.objects.all()[:7],
        "technologies": technologies,
        "engagement_models": EngagementModel.objects.all()[:4],
        "posts": BlogPost.objects.filter(is_published=True).select_related("category")[:3],
        "process": [
            ("Discover", "Workshops with your stakeholders to map goals, users, risks and the first release."),
            ("Design", "Architecture decisions, clickable prototypes and a delivery plan you can hold us to."),
            ("Build", "Two-week sprints with a working demo at the end of each one."),
            ("Test", "Automated suites plus manual QA against real devices and real data volumes."),
            ("Deploy", "Infrastructure as code, staged rollouts and a rollback plan written before launch."),
            ("Support", "SLA-backed monitoring, fixes and a roadmap for the next version."),
        ],
    }
    return render(request, "core/home.html", context)


def about(request):
    return render(request, "core/about.html", {
        "leaders": TeamMember.objects.filter(is_leadership=True),
        "team": TeamMember.objects.filter(is_leadership=False),
        "testimonials": Testimonial.objects.filter(featured=True)[:3],
    })


@rate_limit("contact", limit=5, window=900)
def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        submission = form.save()
        send_mail(
            f"New contact message: {submission.subject}",
            f"From {submission.name} <{submission.email}>\nCompany: {submission.company}\n\n{submission.message}",
            settings.DEFAULT_FROM_EMAIL,
            [settings.INTERNAL_NOTIFY_EMAIL],
            fail_silently=True,
        )
        send_mail(
            "We received your message",
            render_to_string("emails/contact_ack.txt", {"submission": submission}),
            settings.DEFAULT_FROM_EMAIL,
            [submission.email],
            fail_silently=True,
        )
        messages.success(request, "Thanks. Your message is with our team and you will hear back within one working day.")
        return redirect("core:contact")
    return render(request, "core/contact.html", {"form": form})


@rate_limit("consultation", limit=5, window=900)
def consultation(request):
    form = ConsultationForm(request.POST or None, initial={"topic": request.GET.get("topic", "")})
    if request.method == "POST" and form.is_valid():
        booking = form.save()
        send_mail(
            "Consultation request received",
            render_to_string("emails/consultation_ack.txt", {"booking": booking}),
            settings.DEFAULT_FROM_EMAIL,
            [booking.email],
            fail_silently=True,
        )
        send_mail(
            f"New consultation request from {booking.name}",
            f"{booking.get_topic_display()} on {booking.preferred_date} ({booking.get_preferred_slot_display()})\n{booking.email} {booking.phone}\n\n{booking.message}",
            settings.DEFAULT_FROM_EMAIL,
            [settings.INTERNAL_NOTIFY_EMAIL],
            fail_silently=True,
        )
        return render(request, "core/consultation_done.html", {"booking": booking})
    return render(request, "core/consultation.html", {"form": form})


@require_POST
@rate_limit("newsletter", limit=5, window=900)
def newsletter_subscribe(request):
    form = NewsletterForm(request.POST)
    wants_json = request.headers.get("x-requested-with") == "fetch"
    if form.is_valid():
        NewsletterSubscriber.objects.update_or_create(email=form.cleaned_data["email"].lower(), defaults={"is_active": True})
        message = "You are subscribed. Expect one considered email a month."
        if wants_json:
            return JsonResponse({"ok": True, "message": message})
        messages.success(request, message)
    else:
        if wants_json:
            return JsonResponse({"ok": False, "message": "Please enter a valid email address."}, status=400)
        messages.error(request, "Please enter a valid email address.")
    return redirect(request.META.get("HTTP_REFERER") or "core:home")


def search(request):
    q = request.GET.get("q", "").strip()
    posts = cases = services = []
    if q:
        query = SearchQuery(q, search_type="websearch")
        posts = (
            BlogPost.objects.filter(is_published=True)
            .annotate(rank=SearchRank(SearchVector("title", weight="A") + SearchVector("excerpt", weight="B") + SearchVector("body", weight="C"), query))
            .filter(rank__gt=0.01).order_by("-rank")[:10]
        )
        cases = (
            CaseStudy.objects.filter(is_published=True)
            .annotate(rank=SearchRank(SearchVector("title", weight="A") + SearchVector("summary", weight="B") + SearchVector("challenge", "solution", weight="C"), query))
            .filter(rank__gt=0.01).order_by("-rank")[:10]
        )
        services = (
            Service.objects.filter(is_published=True)
            .annotate(rank=SearchRank(SearchVector("name", weight="A") + SearchVector("summary", weight="B") + SearchVector("intro", weight="C"), query))
            .filter(rank__gt=0.01).order_by("-rank")[:10]
        )
    total = len(posts) + len(cases) + len(services)
    return render(request, "core/search.html", {"q": q, "posts": posts, "cases": cases, "services": services, "total": total})


def legal(request, page):
    return render(request, f"core/legal_{page}.html", {"page": page})


def robots_txt(request):
    lines = [
        "User-agent: *",
        f"Disallow: /{settings.DASHBOARD_PATH}",
        "Disallow: /pricing/store/cart/",
        "Disallow: /pricing/store/checkout/",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def page_not_found(request, exception=None):
    return render(request, "404.html", status=404)


def server_error(request):
    return render(request, "500.html", status=500)
