"""aspects.py - whole-sign graha drishti, and what each aspect implies.

Rules: every graha aspects the 7th from itself; Mars adds 4th & 8th,
Jupiter 5th & 9th, Saturn 3rd & 10th. Nodes: 7th only (classical).

The second half of the module is the interpretive layer. `readings()`
turns every planet-to-planet drishti (and every drishti on the Lagna)
into one rule-based paragraph: the aspecting graha's gaze, applied to
the karakatva of what it looks at and to the house that matter works
out through, graded supportive / mixed / testing from the aspecting
graha's natural nature, its dignity and combustion, and its natural
friendship toward what it aspects. Themes and cautions in the classical
register - not event predictions.
"""
from __future__ import annotations

from .model import (BENEFICS, Chart, ENEMIES, FRIENDS, HOUSE_SIGNIFICATIONS,
                    NINE_GRAHAS, SIGNS, SIGN_LORD, dignity, sign_of)

SPECIAL = {
    "Sun": [7], "Moon": [7], "Mercury": [7], "Venus": [7],
    "Mars": [4, 7, 8], "Jupiter": [5, 7, 9], "Saturn": [3, 7, 10],
    "Rahu": [7], "Ketu": [7],
}

LAGNA = "Lagna"


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


# --------------------------------------------------- the interpretive layer

# What a graha's gaze does to whatever it falls on.
GAZE = {
    "Sun": "lights up and exposes what it falls on - authority, "
           "visibility and the father's line enter the matter, and so "
           "does the heat of ego",
    "Moon": "moistens what it falls on - feeling, receptivity and the "
            "public reach the matter, together with the Moon's own "
            "changeability",
    "Mars": "energises and pressures what it falls on - drive, "
            "competition and a cutting edge, buying speed at the cost "
            "of friction",
    "Mercury": "articulates what it falls on - analysis, speech and "
               "exchange enter the matter, along with a restlessness "
               "that can leave it skimmed rather than settled",
    "Jupiter": "protects and expands what it falls on - the classics "
               "rate this the most benign drishti: counsel, growth and "
               "rescue where it lands",
    "Venus": "sweetens what it falls on - refinement, comfort and "
             "relationship enter the matter, with a standing temptation "
             "to postpone the hard call",
    "Saturn": "restrains and matures what it falls on - delay, duty and "
              "contraction first, durability afterwards",
    "Rahu": "amplifies and distorts what it falls on - ambition, "
            "foreign and unconventional routes, and a blurred sense of "
            "the matter's real size",
    "Ketu": "dissolves and detaches what it falls on - refinement "
            "through loss, and a researching, inward turn where "
            "engagement was expected",
}

# What each graha stands for - the karakatva an aspect reaches.
KARAKA = {
    "Sun": "vitality, authority, the father and the visible self",
    "Moon": "the mind, the mother, receptivity and the public",
    "Mars": "energy, courage, siblings, land and conflict",
    "Mercury": "speech, intellect, learning and commerce",
    "Jupiter": "wisdom, wealth, children, gurus and dharma",
    "Venus": "spouse, pleasure, art, vehicles and refinement",
    "Saturn": "discipline, labour, longevity, the old and the poor",
    "Rahu": "desire, foreignness and unconventional means",
    "Ketu": "detachment, insight, ancestry and the unfinished past",
    LAGNA: "the body, the temperament and the direction of the life itself",
}

# The special drishtis, each with the flavour the classics give it.
DRISHTI_NOTE = {
    ("Mars", 4): "Mars' 4th, a strike on the settled ground of the matter",
    ("Mars", 8): "Mars' 8th, pressure arriving suddenly and out of sight",
    ("Jupiter", 5): "Jupiter's 5th, the trinal gaze of counsel and merit",
    ("Jupiter", 9): "Jupiter's 9th, the trinal gaze of fortune and "
                    "protection",
    ("Saturn", 3): "Saturn's 3rd, a grinding weight on effort and "
                   "initiative",
    ("Saturn", 10): "Saturn's 10th, a long structuring weight on action "
                    "and its results",
}
FULL_NOTE = "the 7th, the facing drishti every graha casts in full"

ORDINAL = {3: "3rd", 4: "4th", 5: "5th", 7: "7th", 8: "8th", 9: "9th",
           10: "10th"}

STRONG_DIGNITY = ("Exalted", "Moolatrikona", "Own sign")
WEAK_DIGNITY = ("Debilitated", "Enemy's sign")

TONE_TEXT = {
    "supportive": "Read it as support - the matter runs supervised, and "
                  "the tradition takes that protection as built in "
                  "rather than as something to arrange.",
    "mixed": "Read it as mixed - help and cost arrive together; take "
             "the discipline as the price of the support.",
    "testing": "Read it as pressure - the matter still delivers, but on "
               "{ap} terms and after {ap} price is paid; supply the "
               "moderation yourself.",
}


def _poss(name: str) -> str:
    """Mars' / Jupiter's - the possessive the prose needs."""
    return name + ("'" if name.endswith("s") else "'s")


