"""Web app tests: validation, storage, and the HTTP contract.

The payload assertions pin the same hand-validated chart the golden
suite uses (C3, Raman ayanamsa), so a drift in the ephemeris or in the
computation modules fails here too - the GUI must never show numbers
the PDF would not.
"""
import json
import pathlib
import socket
import sys
import threading
import urllib.error
import urllib.request

import pytest

from kundali.webapp import service
from kundali.webapp.server import build_server
from kundali.webapp.store import Store, parse_years, validate

C3 = {"name": "C3", "birth_date": "1993-11-26", "birth_time": "22:03",
      "tz": "Asia/Kolkata", "lat": 14.6197, "lon": 74.8354,
      "place": "Sirsi", "ayanamsa": "raman", "varsha_years": "2026"}
C2 = {"name": "C2", "birth_date": "2026-05-12", "birth_time": "15:26",
      "tz": "America/Los_Angeles", "lat": 37.3382, "lon": -121.8863,
      "place": "San Jose", "ayanamsa": "raman"}


# ----------------------------------------------------------- validation

def test_validate_accepts_a_full_record():
    rec = validate(C3)
    assert rec["lat"] == pytest.approx(14.6197)
    assert rec["varsha_years"] == "2026"
    assert set(rec) == {"name", "birth_date", "birth_time", "tz", "lat",
                        "lon", "place", "ayanamsa", "varsha_years", "notes"}


@pytest.mark.parametrize("bad, message", [
    ({"name": ""}, "name is required"),
    ({"birth_date": "26-11-1993"}, "birth_date must be"),
    ({"birth_date": "1993-02-30"}, "not a real date"),
    ({"birth_time": "10:03 pm"}, "birth_time must be"),
    ({"tz": "IST"}, "IANA timezone"),
    ({"tz": "UTC+5:30"}, "IANA timezone"),
    ({"lat": 91}, "lat must be between"),
    ({"lon": "east"}, "lon must be a number"),
    ({"ayanamsa": "krishnamurti"}, "raman or lahiri"),
    ({"varsha_years": "twenty"}, "not a year"),
])
def test_validate_rejects_bad_input(bad, message):
    with pytest.raises(ValueError) as err:
        validate({**C3, **bad})
    assert message in str(err.value)


def test_parse_years_accepts_lists_and_strings():
    assert parse_years("2026, 2027 2026") == [2026, 2027]
    assert parse_years([2028, "2026"]) == [2026, 2028]
    assert parse_years("") == []


# ---------------------------------------------------------------- store

@pytest.fixture()
def store(tmp_path):
    return Store(str(tmp_path / "test.sqlite"))


def test_store_crud(store):
    rec = store.create(validate(C3))
    assert rec["id"] and rec["created_at"]
    assert [r["name"] for r in store.list()] == ["C3"]

    store.update(rec["id"], validate({**C3, "name": "Renamed"}))
    assert store.get(rec["id"])["name"] == "Renamed"

    assert store.delete(rec["id"]) is True
    assert store.get(rec["id"]) is None
    assert store.delete(rec["id"]) is False


def test_import_is_idempotent(store):
    store.create(validate(C3))
    backup = store.export_json()
    assert store.import_json(backup) == {"added": 0, "updated": 1}
    assert store.import_json(backup) == {"added": 0, "updated": 1}
    assert len(store.list()) == 1

    store.import_json({"charts": [{**C3, "name": "Someone else"}]})
    assert len(store.list()) == 2


def test_exports_are_open_formats(store):
    store.create(validate(C3))
    assert store.export_csv().splitlines()[0].startswith("id,name,birth_date")
    assert store.raw_bytes().startswith(b"SQLite format 3")


# -------------------------------------------------------------- service

@pytest.fixture(scope="module")
def summary():
    return service.summary({**C3, "id": 1}, asof="2026-08-01")


def test_summary_matches_the_golden_chart(summary):
    ident = summary["identity"]
    assert ident["lagna"] == "Cancer"
    assert ident["rashi"] == "Aries"
    assert (ident["nakshatra"], ident["pada"]) == ("Ashwini", 4)
    moon = next(p for p in summary["positions"] if p["body"] == "Moon")
    assert moon["deg"] == pytest.approx(13.31, abs=0.05)


