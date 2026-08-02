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

from kundali.webapp import geocode, service
from kundali.webapp.server import build_server
from kundali.webapp.store import (Store, parse_years, validate,
                                  validate_place)

C3 = {"name": "C3", "birth_date": "1993-11-26", "birth_time": "22:03",
      "tz": "Asia/Kolkata", "lat": 14.6197, "lon": 74.8354,
      "place": "Sirsi", "ayanamsa": "raman", "varsha_years": "2026"}
C2 = {"name": "C2", "birth_date": "2026-05-12", "birth_time": "15:26",
      "tz": "America/Los_Angeles", "lat": 37.3382, "lon": -121.8863,
      "place": "San Jose", "ayanamsa": "raman"}
P1 = {"name": "Sirsi, Karnataka, India", "lat": 14.6197, "lon": 74.8354,
      "tz": "Asia/Kolkata", "notes": "birthplace"}


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


def test_years_are_stored_space_separated():
    """The stored string goes straight back into the input, and a phone
    keypad has no comma key - so the round trip has to be typeable with
    the space bar alone. Commas still parse, for rows written before."""
    assert validate({**C3, "varsha_years": "2026 2027"})["varsha_years"] \
        == "2026 2027"
    assert validate({**C3, "varsha_years": "2027,2026"})["varsha_years"] \
        == "2026 2027"


def test_validate_place_keeps_the_timezone_optional():
    rec = validate_place({"name": "Sirsi", "lat": "14.6197", "lon": 74.8354})
    assert rec == {"name": "Sirsi", "lat": pytest.approx(14.6197),
                   "lon": pytest.approx(74.8354), "tz": "", "notes": ""}
    assert validate_place(P1)["tz"] == "Asia/Kolkata"


@pytest.mark.parametrize("bad, message", [
    ({"name": "  "}, "a place needs a name"),
    ({"name": "x" * 121}, "too long"),
    ({"lat": 91}, "lat must be between"),
    ({"lon": "west"}, "lon must be a number"),
    ({"tz": "IST"}, "IANA timezone"),
])
def test_validate_place_rejects_bad_input(bad, message):
    with pytest.raises(ValueError) as err:
        validate_place({**P1, **bad})
    assert message in str(err.value)


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
    counts = {"added": 0, "updated": 1, "places_added": 0,
              "places_updated": 0}
    assert store.import_json(backup) == counts
    assert store.import_json(backup) == counts
    assert len(store.list()) == 1

    store.import_json({"charts": [{**C3, "name": "Someone else"}]})
    assert len(store.list()) == 2


def test_place_crud(store):
    rec = store.create_place(validate_place(P1))
    assert rec["id"] and rec["tz"] == "Asia/Kolkata"
    assert [p["name"] for p in store.places()] == [P1["name"]]

    store.update_place(rec["id"], validate_place({**P1, "name": "Sirsi"}))
    assert store.place(rec["id"])["name"] == "Sirsi"

    assert store.delete_place(rec["id"]) is True
    assert store.place(rec["id"]) is None
    assert store.delete_place(rec["id"]) is False


def test_places_survive_a_backup_round_trip(store):
    store.create(validate(C3))
    store.create_place(validate_place(P1))
    backup = store.export_json()
    assert backup["version"] == 2 and len(backup["places"]) == 1

    assert store.import_json(backup) == {
        "added": 0, "updated": 1, "places_added": 0, "places_updated": 1}
    assert len(store.places()) == 1                 # matched, not duplicated

    store.import_json({"charts": [], "places": [{**P1, "name": "Elsewhere"}]})
    assert len(store.places()) == 2


def test_a_version_1_backup_still_restores(store):
    """Backups written before places existed have no 'places' key."""
    assert store.import_json({"format": "kundali-charts", "version": 1,
                              "charts": [C3]})["added"] == 1
    assert store.places() == []


def test_exports_are_open_formats(store):
    store.create(validate(C3))
    store.create_place(validate_place(P1))
    assert store.export_csv().splitlines()[0].startswith("id,name,birth_date")
    assert store.export_places_csv().splitlines()[0] == (
        "id,name,lat,lon,tz,notes,created_at,updated_at")
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


