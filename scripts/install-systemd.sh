#!/usr/bin/env bash
#
# kundali-web - install straight onto the host, under systemd
# (Ubuntu / Debian / Raspberry Pi OS).
#
# This is the non-container path, for hosts that would rather not run Docker.
# The default install is scripts/quickstart.sh (Docker); see DEPLOYMENT.md.
#
# One command, run as root, installs the web GUI as a hardened systemd service:
#
#   curl -fsSL https://raw.githubusercontent.com/chinmay28/vedic-astrology/main/scripts/install-systemd.sh | sudo bash
#
# What it installs: the repo is cloned to $PREFIX/src and pip-installed into a
# private virtualenv at $PREFIX/venv, which systemd runs as a dedicated user.
# There is no build step and no JS toolchain - the PWA is served from the
# package's static directory as-is.
#
# It is deliberately *non-disruptive* and *data-safe* - re-run it any time to
# upgrade in place:
#
#   * Idempotent. Re-running only swaps in newer code; it never re-initialises
#     data, and re-running an unchanged version is a no-op restart.
#   * The live SQLite database lives at a stable path OUTSIDE the source tree
#     ($DATA_DIR), so cloning, pulling or rebuilding can never clobber it.
#   * Every upgrade STOPS the service, snapshots the database (+ WAL/SHM
#     sidecars) to a timestamped backup, THEN swaps code in - so the backup is
#     always taken against a quiesced database.
#   * Each install builds its own virtualenv under $PREFIX/venvs and flips the
#     $PREFIX/venv symlink to it, so the old version keeps serving while the
#     new one installs. If the install fails, the running service is untouched.
#     (A virtualenv cannot be moved - its console scripts hardcode their own
#     path - so the symlink is what makes the swap atomic.)
#   * After restart we poll /api/health; if the new version is unhealthy we
#     ROLL BACK to the previous virtualenv and commit, restore the pre-upgrade
#     database snapshot, and restart - so a bad upgrade self-heals to the last
#     good state with its data.
#
# Configure via environment variables (all optional):
#
#   KUNDALI_REPO      git URL to clone        (default: https://github.com/chinmay28/vedic-astrology.git)
#   KUNDALI_REF       branch/tag/commit       (default: main)
#   KUNDALI_USER      service system user     (default: kundali)
#   KUNDALI_PREFIX    install prefix          (default: /opt/kundali; source -> $PREFIX/src)
#   KUNDALI_DATA_DIR  database + backups dir  (default: /var/lib/kundali)
#   KUNDALI_SERVICE   systemd unit name       (default: kundali-web; change it
#                                              to run a second instance on one
#                                              host, with its own PREFIX/DATA_DIR)
#   PORT              port to listen on       (default: 8777)
#   HOST              bind address            (default: 0.0.0.0)
#   PYTHON            interpreter to build on (default: python3; needs >= 3.10)
#   BACKUP_KEEP       pre-upgrade backups kept (default: 10)
#
set -euo pipefail
umask 022      # the service user must be able to read the code it runs

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
  C_BLUE=$'\033[1;34m'; C_GREEN=$'\033[1;32m'; C_YELLOW=$'\033[1;33m'
  C_RED=$'\033[1;31m'; C_DIM=$'\033[2m'; C_OFF=$'\033[0m'
else
  C_BLUE=''; C_GREEN=''; C_YELLOW=''; C_RED=''; C_DIM=''; C_OFF=''
fi
log()  { printf '%s==>%s %s\n' "$C_BLUE" "$C_OFF" "$*"; }
ok()   { printf '%s ok %s %s\n' "$C_GREEN" "$C_OFF" "$*"; }
warn() { printf '%swarn%s %s\n' "$C_YELLOW" "$C_OFF" "$*" >&2; }
die()  { printf '%serr %s %s\n' "$C_RED" "$C_OFF" "$*" >&2; exit 1; }
step() { printf '\n%s%s%s\n' "$C_DIM" "$*" "$C_OFF"; }

# ---------------------------------------------------------------------------
# Must be root (system-wide service + dedicated user)
# ---------------------------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
  die "Run as root: curl -fsSL .../install-systemd.sh | sudo bash   (or: sudo ./scripts/install-systemd.sh)"