def test_summary_dasha_and_ashtakavarga(summary):
    md, ad, pad = summary["dasha_now"]["running"]
    assert (md["level"], md["label"]) == ("Mahadasha", "Moon")
    assert md["from"] == "02 Dec 2019" and md["to"] == "02 Dec 2029"
    assert ad["label"] == "Moon-Mercury"
    assert pad["label"].startswith("Moon-Mercury-")
    assert 0 < md["progress"] < 1
    assert sum(summary["ashtakavarga"]["sav"]) == 337
    assert len(summary["mahadashas"]) == 9


def test_summary_carries_every_gui_section(summary):
    for key in ("verification", "panchanga", "positions", "diagrams",
                "yogas", "aspects", "dasha_now", "mahadashas",
                "ashtakavarga", "navamsa", "maitri", "avastha", "bhav",
                "sadesati", "varsha", "guidance"):
        assert summary[key], f"missing section: {key}"
    assert summary["diagrams"]["north"].startswith("<svg")
    assert summary["sadesati"]["grade"] in ("mild", "moderate", "demanding")
    assert [v["year"] for v in summary["varsha"]] == [2026]


def test_summary_is_json_serialisable(summary):
    json.loads(json.dumps(summary, default=str))


def test_ayanamsa_is_not_leaked_between_charts():
    """The sidereal mode is process-global; the service must set it per
    chart or a lahiri chart would poison the next raman one."""
    raman = service.summary(C3)["identity"]
    lahiri = service.summary({**C3, "ayanamsa": "lahiri"})["identity"]
    again = service.summary(C3)["identity"]
    assert lahiri["ayanamsa_deg"] != raman["ayanamsa_deg"]
    assert again == raman


def test_dst_is_applied_in_the_web_path():
    # May in California is PDT; a naive UTC-8 shift moves the Lagna.
    assert service.summary(C2)["identity"]["lagna"] == "Virgo"


def test_csv_exports(tmp_path):
    positions = service.positions_csv(C3).splitlines()
    assert positions[0] == ("body,sign,deg,nakshatra,pada,house,dignity,"
                            "retro")
    assert positions[1].startswith("Lagna,Cancer")
    dasha = service.dasha_csv(C3).splitlines()
    assert dasha[0] == "level,lord,sub,from,to"
    assert sum(1 for r in dasha if r.startswith("Mahadasha")) == 9


# ------------------------------------------------ graceful shutdown

def test_sigterm_drains_in_flight_requests(tmp_path):
    """`docker stop` and `systemctl restart` send SIGTERM. An upgrade must
    not cut a PDF render in half and hand the user a truncated file."""
    import signal
    import subprocess
    import time
    from urllib.error import URLError

    db = tmp_path / "drain.sqlite"
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "kundali.webapp", "--host", "127.0.0.1",
         "--port", str(port), "--db", str(db)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):                       # wait for the port
            try:
                call(base, "/api/health")
                break
            except URLError:
                time.sleep(0.1)
        call(base, "/api/charts", "POST", C3)

        result = {}
        thread = threading.Thread(
            target=lambda: result.update(zip(
                ("status", "headers", "body"),
                call(base, "/api/charts/1/report.pdf?varsha=2026,2027"))))
        thread.start()
        time.sleep(1.5)                            # render is under way
        proc.send_signal(signal.SIGTERM)
        thread.join(timeout=60)

        assert result.get("status") == 200, "in-flight request was cut off"
        assert result["body"].startswith(b"%PDF")
        assert proc.wait(timeout=30) == 0
        assert "draining" in (proc.stdout.read() or "")
    finally:
        if proc.poll() is None:
            proc.kill()


