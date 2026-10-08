r"""Turns the home-page hero video into the WebP frame sequences the hero scrubs through.

    python scripts/build_hero_frames.py hero.mp4

Writes static/img/hero-anim/{desktop,mobile}/frame_NNNN.webp, a poster (the first frame, the
image the hero shows before anything else has loaded), an end-state image (the last frame, what
reduced motion shows), and manifest.json, which apps/core/hero_anim.py reads.

The bottom of every frame is trimmed (CROP_BOTTOM): the generated clip carries a few lines of
illegible pseudo-text in its bottom-left corner, which is exactly where the headline sits, and
nothing on the page may be text inside an image.

Needs ffmpeg: on PATH, in the FFMPEG environment variable, or from the imageio-ffmpeg package.
"""

import argparse
import json
import pathlib
import shutil
import subprocess  # nosec B404 - runs a local ffmpeg on a file the developer named
import tempfile

from build_exploded_frames import ffmpeg_binary
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "img" / "hero-anim"
STATIC_PREFIX = "img/hero-anim"

CROP_BOTTOM = 0.12
VARIANTS = {
    "desktop": {"frames": 150, "width": 1600, "quality": 72},
    "mobile": {"frames": 90, "width": 900, "quality": 70},
}
POSTER_QUALITY = 86


def decode(video, into):
    subprocess.run(  # noqa: S603  # nosec B603 - fixed argument list, no shell
        [ffmpeg_binary(), "-v", "error", "-i", str(video), "-vsync", "0", str(into / "%05d.png")],
        check=True,
    )
    return sorted(into.glob("*.png"))


def prepare(source, width):
    with Image.open(source) as im:
        im = im.convert("RGB")
        im = im.crop((0, 0, im.width, round(im.height * (1 - CROP_BOTTOM))))
        return im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)


def build_variant(name, frames, settings, duration):
    target = OUT / name
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    count = settings["frames"]
    step = (len(frames) - 1) / (count - 1)
    paths = []
    for i in range(count):
        im = prepare(frames[round(i * step)], settings["width"])
        filename = f"frame_{i + 1:04d}.webp"
        im.save(target / filename, "WEBP", quality=settings["quality"], method=6)
        paths.append(f"{STATIC_PREFIX}/{name}/{filename}")

    # The poster and the end state are the first and last frames at a higher quality: the poster
    # is the hero's first paint and has to look right on its own.
    stills = {}
    for key, source in (("poster", frames[0]), ("end", frames[-1])):
        filename = f"{key}_{name}.webp"
        prepare(source, settings["width"]).save(OUT / filename, "WEBP", quality=POSTER_QUALITY, method=6)
        stills[key] = f"{STATIC_PREFIX}/{filename}"

    total = sum(f.stat().st_size for f in target.glob("*.webp"))
    print(f"{name}: {count} frames at {im.width}x{im.height}, {total / 1024 / 1024:.2f} MB")
    return {"width": im.width, "height": im.height, "duration": duration, "frames": paths, **stills}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("video", type=pathlib.Path)
    parser.add_argument("--fps", type=float, default=24, help="frame rate of the video")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        frames = decode(args.video, pathlib.Path(tmp))
        duration = round(len(frames) / args.fps, 3)
        manifest = {name: build_variant(name, frames, settings, duration) for name, settings in VARIANTS.items()}

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    for f in sorted(OUT.glob("*.webp")):
        print(f"{f.name}: {f.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
