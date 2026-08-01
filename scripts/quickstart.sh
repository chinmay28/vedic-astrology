#!/usr/bin/env bash
#
# kundali-web - one-command install, in Docker. Written for a Raspberry Pi
# (Raspberry Pi OS 64-bit or 32-bit) and equally happy on any Debian/Ubuntu
# host, x86 or ARM:
#
#   curl -fsSL https://raw.githubusercontent.com/chinmay28/vedic-astrology/main/scripts/quickstart.sh | sudo bash
#
# Starting from a fresh machine it installs Docker if it is missing, fetches
# the source, builds the image and starts the container. Your charts live in
# a Docker volume, so rebuilding or removing the container never touches
# them - see DEPLOYMENT.md.
#
# Re-run the same command to upgrade. It is non-disruptive and data-safe:
#
#   * If the rebuilt image is identical to the one already running, nothing
#     is stopped, restarted or backed up - the re-run is a no-op.
#   * The image is built while the old container keeps serving. A failed
#     build leaves the running version alone.
#   * The new image is smoke-tested in a throwaway container on a scratch
#     volume BEFORE the live one is touched, so an image that cannot boot
#     never causes an outage at all.
#   * Only then is the database backed up to the host (via the app's own
#     export endpoint, so the WAL is folded in; newest $BACKUP_KEEP kept)
#     and the container recreated. The old container gets SIGTERM and
#     drains its in-flight requests first, so a PDF someone is downloading
#     finishes instead of arriving truncated.
#   * The previous image is retagged :prev first, so if the new one fails
#     its health check against the real data we roll back to it and restart.
#
# The swap itself is a container recreate: expect a few seconds of downtime
# on an actual upgrade, and none when nothing changed.
#
# On a Pi, expect the first build to take a while (roughly 5-15 minutes on a
# Pi 4; longer on a Pi 3 or 32-bit OS, where pyswisseph compiles from
# source). Later runs reuse Docker's layer cache and are much quicker.
#
# Configure via environment variables (all optional):
#
#   KUNDALI_REPO     git URL to clone      (default: https://github.com/chinmay28/vedic-astrology.git)
#   KUNDALI_REF      branch/tag/commit     (default: main)
#   KUNDALI_PREFIX   where the source goes (default: /opt/kundali)
#   KUNDALI_BIND     address to publish on (default: 0.0.0.0 - reachable from
#                                           your phone; 127.0.0.1 keeps it on
#                                           this machine only)
#   PORT             port to publish       (default: 8777)
#   BACKUP_DIR       host backup directory (default: /var/lib/kundali/backups)
#   BACKUP_KEEP      backups kept          (default: 10)
#   INSTALL_DOCKER   auto | never          install Docker if missing (default: auto)
#
set -euo pipefail

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

if [ "$(id -u)" -ne 0 ]; then
  die "Run as root: curl -fsSL .../quickstart.sh | sudo bash   (or: sudo ./scripts/quickstart.sh)"
fi

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
KUNDALI_REPO="${KUNDALI_REPO:-https://github.com/chinmay28/vedic-astrology.git}"
KUNDALI_REF="${KUNDALI_REF:-main}"
PREFIX="${KUNDALI_PREFIX:-/opt/kundali}"
BIND="${KUNDALI_BIND:-0.0.0.0}"
PORT="${PORT:-8777}"
BACKUP_DIR="${BACKUP_DIR:-/var/lib/kundali/backups}"
BACKUP_KEEP="${BACKUP_KEEP:-10}"
INSTALL_DOCKER="${INSTALL_DOCKER:-auto}"

SRC_DIR="$PREFIX/src"
IMAGE="kundali-web:local"
PREV_IMAGE="kundali-web:prev"
PROJECT="kundali"                 # matches `name:` in docker-compose.yml
HEALTH_URL="http://127.0.0.1:$PORT/api/health"

# Run from inside a checkout (sudo ./scripts/quickstart.sh)? Use that tree.
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd)"
LOCAL_CHECKOUT=""
if git -C "$SELF_DIR" rev-parse --show-toplevel >/dev/null 2>&1; then
  top="$(git -C "$SELF_DIR" rev-parse --show-toplevel)"
  if grep -q '^name = "kundali-report"' "$top/pyproject.toml" 2>/dev/null; then
    LOCAL_CHECKOUT="$top"
    SRC_DIR="$top"
  fi
