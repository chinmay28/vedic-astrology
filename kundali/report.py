"""report.py - assemble the PDF with reportlab/platypus.

Contract: build_report(natal, varsha_years, out_path, work_dir) -> out_path.
"""
from __future__ import annotations

import tempfile

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from . import aspects, diagrams, ephemeris as eph, yogas
from .ashtakavarga import bav, sav
from .avastha import avastha_table
from .bhav import bhav_table, shifts
from .dasha_now import age_note, guidance_for, locate, lord_condition, sandhi_note
from .guidance import GUIDANCE
from .maitri import maitri_table
from .panchanga import avakahada, karana, tithi, vara, yoga as sy_yoga
from .sadesati import (IMPACTS, NAVIGATION, current_status, lifetime_table,
                       severity_profile)
from .varga import (navamsa_chart, shodashavarga_table, vargottama,
                    vimshopaka)
from .dasha import antardashas_in_window, mahadashas
from .model import (Chart, DIG_BALA_HOUSE, HOUSE_SIGNIFICATIONS, SIGNS,
                    SIGN_LORD, dignity, nakshatra_of, sign_of)
from .varshaphal import Varsha, cast_varsha, sade_sati_phase

NAVY = colors.HexColor("#1e2749")
GOLD = colors.HexColor("#b06c1f")
GREY = colors.HexColor("#5a5f78")
LIGHT = colors.HexColor("#eef0f7")

_ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=_ss["Heading1"], fontName="Helvetica-Bold",
                    fontSize=18, textColor=NAVY, spaceAfter=8)
H2 = ParagraphStyle("H2", parent=_ss["Heading2"], fontName="Helvetica-Bold",
                    fontSize=13, textColor=NAVY, spaceBefore=11, spaceAfter=4)
H3 = ParagraphStyle("H3", parent=_ss["Heading3"], fontName="Helvetica-Bold",
                    fontSize=10.5, textColor=GOLD, spaceBefore=8, spaceAfter=3)
BODY = ParagraphStyle("Body", parent=_ss["Normal"], fontName="Helvetica",
                      fontSize=9.5, leading=13.4, textColor=NAVY,
                      alignment=TA_JUSTIFY, spaceAfter=5)
SMALL = ParagraphStyle("Small", parent=BODY, fontSize=8.3, leading=11.4,
                       textColor=GREY)
CAP = ParagraphStyle("Cap", parent=BODY, fontSize=8.5, textColor=GREY,
                     alignment=TA_CENTER)
TITLE = ParagraphStyle("T", parent=_ss["Title"], fontName="Helvetica-Bold",
                       fontSize=24, textColor=NAVY, alignment=TA_CENTER)
SUBT = ParagraphStyle("ST", parent=BODY, fontSize=11.5, textColor=GOLD,
                      alignment=TA_CENTER)


GUIDE = ParagraphStyle("Guide", parent=SMALL, fontName="Helvetica-Oblique",
                       textColor=GREY, leftIndent=4, spaceBefore=1,
                       spaceAfter=6)


def _guide(key):
    return Paragraph("<b>How to read this:</b> " + GUIDANCE[key], GUIDE)


def _table(data, widths, fs=8.5, header=True):
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
             ("FONTSIZE", (0, 0), (-1, -1), fs),
             ("TEXTCOLOR", (0, 0), (-1, -1), NAVY),
             ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9cbd8")),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("TOPPADDING", (0, 0), (-1, -1), 2.5),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), NAVY),
                  ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                  ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
        style += [("BACKGROUND", (0, i), (-1, i), LIGHT)
                  for i in range(2, len(data), 2)]
    t.setStyle(TableStyle(style))
    return t


