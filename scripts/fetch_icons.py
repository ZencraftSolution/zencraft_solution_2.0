"""Downloads the Phosphor icon font and stylesheets so they are served from this site.

Why self-host rather than subset: icon names are data. Staff pick one per service, industry and
engagement model in the dashboard, and the estimator builds class names at runtime. A sprite
containing only today's 55 icons would render nothing the moment somebody chose a 56th, and would
do it silently. Self-hosting removes the third-party origin and lets WhiteNoise compress the
stylesheets and serve everything with an immutable cache header, which is most of the win.
"""

import pathlib
import re
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
VERSION = "2.1.1"
BASE = f"https://cdn.jsdelivr.net/npm/@phosphor-icons/web@{VERSION}/src"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

WEIGHTS = {"regular": "Phosphor", "fill": "Phosphor-Fill"}


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": UA})  # noqa: S310  # nosec B310 - fixed https URL
    return urllib.request.urlopen(request, timeout=120).read()  # noqa: S310  # nosec B310 - fixed https URL


font_dir = ROOT / "static" / "fonts"
font_dir.mkdir(parents=True, exist_ok=True)
sheets = []

for weight, font_name in WEIGHTS.items():
    woff2 = fetch(f"{BASE}/{weight}/{font_name}.woff2")
    (font_dir / f"{font_name}.woff2").write_bytes(woff2)

    css = fetch(f"{BASE}/{weight}/style.css").decode()
    # Keep only the woff2 source: every browser this site supports reads it, and the ttf and svg
    # fallbacks would otherwise be downloaded by nothing and shipped in the stylesheet forever.
    css = re.sub(r"src:\s*url\([^)]*\)[^;]*;", f"src: url('../fonts/{font_name}.woff2') format('woff2');", css, count=1)
    css = css.replace("font-display: block", "font-display: swap")
    if "font-display" not in css:
        css = css.replace("font-style: normal;", "font-style: normal;\n  font-display: swap;", 1)
    sheets.append(f"/* Phosphor {weight} */\n{css}")
    print(f"{weight}: {len(woff2) / 1024:.0f} KB font, {len(css) / 1024:.0f} KB css")

header = (
    f"/* Phosphor Icons {VERSION}, self-hosted. MIT licensed.\n"
    "   Regenerated with scripts/fetch_icons.py. See that file for why this is not a subset. */\n"
)
(ROOT / "static" / "css" / "icons.css").write_text(header + "\n".join(sheets), encoding="utf-8")
print("wrote static/css/icons.css")
