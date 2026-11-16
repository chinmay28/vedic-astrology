#!/usr/bin/env python3
"""Derive every Android icon from the web app's one mark.

    scripts/android_icons.py            write them into apps/android
    scripts/android_icons.py --check    exit 1 if a committed copy drifted

`kundali/webapp/static/icon.svg` is the only icon anyone draws: the PWA
icons are rasterised from it at runtime (server.py), and this script makes
the Android app's from it, so the launcher, the in-app logo and the browser
tab all wear the same mark. Never edit a generated PNG by hand - change the
SVG and run this again. tests/test_android_icons.py runs --check.

What it makes (apps/android/app/src/main/res/):

    mipmap-<dpi>/ic_launcher.png             the SVG as drawn (rounded plate),
                                             48dp in every density
    mipmap-<dpi>/ic_launcher_foreground.png  the adaptive icon's foreground:
                                             the mark without its plate, the
                                             SVG's 512 units across the 72dp
                                             a launcher shows of a 108dp layer
    mipmap-<dpi>/ic_launcher_monochrome.png  the same in white, for themed
                                             icons (Android 13+)
    mipmap-anydpi-v26/ic_launcher.xml        the adaptive icon itself
    values/ic_launcher_background.xml        the plate's colour, read from
                                             the SVG
    drawable-nodpi/kundali_logo.png          the mark on the app's own screens

The app posts no notifications of its own, so there is no status-bar
silhouette to keep.

Needs cairosvg (already a dependency of the package) and Pillow, which
cairosvg depends on. Rendering is vector-to-pixels at each size, never a
resize of a resize, so every density is as sharp as the SVG allows.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "kundali" / "webapp" / "static" / "icon.svg"
RES = ROOT / "apps" / "android" / "app" / "src" / "main" / "res"

DENSITIES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}
LAUNCHER_DP = 48
LAYER_DP = 108          # an adaptive icon layer
VISIBLE_DP = 72         # how much of it a launcher's mask shows
LOGO_PX = 288        # 72dp, the largest it is shown, at xxxhdpi

# The plate: the full-size rounded rect the mark sits on. The script needs
# exactly one, because the adaptive icon draws the plate itself.
PLATE = re.compile(
    r'<rect\s+width="512"\s+height="512"[^>]*?fill="(#[0-9a-fA-F]{6})"[^>]*/>')

ADAPTIVE_XML = """<?xml version="1.0" encoding="utf-8"?>
<!-- Generated from kundali/webapp/static/icon.svg by scripts/android_icons.py;
     edit that, not this. -->
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/ic_launcher_background" />
    <foreground android:drawable="@mipmap/ic_launcher_foreground" />
    <monochrome android:drawable="@mipmap/ic_launcher_monochrome" />
</adaptive-icon>
"""

BACKGROUND_XML = """<?xml version="1.0" encoding="utf-8"?>
<!-- The icon's plate colour. Generated from kundali/webapp/static/icon.svg by
     scripts/android_icons.py. -->
<resources>
    <color name="ic_launcher_background">{colour}</color>
</resources>
"""


def _svg() -> str:
    return SOURCE.read_text(encoding="utf-8")


def plate_colour(svg: str) -> str:
    found = PLATE.findall(svg)
    if len(found) != 1:
        raise SystemExit(f"{SOURCE}: expected one 512x512 plate <rect>, "
                         f"found {len(found)} - update PLATE in {__file__}")
    return found[0].upper()


def _foreground_svg(svg: str) -> str:
    """The mark without its plate, on a 108dp layer: 512 SVG units span the
    middle 72dp, so the viewBox grows by a quarter on every side."""
    bare = PLATE.sub("", svg, count=1)
    pad = 512 * (LAYER_DP - VISIBLE_DP) / VISIBLE_DP / 2      # 128 units
    size = 512 + 2 * pad
    return re.sub(r'viewBox="[^"]*"', f'viewBox="{-pad:g} {-pad:g} '
                  f'{size:g} {size:g}"', bare, count=1)


def _png(svg: str, px: int) -> bytes:
    import cairosvg
    return cairosvg.svg2png(bytestring=svg.encode("utf-8"),
                            output_width=px, output_height=px)


def _white(png: bytes) -> bytes:
    """Keep the shape, drop the colour: what a themed icon is drawn from."""
    from PIL import Image
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    alpha = img.getchannel("A")
    out = Image.new("RGBA", img.size, (255, 255, 255, 0))
    out.putalpha(alpha)
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _normalised(png: bytes) -> bytes:
    """Re-encode through Pillow so the bytes do not depend on cairo's own
    PNG writer settings."""
    from PIL import Image
    buf = io.BytesIO()
    Image.open(io.BytesIO(png)).convert("RGBA").save(buf, format="PNG",
                                                     optimize=True)
    return buf.getvalue()


def outputs() -> dict[Path, bytes]:
    """Every file this script owns, by path, with its contents."""
    svg = _svg()
    fg = _foreground_svg(svg)
    files: dict[Path, bytes] = {}
    for dpi, scale in DENSITIES.items():
        folder = RES / f"mipmap-{dpi}"
        files[folder / "ic_launcher.png"] = _normalised(
            _png(svg, round(LAUNCHER_DP * scale)))
        layer = _png(fg, round(LAYER_DP * scale))
        files[folder / "ic_launcher_foreground.png"] = _normalised(layer)
        files[folder / "ic_launcher_monochrome.png"] = _white(layer)
    files[RES / "mipmap-anydpi-v26" / "ic_launcher.xml"] = \
        ADAPTIVE_XML.encode("utf-8")
    files[RES / "values" / "ic_launcher_background.xml"] = \
        BACKGROUND_XML.format(colour=plate_colour(svg)).encode("utf-8")
    files[RES / "drawable-nodpi" / "kundali_logo.png"] = _normalised(
        _png(svg, LOGO_PX))
    return files


def drift(tolerance: int = 8) -> list[str]:
    """What differs between the committed files and a fresh render.

    PNGs are compared pixel by pixel with a small tolerance, so a different
    cairo or zlib on another machine is not drift; a changed SVG is."""
    from PIL import Image, ImageChops
    problems = []
    for path, want in outputs().items():
        rel = path.relative_to(ROOT)
        if not path.is_file():
            problems.append(f"{rel}: missing")
            continue
        have = path.read_bytes()
        if path.suffix != ".png":
            if have != want:
                problems.append(f"{rel}: differs")
            continue
        a = Image.open(io.BytesIO(have)).convert("RGBA")
        b = Image.open(io.BytesIO(want)).convert("RGBA")
        if a.size != b.size:
            problems.append(f"{rel}: {a.size} is not {b.size}")
            continue
        worst = max(hi for _, hi in ImageChops.difference(a, b).getextrema())
        if worst > tolerance:
            problems.append(f"{rel}: pixels differ by up to {worst}")
    return problems


def main(argv: list[str]) -> int:
    if "--check" in argv:
        problems = drift()
        for p in problems:
            print(p, file=sys.stderr)
        if problems:
            print("run scripts/android_icons.py to regenerate", file=sys.stderr)
        return 1 if problems else 0
    for path, data in outputs().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