def _positions_table(chart: Chart):
    rows = [["Graha", "Rashi", "Deg", "Nakshatra-Pada", "H", "Dignity"]]
    asc_s, asc_d = sign_of(chart.asc)
    nk, pd = nakshatra_of(chart.asc)
    rows.append(["Lagna", SIGNS[asc_s], f"{asc_d:.2f}", f"{nk} {pd}", "1", "-"])
    for b in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus",
              "Saturn", "Rahu", "Ketu"]:
        s, d = sign_of(chart.bodies[b].lon)
        nk, pd = nakshatra_of(chart.bodies[b].lon)
        dig = dignity(b, s, d)
        h = chart.house_of(b)
        if DIG_BALA_HOUSE.get(b) == h:
            dig += "; dig bala"
        name = b + (" (R)" if chart.bodies[b].retro and b not in ("Rahu", "Ketu") else "")
        if b == "Rahu":
            name = "Rahu (R)"
        rows.append([name, SIGNS[s], f"{d:.2f}", f"{nk} {pd}", str(h), dig])
    return _table(rows, [58, 62, 40, 90, 26, 150])


def _houses_table(chart: Chart):
    occ = chart.occupants()
    rows = [["H", "Sign", "Occupants", "Lord -> H", "Signifies"]]
    for h in range(1, 13):
        si = (chart.lagna_idx + h - 1) % 12
        lord = SIGN_LORD[si]
        nm, sig = HOUSE_SIGNIFICATIONS[h]
        rows.append([str(h), SIGNS[si], ", ".join(occ[h]) or "-",
                     f"{lord} -> {chart.house_of(lord)}", f"{nm}: {sig}"])
    return _table(rows, [20, 62, 108, 72, 220], fs=7.8)