# ------------------------------------------------------------ HTTP layer

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    db = tmp_path_factory.mktemp("web") / "charts.sqlite"
    httpd = build_server("127.0.0.1", 0, str(db), quiet=True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def call(base, path, method="GET", body=None):
    """-> (status, headers, bytes)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            return res.status, dict(res.headers), res.read()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read()


@pytest.fixture(scope="module")
def chart_id(base):
    status, _, body = call(base, "/api/charts", "POST", C3)
    assert status == 201
    return json.loads(body)["chart"]["id"]


def test_health_and_static_shell(base):
    status, _, body = call(base, "/api/health")
    assert status == 200 and json.loads(body)["ok"] is True
    for path, needle in [("/", b"<title>Kundali</title>"),
                         ("/app.js", b"service"),
                         ("/app.css", b"--gold"),
                         ("/manifest.webmanifest", b"standalone"),
                         ("/sw.js", b"kundali-shell")]:
        status, _, body = call(base, path)
        assert status == 200 and needle in body, path


def test_static_assets_are_packaged():
    """The container and any wheel install serve the PWA out of package
    data, not out of a source checkout - so the glob must stay declared."""
    tomllib = pytest.importorskip("tomllib")
    root = pathlib.Path(__file__).resolve().parent.parent
    cfg = tomllib.loads((root / "pyproject.toml").read_text())
    globs = cfg["tool"]["setuptools"]["package-data"]["kundali.webapp"]
    assert any(g.startswith("static/") for g in globs)
    shipped = {p.name for p in (root / "kundali" / "webapp" / "static").iterdir()}
    assert {"index.html", "app.js", "app.css", "sw.js", "icon.svg",
            "manifest.webmanifest"} <= shipped


def test_pwa_icons_are_rendered(base):
    status, headers, body = call(base, "/icons/192.png")
    assert status == 200 and headers["Content-Type"] == "image/png"
    assert body.startswith(b"\x89PNG")
    assert call(base, "/icons/17.png")[0] == 404


def test_crud_over_http(base):
    status, _, body = call(base, "/api/charts", "POST",
                           {**C3, "name": "Temporary"})
    cid = json.loads(body)["chart"]["id"]
    assert status == 201

    status, _, body = call(base, f"/api/charts/{cid}", "PUT",
                           {**C3, "name": "Temporary II"})
    assert status == 200
    assert json.loads(body)["chart"]["name"] == "Temporary II"

    assert call(base, f"/api/charts/{cid}", "DELETE")[0] == 200
    assert call(base, f"/api/charts/{cid}")[0] == 404


def test_validation_errors_reach_the_client(base):
    status, _, body = call(base, "/api/charts", "POST", {**C3, "tz": "IST"})
    assert status == 400
    assert "IANA" in json.loads(body)["error"]
    assert call(base, "/api/nope")[0] == 404


def test_summary_endpoint(base, chart_id):
    status, _, body = call(base, f"/api/charts/{chart_id}/summary"
                                 "?asof=2026-08-01")
    assert status == 200
    assert json.loads(body)["identity"]["lagna"] == "Cancer"


def test_preview_computes_without_saving(base):
    before = json.loads(call(base, "/api/charts")[2])["charts"]
    status, _, body = call(base, "/api/preview", "POST",
                           {**C3, "name": "Unsaved"})
    assert status == 200 and json.loads(body)["identity"]["lagna"] == "Cancer"
    after = json.loads(call(base, "/api/charts")[2])["charts"]
    assert len(before) == len(after)


def test_report_downloads(base, chart_id):
    status, headers, body = call(
        base, f"/api/charts/{chart_id}/report.pdf?varsha=&asof=2026-08-01")
    assert status == 200 and body.startswith(b"%PDF")
    assert 'filename="kundali-c3.pdf"' in headers["Content-Disposition"]

    status, _, body = call(base, f"/api/charts/{chart_id}/report.html?varsha=")
    assert status == 200 and b"Janma Kundali" in body

    status, _, body = call(base, f"/api/charts/{chart_id}/positions.csv")
    assert status == 200 and body.startswith(b"body,sign,deg")


def test_backup_endpoints(base, chart_id):
    status, _, body = call(base, "/api/export/charts.json")
    assert status == 200 and json.loads(body)["format"] == "kundali-charts"

    assert call(base, "/api/export/charts.csv")[2].startswith(b"id,name")
    assert call(base, "/api/export/kundali.sqlite")[2].startswith(
        b"SQLite format 3")

    status, _, body = call(base, "/api/import", "POST", json.loads(
        call(base, "/api/export/charts.json")[2]))
    assert status == 200 and json.loads(body)["added"] == 0
