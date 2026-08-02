"""version.py - the one place the version number is assembled.

The scheme is MAJOR.MINOR.PATCH, where MAJOR and MINOR are declared
here and PATCH is the repository's commit count: every commit is a patch
release, so `1.5.42` is the 42nd commit on the 1.5 line. Bump MINOR when
the app gains something worth naming, MAJOR when the data or deployment
contract breaks.

Resolution order for the patch, first hit wins:

    1. ``$KUNDALI_VERSION_PATCH`` - what a build stamps in. The Docker
       image is built without a ``.git`` directory (see .dockerignore),
       so the installer passes the count in as a build argument.
    2. ``git rev-list --count HEAD`` in the checkout this package lives
       in, so a source tree or an editable install is always current.
       A shallow clone cannot count honestly and reports nothing rather
       than a number that is too small.
    3. The version recorded in the installed distribution metadata -
       which pip wrote from (1) or (2) when the wheel was built. This is
       the path a container or a venv install takes at runtime.
    4. 0, i.e. "this build could not tell you".

Nothing here imports anything but the standard library: the version is
read during the build, before dependencies exist.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

MAJOR = 1
MINOR = 0

_ROOT = Path(__file__).resolve().parent.parent      # the checkout, if any


def _git(*args: str) -> str | None:
    """Run git in the tree above this package. None if it cannot."""
    cmd = ("git", "-C", str(_ROOT), "-c", f"safe.directory={_ROOT}", *args)
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None                                 # no git, or it hung
    return done.stdout.strip() if done.returncode == 0 else None


def commit_count() -> int | None:
    """Commits on HEAD, or None when this is not a countable checkout."""
    if not (_ROOT / "pyproject.toml").is_file():
        return None                                 # installed, not a tree
    if _git("rev-parse", "--show-toplevel") != str(_ROOT):
        return None                                 # a parent repo, not ours
    if _git("rev-parse", "--is-shallow-repository") == "true":
        return None                                 # would undercount
    count = _git("rev-list", "--count", "HEAD")
    return int(count) if count and count.isdigit() else None


def _metadata_patch() -> int | None:
    """The patch pip recorded at build time, for installs with no .git."""
    from importlib.metadata import PackageNotFoundError, version as dist

    try:
        parts = dist("kundali-report").split(".")
    except PackageNotFoundError:
        return None
    except Exception:                               # noqa: BLE001
        return None
    if len(parts) < 3 or not parts[2].isdigit():
        return None
    if (parts[0], parts[1]) != (str(MAJOR), str(MINOR)):
        return None                                 # a stale install's count
    return int(parts[2])


def patch() -> int:
    stamped = os.environ.get("KUNDALI_VERSION_PATCH", "").strip()
    if stamped.isdigit():
        return int(stamped)
    for candidate in (commit_count(), _metadata_patch()):
        if candidate is not None:
            return candidate
    return 0


def version() -> str:
    return f"{MAJOR}.{MINOR}.{patch()}"


if __name__ == "__main__":                          # pragma: no cover
    import sys
    print(patch() if "--patch" in sys.argv[1:] else version())