def _natal_section(natal: Chart, work_dir: str, window: tuple[float, float]):
    n_img, s_img = diagrams.render(natal, work_dir, "natal")
    el = [Paragraph(f"Natal Chart - {natal.name}", H1),
          Paragraph(f"<b>Birth:</b> {natal.dt_local.strftime('%d %b %Y, %H:%M')} "
                    f"({natal.tz}) - {natal.place} ({natal.lat:.2f}, {natal.lon:.2f}). "
                    f"{natal.ayanamsa_name.title()} ayanamsa {natal.ayanamsa_deg:.2f} deg.", BODY),
          Paragraph(f"<b>Lagna</b> {SIGNS[natal.lagna_idx]} - "
                    f"<b>Rashi</b> {SIGNS[natal.sign_idx_of('Moon')]} "
                    f"({nakshatra_of(natal.bodies['Moon'].lon)[0]}).", BODY),
          Paragraph("Input Verification", H2), _guide("verification")]
    off, dst = eph.utc_offset_info(natal.dt_local, natal.tz)
    el += [_table([["Timezone used", f"{natal.tz} -> {off}"
                    + (" (daylight saving ACTIVE on this date)" if dst
                       else " (no daylight saving on this date)")],
                   ["Birth instant (UT)", eph.jd_to_local_str(natal.jd, "UTC") + " UT"],
                   ["Node convention", "Mean node (some software uses True node; "
                    "differences up to ~1.7 deg are a convention, not an error)"]],
                  [110, 380], header=False, fs=8.2), Spacer(1, 2*mm)]

    pk, tn, tname = tithi(natal)
    el += [Paragraph("Panchanga at Birth", H2), _guide("panchanga"),
           _table([["Tithi", f"{pk} {tname} ({tn})"], ["Vara", vara(natal)],
                   ["Nakshatra", f"{nakshatra_of(natal.bodies['Moon'].lon)[0]} "
                    f"pada {nakshatra_of(natal.bodies['Moon'].lon)[1]}"],
                   ["Yoga", sy_yoga(natal)], ["Karana", karana(natal)]],
                  [90, 400], header=False, fs=8.4), Spacer(1, 2*mm),
           Paragraph("Avakahada (birth constants)", H3), _guide("avakahada"),
           _table([[k, v] for k, v in avakahada(natal).items()],
                  [110, 380], header=False, fs=8.4), Spacer(1, 2*mm),
           Paragraph("Graha Positions", H2), _guide("positions"),
           _positions_table(natal), Spacer(1, 3*mm)]
    if natal.sandhi_flags():
        el.append(Paragraph("<b>Sandhi caution:</b> " + ", ".join(natal.sandhi_flags()) +
                            " within 1 deg of a sign boundary - degree-sensitive "
                            "placements; verify birth time and ayanamsa before "
                            "fine-grained timing.", SMALL))
    imgs = Table([[Image(n_img, 76*mm, 76*mm), Image(s_img, 70*mm, 70*mm)],
                  [Paragraph("North Indian (houses fixed)", CAP),
                   Paragraph("South Indian (signs fixed)", CAP)]],
                 colWidths=[84*mm, 78*mm])
    imgs.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    el += [Paragraph(" ", CAP), _guide("diagrams"), imgs, Spacer(1, 3*mm),
           Paragraph("Yogas &amp; Combinations", H2), _guide("yogas")]
    el += [Paragraph(f"<b>{n}.</b> {d}", BODY) for n, d in yogas.detect(natal)]

    el.append(Paragraph("Graha Drishti (Aspects)", H2))
    el.append(_guide("aspects"))
    mut = aspects.mutual_pairs(natal)
    el.append(Paragraph("<b>Mutual aspects:</b> " +
                        ("; ".join(f"{a} &lt;-&gt; {b}" for a, b in mut) or "none"), BODY))
    inbound = aspects.inbound_by_house(natal)
    occ = natal.occupants()
    rows = [["H", "Occupants", "Aspected by"]]
    for h in range(1, 13):
        rows.append([str(h), ", ".join(occ[h]) or "-",
                     ", ".join(inbound[h]) or "-"])
    el += [_table(rows, [22, 150, 310], fs=7.8), Spacer(1, 2*mm),
           Paragraph("Numbers in parentheses give the aspect cast (7 = opposition; "
                     "4/8 Mars, 5/9 Jupiter, 3/10 Saturn).", SMALL)]

    el.append(Paragraph("Vimshottari Mahadasha", H2))
    el.append(_guide("dasha"))
    mds = mahadashas(natal.bodies["Moon"].lon, natal.jd)
    el.append(_table([["Mahadasha", "From", "To"]] +
                     [[m.lord, eph.jd_to_date_str(m.start, natal.tz),
                       eph.jd_to_date_str(m.end, natal.tz)] for m in mds], [90, 110, 110]))
    ads = antardashas_in_window(natal.bodies["Moon"].lon, natal.jd, *window)
    if ads:
        el += [Paragraph("Antardasha detail (report window)", H3),
               _table([["Period", "From", "To"]] +
                      [[f"{a.lord} / {a.sub}", eph.jd_to_date_str(a.start, natal.tz),
                        eph.jd_to_date_str(a.end, natal.tz)] for a in ads], [130, 110, 110])]
        from .dasha import pratyantardashas
        prows = [["MD / AD / PAD", "From", "To"]]
        for a in ads[:3]:
            for md_l, ad_l, pad, ps, pe in pratyantardashas(a):
                prows.append([f"{md_l} / {ad_l} / {pad}",
                              eph.jd_to_date_str(ps, natal.tz),
                              eph.jd_to_date_str(pe, natal.tz)])
        el += [Paragraph("Pratyantardasha (month-scale, first ADs of window)", H3),
               _table(prows, [170, 100, 100], fs=7.6)]
    d9 = navamsa_chart(natal)
    dn, ds = diagrams.render(d9, work_dir, "d9")
    el.append(Paragraph("Navamsa (D-9)", H2))
    el.append(_guide("d9"))
    vg = vargottama(natal)
    if vg:
        el.append(Paragraph("<b>Vargottama:</b> " + ", ".join(vg) +
                            " - same sign in D-1 and D-9; strengthened.", BODY))
    rows = [["Graha", "D-9 Rashi", "D-9 H", "D-9 Dignity"]]
    for b in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus",
              "Saturn", "Rahu", "Ketu"]:
        rows.append([b, SIGNS[d9.sign_idx_of(b)], str(d9.house_of(b)),
                     dignity(b, d9.sign_idx_of(b))])
    d9imgs = Table([[Image(dn, 60*mm, 60*mm), Image(ds, 56*mm, 56*mm)]],
                   colWidths=[68*mm, 64*mm])
    d9imgs.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    el += [_table(rows, [70, 80, 40, 120], fs=8.2), Spacer(1, 2*mm), d9imgs,
           Spacer(1, 2*mm),
           Paragraph("The D-9 shows how each planet matures; dignity gained "
                     "here strengthens a weak D-1 placement and vice versa.",
                     SMALL)]

    el.append(Paragraph("Ashtakavarga", H2))
    el.append(_guide("ashtakavarga"))
    rows = [[""] + [s3[:3] for s3 in SIGNS]]
    rows.append(["SAV"] + [str(x) for x in sav(natal)])
    for p in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"):
        rows.append([p[:4]] + [str(x) for x in bav(natal, p)])
    el += [_table(rows, [34] + [32]*12, fs=7.6),
           Paragraph("SAV totals 337 by construction. Signs holding 30+ "
                     "bindus are strong ground for transits; 24 or fewer, "
                     "thin ground - weigh Saturn/Rahu transits through "
                     "low-SAV signs more heavily.", SMALL)]
    el.append(Paragraph("Shodashavarga &amp; Vimshopaka", H2))
    el.append(_guide("shodashavarga"))
    el.append(_table(shodashavarga_table(natal), [34] + [28]*16, fs=6.8))
    vim = vimshopaka(natal)
    el.append(Spacer(1, 2*mm))
    el.append(_table([["Vimshopaka /20"] + [p[:4] for p in vim],
                      ["score"] + [f"{v}" for v in vim.values()]],
                     [80] + [52]*7, fs=8))
    el.append(Paragraph("Panchadha Maitri (compound friendship)", H2))
    el.append(_guide("maitri"))
    el.append(_table(maitri_table(natal), [52] + [56]*7, fs=7.2))
    el.append(Paragraph("Avasthas (planetary states)", H2))
    el.append(_guide("avasthas"))
    el.append(_table(avastha_table(natal), [60, 100, 130, 130], fs=7.8))
    el.append(Paragraph("Bhav Chalit (Sripati cusps)", H2))
    el.append(_guide("bhav"))
    el.append(_table(bhav_table(natal), [50, 110, 110, 110], fs=7.6))
    sh = shifts(natal)
    el.append(Paragraph(
        ("<b>House shifts vs whole-sign:</b> " +
         "; ".join(f"{p}: H{a} -> H{b}" for p, a, b in sh))
        if sh else "<b>No planet shifts house</b> between whole-sign and "
                   "Bhav Chalit in this chart - the two systems agree.",
        SMALL))
    el += [Paragraph("The Twelve Houses", H2), _guide("houses"),
           _houses_table(natal), PageBreak()]
    return el


