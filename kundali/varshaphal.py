"""varshaphal.py - Tajika annual chart: pravesh, Muntha, year-lord candidates.

Conventions (documented in the report itself):
  * Varsha chart is cast for the birthplace.
  * Year-lord candidates are the panchadhikari MINUS the Tri-rashi-pati;
    full Panchavargiya Bala is not computed. The report lists candidates
    with a dignity hint and leaves final selection to the reader.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from . import ephemeris as eph
from .dasha import Period, mudda
from .model import Chart, SIGNS, SIGN_LORD, dignity, sign_of

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


def sade_sati_phase(moon_sign: int, saturn_sign: int) -> str | None:
    d = (saturn_sign - moon_sign) % 12
    return {11: "first phase (Saturn 12th from Moon)",
            0: "CORE phase (Saturn on the Moon sign)",
            1: "final phase (Saturn 2nd from Moon)"}.get(d)
