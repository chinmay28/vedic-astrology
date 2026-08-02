"""service.py - stored record -> JSON payload / report bytes.

Contract:
    * Input is always a store record dict; output is JSON-serialisable
      data or bytes. Nothing here knows about HTTP.
    * Every entry point holds `_LOCK` for the whole computation: Swiss
      Ephemeris keeps the sidereal mode in process-global state, so two
      charts with different ayanamsas must not compute concurrently.
    * The numbers come from the same modules the PDF uses - the web GUI
      is a third renderer, not a second implementation.
"""
from __future__ import annotations

import csv
import io
import os
import re
import tempfile
import threading
from datetime import datetime

from .. import aspects, ephemeris as eph, yogas
from ..ashtakavarga import bav, sav
from ..avastha import avastha_table
from ..bhav import bhav_table, shifts
from ..cli import cast_natal
from ..dasha import Period, antardashas, mahadashas
from ..dasha_now import age_note, guidance_for, locate, lord_condition, \
    sandhi_note, timeline_guidance
from ..diagrams import north_svg, south_svg
from ..guidance import GUIDANCE
from ..maitri import maitri_table
from ..model import (Chart, HOUSE_SIGNIFICATIONS, SEVEN_GRAHAS, SIGNS,
                     NINE_GRAHAS, dignity, nakshatra_of, sign_of)
from ..panchanga import avakahada, karana, tithi, vara, yoga as sy_yoga
from ..sadesati import (IMPACTS, NAVIGATION, PHASES, current_status,
                        lifetime_table, murti, severity_profile)
from ..varga import navamsa_chart, shodashavarga_table, vargottama, vimshopaka
from ..varshaphal import cast_varsha, outlook as varsha_outlook
from ..weekly import week_outlook

_LOCK = threading.RLock()
DAY = 365.25


# ---------------------------------------------------------------- casting

def cast(rec: dict) -> Chart:
    """Store record -> Chart, via the CLI's single construction path."""
    return cast_natal(rec["name"], rec["birth_date"], rec["birth_time"],
                      rec["tz"], float(rec["lat"]), float(rec["lon"]),
                      rec.get("place") or "", rec.get("ayanamsa") or "raman")


def years_of(rec: dict, asof: datetime | None = None) -> list[int]:
    """The varsha years to cast: the record's own, or - when it names
    none - the current year and the next one, which is what someone
    opening a chart wants to read. `asof` (not the clock) decides which
    year is current, so a report re-rendered for a past date stays
    reproducible."""
    raw = (rec.get("varsha_years") or "").strip()
    if raw:
        return [int(y) for y in re.split(r"[,\s]+", raw) if y]
    year = (asof or datetime.now()).year
    return [year, year + 1]


def _asof_dt(asof: str | None) -> datetime:
    if not asof:
        return datetime.now()
    return datetime.strptime(asof[:10], "%Y-%m-%d")


def slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return s or "kundali"


# ------------------------------------------------------------- fragments

def _positions(chart: Chart) -> list[dict]:
    s, d = sign_of(chart.asc)
    nk, pd = nakshatra_of(chart.asc)
    rows = [{"body": "Lagna", "sign": SIGNS[s], "deg": round(d, 2),
             "nakshatra": nk, "pada": pd, "house": 1, "dignity": "-",
             "retro": False}]
    for b in NINE_GRAHAS:
        s, d = sign_of(chart.bodies[b].lon)
        nk, pd = nakshatra_of(chart.bodies[b].lon)
        rows.append({"body": b, "sign": SIGNS[s], "deg": round(d, 2),
                     "nakshatra": nk, "pada": pd,
                     "house": chart.house_of(b), "dignity": dignity(b, s, d),
                     "retro": bool(chart.bodies[b].retro and b != "Ketu")})
    return rows


def _period(p: Period, tz: str, jd_now: float) -> dict:
    span = max(p.end - p.start, 1e-9)
    return {"lord": p.lord, "sub": p.sub,
            "from": eph.jd_to_date_str(p.start, tz),
            "to": eph.jd_to_date_str(p.end, tz),
            "years": round(span / DAY, 2),
            "current": p.start <= jd_now < p.end,
            "progress": round(min(max((jd_now - p.start) / span, 0), 1), 4)}


