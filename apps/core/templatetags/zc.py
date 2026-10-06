import json
import random

from django import template
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.core import seo
from apps.core import structured_data as sd
from apps.core.models import SiteSettings
from apps.core.utils import format_npr, format_usd, npr_to_usd

register = template.Library()


def _rate(context):
    site = context.get("site") if context else None
    return (site or SiteSettings.load()).exchange_rate_npr_per_usd


@register.filter
def npr(value):
    return format_npr(value)


@register.simple_tag(takes_context=True)
def usd(context, value):
    return format_usd(npr_to_usd(value, _rate(context)))


@register.simple_tag(takes_context=True)
def price(context, value, suffix=""):
    """Renders NPR and USD together. The currency toggle decides which one leads."""
    if value in (None, ""):
        return ""
    usd_value = npr_to_usd(value, _rate(context))
    return format_html(
        '<span class="price"><span class="price__npr">{}</span><span class="price__usd">{}</span>{}</span>',
        format_npr(value),
        format_usd(usd_value),
        format_html('<span class="price__suffix">{}</span>', suffix) if suffix else "",
    )


@register.simple_tag(takes_context=True)
def price_range(context, low, high, suffix=""):
    rate = _rate(context)
    return format_html(
        '<span class="price"><span class="price__npr">{} to {}</span><span class="price__usd">{} to {}</span>{}</span>',
        format_npr(low),
        format_npr(high).replace("Rs. ", ""),
        format_usd(npr_to_usd(low, rate)),
        format_usd(npr_to_usd(high, rate)),
        format_html('<span class="price__suffix">{}</span>', suffix) if suffix else "",
    )


@register.filter
def lines(value):
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


@register.filter
def paragraphs(value):
    return [p.strip() for p in (value or "").split("\n\n") if p.strip()]


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def pad2(value):
    try:
        return f"{int(value):02d}"
    except (TypeError, ValueError):
        return value


@register.simple_tag(takes_context=True)
def json_ld(context, data):
    """Renders a structured-data block. Not executable, and not a place user input reaches."""
    # json.dumps escapes the content and "</" is broken up, so the payload cannot close the tag
    # early. The data comes from our own models, never from a request.
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    # A data block is never executed, so the nonce is not required; carrying it anyway keeps
    # "every script tag on the page has one" true, which is a far easier rule to check.
    request = context.get("request")
    nonce = f' nonce="{request.csp_nonce}"' if request is not None and hasattr(request, "csp_nonce") else ""
    return mark_safe(f'<script type="application/ld+json"{nonce}>{payload}</script>')  # noqa: S308  # nosec B308 B703 - escaped above


@register.simple_tag
def network_svg(seed=7, nodes=34, width=640, height=520):
    """Static fallback for the WebGL hero: a deterministic node network in thin blue lines."""
    rng = random.Random(seed)  # noqa: S311 - decorative geometry, deterministic on purpose
    pts = [(rng.uniform(40, width - 40), rng.uniform(40, height - 40)) for _ in range(nodes)]
    edges = []
    for i, (x1, y1) in enumerate(pts):
        near = sorted(range(nodes), key=lambda j: (pts[j][0] - x1) ** 2 + (pts[j][1] - y1) ** 2)[1:3]
        for j in near:
            if i < j:
                edges.append((i, j))
    line_markup = "".join(
        f'<line x1="{pts[i][0]:.1f}" y1="{pts[i][1]:.1f}" x2="{pts[j][0]:.1f}" y2="{pts[j][1]:.1f}"/>' for i, j in edges
    )
    node_markup = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{3 if k % 5 else 5}"/>' for k, (x, y) in enumerate(pts))
    return mark_safe(  # noqa: S308  # nosec B308 B703 - every value here is a float this function generated
        f'<svg class="hero-fallback" viewBox="0 0 {width} {height}" role="img" aria-label="Diagram of connected systems">'
        f'<g class="hero-fallback__edges">{line_markup}</g><g class="hero-fallback__nodes">{node_markup}</g></svg>'
    )


@register.simple_tag(takes_context=True)
def active(context, prefix):
    request = context.get("request")
    if request and request.path.startswith(prefix):
        return "is-active"
    return ""


