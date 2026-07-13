"""sadesati.py - lifetime table of Saturn's sensitive transits from the
natal Moon: the three Sade Sati phases plus Kantaka (4th) and Ashtama
(8th) Shani. Cross-validated against an independent commercial report
(phase-change dates agreed within ~2 days).
"""
from __future__ import annotations

from . import ephemeris as eph
from .model import Chart, SIGNS

PHASES = {11: "Sade Sati - first phase (12th from Moon)",
          0: "Sade Sati - CORE (Saturn on the Moon sign)",
          1: "Sade Sati - final phase (2nd from Moon)",
          3: "Kantaka Shani (4th from Moon)",
          7: "Ashtama Shani (8th from Moon)"}


MURTI = {1: "Gold", 6: "Gold", 11: "Gold", 2: "Silver", 5: "Silver",
         9: "Silver", 3: "Copper", 7: "Copper", 10: "Copper",
         4: "Iron", 8: "Iron", 12: "Iron"}
MURTI_GRADE = {"Gold": "very favorable", "Silver": "favorable",
               "Copper": "mixed", "Iron": "heavy"}

IMPACTS = {
    11: ("The rising phase. Classical themes: expenditure climbs, sleep and "
         "rest are disturbed, groundwork quietly dissolves before the "
         "rebuild. Twelfth-house matters (losses, foreign affairs, "
         "seclusion) come forward. Best used as a preparation phase: "
         "simplify, close open loops, reduce fixed costs."),
    0: ("The core (janma-shani). Saturn crosses the natal Moon itself - "
        "classically the heaviest stretch: pressure on the mind and "
        "emotions, workload without proportionate recognition, health and "
        "vitality demanding maintenance, responsibilities toward the "
        "mother figure. The tradition calls it the great restructuring: "
        "what is load-bearing in the life is tested; what passes the test "
        "becomes permanent."),
    1: ("The setting phase. Second-house matters carry the weight: family "
        "finances under review, obligations to kin, consequences of "
        "speech. Pressure eases in texture but bills - literal and "
        "figurative - are settled here. A consolidation-and-release "
        "phase."),
    3: ("Kantaka Shani - the 'thorn in the foot'. Fourth-house heaviness: "
        "domestic unrest, property and vehicle matters, the sense that "
        "progress is impeded mid-stride. Shorter and lighter than Sade "
        "Sati; met best with patience in home affairs."),
    7: ("Ashtama Shani - Saturn in the 8th from the Moon, classically the "
        "sharpest of the short transits: sudden changes, health vigilance, "
        "stress around joint or inherited resources. Conservative "
        "commitments and routine health care are the traditional "
        "counsel."),
}

NAVIGATION = (
    "Saturn's periods reward exactly one strategy, in every classical "
    "source: steady, honest, unglamorous work. Keep routines (sleep, "
    "exercise, accounts) non-negotiable; favor maintenance over "
    "expansion and completion over launch; avoid shortcuts, disputes "
    "and litigation, which Saturn transits notoriously prolong; serve - "
    "elders, subordinates, anyone Saturn signifies - since seva is the "
    "tradition's first remedy; and measure progress in structure built, "
    "not recognition received. What Sade Sati removes is, in the "
    "classical reading, what was not load-bearing.")


def _raw_spans(natal: Chart, years: int = 90):
    """[(start_jd, end_jd, sign_idx, phase_offset)] for sensitive spans."""
    eph.set_ayanamsa(natal.ayanamsa_name)   # swe sid-mode is global state
    moon_sign = natal.sign_idx_of("Moon")
    jd0, jd1 = natal.jd, natal.jd + years * 365.25
    spans = [(jd0, natal.sign_idx_of("Saturn"))]
    spans += [(jd, to) for jd, _, to in eph.sign_ingresses("Saturn", jd0, jd1)]
    out = []
    for i, (start, sign) in enumerate(spans):
        end = spans[i + 1][0] if i + 1 < len(spans) else jd1
        off = (sign - moon_sign) % 12
        if off in PHASES:
            out.append((start, end, sign, off))
    return out