def _sadesati_section(natal: Chart, asof):
    from .sadesati import PHASES
    el = [Paragraph("Sade Sati &amp; Saturn's Sensitive Transits", H1),
          _guide("sadesati")]
    grade, factors = severity_profile(natal)
    el += [Paragraph("How it tends to run for this chart: "
                     f"<b>{grade.upper()}</b>", H3),
           _table([["Factor", "Finding"]] + [list(f) for f in factors],
                  [150, 340], fs=7.9), Spacer(1, 2*mm)]
    if asof is not None:
        jd_asof = eph.jd_from_local(asof, natal.tz)
        active, nxt = current_status(natal, jd_asof)
        if active:
            s0, e0, sg, off = active
            el += [Paragraph(f"Current status (as of {asof.strftime('%d %b %Y')}): "
                             f"<b>{PHASES[off]}</b>, Saturn in {SIGNS[sg]}, "
                             f"{eph.jd_to_date_str(s0, natal.tz)} - "
                             f"{eph.jd_to_date_str(e0, natal.tz)}", BODY),
                   Paragraph(IMPACTS[off], BODY)]
            from .dasha_now import locate
            md, ad, _, _, _ = locate(natal, jd_asof)
            if "Saturn" in (md.lord, ad.sub):
                el.append(Paragraph(
                    "<b>Double-Saturn note:</b> a Saturn dasha period runs "
                    "concurrently with this transit - the tradition reads "
                    "the overlap as intensified: the same counsel, applied "
                    "more strictly.", SMALL))
        else:
            el.append(Paragraph(f"No sensitive Saturn transit is active as of "
                                f"{asof.strftime('%d %b %Y')}.", BODY))
        if nxt:
            s1, e1, sg1, off1 = nxt
            el += [Paragraph(f"Next: <b>{PHASES[off1]}</b> "
                             f"({SIGNS[sg1]}), {eph.jd_to_date_str(s1, natal.tz)} - "
                             f"{eph.jd_to_date_str(e1, natal.tz)}.", BODY),
                   Paragraph(IMPACTS[off1], SMALL)]
    el += [Paragraph("Navigating Saturn's periods", H3),
           Paragraph(NAVIGATION, BODY),
           Paragraph("Lifetime table", H3),
           _table([["From", "To", "Saturn in", "Phase", "Murti"]] +
                  [list(r) for r in lifetime_table(natal)],
                  [75, 75, 62, 210, 48], fs=7.4),
           PageBreak()]
    return el


