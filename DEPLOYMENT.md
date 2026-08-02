# Deploying Janma Kundali (kundali-web)

**Janma Kundali** is the mobile web GUI (see README); `kundali-web` is the
command that serves it. This is how to run it as a service on a Linux
box — a home server, a NAS, a Raspberry Pi — so every phone on the
network shares one database.

## Docker (the default)

One command, on a Raspberry Pi or any Debian/Ubuntu host, x86 or ARM:

```bash
curl -fsSL https://raw.githubusercontent.com/chinmay28/vedic-astrology/main/scripts/quickstart.sh | sudo bash
```

From a fresh machine it installs Docker if missing, clones to
`/opt/kundali/src`, builds the image, starts the container, and health-checks
it. Re-run the same command to upgrade — it backs the database up to the host
first, builds while the old container keeps serving, and rolls back to the
previous image if the new one fails its health check.

Already have a checkout? `sudo ./scripts/quickstart.sh` builds *that* tree
instead of cloning a second copy. Or drive Compose yourself:

```bash
docker compose up -d          # builds on first run
docker compose logs -f
docker compose down           # stops it; the volume - and your charts - survive
```

Where it listens comes from the environment, so the compose file needs no
editing (the installer writes these into `.env` beside it):

```bash
KUNDALI_BIND=0.0.0.0 KUNDALI_PORT=8777 docker compose up -d
```

### Installer options

```bash
curl -fsSL …/scripts/quickstart.sh | sudo KUNDALI_BIND=127.0.0.1 PORT=9090 bash
```

| Variable | Default | Meaning |
|---|---|---|
| `KUNDALI_BIND` | `0.0.0.0` | Address to publish on; `127.0.0.1` keeps it on the host |
| `PORT` | `8777` | Published port |
| `KUNDALI_REPO` | this repo | Repo to clone (a fork works) |
| `KUNDALI_REF` | `main` | Branch, tag or commit to build |
| `KUNDALI_PREFIX` | `/opt/kundali` | Where the source is cloned |
| `BACKUP_DIR` | `/var/lib/kundali/backups` | Host directory for pre-upgrade backups |
| `BACKUP_KEEP` | `10` | Backups kept |
| `INSTALL_DOCKER` | `auto` | `never` to fail instead of installing Docker |
| `KUNDALI_GEOCODER` | Open-Meteo's index | `off` disables the city search and timezone inference; a URL points it elsewhere. Set it in `.env` beside the compose file — see [Place search and timezone inference](#place-search-and-timezone-inference). |

On a Pi the first build takes roughly 5-15 minutes (longer on a Pi 3, or on
32-bit Pi OS where pyswisseph compiles from source); later runs reuse
Docker's layer cache. The installer also adds the invoking user to the
`docker` group, so `docker` works without `sudo` after the next login.

**What "isolated" means here.** The container writes to exactly two places:
the `kundali-data` volume (`/data/kundali.sqlite` and its WAL sidecars) and
`/tmp`, which holds scratch files only while a PDF renders. Nothing else on
the host is touched, and the compose file makes that structural:

- `read_only: true` — the container filesystem is immutable; `/data` (the
  volume) and `/tmp` (a 256 MB tmpfs) are the only writable mounts.
- runs as uid `10001`, never root, with `cap_drop: ALL` and
  `no-new-privileges`.
- `127.0.0.1:8777:8777` — published to the loopback interface only. Drop the
  `127.0.0.1:` prefix to reach it from your phone; there is still no
  authentication, so do that on a network you trust.

The image is two-stage: the builder compiles wheels, the runtime carries
only Python, libcairo and the virtualenv.

**Upgrades.** Re-run the quickstart command. What it does, in order:

1. **Builds** the new image while the old container keeps serving. A failed
   build changes nothing.