def murti(natal: Chart, ingress_jd: float) -> tuple[str, str]:
    """(metal, grade) from the transit Moon's house from the natal Moon
    at Saturn's ingress moment - the classical Murti system."""
    eph.set_ayanamsa(natal.ayanamsa_name)
    moon = eph.positions(ingress_jd)["Moon"].lon
    house = ((int(moon // 30) - natal.sign_idx_of("Moon")) % 12) + 1
    m = MURTI[house]
    return m, MURTI_GRADE[m]


def lifetime_table(natal: Chart, years: int = 90):
    """[(from, to, saturn_sign, phase_label, murti)] in the natal tz."""
    rows = []
    for start, end, sign, off in _raw_spans(natal, years):
        m, _ = murti(natal, start) if start > natal.jd else ("-", "")
        rows.append((eph.jd_to_date_str(start, natal.tz),
                     eph.jd_to_date_str(end, natal.tz),
                     SIGNS[sign], PHASES[off], m))
    return rows


def current_status(natal: Chart, jd_asof: float):
    """(active_span_or_None, next_span_or_None); spans are
    (start_jd, end_jd, sign_idx, phase_offset)."""
    spans = _raw_spans(natal)
    active = next((s for s in spans if s[0] <= jd_asof < s[1]), None)
    nxt = next((s for s in spans if s[0] > jd_asof), None)
    return active, nxt


def severity_profile(natal: Chart) -> tuple[str, list[tuple[str, str]]]:
    """('mild'|'moderate'|'demanding', [(factor, finding), ...]).

    Grades how Sade Sati tends to run for THIS chart from four
    computable factors; every factor is shown with its reason."""
    from .ashtakavarga import sav
    from .model import SIGN_LORD, YOGAKARAKA, dignity, sign_of
    from .varga import vimshopaka
    factors, score = [], 0

    yk = YOGAKARAKA.get(natal.lagna_idx)
    if yk == "Saturn":
        factors.append(("Saturn's role for this Lagna",
                        "YOGAKARAKA - the classical strongest mitigation; "
                        "authorities read Sade Sati mildly for these Lagnas"))
        score += 2
    else:
        owned = sorted(((s - natal.lagna_idx) % 12) + 1
                       for s, l in SIGN_LORD.items() if l == "Saturn")
        good = any(h in (1, 4, 5, 7, 9, 10, 11) for h in owned)
        factors.append(("Saturn's role for this Lagna",
                        f"lord of houses {owned[0]} and {owned[1]} - "
                        + ("a functional contributor" if good
                           else "a functional challenger")))
        score += 1 if good else -1

    s_idx, s_deg = sign_of(natal.bodies["Saturn"].lon)
    dig = dignity("Saturn", s_idx, s_deg)
    vim = vimshopaka(natal)["Saturn"]
    strong = dig in ("Exalted", "Moolatrikona", "Own sign") or vim >= 13
    factors.append(("Natal Saturn condition",
                    f"{dig}, Vimshopaka {vim}/20 - "
                    + ("a dignified Saturn disciplines rather than punishes"
                       if strong else "an average-or-weaker Saturn presses "
                       "harder; keep the remedial routines strict")))
    score += 1 if strong else -1

    m_idx, m_deg = sign_of(natal.bodies["Moon"].lon)
    from .aspects import SPECIAL
    from .model import NINE_GRAHAS, BENEFICS
    mh = natal.house_of("Moon")
    protectors = sorted({p for p in BENEFICS for off in SPECIAL[p]
                         if ((natal.house_of(p) - 1 + off - 1) % 12) + 1 == mh})
    mdig = dignity("Moon", m_idx, m_deg)
    prot = bool(protectors) or mdig in ("Exalted", "Moolatrikona", "Own sign")
    factors.append(("Natal Moon protection",
                    f"{mdig}"
                    + (f"; aspected by {', '.join(protectors)}" if protectors
                       else "; no benefic aspects the Moon")
                    + " - " + ("a protected Moon carries the load"
                               if prot else "an unsupported Moon feels the "
                               "full weight; guard rest and mood actively")))
    score += 1 if prot else -1

    savv = sav(natal)
    signs3 = [(m_idx + o) % 12 for o in (11, 0, 1)]
    vals = [savv[i] for i in signs3]
    ground = ("strong" if min(vals) >= 30
              else "thin" if min(vals) <= 24 else "average")
    factors.append(("Ashtakavarga ground (12th/1st/2nd from Moon)",
                    f"SAV {vals[0]}/{vals[1]}/{vals[2]} bindus - {ground} "
                    "ground for the transit"
                    + ("; the low-bindu stretch is where the phase bites"
                       if ground == "thin" else "")))
    score += 1 if ground == "strong" else (-1 if ground == "thin" else 0)

    overall = ("mild" if score >= 2 else
               "demanding" if score <= -2 else "moderate")
    return overall, factors