def _varsha_section(v: Varsha, natal: Chart, work_dir: str):
    n_img, s_img = diagrams.render(v.chart, work_dir, f"varsha{v.age}")
    el = [Paragraph(f"Varshaphala - Age {v.age} "
                    f"({eph.jd_to_date_str(v.chart.jd, natal.tz)})", H2),
          _table([["Pravesh", eph.jd_to_local_str(v.chart.jd, natal.tz) + f" ({natal.tz})"],
                  ["Varsha Lagna", f"{SIGNS[v.chart.lagna_idx]} "
                   f"{sign_of(v.chart.asc)[1]:.1f} deg (natal house "
                   f"{v.natal_house_rising} rising)"],
                  ["Muntha", f"{SIGNS[v.muntha_sign]} in varsha house "
                   f"{v.muntha_house} - {v.grade}; lord {v.muntha_lord}"],
                  ["Birth type", "Day" if v.day_birth else "Night"]],
                 [90, 400], header=False),
          Spacer(1, 2*mm),
          Paragraph("<b>Year-lord candidates</b> (select by strength; "
                    "Panchavargiya Bala not computed): " +
                    "; ".join(f"{role}: {p}" for role, p in v.candidates), SMALL)]
    imgs = Table([[Image(n_img, 62*mm, 62*mm), Image(s_img, 58*mm, 58*mm)]],
                 colWidths=[70*mm, 66*mm])
    imgs.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    el += [Spacer(1, 2*mm), imgs, Spacer(1, 2*mm),
           Paragraph("Mudda dasha", H3),
           _table([["Lord", "From", "To"]] +
                  [[m.lord, eph.jd_to_date_str(m.start, natal.tz),
                    eph.jd_to_date_str(m.end, natal.tz)] for m in v.mudda],
                  [80, 110, 110], fs=7.8),
           Spacer(1, 4*mm)]
    return el