fi

git_src() { git -C "$SRC_DIR" -c safe.directory="$SRC_DIR" "$@"; }
compose() { docker compose -f "$SRC_DIR/docker-compose.yml" "$@"; }

log "kundali-web quick start (Docker)"
printf '  %-9s %s\n' "source"  "$SRC_DIR$( [ -n "$LOCAL_CHECKOUT" ] && echo " (existing checkout)" )"
printf '  %-9s %s\n' "data"    "docker volume ${PROJECT}_kundali-data"
printf '  %-9s %s\n' "backups" "$BACKUP_DIR"
printf '  %-9s %s\n' "listen"  "http://$BIND:$PORT"

# ---------------------------------------------------------------------------
# 1. Docker (installed here if missing) + git
# ---------------------------------------------------------------------------
step "[1/6] Prerequisites"

APT=0; command -v apt-get >/dev/null 2>&1 && APT=1
APT_UPDATED=0
apt_install() {
  [ "$APT" -eq 1 ] || return 1
  if [ "$APT_UPDATED" -eq 0 ]; then apt-get update -y >/dev/null; APT_UPDATED=1; fi
  DEBIAN_FRONTEND=noninteractive apt-get install -y "$@" >/dev/null
}
for cmd_pkg in "curl:curl" "git:git"; do
  cmd="${cmd_pkg%%:*}"; pkg="${cmd_pkg##*:}"
  command -v "$cmd" >/dev/null 2>&1 && continue
  log "installing $pkg…"
  apt_install "$pkg" || die "'$cmd' is missing and apt-get is unavailable. Install it and re-run."
done
ok "git $(git --version | awk '{print $3}'), curl present"

if ! command -v docker >/dev/null 2>&1; then
  [ "$INSTALL_DOCKER" = never ] && die "Docker is not installed. Install it (https://docs.docker.com/engine/install/) and re-run, or set INSTALL_DOCKER=auto."
  case "$(uname -m)" in
    aarch64 | arm64 | armv7l | x86_64 | amd64) ;;
    *) die "Unsupported architecture $(uname -m) for the automatic Docker install; install Docker manually and re-run." ;;
  esac
  log "installing Docker via get.docker.com ($(uname -m)) - this takes a few minutes on a Pi…"
  curl -fsSL https://get.docker.com | sh \
    || die "the Docker install script failed. Install Docker manually (https://docs.docker.com/engine/install/) and re-run."
  ok "Docker installed"
fi
systemctl enable --now docker >/dev/null 2>&1 || true
docker info >/dev/null 2>&1 \
  || die "the Docker daemon is not responding. Start it (systemctl start docker) and re-run."
ok "docker $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo present)"

if ! docker compose version >/dev/null 2>&1; then
  log "installing the Docker Compose plugin…"
  apt_install docker-compose-plugin \
    || die "'docker compose' is unavailable. Install the compose plugin and re-run."
fi
ok "compose $(docker compose version --short 2>/dev/null || echo present)"

# On a Pi the person running this is usually the one who will use it: let
# them drive Docker without sudo from now on (takes effect at next login).
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != root ]; then
  if ! id -nG "$SUDO_USER" | tr ' ' '\n' | grep -qx docker; then
    usermod -aG docker "$SUDO_USER" 2>/dev/null \
      && ok "added '$SUDO_USER' to the docker group (log out and back in to use it)"
  fi
fi

# ---------------------------------------------------------------------------
# 2. Source
# ---------------------------------------------------------------------------
step "[2/6] Source at $SRC_DIR"
UPGRADE=0
docker volume inspect "${PROJECT}_kundali-data" >/dev/null 2>&1 && UPGRADE=1

if [ -n "$LOCAL_CHECKOUT" ]; then
  warn "building your existing checkout in place (no git fetch)."
  ok "source at $(git_src rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