fi
command -v systemctl >/dev/null 2>&1 || die "systemd is required (no systemctl found)."

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
KUNDALI_REPO="${KUNDALI_REPO:-https://github.com/chinmay28/vedic-astrology.git}"
KUNDALI_REF="${KUNDALI_REF:-main}"
SVC_USER="${KUNDALI_USER:-kundali}"
PREFIX="${KUNDALI_PREFIX:-/opt/kundali}"
DATA_DIR="${KUNDALI_DATA_DIR:-/var/lib/kundali}"
PORT="${PORT:-8777}"
HOST="${HOST:-0.0.0.0}"
PYTHON="${PYTHON:-python3}"
BACKUP_KEEP="${BACKUP_KEEP:-10}"

SRC_DIR="$PREFIX/src"
VENV="$PREFIX/venv"                    # symlink to the live build below
VENVS_DIR="$PREFIX/venvs"
NEW_VENV="$VENVS_DIR/build-$(date +%Y%m%d-%H%M%S)-$$"
PREV_VENV=""                           # resolved in step 6, before the flip
DB_PATH="$DATA_DIR/kundali.sqlite"
BACKUP_DIR="$DATA_DIR/backups"
SERVICE_NAME="${KUNDALI_SERVICE:-kundali-web}"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
PY_MIN_MINOR=10        # pyproject requires-python = ">=3.10"

# The source tree is installed and updated as root but read by the service
# user, so git's "dubious ownership" guard can trip on an existing checkout
# (including one an earlier install chowned). Scope the exception to this tree.
git_src() { git -C "$SRC_DIR" -c safe.directory="$SRC_DIR" "$@"; }

# If this script is run from inside an existing checkout
# (sudo ./scripts/quickstart.sh) rather than piped from curl, install that
# checkout instead of cloning a second copy.
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd)"
LOCAL_CHECKOUT=""
if git -C "$SELF_DIR" rev-parse --show-toplevel >/dev/null 2>&1; then
  top="$(git -C "$SELF_DIR" rev-parse --show-toplevel)"
  if grep -q '^name = "kundali-report"' "$top/pyproject.toml" 2>/dev/null; then
    LOCAL_CHECKOUT="$top"
    SRC_DIR="$top"     # install from where the user already cloned
  fi
fi

log "kundali-web quick start"
printf '  %-10s %s\n' "source"   "$SRC_DIR$( [ -n "$LOCAL_CHECKOUT" ] && echo " (existing checkout)" )"
printf '  %-10s %s\n' "venv"     "$VENV"
printf '  %-10s %s\n' "data"     "$DATA_DIR"
printf '  %-10s %s\n' "database" "$DB_PATH"
printf '  %-10s %s\n' "service"  "${SERVICE_NAME}.service (user: $SVC_USER)"
printf '  %-10s %s\n' "listen"   "http://$HOST:$PORT"

# ---------------------------------------------------------------------------
# 1. Prerequisites: git, curl, Python >= 3.10 with venv, and libcairo
#    (cairosvg rasterises the chart diagrams and the PWA icons).
# ---------------------------------------------------------------------------
step "[1/7] Prerequisites"

APT=0; command -v apt-get >/dev/null 2>&1 && APT=1
APT_UPDATED=0
apt_install() {
  [ "$APT" -eq 1 ] || return 1
  if [ "$APT_UPDATED" -eq 0 ]; then apt-get update -y >/dev/null; APT_UPDATED=1; fi
  DEBIAN_FRONTEND=noninteractive apt-get install -y "$@" >/dev/null
}
ensure_cmd() {          # ensure_cmd <command> <apt package>
  command -v "$1" >/dev/null 2>&1 && return 0
  log "installing $2…"
  apt_install "$2" || die "'$1' is missing and apt-get is unavailable. Install it and re-run."
}
ensure_cmd curl curl
ensure_cmd git git
ok "git $(git --version | awk '{print $3}'), curl present"

command -v "$PYTHON" >/dev/null 2>&1 || ensure_cmd "$PYTHON" python3
py_minor="$("$PYTHON" -c 'import sys; print(sys.version_info[1])' 2>/dev/null || echo 0)"
py_major="$("$PYTHON" -c 'import sys; print(sys.version_info[0])' 2>/dev/null || echo 0)"
if [ "${py_major:-0}" -ne 3 ] || [ "${py_minor:-0}" -lt "$PY_MIN_MINOR" ]; then
  die "Python >= 3.$PY_MIN_MINOR is required (found $("$PYTHON" -V 2>&1)). Install a newer python3 and re-run, or set PYTHON=/path/to/python3.x"
