"""Downloads the Latin subsets of the three fonts and writes a self-hosted stylesheet.

Only latin and latin-ext are kept: the site is in English, and shipping Cyrillic, Greek and
Vietnamese subsets to every visitor in Nepal is bytes nobody uses.

All three are variable fonts. Google's stylesheet still lists one @font-face per weight, every one
pointing at the same file, and copying that faithfully put the same bytes on the site under a name
per weight: a first visit downloaded Geist three times and JetBrains Mono four, and a preload of
"geist-600" was a preload of a file the 400 face had already fetched under another name, which
Firefox reports as a preload "not used within a few seconds". So each family and subset is written
once, as a single face whose font-weight is the range of weights asked for. Text renders exactly
as before: within the range the browser picks the weight from the variable font, as it did, and a
weight outside it clamps to the nearest end, which is the face it would have picked before.
"""

import pathlib
import re
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "static" / "fonts"
FONT_DIR.mkdir(parents=True, exist_ok=True)

CSS_URL = (
    "https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600"
    "&family=JetBrains+Mono:wght@400;500;600;700"
    "&family=Space+Grotesk:wght@500;600&display=swap"
)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

KEEP = {"latin", "latin-ext"}


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": UA})  # noqa: S310  # nosec B310 - fixed https URL
    return urllib.request.urlopen(request, timeout=60).read()  # noqa: S310  # nosec B310 - fixed https URL


def collapse(css):
    """One face per (family, subset): [(family, subset, url, min_weight, max_weight, unicode_range)].

    In the order the families first appear, latin-ext before latin, as Google lists them.
    """
    faces = {}
    for subset, block in re.findall(r"/\* ([a-z-]+) \*/\s*(@font-face \{.*?\})", css, re.S):
        if subset not in KEEP:
            continue
        family = re.search(r"font-family: '([^']+)'", block).group(1)
        weight = int(re.search(r"font-weight: (\d+)", block).group(1))
        url = re.search(r"url\((https://[^)]+\.woff2)\)", block).group(1)
        unicode_range = re.search(r"unicode-range: ([^;]+);", block).group(1)
        face = faces.setdefault((family, subset), {"url": url, "weights": [], "range": unicode_range})
        if face["url"] != url:
            raise SystemExit(f"{family} {subset}: weights come from different files, so it is not one variable font")
        face["weights"].append(weight)
    return [(family, subset, f["url"], min(f["weights"]), max(f["weights"]), f["range"]) for (family, subset), f in faces.items()]


def filename(family, subset):
    return f"{family.lower().replace(' ', '-')}-{subset}.woff2"


def main():
    css = fetch(CSS_URL).decode()
    faces = collapse(css)
    blocks, sizes = [], {}
    for family, subset, url, low, high, unicode_range in faces:
        name = filename(family, subset)
        (FONT_DIR / name).write_bytes(fetch(url))
        sizes[name] = (FONT_DIR / name).stat().st_size
        weight = str(low) if low == high else f"{low} {high}"
        blocks.append(
            "@font-face {\n"
            f"  font-family: '{family}';\n"
            "  font-style: normal;\n"
            f"  font-weight: {weight};\n"
            "  font-display: swap;\n"
            f"  src: url('../fonts/{name}') format('woff2');\n"
            f"  unicode-range: {unicode_range};\n"
            "}"
        )

    header = (
        "/* Self-hosted so the browser does not have to resolve, connect to and fetch from two more\n"
        "   origins before any text can be painted. Latin subsets only: this site is in English.\n"
        "   Variable fonts, one file per family and subset; font-weight is the range in use.\n"
        "   Regenerated with scripts/fetch_fonts.py. */\n"
    )
    (ROOT / "static" / "css" / "fonts.css").write_text(header + "\n".join(blocks) + "\n", encoding="utf-8")

    print(f"{len(sizes)} font files, {sum(sizes.values()) / 1024:.0f} KB total")
    for name, size in sorted(sizes.items()):
        print(f"  {name:<34} {size / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
