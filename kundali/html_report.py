"""html_report.py - self-contained single-file HTML report.

Contract: build_html(natal, varsha_years, out_path) -> out_path.
Reuses the exact computations and SVG geometry of the PDF path;
no external assets (SVG is inlined).
"""
from __future__ import annotations

from html import escape

from . import aspects, ephemeris as eph, yogas
from .ashtakavarga import bav, sav
from .avastha import avastha_table
from .bhav import bhav_table, shifts
from .dasha_now import (age_note, guidance_for, locate, lord_condition,
                        sandhi_note, timeline_guidance)
from .guidance import GUIDANCE
from .maitri import maitri_table
from .varga import shodashavarga_table, vimshopaka
from .panchanga import avakahada, karana, tithi, vara, yoga as sy_yoga
from .sadesati import (IMPACTS, NAVIGATION, PHASES, current_status,
                       lifetime_table, severity_profile)
from .dasha import antardashas_in_window, mahadashas
from .diagrams import north_svg, south_svg
from .model import (Chart, HOUSE_SIGNIFICATIONS, SEVEN_GRAHAS, SIGNS,
                    SIGN_LORD, dignity, nakshatra_of, sign_of)
from .varga import navamsa_chart, vargottama
from .varshaphal import cast_varsha, outlook as varsha_outlook
from .weekly import week_outlook

_CSS = """
:root{--bg:#0e1124;--ink:#ece9df;--muted:#9698bd;--gold:#c9a063;
--saffron:#e0913a;--line:#2c2f52;--panel:#13162c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font-family:Georgia,'Spectral',serif;line-height:1.5;padding:clamp(16px,4vw,44px)}
.wrap{max-width:1000px;margin:0 auto}h1{font-weight:400;color:var(--ink);
font-size:clamp(26px,5vw,40px);margin:.2em 0}h2{color:var(--gold);font-weight:400;
font-size:20px;border-bottom:1px solid var(--line);padding-bottom:4px;margin-top:36px}
h3{color:var(--saffron);font-weight:400;font-size:15px;letter-spacing:.06em}
.sub{color:var(--muted)}.sub b{color:var(--gold);font-weight:400}
table{border-collapse:collapse;width:100%;font-size:14px;margin:10px 0}
th,td{border-bottom:1px solid var(--line);padding:5px 8px;text-align:left}
th{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.12em}
td.num{font-variant-numeric:tabular-nums}
.charts{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:16px 0}
.charts svg{width:100%;height:auto;background:#fdfbf5;border-radius:6px}
.note{background:var(--panel);border:1px solid var(--line);border-radius:6px;
padding:12px 16px;font-size:13.5px;color:var(--muted);margin:12px 0}
.note b{color:var(--gold);font-weight:400}
@media(max-width:700px){.charts{grid-template-columns:1fr}}
.foot{color:#7c6b44;font-style:italic;font-size:12.5px;margin-top:30px}
"""


def _g(key: str) -> str:
    return ('<p class="note" style="font-style:italic"><b>How to read this:'
            '</b> ' + escape(GUIDANCE[key]) + "</p>")


def _rows(items: list[list[str]]) -> str:
    return "".join("<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in r)
                   + "</tr>" for r in items)


def _tbl(headers: list[str], items: list[list[str]]) -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    return f"<table><tr>{head}</tr>{_rows(items)}</table>"


def _positions(chart: Chart) -> str:
    items = []
    s, d = sign_of(chart.asc)
    nk, pd = nakshatra_of(chart.asc)
    items.append(["Lagna", SIGNS[s], f"{d:.2f}", f"{nk} {pd}", "1", "-"])
    for b in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus",
              "Saturn", "Rahu", "Ketu"]:
        s, d = sign_of(chart.bodies[b].lon)
        nk, pd = nakshatra_of(chart.bodies[b].lon)
        name = b + (" (R)" if chart.bodies[b].retro and b != "Ketu" else "")
        items.append([name, SIGNS[s], f"{d:.2f}", f"{nk} {pd}",
                      str(chart.house_of(b)), dignity(b, s)])
    return _tbl(["Graha", "Rashi", "Deg", "Nakshatra-Pada", "H", "Dignity"], items)


