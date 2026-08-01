"""webapp - a mobile-first web GUI over the kundali pipeline.

Architecture (mirrors CountRoster's shape: one small server owns a
single SQLite file, every device is a client of it):

    store.py    saved charts in SQLite; stdlib sqlite3 only.
    service.py  Chart -> JSON payloads for the GUI, plus report bytes.
                Serialises all ephemeris work behind one lock, because
                Swiss Ephemeris sidereal mode is process-global state.
    server.py   stdlib ThreadingHTTPServer, JSON API + static PWA shell.
    static/     no build step: hand-written HTML/CSS/JS, service worker
                and manifest, installable on a phone home screen.

No authentication, by design: run it on a trusted network (LAN, VPN,
tailnet) and bind to 127.0.0.1 unless you mean otherwise.
"""
from .server import build_server, main, run

__all__ = ["build_server", "main", "run"]
