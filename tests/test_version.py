"""The version scheme: YEAR.MONTH = the commit's month, patch = commit count.

What matters here is that a build never *invents* a number - it either
asks git, reads back what a build stamped, or says 0. None of these
assert a literal version: it changes with every commit.
"""
import subprocess
import sys

import pytest

from kundali import __version__
from kundali import version as v


def _git(*args):
    out = subprocess.run(["git", *args], cwd=v._ROOT,
                         capture_output=True, text=True)
    return out.stdout.strip() if out.returncode == 0 else None


@pytest.fixture
def unstamped(monkeypatch):
    monkeypatch.delenv("KUNDALI_VERSION_PATCH", raising=False)
    monkeypatch.delenv("KUNDALI_VERSION_DATE", raising=False)


def test_version_is_year_month_and_a_patch():
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)
    assert 1 <= int(parts[1]) <= 12


def test_the_month_is_unpadded(unstamped):
    """A version has to name a real month, and stay valid semver for the
    sibling projects that parse it - which is also why it is unpadded."""
    year, month = v.year_month()
    assert 1 <= month <= 12
    assert v.version().split(".")[1] == str(month)
    assert v.date() == f"{year:04d}-{month:02d}"


def test_the_month_is_head_s_committer_month(unstamped):
    """In the committer's own timezone, as `git log` shows it - not UTC,
    and not the build clock."""
    if v.commit_month() is None:
        pytest.skip("not a checkout (a wheel, or no git)")
    iso = _git("log", "-1", "--format=%cI")
    assert v.date() == iso[:7]
    assert v.year_month() == (int(iso[:4]), int(iso[5:7]))


def test_patch_is_this_checkout_s_commit_count(unstamped):
    """Run from the repo, the patch is exactly `git rev-list --count`."""
    counted = v.commit_count()
    if counted is None:
        pytest.skip("not a countable checkout (shallow clone or a wheel)")
    assert str(counted) == _git("rev-list", "--count", "HEAD")
    year, month = v.year_month()
    assert v.version() == f"{year}.{month}.{counted}"


def test_a_stamped_build_wins(monkeypatch):
    """The Docker image is built without .git, so the installer passes
    the count and the month in as build arguments."""
    monkeypatch.setenv("KUNDALI_VERSION_PATCH", "311")
    monkeypatch.setenv("KUNDALI_VERSION_DATE", "2031-07")
    assert v.patch() == 311
    assert v.date() == "2031-07"
    assert v.version() == "2031.7.311"


@pytest.mark.parametrize("stamp", ["nightly", "2026-13", "2026-8", "26-08",
                                   ""])
def test_a_nonsense_stamp_is_ignored(monkeypatch, stamp):
    monkeypatch.setenv("KUNDALI_VERSION_PATCH", stamp)
    monkeypatch.setenv("KUNDALI_VERSION_DATE", stamp)
    assert isinstance(v.patch(), int)
    assert 1 <= v.year_month()[1] <= 12


def test_parse_month():
    assert v.parse_month("2026-08") == (2026, 8)
    assert v.parse_month("2026-11-16T09:30:00+05:30") == (2026, 11)
    assert v.parse_month("2026-00") is None
    assert v.parse_month(None) is None


def test_without_git_or_stamp_it_is_patch_0_this_month(monkeypatch,
                                                      unstamped):
    """Nothing to ask: say so, under the build clock's month."""
    monkeypatch.setattr(v, "_git", lambda *a: None)
    monkeypatch.setattr(v, "_recorded", lambda: None)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    assert v.patch() == 0
    assert v.year_month() == (now.year, now.month)


def test_installed_metadata_answers_for_a_tree_without_git(monkeypatch,
                                                          unstamped):
    monkeypatch.setattr(v, "_git", lambda *a: None)
    monkeypatch.setattr(v, "_metadata", lambda: (2026, 9, 57))
    assert v.version() == "2026.9.57"


def test_a_stale_install_s_count_is_never_glued_onto_another_month(
        monkeypatch, unstamped):
    """A stamped month with no stamped patch: the metadata's count belongs
    to a different line, so it is not used."""
    monkeypatch.setenv("KUNDALI_VERSION_DATE", "2026-10")
    monkeypatch.setattr(v, "_git", lambda *a: None)
    monkeypatch.setattr(v, "_metadata", lambda: (2026, 9, 57))
    assert v.version() == "2026.10.0"


def test_an_unpacked_sdist_reports_the_version_it_was_built_as(
        monkeypatch, tmp_path, unstamped):
    """The release tarball has no .git; its PKG-INFO says what it is."""
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    (tmp_path / "PKG-INFO").write_text(
        "Metadata-Version: 2.1\nName: kundali-report\nVersion: 2026.11.42\n")
    monkeypatch.setattr(v, "_ROOT", tmp_path)
    monkeypatch.setattr(v, "_git", lambda *a: None)
    monkeypatch.setattr(v, "_metadata", lambda: (2026, 9, 57))
    assert v.version() == "2026.11.42"


def test_metadata_is_well_formed_or_absent():
    """A wheel install has no .git; pip recorded the number at build time.
    None is fine too - that is the honest answer for a source checkout
    that was never installed."""
    meta = v._metadata()
    assert meta is None or (len(meta) == 3 and 1 <= meta[1] <= 12)


@pytest.mark.parametrize("flag", [None, "--patch", "--date"])
def test_the_helper_script_agrees_with_the_package(flag):
    script = v._ROOT / "scripts" / "version.py"
    out = subprocess.run([sys.executable, str(script)] + ([flag] if flag
                                                           else []),
                         capture_output=True, text=True)
    assert out.returncode == 0
    expected = {None: v.version(), "--patch": str(v.patch()),
                "--date": v.date()}[flag]
    assert out.stdout.strip() == expected
