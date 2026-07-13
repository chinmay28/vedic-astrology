"""yogas.py - rule-based detection of classical combinations.

Contract: detect(chart) -> list[(name, description)].
Every rule is explicit; the set is documented in USER_GUIDE.md.
The detector covers common Chandra-, Surya-, Mahapurusha- and
lagna-structural yogas. It does not attempt exhaustive Parashari
raja/dhana yoga enumeration.
"""
from __future__ import annotations

from .model import (BENEFICS, Chart, EXALTATION, OWN_SIGNS, SIGNS,
                    SIGN_LORD, YOGAKARAKA)

KENDRA_OFFSETS = {0, 3, 6, 9}
MAHAPURUSHA = {"Mars": "Ruchaka", "Mercury": "Bhadra", "Jupiter": "Hamsa",
               "Venus": "Malavya", "Saturn": "Sasa"}


def _sign_distance(a: int, b: int) -> int:
    return (b - a) % 12


def detect(chart: Chart) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    s = chart.sign_idx_of
    h = chart.house_of
    occ_sign = chart.occupants_by_sign()
    moon_s, jup_s, sun_s = s("Moon"), s("Jupiter"), s("Sun")

    # --- Gaja-Kesari: Moon & Jupiter in mutual kendra
    if _sign_distance(moon_s, jup_s) in KENDRA_OFFSETS:
        out.append(("Gaja-Kesari Yoga",
                    f"Moon ({SIGNS[moon_s]}) and Jupiter ({SIGNS[jup_s]}) in mutual "
                    "kendra: wisdom, reputation, a protected mind."))

    # --- Budha-Aditya
    if sun_s == s("Mercury"):
        out.append(("Budha-Aditya Yoga",
                    f"Sun and Mercury conjunct in house {h('Sun')}: intellect fused "
                    "with authority; analytical, articulate expression."))

    # --- Pancha Mahapurusha: own/exalted sign in a kendra from Lagna
    for planet, yname in MAHAPURUSHA.items():
        ps = s(planet)
        in_kendra = (h(planet) - 1) in KENDRA_OFFSETS
        dignified = ps in OWN_SIGNS[planet] or ps == EXALTATION[planet]
        if in_kendra and dignified:
            out.append((f"{yname} Mahapurusha Yoga",
                        f"{planet} in {SIGNS[ps]} (own/exalted) in kendra house "
                        f"{h(planet)}: a first-rank dignity signature."))

    # --- Chandra yogas: Sunapha / Anapha / Durudhara / Kemadruma
    second = occ_sign.get((moon_s + 1) % 12, [])
    twelfth = occ_sign.get((moon_s - 1) % 12, [])
    f2 = [p for p in second if p not in ("Sun", "Moon", "Rahu", "Ketu")]
    f12 = [p for p in twelfth if p not in ("Sun", "Moon", "Rahu", "Ketu")]
    if f2 and f12:
        out.append(("Durudhara Yoga",
                    f"Planets on both sides of the Moon ({', '.join(f2)} | "
                    f"{', '.join(f12)}): resourceful, well-supported mind."))
    elif f2:
        out.append(("Sunapha Yoga",
                    f"{', '.join(f2)} in the 2nd from the Moon: self-made "
                    "resourcefulness."))
    elif f12:
        out.append(("Anapha Yoga",
                    f"{', '.join(f12)} in the 12th from the Moon: composed, "
                    "self-possessed temperament."))
    else:
        cancel = []
        if (h("Moon") - 1) in KENDRA_OFFSETS:
            cancel.append("Moon in a kendra")
        if _sign_distance(moon_s, jup_s) in KENDRA_OFFSETS:
            cancel.append("Jupiter in kendra from Moon")
        note = ("; CANCELED by " + " and ".join(cancel)) if cancel else ""
        out.append(("Kemadruma Yoga" + (" (canceled)" if cancel else ""),
                    "No planets flank the Moon" + note + "."))

    # --- Adhi Yoga: benefics in 6/7/8 from the Moon
    adhi = [p for p in BENEFICS
            if _sign_distance(moon_s, s(p)) in (5, 6, 7)]
    if len(adhi) >= 2:
        out.append(("Chandra-Adhi Yoga",
                    f"Benefics ({', '.join(sorted(adhi))}) in the 6th/7th/8th from "
                    "the Moon: leadership, prosperity, resilience."))

    # --- Vesi / Vasi / Ubhayachari (from the Sun)
    v2 = [p for p in occ_sign.get((sun_s + 1) % 12, [])
          if p not in ("Sun", "Moon", "Rahu", "Ketu")]
    v12 = [p for p in occ_sign.get((sun_s - 1) % 12, [])
           if p not in ("Sun", "Moon", "Rahu", "Ketu")]
    if v2 and v12:
        out.append(("Ubhayachari Yoga", "Planets on both sides of the Sun: "
                    "balanced, capable public bearing."))
    elif v2:
        out.append(("Vesi Yoga", f"{', '.join(v2)} in the 2nd from the Sun: "
                    "forthright, well-spoken presence."))
    elif v12:
        out.append(("Vasi Yoga", f"{', '.join(v12)} in the 12th from the Sun: "
                    "refined, composed bearing."))

    # --- Amala: natural benefic in the 10th from Lagna or Moon
    for base_name, base in (("Lagna", chart.lagna_idx), ("Moon", moon_s)):
        tenth = (base + 9) % 12
        ben = [p for p in occ_sign.get(tenth, []) if p in BENEFICS]
        if ben:
            out.append(("Amala Yoga",
                        f"{', '.join(ben)} in the 10th from {base_name}: "
                        "reputation for clean, ethical conduct."))
            break

    # --- Yogakaraka
    yk = YOGAKARAKA.get(chart.lagna_idx)
    if yk:
        out.append((f"Yogakaraka {yk}",
                    f"For {SIGNS[chart.lagna_idx]} Lagna, {yk} owns the best trine "
                    f"and best kendra; placed in house {h(yk)} "
                    f"({SIGNS[s(yk)]}, {chart.bodies[yk].lon % 30:.1f} deg)."))

    # --- Kuja dosha (flag, not verdict)
    if h("Mars") in (1, 2, 4, 7, 8, 12):
        out.append(("Kuja Dosha (flag)",
                    f"Mars in house {h('Mars')} is a classical Mangala-dosha "
                    "position; assess cancellations before weighing it."))

    # --- Guru-Chandala (conjunction or mutual aspect, Jupiter-Rahu)
    if s("Jupiter") == s("Rahu"):
        out.append(("Guru-Chandala Yoga",
                    "Jupiter conjunct Rahu: wisdom entangled with ambition."))

    # --- Chandra-Mangala
    if moon_s == s("Mars"):
        out.append(("Chandra-Mangala Yoga",
                    "Moon conjunct Mars: energetic, enterprising mind; "
                    "earning drive."))

    # --- Combustion flags
    for p in chart.combust():
        out.append((f"{p} combust",
                    f"{p} within combustion orb of the Sun: its significations "
                    "operate under the Sun's glare (weakened externally, "
                    "intensified internally)."))
    return out