def _dasha_now_section(natal: Chart, asof):
    jd_asof = eph.jd_from_local(asof, natal.tz)
    md, ad, pad, next_ad, next_md = locate(natal, jd_asof)
    vim = vimshopaka(natal)
    el = [Paragraph("Dasha Now &amp; Next - Navigating the Current Periods", H1),
          _guide("dashanow"),
          Paragraph(f"As of <b>{asof.strftime('%d %b %Y')}</b>:", BODY)]
    an = age_note(natal, jd_asof)
    if an:
        el.append(Paragraph(an, SMALL))
    el += [
          _table([["Level", "Period", "From", "To"],
                  ["Mahadasha (era)", md.lord,
                   eph.jd_to_date_str(md.start, natal.tz),
                   eph.jd_to_date_str(md.end, natal.tz)],
                  ["Antardasha (chapter)", f"{md.lord} / {ad.sub}",
                   eph.jd_to_date_str(ad.start, natal.tz),
                   eph.jd_to_date_str(ad.end, natal.tz)],
                  ["Pratyantar (texture)", f"{pad[0]} / {pad[1]} / {pad[2]}",
                   eph.jd_to_date_str(pad[3], natal.tz),
                   eph.jd_to_date_str(pad[4], natal.tz)],
                  ["Next Antardasha", f"{next_ad.lord} / {next_ad.sub}",
                   eph.jd_to_date_str(next_ad.start, natal.tz),
                   eph.jd_to_date_str(next_ad.end, natal.tz)],
                  ["Next Mahadasha", next_md.lord,
                   eph.jd_to_date_str(next_md.start, natal.tz),
                   eph.jd_to_date_str(next_md.end, natal.tz)]],
                 [110, 130, 90, 90], fs=8.4),
          Spacer(1, 2*mm),
          Paragraph("Navigating the current era", H3),
          Paragraph(guidance_for(natal, lord_condition(natal, md.lord, vim),
                                 "Mahadasha"), BODY),
          Paragraph("Navigating the current chapter", H3),
          Paragraph(guidance_for(natal, lord_condition(natal, ad.sub, vim),
                                 "Antardasha"), BODY),
          Paragraph("The next chapter", H3),
          Paragraph(guidance_for(natal, lord_condition(natal, next_ad.sub, vim),
                                 "coming Antardasha")
                    + f" It begins {eph.jd_to_date_str(next_ad.start, natal.tz)}"
                    " - position accordingly in the months before.", BODY)]
    if next_md.lord != md.lord:
        el.append(Paragraph("The next era", H3))
        el.append(Paragraph(
            f"The {next_md.lord} Mahadasha opens "
            f"{eph.jd_to_date_str(next_md.start, natal.tz)}. "
            + guidance_for(natal, lord_condition(natal, next_md.lord, vim),
                           "coming Mahadasha"), BODY))
    note = sandhi_note(md, ad, jd_asof, natal.tz)
    if note:
        el.append(Paragraph(note, SMALL))
    el.append(Paragraph(
        "General counsel for any period: the dasha shows which of the "
        "chart's standing promises is switched on, not what must happen. "
        "Strong-lord periods reward initiative; strained-lord periods "
        "reward maintenance, patience, and the lord's classical remedies "
        "(discipline for Saturn, service for the nodes, generosity for "
        "Jupiter...). Cross-check any big move against the transit "
        "calendar and the year's varsha chart - convergence is "
        "confirmation.", SMALL))
    el.append(PageBreak())
    return el


def _transits_section(natal: Chart, jd_from: float, jd_to: float):
    eph.set_ayanamsa(natal.ayanamsa_name)   # swe sid-mode is global state
    el = [Paragraph("Transit Calendar (report window)", H2)]
    rows = [["Body", "Ingress", "Into", "Natal house entered"]]
    for body in ("Jupiter", "Saturn", "Rahu"):
        for jd, _, to in eph.sign_ingresses(body, jd_from, jd_to):
            h = ((to - natal.lagna_idx) % 12) + 1
            rows.append([body, eph.jd_to_date_str(jd, natal.tz), SIGNS[to], str(h)])
    el.append(_table(rows, [70, 100, 90, 130], fs=8.2))
    moon_s = natal.sign_idx_of("Moon")
    phase = sade_sati_phase(moon_s, natal.sign_idx_of("Saturn"))
    notes = []
    for jd, _, to in eph.sign_ingresses("Saturn", jd_from, jd_to):
        ph = sade_sati_phase(moon_s, to)
        if ph:
            notes.append(f"{eph.jd_to_date_str(jd)}: {ph}")
    if notes:
        el.append(Paragraph("<b>Sade Sati:</b> " + "; ".join(notes) + ".", SMALL))
    return el


