"""bhav.py - Bhav Chalit: the Sripati (Porphyry-based) cusped house
system laid over the whole-sign chart.

Mid-bhav points are the Porphyry cusps (angles trisected); each bhava
spans from the midpoint with the previous cusp to the midpoint with the
next. The useful output is the SHIFT LIST: planets whose bhava differs
from their whole-sign house - those are the placements where the two
house systems disagree and judgment is required.
"""
from __future__ import annotations

import swisseph as swe

from .model import Chart, NINE_GRAHAS, SIGNS, sign_of

_FLAGS = swe.FLG_SIDEREAL


def porphyry_cusps(chart: Chart) -> list[float]:
    """Twelve mid-bhav longitudes (cusp 1 = ascendant)."""
    from .ephemeris import set_ayanamsa
    set_ayanamsa(chart.ayanamsa_name)       # swe sid-mode is global state
    cusps, _ = swe.houses_ex(chart.jd, chart.lat, chart.lon, b"O", _FLAGS)
    return [c % 360 for c in cusps[:12]]


def bhav_spans(chart: Chart) -> list[tuple[float, float, float]]:
    """[(begin, mid, end)] for bhavas 1-12."""
    mids = porphyry_cusps(chart)
    out = []
    for i in range(12):
        prev, nxt = mids[i - 1], mids[(i + 1) % 12]
        begin = (prev + (((mids[i] - prev) % 360) / 2)) % 360
        end = (mids[i] + (((nxt - mids[i]) % 360) / 2)) % 360
        out.append((begin, mids[i], end))
    return out


def bhav_of(chart: Chart, lon: float) -> int:
    for i, (b, _, e) in enumerate(bhav_spans(chart)):
        if (lon - b) % 360 < (e - b) % 360:
            return i + 1
    return 12


def shifts(chart: Chart) -> list[tuple[str, int, int]]:
    """Planets whose Bhav Chalit house differs from whole-sign:
    [(planet, whole_sign_house, bhav_house)]."""
    out = []
    for p in NINE_GRAHAS:
        ws = chart.house_of(p)
        bc = bhav_of(chart, chart.bodies[p].lon)
        if ws != bc:
            out.append((p, ws, bc))
    return out


def bhav_table(chart: Chart) -> list[list[str]]:
    rows = [["Bhava", "Begins", "Mid (cusp)", "Ends"]]
    for i, (b, m, e) in enumerate(bhav_spans(chart), 1):
        def f(x):
            s, d = sign_of(x)
            return f"{SIGNS[s][:3]} {int(d)}:{int((d % 1) * 60):02d}"
        rows.append([str(i), f(b), f(m), f(e)])
    return rows