2. **Stops early if nothing changed.** If the rebuilt image is byte-identical
   to the one already running and the app is healthy, the container is not
   touched at all - no restart, no backup, no downtime. Re-running the
   installer "just to be sure" costs nothing.
3. **Smoke-tests the new image** in a throwaway container on a scratch
   volume. An image that cannot boot is rejected here, before anything
   you are using is stopped - a broken build causes no outage at all.
4. **Backs up** the database to the host through `/api/export/kundali.sqlite`
   (WAL folded in), keeping the newest `BACKUP_KEEP` copies.
5. **Recreates** the container. The old one gets SIGTERM and drains: the
   server stops accepting connections and finishes what is in flight, so a
   PDF someone is downloading completes instead of arriving truncated
   (`stop_grace_period: 30s` covers a render that is nearly done).
6. **Health-checks** the new container against the real data, and rolls back
   to `kundali-web:prev` with the pre-upgrade database if it fails.

So: zero downtime when nothing changed, none when a build is broken, and a
few seconds - one container recreate - on a genuine upgrade. The volume is
not part of the image, so rebuilding, re-tagging or removing the container
never touches the database.

**Backups.** The web app's own Data screen (JSON / CSV / SQLite download)
works exactly as it does anywhere else. From the host:

```bash
docker compose exec kundali-web \
    python -c "import urllib.request,sys; sys.stdout.buffer.write(
    urllib.request.urlopen('http://127.0.0.1:8777/api/export/kundali.sqlite').read())" \
    > kundali-backup.sqlite
```

That takes a proper SQLite backup with the WAL folded in, which copying the
file out of a running container does not.

**Moving an existing database in.** Stop the container, then:

```bash
docker run --rm -v kundali-data:/data -v "$PWD:/in" alpine \
    sh -c 'cp /in/kundali.sqlite /data/ && chown 10001:10001 /data/kundali.sqlite'
```

**Bind mount instead of a volume?** Replace the `volumes:` entry with a host
path and give it to the container's uid: `sudo chown -R 10001:10001 /srv/kundali`.

**Volume naming.** The compose file pins the project name to `kundali`, so
the volume is `kundali_kundali-data` wherever the checkout lives. If you
started the stack before that was pinned, your data is in
`<directory>_kundali-data`; move it over once with:

```bash
docker run --rm -v vedic-astrology_kundali-data:/from -v kundali_kundali-data:/to \
    kundali-web:local sh -c 'cp -a /from/. /to/'
```

To have systemd own the container's lifecycle rather than Docker's restart
policy, `deploy/kundali-web-docker.service` runs the compose stack at boot.

Everything below — the systemd install, its upgrade and rollback machinery —
is the non-container path.

## Install as a systemd service

Prefer this when you would rather not run Docker on the host: it installs
the app straight onto the machine, supervised by systemd.

```bash
curl -fsSL https://raw.githubusercontent.com/chinmay28/vedic-astrology/main/scripts/install-systemd.sh | sudo bash
```

That clones the repo, installs it into a private virtualenv, creates a
dedicated system user, writes a hardened systemd unit and starts it. Open
`http://<host>:8777`.

Already have a checkout? `sudo ./scripts/install-systemd.sh` installs
*that* tree instead of cloning a second copy.

