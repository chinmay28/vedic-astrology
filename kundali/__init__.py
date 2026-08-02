"""kundali - Jyotish chart computation and PDF report generation."""
from .version import version as _version

# MAJOR.MINOR live in version.py; the patch is the repository's commit
# count. See that module for how a build with no .git still knows its
# own number.
__version__ = _version()
