"""The Android app's icons are derived from the web app's icon.svg.

scripts/android_icons.py makes every launcher icon, the adaptive icon's
layers and the in-app logo from the one SVG; this fails if a committed copy
has drifted from it (the SVG changed and nobody re-ran the script, or a PNG
was edited by hand).
"""
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ANDROID = ROOT / "apps" / "android" / "app" / "src" / "main"


@pytest.fixture(scope="module")
def icons():
    pytest.importorskip("cairosvg")
    pytest.importorskip("PIL")
    spec = importlib.util.spec_from_file_location(
        "android_icons", ROOT / "scripts" / "android_icons.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_committed_icons_match_the_svg(icons):
    assert icons.drift() == []


def test_the_background_is_the_svg_s_plate(icons):
    svg = (ROOT / "kundali" / "webapp" / "static" / "icon.svg").read_text()
    assert icons.plate_colour(svg) == "#0E1124"


def test_every_android_resource_reference_exists():
    """Retiring an icon must not leave a reference only Gradle would notice."""
    res = ANDROID / "res"
    texts = [p.read_text(encoding="utf-8")
             for p in list(ANDROID.rglob("*.xml")) + list(ANDROID.rglob("*.kt"))]
    refs = set()
    for t in texts:
        refs |= set(re.findall(r"@(drawable|mipmap)/(\w+)", t))
        refs |= set(re.findall(r"R\.(drawable|mipmap)\.(\w+)", t))
    assert refs, "found no references at all - the scan is broken"
    for kind, name in sorted(refs):
        found = list(res.glob(f"{kind}*/{name}.*"))
        assert found, f"@{kind}/{name} is referenced but no file provides it"
