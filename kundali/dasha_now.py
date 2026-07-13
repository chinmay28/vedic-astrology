"""dasha_now.py - the "where am I in the dasha cycle" section.

Locates the running Mahadasha / Antardasha / Pratyantardasha for an
as-of date, plus the next AD and next MD, and generates navigation
guidance from each lord's NATAL condition (house, dignity, Vimshopaka
score, aspects received). The guidance is rule-based and classical in
framing: themes to lean into, cautions to hold - not event predictions.
"""
from __future__ import annotations

from . import ephemeris as eph
from .aspects import SPECIAL
from .dasha import Period, antardashas, mahadashas, pratyantardashas
from .model import (BENEFICS, Chart, HOUSE_SIGNIFICATIONS, NINE_GRAHAS,
                    SIGNS, dignity, sign_of)
from .varga import vimshopaka

KENDRAS, TRIKONAS = {1, 4, 7, 10}, {1, 5, 9}
DUSTHANAS, UPACHAYAS = {6, 8, 12}, {3, 6, 10, 11}


def locate(natal: Chart, jd_asof: float):
    """(current_md, current_ad, current_pad, next_ad, next_md)."""
    mds = mahadashas(natal.bodies["Moon"].lon, natal.jd)
    md = next((m for m in mds if m.start <= jd_asof < m.end), mds[-1])
    ads = antardashas(md)
    ad = next((a for a in ads if a.start <= jd_asof < a.end), ads[-1])
    pads = pratyantardashas(ad)
    pad = next((p for p in pads if p[3] <= jd_asof < p[4]), pads[-1])
    i = ads.index(ad)
    if i + 1 < len(ads):
        next_ad = ads[i + 1]
    else:
        nxt_md = mds[min(mds.index(md) + 1, len(mds) - 1)]
        next_ad = antardashas(nxt_md)[0]
    next_md = mds[min(mds.index(md) + 1, len(mds) - 1)]
    return md, ad, pad, next_ad, next_md


def _aspects_on(natal: Chart, planet: str) -> tuple[list[str], list[str]]:
    """(benefics aspecting `planet`, malefics aspecting it)."""
    h = natal.house_of(planet)
    ben, mal = [], []
    for p in NINE_GRAHAS:
        if p == planet:
            continue
        ph = natal.house_of(p)
        for off in SPECIAL[p]:
            if ((ph - 1 + off - 1) % 12) + 1 == h:
                (ben if p in BENEFICS else mal).append(p)
    return sorted(set(ben)), sorted(set(mal))


def lord_condition(natal: Chart, planet: str,
                   vimsho: dict[str, float]) -> dict:
    s, d = sign_of(natal.bodies[planet].lon)
    h = natal.house_of(planet)
    ben, mal = _aspects_on(natal, planet)
    return {"planet": planet, "sign": SIGNS[s], "house": h,
            "dignity": dignity(planet, s, d),
            "score": vimsho.get(planet),          # None for nodes
            "themes": HOUSE_SIGNIFICATIONS[h][1],
            "benefic_aspects": ben, "malefic_aspects": mal,
            "combust": planet in natal.combust() and planet != "Sun"}


def _tone(c: dict) -> str:
    good = c["dignity"] in ("Exalted", "Moolatrikona", "Own sign")
    weak = c["dignity"] in ("Debilitated", "Enemy's sign") or c["combust"]
    if c["score"] is not None:
        good = good or c["score"] >= 13
        weak = weak or c["score"] < 9
    if good and not weak:
        return "strong"
    if weak and not good:
        return "challenged"
    return "mixed"


def age_note(natal: Chart, jd_asof: float) -> str | None:
    """Child charts must not get adult template guidance - the classical
    convention reads a minor's periods through development, health and
    the household, with agency belonging to the parents."""
    years = (jd_asof - natal.jd) / 365.25
    if years < 12:
        return ("Note: the native is a child (age "
                f"{years:.1f}). Read every period theme below through "
                "development, health, education and the household - the "
                "classical convention for minors - rather than through "
                "adult agency (career moves, partnership decisions).")
    return None


def guidance_for(natal: Chart, c: dict, role: str) -> str:
    """One paragraph of navigation guidance for a period lord."""
    p, h = c["planet"], c["house"]
    bits = [f"The {role} lord {p} sits natally in your house {h} "
            f"({c['sign']}, {c['dignity']}"
            + (f", Vimshopaka {c['score']}/20" if c["score"] else "") + ")"
            + (", combust" if c["combust"] else "")
            + f" - so this period foregrounds house-{h} matters: {c['themes']}."]
    tone = _tone(c)
    if tone == "strong":
        bits.append(f"A well-conditioned lord: the tradition reads its periods "
                    f"as delivery time - initiate, commit, and build in these "
                    f"areas rather than waiting them out.")
    elif tone == "challenged":
        bits.append(f"A strained lord: treat this period as maintenance, not "
                    f"expansion - consolidate, avoid overcommitting in "
                    f"house-{h} matters, and let remedial patience (routine, "
                    f"service, humility - {p}'s classical antidotes) do the work.")
    else:
        bits.append("A mixed-condition lord: expect uneven delivery - "
                    "the supported themes advance while the strained ones "
                    "demand maintenance; move on concrete openings, not "
                    "momentum.")
    if h in KENDRAS or h in TRIKONAS:
        bits.append(f"House {h} is a {'kendra' if h in KENDRAS else ''}"
                    f"{'/' if h in KENDRAS and h in TRIKONAS else ''}"
                    f"{'trikona' if h in TRIKONAS else ''} - structurally "
                    "supportive ground.")
    elif h in DUSTHANAS:
        bits.append(f"House {h} is a dusthana: the period works through "
                    "difficulty, depth or service"
                    + (" (an upachaya too - it improves with sustained effort)"
                       if h in UPACHAYAS else "")
                    + "; its gifts are earned, not given.")
    if c["benefic_aspects"]:
        bits.append(f"{', '.join(c['benefic_aspects'])} aspect the lord - "
                    "supervision and softening are built in.")
    if c["malefic_aspects"] and not c["benefic_aspects"]:
        bits.append(f"Only {', '.join(c['malefic_aspects'])} aspect the lord - "
                    "the period runs unsoftened; add the moderation yourself.")
    return " ".join(bits)


def sandhi_note(md: Period, ad: Period, jd_asof: float, tz: str) -> str | None:
    """Warn when within ~3 months of a Mahadasha boundary (dasha-sandhi)."""
    for edge, label in ((md.start, "began"), (md.end, "ends")):
        if abs(jd_asof - edge) < 91:
            return (f"Dasha-sandhi: the Mahadasha {label} near "
                    f"{eph.jd_to_date_str(edge, tz)}. The junction between "
                    "two great periods is classically a transition zone - "
                    "themes of the outgoing lord unwind while the incoming "
                    "lord's are not yet established. Favor completion over "
                    "launch until the new period settles (a few months in).")
    return None
