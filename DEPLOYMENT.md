# Deploying kundali-web

`kundali-web` is the mobile web GUI (see README). This is how to run it as
a service on a Linux box — a home server, a NAS, a Raspberry Pi — so every
phone on the network shares one database.

## Quick start (Linux + systemd)

```bash
curl -fsSL https://raw.githubusercontent.com/chinmay28/vedic-astrology/main/scripts/quickstart.sh | sudo bash
```

That clones the repo, installs it into a private virtualenv, creates a
dedicated system user, writes a hardened systemd unit and starts it. Open
`http://<host>:8777`.

Already have a checkout? `sudo ./scripts/quickstart.sh` installs *that*
tree instead of cloning a second copy.

**Re-run the same command to upgrade.** It is idempotent and data-safe;
see [Upgrades and rollback](#upgrades-and-rollback).

### Options

Everything is an environment variable, so a one-liner stays a one-liner:

```bash
curl -fsSL …/scripts/quickstart.sh | sudo PORT=9090 KUNDALI_REF=v1.4.0 bash
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
app itself — the **Data** screen downloads all charts as JSON or CSV, or
the whole `kundali.sqlite` file, and restores from a JSON backup (matching
records are updated, not duplicated). Everything is an open format; the
SQLite file opens in any SQLite tool.

Copying the live database file directly is fine while the service is
stopped. While it is running, prefer the `/api/export/kundali.sqlite`
endpoint — it takes a proper SQLite backup with the WAL folded in.

## Exposing it safely

**There is no authentication, by design.** Anyone who can reach the port
can read and edit every chart. Keep it on a trusted network: a LAN, a
Tailscale tailnet, or a VPN. `HOST=127.0.0.1` restricts it to the machine
itself if you only want a reverse proxy to reach it.

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