def build_html(natal: Chart, varsha_years: list[int], out_path: str, asof=None) -> str:
    varshas = [v for v in (cast_varsha(natal, y) for y in sorted(varsha_years))
               if v is not None]
    jd_from = varshas[0].chart.jd if varshas else natal.jd
    jd_to = (varshas[-1].chart.jd + 366) if varshas else natal.jd + 366

    h: list[str] = [f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Janma Kundali - {escape(natal.name)}</title><style>{_CSS}</style></head>
<body><div class="wrap">
<p class="sub" style="letter-spacing:.25em;text-transform:uppercase;color:var(--saffron);font-size:12px">Janma Kundali</p>
<h1>{escape(natal.name)}</h1>
<p class="sub"><b>{natal.dt_local.strftime('%d %b %Y, %H:%M')}</b> ({escape(natal.tz)})
 - {escape(natal.place)} ({natal.lat:.2f}, {natal.lon:.2f})</p>
<p class="sub">Lagna <b>{SIGNS[natal.lagna_idx]}</b> - Rashi
<b>{SIGNS[natal.sign_idx_of('Moon')]}</b>
({nakshatra_of(natal.bodies['Moon'].lon)[0]}) -
{natal.ayanamsa_name.title()} ayanamsa {natal.ayanamsa_deg:.2f}&deg;</p>"""]

    off, dst = eph.utc_offset_info(natal.dt_local, natal.tz)
    h.append("<h2>Input Verification</h2>" + _g("verification") +
             _tbl(["", ""], [
                 ["Timezone used", f"{natal.tz} -> {off}" +
                  (" (DST active)" if dst else " (no DST)")],
                 ["Birth instant (UT)", eph.jd_to_local_str(natal.jd, "UTC") + " UT"],
                 ["Node convention", "Mean node"]]))
    pk, tn, tname = tithi(natal)
    from .model import nakshatra_of as _nk
    h.append("<h2>Panchanga at Birth</h2>" + _g("panchanga") +
             _tbl(["", ""], [["Tithi", f"{pk} {tname} ({tn})"],
                             ["Vara", vara(natal)],
                             ["Nakshatra", f"{_nk(natal.bodies['Moon'].lon)[0]} "
                              f"pada {_nk(natal.bodies['Moon'].lon)[1]}"],
                             ["Yoga", sy_yoga(natal)], ["Karana", karana(natal)]]) +
             "<h3>Avakahada</h3>" + _g("avakahada") +
             _tbl(["", ""], [[k, v] for k, v in avakahada(natal).items()]))
    h.append("<h2>Graha Positions</h2>" + _g("positions") + _positions(natal))
    if natal.sandhi_flags():
        h.append(f'<div class="note"><b>Sandhi caution:</b> '
                 f'{", ".join(natal.sandhi_flags())} within 1&deg; of a sign '
                 'boundary - verify birth time before fine-grained timing.</div>')

    h.append(f'<div class="charts"><div>{north_svg(natal)}'
             '<p class="sub" style="text-align:center;font-size:12px">North Indian</p></div>'
             f'<div>{south_svg(natal)}'
             '<p class="sub" style="text-align:center;font-size:12px">South Indian</p></div></div>')
    h.append(_g("diagrams"))

    h.append("<h2>Yogas &amp; Combinations</h2>" + _g("yogas"))
    for n, d in yogas.detect(natal):
        h.append(f'<p><b style="color:var(--gold)">{escape(n)}.</b> {escape(d)}</p>')

    h.append("<h2>Graha Drishti</h2>" + _g("aspects"))
    mut = aspects.mutual_pairs(natal)
    h.append('<p class="sub"><b>Mutual:</b> ' +
             ("; ".join(f"{a} &harr; {b}" for a, b in mut) or "none") + "</p>")
    occ, inbound = natal.occupants(), aspects.inbound_by_house(natal)
    h.append(_tbl(["H", "Occupants", "Aspected by"],
                  [[str(i), ", ".join(occ[i]) or "-", ", ".join(inbound[i]) or "-"]
                   for i in range(1, 13)]))

    h.append("<h2>Vimshottari Dasha</h2>" + _g("dasha"))
    mds = mahadashas(natal.bodies["Moon"].lon, natal.jd)
    h.append(_tbl(["Mahadasha", "From", "To"],
                  [[m.lord, eph.jd_to_date_str(m.start, natal.tz),
                    eph.jd_to_date_str(m.end, natal.tz)] for m in mds]))
    ads = antardashas_in_window(natal.bodies["Moon"].lon, natal.jd, jd_from, jd_to)
    if ads:
        h.append("<h3>Antardashas in the report window</h3>")
        h.append(_tbl(["Period", "From", "To"],
                      [[f"{a.lord} / {a.sub}", eph.jd_to_date_str(a.start, natal.tz),
                        eph.jd_to_date_str(a.end, natal.tz)] for a in ads]))

    jd_asof = eph.jd_from_local(asof, natal.tz) if asof is not None else None
    h.append("<h2>Navigating Each Mahadasha</h2>" + _g("dashatimeline"))
    for g in timeline_guidance(natal, jd_asof):
        meta = [f"House {g['house']}", g["sign"]]
        if g["dignity"] != "-":
            meta.append(g["dignity"])
        if g["score"]:
            meta.append(f"Vimshopaka {g['score']}/20")
        h.append(f"<h3>{escape(g['lord'])} Mahadasha - {escape(g['from'])} "
                 f"to {escape(g['to'])}"
                 + (" &middot; running" if g["status"] == "running" else "")
                 + "</h3>"
                 + '<p class="sub">'
                 + " &middot; ".join(escape(m) for m in meta)
                 + f" &mdash; {escape(g['timing'])}</p>"
                 + f"<p>{escape(g['text'])}</p>")

    if asof is not None:
        w = week_outlook(natal, asof)
        h.append(f"<h2>The Week Ahead - {escape(w['label'])}</h2>"
                 + _g("week")
                 + f"<p>{escape(w['headline'])}</p>"
                 + f'<p class="sub">{escape(w["dasha"]["text"])}</p>')
        for c in w["dasha"]["changes"]:
            h.append('<div class="note">' + escape(c["date"]) + ": "
                     + escape(c["what"]) + ".</div>")
        h.append("<h3>Day by day (the transit Moon)</h3>")
        h.append(_tbl(["Day", "Moon in", "From Moon", "Grade",
                       "What it carries"],
                      [[f"{d['day'][:3]} {d['date']}", d["moon_sign"],
                        str(d["from_moon"]), d["grade"], d["note"]]
                       for d in w["days"]]))
        for title, items in (("What to do with it", w["suggestions"]),
                             ("Lean into", w["themes"]),
                             ("Hold lightly", w["cautions"])):
            h.append(f"<h3>{title}</h3><ul>"
                     + "".join(f"<li>{escape(x)}</li>" for x in items)
                     + "</ul>")
        h.append("<h3>Transits this week</h3>")
        h.append(_tbl(["Graha", "Sign", "From Moon", "From Lagna", "SAV",
                       "Reading"],
                      [[t["body"] + (" (R)" if t["retro"] else ""),
                        t["sign"], str(t["from_moon"]), str(t["from_lagna"]),
                        str(t["sav"]),
                        t["grade"] + (f"; {t['ingress']}" if t["ingress"]
                                      else "")]
                       for t in w["transits"]]))

        md, ad, pad, next_ad, next_md = locate(natal, jd_asof)
        vim = vimshopaka(natal)
        h.append("<h2>Dasha Now &amp; Next</h2>" + _g("dashanow"))
        an = age_note(natal, jd_asof)
        if an:
            h.append('<div class="note">' + escape(an) + "</div>")
        h.append(_tbl(["Level", "Period", "From", "To"], [
            ["Mahadasha", md.lord, eph.jd_to_date_str(md.start, natal.tz),
             eph.jd_to_date_str(md.end, natal.tz)],
            ["Antardasha", f"{md.lord} / {ad.sub}",
             eph.jd_to_date_str(ad.start, natal.tz),
             eph.jd_to_date_str(ad.end, natal.tz)],
            ["Pratyantar", f"{pad[0]} / {pad[1]} / {pad[2]}",
             eph.jd_to_date_str(pad[3], natal.tz),
             eph.jd_to_date_str(pad[4], natal.tz)],
            ["Next AD", f"{next_ad.lord} / {next_ad.sub}",
             eph.jd_to_date_str(next_ad.start, natal.tz),
             eph.jd_to_date_str(next_ad.end, natal.tz)],
            ["Next MD", next_md.lord,
             eph.jd_to_date_str(next_md.start, natal.tz),
             eph.jd_to_date_str(next_md.end, natal.tz)]]))
        for role, lord in (("era (Mahadasha)", md.lord),
                           ("chapter (Antardasha)", ad.sub),
                           ("next chapter", next_ad.sub)):
            h.append(f"<h3>Navigating the {escape(role)}</h3><p>"
                     + escape(guidance_for(natal,
                                           lord_condition(natal, lord, vim),
                                           role)) + "</p>")
        note = sandhi_note(md, ad, jd_asof, natal.tz)
        if note:
            h.append('<div class="note">' + escape(note) + "</div>")

    h.append("<h2>Shodashavarga &amp; Vimshopaka</h2>" + _g("shodashavarga"))
    sv = shodashavarga_table(natal)
    h.append(_tbl(sv[0], sv[1:]))
    vim2 = vimshopaka(natal)
    h.append(_tbl(["Vimshopaka /20"] + list(vim2),
                  [["score"] + [str(v) for v in vim2.values()]]))
    h.append("<h2>Panchadha Maitri</h2>" + _g("maitri"))
    mt = maitri_table(natal)
    h.append(_tbl(mt[0], mt[1:]))
    h.append("<h2>Avasthas</h2>" + _g("avasthas"))
    av = avastha_table(natal)
    h.append(_tbl(av[0], av[1:]))
    h.append("<h2>Bhav Chalit</h2>" + _g("bhav"))
    bt = bhav_table(natal)
    h.append(_tbl(bt[0], bt[1:]))
    sh = shifts(natal)
    h.append('<p class="sub">' + (("House shifts vs whole-sign: " +
              "; ".join(f"{p}: H{a} &rarr; H{b}" for p, a, b in sh)) if sh
              else "No planet shifts house between the two systems.") + "</p>")

    d9 = navamsa_chart(natal)
    h.append("<h2>Navamsa (D-9)</h2>" + _g("d9"))
    vg = vargottama(natal)
    if vg:
        h.append(f'<p class="sub"><b>Vargottama:</b> {", ".join(vg)} '
                 "(same sign in D-1 and D-9 - strengthened).</p>")
    h.append(_tbl(["Graha", "D-9 Rashi", "D-9 House", "D-9 Dignity"],
                  [[b, SIGNS[d9.sign_idx_of(b)], str(d9.house_of(b)),
                    dignity(b, d9.sign_idx_of(b))]
                   for b in ["Sun", "Moon", "Mars", "Mercury", "Jupiter",
                             "Venus", "Saturn", "Rahu", "Ketu"]]))
    h.append(f'<div class="charts"><div>{north_svg(d9)}'
             '<p class="sub" style="text-align:center;font-size:12px">D-9 North Indian</p></div>'
             f'<div>{south_svg(d9)}'
             '<p class="sub" style="text-align:center;font-size:12px">D-9 South Indian</p></div></div>')

    h.append("<h2>Ashtakavarga</h2>" + _g("ashtakavarga"))
    savv = sav(natal)
    h.append(_tbl(["", *SIGNS],
                  [["SAV", *map(str, savv)]] +
                  [[p, *map(str, bav(natal, p))] for p in SEVEN_GRAHAS]))
    h.append('<div class="note">SAV total 337 by construction. Signs with '
             '30+ bindus are strong ground for transits; 24 or fewer, thin '
             'ground - weigh Saturn/Rahu transits through low-SAV signs '
             'more heavily.</div>')

    h.append("<h2>Houses</h2>" + _g("houses"))
    h.append(_tbl(["H", "Sign", "Occupants", "Lord &rarr; H", "Signifies"],
                  [[str(i), SIGNS[(natal.lagna_idx + i - 1) % 12],
                    ", ".join(occ[i]) or "-",
                    f"{SIGN_LORD[(natal.lagna_idx + i - 1) % 12]} -> "
                    f"{natal.house_of(SIGN_LORD[(natal.lagna_idx + i - 1) % 12])}",
                    f"{HOUSE_SIGNIFICATIONS[i][0]}: {HOUSE_SIGNIFICATIONS[i][1]}"]
                   for i in range(1, 13)]))

    h.append("<h2>Sade Sati &amp; Saturn's Sensitive Transits</h2>" + _g("sadesati"))
    grade, factors = severity_profile(natal)
    h.append(f"<h3>How it tends to run for this chart: {grade.upper()}</h3>")
    h.append(_tbl(["Factor", "Finding"], [list(f) for f in factors]))
    if asof is not None:
        jd_asof2 = eph.jd_from_local(asof, natal.tz)
        active, nxt = current_status(natal, jd_asof2)
        if active:
            s0, e0, sg, off = active
            h.append(f"<p><b>Current:</b> {escape(PHASES[off])}, Saturn in "
                     f"{SIGNS[sg]}, {eph.jd_to_date_str(s0, natal.tz)} - "
                     f"{eph.jd_to_date_str(e0, natal.tz)}.</p><p>"
                     + escape(IMPACTS[off]) + "</p>")
        if nxt:
            s1, e1, sg1, off1 = nxt
            h.append(f"<p><b>Next:</b> {escape(PHASES[off1])} ({SIGNS[sg1]}), "
                     f"{eph.jd_to_date_str(s1, natal.tz)} - "
                     f"{eph.jd_to_date_str(e1, natal.tz)}.</p>")
    h.append('<div class="note">' + escape(NAVIGATION) + "</div>")
    h.append(_tbl(["From", "To", "Saturn in", "Phase", "Murti"],
                  [list(r) for r in lifetime_table(natal)]))
    if varshas:
        h.append(_g("varshaphal"))
    for v in varshas:
        h.append(f"<h2>Varshaphala - Age {v.age} "
                 f"({eph.jd_to_date_str(v.chart.jd, natal.tz)})</h2>")
        h.append(_tbl(["", ""], [
            ["Pravesh", eph.jd_to_local_str(v.chart.jd, natal.tz)],
            ["Varsha Lagna", f"{SIGNS[v.chart.lagna_idx]} "
             f"(natal house {v.natal_house_rising} rising)"],
            ["Muntha", f"{SIGNS[v.muntha_sign]} in house {v.muntha_house} "
             f"- {v.grade}; lord {v.muntha_lord}"],
            ["Year-lord candidates",
             "; ".join(f"{r}: {p}" for r, p in v.candidates)]]))
        o = varsha_outlook(natal, v)
        h.append(f"<h3>The year's outlook</h3><p>{escape(o['text'])}</p>")
        for title, items in (("Themes", o["themes"]),
                             ("Suggestions", o["suggestions"])):
            h.append(f"<h3>{title}</h3><ul>"
                     + "".join(f"<li>{escape(x)}</li>" for x in items)
                     + "</ul>")
        h.append("<h3>Mudda dasha - the year month by month</h3>")
        h.append(_tbl(["Lord", "From", "To", "Stretch", "Reading"],
                      [[m["lord"], m["from"], m["to"], m["strength"],
                        m["note"]] for m in o["months"]]))

    h.append("<h2>Putting It Together</h2><p>" + escape(GUIDANCE["closing"]) + "</p>")
    h.append('<p class="foot">Computed with the Swiss Ephemeris (sidereal, '
             f'{natal.ayanamsa_name.title()} ayanamsa, whole-sign houses, mean '
             'node). Positions are exact astronomy; interpretations follow the '
             'classical Jyotish tradition and are offered for study.</p>')
    from . import __version__
    h.append('<p class="foot" style="font-style:normal">'
             f'kundali-report v{__version__} &middot; '
             '<a href="https://github.com/chinmay28/vedic-astrology" '
             'style="color:#c9a063">github.com/chinmay28/vedic-astrology</a>'
             '</p>')
    h.append("</div></body></html>")
    with open(out_path, "w") as f:
        f.write("\n".join(h))
    return out_path