elif [ -d "$SRC_DIR/.git" ]; then
  log "updating to $KUNDALI_REF…"
  git_src fetch --filter=blob:none origin "$KUNDALI_REF" \
    || git_src fetch origin "$KUNDALI_REF" \
    || die "could not fetch '$KUNDALI_REF' - the running container is untouched."
  git_src checkout -q -B deploy FETCH_HEAD \
    || die "could not check out the fetched ref - the running container is untouched."
  ok "source at $(git_src rev-parse --short HEAD)"
else
  log "cloning $KUNDALI_REPO (ref: $KUNDALI_REF)…"
  install -d -m 755 "$PREFIX"
  git clone --filter=blob:none --branch "$KUNDALI_REF" "$KUNDALI_REPO" "$SRC_DIR" \
    || git clone --branch "$KUNDALI_REF" "$KUNDALI_REPO" "$SRC_DIR" \
    || git clone "$KUNDALI_REPO" "$SRC_DIR"
  ok "cloned to $SRC_DIR"
fi
[ -f "$SRC_DIR/docker-compose.yml" ] || die "no docker-compose.yml at $SRC_DIR - checkout failed?"

# Where to listen is per-host, so it lives in a .env beside the compose file
# rather than in the compose file itself.
cat > "$SRC_DIR/.env" <<ENV
# written by scripts/quickstart.sh - edit and re-run 'docker compose up -d'
KUNDALI_BIND=$BIND
KUNDALI_PORT=$PORT
ENV
ok "wrote $SRC_DIR/.env (bind $BIND, port $PORT)"

# ---------------------------------------------------------------------------
# 3. Build (the old container keeps serving meanwhile)
# ---------------------------------------------------------------------------
step "[3/6] Build the image"
ROLLBACK=0
RUNNING_IMAGE="$(docker inspect --format '{{.Image}}' kundali-web 2>/dev/null || true)"
if docker image inspect "$IMAGE" >/dev/null 2>&1; then
  docker image tag "$IMAGE" "$PREV_IMAGE" && ROLLBACK=1
fi
log "building - first time on a Pi this can take 5-15 minutes…"
compose build \
  || die "the image build failed. The running container (if any) is untouched. Re-run once the cause is fixed."
NEW_IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$IMAGE" 2>/dev/null || true)"
ok "image built"

# ---------------------------------------------------------------------------
# 4. Nothing to do? Then do nothing. Otherwise smoke-test the new image in a
#    throwaway container before the live one is touched.
# ---------------------------------------------------------------------------
step "[4/6] Pre-flight"

if [ -n "$RUNNING_IMAGE" ] && [ "$RUNNING_IMAGE" = "$NEW_IMAGE_ID" ] \
   && curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
  ok "already running this exact image and healthy - nothing to restart"
  lan_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"; [ -n "$lan_ip" ] || lan_ip="<this-host>"
  url="http://$lan_ip:$PORT"; [ "$BIND" = "127.0.0.1" ] && url="http://127.0.0.1:$PORT"
  printf '\n%skundali-web is already up to date and running.%s\n\n  Open it: %s\n\n' \
    "$C_GREEN" "$C_OFF" "$url"
  exit 0
fi

# Boot the new image against a scratch volume on a throwaway port. If it
# cannot serve, we abort here - before stopping anything the user is using.
preflight() {
  local name="kundali-preflight-$$" vol="kundali-preflight-$$" hostport ok_=0
  docker run -d --name "$name" -v "$vol:/data" -p 127.0.0.1::8777 "$IMAGE" \
    >/dev/null 2>&1 || return 1
  hostport="$(docker port "$name" 8777/tcp 2>/dev/null | head -1 | sed 's/.*://')"
  if [ -n "$hostport" ]; then
    for _ in $(seq 1 45); do
      curl -fsS "http://127.0.0.1:$hostport/api/health" >/dev/null 2>&1 \
        && { ok_=1; break; }
      sleep 1
    done
  fi
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker volume rm "$vol" >/dev/null 2>&1 || true
  [ "$ok_" -eq 1 ]
}

if preflight; then
  ok "the new image boots and serves"
