"""Checks the live site after a deploy: no localhost in what search engines read, and healthy.

    python scripts/check_live_site.py https://zencraftsolution.com

Fails (exit 1) when
  - the home page's canonical link or og:url is missing or points at localhost / 127.0.0.1,
  - robots.txt has no Sitemap line, or one points at localhost / 127.0.0.1,
  - /healthz/ does not answer 200 (retried a few times: a site that has just deployed may still
    be starting).

A SITE_URL left at its development default produces exactly these symptoms on an otherwise
working site, which is why it is worth a check of its own: the deploy check in the build stops
the obvious case, this catches whatever reaches production anyway. Standard library only, so it
runs on a bare CI runner. Used by .github/workflows/live-site.yml.
"""

import argparse
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser

LOCAL_MARKERS = ("localhost", "127.0.0.1")
USER_AGENT = "zencraft-live-site-check/1.0"
HEALTH_ATTEMPTS = 6
HEALTH_DELAY_SECONDS = 15
TIMEOUT_SECONDS = 30


def fetch(url):
    """(status, body) for a GET. HTTP errors are answers, not exceptions; no answer is status 0."""
    # Only web addresses: urlopen would also read file: and other schemes.
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"not an http(s) URL: {url!r}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310  # nosec B310 - http(s) only, checked above
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310  # nosec B310 - http(s) only, checked above
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, str(exc)


class _HeadLinks(HTMLParser):
    """Collects <link rel="canonical" href> and <meta property="og:url" content>."""

    def __init__(self):
        super().__init__()
        self.canonical = None
        self.og_url = None

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "link" and "canonical" in a.get("rel", "").lower().split() and self.canonical is None:
            self.canonical = a.get("href", "")
        if tag == "meta" and a.get("property", "").lower() == "og:url" and self.og_url is None:
            self.og_url = a.get("content", "")


def head_links(html):
    parser = _HeadLinks()
    parser.feed(html)
    return parser.canonical, parser.og_url


def sitemap_lines(robots):
    return [line.split(":", 1)[1].strip() for line in robots.splitlines() if line.lower().startswith("sitemap:")]


def is_local(url):
    return any(marker in url.lower() for marker in LOCAL_MARKERS)


def check(base_url, fetch=fetch, sleep=time.sleep):
    """Every problem found, as human-readable lines. Empty means the site passed."""
    base = base_url.rstrip("/")
    problems = []

    status, html = fetch(f"{base}/")
    if status != 200:
        problems.append(f"the home page answered {status or 'nothing'}, so its tags could not be checked")
    else:
        canonical, og_url = head_links(html)
        for name, value in (("canonical link", canonical), ("og:url", og_url)):
            if not value:
                problems.append(f"the home page has no {name}")
            elif is_local(value):
                problems.append(f"the home page {name} points at a local address: {value}")

    status, robots = fetch(f"{base}/robots.txt")
    if status != 200:
        problems.append(f"robots.txt answered {status or 'nothing'}")
    else:
        lines = sitemap_lines(robots)
        if not lines:
            problems.append("robots.txt has no Sitemap line")
        problems += [f"robots.txt Sitemap points at a local address: {line}" for line in lines if is_local(line)]

    for attempt in range(1, HEALTH_ATTEMPTS + 1):
        status, body = fetch(f"{base}/healthz/")
        if status == 200:
            break
        if attempt < HEALTH_ATTEMPTS:
            sleep(HEALTH_DELAY_SECONDS)
    else:
        problems.append(f"/healthz/ answered {status or 'nothing'} after {HEALTH_ATTEMPTS} attempts: {body[:200]}")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("base_url", help="the live site, e.g. https://zencraftsolution.com")
    args = parser.parse_args(argv)
    if not args.base_url.startswith(("http://", "https://")):
        print(f"Not a URL: {args.base_url!r}. Set the LIVE_SITE_URL repository variable to the site's address.")
        return 1
    problems = check(args.base_url)
    for problem in problems:
        print(f"FAIL: {problem}")
    if not problems:
        print(f"OK: {args.base_url} has no local addresses in its canonical, og:url or sitemap, and /healthz/ is 200.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