def build_report(natal: Chart, varsha_years: list[int], out_path: str,
                 work_dir: str | None = None, asof=None) -> str:
    work_dir = work_dir or tempfile.mkdtemp(prefix="kundali_")
    jd_from = min(natal.jd, eph.jd_from_local(
        natal.dt_local.replace(year=min(varsha_years), month=1, day=1), natal.tz)) \
        if varsha_years else natal.jd
    varshas = [v for v in (cast_varsha(natal, y) for y in sorted(varsha_years))
               if v is not None]
    jd_from = varshas[0].chart.jd if varshas else natal.jd
    jd_to = (varshas[-1].chart.jd + 366) if varshas else natal.jd + 366

    story = [Spacer(1, 26*mm), Paragraph("Janma Kundali Report", TITLE),
             Spacer(1, 4*mm), Paragraph(natal.name, SUBT),
             Paragraph(f"{natal.dt_local.strftime('%d %b %Y, %H:%M')} - {natal.place}", SUBT),
             Spacer(1, 8*mm),
             Paragraph(f"Swiss Ephemeris - sidereal, {natal.ayanamsa_name.title()} "
                       "ayanamsa - whole-sign houses - mean node - varsha charts "
                       "cast for the birthplace", CAP),
             Spacer(1, 3*mm),
             Paragraph("Computed positions are exact astronomy; interpretations "
                       "present the classical Jyotish tradition's reading and are "
                       "offered for study, not as guidance for medical, financial "
                       "or legal decisions.", CAP),
             PageBreak()]
    story += _natal_section(natal, work_dir, (jd_from, jd_to))
    if asof is not None:
        story += _dasha_now_section(natal, asof)
    story += _sadesati_section(natal, asof)
    if varshas:
        story.append(Paragraph("Tajika Varshaphala", H1))
        story.append(Paragraph("<b>How to read this:</b> " + GUIDANCE["varshaphal"],
                               ParagraphStyle("G2", parent=SMALL,
                                              fontName="Helvetica-Oblique")))
        story.append(Paragraph(
            "Muntha grades (Neelakantha): houses 1, 9, 10, 11 excellent; "
            "2, 3, 5 good; 4, 6, 7, 8, 12 adverse. The Mudda dasha times the "
            "year month by month.", SMALL))
        for v in varshas:
            story += _varsha_section(v, natal, work_dir)
        story.append(PageBreak())
    story += _transits_section(natal, jd_from, jd_to)
    story += [Spacer(1, 3*mm),
              Paragraph("<b>How to read this:</b> " + GUIDANCE["transits"],
                        ParagraphStyle("G3", parent=SMALL,
                                       fontName="Helvetica-Oblique")),
              Spacer(1, 4*mm), Paragraph("Putting It Together", H2),
              Paragraph(GUIDANCE["closing"], BODY)]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GREY)
        from . import __version__
        canvas.drawString(17*mm, 9*mm,
                          f"{natal.name} - {natal.ayanamsa_name.title()} "
                          f"ayanamsa - kundali-report v{__version__}")
        canvas.drawRightString(A4[0] - 17*mm, 9*mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(out_path, pagesize=A4, topMargin=16*mm,
                            bottomMargin=16*mm, leftMargin=17*mm,
                            rightMargin=17*mm, title=f"Kundali - {natal.name}")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out_path
