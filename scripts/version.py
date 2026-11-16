#!/usr/bin/env python3
"""Print the version this checkout would build as.

    scripts/version.py            ->  2026.8.14
    scripts/version.py --patch    ->  14
    scripts/version.py --date     ->  2026-08

YEAR.MONTH is the month of HEAD's commit (its committer date, in the
committer's timezone) and the patch is the commit count, so every commit
is a patch release; kundali/version.py is where that is worked out. The
installers and the release workflow use --patch and --date to stamp a
build that has no .git of its own (the Docker image, the APK); everything
else works this out for itself at import time.

Deliberately importable without the project's dependencies installed -
it only touches kundali/version.py, which is stdlib-only.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kundali.version import date, patch, version    # noqa: E402

if __name__ == "__main__":
    args = sys.argv[1:]
    print(patch() if "--patch" in args
          else date() if "--date" in args
          else version())
