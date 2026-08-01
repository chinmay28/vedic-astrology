"""server.py - the HTTP layer: JSON API + the static PWA shell.

Contract:
    * Stdlib only (http.server + sqlite3); no web framework, no build
      step for the frontend.
    * Every /api route returns JSON; errors are {"error": "..."} with a
      4xx/5xx status and a message meant to be shown to the user.
    * Report downloads stream bytes produced by service.py, so the web
      GUI and the CLI emit byte-identical documents.

There is no authentication: like CountRoster, this is meant for a
trusted network. The default bind is 127.0.0.1.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import re
import signal
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from zoneinfo import available_timezones

from . import service
from .store import Store, default_db_path, parse_years, validate

STATIC = Path(__file__).parent / "static"
MAX_BODY = 8 << 20          # 8 MB: enough for a full backup restore
ICON_SIZES = (180, 192, 512)
DRAIN_TIMEOUT = 25          # seconds to let in-flight requests finish

# In-flight request count, so a shutdown can drain rather than cut a
# response in half. A PDF takes seconds to render; an upgrade that kills
# it mid-download hands the user a truncated file.
_inflight = 0
_inflight_cv = threading.Condition()


def drain(timeout: float = DRAIN_TIMEOUT) -> bool:
    """Wait for in-flight requests to finish. True if none are left."""
    deadline = time.monotonic() + timeout
    with _inflight_cv:
        while _inflight:
            left = deadline - time.monotonic()
            if left <= 0:
                return False
            _inflight_cv.wait(min(0.25, left))
        return True


def _json_default(o):
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    return str(o)


class Handler(BaseHTTPRequestHandler):
    server_version = "kundali-web"
    protocol_version = "HTTP/1.1"
    store: Store                      # injected on the server instance

    # ---------------------------------------------------------- plumbing
    @property
    def db(self) -> Store:
        return self.server.store       # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args) -> None:
        if self.server.quiet:          # type: ignore[attr-defined]
            return
        sys.stderr.write("%s - %s\n" % (self.log_date_time_string(),
                                        fmt % args))

    def _send(self, status: int, body: bytes, ctype: str,
              headers: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, data, status: int = 200) -> None:
        body = json.dumps(data, default=_json_default).encode()
        self._send(status, body, "application/json; charset=utf-8",
                   {"Cache-Control": "no-store"})

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message}, status)

    def _download(self, body: bytes, ctype: str, filename: str) -> None:
        self._send(200, body, ctype, {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store"})

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ValueError("request body too large")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON: {exc.msg}") from None

    # ------------------------------------------------------------ routing
    ROUTES: list[tuple[str, re.Pattern, str]] = []

    def _dispatch(self) -> None:
        global _inflight
        with _inflight_cv:
            _inflight += 1
        try:
            self._route()
        finally:
            with _inflight_cv:
                _inflight -= 1
                _inflight_cv.notify_all()

    def _route(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        self.query = parse_qs(parsed.query)
        for method, pattern, name in self.ROUTES:
            m = pattern.fullmatch(path)
            if not m:
                continue
            if method != self.command and not (
                    method == "GET" and self.command == "HEAD"):
                continue
            try:
                getattr(self, name)(*m.groups())
            except ValueError as exc:
                self._error(400, str(exc))
            except BrokenPipeError:
                pass
            except Exception as exc:                    # noqa: BLE001
                self.log_message("error on %s: %r", path, exc)
                self._error(500, f"{type(exc).__name__}: {exc}")
            return
        if path.startswith("/api/"):
            self._error(404, "no such endpoint")
        else:
            self._static("index.html")                  # SPA fallback

    do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = _dispatch

    # ------------------------------------------------------------- static
    def _static(self, name: str) -> None:
        target = (STATIC / name).resolve()
        if not str(target).startswith(str(STATIC.resolve())) \
                or not target.is_file():
            self._error(404, "not found")
            return
        ctype = (mimetypes.guess_type(target.name)[0]
                 or "application/octet-stream")
        if target.suffix == ".webmanifest":
            ctype = "application/manifest+json"
        if target.suffix in (".html", ".js", ".css", ".webmanifest", ".svg"):
            ctype += "; charset=utf-8"
        cache = "no-cache" if target.name in ("sw.js", "index.html") \
            else "max-age=300"
        self._send(200, target.read_bytes(), ctype, {"Cache-Control": cache})

    def index(self) -> None:
        self._static("index.html")

    def asset(self, name: str) -> None:
        self._static(name)

    def icon(self, size: str) -> None:
        """PWA icons, rasterised from the one SVG with cairosvg."""
        px = int(size)
        if px not in ICON_SIZES:
            self._error(404, "no such icon size")
            return
        import cairosvg
        png = cairosvg.svg2png(bytestring=(STATIC / "icon.svg").read_bytes(),
                               output_width=px, output_height=px)
        self._send(200, png, "image/png", {"Cache-Control": "max-age=86400"})

    # ---------------------------------------------------------- meta APIs
    def health(self) -> None:
        from .. import __version__
        self._json({"ok": True, "version": __version__, "db": self.db.path,
                    "charts": len(self.db.list())})

    def timezones(self) -> None:
        self._json({"timezones": sorted(available_timezones())})

    # --------------------------------------------------------- chart CRUD
    def _require(self, chart_id: str) -> dict | None:
        rec = self.db.get(int(chart_id))
        if rec is None:
            self._error(404, "no chart with that id")
        return rec

    def charts_list(self) -> None:
        self._json({"charts": self.db.list()})

    def charts_create(self) -> None:
        self._json({"chart": self.db.create(validate(self._body()))}, 201)

    def chart_get(self, chart_id: str) -> None:
        rec = self._require(chart_id)
        if rec:
            self._json({"chart": rec})

    def chart_update(self, chart_id: str) -> None:
        if self._require(chart_id) is None:
            return
        self._json({"chart": self.db.update(int(chart_id),
                                            validate(self._body()))})

    def chart_delete(self, chart_id: str) -> None:
        if self._require(chart_id) is None:
            return
        self.db.delete(int(chart_id))
        self._json({"deleted": int(chart_id)})

    # ------------------------------------------------------- computations
    def _asof(self) -> str | None:
        v = self.query.get("asof", [None])[0]
        return v or None

    def _years(self, rec: dict) -> list[int]:
        raw = self.query.get("varsha", [None])[0]
        return parse_years(raw) if raw is not None else service.years_of(rec)

    def chart_summary(self, chart_id: str) -> None:
        rec = self._require(chart_id)
        if rec:
            self._json(service.summary(rec, self._asof()))

    def preview(self) -> None:
        """Compute without saving - the 'try it' path on the form."""
        body = self._body()
        rec = validate(body)
        rec["id"] = None
        self._json(service.summary(rec, body.get("asof")))

    # ---------------------------------------------------------- downloads
    def chart_pdf(self, chart_id: str) -> None:
        rec = self._require(chart_id)
        if rec is None:
            return
        data = service.pdf_bytes(rec, self._years(rec), self._asof())
        self._download(data, "application/pdf",
                       f"kundali-{service.slug(rec['name'])}.pdf")

    def chart_html(self, chart_id: str) -> None:
        rec = self._require(chart_id)
        if rec is None:
            return
        data = service.html_bytes(rec, self._years(rec), self._asof())
        self._download(data, "text/html; charset=utf-8",
                       f"kundali-{service.slug(rec['name'])}.html")

    def chart_json(self, chart_id: str) -> None:
        rec = self._require(chart_id)
        if rec is None:
            return
        body = json.dumps(service.summary(rec, self._asof()),
                          default=_json_default, indent=2).encode()
        self._download(body, "application/json",
                       f"kundali-{service.slug(rec['name'])}.json")

    def chart_positions_csv(self, chart_id: str) -> None:
        rec = self._require(chart_id)
        if rec is None:
            return
        self._download(service.positions_csv(rec).encode(), "text/csv",
                       f"kundali-{service.slug(rec['name'])}-positions.csv")

    def chart_dasha_csv(self, chart_id: str) -> None:
        rec = self._require(chart_id)
        if rec is None:
            return
        self._download(service.dasha_csv(rec).encode(), "text/csv",
                       f"kundali-{service.slug(rec['name'])}-dasha.csv")

    # ------------------------------------------------------ backup APIs
    def export_json(self) -> None:
        body = json.dumps(self.db.export_json(), indent=2).encode()
        self._download(body, "application/json", "kundali-charts.json")

    def export_csv(self) -> None:
        self._download(self.db.export_csv().encode(), "text/csv",
                       "kundali-charts.csv")

    def export_sqlite(self) -> None:
        self._download(self.db.raw_bytes(), "application/vnd.sqlite3",
                       "kundali.sqlite")

    def import_json(self) -> None:
        self._json(self.db.import_json(self._body()))


Handler.ROUTES = [
    ("GET", re.compile(r"/"), "index"),
    ("GET", re.compile(r"/index\.html"), "index"),
    ("GET", re.compile(r"/(app\.js|app\.css|sw\.js|icon\.svg"
                       r"|manifest\.webmanifest|dev-badge\.png"
                       r"|dev-badge-full\.png)"), "asset"),
    ("GET", re.compile(r"/icons/(\d+)\.png"), "icon"),
    ("GET", re.compile(r"/api/health"), "health"),
    ("GET", re.compile(r"/api/timezones"), "timezones"),
    ("GET", re.compile(r"/api/charts"), "charts_list"),
    ("POST", re.compile(r"/api/charts"), "charts_create"),
    ("POST", re.compile(r"/api/preview"), "preview"),
    ("GET", re.compile(r"/api/charts/(\d+)"), "chart_get"),
    ("PUT", re.compile(r"/api/charts/(\d+)"), "chart_update"),
    ("DELETE", re.compile(r"/api/charts/(\d+)"), "chart_delete"),
    ("GET", re.compile(r"/api/charts/(\d+)/summary"), "chart_summary"),
    ("GET", re.compile(r"/api/charts/(\d+)/report\.pdf"), "chart_pdf"),
    ("GET", re.compile(r"/api/charts/(\d+)/report\.html"), "chart_html"),
    ("GET", re.compile(r"/api/charts/(\d+)/export\.json"), "chart_json"),
    ("GET", re.compile(r"/api/charts/(\d+)/positions\.csv"),
     "chart_positions_csv"),
    ("GET", re.compile(r"/api/charts/(\d+)/dasha\.csv"), "chart_dasha_csv"),
    ("GET", re.compile(r"/api/export/charts\.json"), "export_json"),
    ("GET", re.compile(r"/api/export/charts\.csv"), "export_csv"),
    ("GET", re.compile(r"/api/export/kundali\.sqlite"), "export_sqlite"),
    ("POST", re.compile(r"/api/import"), "import_json"),
]


def build_server(host: str, port: int, db_path: str,
                 quiet: bool = False) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    httpd.store = Store(db_path)            # type: ignore[attr-defined]
    httpd.quiet = quiet                     # type: ignore[attr-defined]
    return httpd


def _lan_hint(port: int) -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return f"http://{ip}:{port}"
    except OSError:
        return ""


def run(host: str = "127.0.0.1", port: int = 8777,
        db_path: str | None = None) -> int:
    httpd = build_server(host, port, db_path or default_db_path())
    print(f"kundali-web on http://{host}:{port}  (db: {httpd.store.path})")
    if host in ("0.0.0.0", "::"):
        hint = _lan_hint(port)
        if hint:
            print(f"reachable on this network at {hint}")
        print("no authentication - keep this on a trusted network")
    # SIGTERM is what `docker stop` and `systemctl restart` send, so an
    # upgrade must not cut a running PDF render in half: stop accepting
    # new connections, drain what is in flight, then exit cleanly.
    def _stop(signum, _frame):
        name = signal.Signals(signum).name
        print(f"\n{name}: draining in-flight requests…", flush=True)
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _stop)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:            # no handler installed (embedded use)
        pass
    finally:
        if drain():
            print("stopped cleanly")
        else:
            print(f"stopped with requests still running after "
                  f"{DRAIN_TIMEOUT}s")
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="kundali-web",
        description="Mobile-friendly web GUI for kundali reports.")
    ap.add_argument("--host", default="127.0.0.1",
                    help="bind address; 0.0.0.0 to reach it from a phone")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--db", default=None,
                    help=f"SQLite file (default: {default_db_path()})")
    args = ap.parse_args(argv)
    return run(args.host, args.port, args.db)
