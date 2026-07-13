"""aspects.py - whole-sign graha drishti.

Rules: every graha aspects the 7th from itself; Mars adds 4th & 8th,
Jupiter 5th & 9th, Saturn 3rd & 10th. Nodes: 7th only (classical).
"""
from __future__ import annotations

from .model import Chart, NINE_GRAHAS

SPECIAL = {
    "Sun": [7], "Moon": [7], "Mercury": [7], "Venus": [7],
    "Mars": [4, 7, 8], "Jupiter": [5, 7, 9], "Saturn": [3, 7, 10],
    "Rahu": [7], "Ketu": [7],
}


def edges(chart: Chart) -> list[tuple[str, str, int]]:
    """Planet-to-planet aspects: (aspecting, aspected, offset)."""
    occ = chart.occupants()
    out = []
    for p in NINE_GRAHAS:
        h = chart.house_of(p)
        for off in SPECIAL[p]:
            target = ((h - 1 + off - 1) % 12) + 1
            out.extend((p, q, off) for q in occ[target] if q != p)
    return out


def mutual_pairs(chart: Chart) -> list[tuple[str, str]]:
    """Unordered pairs that aspect each other."""
    e = {(a, b) for a, b, _ in edges(chart)}
    seen, out = set(), []
    for a, b in e:
        if (b, a) in e and (b, a) not in seen:
            seen.add((a, b))
            out.append((a, b))
    return out


def inbound_by_house(chart: Chart) -> dict[int, list[str]]:
    """For each house, which grahas aspect it (with offset annotation)."""
    out: dict[int, list[str]] = {h: [] for h in range(1, 13)}
    for p in NINE_GRAHAS:
        h = chart.house_of(p)
        for off in SPECIAL[p]:
            target = ((h - 1 + off - 1) % 12) + 1
            out[target].append(f"{p}({off})")
    return out
