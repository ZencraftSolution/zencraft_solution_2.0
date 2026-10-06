"""Downloads the Latin subsets of the three fonts and writes a self-hosted stylesheet.

Only latin and latin-ext are kept: the site is in English, and shipping Cyrillic, Greek and
Vietnamese subsets to every visitor in Nepal is bytes nobody uses.
"""

import pathlib
import re
import urllib.request

ROOT = pathlib.Path(r"C:\Users\kheml\OneDrive\Desktop\Django Project\trae-ai\my_personal_apps\earn_project\zencraft_solution_2.0")
FONT_DIR = ROOT / "static" / "fonts"
FONT_DIR.mkdir(parents=True, exist_ok=True)

CSS_URL = (
    "https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600"
    "&family=JetBrains+Mono:wght@400;500;600;700"
    "&family=Space+Grotesk:wght@500;600&display=swap"
)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

KEEP = {"latin", "latin-ext"}

request = urllib.request.Request(CSS_URL, headers={"User-Agent": UA})
css = urllib.request.urlopen(request, timeout=60).read().decode()  # noqa: S310  # nosec B310 - fixed https URL

blocks = re.findall(r"/\* ([a-z-]+) \*/\s*(@font-face \{.*?\})", css, re.S)
kept, downloaded = [], {}

for subset, block in blocks:
    if subset not in KEEP:
        continue
    url = re.search(r"url\((https://[^)]+\.woff2)\)", block).group(1)
    family = re.search(r"font-family: '([^']+)'", block).group(1)
    weight = re.search(r"font-weight: (\d+)", block).group(1)
    filename = f"{family.lower().replace(' ', '-')}-{weight}-{subset}.woff2"
    target = FONT_DIR / filename
    if filename not in downloaded:
        req = urllib.request.Request(url, headers={"User-Agent": UA})  # noqa: S310  # nosec B310 - fixed https URL
        target.write_bytes(urllib.request.urlopen(req, timeout=60).read())  # noqa: S310  # nosec B310
        downloaded[filename] = target.stat().st_size
    kept.append(re.sub(r"url\(https://[^)]+\)", f"url('../fonts/{filename}')", block))

header = (
    "/* Self-hosted so the browser does not have to resolve, connect to and fetch from two more\n"
    "   origins before any text can be painted. Latin subsets only: this site is in English.\n"
    "   Regenerated with scripts/fetch_fonts.py. */\n"
)
(ROOT / "static" / "css" / "fonts.css").write_text(header + "\n".join(kept) + "\n", encoding="utf-8")

total = sum(downloaded.values())
print(f"{len(downloaded)} font files, {total / 1024:.0f} KB total")
for name, size in sorted(downloaded.items()):
    print(f"  {name:<34} {size / 1024:6.1f} KB")
