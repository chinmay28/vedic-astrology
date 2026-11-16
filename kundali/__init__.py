"""kundali - Jyotish chart computation and PDF report generation."""
from .version import version as _version

# YEAR.MONTH is the month of HEAD's commit and the patch is the
# repository's commit count. See version.py for how a build with no .git
# still knows its own number.
__version__ = _version()
