"""varshaphal.py - Tajika annual chart: pravesh, Muntha, year-lord
candidates, and the year's reading (outlook, themes, suggestions, and
the Mudda calendar month by month).

Conventions (documented in the report itself):
  * Varsha chart is cast for the birthplace.
  * Year-lord candidates are the panchadhikari MINUS the Tri-rashi-pati;
    full Panchavargiya Bala is not computed. The report lists candidates
    with a dignity hint and leaves final selection to the reader.
  * `outlook()` is rule-based and classical in framing, like guidance.py
    and dasha_now.py: what the year foregrounds and what posture it
    rewards, never an event prediction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from . import ephemeris as eph
from .dasha import Period, mudda
from .model import (Chart, HOUSE_SIGNIFICATIONS, SIGNS, SIGN_LORD, dignity,
                    sign_of)

MUNTHA_GRADE = {1: "excellent", 9: "excellent", 10: "excellent", 11: "excellent",
                2: "good", 3: "good", 5: "good",
                4: "adverse", 6: "adverse", 7: "adverse", 8: "adverse",
                12: "adverse"}


@dataclass
class Varsha:
    age: int
    chart: Chart
    muntha_sign: int
    muntha_house: int
    muntha_lord: str
    grade: str
    day_birth: bool
    candidates: list[tuple[str, str]]     # (role, planet)
    mudda: list[Period]
    natal_house_rising: int


def cast_varsha(natal: Chart, calendar_year: int) -> Varsha | None:
    """The solar return whose pravesh falls in `calendar_year`.

    Returns None for age < 1 (the natal chart itself governs year zero).
    """
    age = calendar_year - natal.dt_local.year
    if age < 1:
        return None
    eph.set_ayanamsa(natal.ayanamsa_name)   # swe sid-mode is global state
    guess = natal.jd + age * 365.2425
    jr = eph.solar_return(natal.bodies["Sun"].lon, guess)
    bodies = eph.positions(jr)
    asc = eph.ascendant(jr, natal.lat, natal.lon)
    chart = Chart(name=f"{natal.name} - Varsha age {age}",
                  dt_local=datetime.now(), tz=natal.tz, place=natal.place,
                  lat=natal.lat, lon=natal.lon, jd=jr, asc=asc, bodies=bodies,
                  ayanamsa_name=natal.ayanamsa_name,
                  ayanamsa_deg=eph.ayanamsa_value(jr))

    muntha_sign = (natal.lagna_idx + age) % 12
    muntha_house = ((muntha_sign - chart.lagna_idx) % 12) + 1
    m_lord = SIGN_LORD[muntha_sign]

    sun_h = chart.house_of("Sun")
    day = sun_h in (7, 8, 9, 10, 11, 12)
    dr_pati = SIGN_LORD[chart.sign_idx_of("Sun") if day
                        else chart.sign_idx_of("Moon")]

    def hint(p: str) -> str:
        return f"{p} ({dignity(p, chart.sign_idx_of(p))}, H{chart.house_of(p)})"

    candidates = [("Muntha lord", hint(m_lord)),
                  ("Varsha-Lagna lord", hint(SIGN_LORD[chart.lagna_idx])),
                  ("Janma-Lagna lord", hint(SIGN_LORD[natal.lagna_idx])),
                  ("Dina/Ratri-pati", hint(dr_pati))]

    return Varsha(age=age, chart=chart, muntha_sign=muntha_sign,
                  muntha_house=muntha_house, muntha_lord=m_lord,
                  grade=MUNTHA_GRADE[muntha_house], day_birth=day,
                  candidates=candidates,
                  mudda=mudda(bodies["Moon"].lon, jr),
                  natal_house_rising=((chart.lagna_idx - natal.lagna_idx) % 12) + 1)


KENDRA_TRIKONA = {1, 4, 5, 7, 9, 10}
DUSTHANA = {6, 8, 12}

GRADE_COUNSEL = {
    "excellent": ("An excellent Muntha is the classical signature of a "
                  "year that carries initiative: what is started here "
                  "tends to stand, so this is the year to commit rather "
                  "than to wait."),
    "good": ("A good Muntha marks a workable year - it supports what is "
             "already moving more readily than it launches something "
             "wholly new."),
    "adverse": ("An adverse Muntha is not a bad year; it is a year that "
                "gives through effort rather than through luck, and the "
                "Muntha lord's condition decides how much it gives. "
                "Consolidation beats expansion here."),
}


def _strength(chart: Chart, planet: str) -> str:
    """'strong' / 'mixed' / 'strained' for a planet in the annual chart."""
    h = chart.house_of(planet)
    dig = dignity(planet, chart.sign_idx_of(planet))
    good = (dig in ("Exalted", "Moolatrikona", "Own sign")
            or h in KENDRA_TRIKONA)
    bad = dig in ("Debilitated", "Enemy's sign") or h in DUSTHANA
    if good and not bad:
        return "strong"
    if bad and not good:
        return "strained"
    return "mixed"


def _months(natal: Chart, v: Varsha) -> list[dict]:
    """The Mudda calendar with each stretch read through its lord's
    condition in the annual chart."""
    out = []
    for p in v.mudda:
        s = _strength(v.chart, p.lord)
        dig = dignity(p.lord, v.chart.sign_idx_of(p.lord))
        h = v.chart.house_of(p.lord)
        note = (f"{p.lord} is {s} in the year chart (house {h}"
                + (f", {dig}" if dig != "-" else "") + ") - "
                + ("a supported stretch: put the year's deliberate moves "
                   "here." if s == "strong" else
                   "a stretch to hold steady through: maintenance, not "
                   "expansion." if s == "strained" else
                   "an uneven stretch: move on concrete openings, not "
                   "on momentum.")
                + f" Its themes are house-{h} matters: "
                + HOUSE_SIGNIFICATIONS[h][1] + ".")
        out.append({"lord": p.lord, "strength": s,
                    "from": eph.jd_to_date_str(p.start, natal.tz),
                    "to": eph.jd_to_date_str(p.end, natal.tz),
                    "days": round(p.end - p.start),
                    "house": h, "note": note})
    return out


def outlook(natal: Chart, v: Varsha) -> dict:
    """The year's reading: outlook, themes, suggestions, Mudda calendar."""
    rise_sig = HOUSE_SIGNIFICATIONS[v.natal_house_rising][1]
    m_sig = HOUSE_SIGNIFICATIONS[v.muntha_house][1]
    m_strength = _strength(v.chart, v.muntha_lord)
    m_dig = dignity(v.muntha_lord, v.chart.sign_idx_of(v.muntha_lord))
    m_house = v.chart.house_of(v.muntha_lord)
    year_lord = SIGN_LORD[v.chart.lagna_idx]
    y_strength = _strength(v.chart, year_lord)
    months = _months(natal, v)

    text = (
        f"Age {v.age}. The annual chart rises in "
        f"{SIGNS[v.chart.lagna_idx]} - your natal "
        f"{v.natal_house_rising}th house - so the year's frame is "
        f"{rise_sig}. The Muntha stands in house {v.muntha_house} of the "
        f"annual chart ({v.grade}), foregrounding {m_sig}; its lord "
        f"{v.muntha_lord} is {m_strength} there (house {m_house}"
        + (f", {m_dig}" if m_dig != "-" else "") + "). "
        + GRADE_COUNSEL[v.grade])
    if v.grade == "adverse" and m_strength == "strong":
        text += (" Here the Muntha lord is well placed, which the "
                 "tradition reads as a substantial rescue of an adverse "
                 "Muntha - the year asks for effort, not retreat.")
    elif v.grade in ("excellent", "good") and m_strength == "strained":
        text += (" The Muntha lord is under strain, though, so read the "
                 "promise as needing support rather than arriving on "
                 "its own.")
    text += (f" The year-lord candidate from the varsha Lagna, "
             f"{year_lord}, is {y_strength} - that is the tone the year "
             "delivers in.")

    themes = [f"House {v.muntha_house} of the year chart (the Muntha): "
              f"{m_sig} - the year's headline.",
              f"Your natal house {v.natal_house_rising} rises: {rise_sig} "
              "- the frame the year is lived inside."]
    sade = sade_sati_phase(natal.sign_idx_of("Moon"),
                           v.chart.sign_idx_of("Saturn"))
    if sade:
        themes.append(f"Sade Sati is running as the year opens - {sade}. "
                      "Read the Shani section for where it turns; it "
                      "outweighs the annual chart.")

    # The seed Mudda period is whatever is left of its lord's share at
    # the pravesh, which can be under a day - too short to plan around.
    plannable = [m for m in months if m["days"] >= 3]
    strong = [m for m in plannable if m["strength"] == "strong"]
    weak = [m for m in plannable if m["strength"] == "strained"]
    suggestions = []
    if strong:
        suggestions.append(
            "Put the year's deliberate moves - the commitments, the "
            "launches, the asks - into "
            + "; ".join(f"{m['lord']} ({m['from']} to {m['to']})"
                        for m in strong[:3])
            + ": those Mudda stretches have the best-placed lords.")
    if weak:
        suggestions.append(
            "Treat "
            + "; ".join(f"{m['lord']} ({m['from']} to {m['to']})"
                        for m in weak[:3])
            + " as maintenance months: finish rather than start, keep "
              "commitments small and reversible, and expect to work "
              "harder for the same distance.")
    suggestions.append(
        f"The year's weight falls on {m_sig} - plan the calendar around "
        "those matters rather than being surprised by them."
        if v.grade != "adverse" else
        f"With an adverse Muntha in {m_sig}, budget time and money for "
        "that area before the year needs it; the classical counsel is "
        "to reduce exposure early rather than to react late.")
    if m_strength == "strained":
        suggestions.append(
            f"{v.muntha_lord} carries the year and is under strain: give "
            f"its matters (house {m_house}: "
            f"{HOUSE_SIGNIFICATIONS[m_house][1]}) more margin than "
            "usual, and use the classical remedies for it - routine, "
            "restraint and service - rather than force.")
    suggestions.append(
        "The annual chart describes one year inside the dasha, and never "
        "outranks it: where the two disagree, the dasha is the stronger "
        "signal and the year only says how that period lands in these "
        "twelve months.")

    return {"text": text, "themes": themes, "suggestions": suggestions,
            "months": months, "year_lord": year_lord,
            "year_lord_strength": y_strength,
            "muntha_strength": m_strength}


def sade_sati_phase(moon_sign: int, saturn_sign: int) -> str | None:
    d = (saturn_sign - moon_sign) % 12
    return {11: "first phase (Saturn 12th from Moon)",
            0: "CORE phase (Saturn on the Moon sign)",
            1: "final phase (Saturn 2nd from Moon)"}.get(d)
