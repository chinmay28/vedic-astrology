"""avastha.py - three classical planetary "state" systems.

Baladi (age, by degree in sign), Jagradadi (wakefulness, by dignity
class), Deeptadi (mood, by compound-friendship dignity + combustion/
debilitation). Deeptadi and Jagradadi validated against an independent
commercial report for the same chart (Sun Deepta, Mercury Dukhita via
combustion+Shatru, Moon Shanta via temporal friendship, etc.).
"""
from __future__ import annotations

from .maitri import relation_to_sign_lord
from .model import Chart, EXALTATION, NINE_GRAHAS, SEVEN_GRAHAS, sign_of

BALADI = ["Bala", "Kumara", "Yuva", "Vriddha", "Mrita"]


def baladi(chart: Chart, planet: str) -> str:
    s, d = sign_of(chart.bodies[planet].lon)
    idx = int(d // 6)
    if s % 2 == 1:               # even signs run in reverse
        idx = 4 - idx
    return BALADI[idx]


def _dignity_class(chart: Chart, planet: str) -> str:
    s = chart.sign_idx_of(planet)
    if planet in EXALTATION and EXALTATION[planet] == s:
        return "exalted"
    if planet in EXALTATION and (EXALTATION[planet] + 6) % 12 == s:
        return "debilitated"
    return relation_to_sign_lord(chart, planet, s)   # Own/Adhimitra/../Adhishatru


def jagradadi(chart: Chart, planet: str) -> str:
    c = _dignity_class(chart, planet)
    if c in ("exalted", "Own"):
        return "Jagrata"          # awake
    if c in ("Adhimitra", "Mitra", "Sama"):
        return "Swapna"           # dreaming
    return "Supta"                # asleep (enemy classes, debilitated)


def deeptadi(chart: Chart, planet: str) -> str:
    if planet in SEVEN_GRAHAS and planet != "Sun" and planet in chart.combust():
        return "Dukhita"          # combust overrides (report convention)
    c = _dignity_class(chart, planet)
    return {"exalted": "Deepta", "Own": "Swastha", "Adhimitra": "Mudita",
            "Mitra": "Shanta", "Sama": "Deena", "Shatru": "Dukhita",
            "Adhishatru": "Khala", "debilitated": "Khala"}[c]


def avastha_table(chart: Chart) -> list[list[str]]:
    rows = [["Graha", "Baladi (age)", "Jagradadi (alertness)", "Deeptadi (mood)"]]
    for p in NINE_GRAHAS:
        if p in ("Rahu", "Ketu"):
            rows.append([p, baladi(chart, p), "-", "-"])
        else:
            rows.append([p, baladi(chart, p), jagradadi(chart, p),
                         deeptadi(chart, p)])
    return rows
