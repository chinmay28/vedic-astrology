"""ashtakavarga.py - Bhinnashtakavarga (BAV) and Sarvashtakavarga (SAV).

Tables are the standard Parashari set. Built-in checksum: the fixed
per-BAV totals are Sun 48, Moon 49, Mars 39, Mercury 54, Jupiter 56,
Venus 52, Saturn 39 - SAV total 337 for every chart. The test suite
asserts these invariants.

Reading convention (documented in USER_GUIDE.md): a sign with SAV >= 30
is strong ground for transits; <= 24 is thin ground; 25-29 average.
"""
from __future__ import annotations

from .model import Chart, SEVEN_GRAHAS

# BAV_TABLES[planet][contributor] = houses (from the contributor) that
# receive a bindu in that planet's ashtakavarga. "Lagna" contributes too.
BAV_TABLES: dict[str, dict[str, list[int]]] = {
    "Sun": {
        "Sun": [1, 2, 4, 7, 8, 9, 10, 11], "Moon": [3, 6, 10, 11],
        "Mars": [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [3, 5, 6, 9, 10, 11, 12], "Jupiter": [5, 6, 9, 11],
        "Venus": [6, 7, 12], "Saturn": [1, 2, 4, 7, 8, 9, 10, 11],
        "Lagna": [3, 4, 6, 10, 11, 12],
    },
    "Moon": {
        "Sun": [3, 6, 7, 8, 10, 11], "Moon": [1, 3, 6, 7, 10, 11],
        "Mars": [2, 3, 5, 6, 9, 10, 11],
        "Mercury": [1, 3, 4, 5, 7, 8, 10, 11],
        "Jupiter": [1, 4, 7, 8, 10, 11, 12],
        "Venus": [3, 4, 5, 7, 9, 10, 11], "Saturn": [3, 5, 6, 11],
        "Lagna": [3, 6, 10, 11],
    },
    "Mars": {
        "Sun": [3, 5, 6, 10, 11], "Moon": [3, 6, 11],
        "Mars": [1, 2, 4, 7, 8, 10, 11], "Mercury": [3, 5, 6, 11],
        "Jupiter": [6, 10, 11, 12], "Venus": [6, 8, 11, 12],
        "Saturn": [1, 4, 7, 8, 9, 10, 11], "Lagna": [1, 3, 6, 10, 11],
    },
    "Mercury": {
        "Sun": [5, 6, 9, 11, 12], "Moon": [2, 4, 6, 8, 10, 11],
        "Mars": [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [1, 3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [6, 8, 11, 12], "Venus": [1, 2, 3, 4, 5, 8, 9, 11],
        "Saturn": [1, 2, 4, 7, 8, 9, 10, 11],
        "Lagna": [1, 2, 4, 6, 8, 10, 11],
    },
    "Jupiter": {
        "Sun": [1, 2, 3, 4, 7, 8, 9, 10, 11], "Moon": [2, 5, 7, 9, 11],
        "Mars": [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [1, 2, 4, 5, 6, 9, 10, 11],
        "Jupiter": [1, 2, 3, 4, 7, 8, 10, 11],
        "Venus": [2, 5, 6, 9, 10, 11], "Saturn": [3, 5, 6, 12],
        "Lagna": [1, 2, 4, 5, 6, 7, 9, 10, 11],
    },
    "Venus": {
        "Sun": [8, 11, 12], "Moon": [1, 2, 3, 4, 5, 8, 9, 11, 12],
        "Mars": [3, 5, 6, 9, 11, 12], "Mercury": [3, 5, 6, 9, 11],
        "Jupiter": [5, 8, 9, 10, 11],
        "Venus": [1, 2, 3, 4, 5, 8, 9, 10, 11],
        "Saturn": [3, 4, 5, 8, 9, 10, 11],
        "Lagna": [1, 2, 3, 4, 5, 8, 9, 11],
    },
    "Saturn": {
        "Sun": [1, 2, 4, 7, 8, 10, 11], "Moon": [3, 6, 11],
        "Mars": [3, 5, 6, 10, 11, 12],
        "Mercury": [6, 8, 9, 10, 11, 12], "Jupiter": [5, 6, 11, 12],
        "Venus": [6, 11, 12], "Saturn": [3, 5, 6, 11],
        "Lagna": [1, 3, 4, 6, 10, 11],
    },
}

BAV_TOTALS = {"Sun": 48, "Moon": 49, "Mars": 39, "Mercury": 54,
              "Jupiter": 56, "Venus": 52, "Saturn": 39}
SAV_TOTAL = 337


def bav(chart: Chart, planet: str) -> list[int]:
    """Bindus per sign (index 0 = Aries) in `planet`'s ashtakavarga."""
    out = [0] * 12
    for contributor, houses in BAV_TABLES[planet].items():
        base = (chart.lagna_idx if contributor == "Lagna"
                else chart.sign_idx_of(contributor))
        for h in houses:
            out[(base + h - 1) % 12] += 1
    return out


def sav(chart: Chart) -> list[int]:
    """Sarvashtakavarga: summed bindus per sign across the seven BAVs."""
    total = [0] * 12
    for p in SEVEN_GRAHAS:
        for i, v in enumerate(bav(chart, p)):
            total[i] += v
    return total


# ---------------- Reductions & Pinda (v1.3) ----------------
# Trikona shodhana: within each element-trine, subtract the trine's
# minimum from all three signs.
# Ekadhipatya shodhana (validated against an independent report's
# tables and Shodhya Pinda): for each of the five two-sign lords, if
# both signs are occupied (by any of the 7 planets) no change;
# otherwise every UNOCCUPIED sign of the pair loses min(pair).
# Sun's and Moon's single signs are untouched.

RASI_MANA = [7, 10, 8, 4, 10, 5, 7, 8, 9, 5, 11, 12]
GRAHA_MANA = {"Sun": 5, "Moon": 5, "Mars": 8, "Mercury": 5,
              "Jupiter": 10, "Venus": 7, "Saturn": 5}
LORD_PAIRS = {"Mars": (0, 7), "Mercury": (2, 5), "Jupiter": (8, 11),
              "Venus": (1, 6), "Saturn": (9, 10)}


def trikona_shodhana(values: list[int]) -> list[int]:
    out = list(values)
    for trine in ((0, 4, 8), (1, 5, 9), (2, 6, 10), (3, 7, 11)):
        m = min(out[i] for i in trine)
        for i in trine:
            out[i] -= m
    return out


def ekadhipatya_shodhana(values: list[int], chart: Chart) -> list[int]:
    occupied = {chart.sign_idx_of(p) for p in SEVEN_GRAHAS}
    out = list(values)
    for a, b in LORD_PAIRS.values():
        occ_a, occ_b = a in occupied, b in occupied
        if occ_a and occ_b:
            continue
        m = min(out[a], out[b])
        if not occ_a:
            out[a] -= m
        if not occ_b:
            out[b] -= m
    return out


def reduced_bav(chart: Chart, planet: str) -> list[int]:
    return ekadhipatya_shodhana(trikona_shodhana(bav(chart, planet)), chart)


def shodhya_pinda(chart: Chart, planet: str) -> tuple[int, int, int]:
    """(rasi_pinda, graha_pinda, shodhya_pinda) for one planet's BAV."""
    red = reduced_bav(chart, planet)
    rasi = sum(v * RASI_MANA[i] for i, v in enumerate(red))
    graha = sum(red[chart.sign_idx_of(p)] * GRAHA_MANA[p]
                for p in SEVEN_GRAHAS)
    return rasi, graha, rasi + graha
