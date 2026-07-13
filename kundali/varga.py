"""varga.py - divisional charts. v1.1 implements the Navamsa (D-9).

The D-9 sign follows the classical start-sign rule: movable signs count
navamsas from themselves, fixed signs from the 9th, dual signs from the
5th. This is equivalent to the closed form used here:

    navamsa_sign = (sign_index * 9 + navamsa_number) mod 12

The equivalence is asserted by a property test in the suite.
"""
from __future__ import annotations

from datetime import datetime

from .ephemeris import BodyPosition
from .model import Chart, NINE_GRAHAS, sign_of

NAV_SPAN = 10 / 3  # 3 deg 20 min


def navamsa_sign(lon: float) -> int:
    s, deg = sign_of(lon)
    return (s * 9 + int(deg // NAV_SPAN)) % 12


def navamsa_sign_by_rule(lon: float) -> int:
    """Independent derivation via the movable/fixed/dual start rule."""
    s, deg = sign_of(lon)
    start = {0: 0, 1: 8, 2: 4}[s % 3]        # self / 9th / 5th
    return (s + start + int(deg // NAV_SPAN)) % 12


def navamsa_chart(natal: Chart) -> Chart:
    """A Chart whose signs are the D-9 signs.

    Synthetic degrees are the position within the navamsa scaled to
    0-30, so dignity/diagram code works unchanged. Houses are counted
    from the navamsa Lagna, per standard practice.
    """
    def synth(lon: float, retro: bool) -> BodyPosition:
        _, deg = sign_of(lon)
        within = (deg % NAV_SPAN) * 9
        return BodyPosition(navamsa_sign(lon) * 30 + within, -1 if retro else 1, retro)

    bodies = {b: synth(p.lon, p.retro) for b, p in natal.bodies.items()}
    asc = synth(natal.asc, False).lon
    return Chart(name=natal.name + " D-9", dt_local=natal.dt_local,
                 tz=natal.tz, place=natal.place, lat=natal.lat, lon=natal.lon,
                 jd=natal.jd, asc=asc, bodies=bodies,
                 ayanamsa_name=natal.ayanamsa_name,
                 ayanamsa_deg=natal.ayanamsa_deg)


# ---------------- Full Shodashavarga (v1.3) ----------------
# Each rule: given (sign s, deg d in sign) -> varga sign index.
# Special lords for D-2 and D-30 map to fixed signs.

def _movable_fixed_dual(s: int, starts: tuple[int, int, int], n: int, d: float) -> int:
    start = starts[s % 3]
    return (start + int(d // (30 / n))) % 12


def varga_sign(lon: float, n: int) -> int:
    """Sign index of `lon` in the D-n chart (Parashari rules)."""
    from .model import sign_of
    s, d = sign_of(lon)
    odd = s % 2 == 0            # Aries=0 is an ODD sign (1st)
    if n == 1:
        return s
    if n == 2:                  # Hora: Leo / Cancer halves
        first = d < 15
        return 4 if (odd == first) else 3
    if n == 3:                  # Drekkana: 1st/5th/9th from sign
        return (s + 4 * int(d // 10)) % 12
    if n == 4:                  # Chaturthamsha: kendras from sign
        return (s + 3 * int(d // 7.5)) % 12
    if n == 7:                  # Saptamsha: odd from sign, even from 7th
        start = s if odd else (s + 6) % 12
        return (start + int(d // (30 / 7))) % 12
    if n == 9:
        return navamsa_sign(lon)
    if n == 10:                 # Dashamsha: odd from sign, even from 9th
        start = s if odd else (s + 8) % 12
        return (start + int(d // 3)) % 12
    if n == 12:                 # Dwadashamsha: from the sign itself
        return (s + int(d // 2.5)) % 12
    if n == 16:                 # Shodashamsha: mov Ari, fix Leo, dual Sag
        return _movable_fixed_dual(s, (0, 4, 8), 16, d)
    if n == 20:                 # Vimshamsha: mov Ari, fix Sag, dual Leo
        return _movable_fixed_dual(s, (0, 8, 4), 20, d)
    if n == 24:                 # Chaturvimshamsha: odd Leo, even Cancer
        start = 4 if odd else 3
        return (start + int(d // 1.25)) % 12
    if n == 27:                 # Bhamsha: fire Ari, earth Can, air Lib, water Cap
        start = {0: 0, 1: 3, 2: 6, 3: 9}[s % 4]
        return (start + int(d // (30 / 27))) % 12
    if n == 30:                 # Trimshamsha: unequal lord segments
        odd_map = [(5, 0), (10, 10), (18, 8), (25, 2), (30, 6)]
        even_map = [(5, 1), (12, 5), (20, 11), (25, 9), (30, 7)]
        for hi, sign in (odd_map if odd else even_map):
            if d < hi:
                return sign
    if n == 40:                 # Khavedamsha: odd Aries, even Libra
        start = 0 if odd else 6
        return (start + int(d // 0.75)) % 12
    if n == 45:                 # Akshavedamsha: mov Ari, fix Leo, dual Sag
        return _movable_fixed_dual(s, (0, 4, 8), 45, d)
    if n == 60:                 # Shashtiamsha: from the sign itself
        return (s + int(d // 0.5)) % 12
    raise ValueError(f"unsupported varga D-{n}")


SHODASHAVARGA = [1, 2, 3, 4, 7, 9, 10, 12, 16, 20, 24, 27, 30, 40, 45, 60]
VARGA_NAMES = {1: "Rashi", 2: "Hora", 3: "Drekkana", 4: "Chaturthamsha",
               7: "Saptamsha", 9: "Navamsa", 10: "Dashamsha",
               12: "Dwadashamsha", 16: "Shodashamsha", 20: "Vimshamsha",
               24: "Chaturvimshamsha", 27: "Bhamsha", 30: "Trimshamsha",
               40: "Khavedamsha", 45: "Akshavedamsha", 60: "Shashtiamsha"}
VARGA_AREAS = {1: "the whole", 2: "wealth", 3: "siblings, courage",
               4: "property, fortune", 7: "children", 9: "spouse, maturation",
               10: "career", 12: "parents", 16: "vehicles, comforts",
               20: "spiritual practice", 24: "learning", 27: "strengths",
               30: "adversity", 40: "auspiciousness (maternal)",
               45: "conduct (paternal)", 60: "totality of karma"}
VIMSHOPAKA_WEIGHTS = {1: 3.5, 2: 1, 3: 1, 4: 0.5, 7: 0.5, 9: 3, 10: 0.5,
                      12: 0.5, 16: 2, 20: 0.5, 24: 0.5, 27: 0.5, 30: 1,
                      40: 0.5, 45: 0.5, 60: 4}


def shodashavarga_table(natal: Chart) -> list[list[str]]:
    """Rows: planet; columns: the 16 vargas (3-letter signs)."""
    from .model import NINE_GRAHAS, SIGNS
    rows = [["Graha"] + [f"D{n}" for n in SHODASHAVARGA]]
    for b in NINE_GRAHAS:
        rows.append([b[:4]] + [SIGNS[varga_sign(natal.bodies[b].lon, n)][:3]
                               for n in SHODASHAVARGA])
    return rows


def vimshopaka(natal: Chart) -> dict[str, float]:
    """Composite varga strength out of 20 for the seven planets, using
    compound (panchadha) friendship dignity in each varga."""
    from .maitri import VIMSHOPAKA_POINTS, relation_to_sign_lord
    from .model import SEVEN_GRAHAS
    out = {}
    for p in SEVEN_GRAHAS:
        total = 0.0
        for n in SHODASHAVARGA:
            vs = varga_sign(natal.bodies[p].lon, n)
            rel = relation_to_sign_lord(natal, p, vs)
            total += VIMSHOPAKA_WEIGHTS[n] * VIMSHOPAKA_POINTS[rel]
        out[p] = round(total / 20, 2)
    return out


def vargottama(natal: Chart) -> list[str]:
    """Bodies occupying the same sign in D-1 and D-9 (strengthened)."""
    return [b for b in NINE_GRAHAS
            if natal.sign_idx_of(b) == navamsa_sign(natal.bodies[b].lon)]
