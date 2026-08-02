"""Golden-value tests.

Every expected value below was hand-validated during the study that
produced this tool (three charts, Raman ayanamsa, whole-sign houses).
If these fail, the ephemeris contract has drifted.
"""
import pytest

from kundali.aspects import mutual_pairs
from kundali.cli import cast_natal
from kundali.dasha import mahadashas, mudda
from kundali.ephemeris import jd_to_date_str, solar_return
from kundali.model import SIGNS, nakshatra_of, sign_of
from kundali.varshaphal import cast_varsha
from kundali.yogas import detect


@pytest.fixture(scope="module")
def c1():
    return cast_natal("C1", "1990-02-28", "11:47", "Asia/Kolkata",
                      14.6197, 74.8354, "Sirsi", "raman")


@pytest.fixture(scope="module")
def c2():
    return cast_natal("C2", "2026-05-12", "15:26", "America/Los_Angeles",
                      37.3382, -121.8863, "San Jose", "raman")


@pytest.fixture(scope="module")
def c3():
    return cast_natal("C3", "1993-11-26", "22:03", "Asia/Kolkata",
                      14.6197, 74.8354, "Sirsi", "raman")


def test_lagnas(c1, c2, c3):
    assert SIGNS[c1.lagna_idx] == "Taurus"
    assert SIGNS[c2.lagna_idx] == "Virgo"
    assert SIGNS[c3.lagna_idx] == "Cancer"


def test_positions_degrees(c1, c2, c3):
    # tolerance 0.05 deg against hand-validated values
    assert sign_of(c1.bodies["Saturn"].lon) == (8, pytest.approx(29.77, abs=0.05))
    assert sign_of(c2.bodies["Venus"].lon) == (1, pytest.approx(29.90, abs=0.05))
    assert sign_of(c3.bodies["Moon"].lon) == (0, pytest.approx(13.31, abs=0.05))


def test_timezone_handles_dst(c2):
    # May in California is PDT (UTC-7); a naive UTC-8 conversion would
    # shift the Lagna. Virgo rising is the DST-correct result.
    assert SIGNS[c2.lagna_idx] == "Virgo"


def test_nakshatras(c1, c3):
    assert nakshatra_of(c1.bodies["Moon"].lon) == ("Revati", 3)
    assert nakshatra_of(c3.bodies["Moon"].lon) == ("Ashwini", 4)


def test_houses(c1, c2, c3):
    assert c1.house_of("Sun") == 10 and c1.house_of("Saturn") == 8
    assert c2.house_of("Mars") == 8 and c2.house_of("Saturn") == 7
    assert c3.house_of("Moon") == 10 and c3.house_of("Venus") == 4


def test_mahadasha_dates(c1, c3):
    md1 = {m.lord: m for m in mahadashas(c1.bodies["Moon"].lon, c1.jd)}
    assert jd_to_date_str(md1["Sun"].start, "Asia/Kolkata") == "12 May 2022"
    assert jd_to_date_str(md1["Moon"].start, "Asia/Kolkata") == "11 May 2028"
    md3 = {m.lord: m for m in mahadashas(c3.bodies["Moon"].lon, c3.jd)}
    assert jd_to_date_str(md3["Moon"].start, "Asia/Kolkata") == "02 Dec 2019"


def test_solar_return_and_muntha(c1):
    v = cast_varsha(c1, 2026)
    assert v.age == 36
    assert jd_to_date_str(v.chart.jd) == "28 Feb 2026"
    assert SIGNS[v.chart.lagna_idx] == "Leo"
    assert v.muntha_house == 10 and v.grade == "excellent"


def test_varsha_age_zero_skipped(c2):
    assert cast_varsha(c2, 2026) is None       # birth year
    assert cast_varsha(c2, 2027).age == 1


def test_mudda_covers_year(c1):
    v = cast_varsha(c1, 2026)
    total = sum(m.end - m.start for m in v.mudda)
    assert total == pytest.approx(365.25, abs=1e-6)


def test_mutual_aspects_chart1(c1):
    pairs = {frozenset(p) for p in mutual_pairs(c1)}
    assert frozenset({"Jupiter", "Mars"}) in pairs
    assert frozenset({"Jupiter", "Saturn"}) in pairs
    assert frozenset({"Rahu", "Ketu"}) in pairs


