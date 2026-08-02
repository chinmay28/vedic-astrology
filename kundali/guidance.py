"""guidance.py - the teaching layer.

One short "how to read this" paragraph per report section, rendered
inline in both PDF and HTML output. Written for a reader with no prior
Jyotish background; deliberately concrete about what to look at first
and what NOT to over-read.
"""

GUIDANCE: dict[str, str] = {
    "verification": (
        "Check this box before reading anything else. Every result in a "
        "chart hangs on the birth moment in Universal Time; the single "
        "most common error in commercial reports is a wrong timezone or "
        "daylight-saving setting, which silently shifts the Lagna and "
        "every house. If another report for the same birth shows a "
        "different Lagna, compare its UTC offset with the one shown here."),
    "panchanga": (
        "The panchanga is the Vedic calendar's five limbs at the birth "
        "moment: tithi (lunar day - the Sun-Moon angle), vara (weekday), "
        "nakshatra (the Moon's lunar mansion), yoga (a Sun+Moon "
        "combination), and karana (half-tithi). Traditional practice uses "
        "them for muhurta (electional timing) and for the birth constants "
        "below. The nakshatra matters most: it names the janma nakshatra "
        "and seeds the dasha clock."),
    "avakahada": (
        "Moon-derived birth constants, traditionally used for naming the "
        "child (the syllable) and in kuta match-making (gana, yoni, nadi, "
        "varna, vashya are five of the eight compatibility factors). Read "
        "them as classical categories, not personality verdicts; nadi and "
        "gana carry the most weight in traditional matching."),
    "positions": (
        "Start with three rows: the Lagna (the frame of the whole chart), "
        "the Moon (the mind; its nakshatra runs the dasha clock), and the "
        "Lagna lord. Then scan the Dignity column - Exalted/Moolatrikona/"
        "Own-sign planets deliver cleanly; Debilitated or Enemy-sign "
        "planets deliver with friction. A planet flagged sandhi (within "
        "1 deg of a sign edge) is provisional: verify birth time before "
        "trusting anything fine-grained built on it."),
    "diagrams": (
        "Both diagrams show the same chart. North Indian: houses are "
        "fixed (top-centre diamond is always house 1), the number inside "
        "is the sign (1=Aries...12=Pisces). South Indian: signs are fixed "
        "(clockwise, Pisces top-left), the slashed cell is the Lagna; "
        "count houses clockwise from it."),
    "yogas": (
        "Named patterns the classics single out. Weigh, don't count: one "
        "strong yoga formed by dignified planets outweighs several weak "
        "ones, and a yoga's promise is delivered mainly during the dasha "
        "periods of its participant planets. Items marked as flags "
        "(Kuja dosha, combustion) are cautions to assess, not verdicts."),
    "aspects": (
        "Vedic aspects work by whole house, not degree orbs. Read the "
        "table two ways: an empty house with several inbound aspects is "
        "still highly active, and a powerful cluster with no benefic "
        "aspect runs 'raw' while a harsh conjunction watched by Jupiter "
        "runs 'supervised'. Mutual aspects are standing dialogues between "
        "the two planets' life areas."),
    "dasha": (
        "The Vimshottari system activates one planet's promise at a time. "
        "The Mahadasha lord sets the era; the Antardasha lord the "
        "chapter; the Pratyantardasha the month-scale texture. Always "
        "read a period lord through its NATAL condition - house, sign, "
        "dignity, aspects. Dates inherit every input sensitivity: if the "
        "Moon is near a nakshatra edge, treat all dates as +/- months."),
    "week": (
        "The week's weather, read as classical gochara: every transit is "
        "counted from your natal MOON (not the Lagna), graded by the "
        "standard favourable-house table, and weighted by the "
        "Ashtakavarga bindus of the sign being transited - 30+ is strong "
        "ground, 24 or fewer is thin. The day table follows the transit "
        "Moon, which changes sign every 2-3 days: days it spends in the "
        "1st, 3rd, 6th, 7th, 10th or 11th from your natal Moon carry "
        "outward moves best, and the 8th (chandrashtama) is the day the "
        "tradition says to keep light. All of it sits inside the running "
        "dasha, which is the stronger signal: a favourable week inside a "
        "strained period is a good week for that period's work, not a "
        "different life. Vedha (the obstruction rule that cancels some "
        "transit results) is deliberately not applied here. The week "
        "shown is the Monday-to-Sunday one containing the as-of date - "
        "move that date to read another week."),
    "dashatimeline": (
        "The same reading applied to every era of the timeline above, one "
        "entry per Mahadasha, because a period delivers what its lord can "
        "deliver: the lord's natal house sets the themes, its dignity and "
        "Vimshopaka set how cleanly they arrive, and the aspects on it say "
        "whether the era runs supervised or raw. Read the past eras "
        "backwards - they are a check on whether the chart describes the "
        "life so far - and the coming ones as ground to prepare, not to "
        "act on yet. Node eras (Rahu, Ketu) have no dignity of their own "
        "and are read through their house and their dispositor. Dates "
        "carry the same birth-time sensitivity as the timeline itself."),
    "d9": (
        "The Navamsa is the chart of marriage and of maturation: dignity "
        "gained here strengthens a weak D-1 placement with age, dignity "
        "lost warns of early promise needing protection. Vargottama "
        "planets (same sign in both) are especially steady. Caution: a "
        "navamsa is only 3 deg 20 min wide - sandhi planets may occupy a "
        "different D-9 sign under a small birth-time correction."),
    "ashtakavarga": (
        "A transit-weighting map. The SAV row scores each sign's ground: "
        "30+ bindus, strong ground (transits deliver); 24 or fewer, thin "
        "ground (hard transits bite harder, benefics give less). Before "
        "judging any Saturn or Jupiter transit - including Sade Sati "
        "phases - check the SAV of the sign being transited."),
    "houses": (
        "An empty house is not a silent house: read it through its lord's "
        "placement (row: Lord -> H). '2nd lord in the 9th' ties wealth to "
        "fortune and father even with nobody home in the 2nd. Houses "
        "1, 4, 7, 10 (kendras) and 1, 5, 9 (trikonas) carry the most "
        "weight; 6, 8, 12 are the houses of difficulty and depth."),
    "sadesati": (
        "Saturn's ~7.5-year passage over the 12th, 1st and 2nd signs "
        "from the natal Moon, plus the shorter Kantaka (4th) and Ashtama "
        "(8th) transits. Read it as scheduled load, not doom - every "
        "human with a Moon has these periods, three or four times in a "
        "life. This section grades how it tends to run for THIS chart "
        "(severity factors, each with its reason), locates the current "
        "and next phase, and gives each phase's classical themes. The "
        "Murti column grades each entry by the Moon's position at "
        "Saturn's ingress: Gold best, Iron heaviest - a fine-tuning "
        "layer, not a verdict."),
    "varshaphal": (
        "The annual chart: the year's weather over the natal climate. "
        "Read in order: which natal house rises (the year's theme), the "
        "Muntha's house and grade (the headline), the year-lord's "
        "condition (the tone), then the Mudda dasha (the month-by-month "
        "calendar). An adverse Muntha with a well-placed Muntha lord is "
        "substantially rescued."),
    "transits": (
        "Slow-mover ingresses during the report window, with the natal "
        "house each one activates. Classical gochara counts houses from "
        "the natal MOON as much as from the Lagna. A transit gains "
        "weight when it agrees with the running dasha - one indicator "
        "alone is weak; convergence is how the tradition confirms."),
    "dashanow": (
        "The most practical section of the report. It locates today "
        "inside the dasha cycle (era / chapter / month-scale), then reads "
        "each running lord through its NATAL condition - because a period "
        "delivers what its lord can deliver. The guidance describes "
        "themes and posture (build vs consolidate), not events. Re-run "
        "the report with --asof for any other date."),
    "shodashavarga": (
        "The sixteen divisional charts, each refining one life area "
        "(D-10 career, D-7 children, D-12 parents...). Reading rule: a "
        "planet's dignity in a varga refines its promise for that area. "
        "The Vimshopaka score condenses all sixteen into one strength "
        "number out of 20: 15+ excellent, 10-15 serviceable, below 10 "
        "the planet needs support. Degree sensitivity is extreme in "
        "high-number vargas (a D-60 division is half a degree wide) - "
        "treat D-40/45/60 as birth-time-verified territory only."),
    "maitri": (
        "Five-fold friendship: each planet's fixed natural relation to "
        "the others, adjusted by this chart's temporal relations (a "
        "planet befriends occupants of the 2nd-4th and 10th-12th from "
        "itself), giving the compound grades used throughout this "
        "report (Vimshopaka, avasthas). Read row -> column: how the row "
        "planet regards the column planet. The relation need not be "
        "mutual."),
    "avasthas": (
        "Three ways of grading how fully a planet can act: Baladi (its "
        "'age' by degree - infant and dead states deliver weakly, youth "
        "fully), Jagradadi (awake / dreaming / asleep, from dignity), "
        "Deeptadi (its 'mood', from compound friendship, combustion and "
        "debilitation). Use them as volume knobs on the planet's "
        "promises, and expect minor differences between software - the "
        "schemes have variant readings."),
    "bhav": (
        "A second house system (Sripati cusps) laid over the whole-sign "
        "chart. Most planets occupy the same house in both; the SHIFT "
        "list is what matters - a shifted planet genuinely straddles two "
        "houses, and traditions differ on which to prefer (many read "
        "whole-sign for yogas/aspects, bhav chalit for house strength). "
        "Treat shifted planets as expressing both houses."),
    "closing": (
        "How the layers stack: the natal chart is the promise, the dasha "
        "decides WHEN a promise activates, transits and the varsha chart "
        "describe the year it lands in. A claim supported by all of them "
        "at once is a confirmed signal; anything resting on one factor - "
        "or on a sandhi planet - is a hypothesis. Computed positions here "
        "are exact astronomy; all interpretation is the classical "
        "tradition's voice, offered for study."),
}