fi
ok "$("$PYTHON" -V 2>&1)"

if ! "$PYTHON" -c 'import venv, ensurepip' >/dev/null 2>&1; then
  log "installing the venv module…"
  apt_install "python3-venv" \
    || apt_install "python$("$PYTHON" -c 'import sys;print("%d.%d"%sys.version_info[:2])')-venv" \
    || die "Python's venv module is missing. Install python3-venv and re-run."
fi
ok "venv module present"

# cairosvg dlopen()s libcairo at import time; without it the service starts and
# then fails on the first diagram.
if ! ldconfig -p 2>/dev/null | grep -q 'libcairo\.so'; then
  log "installing libcairo2 (needed by cairosvg)…"
  apt_install libcairo2 \
    || warn "could not install libcairo2 automatically - install the cairo library if diagrams fail."
fi
ok "cairo present"

# ---------------------------------------------------------------------------
# 2. Dedicated system user (home = data dir, no login shell)
# ---------------------------------------------------------------------------
step "[2/7] Service user '$SVC_USER'"
if id -u "$SVC_USER" >/dev/null 2>&1; then
  ok "user '$SVC_USER' already exists"
else
  nologin="$(command -v nologin || echo /usr/sbin/nologin)"
  useradd --system --home-dir "$DATA_DIR" --create-home --shell "$nologin" "$SVC_USER"
  ok "created system user '$SVC_USER'"
fi

# ---------------------------------------------------------------------------
# 3. Source tree. The data directory lives elsewhere and is never touched here.
# ---------------------------------------------------------------------------
step "[3/7] Source at $SRC_DIR"

# Detect an upgrade BEFORE changing anything: it decides whether we snapshot
# the database and whether a failed health check should roll back.
UPGRADE=0
{ [ -f "$DB_PATH" ] || [ -f "$UNIT_PATH" ]; } && UPGRADE=1

PREV_SHA=""
if [ -n "$LOCAL_CHECKOUT" ]; then
  warn "installing your existing checkout in place (no git fetch)."
  PREV_SHA="$(git_src rev-parse HEAD 2>/dev/null || true)"
  ok "source at ${PREV_SHA:0:12}"
elif [ -d "$SRC_DIR/.git" ]; then
  PREV_SHA="$(git_src rev-parse HEAD 2>/dev/null || true)"
  log "updating to $KUNDALI_REF…"
  git_src fetch --filter=blob:none origin "$KUNDALI_REF" \
    || git_src fetch origin "$KUNDALI_REF" \
    || die "could not fetch '$KUNDALI_REF' from origin in $SRC_DIR - the service is still running the old version."
  git_src checkout -q -B deploy FETCH_HEAD \
    || die "could not check out the fetched ref in $SRC_DIR - the service is still running the old version."
  ok "updated $( [ -n "$PREV_SHA" ] && echo "${PREV_SHA:0:12} -> " )$(git_src rev-parse --short HEAD)"
else
  log "cloning $KUNDALI_REPO (ref: $KUNDALI_REF)…"
  install -d -m 755 "$PREFIX"
  git clone --filter=blob:none --branch "$KUNDALI_REF" "$KUNDALI_REPO" "$SRC_DIR" \
    || git clone --branch "$KUNDALI_REF" "$KUNDALI_REPO" "$SRC_DIR" \
    || git clone "$KUNDALI_REPO" "$SRC_DIR"
  ok "cloned to $SRC_DIR"
fi
[ -f "$SRC_DIR/pyproject.toml" ] || die "no pyproject.toml at $SRC_DIR - checkout failed?"

# ---------------------------------------------------------------------------
# 4. Build the new virtualenv beside the running one, so a failed install
#    leaves the live service untouched.
# ---------------------------------------------------------------------------
step "[4/7] Virtualenv (pip install into $NEW_VENV)"

