"""cli.py - command-line contract.

Example:
    kundali-report --name "Chart 3" --date 1993-11-26 --time 22:03 \\
        --tz Asia/Kolkata --lat 14.6197 --lon 74.8354 \\
        --place "Sirsi, Karnataka" --ayanamsa raman \\
        --varsha 2026 2027 2028 --out chart3.pdf
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from . import ephemeris as eph
from .model import Chart
from .report import build_report


def cast_natal(name: str, date: str, time: str, tz: str, lat: float,
               lon: float, place: str, ayanamsa: str) -> Chart:
    """Cast a natal chart. The single construction path for the whole tool."""
    eph.set_ayanamsa(ayanamsa)
    dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    jd = eph.jd_from_local(dt, tz)
    return Chart(name=name, dt_local=dt, tz=tz, place=place, lat=lat,
                 lon=lon, jd=jd, asc=eph.ascendant(jd, lat, lon),
                 bodies=eph.positions(jd), ayanamsa_name=ayanamsa,
                 ayanamsa_deg=eph.ayanamsa_value(jd))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="kundali-report",
        description="Generate a Jyotish natal + varshaphala PDF report.")
    ap.add_argument("--name", default="Native")
    ap.add_argument("--date", required=True, help="Birth date, YYYY-MM-DD")
    ap.add_argument("--time", required=True, help="Local birth time, HH:MM (24h)")
    ap.add_argument("--tz", required=True,
                    help="IANA timezone, e.g. Asia/Kolkata (handles historical DST)")
    ap.add_argument("--lat", type=float, required=True, help="Latitude, +N")
    ap.add_argument("--lon", type=float, required=True, help="Longitude, +E")
    ap.add_argument("--place", default="", help="Place label for the report")
    ap.add_argument("--ayanamsa", choices=["raman", "lahiri"], default="raman")
    ap.add_argument("--varsha", nargs="*", type=int, default=None,
                    help="Calendar years for Tajika annual charts, e.g. "
                         "2026 2027. Omit the flag for the current year "
                         "and the next; pass it with no years for none.")
    ap.add_argument("--asof", default=None,
                    help="Date (YYYY-MM-DD) for the 'Dasha Now' section; "
                         "defaults to today")
    ap.add_argument("--format", choices=["pdf", "html", "both"], default="pdf")
    ap.add_argument("--out", default="kundali-report.pdf")
    args = ap.parse_args(argv)

    natal = cast_natal(args.name, args.date, args.time, args.tz, args.lat,
                       args.lon, args.place, args.ayanamsa)
    stem = args.out.rsplit(".", 1)[0]
    from datetime import datetime as _dt
    asof = (_dt.strptime(args.asof, "%Y-%m-%d") if args.asof else _dt.now())
    # No --varsha at all means "the years someone actually wants to read":
    # this one and the next. `--varsha` with no years still means none.
    varsha = args.varsha if args.varsha is not None else [asof.year,
                                                          asof.year + 1]
    if args.format in ("pdf", "both"):
        out = args.out if args.out.endswith(".pdf") else stem + ".pdf"
        print(f"Report written: {build_report(natal, varsha, out, asof=asof)}")
    if args.format in ("html", "both"):
        from .html_report import build_html
        out = args.out if (args.format == "html" and args.out.endswith(".html")) \
            else stem + ".html"
        print(f"Report written: {build_html(natal, varsha, out, asof=asof)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
