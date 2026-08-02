# vedic-astrology

`kundali-report` — generate a Jyotish report (PDF and/or self-contained HTML) from a birth
date, time, and place: North + South Indian diagrams, positions with
dignities (incl. moolatrikona), panchanga and avakahada birth constants,
yogas, whole-sign aspects, Vimshottari dasha to pratyantar level with
navigation guidance for every mahadasha of the cycle, a week-ahead
gochara reading (day by day from the natal Moon),
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

## Quick start

**Janma Kundali, the web app — one command.** On a Raspberry Pi, or any
Debian/Ubuntu machine, x86 or ARM:

```bash
curl -fsSL https://raw.githubusercontent.com/chinmay28/vedic-astrology/main/scripts/quickstart.sh | sudo bash
```

Starting from a fresh Pi that is all of it: the script installs Docker if
it is missing, fetches the source, builds the image, starts the container
and prints the URL to open. Your charts live in a Docker volume, so
rebuilds and upgrades never touch them, and the container comes back with
the Pi on its own.

Open the URL on a phone and *Add to Home Screen* — it is an installable
PWA. First build on a Pi takes roughly 5–15 minutes; later runs are much
quicker.

**Re-run the same command to upgrade.** It builds while the old container
keeps serving, does nothing at all if nothing changed, smoke-tests the new
image before swapping it in, backs the database up to the host, and rolls
back if the new version turns out unhealthy. A PDF someone is downloading
finishes rather than arriving truncated.

It publishes on `0.0.0.0:8777` so your phone can reach it. There is no
authentication — keep it on a network you trust, or install it with
`KUNDALI_BIND=127.0.0.1` and put a proxy in front. Options, backups and
HTTPS: [DEPLOYMENT.md](DEPLOYMENT.md).

**Just want a PDF?** No Docker needed — Python 3.10+ and the cairo system
library (`apt install libcairo2`):

```bash
git clone https://github.com/chinmay28/vedic-astrology.git
cd vedic-astrology
pip install .

kundali-report --name "Chart 3" \
  --date 1993-11-26 --time 22:03 --tz Asia/Kolkata \
  --lat 14.6197 --lon 74.8354 --place "Sirsi, Karnataka, India" \
  --out chart3.pdf
```

How to read the report once you have one: [USER_GUIDE.md](USER_GUIDE.md).

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

Coordinates are an explicit input on the command line by design —
geocoding services change, coordinates don't. Look them up once (any map
app shows them). The web app can search for a town for you and save the
result; the CLI never calls out to anything.

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

## Janma Kundali — the web app (mobile friendly)

**Janma Kundali** is the phone-first GUI over the same computation pipeline —
one small server owns a single SQLite file, and every device on the
network is a client of it. One command installs it (see
[Quick start](#quick-start)). It installs to the home screen under that
name; the package and commands keep the `kundali-` prefix.

The server itself is the `kundali-web` console script, which is what the
container runs; [DEPLOYMENT.md](DEPLOYMENT.md) covers running it directly
or under systemd, plus upgrades, backups and HTTPS.

Open it on a phone and *Add to Home Screen* — it is an installable PWA
(standalone window, cached app shell, previously viewed charts readable
offline). No build step: the frontend is hand-written HTML/CSS/JS
served straight from `kundali/webapp/static/`.

| In the GUI | What you get |
|---|---|
| Charts | Saved birth records, searchable; add/edit/delete |
| Places | Saved coordinates, searchable; pick one on the chart form instead of re-typing a birthplace |
| Snapshot | Lagna, rashi, nakshatra, input verification, panchanga, avakahada, yogas |
| Charts | North / South / D-9 diagrams (the same SVG geometry the PDF uses), positions, drishti, Bhav Chalit |
| Dasha | The week ahead (gochara, day by day — folded away by default, with week-stepping arrows), running MD/AD/PD with progress, rule-based navigation guidance, full Vimshottari timeline, per-mahadasha navigation for every era of the cycle, varshaphala |
| Strength | SAV bar chart with the 30/24-bindu thresholds, BAV table, Vimshopaka, Shodashavarga, Maitri, Avasthas |
| Shani | Sade Sati severity grading, current/next phase with Murti, lifetime table |
| Report | **PDF download**, single-file HTML, JSON, positions CSV, dasha CSV — with an as-of date and varsha years you pick on the page |
| Data | Backups as JSON / CSV / the raw `kundali.sqlite`, plus JSON restore |

Reports downloaded from the GUI are produced by `report.py` and
`html_report.py` — the same code the CLI runs, so a PDF from the phone
is the PDF from the terminal. The running version is shown in the app
header, on the Data screen and in the footer of every report, so it is
always clear which build produced a document.

**Version numbers.** `MAJOR.MINOR.PATCH`, where the patch is the
repository's commit count — every commit is a patch release, so `1.5.42`
is the 42nd commit on the 1.5 line, the same scheme
[CountRoster](https://github.com/chinmay28/CountRoster) uses. `MAJOR` and
`MINOR` are declared in `kundali/version.py` and nowhere else;
`scripts/version.py` prints what this checkout would build as. A build
that genuinely cannot count (a shallow clone) reports patch `0` rather
than a number that is too small.

**No authentication, by design.** Like the tracker app this borrows its
shape from, it is meant for a trusted network (LAN, VPN, tailnet);
anyone who can reach the port can read and edit every chart. The
quickstart publishes on `0.0.0.0` because a phone has to reach it —
install with `KUNDALI_BIND=127.0.0.1` if you would rather it stayed on
the machine. The "use this device's location" button reads the phone's own
GPS and sends nothing anywhere.

### Places, and looking a town up

The **Places** tab is a coordinate book: save the birthplace once, pick it
from the chart form ever after. Nothing is computed from a place — it only
fills in latitude, longitude and timezone.

**The timezone is not asked for.** It is a fact about the birthplace, so
it comes from the birthplace: a place picked from the index or from your
saved places brings its own zone, and coordinates typed by hand are looked
up. The chart form shows the result and where it came from, with a
*Change* link, because a chart cast in the wrong zone is wrong by hours —
this is the one inference you must be able to see and overrule. It is
resolved once, when the chart is saved, and stored; a lookup answering
differently next year never moves a chart you already have.

If the zone cannot be established — search switched off, or offline — the
field comes back and asks. **It is never guessed.** The tempting offline
shortcut, nearest city in the tz database's own table, is wrong exactly
where this tool is most used: it puts Sirsi in `Asia/Colombo` and Mumbai
in `Asia/Karachi`, both half an hour out. A question beats a plausible
lie.

Typing a town name is optional convenience, and the only thing in this
project that talks to the internet. Pressing *Search* sends that name (and
nothing else) to Open-Meteo's public GeoNames index, which answers with
coordinates **and the IANA timezone** — the part people most often get
wrong. Saving a chart whose zone is not known yet asks the same index
which zone those coordinates sit in. Both run server-side, so phones talk
only to your own server.

Switch it off for an installation that must stay sealed:

```bash
KUNDALI_GEOCODER=off      # hides the search box and asks for the timezone
```

Point it at another GeoNames-shaped index by setting the same variable to
that URL. With search off — or simply offline — every form still works:
type the coordinates and the zone in, as the CLI always has. The CLI's
`--tz` stays required for the same reason: it has no lookup and must not
invent one.

## Credits

Built by CM Hegday · 0x434d — [github.com/chinmay28](https://github.com/chinmay28).
The developer badge in the app header is the same mark used in
[CountRoster](https://github.com/chinmay28/CountRoster); tap it to see it
full screen.

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