build_venv() {                      # build_venv <target-dir>
  local target="$1"
  rm -rf "$target"
  "$PYTHON" -m venv "$target"
  "$target/bin/python" -m pip install --quiet --upgrade pip wheel
  # pyswisseph is a C extension: if no wheel matches this platform, pip needs a
  # compiler and Python headers. Install them and retry once before giving up.
  if ! "$target/bin/python" -m pip install --quiet "$SRC_DIR"; then
    warn "pip install failed - installing build tools and retrying once…"
    apt_install build-essential "python$("$PYTHON" -c 'import sys;print("%d.%d"%sys.version_info[:2])')-dev" \
      || apt_install build-essential python3-dev \
      || true
    "$target/bin/python" -m pip install --quiet "$SRC_DIR" \
      || die "pip install failed. Full output: $target/bin/python -m pip install '$SRC_DIR'"
  fi
  [ -x "$target/bin/kundali-web" ] || die "install produced no kundali-web entry point"
  # Import once as a smoke test: this is where a missing libcairo or a broken
  # pyswisseph wheel surfaces, while the old version is still serving.
  "$target/bin/python" -c 'import kundali.webapp.server' \
    || die "the new install cannot be imported - leaving the running service alone."
}

install -d -m 755 "$PREFIX" "$VENVS_DIR"
build_venv "$NEW_VENV"
ok "installed $("$NEW_VENV/bin/python" -c 'import kundali; print("kundali", kundali.__version__)')"

# ---------------------------------------------------------------------------
# 5. Data dir + pre-upgrade database snapshot
# ---------------------------------------------------------------------------
step "[5/7] Data directory + backup"
install -d -o "$SVC_USER" -g "$SVC_USER" -m 750 "$DATA_DIR" "$BACKUP_DIR"
ok "data dir ready ($DATA_DIR, owned by $SVC_USER)"

stop_service()  { systemctl stop  "${SERVICE_NAME}.service" 2>/dev/null || true; }
start_service() { systemctl start "${SERVICE_NAME}.service"; }

SNAP=""
if [ "$UPGRADE" -eq 1 ] && [ -f "$DB_PATH" ]; then
  # Quiesce first so the snapshot is consistent (no live WAL writers).
  stop_service
  ts="$(date +%Y%m%d-%H%M%S)"
  SNAP="$BACKUP_DIR/kundali-$ts.sqlite"
  cp "$DB_PATH" "$SNAP"
  for ext in -wal -shm; do
    [ -f "${DB_PATH}${ext}" ] && cp "${DB_PATH}${ext}" "${SNAP}${ext}"
  done
  chown "$SVC_USER":"$SVC_USER" "$SNAP"* 2>/dev/null || true
  ok "database backed up -> $SNAP"
  if [ "$BACKUP_KEEP" -gt 0 ]; then
    ls -1t "$BACKUP_DIR"/kundali-*.sqlite 2>/dev/null \
      | tail -n +"$((BACKUP_KEEP + 1))" \
      | while read -r old; do rm -f "$old" "${old}-wal" "${old}-shm"; done
  fi
fi

# ---------------------------------------------------------------------------
# 6. Swap the virtualenv in, write the unit, (re)start
# ---------------------------------------------------------------------------
step "[6/7] systemd service"
stop_service                       # no-op on a first install
PREV_VENV="$(readlink -f "$VENV" 2>/dev/null || true)"
# Code stays root-owned and world-readable: the service reads and executes it
# but cannot rewrite what it runs (ProtectSystem=strict blocks /opt anyway).
ln -sfn "$NEW_VENV" "$VENV"        # the swap: one symlink, no moved venv
ok "virtualenv in place ($VENV -> $NEW_VENV)"

