"""maitri.py - five-fold (panchadha) friendship.

Natural friendship (fixed, in model.py) combines with temporal
friendship (chart-specific: a planet befriends whoever occupies the
2nd, 3rd, 4th, 10th, 11th or 12th sign from it) into the compound
scale: Adhimitra > Mitra > Sama > Shatru > Adhishatru.

Validated against an independent commercial report's Panchadha table
for the same chart (Sun-Mercury Shatru, Sun-Jupiter Adhimitra,
Sun-Venus Sama, etc.).
"""
from __future__ import annotations

from .model import Chart, ENEMIES, FRIENDS, SEVEN_GRAHAS

TEMPORAL_FRIEND_OFFSETS = {1, 2, 3, 9, 10, 11}   # 2nd,3rd,4th,10th,11th,12th

COMPOUND = {("F", "F"): "Adhimitra", ("F", "N"): "Mitra", ("N", "F"): "Mitra",
            ("N", "N"): "Sama", ("F", "E"): "Sama", ("E", "F"): "Sama",
            ("N", "E"): "Shatru", ("E", "N"): "Shatru", ("E", "E"): "Adhishatru"}
# key = (natural, temporal); temporal is only F/E

VIMSHOPAKA_POINTS = {"Own": 20, "Adhimitra": 18, "Mitra": 15, "Sama": 10,
                     "Shatru": 7, "Adhishatru": 5}


def natural(a: str, b: str) -> str:
    if b in FRIENDS[a]:
        return "F"
    if b in ENEMIES[a]:
        return "E"
    return "N"


def temporal(chart: Chart, a: str, b: str) -> str:
    off = (chart.sign_idx_of(b) - chart.sign_idx_of(a)) % 12
    return "F" if off in TEMPORAL_FRIEND_OFFSETS else "E"


def compound(chart: Chart, a: str, b: str) -> str:
    """How planet `a` regards planet `b` in this chart."""
    return COMPOUND[(natural(a, b), temporal(chart, a, b))]


def maitri_table(chart: Chart) -> list[list[str]]:
    """7x7 compound-friendship grid for the report."""
    rows = [[""] + [p[:3] for p in SEVEN_GRAHAS]]
    for a in SEVEN_GRAHAS:
        rows.append([a] + [("-" if a == b else compound(chart, a, b))
                           for b in SEVEN_GRAHAS])
    return rows


def relation_to_sign_lord(chart: Chart, planet: str, sign_idx: int) -> str:
    """Compound relation of `planet` to the lord of `sign_idx` -
    'Own' if the planet rules the sign. Used by Vimshopaka and the
    Deeptadi avastha."""
    from .model import SIGN_LORD
    lord = SIGN_LORD[sign_idx]
    if lord == planet:
        return "Own"
    return compound(chart, planet, lord)