def test_yogas(c1, c2, c3):
    names1 = {n for n, _ in detect(c1)}
    assert any("Gaja-Kesari" in n for n in names1)
    assert any("Budha-Aditya" in n for n in names1)
    assert any("Yogakaraka Saturn" in n for n in names1)
    names2 = {n for n, _ in detect(c2)}
    assert "Mercury combust" in names2          # deep combustion, 2.0 deg
    names3 = {n for n, _ in detect(c3)}
    assert any("Malavya" in n for n in names3)
    assert any("Adhi" in n for n in names3)


# ---------- v1.1: Navamsa ----------

def test_navamsa_formula_matches_classical_rule():
    """Closed form must equal the movable/fixed/dual start rule everywhere."""
    from kundali.varga import navamsa_sign, navamsa_sign_by_rule
    lon = 0.0
    while lon < 360:
        assert navamsa_sign(lon) == navamsa_sign_by_rule(lon), lon
        lon += 0.7


def test_navamsa_golden_values(c1, c3):
    # Hand-derived: C1 Moon 25.92 Pisces (dual, starts 5th=Cancer),
    # navamsa #7 -> Aquarius. C3 Venus 29.75 Libra (movable), #8 -> Gemini.
    from kundali.varga import navamsa_chart
    d9_1 = navamsa_chart(c1)
    assert SIGNS[d9_1.sign_idx_of("Moon")] == "Aquarius"
    assert SIGNS[d9_1.lagna_idx] == "Aries"       # Lagna 12.35 Taurus -> #3
    d9_3 = navamsa_chart(c3)
    assert SIGNS[d9_3.sign_idx_of("Venus")] == "Gemini"


# ---------- v1.1: Ashtakavarga ----------

def test_bav_totals_are_classical_constants(c1, c2, c3):
    from kundali.ashtakavarga import BAV_TOTALS, SAV_TOTAL, bav, sav
    for chart in (c1, c2, c3):
        for planet, expected in BAV_TOTALS.items():
            assert sum(bav(chart, planet)) == expected, planet
        assert sum(sav(chart)) == SAV_TOTAL


def test_bav_values_in_range(c1):
    from kundali.ashtakavarga import bav
    for p in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"):
        assert all(0 <= v <= 8 for v in bav(c1, p))


# ---------- v1.2: Panchanga / Avakahada (validated against an
# independent commercial report for the same birth) ----------

def test_panchanga_chart2(c2):
    from kundali.panchanga import avakahada, karana, tithi, yoga
    pk, n, name = tithi(c2)
    assert (pk, n, name) == ("Krishna", 11, "Ekadashi")
    assert yoga(c2) == "Vishkumbha"
    # The commercial report printed 'Bava' - correct only under its
    # 2-hour timezone error; at the true PDT instant the karana is Balava.
    assert karana(c2) == "Balava"
    av = avakahada(c2)
    assert av["Gana"] == "Manushya" and av["Yoni"] == "Cow"
    assert av["Nadi"] == "Madhya" and av["Varna"] == "Brahmin"
    assert av["Vashya"] == "Jalachara"
    assert av["Name syllable"].startswith("Du")