def nature(chart: Chart, planet: str) -> str:
    """'benefic' / 'malefic' for the aspecting graha.

    Fixed naisargika nature, with the one classical variable the
    tradition insists on: the Moon is benefic waxing and malefic waning.
    Mercury is graded benefic here (as everywhere in this package), while
    the classics have it take the colour of its company - said out loud
    in the section guidance rather than half-modelled.
    """
    if planet == "Moon":
        elong = (chart.bodies["Moon"].lon - chart.bodies["Sun"].lon) % 360
        return "benefic" if 0 < elong < 180 else "malefic"
    return "benefic" if planet in BENEFICS else "malefic"


def _relation(aspecting: str, target: str, lagna_lord: str) -> str:
    """Natural friendship of the aspecting graha toward what it sees.

    The Lagna is judged through its lord, which is how the classics read
    a drishti on a sign nobody occupies. Nodes own no sign and appear in
    no maitri table, so any pairing with one is 'neutral'.
    """
    other = lagna_lord if target == LAGNA else target
    if aspecting not in FRIENDS or other not in FRIENDS:
        return "neutral"
    if other in FRIENDS[aspecting]:
        return "friend"
    if other in ENEMIES[aspecting]:
        return "enemy"
    return "neutral"


def _grade(chart: Chart, aspecting: str, target: str,
           lagna_lord: str) -> tuple[str, str]:
    """(tone, the sentence saying why) for one drishti."""
    s, d = sign_of(chart.bodies[aspecting].lon)
    dig = dignity(aspecting, s, d)
    nat = nature(chart, aspecting)
    rel = _relation(aspecting, target, lagna_lord)
    combust = aspecting != "Sun" and aspecting in chart.combust()

    score = 1 if nat == "benefic" else -1
    if dig in STRONG_DIGNITY:
        score += 1
    elif dig in WEAK_DIGNITY:
        score -= 1
    if rel == "friend":
        score += 1
    elif rel == "enemy":
        score -= 1
    if combust:
        score -= 1
    tone = ("supportive" if score >= 1
            else "testing" if score <= -1 else "mixed")

    if aspecting == "Moon":
        why = [f"the Moon is {'waxing' if nat == 'benefic' else 'waning'}"
               f" (a {nat} by the classical rule)"]
    else:
        why = [f"{aspecting} is a natural {nat}"]
    if dig in STRONG_DIGNITY:
        why.append(f"dignified ({dig})")
    elif dig in WEAK_DIGNITY:
        why.append(f"weakly placed ({dig})")
    if combust:
        why.append("combust")
    if rel != "neutral":
        named = (f"{lagna_lord}, your Lagna lord" if target == LAGNA
                 else target)
        why.append(f"and counts {named} "
                   + ("a friend" if rel == "friend" else "an enemy"))
    return tone, "Why: " + ", ".join(why) + "."


def readings(chart: Chart) -> list[dict]:
    """One rule-based paragraph per drishti cast in this chart.

    Covers planet-to-planet aspects and aspects on the Lagna (a house
    nobody occupies is still aspected, and the 1st is the one the whole
    chart is read from). Ordered by the aspecting graha, then by the
    house the aspect lands in.
    """
    lagna_lord = SIGN_LORD[chart.lagna_idx]
    mutual = {frozenset(p) for p in mutual_pairs(chart)}
    targets = [(b, chart.house_of(b), chart.sign_idx_of(b))
               for b in NINE_GRAHAS]
    targets.append((LAGNA, 1, chart.lagna_idx))

    out = []
    for a in NINE_GRAHAS:
        ah = chart.house_of(a)
        for off in SPECIAL[a]:
            house = ((ah - 1 + off - 1) % 12) + 1
            note = DRISHTI_NOTE.get((a, off), FULL_NOTE)
            for b, bh, bsign in targets:
                if bh != house or b == a:
                    continue
                tone, why = _grade(chart, a, b, lagna_lord)
                is_mutual = frozenset({a, b}) in mutual
                what = (f"the Lagna itself ({SIGNS[bsign]})" if b == LAGNA
                        else f"{b} in house {house} ({SIGNS[bsign]})")
                text = (
                    f"{a} casts its {ORDINAL[off]} on {what}"
                    f" - {note}. {a} {GAZE[a]}; "
                    f"here that reaches {KARAKA[b]}, as those matters "
                    f"work out through house {house}: "
                    f"{HOUSE_SIGNIFICATIONS[house][1]}. "
                    f"{TONE_TEXT[tone].format(ap=_poss(a))} {why}")
                if is_mutual:
                    text += (f" {b} aspects {a} back: a standing dialogue "
                             "between the two, not a one-way influence.")
                out.append({
                    "from": a, "to": b, "offset": off,
                    "drishti": ORDINAL[off], "house": house,
                    "sign": SIGNS[bsign], "target_is_lagna": b == LAGNA,
                    "mutual": is_mutual, "tone": tone, "text": text})
    out.sort(key=lambda r: (NINE_GRAHAS.index(r["from"]), r["house"],
                            r["to"]))
    return out


def unaspected(chart: Chart) -> list[str]:
    """Grahas no other graha aspects - unsupervised rather than free."""
    seen = {b for _, b, _ in edges(chart)}
    return [p for p in NINE_GRAHAS if p not in seen]
