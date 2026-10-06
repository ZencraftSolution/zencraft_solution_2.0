"""Allow-list sanitising for the one field the templates render with |safe.

Blog bodies are HTML written by staff and printed unescaped. A compromised or careless staff
account would otherwise be able to put a <script> on a public page, so the HTML is cleaned on
the way in, at save time, rather than trusted on the way out.
"""

import nh3

# Everything an article actually needs, and nothing that can execute.
ALLOWED_TAGS = {
    "p", "br", "hr", "span", "div",
    "h2", "h3", "h4", "h5",
    "ul", "ol", "li",
    "strong", "b", "em", "i", "u", "s", "sup", "sub", "small", "mark",
    "a", "img", "figure", "figcaption",
    "blockquote", "q", "cite",
    "code", "pre", "kbd", "samp",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption",
    "dl", "dt", "dd",
}

ALLOWED_ATTRIBUTES = {
    "*": {"class", "id", "title", "lang", "dir"},
    "a": {"href", "target"},  # rel is set by link_rel below, so it must not be listed here
    "img": {"src", "alt", "width", "height", "loading", "srcset", "sizes"},
    "th": {"colspan", "rowspan", "scope"},
    "td": {"colspan", "rowspan"},
    "ol": {"start", "type"},
    "time": {"datetime"},
}

# No javascript: or data: URLs, which are the usual way round an attribute allow-list.
ALLOWED_SCHEMES = {"http", "https", "mailto", "tel"}


def sanitise_html(value):
    """Returns the value with anything that could execute removed."""
    if not value:
        return value
    return nh3.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_SCHEMES,
        link_rel="noopener noreferrer",
        strip_comments=True,
    )