else
  die "the new image failed to start in a throwaway container - NOT swapping it in. Your running app is untouched. Logs: docker logs kundali-preflight-$$ (if it survived), or re-run once fixed."
fi

# ---------------------------------------------------------------------------
# 5. Back up, then swap
# ---------------------------------------------------------------------------
step "[5/6] Backup and swap"
SNAP=""
if [ "$UPGRADE" -eq 1 ]; then
  install -d -m 750 "$BACKUP_DIR"
  ts="$(date +%Y%m%d-%H%M%S)"
  SNAP="$BACKUP_DIR/kundali-$ts.sqlite"
  # The export endpoint takes a real SQLite backup (WAL folded in); copying
  # the file out of the volume under a live writer would not.
  if curl -fsS --max-time 120 "http://127.0.0.1:$PORT/api/export/kundali.sqlite" \
       -o "$SNAP" 2>/dev/null && [ -s "$SNAP" ]; then
    ok "database backed up -> $SNAP"
  else
    rm -f "$SNAP"; SNAP=""
    warn "could not reach the running app to back up (not running?) - continuing."
  fi
  if [ -n "$SNAP" ] && [ "$BACKUP_KEEP" -gt 0 ]; then
    ls -1t "$BACKUP_DIR"/kundali-*.sqlite 2>/dev/null \
      | tail -n +"$((BACKUP_KEEP + 1))" | xargs -r rm -f
  fi
else
  ok "first install - nothing to back up yet"
fi

# The old container is sent SIGTERM and drains its in-flight requests
# (stop_grace_period in docker-compose.yml) before the new one takes over.
compose up -d --remove-orphans
ok "container swapped in"

# ---------------------------------------------------------------------------
# 6. Health check, with rollback to the previous image
# ---------------------------------------------------------------------------
step "[6/6] Health check"
check_health() {
  for _ in $(seq 1 60); do            # up to 60s: a Pi starts slowly
    curl -fsS "$HEALTH_URL" >/dev/null 2>&1 && return 0
    sleep 1
  done
  return 1
}

if check_health; then
  ok "healthy ($HEALTH_URL) - kundali $(curl -fsS "$HEALTH_URL" 2>/dev/null \
      | sed -n 's/.*"version" *: *"\([^"]*\)".*/\1/p')"
elif [ "$ROLLBACK" -eq 1 ]; then
  warn "the new image failed its health check - rolling back to the previous one…"
  docker image tag "$PREV_IMAGE" "$IMAGE"
  compose up -d --force-recreate
  if check_health; then
    die "Upgrade failed its health check - rolled back to the previous image, your data is untouched${SNAP:+ (backup at $SNAP)}. Logs: docker compose -f $SRC_DIR/docker-compose.yml logs"
  fi
  die "Upgrade AND rollback both failed health checks.${SNAP:+ Backup is safe at $SNAP.} Logs: docker compose -f $SRC_DIR/docker-compose.yml logs"
else
  die "The container is not healthy. Logs: docker compose -f $SRC_DIR/docker-compose.yml logs"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
lan_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"; [ -n "$lan_ip" ] || lan_ip="<this-host>"
verb="installed"; [ "$UPGRADE" -eq 1 ] && verb="upgraded"
url="http://$lan_ip:$PORT"
[ "$BIND" = "127.0.0.1" ] && url="http://127.0.0.1:$PORT"

cat <<DONE

${C_GREEN}kundali-web $verb and running.${C_OFF}

  Open it:     $url
  On a phone:  open that URL, then "Add to Home Screen"
  Data:        docker volume ${PROJECT}_kundali-data (survives rebuilds)
  Backups:     $BACKUP_DIR
  Upgrade:     re-run this command - it backs up first and rolls back on failure

  Manage it:
    docker compose -f $SRC_DIR/docker-compose.yml ps
    docker compose -f $SRC_DIR/docker-compose.yml logs -f
    docker compose -f $SRC_DIR/docker-compose.yml restart
${C_DIM}
  It restarts with the Pi on its own (restart: unless-stopped + Docker
  enabled at boot). No authentication by design - keep it on a trusted
  network (LAN / Tailscale / VPN). See DEPLOYMENT.md.${C_OFF}
DONE
