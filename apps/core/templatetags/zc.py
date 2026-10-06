import json
import random

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

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


@register.simple_tag
def json_ld(data):
    """Renders a structured-data block. Not executable, and not a place user input reaches."""
    # json.dumps escapes the content and "</" is broken up, so the payload cannot close the tag
    # early. The data comes from our own models, never from a request.
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return mark_safe(f'<script type="application/ld+json">{payload}</script>')  # noqa: S308  # nosec B308 B703 - escaped above


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
