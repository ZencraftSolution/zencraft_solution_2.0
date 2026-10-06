"""Measures what a page costs to load, without needing Lighthouse.

Counts the requests a browser must make before it can paint, how many of those go to someone
else's server, and how many bytes of CSS and JS are involved. These are the numbers the
front-end work actually moves; Lighthouse's score is a weighted summary of them plus timings
that depend on the machine it runs on.

    python scripts/page_weight.py            # against http://127.0.0.1:8000
    python scripts/page_weight.py http://127.0.0.1:8099
"""

import gzip
import re
import sys
import urllib.parse
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
PAGES = ["/", "/services/web-development/", "/work/", "/insights/", "/careers/", "/pricing/"]
UA = {"User-Agent": "zencraft-page-weight/1.0", "Accept-Encoding": "gzip"}


def fetch(url):
    request = urllib.request.Request(url, headers=UA)  # noqa: S310  # nosec B310 - a URL this script was pointed at
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310  # nosec B310 - local URL
        raw = response.read()
    return gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw, len(raw)


def report(path):
    html, html_bytes = fetch(BASE + path)
    text = html.decode("utf-8", "replace")

    stylesheets = re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"', text)
    scripts = re.findall(r'<script[^>]+src="([^"]+)"', text)
    images = re.findall(r"<img[^>]+>", text)

    third_party = set()
    blocking_bytes = 0
    for href in stylesheets:
        host = urllib.parse.urlsplit(href).netloc
        if host and host not in BASE:
            third_party.add(host)
            continue  # not fetched: a third party's size is not ours to report
        _, size = fetch(urllib.parse.urljoin(BASE, href))
        blocking_bytes += size
    for src in scripts:
        host = urllib.parse.urlsplit(src).netloc
        if host and host not in BASE:
            third_party.add(host)

    deferred = len(re.findall(r"<script[^>]+(?:defer|async)[^>]*>", text))
    lazy = sum(1 for img in images if 'loading="lazy"' in img)
    responsive = sum(1 for img in images if "srcset=" in img and 'srcset=""' not in img)
    sized = sum(1 for img in images if "width=" in img and "height=" in img)

    return {
        "path": path,
        "html_kb": html_bytes / 1024,
        "css_js_kb": blocking_bytes / 1024,
        "stylesheets": len(stylesheets),
        "scripts": len(scripts),
        "deferred": deferred,
        "third_party": len(third_party),
        "images": len(images),
        "lazy": lazy,
        "srcset": responsive,
        "sized": sized,
        "hosts": sorted(third_party),
    }


rows = [report(path) for path in PAGES]
print(f"{'page':<28} {'html':>7} {'css+js':>8} {'css':>4} {'js':>3} {'def':>4} {'3rd':>4} "
      f"{'img':>4} {'lazy':>5} {'srcset':>7} {'sized':>6}")
for row in rows:
    print(f"{row['path']:<28} {row['html_kb']:>6.1f}K {row['css_js_kb']:>7.1f}K {row['stylesheets']:>4} "
          f"{row['scripts']:>3} {row['deferred']:>4} {row['third_party']:>4} {row['images']:>4} "
          f"{row['lazy']:>5} {row['srcset']:>7} {row['sized']:>6}")

hosts = sorted({host for row in rows for host in row["hosts"]})
print("\nthird-party origins:", ", ".join(hosts) if hosts else "none")
unsized = [row["path"] for row in rows if row["sized"] != row["images"]]
print("pages with an image missing width/height:", ", ".join(unsized) if unsized else "none")
