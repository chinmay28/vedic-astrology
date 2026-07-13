"""ephemeris.py - all Swiss Ephemeris access lives behind this module.

Contract:
    * Every function takes/returns Julian Day (UT) floats and sidereal
      longitudes in degrees [0, 360).
    * set_ayanamsa() must be called once before any computation.
    * No other module may import swisseph directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import swisseph as swe

_FLAGS = swe.FLG_SIDEREAL | swe.FLG_SPEED

AYANAMSAS = {"raman": swe.SIDM_RAMAN, "lahiri": swe.SIDM_LAHIRI}

BODY_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
    "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER, "Venus": swe.VENUS,
    "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE,
}


@dataclass(frozen=True)
class BodyPosition:
    lon: float          # sidereal longitude, degrees
    speed: float        # deg/day; negative == retrograde
    retro: bool


def set_ayanamsa(name: str) -> None:
    """Select the sidereal mode. Raises KeyError for unknown names."""
    swe.set_sid_mode(AYANAMSAS[name.lower()])


def ayanamsa_value(jd: float) -> float:
    return swe.get_ayanamsa_ut(jd)


def jd_from_local(dt_local: datetime, tz_name: str) -> float:
    """Convert a naive local datetime + IANA zone to Julian Day (UT).

    zoneinfo applies the correct historical UTC offset, including DST.
    """
    aware = dt_local.replace(tzinfo=ZoneInfo(tz_name))
    ut = aware.astimezone(ZoneInfo("UTC"))
    hour = ut.hour + ut.minute / 60 + ut.second / 3600
    return swe.julday(ut.year, ut.month, ut.day, hour)


def jd_to_local_str(jd: float, tz_name: str) -> str:
    """Format a JD(UT) as 'DD Mon YYYY HH:MM' in the given zone."""
    y, m, d, h = swe.revjul(jd)
    frac_min = round((h - int(h)) * 60)
    base = datetime(int(y), int(m), int(d), int(h) % 24,
                    min(frac_min, 59), tzinfo=ZoneInfo("UTC"))
    loc = base.astimezone(ZoneInfo(tz_name))
    return loc.strftime("%d %b %Y %H:%M")


def jd_to_date_str(jd: float, tz_name: str | None = None) -> str:
    """Date of a JD(UT); if tz_name is given, the date in that zone."""
    if tz_name:
        y, m, d, h = swe.revjul(jd)
        base = datetime(int(y), int(m), int(d), int(h) % 24,
                        int((h - int(h)) * 60) % 60, tzinfo=ZoneInfo("UTC"))
        return base.astimezone(ZoneInfo(tz_name)).strftime("%d %b %Y")
    y, m, d, _ = swe.revjul(jd)
    return datetime(int(y), int(m), int(d)).strftime("%d %b %Y")


def positions(jd: float) -> dict[str, BodyPosition]:
    """Sidereal positions of the nine grahas (Ketu derived from Rahu)."""
    out: dict[str, BodyPosition] = {}
    for name, pid in BODY_IDS.items():
        p, _ = swe.calc_ut(jd, pid, _FLAGS)
        out[name] = BodyPosition(p[0] % 360, p[3], p[3] < 0)
    r = out["Rahu"]
    out["Ketu"] = BodyPosition((r.lon + 180) % 360, r.speed, r.retro)
    return out


def ascendant(jd: float, lat: float, lon: float) -> float:
    """Sidereal ascendant longitude (whole-sign houses derive from this)."""
    _, ascmc = swe.houses_ex(jd, lat, lon, b"W", _FLAGS)
    return ascmc[0] % 360


def solar_return(natal_sun_lon: float, jd_guess: float) -> float:
    """JD(UT) when the Sun returns to its natal sidereal longitude.

    Newton iteration; converges in a handful of steps from a guess
    within a few days of the birthday.
    """
    jd = jd_guess
    for _ in range(40):
        p, _ = swe.calc_ut(jd, swe.SUN, _FLAGS)
        diff = ((p[0] - natal_sun_lon + 180) % 360) - 180
        if abs(diff) < 1e-7:
            return jd
        jd -= diff / p[3]
    raise RuntimeError("solar_return failed to converge")


def sign_ingresses(body: str, jd_start: float, jd_end: float) -> list[tuple[float, int, int]]:
    """Daily-scan sign changes for one body.

    Returns [(jd, from_sign_idx, to_sign_idx), ...].
    """
    pid = BODY_IDS[body]
    jd = jd_start
    prev = int((swe.calc_ut(jd, pid, _FLAGS)[0][0] % 360) // 30)
    events = []
    while jd < jd_end:
        jd += 1.0
        cur = int((swe.calc_ut(jd, pid, _FLAGS)[0][0] % 360) // 30)
        if cur != prev:
            events.append((jd, prev, cur))
            prev = cur
    return events


def utc_offset_info(dt_local: datetime, tz_name: str) -> tuple[str, bool]:
    """('UTC-07:00', dst_active) for the birth instant - the verification
    the single most common commercial-report error (wrong tz/DST) needs."""
    aware = dt_local.replace(tzinfo=ZoneInfo(tz_name))
    off = aware.utcoffset()
    total = int(off.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    dst = aware.dst() is not None and aware.dst().total_seconds() != 0
    return f"UTC{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}", dst
