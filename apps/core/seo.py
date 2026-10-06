"""Shared SEO helpers: canonical URLs, length limits and a tiny HTML reader for the crawl test.

The limits are not arbitrary. Google truncates a title at roughly 600 pixels, which is about 60
characters, and a description at about 160. Below 30 and 70 respectively there is usually not
enough there to tell one page from another, which is the thing that actually costs rankings.
"""

import re
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit

from django.conf import settings

TITLE_MIN, TITLE_MAX = 30, 60
DESCRIPTION_MIN, DESCRIPTION_MAX = 70, 160

# Parameters that identify a visit, not a page. Keeping them in the canonical URL splits one
# page's ranking across every campaign that ever linked to it.
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "gclid", "gbraid", "wbraid", "fbclid", "msclkid", "ttclid", "igshid", "mc_cid", "mc_eid",
    "ref", "referrer", "source", "_ga", "_gl", "yclid", "twclid",
}
# Parameters that really do change what is on the page, so they belong in the canonical URL.
MEANINGFUL_PARAMS = {"page", "q", "industry", "category", "tag", "department", "level", "type", "mode"}


def site_url():
    return settings.SITE_URL.rstrip("/")


def canonical_url(request):
    """The absolute URL this page should be indexed under.

    Built from SITE_URL rather than the Host header, so a request that arrives on the Render
    subdomain, on www, or on a preview host still points search engines at the real address.
    """
    query = {
        key: value
        for key, value in sorted(request.GET.items())
        if key in MEANINGFUL_PARAMS and key not in TRACKING_PARAMS and value
    }
    suffix = f"?{urlencode(query)}" if query else ""
    return f"{site_url()}{request.path}{suffix}"


def absolute(path_or_url):
    """Turns a stored path or relative URL into an absolute one. Leaves absolute URLs alone."""
    if not path_or_url:
        return ""
    if urlsplit(path_or_url).scheme in {"http", "https"}:
        return path_or_url
    return f"{site_url()}/{str(path_or_url).lstrip('/')}"


def truncate_title(value, limit=TITLE_MAX):
    """Shortens on a word boundary, so a title is never cut mid-word in a search result."""
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,.;:-")
    return f"{cut}…"


def truncate_description(value, limit=DESCRIPTION_MAX):
    text = re.sub(r"<[^>]+>", " ", value or "")
    return truncate_title(text, limit)


def compose_title(primary, brand, suffix=""):
    """Builds "<page> | <section> | <brand>", dropping parts until it fits a search result.

    The brand goes last and is the first thing sacrificed: a case study headline earns the space
    more than a company name the reader has already seen on every other result.
    """
    primary = " ".join((primary or "").split())
    candidates = []
    if suffix:
        candidates.append(" | ".join([primary, suffix, brand]))
    candidates.append(" | ".join([primary, brand]))
    if suffix:
        candidates.append(" | ".join([primary, suffix]))
    candidates.append(primary)
    for candidate in candidates:
        if len(candidate) <= TITLE_MAX:
            return candidate
    return truncate_title(primary)


def compose_description(value, fallback=""):
    """Trims a description to the length a search result shows, on a word boundary."""
    text = " ".join(re.sub(r"<[^>]+>", " ", value or "").split()) or fallback
    return truncate_description(text)


# Hosts that resize an image when asked, and how to ask them.
def image_at_width(url, width):
    """The same image at a given width, or "" when the host cannot resize it.

    Returning "" rather than the original is deliberate: a srcset that offers one 1.5 MB file at
    four widths makes the page slower, not faster, because the browser trusts the descriptors.
    """
    if not url:
        return ""
    if "res.cloudinary.com" in url and "/upload/" in url:
        head, _, tail = url.partition("/upload/")
        tail = re.sub(r"^(w_\d+|c_[a-z]+|q_[a-z0-9]+|f_[a-z]+)(,[^/]*)?/", "", tail)
        return f"{head}/upload/c_limit,w_{width},q_auto,f_auto/{tail}"
    if "images.unsplash.com" in url:
        base = url.split("?")[0]
        return f"{base}?auto=format&fit=crop&w={width}&q=75"
    return ""


class PageParser(HTMLParser):
    """Collects just enough of a page to check it: headings, images, links and meta tags.

    A real parser rather than regular expressions, because "does every image have alt text" is
    exactly the kind of question regular expressions get subtly wrong.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.headings = []  # (level, text)
        self.images = []  # dict of attributes
        self.meta = {}  # name or property -> content
        self.canonical = ""
        self.json_ld = []
        self.html_lang = ""
        self._capture = None
        self._buffer = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "html":
            self.html_lang = attributes.get("lang", "")
        elif tag == "title":
            self._capture = "title"
            self._buffer = []
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._capture = tag
            self._buffer = []
        elif tag == "img":
            self.images.append(attributes)
        elif tag == "meta":
            key = attributes.get("name") or attributes.get("property")
            if key:
                self.meta[key] = attributes.get("content", "")
        elif tag == "link" and attributes.get("rel") == "canonical":
            self.canonical = attributes.get("href", "")
        elif tag == "script" and attributes.get("type") == "application/ld+json":
            self._capture = "json_ld"
            self._buffer = []

    def handle_data(self, data):
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if not self._capture:
            return
        text = "".join(self._buffer).strip()
        if self._capture == "title" and tag == "title":
            self.title = " ".join(text.split())
        elif self._capture == "json_ld" and tag == "script":
            self.json_ld.append(text)
        elif self._capture == tag:
            self.headings.append((int(tag[1]), " ".join(text.split())))
        else:
            return
        self._capture = None
        self._buffer = []

    @property
    def description(self):
        return self.meta.get("description", "")

    @property
    def robots(self):
        return self.meta.get("robots", "")

    def heading_gaps(self):
        """Levels that jump by more than one, for example an h1 followed by an h3.

        Assistive software uses the heading outline to move around a page, and a skipped level
        reads as a missing section.
        """
        gaps = []
        previous = None
        for level, text in self.headings:
            if previous is not None and level > previous + 1:
                gaps.append((previous, level, text))
            previous = level
        return gaps


def parse(html):
    parser = PageParser()
    parser.feed(html)
    return parser
