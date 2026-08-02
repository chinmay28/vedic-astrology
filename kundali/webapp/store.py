"""store.py - saved birth records and saved places, in one SQLite file.

Contract:
    * Every function takes/returns plain dicts with the field names the
      HTTP API uses; no Chart objects and no ephemeris calls here.
    * `validate()` / `validate_place()` are the only places input
      coercion happens - the server hands them raw JSON and gets back a
      clean record or a ValueError.
    * Connections are per-call (SQLite is happy with that) so the
      threading HTTP server needs no connection pool.
    * Two tables, same shape of API: `list/get/create/update/delete` for
      charts, `places_*` for places. A place is only a coordinate book -
      nothing computes from it, it just fills a chart form in.
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
PLACE_FIELDS = ("name", "lat", "lon", "tz", "notes")
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

CREATE TABLE IF NOT EXISTS places (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    lat          REAL    NOT NULL,
    lon          REAL    NOT NULL,
    tz           TEXT    NOT NULL DEFAULT '',
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

    # -- rows, table-agnostic ------------------------------------------
    def _rows(self, table: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(f"SELECT * FROM {table} "
                             "ORDER BY name COLLATE NOCASE").fetchall()
        return [dict(r) for r in rows]

    def _row(self, table: str, row_id: int) -> dict | None:
        with self._conn() as c:
            r = c.execute(f"SELECT * FROM {table} WHERE id=?",
                          (row_id,)).fetchone()
        return dict(r) if r else None

    def _insert(self, table: str, fields: tuple, rec: dict) -> dict:
        now = _now()
        cols = ", ".join(fields) + ", created_at, updated_at"
        marks = ", ".join("?" * (len(fields) + 2))
        vals = [rec[f] for f in fields] + [now, now]
        with self._conn() as c:
            cur = c.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})",
                            vals)
            new_id = cur.lastrowid
        return self._row(table, new_id)

    def _update(self, table: str, fields: tuple, row_id: int,
                rec: dict) -> dict | None:
        if self._row(table, row_id) is None:
            return None
        sets = ", ".join(f"{f}=?" for f in fields) + ", updated_at=?"
        vals = [rec[f] for f in fields] + [_now(), row_id]
        with self._conn() as c:
            c.execute(f"UPDATE {table} SET {sets} WHERE id=?", vals)
        return self._row(table, row_id)

    def _remove(self, table: str, row_id: int) -> bool:
        with self._conn() as c:
            cur = c.execute(f"DELETE FROM {table} WHERE id=?", (row_id,))
            return cur.rowcount > 0

    # -- charts ---------------------------------------------------------
    def list(self) -> list[dict]:
        return self._rows("charts")

    def get(self, chart_id: int) -> dict | None:
        return self._row("charts", chart_id)

    def create(self, rec: dict) -> dict:
        return self._insert("charts", FIELDS, rec)

    def update(self, chart_id: int, rec: dict) -> dict | None:
        return self._update("charts", FIELDS, chart_id, rec)

    def delete(self, chart_id: int) -> bool:
        return self._remove("charts", chart_id)

    # -- places ---------------------------------------------------------
    def places(self) -> list[dict]:
        return self._rows("places")

    def place(self, place_id: int) -> dict | None:
        return self._row("places", place_id)

    def create_place(self, rec: dict) -> dict:
        return self._insert("places", PLACE_FIELDS, rec)

    def update_place(self, place_id: int, rec: dict) -> dict | None:
        return self._update("places", PLACE_FIELDS, place_id, rec)

    def delete_place(self, place_id: int) -> bool:
        return self._remove("places", place_id)

    # -- backup / restore ----------------------------------------------
    def export_json(self) -> dict:
        # format version 2 added `places`; a version 1 backup restores
        # fine, it simply has no places in it.
        return {"format": "kundali-charts", "version": 2,
                "exported_at": _now(), "charts": self.list(),
                "places": self.places()}

    def export_csv(self) -> str:
        return _csv(["id", *FIELDS, "created_at", "updated_at"], self.list())

    def export_places_csv(self) -> str:
        return _csv(["id", *PLACE_FIELDS, "created_at", "updated_at"],
                    self.places())

    def import_json(self, payload: dict) -> dict:
        """Merge a backup in. Records are matched on the birth identity
        (name + moment + place) and places on name + coordinates, so
        re-importing is idempotent."""
        charts = payload.get("charts")
        if not isinstance(charts, list):
            raise ValueError("expected an object with a 'charts' list")
        places = payload.get("places") or []
        if not isinstance(places, list):
            raise ValueError("'places' must be a list")

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

        known = {_place_identity(r): r["id"] for r in self.places()}
        places_added = places_updated = 0
        for raw in places:
            rec = validate_place(raw)
            key = _place_identity(rec)
            if key in known:
                self.update_place(known[key], rec)
                places_updated += 1
            else:
                known[key] = self.create_place(rec)["id"]
                places_added += 1
        return {"added": added, "updated": updated,
                "places_added": places_added,
                "places_updated": places_updated}

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


def _csv(cols: list[str], rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    for row in rows:
        w.writerow({k: row[k] for k in cols})
    return buf.getvalue()


def _identity(rec: dict) -> tuple:
    return (rec["name"].strip().lower(), rec["birth_date"],
            rec["birth_time"], rec["tz"], round(float(rec["lat"]), 4),
            round(float(rec["lon"]), 4))


def _place_identity(rec: dict) -> tuple:
    return (rec["name"].strip().lower(), round(float(rec["lat"]), 4),
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
        # Space-separated, because this string is echoed back into the
        # input and a phone keypad cannot type a comma to extend it.
        # parse_years still reads either, so older comma rows load fine.
        "varsha_years": " ".join(str(y) for y in
                                 parse_years(raw.get("varsha_years"))),
        "notes": str(raw.get("notes") or "").strip()[:2000],
    }


def validate_place(raw: dict) -> dict:
    """Raw JSON -> a storable place. The timezone is optional here (a
    coordinate is useful on its own), but if given it must be a real
    IANA name, because it is what a chart form will be filled with."""
    if not isinstance(raw, dict):
        raise ValueError("expected a JSON object")
    name = str(raw.get("name") or "").strip()
    if not name:
        raise ValueError("a place needs a name")
    if len(name) > 120:
        raise ValueError("place name is too long (120 characters max)")
    tz = str(raw.get("tz") or "").strip()
    if tz and tz not in available_timezones():
        raise ValueError(f"'{tz}' is not an IANA timezone name "
                         "(e.g. Asia/Kolkata)")
    return {"name": name, "lat": _num(raw, "lat", -90, 90),
            "lon": _num(raw, "lon", -180, 180), "tz": tz,
            "notes": str(raw.get("notes") or "").strip()[:500]}