def test_timezone_error_reproduces_commercial_report():
    """Casting Chart 2 with the wrong UTC-5 offset must reproduce the
    commercial report's (erroneous) Leo Lagna - proving the discrepancy
    is a timezone error, not an ayanamsa or algorithm difference."""
    from kundali import ephemeris as eph
    from kundali.model import Chart
    from datetime import datetime
    eph.set_ayanamsa("raman")
    dt = datetime(2026, 5, 12, 15, 26)
    jd_wrong = eph.jd_from_local(dt, "America/Bogota")   # fixed UTC-5
    asc = eph.ascendant(jd_wrong, 37.3382, -121.8863)
    assert SIGNS[int(asc // 30)] == "Leo"
    assert abs(asc % 30 - 8.87) < 0.1


# ---------- v1.2: Moolatrikona ----------

def test_moolatrikona(c2):
    from kundali.model import dignity, sign_of
    s, d = sign_of(c2.bodies["Mars"].lon)      # Aries 2.7 - in 0-12 band
    assert dignity("Mars", s, d) == "Moolatrikona"
    s, d = sign_of(c2.bodies["Sun"].lon)       # Aries - still Exalted
    assert dignity("Sun", s, d) == "Exalted"
    s, d = sign_of(c2.bodies["Venus"].lon)     # Taurus 29.9 - Own sign
    assert dignity("Venus", s, d) == "Own sign"
    assert dignity("Moon", 1, 2.0) == "Exalted"        # below the band
    assert dignity("Moon", 1, 20.0) == "Moolatrikona"  # inside 3-30


# ---------- v1.2: Sade Sati lifetime ----------

def test_sadesati_lifetime(c2):
    from kundali.sadesati import lifetime_table
    rows = lifetime_table(c2, years=30)
    assert any("CORE" in r[3] and r[2] == "Pisces" for r in rows)
    assert any("Kantaka" in r[3] and r[2] == "Gemini" for r in rows)


# ---------- v1.2: Pratyantardasha ----------

def test_pratyantar_covers_ad(c1):
    from kundali.dasha import antardashas, mahadashas, pratyantardashas
    md = [m for m in mahadashas(c1.bodies["Moon"].lon, c1.jd)
          if m.lord == "Sun"][0]
    ad = antardashas(md)[0]
    pads = pratyantardashas(ad)
    assert len(pads) == 9
    assert abs(pads[-1][4] - ad.end) < 1e-6
    assert abs(pads[0][3] - ad.start) < 1e-6


# ---------- v1.3: fixture chart (the commercial report's UTC-5 instant) ----------

@pytest.fixture(scope="module")
def fx():
    return cast_natal("fixture", "2026-05-12", "15:26", "America/Bogota",
                      37.3382, -121.8863, "San Jose (report tz error)", "raman")


def test_shodhana_matches_commercial_report(fx):
    from kundali.ashtakavarga import (bav, ekadhipatya_shodhana,
                                      shodhya_pinda, trikona_shodhana)
    assert bav(fx, "Sun") == [5, 4, 3, 3, 2, 2, 6, 6, 5, 6, 4, 2]
    tri = trikona_shodhana(bav(fx, "Sun"))
    assert tri == [3, 2, 0, 1, 0, 0, 3, 4, 3, 4, 1, 0]
    assert ekadhipatya_shodhana(tri, fx) == [3, 2, 0, 1, 0, 0, 1, 1, 3, 3, 0, 0]
    expected = {"Sun": 170, "Moon": 85, "Mars": 142, "Mercury": 133,
                "Jupiter": 95, "Venus": 131, "Saturn": 168}
    for p, e in expected.items():
        assert shodhya_pinda(fx, p)[2] == e, p


def test_maitri_matches_commercial_report(fx):
    from kundali.maitri import compound
    assert compound(fx, "Sun", "Mercury") == "Shatru"
    assert compound(fx, "Sun", "Jupiter") == "Adhimitra"
    assert compound(fx, "Sun", "Venus") == "Sama"
    assert compound(fx, "Sun", "Moon") == "Adhimitra"
    assert compound(fx, "Moon", "Jupiter") == "Mitra"


def test_avasthas_match_commercial_report(fx):
    # 6/7 Deeptadi cells match the vendor; their Saturn cell contradicts
    # their own Panchadha table (see module docstring), ours follows it.
    from kundali.avastha import baladi, deeptadi, jagradadi
    assert (baladi(fx, "Sun"), jagradadi(fx, "Sun"), deeptadi(fx, "Sun")) == \
        ("Mrita", "Jagrata", "Deepta")
    assert deeptadi(fx, "Mercury") == "Dukhita"     # combust + Shatru
    assert deeptadi(fx, "Moon") == "Shanta"
    assert (baladi(fx, "Venus"), baladi(fx, "Saturn")) == ("Bala", "Yuva")


# ---------- v1.3: vargas & vimshopaka ----------

def test_varga_engine(c2, c3):
    from kundali.varga import SHODASHAVARGA, varga_sign
    # D-1 identity and D-9 agreement with the dedicated navamsa
    from kundali.varga import navamsa_sign
    for lon in (0.0, 95.5, 214.2, 359.9):
        assert varga_sign(lon, 1) == int(lon // 30)
        assert varga_sign(lon, 9) == navamsa_sign(lon)
    # Hand-derived: Sun 29.42 Aries D-30 -> Venus segment -> Libra
    assert SIGNS[varga_sign(c2.bodies["Sun"].lon, 30)] == "Libra"
    # Chart 3 Venus 29.75 Libra (odd sign) D-30 -> Venus 25-30 -> Libra
    assert SIGNS[varga_sign(c3.bodies["Venus"].lon, 30)] == "Libra"
    # every varga yields a valid sign for every graha
    for n in SHODASHAVARGA:
        for b in c3.bodies.values():
            assert 0 <= varga_sign(b.lon, n) <= 11


def test_vimshopaka_range(c1, c2, c3):
    from kundali.varga import vimshopaka
    for chart in (c1, c2, c3):
        for p, v in vimshopaka(chart).items():
            assert 5.0 <= v <= 20.0, (p, v)


# ---------- v1.3: bhav chalit ----------

def test_bhav_chalit(c2):
    from kundali.bhav import bhav_of, porphyry_cusps
    cusps = porphyry_cusps(c2)
    assert abs(cusps[0] - c2.asc) < 1e-6          # cusp 1 = ascendant
    # the ascendant degree itself lies in bhava 1
    assert bhav_of(c2, c2.asc + 0.1) == 1


# ---------- v1.3: dasha now & next ----------

def test_dasha_now(c1):
    from datetime import datetime
    from kundali import ephemeris as eph
    from kundali.dasha_now import locate
    jd = eph.jd_from_local(datetime(2026, 7, 12), "Asia/Kolkata")
    md, ad, pad, next_ad, next_md = locate(c1, jd)
    assert md.lord == "Sun" and ad.sub == "Mercury"
    assert next_ad.sub == "Ketu"
    assert next_md.lord == "Moon"
    assert pad[3] <= jd < pad[4]


# ---------- v1.4: Sade Sati impacts ----------

def test_severity_profile(c1, c2, c3):
    from kundali.sadesati import severity_profile
    for chart in (c1, c2, c3):
        grade, factors = severity_profile(chart)
        assert grade in ("mild", "moderate", "demanding")
        assert len(factors) == 4
    # Chart 1: Saturn is Yogakaraka for Taurus Lagna - must be cited
    _, f1 = severity_profile(c1)
    assert any("YOGAKARAKA" in v for _, v in f1)


def test_current_status_and_murti(c2):
    from datetime import datetime
    from kundali import ephemeris as eph
    from kundali.sadesati import current_status, lifetime_table, murti
    jd = eph.jd_from_local(datetime(2026, 7, 12), c2.tz)
    active, nxt = current_status(c2, jd)
    assert active is not None and active[3] == 0        # CORE phase now
    assert SIGNS[active[2]] == "Pisces"
    assert nxt is not None and nxt[3] == 1              # final phase next
    rows = lifetime_table(c2, 40)
    assert all(r[4] in ("Gold", "Silver", "Copper", "Iron", "-") for r in rows)
    # anchored fixture value: Saturn's Pisces ingress in Mar 2025 -> Iron
    import swisseph as swe
    m, grade = murti(c2, swe.julday(2025, 3, 18, 0))
    assert m == "Iron"


# ---------- regression: global ayanamsa state must not leak ----------

def test_ayanamsa_state_isolation(c2):
    """Casting a Lahiri chart must not contaminate a Raman chart's
    subsequent ephemeris-backed computations. Caught by the Chandan
    verification: a Lahiri cast shifted the Sade Sati ingress dates by
    ~13 days."""
    from datetime import datetime
    from kundali import ephemeris as eph
    from kundali.sadesati import current_status
    jd = eph.jd_from_local(datetime(2026, 7, 12), c2.tz)
    _before, _ = current_status(c2, jd)
    cast_natal("pollute", "1994-06-02", "07:35", "Asia/Kolkata",
               14.6197, 74.8354, "Sirsi", "lahiri")     # flips global mode
    _after, _ = current_status(c2, jd)                  # must self-correct
    assert abs(_before[1] - _after[1]) < 0.01           # same end JD
    # and the Raman core phase must end ~21 May 2027 (+- scan grid)
    assert eph.jd_to_date_str(_after[1], c2.tz)[3:] == "May 2027"


def test_sadesati_cache_keys_on_ayanamsa():
    """The memoised Saturn scan must not serve one ayanamsa's dates to
    another. This birth instant is the worst case: Raman and Lahiri agree
    on the Moon's and Saturn's signs, so the ayanamsa name is the only
    thing telling the two cache entries apart - which is why `_spans`
    takes it despite never reading it."""
    from kundali.sadesati import _raw_spans
    args = ("C3", "1993-11-26", "22:03", "Asia/Kolkata",
            14.6197, 74.8354, "Sirsi")
    raman, lahiri = cast_natal(*args, "raman"), cast_natal(*args, "lahiri")
    assert raman.jd == lahiri.jd
    assert raman.sign_idx_of("Moon") == lahiri.sign_idx_of("Moon")
    assert raman.sign_idx_of("Saturn") == lahiri.sign_idx_of("Saturn")

    spans_r, spans_l = _raw_spans(raman), _raw_spans(lahiri)
    assert spans_r != spans_l                   # ~12 days apart, not shared
    assert _raw_spans(raman) == spans_r         # and stable either way round
    assert _raw_spans(lahiri) == spans_l
