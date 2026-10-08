r"""Turns the exploded-view videos into the WebP frame sequences the home page scrubs through.

    python scripts/build_exploded_frames.py \
        --desktop desktop.mp4 --desktop-keys 0,1.75,2.3,2.55,2.8,3.6,5.04 \
        --mobile mobile.mp4 --mobile-keys 0,1.5,2.0,2.4,2.75,3.1,5.04 \
        --still desktop_end.png --still-mobile mobile_end.png \
        --poster desktop_start.png --poster-mobile mobile_start.png

Why frames and not the video: a <video> cannot be scrubbed smoothly by scroll position. Browsers
seek to the nearest keyframe, so scrolling back up stutters, and iOS will not decode a frame it was
not asked to play. Still images drawn on a canvas show exactly the frame the scroll asks for, in
either direction.

The keys retime the video. A generated clip never paces itself evenly: the screen takes a second
and a half to lift, then three layers appear in half a second. Each key is the moment, in seconds,
that something arrives: the start, each of the five layers in order, and the end. Frames are
chosen so that key k lands at k/6 of the scroll, which is exactly when static/js/exploded.js shows
label k. Read the keys off a contact sheet of the clip; without them the clip plays as recorded.

Writes static/img/exploded/{desktop,mobile}/frame_NNNN.webp, the stills, and manifest.json, which
apps/core/exploded.py reads. Delete the manifest and the section disappears from the page.

Needs ffmpeg: on PATH, in the FFMPEG environment variable, or from the imageio-ffmpeg package.
"""

import argparse
import json
import os
import pathlib
import shutil
import subprocess  # nosec B404 - runs a local ffmpeg on files the developer named
import tempfile

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "img" / "exploded"
STATIC_PREFIX = "img/exploded"

# Enough frames that a slow scroll never shows a jump, few enough to stay under the page budget.
VARIANTS = {
    "desktop": {"frames": 100, "width": 1600, "quality": 72},
    "mobile": {"frames": 72, "width": 800, "quality": 72},
}
STILL_QUALITY = 80


def ffmpeg_binary():
    found = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
    except ImportError:
        raise SystemExit("ffmpeg not found: install it, set FFMPEG, or pip install imageio-ffmpeg") from None
    return imageio_ffmpeg.get_ffmpeg_exe()


def decode(video, into):
    """Every frame of the video as a PNG, in order."""
    subprocess.run(  # noqa: S603  # nosec B603 - fixed argument list, no shell
        [ffmpeg_binary(), "-v", "error", "-i", str(video), "-vsync", "0", str(into / "%05d.png")],
        check=True,
    )
    frames = sorted(into.glob("*.png"))
    if len(frames) < 2:
        raise SystemExit(f"{video} decoded to {len(frames)} frames")
    return frames


def pick(frames, count, keys, fps):
    """count frames from first to last, both ends included, with the keys spaced evenly.

    A slowed-down stretch of the clip asks for the same source frame more than once; it is
    written once and listed as often as it is needed, and the browser downloads it once.
    """
    keys = keys or [0, (len(frames) - 1) / fps]
    segments = len(keys) - 1
    chosen = []
    for i in range(count):
        u = i / (count - 1) * segments
        s = min(int(u), segments - 1)
        at = keys[s] + (keys[s + 1] - keys[s]) * (u - s)
        chosen.append(frames[min(len(frames) - 1, max(0, round(at * fps)))])
    return chosen


def save_webp(source, target, width, quality):
    with Image.open(source) as im:
        im = im.convert("RGB")
        if im.width != width:
            im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        im.save(target, "WEBP", quality=quality, method=6)
        return im.size


def build_variant(name, video, settings, keys, fps):
    target = OUT / name
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    with tempfile.TemporaryDirectory() as tmp:
        chosen = pick(decode(video, pathlib.Path(tmp)), settings["frames"], keys, fps)
        written = {}
        paths = []
        size = None
        for frame in chosen:
            if frame not in written:
                filename = f"frame_{len(written) + 1:04d}.webp"
                size = save_webp(frame, target / filename, settings["width"], settings["quality"])
                written[frame] = f"{STATIC_PREFIX}/{name}/{filename}"
            paths.append(written[frame])

    total = sum(f.stat().st_size for f in target.glob("*.webp"))
    print(f"{name}: {len(paths)} frames ({len(written)} distinct) at {size[0]}x{size[1]}, {total / 1024:.0f} KB")
    return {"width": size[0], "height": size[1], "frames": paths}


def build_still(source, filename, width):
    save_webp(source, OUT / filename, width, STILL_QUALITY)
    print(f"{filename}: {(OUT / filename).stat().st_size / 1024:.0f} KB")
    return f"{STATIC_PREFIX}/{filename}"


def seconds(text):
    keys = [float(k) for k in text.split(",")]
    if len(keys) < 2 or keys != sorted(keys):
        raise argparse.ArgumentTypeError("keys are two or more increasing times in seconds")
    return keys


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--desktop", type=pathlib.Path, required=True, help="16:9 transition video")
    parser.add_argument("--desktop-keys", type=seconds, help="seconds: start, each layer, end")
    parser.add_argument("--mobile", type=pathlib.Path, required=True, help="9:16 transition video")
    parser.add_argument("--mobile-keys", type=seconds, help="seconds: start, each layer, end")
    parser.add_argument("--fps", type=float, default=24, help="frame rate of both videos")
    parser.add_argument("--still", type=pathlib.Path, required=True, help="16:9 exploded still")
    parser.add_argument("--still-mobile", type=pathlib.Path, required=True, help="9:16 exploded still")
    parser.add_argument("--poster", type=pathlib.Path, help="16:9 assembled still")
    parser.add_argument("--poster-mobile", type=pathlib.Path, help="9:16 assembled still")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "desktop": build_variant("desktop", args.desktop, VARIANTS["desktop"], args.desktop_keys, args.fps),
        "mobile": build_variant("mobile", args.mobile, VARIANTS["mobile"], args.mobile_keys, args.fps),
        "still": build_still(args.still, "exploded.webp", VARIANTS["desktop"]["width"]),
        "still_mobile": build_still(args.still_mobile, "exploded_mobile.webp", VARIANTS["mobile"]["width"]),
    }
    if args.poster:
        manifest["poster"] = build_still(args.poster, "assembled.webp", VARIANTS["desktop"]["width"])
    if args.poster_mobile:
        manifest["poster_mobile"] = build_still(args.poster_mobile, "assembled_mobile.webp", VARIANTS["mobile"]["width"])

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    total = sum(f.stat().st_size for f in OUT.rglob("*.webp"))
    desktop_total = sum(f.stat().st_size for f in (OUT / "desktop").glob("*.webp"))
    print(f"desktop download: {desktop_total / 1024 / 1024:.2f} MB; everything: {total / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
