"""version.py - the one place the version number is assembled.

The scheme is calendar-based: YEAR.MONTH.PATCH, where YEAR.MONTH is the
month of the commit being built and PATCH is the repository's commit
count: every commit is a patch release, so `2026.8.42` is the 42nd
commit, made in August 2026. The leading numbers say *when* a release
line opened, not what it promises about compatibility - what breaks on
an upgrade is what the release notes are for.

Nobody bumps anything. The month is HEAD's *committer* date, in the
committer's own timezone (`git log -1 --format=%cI`, first seven
characters): a change authored in September and landed in October is an
October release, and the month is the one git shows on the commit. A
rebuild of an old tree still names what it shipped as, because a
commit's date does not change. It is never the build clock - except for
a tree with no commit to ask and nothing stamped, which then says
"patch 0, built this month", visibly not a release.

The month is written plain, never zero-padded. PEP 440 normalises
`2026.08.42` to `2026.8.42` anyway, so the padded form would only make
the string here disagree with the one pip records; semver, which the
sibling projects on this scheme have to satisfy, forbids the leading zero
outright.

Resolution, first hit wins, for each half:

    1. ``$KUNDALI_VERSION_PATCH`` / ``$KUNDALI_VERSION_DATE`` (``YYYY-MM``)
       - what a build stamps in. The Docker image is built without a
       ``.git`` directory (see .dockerignore), so the installer passes
       both in as build arguments.
    2. The checkout this package lives in: ``git rev-list --count HEAD``
       and HEAD's committer month, so a source tree or an editable
       install is always current. A shallow clone cannot count honestly
       and reports no patch rather than a number that is too small (its
       HEAD still has an honest date).
    3. The version recorded in the installed distribution metadata -
       which pip wrote from (1) or (2) when the wheel was built. This is
       the path a container or a venv install takes at runtime. Its
       patch is used only under its own month, so a stale install's
       count is never glued onto another line.
    4. Patch 0, under the build clock's month (UTC): "this build could
       not tell you".

Nothing here imports anything but the standard library: the version is
read during the build, before dependencies exist.
"""
from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent      # the checkout, if any
_MONTH = re.compile(r"^(\d{4})-(\d{2})$")


def _git(*args: str) -> str | None:
    """Run git in the tree above this package. None if it cannot."""
    cmd = ("git", "-C", str(_ROOT), "-c", f"safe.directory={_ROOT}", *args)
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None                                 # no git, or it hung
    return done.stdout.strip() if done.returncode == 0 else None


def _is_checkout() -> bool:
    """Whether this package sits in its own git checkout (not a wheel,
    not some parent repository that happens to contain it)."""
    if not (_ROOT / "pyproject.toml").is_file():
        return False                                # installed, not a tree
    return _git("rev-parse", "--show-toplevel") == str(_ROOT)


def parse_month(text: str | None) -> tuple[int, int] | None:
    """``"2026-08"`` (or a longer ISO date) -> (2026, 8); None if it is
    not a calendar month."""
    m = _MONTH.match((text or "").strip()[:7])
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    return (year, month) if 1 <= month <= 12 else None


def commit_count() -> int | None:
    """Commits on HEAD, or None when this is not a countable checkout."""
    if not _is_checkout():
        return None
    if _git("rev-parse", "--is-shallow-repository") == "true":
        return None                                 # would undercount
    count = _git("rev-list", "--count", "HEAD")
    return int(count) if count and count.isdigit() else None


def commit_month() -> tuple[int, int] | None:
    """HEAD's committer month, in the committer's timezone, or None."""
    if not _is_checkout():
        return None
    return parse_month(_git("log", "-1", "--format=%cI"))


def _metadata() -> tuple[int, int, int] | None:
    """(year, month, patch) as pip recorded them, for installs with no
    .git."""
    from importlib.metadata import PackageNotFoundError, version as dist

    try:
        parts = dist("kundali-report").split(".")
    except PackageNotFoundError:
        return None
    except Exception:                               # noqa: BLE001
        return None
    if len(parts) < 3 or not all(p.isdigit() for p in parts[:3]):
        return None
    year, month, count = (int(p) for p in parts[:3])
    return (year, month, count) if 1 <= month <= 12 else None


def year_month() -> tuple[int, int]:
    """The release line: stamped, else the commit's, else the
    installed metadata's, else the build clock's."""
    stamped = parse_month(os.environ.get("KUNDALI_VERSION_DATE"))
    if stamped:
        return stamped
    committed = commit_month()
    if committed:
        return committed
    meta = _metadata()
    if meta:
        return meta[0], meta[1]
    now = datetime.now(timezone.utc)
    return now.year, now.month


def date() -> str:
    """The release line as ``YYYY-MM``, the form ``--date`` prints and
    ``$KUNDALI_VERSION_DATE`` takes."""
    year, month = year_month()
    return f"{year:04d}-{month:02d}"


def patch() -> int:
    stamped = os.environ.get("KUNDALI_VERSION_PATCH", "").strip()
    if stamped.isdigit():
        return int(stamped)
    counted = commit_count()
    if counted is not None:
        return counted
    meta = _metadata()
    if meta and meta[:2] == year_month():
        return meta[2]                              # never a stale line's
    return 0


def version() -> str:
    year, month = year_month()
    return f"{year}.{month}.{patch()}"


if __name__ == "__main__":                          # pragma: no cover
    import sys
    args = sys.argv[1:]
    print(patch() if "--patch" in args
          else date() if "--date" in args
          else version())
