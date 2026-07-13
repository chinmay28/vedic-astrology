# vedic-astrology

`kundali-report` — generate a Jyotish report (PDF and/or self-contained HTML) from a birth
date, time, and place: North + South Indian diagrams, positions with
dignities (incl. moolatrikona), panchanga and avakahada birth constants,
yogas, whole-sign aspects, Vimshottari dasha to pratyantar level,
Navamsa (D-9) with vargottama, Ashtakavarga (BAV/SAV), a lifetime
Sade Sati / Kantaka / Ashtama Shani table, Tajika varshaphala annual
charts with Mudda dasha, the full Shodashavarga (16 divisionals) with
Vimshopaka Bala, Panchadha Maitri, Ashtakavarga reductions (Trikona +
Ekadhipatya) with Shodhya Pinda, three Avastha systems, Bhav Chalit with
house-shift detection, a 'Dasha Now & Next' navigation section
(--asof DATE) with rule-based guidance and dasha-sandhi warnings, and a
full 'Sade Sati & Impacts' section: per-chart severity grading (Saturn's
functional role, natal condition, Moon protection, SAV ground - each
factor with its reason), current/next phase with classical impact
themes, Murti grading of every entry, double-Saturn overlap detection,
and navigation counsel - with inline "how to read this" guidance in
every section, and an input-verification panel that catches the
timezone/DST errors common in commercial reports.

Computation: Swiss Ephemeris, sidereal zodiac (Raman or Lahiri ayanamsa),
whole-sign houses, mean lunar node. Timezone handling uses the IANA
database, so historical DST (e.g. US Pacific time) is applied correctly.

## Install

```bash
pip install .            # or: pip install pyswisseph reportlab cairosvg
```

Requires Python 3.10+. `cairosvg` needs the cairo system library
(preinstalled on most Linux distros; `apt install libcairo2` otherwise).

## Usage

```bash
kundali-report \
  --name "Chart 3" \
  --date 1993-11-26 --time 22:03 --tz Asia/Kolkata \
  --lat 14.6197 --lon 74.8354 --place "Sirsi, Karnataka, India" \
  --ayanamsa raman \
  --varsha 2026 2027 2028 \
  --out chart3.pdf
```

Or without installing: `python -m kundali <same flags>`.

| Flag | Meaning |
|---|---|
| `--date` | Birth date, `YYYY-MM-DD` |
| `--time` | Local birth time, 24h `HH:MM` |
| `--tz` | IANA zone name (`Asia/Kolkata`, `America/Los_Angeles`, ...) |
| `--lat --lon` | Decimal degrees, north/east positive |
| `--ayanamsa` | `raman` (default) or `lahiri` |
| `--varsha` | Calendar years for annual charts (0+ years; age-0 is skipped) |
| `--out` | Output PDF path |

Coordinates are an explicit input by design — geocoding services change,
coordinates don't. Look them up once (any map app shows them).

## Contracts

* `ephemeris.py` is the only module that touches Swiss Ephemeris.
* `model.py` holds static reference data and the `Chart` object; pure.
* `dasha.py`, `aspects.py`, `yogas.py`, `varshaphal.py`: pure functions
  over `Chart`/longitudes.
* `diagrams.py` renders validated North/South geometry to PNG.
* `report.py` assembles the PDF; `cli.py` is the entry point.

## Tests

```bash
pip install pytest && python -m pytest tests/
```

The suite pins golden values from three hand-validated charts (lagnas,
degrees, nakshatras, dasha dates, solar-return dates, muntha houses,
aspect pairs, yoga detection, DST correctness). If they fail, the
ephemeris contract has drifted.

## Output formats

`--format pdf` (default), `--format html` (single self-contained file,
dark theme, inline SVG charts), or `--format both`.

## Scope, honestly stated

The tool automates the *computation* and the *classical rule layer*
(dignities, standard yogas, muntha grades, dasha/mudda calendars,
Navamsa D-9 with vargottama, Bhinna- and Sarva-ashtakavarga). It does
not attempt the interpretive synthesis a practicing astrologer adds on
top; see USER_GUIDE.md for how to read the output and where human
judgment enters.

**Fixture-validated (v1.3):** the Ashtakavarga reduction chain, Shodhya
Pinda, Panchadha Maitri and the Avasthas are tested cell-for-cell
against an independent commercial report for a known chart.

**Deliberately deferred: Shadbala.** A correct implementation needs
seven divisional charts and a dozen sub-strengths (natonnata, paksha,
tribhaga, ayana, cheshta...); a partial version would emit numbers that
disagree with standard software, which is worse than none. Also out of
scope: divisional charts beyond D-9, and full Panchavargiya Bala for
the Tajika year-lord (candidates are listed with dignity hints instead).

The Ashtakavarga tables are the standard Parashari set; the test suite
asserts the classical invariants (per-BAV totals 48/49/39/54/56/52/39,
SAV 337) on every run.
