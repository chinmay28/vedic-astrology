"""dasha.py - Vimshottari mahadasha/antardasha and Tajika mudda dasha.

Contract: pure arithmetic over (moon_lon, jd). Year = 365.25 days.
"""
from __future__ import annotations

from dataclasses import dataclass

YEAR = 365.25
LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
YEARS = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
         "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}
NAK_SPAN = 40 / 3


@dataclass(frozen=True)
class Period:
    lord: str
    sub: str | None      # None for a mahadasha row
    start: float         # JD
    end: float           # JD


def _seed(moon_lon: float) -> tuple[str, float]:
    """(starting lord, fraction of that dasha elapsed at the seed moment)."""
    idx = int(moon_lon // NAK_SPAN) % 27
    frac = (moon_lon % NAK_SPAN) / NAK_SPAN
    return LORDS[idx % 9], frac


def mahadashas(moon_lon: float, jd_birth: float) -> list[Period]:
    """Full nine-mahadasha cycle from birth."""
    lord0, frac = _seed(moon_lon)
    start = jd_birth - frac * YEARS[lord0] * YEAR
    i = LORDS.index(lord0)
    out, t = [], start
    for k in range(9):
        lord = LORDS[(i + k) % 9]
        end = t + YEARS[lord] * YEAR
        out.append(Period(lord, None, t, end))
        t = end
    return out


def antardashas(md: Period) -> list[Period]:
    """The nine sub-periods of one mahadasha."""
    i = LORDS.index(md.lord)
    out, t = [], md.start
    for k in range(9):
        sub = LORDS[(i + k) % 9]
        end = t + YEARS[md.lord] * YEARS[sub] / 120 * YEAR
        out.append(Period(md.lord, sub, t, end))
        t = end
    return out


def antardashas_in_window(moon_lon: float, jd_birth: float,
                          jd_from: float, jd_to: float) -> list[Period]:
    """All ADs overlapping [jd_from, jd_to]."""
    out = []
    for md in mahadashas(moon_lon, jd_birth):
        if md.end < jd_from or md.start > jd_to:
            continue
        out.extend(a for a in antardashas(md)
                   if a.end >= jd_from and a.start <= jd_to)
    return out


def mudda(varsha_moon_lon: float, jd_pravesh: float) -> list[Period]:
    """Compressed Vimshottari over one solar year, seeded from the varsha Moon."""
    lord0, frac = _seed(varsha_moon_lon)
    i = LORDS.index(lord0)
    out: list[Period] = []
    t = jd_pravesh
    dur = (1 - frac) * YEARS[lord0] / 120 * YEAR
    k = 0
    total = 0.0
    lord = lord0
    while total < YEAR - 1e-9:
        dur = min(dur, YEAR - total)
        out.append(Period(lord, None, t, t + dur))
        total += dur
        t += dur
        k += 1
        lord = LORDS[(i + k) % 9]
        dur = YEARS[lord] / 120 * YEAR
    return out


def pratyantardashas(ad: Period) -> list[tuple[str, str, str, float, float]]:
    """(md_lord, ad_lord, pad_lord, start, end) for one antardasha."""
    assert ad.sub is not None
    ad_days = ad.end - ad.start
    i = LORDS.index(ad.sub)
    out, t = [], ad.start
    for k in range(9):
        pad = LORDS[(i + k) % 9]
        end = t + ad_days * YEARS[pad] / 120
        out.append((ad.lord, ad.sub, pad, t, end))
        t = end
    return out
