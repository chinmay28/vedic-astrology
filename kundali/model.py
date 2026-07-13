"""model.py - static Jyotish reference data and the Chart domain object.

Contract: pure data + pure functions. No ephemeris calls here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .ephemeris import BodyPosition

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "P.Phalguni", "U.Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "P.Ashadha", "U.Ashadha", "Shravana", "Dhanishta",
    "Shatabhisha", "P.Bhadrapada", "U.Bhadrapada", "Revati",
]

SIGN_LORD = {0: "Mars", 1: "Venus", 2: "Mercury", 3: "Moon", 4: "Sun",
             5: "Mercury", 6: "Venus", 7: "Mars", 8: "Jupiter",
             9: "Saturn", 10: "Saturn", 11: "Jupiter"}

OWN_SIGNS = {"Sun": {4}, "Moon": {3}, "Mars": {0, 7}, "Mercury": {2, 5},
             "Jupiter": {8, 11}, "Venus": {1, 6}, "Saturn": {9, 10}}

EXALTATION = {"Sun": 0, "Moon": 1, "Mars": 9, "Mercury": 5,
              "Jupiter": 3, "Venus": 11, "Saturn": 6}

# Moolatrikona: (sign, from_deg, to_deg). Checked before whole-sign
# exaltation so Moon in Taurus 3-30 and similar bands resolve classically.
MOOLATRIKONA = {"Sun": (4, 0, 20), "Moon": (1, 3, 30), "Mars": (0, 0, 12),
                "Mercury": (5, 16, 20), "Jupiter": (8, 0, 10),
                "Venus": (6, 0, 15), "Saturn": (10, 0, 20)}

# Naisargika maitri (natural friendship)
FRIENDS = {
    "Sun": {"Moon", "Mars", "Jupiter"}, "Moon": {"Sun", "Mercury"},
    "Mars": {"Sun", "Moon", "Jupiter"}, "Mercury": {"Sun", "Venus"},
    "Jupiter": {"Sun", "Moon", "Mars"}, "Venus": {"Mercury", "Saturn"},
    "Saturn": {"Mercury", "Venus"},
}
ENEMIES = {
    "Sun": {"Venus", "Saturn"}, "Moon": set(), "Mars": {"Mercury"},
    "Mercury": {"Moon"}, "Jupiter": {"Mercury", "Venus"},
    "Venus": {"Sun", "Moon"}, "Saturn": {"Sun", "Moon", "Mars"},
}

BENEFICS = {"Jupiter", "Venus", "Mercury"}   # Mercury: natural benefic (simplified)
SEVEN_GRAHAS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
NINE_GRAHAS = SEVEN_GRAHAS + ["Rahu", "Ketu"]

# Yogakaraka by Lagna (single planet owning best trine + best kendra)
YOGAKARAKA = {1: "Saturn", 6: "Saturn", 3: "Mars", 4: "Mars",
              9: "Venus", 10: "Venus"}

# Combustion orbs (degrees from Sun; direct motion values)
COMBUST_ORB = {"Moon": 12, "Mars": 17, "Mercury": 14,
               "Jupiter": 11, "Venus": 10, "Saturn": 15}

DIG_BALA_HOUSE = {"Sun": 10, "Mars": 10, "Jupiter": 1, "Mercury": 1,
                  "Moon": 4, "Venus": 4, "Saturn": 7}

HOUSE_SIGNIFICATIONS = {
    1: ("Tanu", "body, vitality, personality, life direction"),
    2: ("Dhana", "wealth, speech, food, family, values"),
    3: ("Sahaja", "courage, siblings, effort, skills, communication"),
    4: ("Sukha", "mother, home, inner peace, property, education"),
    5: ("Putra", "children, intellect, creativity, romance, merit"),
    6: ("Ari", "enemies, debts, disease, service, competition"),
    7: ("Kalatra", "spouse, partnership, the public, trade"),
    8: ("Randhra", "longevity, transformation, the hidden, research"),
    9: ("Bhagya", "fortune, dharma, father, gurus, philosophy"),
    10: ("Karma", "career, status, authority, visible action"),
    11: ("Labha", "gains, income, friends, aspirations"),
    12: ("Vyaya", "loss, expenditure, foreign lands, moksha"),
}

SANDHI_ORB = 1.0  # degrees from a sign boundary worth flagging


def sign_of(lon: float) -> tuple[int, float]:
    """(sign_index 0-11, degrees within sign)."""
    s = int(lon // 30) % 12
    return s, lon - s * 30


def nakshatra_of(lon: float) -> tuple[str, int]:
    """(nakshatra name, pada 1-4)."""
    span = 40 / 3
    idx = int(lon // span) % 27
    pada = int((lon % span) // (span / 4)) + 1
    return NAKSHATRAS[idx], pada


def dignity(body: str, sign_idx: int, deg: float | None = None) -> str:
    """Exalted / Moolatrikona / Own sign / Friend / Enemy / Neutral / Debilitated.

    `deg` (degrees within sign) enables the moolatrikona band check;
    without it the band is skipped (whole-sign logic only).
    """
    if body in ("Rahu", "Ketu"):
        return "-"
    if deg is not None and body in MOOLATRIKONA:
        ms, lo, hi = MOOLATRIKONA[body]
        if sign_idx == ms and lo <= deg < hi:
            return "Moolatrikona"
    if EXALTATION[body] == sign_idx:
        return "Exalted"
    if (EXALTATION[body] + 6) % 12 == sign_idx:
        return "Debilitated"
    if sign_idx in OWN_SIGNS[body]:
        return "Own sign"
    lord = SIGN_LORD[sign_idx]
    if lord == body:
        return "Own sign"
    if lord in FRIENDS[body]:
        return "Friend's sign"
    if lord in ENEMIES[body]:
        return "Enemy's sign"
    return "Neutral"


@dataclass
class Chart:
    """A cast chart: natal or varsha. Whole-sign houses from the Lagna."""
    name: str
    dt_local: datetime
    tz: str
    place: str
    lat: float
    lon: float
    jd: float
    asc: float
    bodies: dict[str, BodyPosition]
    ayanamsa_name: str = "raman"
    ayanamsa_deg: float = 0.0
    lagna_idx: int = field(init=False)

    def __post_init__(self) -> None:
        self.lagna_idx = sign_of(self.asc)[0]

    def house_of(self, body: str) -> int:
        s, _ = sign_of(self.bodies[body].lon)
        return ((s - self.lagna_idx) % 12) + 1

    def sign_idx_of(self, body: str) -> int:
        return sign_of(self.bodies[body].lon)[0]

    def occupants(self) -> dict[int, list[str]]:
        occ: dict[int, list[str]] = {h: [] for h in range(1, 13)}
        for b in NINE_GRAHAS:
            occ[self.house_of(b)].append(b)
        return occ

    def occupants_by_sign(self) -> dict[int, list[str]]:
        occ: dict[int, list[str]] = {}
        for b in NINE_GRAHAS:
            occ.setdefault(self.sign_idx_of(b), []).append(b)
        return occ

    def combust(self) -> list[str]:
        """Planets within combustion orb of the Sun (same or adjacent sign)."""
        sun = self.bodies["Sun"].lon
        out = []
        for b, orb in COMBUST_ORB.items():
            d = abs(((self.bodies[b].lon - sun + 180) % 360) - 180)
            if d <= orb:
                out.append(b)
        return out

    def sandhi_flags(self) -> list[str]:
        out = []
        for b in NINE_GRAHAS:
            _, deg = sign_of(self.bodies[b].lon)
            if deg < SANDHI_ORB or deg > 30 - SANDHI_ORB:
                out.append(b)
        return out