**Re-run the same command to upgrade.** It is idempotent and data-safe;
see [Upgrades and rollback](#upgrades-and-rollback).

### Options

Everything is an environment variable, so a one-liner stays a one-liner:

```bash
curl -fsSL …/scripts/install-systemd.sh | sudo PORT=9090 KUNDALI_REF=v1.4.0 bash
```

| Variable | Default | Meaning |
|---|---|---|
| `KUNDALI_REPO` | `https://github.com/chinmay28/vedic-astrology.git` | Repo to clone (a fork works) |
| `KUNDALI_REF` | `main` | Branch, tag or commit to install |
| `KUNDALI_USER` | `kundali` | System user the service runs as |
| `KUNDALI_PREFIX` | `/opt/kundali` | Code + virtualenv location |
| `KUNDALI_DATA_DIR` | `/var/lib/kundali` | Database and backups |
| `KUNDALI_SERVICE` | `kundali-web` | systemd unit name |
| `PORT` | `8777` | Port to listen on |
| `HOST` | `0.0.0.0` | Bind address (`127.0.0.1` for localhost only) |
| `PYTHON` | `python3` | Interpreter to build the venv from (needs ≥ 3.10) |
| `BACKUP_KEEP` | `10` | Pre-upgrade database snapshots to keep |
| `KUNDALI_GEOCODER` | Open-Meteo's index | `off` disables the city search and timezone inference — see [Place search and timezone inference](#place-search-and-timezone-inference) |

Running two instances on one host: give each its own `KUNDALI_SERVICE`,
`KUNDALI_PREFIX`, `KUNDALI_DATA_DIR` and `PORT`.

## What lands where

| Component | Path |
|---|---|
| Source tree | `/opt/kundali/src` (root-owned; the service only reads it) |
| Virtualenv | `/opt/kundali/venv` → `/opt/kundali/venvs/build-<timestamp>` |
| Database | `/var/lib/kundali/kundali.sqlite` |
| Backups | `/var/lib/kundali/backups/kundali-<timestamp>.sqlite` |
| Unit file | `/etc/systemd/system/kundali-web.service` (reference copy in `deploy/`) |

The virtualenv is a symlink to a timestamped build. A virtualenv cannot be
relocated — its console scripts hardcode their own path — so flipping the
symlink is what makes the swap atomic and the rollback instant.

Prerequisites the installer handles on apt systems: `git`, `curl`,
`python3-venv`, and `libcairo2` (cairosvg rasterises the chart diagrams and
the PWA icons). If no `pyswisseph` wheel matches the platform — common on
older ARM boards — it installs `build-essential` and the Python headers and
retries once.

## Managing the service

```bash
systemctl status  kundali-web
systemctl restart kundali-web
journalctl -u kundali-web -f
```

`restart` and `stop` are graceful: systemd sends SIGTERM, and the server
stops accepting new connections and finishes in-flight requests (up to 25
seconds) before exiting, so an in-progress PDF download is not cut off.

The CLI is installed alongside it:

```bash
/opt/kundali/venv/bin/kundali-report --date 1993-11-26 --time 22:03 \
    --tz Asia/Kolkata --lat 14.6197 --lon 74.8354 --out /tmp/chart.pdf
```

## Upgrades and rollback

Re-running the script performs, in order:

1. **Fetch** the new code. If that fails, the running service is untouched.
2. **Build** a fresh virtualenv beside the live one and import-check it —
   a missing libcairo or a broken wheel is caught here, while the old
   version is still serving.
3. **Stop** the service and **snapshot** the database (plus its `-wal` and
   `-shm` sidecars) to `backups/`, so the copy is taken quiesced. The
   newest `BACKUP_KEEP` snapshots are kept.
4. **Flip** the venv symlink, rewrite the unit, start.
5. **Health check** `/api/health` for 15 seconds. If the new version is
   unhealthy, it rolls the symlink back to the previous build, checks the
   source tree back out at the previous commit, restores the pre-upgrade
   database snapshot and restarts — then reports the failure with a
   `journalctl` pointer.

Data is never re-initialised: the database lives outside the source tree,
so cloning, pulling and rebuilding cannot touch it.

## Backups

The installer's snapshots cover upgrades. For routine backups, use the web
app itself — the **Data** screen downloads everything as JSON (charts and
saved places together), charts or places as CSV, or the whole
`kundali.sqlite` file, and restores from a JSON backup (matching records
are updated, not duplicated; a backup taken before places existed still
restores). Everything is an open format; the SQLite file opens in any
SQLite tool.

Copying the live database file directly is fine while the service is
stopped. While it is running, prefer the `/api/export/kundali.sqlite`
endpoint — it takes a proper SQLite backup with the WAL folded in.

## Place search and timezone inference

The **Places** tab and the birthplace box on the chart form can look a
city or town up instead of asking for coordinates, and work out the
timezone from the birthplace so nobody has to type one. Those lookups are
the only thing in this project that leaves the machine:

* One outbound `GET` per lookup, made by the server (never by the phone),
  to `$KUNDALI_GEOCODER` — Open-Meteo's public GeoNames index by default.
* A search carries the name typed into the box and nothing else. A
  timezone lookup carries a latitude and longitude and nothing else. No
  birth times, no names, no identifiers.
* A search runs only when someone presses **Search**. A timezone lookup
  runs when coordinates change on a form, or when a chart is saved whose
  zone is not known yet — never for a chart that already has one.
* Results fill in latitude, longitude and the IANA timezone.

A chart's zone is resolved **once, on write, and stored**. Nothing
re-resolves a saved chart, so a lookup that answers differently later
cannot move a chart you already have.

To keep an installation sealed, switch it off — the GUI then hides the
search box rather than offering a button that cannot work, and asks for
the timezone as it used to:

```bash
# Docker: add it to the .env beside docker-compose.yml, then re-run up -d
KUNDALI_GEOCODER=off

# systemd: add to the unit and `systemctl daemon-reload && restart`
Environment=KUNDALI_GEOCODER=off
```

Setting it to a URL points the search at another GeoNames-shaped index (a
self-hosted one, for instance); `KUNDALI_TZ_LOOKUP` does the same for the
coordinate-to-zone endpoint, and `off` disables just that half.
`/api/health` reports which index is in use for each, or `null`.

**The zone is never guessed.** If it cannot be established the form asks,
and the API answers `400` rather than storing something plausible: the
only offline alternative — nearest city in the tz database's own table —
places Indian births in `Asia/Colombo` or `Asia/Karachi`, half an hour
out, which is the exact class of error this tool exists to avoid.

## Exposing it safely

**There is no authentication, by design.** Anyone who can reach the port
can read and edit every chart. Keep it on a trusted network: a LAN, a
Tailscale tailnet, or a VPN. Under Docker the published port is
`127.0.0.1:8777:8777` — change it to `8777:8777` to reach the app from
other devices; under systemd the equivalent knob is `HOST`
(`0.0.0.0` to publish, `127.0.0.1` to keep it local to the machine).

For HTTPS — which browsers require before they will install a PWA from
anything other than `localhost` — front it with Tailscale Serve:

```bash
tailscale serve --bg 8777
```

…or a reverse proxy. Caddy, two lines:

```
kundali.example.com {
    reverse_proxy 127.0.0.1:8777
}
```

If you put it behind a proxy that is reachable from the internet, add
authentication *at the proxy* (basic auth, an identity provider, Tailscale
Funnel with an ACL). Do not expose it unauthenticated.

## Uninstalling

Container install — `down -v` is what deletes the charts, so it is opt-in:

```bash
docker compose down            # stop; the volume survives
docker compose down -v         # …and delete the data volume too
docker image rm kundali-web:local
```

systemd install:

```bash
sudo systemctl disable --now kundali-web
sudo rm /etc/systemd/system/kundali-web.service
sudo systemctl daemon-reload
sudo rm -rf /opt/kundali            # code and virtualenvs
# Your charts live here. Back them up first if you want to keep them:
sudo rm -rf /var/lib/kundali
sudo userdel kundali
```

## Without systemd

The app is a plain Python package with no runtime services of its own:

```bash
pip install .
kundali-web --host 0.0.0.0 --port 8777 --db /path/to/kundali.sqlite
```

Anything that can supervise a long-running process — a container, an
OpenRC/runit service, `launchd`, `tmux` for a quick trial — will do. The
database path is the only state.
