"""store.py - saved birth records in a single SQLite file.

Contract:
    * Every function takes/returns plain dicts with the field names the
      HTTP API uses; no Chart objects and no ephemeris calls here.
    * `validate()` is the only place input coercion happens - the server
      hands it raw JSON and gets back a clean record or a ValueError.
    * Connections are per-call (SQLite is happy with that) so the
      threading HTTP server needs no connection pool.
"""
from __future__ import annotations

import csv
import io
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import available_timezones

AYANAMSAS = ("raman", "lahiri")
FIELDS = ("name", "birth_date", "birth_time", "tz", "lat", "lon", "place",
          "ayanamsa", "varsha_years", "notes")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME = re.compile(r"^\d{2}:\d{2}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS charts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    birth_date   TEXT    NOT NULL,
    birth_time   TEXT    NOT NULL,
    tz           TEXT    NOT NULL,
    lat          REAL    NOT NULL,
    lon          REAL    NOT NULL,
    place        TEXT    NOT NULL DEFAULT '',
    ayanamsa     TEXT    NOT NULL DEFAULT 'raman',
    varsha_years TEXT    NOT NULL DEFAULT '',
    notes        TEXT    NOT NULL DEFAULT '',
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL
);
"""


def default_db_path() -> str:
    """XDG data dir, overridable with $KUNDALI_DB."""
    env = os.environ.get("KUNDALI_DB")
    if env:
        return env
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local"
                                                  / "share")
    return str(Path(base) / "kundali" / "kundali.sqlite")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Store:
    """CRUD over the `charts` table. One instance per server."""

    def __init__(self, path: str) -> None:
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._mem = (sqlite3.connect(path, check_same_thread=False)
                     if path == ":memory:" else None)
        with self._conn() as c:
            c.executescript(SCHEMA)
            if self._mem is None:
                c.execute("PRAGMA journal_mode=WAL")

    def _conn(self) -> sqlite3.Connection:
        if self._mem is not None:          # tests: keep the one handle
            self._mem.row_factory = sqlite3.Row
            return self._mem
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        return c

    # -- reads ---------------------------------------------------------
    def list(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM charts ORDER BY name COLLATE NOCASE").fetchall()
        return [dict(r) for r in rows]

    def get(self, chart_id: int) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM charts WHERE id=?",
                          (chart_id,)).fetchone()
        return dict(r) if r else None

    # -- writes --------------------------------------------------------
    def create(self, rec: dict) -> dict:
        now = _now()
        cols = ", ".join(FIELDS) + ", created_at, updated_at"
        marks = ", ".join("?" * (len(FIELDS) + 2))
        vals = [rec[f] for f in FIELDS] + [now, now]
        with self._conn() as c:
            cur = c.execute(f"INSERT INTO charts ({cols}) VALUES ({marks})",
                            vals)
            new_id = cur.lastrowid
        return self.get(new_id)

    def update(self, chart_id: int, rec: dict) -> dict | None:
        if self.get(chart_id) is None:
            return None
        sets = ", ".join(f"{f}=?" for f in FIELDS) + ", updated_at=?"
        vals = [rec[f] for f in FIELDS] + [_now(), chart_id]
        with self._conn() as c:
            c.execute(f"UPDATE charts SET {sets} WHERE id=?", vals)
        return self.get(chart_id)

    def delete(self, chart_id: int) -> bool:
        with self._conn() as c:
            cur = c.execute("DELETE FROM charts WHERE id=?", (chart_id,))
            return cur.rowcount > 0

    # -- backup / restore ----------------------------------------------
    def export_json(self) -> dict:
        return {"format": "kundali-charts", "version": 1,
                "exported_at": _now(), "charts": self.list()}

    def export_csv(self) -> str:
        buf = io.StringIO()
        cols = ["id", *FIELDS, "created_at", "updated_at"]
        w = csv.DictWriter(buf, fieldnames=cols)
        w.writeheader()
        for row in self.list():
            w.writerow({k: row[k] for k in cols})
        return buf.getvalue()

    def import_json(self, payload: dict) -> dict:
        """Merge a backup in. Records are matched on the birth identity
        (name + moment + place), so re-importing is idempotent."""
        charts = payload.get("charts")
        if not isinstance(charts, list):
            raise ValueError("expected an object with a 'charts' list")
        existing = {_identity(r): r["id"] for r in self.list()}
        added = updated = 0
        for raw in charts:
            rec = validate(raw)
            key = _identity(rec)
            if key in existing:
                self.update(existing[key], rec)
                updated += 1
            else:
                existing[key] = self.create(rec)["id"]
                added += 1
        return {"added": added, "updated": updated}

    def raw_bytes(self) -> bytes:
        """A consistent snapshot of the database file, WAL folded in."""
        with tempfile.TemporaryDirectory() as tmp:
            snap = str(Path(tmp) / "kundali.sqlite")
            dest = sqlite3.connect(snap)
            try:
                with self._conn() as c:
                    c.backup(dest)
            finally:
                dest.close()
            return Path(snap).read_bytes()


def _identity(rec: dict) -> tuple:
    return (rec["name"].strip().lower(), rec["birth_date"],
            rec["birth_time"], rec["tz"], round(float(rec["lat"]), 4),
            round(float(rec["lon"]), 4))


def _num(raw: dict, key: str, lo: float, hi: float) -> float:
    try:
        v = float(raw.get(key))
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be a number") from None
    if not lo <= v <= hi:
        raise ValueError(f"{key} must be between {lo} and {hi}")
    return v


def parse_years(raw) -> list[int]:
    """Accepts a list, or a comma/space separated string of years."""
    if raw in (None, "", []):
        return []
    items = raw if isinstance(raw, list) else re.split(r"[,\s]+", str(raw))
    out = []
    for item in items:
        if str(item).strip() == "":
            continue
        try:
            y = int(str(item).strip())
        except ValueError:
            raise ValueError(f"'{item}' is not a year") from None
        if not 1800 <= y <= 2200:
            raise ValueError(f"year {y} is outside 1800-2200")
        if y not in out:
            out.append(y)
    return sorted(out)


def validate(raw: dict) -> dict:
    """Raw JSON -> a storable record. Raises ValueError with a message
    meant to be shown in the GUI."""
    if not isinstance(raw, dict):
        raise ValueError("expected a JSON object")
    name = str(raw.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    if len(name) > 80:
        raise ValueError("name is too long (80 characters max)")
    date = str(raw.get("birth_date") or "").strip()
    if not _DATE.match(date):
        raise ValueError("birth_date must be YYYY-MM-DD")
    time = str(raw.get("birth_time") or "").strip()
    if not _TIME.match(time):
        raise ValueError("birth_time must be HH:MM (24-hour)")
    try:
        datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise ValueError(f"'{date} {time}' is not a real date/time") from None
    tz = str(raw.get("tz") or "").strip()
    if tz not in available_timezones():
        raise ValueError(f"'{tz}' is not an IANA timezone name "
                         "(e.g. Asia/Kolkata)")
    ayanamsa = str(raw.get("ayanamsa") or "raman").strip().lower()
    if ayanamsa not in AYANAMSAS:
        raise ValueError("ayanamsa must be raman or lahiri")
    return {
        "name": name, "birth_date": date, "birth_time": time, "tz": tz,
        "lat": _num(raw, "lat", -90, 90), "lon": _num(raw, "lon", -180, 180),
        "place": str(raw.get("place") or "").strip()[:120],
        "ayanamsa": ayanamsa,
        "varsha_years": ",".join(str(y) for y in
                                 parse_years(raw.get("varsha_years"))),
        "notes": str(raw.get("notes") or "").strip()[:2000],
    }