def _dasha_now(natal: Chart, jd_now: float) -> dict:
    md, ad, pad, next_ad, next_md = locate(natal, jd_now)
    vim = vimshopaka(natal)
    roles = [("Mahadasha", md), ("Antardasha", ad)]
    out = {
        "running": [
            {"level": "Mahadasha", "label": md.lord,
             **_period(md, natal.tz, jd_now)},
            {"level": "Antardasha", "label": f"{ad.lord}-{ad.sub}",
             **_period(ad, natal.tz, jd_now)},
            {"level": "Pratyantardasha", "label": "-".join(pad[:3]),
             "lord": pad[2], "sub": None,
             "from": eph.jd_to_date_str(pad[3], natal.tz),
             "to": eph.jd_to_date_str(pad[4], natal.tz),
             "current": True,
             "progress": round(min(max((jd_now - pad[3])
                                       / max(pad[4] - pad[3], 1e-9), 0), 1),
                               4)},
        ],
        "next": [
            {"level": "Next Antardasha",
             "label": f"{next_ad.lord}-{next_ad.sub}",
             **_period(next_ad, natal.tz, jd_now)},
            {"level": "Next Mahadasha", "label": next_md.lord,
             **_period(next_md, natal.tz, jd_now)},
        ],
        "guidance": [],
        "notes": [n for n in (age_note(natal, jd_now),
                              sandhi_note(md, ad, jd_now, natal.tz)) if n],
    }
    for role, period in roles:
        lord = period.sub or period.lord
        cond = lord_condition(natal, lord, vim)
        out["guidance"].append({
            "role": role, "planet": lord, "house": cond["house"],
            "sign": cond["sign"], "dignity": cond["dignity"],
            "score": cond["score"], "themes": cond["themes"],
            "text": guidance_for(natal, cond, role.lower())})
    return out


def _sadesati(natal: Chart, jd_now: float) -> dict:
    grade, factors = severity_profile(natal)
    active, nxt = current_status(natal, jd_now)

    def span(s):
        if s is None:
            return None
        start, end, sign, off = s
        metal, mgrade = (murti(natal, start) if start > natal.jd
                         else ("-", "-"))
        return {"from": eph.jd_to_date_str(start, natal.tz),
                "to": eph.jd_to_date_str(end, natal.tz),
                "sign": SIGNS[sign], "phase": PHASES[off],
                "impact": IMPACTS[off], "murti": metal, "murti_grade": mgrade}

    return {"grade": grade,
            "factors": [{"factor": f, "finding": v} for f, v in factors],
            "active": span(active), "next": span(nxt),
            "navigation": NAVIGATION,
            "lifetime": [{"from": r[0], "to": r[1], "sign": r[2],
                          "phase": r[3], "murti": r[4]}
                         for r in lifetime_table(natal)]}


def _ashtakavarga(natal: Chart) -> dict:
    s = sav(natal)
    houses = []
    for h in range(1, 13):
        idx = (natal.lagna_idx + h - 1) % 12
        houses.append({"house": h, "sign": SIGNS[idx], "sav": s[idx]})
    return {"signs": SIGNS, "sav": s,
            "bav": {p: bav(natal, p) for p in SEVEN_GRAHAS},
            "houses": houses, "max": max(s), "min": min(s)}


def _varsha(natal: Chart, years: list[int], jd_now: float) -> list[dict]:
    out = []
    for y in sorted(years):
        v = cast_varsha(natal, y)
        if v is None:
            continue
        out.append({
            "year": y, "age": v.age,
            "pravesh": eph.jd_to_local_str(v.chart.jd, natal.tz),
            "lagna": SIGNS[v.chart.lagna_idx],
            "muntha_sign": SIGNS[v.muntha_sign],
            "muntha_house": v.muntha_house, "muntha_lord": v.muntha_lord,
            "grade": v.grade,
            "day_birth": v.day_birth,
            "candidates": [{"role": r, "planet": p} for r, p in v.candidates],
            "mudda": [_period(p, natal.tz, jd_now) for p in v.mudda],
            "outlook": varsha_outlook(natal, v),
            "north": north_svg(v.chart)})
    return out


# ------------------------------------------------------------ entry point