# Keep the live build and the one we can roll back to; drop older ones.
prune_venvs() {
  local keep_a="$1" keep_b="$2" d
  for d in "$VENVS_DIR"/*; do
    [ -d "$d" ] || continue
    [ "$d" = "$keep_a" ] || [ "$d" = "$keep_b" ] || rm -rf "$d"
  done
}
prune_venvs "$NEW_VENV" "${PREV_VENV:-}"

write_unit() {
  cat > "$UNIT_PATH" <<UNIT
[Unit]
Description=kundali-web - Jyotish chart reports (JSON API + PWA)
Documentation=https://github.com/chinmay28/vedic-astrology
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SVC_USER
Group=$SVC_USER
WorkingDirectory=$DATA_DIR
ExecStart=$VENV/bin/kundali-web --host $HOST --port $PORT --db $DB_PATH
Environment=KUNDALI_DB=$DB_PATH
Environment=PYTHONUNBUFFERED=1
Restart=on-failure
RestartSec=3

# Hardening - safe on a trusted LAN, defensive if exposure ever widens.
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
ProtectClock=true
ProtectControlGroups=true
ProtectKernelLogs=true
ProtectKernelModules=true
ProtectKernelTunables=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
RestrictNamespaces=true
RestrictSUIDSGID=true
LockPersonality=true
SystemCallArchitectures=native
UMask=0077
ReadWritePaths=$DATA_DIR

[Install]
WantedBy=multi-user.target
UNIT
}
write_unit
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service" >/dev/null 2>&1 || true
start_service
ok "service enabled and started"

# ---------------------------------------------------------------------------
# 7. Health check (with rollback on a failed upgrade)
# ---------------------------------------------------------------------------
step "[7/7] Health check"
health_url="http://127.0.0.1:$PORT/api/health"
check_health() {
  for _ in $(seq 1 30); do
    curl -fsS "$health_url" >/dev/null 2>&1 && return 0
    sleep 0.5
  done
  return 1
}
health_version() {
  curl -fsS "$health_url" 2>/dev/null \
    | sed -n 's/.*"version" *: *"\([^"]*\)".*/\1/p'
}

# Restore the pre-upgrade snapshot so the version we roll back to sees the
# database it was running against.
restore_snapshot() {
  [ -n "$SNAP" ] && [ -f "$SNAP" ] || return 0
  cp "$SNAP" "$DB_PATH"
  for ext in -wal -shm; do
    if [ -f "${SNAP}${ext}" ]; then cp "${SNAP}${ext}" "${DB_PATH}${ext}"
    else rm -f "${DB_PATH}${ext}"; fi
  done
  chown "$SVC_USER":"$SVC_USER" "$DB_PATH"* 2>/dev/null || true
}

if check_health; then
  ok "healthy ($health_url) - kundali $(health_version)"
elif [ "$UPGRADE" -eq 1 ] && [ -n "$PREV_VENV" ] && [ -d "$PREV_VENV" ]; then
  warn "the new version failed its health check."
  warn "rolling back to the previous install and restoring the pre-upgrade database…"
  stop_service
  restore_snapshot
  ln -sfn "$PREV_VENV" "$VENV"
  if [ -n "$PREV_SHA" ] && [ -z "$LOCAL_CHECKOUT" ]; then
    git_src checkout -q -B deploy "$PREV_SHA" || true
  fi
  start_service
  if check_health; then
    die "Upgrade failed its health check - rolled back to $( [ -n "$PREV_SHA" ] && echo "${PREV_SHA:0:12}" || echo "the previous install") with your data intact. Check: journalctl -u ${SERVICE_NAME} -n 80"
  fi
  die "Upgrade AND rollback both failed health checks. Data snapshot is safe at ${SNAP:-$DB_PATH}. Inspect: journalctl -u ${SERVICE_NAME} -n 80"
else
  die "Service is not healthy. Inspect logs: journalctl -u ${SERVICE_NAME} -n 80 --no-pager"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
lan_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"; [ -n "$lan_ip" ] || lan_ip="<this-host>"
verb="installed"; [ "$UPGRADE" -eq 1 ] && verb="upgraded"

cat <<DONE

${C_GREEN}kundali-web $verb and running.${C_OFF}

  Open it:     http://$lan_ip:$PORT      (http://localhost:$PORT on this machine)
  Database:    $DB_PATH
  Backups:     $BACKUP_DIR
  Virtualenv:  $VENV -> $NEW_VENV
  Source:      $SRC_DIR
  Upgrade:     re-run this script - it swaps code in, backs up data, self-heals.

  Manage the service:
    systemctl status  ${SERVICE_NAME}
    systemctl restart ${SERVICE_NAME}
    journalctl -u ${SERVICE_NAME} -f

  The CLI is installed too:
    $VENV/bin/kundali-report --date 1993-11-26 --time 22:03 --tz Asia/Kolkata \\
        --lat 14.6197 --lon 74.8354 --out /tmp/chart.pdf
${C_DIM}
  No auth by design - keep this on a trusted network (LAN / Tailscale / VPN).
  For HTTPS and "Add to Home Screen" off-LAN, front it with Tailscale Serve or
  a reverse proxy (Caddy/nginx). See DEPLOYMENT.md.${C_OFF}
DONE