# ------------------------------------------------------- place lookup

SAMPLE_HITS = {"results": [
    {"id": 1, "name": "Sirsi", "latitude": 14.62072, "longitude": 74.83554,
     "country": "India", "admin1": "Karnataka", "timezone": "Asia/Kolkata",
     "population": 60468},
    {"id": 2, "name": "Sirsi", "latitude": 27.17, "longitude": 78.65,
     "country": "India", "admin1": "Uttar Pradesh",
     "timezone": "Asia/Kolkata"},
    {"id": 3, "name": "Broken", "latitude": "nope", "longitude": 1},
]}


def test_geocode_parses_hits_and_drops_unusable_ones():
    rows = geocode.parse(SAMPLE_HITS)
    assert [r["label"] for r in rows] == ["Sirsi, Karnataka, India",
                                          "Sirsi, Uttar Pradesh, India"]
    assert rows[0] == {"label": "Sirsi, Karnataka, India", "name": "Sirsi",
                       "admin1": "Karnataka", "country": "India",
                       "lat": 14.6207, "lon": 74.8355, "tz": "Asia/Kolkata",
                       "population": 60468}


@pytest.mark.parametrize("payload", [{}, {"results": None}, {"results": []},
                                     {"results": ["nonsense"]},
                                     {"results": [{"name": "No coords"}]}])
def test_geocode_never_raises_on_an_odd_payload(payload):
    assert geocode.parse(payload) == []


def test_geocode_label_does_not_repeat_itself():
    assert geocode.label({"name": "Singapore", "admin1": "Singapore",
                          "country": "Singapore"}) == "Singapore"


def test_geocode_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("KUNDALI_GEOCODER", "off")
    assert geocode.enabled() is False and geocode.source() is None
    with pytest.raises(LookupError) as err:
        geocode.search("Sirsi")
    assert "switched off" in str(err.value)


def test_geocode_endpoint_is_configurable(monkeypatch):
    monkeypatch.delenv("KUNDALI_GEOCODER", raising=False)
    assert geocode.endpoint() == geocode.DEFAULT_ENDPOINT
    assert geocode.source() == geocode.SOURCE
    monkeypatch.setenv("KUNDALI_GEOCODER", "https://gazetteer.example/search")
    assert geocode.source() == "gazetteer.example"


def test_geocode_reports_an_unreachable_index_as_a_message(monkeypatch):
    monkeypatch.setenv("KUNDALI_GEOCODER", "http://127.0.0.1:1/search")
    with pytest.raises(LookupError) as err:
        geocode.search("Sirsi")
    assert "coordinates by hand" in str(err.value)


# ---------------------------------------------------- timezone inference

