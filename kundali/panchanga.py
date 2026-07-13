"""panchanga.py - the five limbs of the calendar at birth, plus the
avakahada (Moon-derived birth constants used in naming and kuta matching).

All pure functions over sidereal longitudes; ayanamsa cancels in tithi,
yoga and karana (they use Sun-Moon combinations in the same zodiac).
Validated against an independent commercial report for the karana
boundary (Bava/Balava) and tithi/yoga.
"""
from __future__ import annotations

from .model import Chart, nakshatra_of, sign_of, NAKSHATRAS

TITHI_NAMES = ["Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
               "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
               "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", ""]
YOGA_NAMES = ["Vishkumbha", "Priti", "Ayushman", "Saubhagya", "Shobhana",
              "Atiganda", "Sukarman", "Dhriti", "Shula", "Ganda", "Vriddhi",
              "Dhruva", "Vyaghata", "Harshana", "Vajra", "Siddhi",
              "Vyatipata", "Variyana", "Parigha", "Shiva", "Siddha",
              "Sadhya", "Shubha", "Shukla", "Brahma", "Indra", "Vaidhriti"]
MOVABLE_KARANAS = ["Bava", "Balava", "Kaulava", "Taitila", "Gara",
                   "Vanija", "Vishti"]

# --- Avakahada tables (indexed by nakshatra 0-26 unless noted) ---
GANA = {"Deva": {0, 4, 6, 7, 12, 14, 16, 21, 26},
        "Manushya": {1, 3, 5, 10, 11, 19, 20, 24, 25},
        "Rakshasa": {2, 8, 9, 13, 15, 17, 18, 22, 23}}
YONI = ["Horse", "Elephant", "Sheep", "Serpent", "Serpent", "Dog", "Cat",
        "Sheep", "Cat", "Rat", "Rat", "Cow", "Buffalo", "Tiger", "Buffalo",
        "Tiger", "Deer", "Deer", "Dog", "Monkey", "Mongoose", "Monkey",
        "Lion", "Horse", "Lion", "Cow", "Elephant"]
NADI = {"Adi": {0, 5, 6, 11, 12, 17, 18, 23, 24},
        "Madhya": {1, 4, 7, 10, 13, 16, 19, 22, 25},
        "Antya": {2, 3, 8, 9, 14, 15, 20, 21, 26}}
# Varna by Moon rashi element: water Brahmin, fire Kshatriya,
# earth Vaishya, air Shudra.
VARNA = ["Kshatriya", "Vaishya", "Shudra", "Brahmin"] * 3
# Vashya by Moon rashi (primary attribution; some traditions split
# Sagittarius/Capricorn by half-sign).
VASHYA = ["Chatushpada", "Chatushpada", "Manava", "Jalachara", "Vanachara",
          "Manava", "Manava", "Keeta", "Chatushpada", "Jalachara",
          "Manava", "Jalachara"]
NAME_SYLLABLES = [
    ["Chu", "Che", "Cho", "La"], ["Li", "Lu", "Le", "Lo"],
    ["A", "I", "U", "E"], ["O", "Va", "Vi", "Vu"],
    ["Ve", "Vo", "Ka", "Ki"], ["Ku", "Gha", "Nga", "Chha"],
    ["Ke", "Ko", "Ha", "Hi"], ["Hu", "He", "Ho", "Da"],
    ["Di", "Du", "De", "Do"], ["Ma", "Mi", "Mu", "Me"],
    ["Mo", "Ta", "Ti", "Tu"], ["Te", "To", "Pa", "Pi"],
    ["Pu", "Sha", "Na", "Tha"], ["Pe", "Po", "Ra", "Ri"],
    ["Ru", "Re", "Ro", "Ta"], ["Ti", "Tu", "Te", "To"],
    ["Na", "Ni", "Nu", "Ne"], ["No", "Ya", "Yi", "Yu"],
    ["Ye", "Yo", "Bha", "Bhi"], ["Bhu", "Dha", "Pha", "Dha"],
    ["Bhe", "Bho", "Ja", "Ji"], ["Khi", "Khu", "Khe", "Kho"],
    ["Ga", "Gi", "Gu", "Ge"], ["Go", "Sa", "Si", "Su"],
    ["Se", "So", "Da", "Di"], ["Du", "Tha", "Jha", "Nya"],
    ["De", "Do", "Cha", "Chi"],
]


def tithi(chart: Chart) -> tuple[str, int, str]:
    """(paksha, number 1-15, name)."""
    diff = (chart.bodies["Moon"].lon - chart.bodies["Sun"].lon) % 360
    t = int(diff // 12) + 1
    paksha = "Shukla" if t <= 15 else "Krishna"
    n = t if t <= 15 else t - 15
    name = "Purnima" if t == 15 else "Amavasya" if t == 30 else TITHI_NAMES[n - 1]
    return paksha, n, name


def yoga(chart: Chart) -> str:
    total = (chart.bodies["Sun"].lon + chart.bodies["Moon"].lon) % 360
    return YOGA_NAMES[int(total // (40 / 3))]


def karana(chart: Chart) -> str:
    diff = (chart.bodies["Moon"].lon - chart.bodies["Sun"].lon) % 360
    k = int(diff // 6)
    if k == 0:
        return "Kimstughna"
    if k >= 57:
        return ["Shakuni", "Chatushpada", "Naga"][k - 57]
    return MOVABLE_KARANAS[(k - 1) % 7]


def vara(chart: Chart) -> str:
    return chart.dt_local.strftime("%A")


def avakahada(chart: Chart) -> dict[str, str]:
    """Moon-derived birth constants (the Avakahada Chakra of
    traditional reports). Used in naming and in kuta match-making."""
    ml = chart.bodies["Moon"].lon
    nk_idx = int(ml // (40 / 3)) % 27
    nk, pada = nakshatra_of(ml)
    rashi = sign_of(ml)[0]
    gana = next(g for g, s in GANA.items() if nk_idx in s)
    nadi = next(n for n, s in NADI.items() if nk_idx in s)
    return {
        "Janma Nakshatra": f"{nk} pada {pada}",
        "Name syllable": NAME_SYLLABLES[nk_idx][pada - 1]
                         + f"  (nakshatra set: {', '.join(NAME_SYLLABLES[nk_idx])})",
        "Gana": gana, "Yoni": YONI[nk_idx], "Nadi": nadi,
        "Varna": VARNA[rashi], "Vashya": VASHYA[rashi],
    }
