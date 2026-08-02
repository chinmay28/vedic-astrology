"""geocode.py - place lookup, and the timezone that comes with a place.

Contract:
    * Stdlib only, and entirely optional. Typing coordinates in by hand
      is still the documented path and still the only one the CLI has;
      this exists so that saving "Sirsi, Karnataka" does not mean
      switching to a map app first.
    * Nothing leaves the machine unless someone types a name and presses
      search, or saves a chart whose timezone is not known yet. One
      outbound GET per lookup, to `$KUNDALI_GEOCODER` (Open-Meteo's
      public GeoNames index by default). Set that variable to `off` for
      an installation that must never reach the internet - the GUI then
      asks for the coordinates and the zone, as it used to.
    * A result carries the IANA timezone as well as the coordinates,
      because a birth chart cast in the wrong zone is wrong by hours -
      which is the whole reason the timezone is inferred rather than
      typed.
    * **The zone is never guessed.** It comes from an index that knows
      the political boundary, or it is reported as unknown and asked
      for. Nearest-city-by-distance over the tz database's own
      representative points looks tempting and is wrong where it matters
      most: it puts every Indian birthplace in Asia/Colombo or
      Asia/Karachi, both half an hour out. `timezone_at()` returns None
      rather than a plausible lie.
    * Failures raise LookupError with a message meant for the user; the
      caller turns that into an HTTP error. A lookup that cannot run
      never blocks saving a place by hand.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import available_timezones

DEFAULT_ENDPOINT = "https://geocoding-api.open-meteo.com/v1/search"
# Same index, asked "which zone is this coordinate in?" - the answer is a
# real IANA name resolved against timezone boundaries, not a guess.
DEFAULT_TZ_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
SOURCE = "open-meteo (GeoNames)"
TIMEOUT = 8                 # seconds; a phone gives up long before this
MAX_RESULTS = 10
_OFF = ("off", "none", "0", "false", "disabled")


def endpoint() -> str | None:
    """The search URL, or None when lookup is switched off."""
    raw = os.environ.get("KUNDALI_GEOCODER", "").strip()
    if raw.lower() in _OFF:
        return None
    return raw or DEFAULT_ENDPOINT


def enabled() -> bool:
    return endpoint() is not None


def timezone_endpoint() -> str | None:
    """The coordinate -> zone URL, or None when it is switched off.
    `KUNDALI_GEOCODER=off` seals the whole module: an installation that
    must not reach the internet must not reach it for this either."""
    if not enabled():
        return None
    raw = os.environ.get("KUNDALI_TZ_LOOKUP", "").strip()
    if raw.lower() in _OFF:
        return None
    return raw or DEFAULT_TZ_ENDPOINT


def timezone_source() -> str | None:
    url = timezone_endpoint()
    if url is None:
        return None
    return SOURCE if url == DEFAULT_TZ_ENDPOINT else urllib.parse.urlparse(
        url).netloc or url


def source() -> str | None:
    """What to tell the user they are querying, or None when off."""
    if not enabled():
        return None
    url = endpoint()
    return SOURCE if url == DEFAULT_ENDPOINT else urllib.parse.urlparse(
        url).netloc or url


def label(hit: dict) -> str:
    """'Sirsi, Karnataka, India' - the line a person recognises."""
    parts = [hit.get("name"), hit.get("admin1"), hit.get("country")]
    seen, out = set(), []
    for part in parts:
        part = (part or "").strip()
        if part and part.lower() not in seen:
            seen.add(part.lower())
            out.append(part)
    return ", ".join(out)


def parse(payload: dict) -> list[dict]:
    """Provider JSON -> the flat rows the GUI renders. Defensive on
    purpose: an unrecognised shape yields no results, never an error."""
    rows = []
    for hit in (payload or {}).get("results") or []:
        if not isinstance(hit, dict):
            continue
        try:
            lat = float(hit["latitude"])
            lon = float(hit["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        rows.append({
            "label": label(hit),
            "name": (hit.get("name") or "").strip(),
            "admin1": (hit.get("admin1") or "").strip(),
            "country": (hit.get("country") or "").strip(),
            "lat": round(lat, 4), "lon": round(lon, 4),
            "tz": (hit.get("timezone") or "").strip(),
            "population": hit.get("population") or 0,
        })
    return rows


def _fetch(url: str) -> dict | None:
    """GET some JSON. None on any failure - callers must cope without."""
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "kundali-web (github.com/chinmay28/vedic-astrology)"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return json.loads(res.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError,
            UnicodeDecodeError, ValueError):
        return None


def timezone_at(lat: float, lon: float) -> str | None:
    """The IANA zone those coordinates sit in, or None if it cannot be
    established. Never raises, and never guesses: an unknown zone must
    surface as a question, not as a chart that is half an hour out."""
    url = timezone_endpoint()
    if url is None:
        return None
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    query = urllib.parse.urlencode({
        "latitude": round(lat, 4), "longitude": round(lon, 4),
        "timezone": "auto", "forecast_days": 1, "current": "temperature_2m"})
    payload = _fetch(f"{url}{'&' if '?' in url else '?'}{query}")
    if not isinstance(payload, dict):
        return None
    name = str(payload.get("timezone") or "").strip()
    # Only a name this machine can actually resolve is worth anything -
    # the whole point is that zoneinfo applies the historical DST rules.
    return name if name in available_timezones() else None


def search(name: str, count: int = MAX_RESULTS) -> list[dict]:
    """Look a city or town up. Raises LookupError with a message the GUI
    can show; the caller is expected to keep working without it."""
    url = endpoint()
    if url is None:
        raise LookupError("place search is switched off on this server "
                          "(KUNDALI_GEOCODER=off) - enter coordinates "
                          "by hand")
    name = (name or "").strip()
    if not name:
        raise LookupError("type a city or town name to search for")

    query = urllib.parse.urlencode({
        "name": name, "count": max(1, min(int(count), MAX_RESULTS)),
        "language": "en", "format": "json"})
    req = urllib.request.Request(
        f"{url}{'&' if '?' in url else '?'}{query}",
        headers={"Accept": "application/json",
                 "User-Agent": "kundali-web (github.com/chinmay28/"
                               "vedic-astrology)"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            payload = json.loads(res.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        raise LookupError(f"the place index answered {exc.code} - try "
                          "again, or enter coordinates by hand") from None
    except (urllib.error.URLError, OSError):
        raise LookupError("could not reach the place index (offline?) - "
                          "enter coordinates by hand") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise LookupError("the place index sent something unreadable - "
                          "enter coordinates by hand") from None
    return parse(payload)