@pytest.fixture()
def tz_index(monkeypatch):
    """A stand-in for the coordinate -> zone endpoint. `answer` is what
    it will claim the zone is."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    state = {"answer": "Asia/Kolkata"}

    class Stub(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"timezone": state["answer"]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setenv("KUNDALI_GEOCODER", "http://127.0.0.1:1/search")
    monkeypatch.setenv(
        "KUNDALI_TZ_LOOKUP",
        f"http://127.0.0.1:{httpd.server_address[1]}/v1/forecast")
    yield state
    httpd.shutdown()
    httpd.server_close()


def test_timezone_comes_from_the_index(tz_index):
    assert geocode.timezone_at(14.6197, 74.8354) == "Asia/Kolkata"
    assert geocode.timezone_source() in geocode.timezone_endpoint()


def test_an_unresolvable_zone_name_is_refused(tz_index):
    """Only a name this machine can resolve is worth anything - zoneinfo
    is what applies the historical DST rules."""
    tz_index["answer"] = "Mars/Olympus_Mons"
    assert geocode.timezone_at(14.6197, 74.8354) is None
    tz_index["answer"] = ""
    assert geocode.timezone_at(14.6197, 74.8354) is None


def test_timezone_lookup_never_raises(monkeypatch):
    monkeypatch.setenv("KUNDALI_GEOCODER", "http://127.0.0.1:1/search")
    monkeypatch.setenv("KUNDALI_TZ_LOOKUP", "http://127.0.0.1:1/forecast")
    assert geocode.timezone_at(14.6197, 74.8354) is None      # unreachable
    assert geocode.timezone_at("north", 74.8354) is None      # not a number
    assert geocode.timezone_at(999, 74.8354) is None          # off the globe


def test_sealing_the_geocoder_seals_the_timezone_lookup_too(monkeypatch):
    monkeypatch.setenv("KUNDALI_GEOCODER", "off")
    monkeypatch.delenv("KUNDALI_TZ_LOOKUP", raising=False)
    assert geocode.timezone_endpoint() is None
    assert geocode.timezone_source() is None
    assert geocode.timezone_at(14.6197, 74.8354) is None


def test_the_zone_is_never_guessed_from_distance():
    """The tempting offline shortcut - nearest representative city in the
    tz database - puts every Indian birthplace half an hour out. Nothing
    in here may fall back to it."""
    src = pathlib.Path(geocode.__file__).read_text()
    assert "zone1970" not in src and "zone.tab" not in src


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
    for path, needle in [("/", b"<title>Janma Kundali</title>"),
                         ("/app.js", b"service"),
                         ("/app.css", b"--gold"),
                         ("/manifest.webmanifest", b"standalone"),
                         ("/sw.js", b"kundali-shell")]:
        status, _, body = call(base, path)
        assert status == 200 and needle in body, path


def test_the_app_is_called_janma_kundali_everywhere_it_shows(base):
    """The display name is the app bar, the tab title and the installed
    PWA; the package, commands and database keep the kundali- prefix."""
    for path in ("/", "/manifest.webmanifest", "/app.js"):
        assert b"Jataka" not in call(base, path)[2], path
    assert b"Janma Kundali" in call(base, "/")[2]
    manifest = json.loads(call(base, "/manifest.webmanifest")[2])
    assert manifest["short_name"] == "Janma Kundali"
    assert manifest["name"].startswith("Janma Kundali")


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


def test_brand_and_developer_assets_are_served(base):
    """The header logo, the version and the developer badge come from the
    package, so a wheel or container install has them too."""
    for path, magic in [("/icon.svg", b"<svg"),
                        ("/dev-badge.png", b"\x89PNG"),
                        ("/dev-badge-full.png", b"\x89PNG")]:
        status, headers, body = call(base, path)
        assert status == 200 and body.startswith(magic), path
    shell = call(base, "/")[2]
    assert b'id="version"' in shell
    assert b"/dev-badge.png" in shell
    assert b"github.com/chinmay28" in shell
    assert json.loads(call(base, "/api/health")[2])["version"]


def test_reports_carry_the_version(tmp_path):
    from kundali import __version__
    html = service.html_bytes(C3, []).decode()
    assert f"kundali-report v{__version__}" in html
    assert "github.com/chinmay28/vedic-astrology" in html


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


def test_place_crud_over_http(base):
    status, _, body = call(base, "/api/places", "POST", P1)
    assert status == 201
    pid = json.loads(body)["place"]["id"]

    assert any(p["id"] == pid
               for p in json.loads(call(base, "/api/places")[2])["places"])
    assert json.loads(call(base, f"/api/places/{pid}")[2])["place"]["tz"] \
        == "Asia/Kolkata"

    status, _, body = call(base, f"/api/places/{pid}", "PUT",
                           {**P1, "name": "Sirsi"})
    assert status == 200 and json.loads(body)["place"]["name"] == "Sirsi"

    assert call(base, f"/api/places/{pid}", "DELETE")[0] == 200
    assert call(base, f"/api/places/{pid}")[0] == 404
    assert call(base, "/api/places/9999", "DELETE")[0] == 404


def test_place_validation_errors_reach_the_client(base):
    status, _, body = call(base, "/api/places", "POST", {**P1, "tz": "IST"})
    assert status == 400 and "IANA" in json.loads(body)["error"]


def test_health_reports_the_place_index(base, monkeypatch):
    monkeypatch.setenv("KUNDALI_GEOCODER", "off")
    health = json.loads(call(base, "/api/health")[2])
    assert health["geocoder"] is None            # the GUI hides the box
    assert "places" in health

    status, _, body = call(base, "/api/geocode?q=Sirsi")
    assert status == 503 and "by hand" in json.loads(body)["error"]

    monkeypatch.setenv("KUNDALI_GEOCODER", "http://127.0.0.1:1/search")
    health = json.loads(call(base, "/api/health")[2])
    assert health["geocoder"] == "127.0.0.1:1"
    assert call(base, "/api/geocode?q=")[0] == 400        # nothing to search
    assert call(base, "/api/geocode?q=Sirsi")[0] == 502   # index unreachable


def test_a_chart_saved_without_a_timezone_gets_one_from_its_birthplace(
        base, tz_index):
    """The zone is a fact about the coordinates, so it is not asked for."""
    payload = {k: v for k, v in C3.items() if k != "tz"}
    status, _, body = call(base, "/api/charts", "POST",
                           {**payload, "name": "Inferred"})
    assert status == 201
    rec = json.loads(body)["chart"]
    assert rec["tz"] == "Asia/Kolkata"

    # Resolved once and stored: a later lookup answering differently must
    # not silently move a saved chart.
    tz_index["answer"] = "America/Denver"
    assert json.loads(call(base, f"/api/charts/{rec['id']}")[2])["chart"] \
        ["tz"] == "Asia/Kolkata"
    call(base, f"/api/charts/{rec['id']}", "DELETE")


def test_an_explicit_timezone_is_never_overridden(base, tz_index):
    tz_index["answer"] = "America/Denver"
    status, _, body = call(base, "/api/charts", "POST",
                           {**C3, "name": "Explicit"})
    assert status == 201
    rec = json.loads(body)["chart"]
    assert rec["tz"] == "Asia/Kolkata"
    call(base, f"/api/charts/{rec['id']}", "DELETE")


def test_an_unresolvable_timezone_asks_instead_of_guessing(base, monkeypatch):
    monkeypatch.setenv("KUNDALI_GEOCODER", "off")
    payload = {k: v for k, v in C3.items() if k != "tz"}
    status, _, body = call(base, "/api/charts", "POST", payload)
    assert status == 400
    assert "timezone" in json.loads(body)["error"]

    status, _, body = call(base, "/api/preview", "POST", payload)
    assert status == 400 and "timezone" in json.loads(body)["error"]


def test_timezone_endpoint_answers_null_rather_than_erroring(base,
                                                             monkeypatch):
    monkeypatch.setenv("KUNDALI_GEOCODER", "off")
    status, _, body = call(base, "/api/timezone?lat=14.6197&lon=74.8354")
    assert status == 200
    assert json.loads(body) == {"tz": None, "source": None,
                                "reason": "timezone lookup is off on this "
                                          "server"}
    assert call(base, "/api/timezone?lat=here&lon=there")[0] == 400


def test_timezone_endpoint_resolves(base, tz_index):
    status, _, body = call(base, "/api/timezone?lat=14.6197&lon=74.8354")
    assert status == 200 and json.loads(body)["tz"] == "Asia/Kolkata"
    assert json.loads(call(base, "/api/health")[2])["tz_lookup"]


def test_backup_endpoints(base, chart_id):
    call(base, "/api/places", "POST", P1)
    status, _, body = call(base, "/api/export/charts.json")
    assert status == 200
    backup = json.loads(body)
    assert backup["format"] == "kundali-charts" and backup["version"] == 2
    assert [p["name"] for p in backup["places"]] == [P1["name"]]

    assert call(base, "/api/export/charts.csv")[2].startswith(b"id,name")
    assert call(base, "/api/export/places.csv")[2].startswith(b"id,name,lat")
    assert call(base, "/api/export/kundali.sqlite")[2].startswith(
        b"SQLite format 3")

    status, _, body = call(base, "/api/import", "POST", backup)
    assert status == 200
    assert json.loads(body) == {"added": 0, "updated": len(backup["charts"]),
                                "places_added": 0, "places_updated": 1}
