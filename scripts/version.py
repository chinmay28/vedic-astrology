#!/usr/bin/env python3
"""Print the version this checkout would build as.

    scripts/version.py            ->  1.5.14
    scripts/version.py --patch    ->  14

MAJOR.MINOR come from kundali/version.py; the patch is the commit count,
so every commit is a patch release. The installers use --patch to stamp
a build that has no .git of its own (the Docker image); everything else
works this out for itself at import time.

Deliberately importable without the project's dependencies installed -
it only touches kundali/version.py, which is stdlib-only.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kundali.version import patch, version          # noqa: E402

if __name__ == "__main__":
    print(patch() if "--patch" in sys.argv[1:] else version())
