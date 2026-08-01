# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

`kundali-report`: a Python CLI that computes a Vedic (Jyotish) natal +
Tajika varshaphala chart and renders it as a PDF and/or a self-contained
HTML report. Swiss Ephemeris, sidereal zodiac (Raman default, Lahiri
optional), whole-sign houses, mean lunar node. See README.md for the
feature list and USER_GUIDE.md for how the output is meant to be read.

## Commands

```bash
pip install -e .[dev]        # deps: pyswisseph, reportlab, cairosvg; dev adds pytest
python -m pytest tests/      # golden-value test suite
python -m kundali --date 1993-11-26 --time 22:03 --tz Asia/Kolkata \
    --lat 14.6197 --lon 74.8354 --ayanamsa raman --out /tmp/chart.pdf
python -m kundali.webapp --host 0.0.0.0   # mobile web GUI, port 8777
sudo ./scripts/quickstart.sh             # install as a systemd service
```

`cairosvg` needs the cairo system library (`apt install libcairo2`).
There is no linter or formatter configured; match the existing style
(PEP 8, ~79 columns, module docstrings that state the module's contract).

## Architecture

The package is a layered pipeline: ephemeris → pure computation → rendering.

- `ephemeris.py` — **the only module allowed to import `swisseph`.**
  Everything takes/returns Julian Day (UT) floats and sidereal longitudes
  in degrees [0, 360). `set_ayanamsa()` must be called before any
  computation (the CLI does this once).
- `model.py` — static reference data (signs, nakshatras, dignities,
  natural friendships) and the `Chart` dataclass. Pure; no ephemeris calls.
- Pure computation over `Chart`/longitudes, one concern per module:
  `dasha.py` (Vimshottari + Mudda), `dasha_now.py` (running MD/AD/PD as of
  a date), `aspects.py` (whole-sign drishti), `yogas.py`, `varga.py`
  (D-9 / Shodashavarga + Vimshopaka), `maitri.py` (panchadha friendship),
  `avastha.py`, `ashtakavarga.py` (BAV/SAV + reductions), `bhav.py`
  (Bhav Chalit shift list), `panchanga.py`, `sadesati.py`,
  `varshaphal.py` (Tajika annual charts).
- `guidance.py` — inline "how to read this" prose per report section.
- Rendering: `diagrams.py` (North/South Indian charts, SVG → PNG),
  `report.py` (PDF via reportlab), `html_report.py` (single-file HTML that
  reuses the same computations and SVG geometry — keep the two in sync
  when adding sections).
- `cli.py` — argument parsing and `cast_natal()`, the single chart
  construction path for the whole tool. `__main__.py` delegates to it.
- `webapp/` — mobile-first web GUI, stdlib only, layered the same way:
  `store.py` (saved records in one SQLite file + input validation),
  `service.py` (record → JSON payload / report bytes), `server.py`
  (`ThreadingHTTPServer`, JSON API + static shell), `static/` (no build
  step: hand-written HTML/CSS/JS, service worker, manifest).

## Invariants and conventions

- **Golden tests**: `tests/test_charts.py` pins hand-validated values for
  three charts (lagnas, degrees, nakshatras, dasha dates, solar-return
  dates, yogas, DST correctness). A failure means the ephemeris contract
  drifted — do not "fix" expected values to make tests pass without
  understanding why they changed.
- **Ashtakavarga checksums**: per-BAV totals are fixed (Sun 48, Moon 49,
  Mars 39, Mercury 54, Jupiter 56, Venus 52, Saturn 39; SAV 337) and
  asserted on every run.
- Timezones are IANA names resolved via the standard library, so
  historical DST is applied correctly — never hand-roll UTC offsets.
- **The web app is a renderer, not a second implementation.** Every
  number it shows comes from the modules above; downloads call
  `report.py` / `html_report.py`. When adding a report section, add it
  to the PDF, the HTML report and `webapp/service.summary()` together.
- `webapp/service.py` holds `_LOCK` around every computation because
  Swiss Ephemeris' sidereal mode is process-global — a concurrent
  lahiri request would otherwise poison a raman one. Keep new entry
  points inside that lock.
- The web app adds no dependencies (stdlib `http.server` + `sqlite3`;
  `cairosvg`, already required, rasterises the PWA icons) and no
  frontend build step. Keep it that way.
- `scripts/quickstart.sh` is the systemd installer (idempotent, backs up
  the database before an upgrade, health-checks and self-heals). It must
  keep working when piped from curl *and* run from a checkout; a venv is
  never moved (console scripts hardcode their path) — the
  `$PREFIX/venv` symlink is what swaps. `deploy/kundali-web.service` is
  the reference unit and DEPLOYMENT.md the operator doc; keep the three
  in sync when the unit or the paths change.
- The web app has no authentication on purpose (trusted-network tool,
  binds 127.0.0.1 by default). Don't bolt on half of an auth system;
  if it ever needs one, it needs the whole thing.
- Coordinates are explicit CLI inputs by design; do not add geocoding.
- **Deliberately out of scope** (see README "Scope, honestly stated"):
  Shadbala, divisional charts beyond what varga.py implements, full
  Panchavargiya Bala. A partial implementation that emits numbers
  disagreeing with standard software is worse than none — don't add
  these piecemeal.
- Interpretive text (guidance.py, dasha_now.py counsel) is rule-based and
  classical in framing: themes and cautions, not event predictions. Keep
  that register when editing.