@register.filter
def star_range(value):
    try:
        return range(int(value))
    except (TypeError, ValueError):
        return range(0)


@register.simple_tag(takes_context=True)
def page_title(context, primary, suffix=""):
    """The <title> for a page, trimmed to what a search result shows.

    Used instead of writing "X | Zencraft Solution" by hand in every template, which is how
    titles drifted to 104 characters and got cut off mid-sentence in the results.
    """
    site_settings = context.get("site")
    brand = getattr(site_settings, "company_name", "Zencraft Solution")
    return seo.compose_title(primary, brand, suffix)


@register.simple_tag
def page_description(value, fallback=""):
    """The meta description, trimmed on a word boundary."""
    return seo.compose_description(value, fallback)


@register.simple_tag(takes_context=True)
def canonical(context):
    """The absolute URL this page should be indexed under, without tracking parameters."""
    request = context.get("request")
    return seo.canonical_url(request) if request else ""


@register.simple_tag
def absolute_url(value):
    """Turns a stored path into an absolute URL, for og:image and structured data."""
    return seo.absolute(value)


@register.inclusion_tag("partials/share_meta.html", takes_context=True)
def share_meta(context, title, description, image=""):
    """Renders every Open Graph and Twitter tag from one title, description and image."""
    site_settings = context.get("site")
    return {
        "share_title": seo.truncate_title(title, 70),
        "share_description": seo.compose_description(description),
        "share_image": seo.absolute(image or getattr(site_settings, "share_image_src", "")),
        "share_image_alt": getattr(site_settings, "company_name", "Zencraft Solution"),
    }


@register.simple_tag(takes_context=True)
def schema(context, kind, obj=None, *extra):
    """Renders one structured-data block, built in apps/core/structured_data.py.

    Templates ask for a kind rather than writing JSON, so every page's blocks share one shape
    and the tests can assert on them.
    """
    site_settings = context.get("site")
    builders = {
        "organization": lambda: sd.organization(site_settings),
        "website": lambda: sd.website(site_settings),
        "service": lambda: sd.service(obj, site_settings),
        "article": lambda: sd.article(obj, site_settings),
        "case_study": lambda: sd.case_study(obj, site_settings),
        "job": lambda: sd.job_posting(obj, site_settings),
        "product": lambda: sd.product(obj, site_settings),
        "faq": lambda: sd.faq_page(obj or []),
    }
    data = builders[kind]()
    return json_ld(context, data) if data else ""


@register.inclusion_tag("partials/breadcrumbs.html", takes_context=True)
def breadcrumbs(context, *pairs):
    """Renders the visible trail and its BreadcrumbList from one list of label/URL pairs.

    Takes label, url, label, url, ... with an empty url for the page you are on. Keeping both
    outputs on one source is the point: a visible trail that disagrees with the structured data
    is worse than having neither.
    """
    items = [(pairs[i], _trail_url(pairs[i + 1])) for i in range(0, len(pairs) - 1, 2)]
    full = [("Home", reverse("core:home")), *items]
    return {"items": full, "json_ld": json_ld(context, sd.breadcrumbs(full))}


def _trail_url(value):
    """Accepts a URL name ("blog:list"), a path, or "" for the page you are already on."""
    if not value:
        return ""
    if ":" in value and "/" not in value:
        return reverse(value)
    return value


# Widths offered to the browser. A phone on a Nepali mobile network should not download a
# 1200px image to paint it 380px wide.
SRCSET_WIDTHS = (480, 768, 1200, 1600)


@register.simple_tag
def srcset(url, widths=None):
    """Builds a srcset for an image, when the host can resize it on request.

    Cloudinary and Unsplash both do. Anything else is returned empty, so the template falls back
    to the single src rather than offering the same file four times under four different widths.
    """
    if not url:
        return ""
    widths = widths or SRCSET_WIDTHS
    candidates = [(seo.image_at_width(url, width), width) for width in widths]
    usable = [(resized, width) for resized, width in candidates if resized]
    if not usable:
        return ""
    return mark_safe(", ".join(f"{resized} {width}w" for resized, width in usable))  # noqa: S308  # nosec B308 B703 - URLs built from our own data
