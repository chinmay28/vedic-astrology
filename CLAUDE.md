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
sudo ./scripts/quickstart.sh             # install as a Docker service (Pi-friendly)
sudo ./scripts/install-systemd.sh        # ...or straight onto the host, under systemd
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
  `store.py` (saved charts and saved places in one SQLite file + input
  validation), `service.py` (record → JSON payload / report bytes),
  `geocode.py` (the optional city lookup, and the only outbound call in
  the project), `server.py` (`ThreadingHTTPServer`, JSON API + static
  shell), `static/` (no build step: hand-written HTML/CSS/JS, service
  worker, manifest).

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
- `server.run()` drains on SIGTERM/SIGINT: it stops accepting, waits up
  to `DRAIN_TIMEOUT` for in-flight requests (a PDF render takes seconds),
  then exits 0. Upgrades depend on it — keep new long-running work inside
  the request path so the `_inflight` counter sees it, and keep
  `stop_grace_period` in the compose file above `DRAIN_TIMEOUT`.
- `webapp/service.py` holds `_LOCK` around every computation because
  Swiss Ephemeris' sidereal mode is process-global — a concurrent
  lahiri request would otherwise poison a raman one. Keep new entry
  points inside that lock.
- `sadesati._spans` memoises the 90-year Saturn ingress scan, which
  dominated every render (a chart summary was 2.3s, of which 2.25s was
  this, scanned twice). It is keyed on the birth instant **and the
  ayanamsa name**, which the scan body never reads — the body reads the
  process-global sidereal mode the caller just set from it, so dropping
  the name from the key silently serves one ayanamsa's dates to another.
  A test pins that. `_raw_spans` re-sets that mode on hits as well as
  misses, so a cached call leaves the process exactly as a fresh one
  would. Cache derived-from-the-chart work this way rather than caching
  a whole payload: the reports mix natal values, which never change,
  with as-of-today ones, which must not be frozen.
- **The web app is called Janma Kundali; the package and commands are
  not.** (It was called Jataka until v1.5 — that name should not come
  back anywhere.) "Janma Kundali" is the display name only: `<title>`,
  the manifest, the app bar, the PDF/HTML document title. The package
  (`kundali`), the console scripts (`kundali-report`, `kundali-web`), the
  database filename, the install paths, the Docker volume and the systemd
  unit deliberately keep the `kundali` name, because deployed instances
  depend on them. Do not "finish" the rename without a migration path in
  both installers. The same words are also domain vocabulary inside a
  report, which is why the rename cost nothing there.
- Branding lives in `webapp/static/`: `icon.svg` is the app mark (also
  rasterised for the PWA icons), `dev-badge*.png` the developer badge.
  The version shown in the app header comes from `/api/health`, i.e.
  `kundali.__version__` — the same string stamped into the PDF footer and
  the HTML report, so a document always names the build that made it.
- **The version assembles itself; do not hand-write one.**
  `kundali/version.py` holds `MAJOR`/`MINOR` and nothing else does -
  `pyproject.toml` is `dynamic` and reads `kundali.__version__`. The
  patch is the commit count (every commit is a patch release, as in
  CountRoster), resolved in this order: `$KUNDALI_VERSION_PATCH` ->
  `git rev-list --count HEAD` in the checkout -> the patch pip recorded
  in the installed metadata -> 0. That last-resort 0 is deliberate: a
  shallow clone must not report a number that is too small. The Docker
  build has no `.git` (see .dockerignore), so `scripts/quickstart.sh`
  writes the count into `.env` and compose passes it as a build arg -
  keep that chain intact when touching either file.
- The web app adds no dependencies (stdlib `http.server` + `sqlite3`;
  `cairosvg`, already required, rasterises the PWA icons) and no
  frontend build step. Keep it that way.
- Two installers, both idempotent, both backing up the database before an
  upgrade and rolling back on a failed health check. Each must keep
  working when piped from curl *and* when run from a checkout:
  `scripts/quickstart.sh` (the headline one-liner: installs Docker if
  missing, builds the image, runs Compose; it exits early when the built
  image already matches the running one, smoke-tests a new image in a
  throwaway container before swapping, and keeps the previous image as
  `kundali-web:prev` to roll back to) and `scripts/install-systemd.sh`
  (the non-container path: a venv per build under `$PREFIX/venvs` with
  the `$PREFIX/venv` symlink swapping between them, because a venv can
  never be moved — console scripts hardcode their path).
  `deploy/*.service` are the reference units and DEPLOYMENT.md the
  operator doc; keep them in sync when paths or the unit change.
- `Dockerfile` / `docker-compose.yml` are the container path: two stages,
  unprivileged uid 10001, read-only rootfs, and **all** state in `/data`
  (plus `/tmp` for PDF scratch). Keep that true — a feature that writes
  anywhere else breaks `read_only: true`. The venv is built and copied at
  the same path (`/opt/venv`) for the reason above. The compose project
  name is pinned (`name: kundali`) so the data volume is
  `kundali_kundali-data` regardless of the checkout directory; the
  published address comes from `KUNDALI_BIND`/`KUNDALI_PORT` (a `.env`
  the installer writes), not from edits to the compose file.
- The web app has no authentication on purpose (trusted-network tool,
  binds 127.0.0.1 by default). Don't bolt on half of an auth system;
  if it ever needs one, it needs the whole thing.
- Coordinates are explicit inputs by design and the CLI has no lookup at
  all - `--tz` stays required there. The web app's **Places** tab (a
  `places` table in the same SQLite file, no computation attached) and
  `webapp/geocode.py` are the one exception, and a narrow one: a single
  outbound GET, only when someone searches or saves a chart whose zone is
  not known yet, only when `$KUNDALI_GEOCODER` is not `off`, and every
  form still works with the lookup dead. Keep it that way - no background
  lookups, and never make an already-saved chart depend on a network call.
- **The timezone is inferred from the birthplace, never asked for and
  never guessed.** A picked place or search hit brings its own zone;
  typed coordinates get one from the index; `server._with_timezone`
  resolves a missing zone once, on write, and stores it, so a lookup that
  answers differently later cannot move a saved chart. When it cannot be
  established the GUI shows the field again and the API returns 400.
  Do not add an offline fallback: nearest representative city in the tz
  database's own table - the only stdlib option - puts Sirsi in
  Asia/Colombo and Mumbai in Asia/Karachi, both half an hour out, which
  is the exact error class this tool exists to prevent. A test pins that
  geocode.py never reads zone.tab.
- The GUI shows the resolved zone and where it came from, with a Change
  link. That is deliberate: it is the one inferred value a wrong answer
  silently ruins a chart with, so it stays visible and overridable.
  `renderTz()` updates the box in place - never re-render it wholesale,
  because it is reached by tabbing out of a coordinate field (which
  fires a lookup) and a replaced input eats what is being typed.
- **Deliberately out of scope** (see README "Scope, honestly stated"):
  Shadbala, divisional charts beyond what varga.py implements, full
  Panchavargiya Bala. A partial implementation that emits numbers
  disagreeing with standard software is worse than none — don't add
  these piecemeal.
- Interpretive text (guidance.py, dasha_now.py counsel) is rule-based and
  classical in framing: themes and cautions, not event predictions. Keep
  that register when editing.
