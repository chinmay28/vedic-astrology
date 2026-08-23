"""The version scheme: YEAR.MONTH from source, patch = commit count.

What matters here is that a build never *invents* a patch number - it
either counts the commits, reads back what a build stamped, or says 0.
"""
import subprocess
import sys

import pytest

from kundali import __version__
from kundali import version as v


def test_version_is_year_month_and_a_patch():
    parts = __version__.split(".")
    assert len(parts) == 3
    assert (parts[0], parts[1]) == (str(v.YEAR), str(v.MONTH))
    assert parts[2].isdigit()


def test_the_month_is_a_calendar_month():
    """A version has to name a real month, and stay valid semver for the
    sibling projects that parse it - which is also why it is unpadded."""
    assert 1 <= v.MONTH <= 12
    assert not str(v.MONTH).startswith("0")


def test_patch_is_this_checkout_s_commit_count():
    """Run from the repo, the patch is exactly `git rev-list --count`."""
    counted = v.commit_count()
    if counted is None:
        pytest.skip("not a countable checkout (shallow clone or a wheel)")
    real = subprocess.run(["git", "rev-list", "--count", "HEAD"],
                          cwd=v._ROOT, capture_output=True, text=True)
    assert str(counted) == real.stdout.strip()
    assert v.version() == f"{v.YEAR}.{v.MONTH}.{counted}"


def test_a_stamped_patch_wins(monkeypatch):
    """The Docker image is built without .git, so the installer passes the
    count in as a build argument."""
    monkeypatch.setenv("KUNDALI_VERSION_PATCH", "311")
    assert v.patch() == 311
    assert v.version() == f"{v.YEAR}.{v.MONTH}.311"


def test_a_nonsense_stamp_is_ignored(monkeypatch):
    monkeypatch.setenv("KUNDALI_VERSION_PATCH", "nightly")
    assert isinstance(v.patch(), int)


def test_metadata_carries_the_patch_for_installs_without_git():
    """A wheel install has no .git; pip recorded the number at build time.
    None is fine too - that is the honest answer for a source checkout
    that was never installed."""
    from_meta = v._metadata_patch()
    assert from_meta is None or isinstance(from_meta, int)


def test_the_helper_script_agrees_with_the_package():
    script = v._ROOT / "scripts" / "version.py"
    out = subprocess.run([sys.executable, str(script)],
                         capture_output=True, text=True)
    assert out.returncode == 0
    assert out.stdout.strip() == __version__
