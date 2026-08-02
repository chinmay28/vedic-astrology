"""weekly.py - the week ahead, read as classical gochara.

Contract: pure computation over a natal Chart and an as-of date; every
ephemeris value comes through `ephemeris`. The week is Monday to Sunday,
the one containing the as-of date.

How it grades, and why: gochara is counted from the natal MOON, not the
Lagna, so every transit here carries its house-from-Moon; the
favourable-house table is the standard one (Phaladeepika / BPHS); the
Ashtakavarga bindus of the transited sign say how much ground a transit
has to work with (30+ strong, 24 or fewer thin); and the running dasha
says which of the chart's promises is switched on while all this passes.
Vedha (the classical obstruction rule) is deliberately NOT applied - a
half-implemented vedha would silently contradict standard software.

The output is weather, not events: themes to lean into and days to
treat gently, in the same register as guidance.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from . import ephemeris as eph
from .ashtakavarga import sav
from .dasha import pratyantardashas
from .dasha_now import locate, tone_of
from .model import (Chart, HOUSE_SIGNIFICATIONS, NAKSHATRAS,
                    NINE_GRAHAS, SIGNS, nakshatra_of, sign_of)
from .panchanga import tithi_of

# Classical gochara: houses counted FROM THE NATAL MOON in which each
# graha's transit is held favourable. Everything else is read as a
# quiet or testing passage for that graha's significations.
GOCHARA_GOOD = {
    "Sun": {3, 6, 10, 11},
    "Moon": {1, 3, 6, 7, 10, 11},
    "Mars": {3, 6, 11},
    "Mercury": {2, 4, 6, 8, 10, 11},
    "Jupiter": {2, 5, 7, 9, 11},
    "Venus": {1, 2, 3, 4, 5, 8, 9, 11, 12},
    "Saturn": {3, 6, 11},
    "Rahu": {3, 6, 11},
    "Ketu": {3, 6, 11},
}
MALEFICS = ("Sun", "Mars", "Saturn", "Rahu", "Ketu")
SLOW = ("Jupiter", "Saturn", "Rahu", "Ketu")   # a whole week in one sign

# What each graha's transit foregrounds, in one phrase.
KARAKA = {"Sun": "authority, vitality, the father, recognition",
          "Moon": "mood, the public, the mother, daily rhythm",
          "Mars": "drive, disputes, machinery, siblings",
          "Mercury": "speech, paperwork, trade, travel",
          "Jupiter": "counsel, teachers, growth, dharma",
          "Venus": "relationships, comfort, money, art",
          "Saturn": "structure, labour, delay, elders",
          "Rahu": "ambition, the unfamiliar, shortcuts",
          "Ketu": "detachment, research, loose ends"}


def _ord(n: int) -> str:
    """1st, 2nd, 3rd, 4th... - house counts read as ordinals in prose."""
    if 11 <= n <= 13:
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def week_bounds(asof: datetime) -> tuple[datetime, datetime]:
    """(Monday 00:00, the following Monday 00:00) around `asof`."""
    day = asof.replace(hour=0, minute=0, second=0, microsecond=0)
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=7)


def _grade(body: str, house: int) -> str:
    if house in GOCHARA_GOOD[body]:
        return "favourable"
    if house == 8 or (body in MALEFICS and house in (1, 4, 12)):
        return "testing"
    return "quiet"


def _dasha_week(natal: Chart, jd_mon: float, jd_next: float) -> dict:
    """Running MD/AD/PAD on Monday, plus any change inside the week."""
    md, ad, pad, _, _ = locate(natal, jd_mon)
    changes = []
    for _, _, lord, start, end in pratyantardashas(ad):
        if jd_mon < start < jd_next:
            changes.append({"date": eph.jd_to_date_str(start, natal.tz),
                            "what": f"Pratyantardasha turns to "
                                    f"{ad.lord}-{ad.sub}-{lord}"})
    if jd_mon < ad.end < jd_next:
        changes.append({"date": eph.jd_to_date_str(ad.end, natal.tz),
                        "what": f"the {ad.lord}-{ad.sub} Antardasha ends"})
    if jd_mon < md.end < jd_next:
        changes.append({"date": eph.jd_to_date_str(md.end, natal.tz),
                        "what": f"the {md.lord} Mahadasha ends - a "
                                "dasha-sandhi week"})
    tone = tone_of(natal, ad.sub or ad.lord)
    return {"md": md.lord, "ad": f"{ad.lord}-{ad.sub}",
            "pad": "-".join(pad[:3]), "tone": tone,
            "changes": sorted(changes, key=lambda c: c["date"]),
            "text": (f"The week runs inside the {md.lord} Mahadasha and the "
                     f"{ad.lord}-{ad.sub} Antardasha, whose lord "
                     f"{ad.sub} is {tone} in this chart - that is the "
                     "standing background the week's transits play over.")}


def _days(natal: Chart, monday: datetime, asof: datetime) -> list[dict]:
    moon_sign = natal.sign_idx_of("Moon")
    janma_nak = nakshatra_of(natal.bodies["Moon"].lon)[0]
    starts = [eph.positions(eph.jd_from_local(monday + timedelta(days=i),
                                              natal.tz))["Moon"].lon
              for i in range(8)]
    out = []
    for i in range(7):
        d = monday + timedelta(days=i)
        p = eph.positions(eph.jd_from_local(d.replace(hour=12), natal.tz))
        s = sign_of(p["Moon"].lon)[0]
        house = ((s - moon_sign) % 12) + 1
        grade = _grade("Moon", house)
        nak = nakshatra_of(p["Moon"].lon)[0]
        paksha, tn, tname = tithi_of(p["Sun"].lon, p["Moon"].lon)
        if house == 8:
            reading = ("chandrashtama - the Moon rides the 8th from your "
                       "natal Moon; the classical advice is to keep the "
                       "day light: no launches, no confrontations, rest")
        elif grade == "favourable":
            reading = (f"the {_ord(house)} from your natal Moon, a "
                       "classically favourable passage - the day carries "
                       "outward moves well")
        else:
            reading = (f"the {_ord(house)} from your natal Moon - a quiet "
                       "day by the classical table; steady work and "
                       "inner matters over new undertakings")
        # Flags are the things a compact day table cannot say: the
        # renderers list them separately, the prose note keeps them inline.
        flags = []
        if nak == janma_nak:
            flags.append("the Moon crosses your janma nakshatra: "
                         "traditionally a day for rest, ritual and "
                         "self-care rather than exertion")
        s_open, s_close = sign_of(starts[i])[0], sign_of(starts[i + 1])[0]
        if s_open != s:                       # the change already happened
            flags.append(f"the Moon entered {SIGNS[s]} earlier in the day, "
                         f"leaving {SIGNS[s_open]}")
        elif s_close != s:                    # ...or is still to come
            flags.append(f"the Moon leaves {SIGNS[s]} for "
                         f"{SIGNS[s_close]} later in the day")
        today = asof.date()
        when = ("today" if d.date() == today else
                "past" if d.date() < today else "ahead")
        out.append({
            "day": d.strftime("%A"), "date": d.strftime("%d %b"),
            "when": when,
            "moon_sign": SIGNS[s], "from_moon": house,
            "from_lagna": ((s - natal.lagna_idx) % 12) + 1,
            "nakshatra": nak, "tithi": f"{paksha} {tname}",
            "grade": grade, "flags": flags,
            "note": "; ".join([reading] + flags) + "."})
    return out


def _transits(natal: Chart, jd_mon: float, jd_next: float) -> list[dict]:
    moon_sign = natal.sign_idx_of("Moon")
    bindus = sav(natal)
    start, end = eph.positions(jd_mon), eph.positions(jd_next)
    out = []
    for body in NINE_GRAHAS:
        if body == "Moon":                       # the Moon has its own table
            continue
        s0 = sign_of(start[body].lon)[0]
        s1 = sign_of(end[body].lon)[0]
        house = ((s0 - moon_sign) % 12) + 1
        grade = _grade(body, house)
        row = {"body": body, "sign": SIGNS[s0], "from_moon": house,
               "from_lagna": ((s0 - natal.lagna_idx) % 12) + 1,
               "sav": bindus[s0], "grade": grade,
               "retro": bool(start[body].retro and body != "Ketu"),
               "ingress": (f"moves into {SIGNS[s1]} this week"
                           if s1 != s0 else None),
               "themes": HOUSE_SIGNIFICATIONS[house][1],
               "karaka": KARAKA[body]}
        out.append(row)
    return out


def _phrase(t: dict) -> str:
    ground = ("strong ground" if t["sav"] >= 30 else
              "thin ground" if t["sav"] <= 24 else "average ground")
    return (f"{t['body']} in {t['sign']}, the {_ord(t['from_moon'])} from "
            f"your Moon ({t['sav']} bindus - {ground}): {t['themes']}")


def _synthesis(dasha: dict, days: list[dict],
               transits: list[dict]) -> tuple[str, list[str], list[str]]:
    good = [t for t in transits if t["grade"] == "favourable"]
    hard = [t for t in transits if t["grade"] == "testing"]
    bright = [d for d in days if d["grade"] == "favourable"]
    themes = [_phrase(t) + " - lean into these." for t in good]
    cautions = [_phrase(t) + " - the passage asks for patience here, not "
                "force." for t in hard]
    for d in days:
        if d["from_moon"] == 8:
            cautions.append(f"{d['day']} {d['date']} is chandrashtama "
                            "(Moon in the 8th from your natal Moon) - keep "
                            "it light and unscheduled where you can.")
    for t in transits:
        if t["ingress"]:
            themes.append(f"{t['body']} {t['ingress']} - the {t['karaka']} "
                          "it carries change house mid-week; expect the "
                          "texture to shift with it.")
    weight = ("a supported week" if len(good) > len(hard) else
              "a testing week" if len(hard) > len(good) else
              "an evenly balanced week")
    headline = (
        f"{weight.capitalize()}: {len(good)} of {len(transits)} transits sit "
        f"in classically favourable houses from your natal Moon, "
        f"{len(bright)} of the 7 days carry the Moon through a favourable "
        f"house, and all of it runs inside a {dasha['tone']} "
        f"{dasha['ad']} chapter.")
    if not themes:
        themes.append("No transit sits in a classically favourable house "
                      "this week - a maintenance week by the gochara "
                      "table; work the routine and let the calendar turn.")
    if not cautions:
        cautions.append("Nothing in the week's gochara is classically "
                        "adverse - the ordinary cautions apply and no "
                        "more.")
    return headline, themes, cautions


def week_outlook(natal: Chart, asof: datetime,
                 today: datetime | None = None) -> dict:
    """The week containing `asof`, Monday to Sunday, as gochara weather.

    `today` (the real one, which the caller owns - this module never
    reads the clock) only decides the `current` flag: with the as-of
    date free to move, "is this the week I am living in" is a question
    the payload cannot answer from `asof` alone.
    """
    monday, next_monday = week_bounds(asof)
    jd_mon = eph.jd_from_local(monday, natal.tz)
    jd_next = eph.jd_from_local(next_monday, natal.tz)
    sunday = next_monday - timedelta(days=1)

    dasha = _dasha_week(natal, jd_mon, jd_next)
    days = _days(natal, monday, asof)
    transits = _transits(natal, jd_mon, jd_next)
    headline, themes, cautions = _synthesis(dasha, days, transits)
    spent = sum(1 for d in days if d["when"] == "past")
    if spent:
        headline += (" One of the seven days is already past." if spent == 1
                     else f" {spent} of the seven days are already past.")
    return {
        "from": monday.strftime("%d %b %Y"),
        "to": sunday.strftime("%d %b %Y"),
        # ISO handles for the GUI's week stepper (it re-asks for a
        # summary with that as-of date; nothing is cached client-side).
        "monday": monday.strftime("%Y-%m-%d"),
        "prev": (monday - timedelta(days=7)).strftime("%Y-%m-%d"),
        "next": next_monday.strftime("%Y-%m-%d"),
        "label": f"Week of {monday.strftime('%d %b')} - "
                 f"{sunday.strftime('%d %b %Y')}",
        "current": today is not None and monday <= today < next_monday,
        "headline": headline, "dasha": dasha, "days": days,
        "transits": transits, "themes": themes, "cautions": cautions,
        "best_days": [f"{d['day']} {d['date']}" for d in days
                      if d["grade"] == "favourable"],
        "guarded_days": [f"{d['day']} {d['date']}" for d in days
                         if d["grade"] == "testing"],
    }