def summary(rec: dict, asof: str | None = None) -> dict:
    """Everything the GUI renders for one chart, in one payload."""
    with _LOCK:
        natal = cast(rec)
        asof_dt = _asof_dt(asof)
        jd_now = eph.jd_from_local(asof_dt, natal.tz)
        off, dst = eph.utc_offset_info(natal.dt_local, natal.tz)
        moon = natal.bodies["Moon"].lon
        nk, pd = nakshatra_of(moon)
        pk, tn, tname = tithi(natal)
        nav = navamsa_chart(natal)
        occ, inbound = natal.occupants(), aspects.inbound_by_house(natal)
        mds = mahadashas(moon, natal.jd)
        return {
            "chart": rec,
            "asof": asof_dt.strftime("%Y-%m-%d"),
            "identity": {
                "name": natal.name,
                "when": natal.dt_local.strftime("%d %b %Y, %H:%M"),
                "tz": natal.tz, "place": natal.place,
                "lat": natal.lat, "lon": natal.lon,
                "lagna": SIGNS[natal.lagna_idx],
                "lagna_deg": round(sign_of(natal.asc)[1], 2),
                "rashi": SIGNS[natal.sign_idx_of("Moon")],
                "nakshatra": nk, "pada": pd,
                "ayanamsa": natal.ayanamsa_name.title(),
                "ayanamsa_deg": round(natal.ayanamsa_deg, 2),
                "age": round((jd_now - natal.jd) / DAY, 1)},
            "verification": [
                ["Timezone used", f"{natal.tz} -> {off}"
                 + (" (DST active)" if dst else " (no DST)")],
                ["Birth instant (UT)",
                 eph.jd_to_local_str(natal.jd, "UTC") + " UT"],
                ["Houses", "Whole sign, from the Lagna"],
                ["Node convention", "Mean node"]],
            "panchanga": {
                "rows": [["Tithi", f"{pk} {tname} ({tn})"],
                         ["Vara", vara(natal)],
                         ["Nakshatra", f"{nk} pada {pd}"],
                         ["Yoga", sy_yoga(natal)],
                         ["Karana", karana(natal)]],
                "avakahada": [[k, v] for k, v in avakahada(natal).items()]},
            "positions": _positions(natal),
            "sandhi": natal.sandhi_flags(),
            "combust": [b for b in natal.combust() if b != "Sun"],
            "diagrams": {"north": north_svg(natal), "south": south_svg(natal),
                         "navamsa": south_svg(nav)},
            "yogas": [{"name": n, "detail": d}
                      for n, d in yogas.detect(natal)],
            "aspects": {
                "mutual": [[a, b] for a, b in aspects.mutual_pairs(natal)],
                "houses": [{"house": h, "sign": SIGNS[(natal.lagna_idx + h - 1)
                                                      % 12],
                            "significations": HOUSE_SIGNIFICATIONS[h][1],
                            "occupants": occ[h],
                            "aspected_by": inbound.get(h, [])}
                           for h in range(1, 13)]},
            "week": week_outlook(natal, asof_dt, today=datetime.now()),
            "dasha_now": _dasha_now(natal, jd_now),
            "mahadashas": [{**_period(m, natal.tz, jd_now),
                            "antardashas": [_period(a, natal.tz, jd_now)
                                            for a in antardashas(m)]}
                           for m in mds],
            "mahadasha_guidance": timeline_guidance(natal, jd_now),
            "ashtakavarga": _ashtakavarga(natal),
            "navamsa": {"positions": _positions(nav),
                        "vargottama": vargottama(natal),
                        "vimshopaka": vimshopaka(natal),
                        "shodashavarga": shodashavarga_table(natal)},
            "maitri": maitri_table(natal),
            "avastha": avastha_table(natal),
            "bhav": {"table": bhav_table(natal),
                     "shifts": [{"planet": p, "whole_sign": ws, "chalit": bc}
                                for p, ws, bc in shifts(natal)]},
            "sadesati": _sadesati(natal, jd_now),
            "varsha": _varsha(natal, years_of(rec, asof_dt), jd_now),
            "guidance": dict(GUIDANCE),
        }


# ----------------------------------------------------------- downloadables

def pdf_bytes(rec: dict, years: list[int] | None = None,
              asof: str | None = None) -> bytes:
    from ..report import build_report
    with _LOCK:
        natal = cast(rec)
        yrs = years if years is not None else years_of(rec, _asof_dt(asof))
        with tempfile.TemporaryDirectory(prefix="kundali_web_") as work:
            out = os.path.join(work, "report.pdf")
            build_report(natal, yrs, out, work_dir=work,
                         asof=_asof_dt(asof))
            with open(out, "rb") as fh:
                return fh.read()


def html_bytes(rec: dict, years: list[int] | None = None,
               asof: str | None = None) -> bytes:
    from ..html_report import build_html
    with _LOCK:
        natal = cast(rec)
        yrs = years if years is not None else years_of(rec, _asof_dt(asof))
        with tempfile.TemporaryDirectory(prefix="kundali_web_") as work:
            out = os.path.join(work, "report.html")
            build_html(natal, yrs, out, asof=_asof_dt(asof))
            with open(out, "rb") as fh:
                return fh.read()


def positions_csv(rec: dict) -> str:
    with _LOCK:
        rows = _positions(cast(rec))
    buf = io.StringIO()
    cols = ["body", "sign", "deg", "nakshatra", "pada", "house", "dignity",
            "retro"]
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def dasha_csv(rec: dict) -> str:
    """Mahadasha/antardasha calendar - the table people actually re-use."""
    with _LOCK:
        natal = cast(rec)
        mds = mahadashas(natal.bodies["Moon"].lon, natal.jd)
        rows = []
        for m in mds:
            rows.append(["Mahadasha", m.lord, "",
                         eph.jd_to_date_str(m.start, natal.tz),
                         eph.jd_to_date_str(m.end, natal.tz)])
            for a in antardashas(m):
                rows.append(["Antardasha", a.lord, a.sub,
                             eph.jd_to_date_str(a.start, natal.tz),
                             eph.jd_to_date_str(a.end, natal.tz)])
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["level", "lord", "sub", "from", "to"])
    w.writerows(rows)
    return buf.getvalue()
