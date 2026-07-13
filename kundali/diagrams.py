"""diagrams.py - North & South Indian kundali diagrams (SVG -> PNG).

Contract: render(chart, out_dir) -> (north_png_path, south_png_path).
Geometry validated against hand-checked charts.
"""
from __future__ import annotations

import os

import cairosvg

from .model import Chart, NINE_GRAHAS, SIGNS, sign_of

BG, LINE, NUM, TXT, LAG = "#fdfbf5", "#1e2749", "#b06c1f", "#1e2749", "#8a5a10"
ABBR = {"Sun": "Su", "Moon": "Mo", "Mars": "Ma", "Mercury": "Me",
        "Jupiter": "Ju", "Venus": "Ve", "Saturn": "Sa", "Rahu": "Ra",
        "Ketu": "Ke"}


def _labels(chart: Chart) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for b in NINE_GRAHAS:
        s, deg = sign_of(chart.bodies[b].lon)
        tag = f"{ABBR[b]} {int(deg)}" + ("(R)" if chart.bodies[b].retro and b not in ("Rahu", "Ketu") else "")
        if b == "Rahu":
            tag = f"Ra {int(deg)}"
        out.setdefault(s, []).append(tag)
    return out


def _txt(x: float, y: float, fill: str, size: float, s: str,
         anchor: str = "middle") -> str:
    return (f'<text x="{x}" y="{y}" fill="{fill}" font-family="Georgia" '
            f'font-size="{size}" text-anchor="{anchor}">{s}</text>')


def north_svg(chart: Chart) -> str:
    lag, placements = chart.lagna_idx, _labels(chart)
    W = 500
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{W}" viewBox="0 0 {W} {W}">',
         f'<rect width="{W}" height="{W}" fill="{BG}"/>',
         f'<rect x="3" y="3" width="{W-6}" height="{W-6}" fill="none" stroke="{LINE}" stroke-width="2.5"/>']
    T, R, B, L, C = (250, 3), (497, 250), (250, 497), (3, 250), (250, 250)
    TL, TR, BR, BL = (3, 3), (497, 3), (497, 497), (3, 497)
    mLT, mTR, mRB, mBL = (126, 126), (374, 126), (374, 374), (126, 374)
    for a, b in [(TL, BR), (TR, BL), (T, R), (R, B), (B, L), (L, T)]:
        p.append(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" '
                 f'stroke="{LINE}" stroke-width="1.6"/>')
    houses = {1: [T, mTR, C, mLT], 2: [TL, T, mLT], 3: [TL, L, mLT],
              4: [L, mLT, C, mBL], 5: [BL, L, mBL], 6: [BL, B, mBL],
              7: [B, mBL, C, mRB], 8: [BR, B, mRB], 9: [BR, R, mRB],
              10: [R, mRB, C, mTR], 11: [TR, R, mTR], 12: [TR, T, mTR]}
    for h in range(1, 13):
        pts = houses[h]
        cx = sum(q[0] for q in pts) / len(pts)
        cy = sum(q[1] for q in pts) / len(pts)
        si = (lag + h - 1) % 12
        p.append(_txt(cx, cy - 20, NUM, 15, str(si + 1)))
        bodies = list(placements.get(si, []))
        if h == 1:
            bodies = ["Lagna"] + bodies
        start = cy - (len(bodies) - 1) * 8 + 4
        for i, bd in enumerate(bodies):
            p.append(_txt(cx, start + i * 15, LAG if bd == "Lagna" else TXT,
                          12.5 if bd == "Lagna" else 13, bd))
    p.append("</svg>")
    return "\n".join(p)


def south_svg(chart: Chart) -> str:
    lag, placements = chart.lagna_idx, _labels(chart)
    G = 420
    s4 = G / 4
    cell = {11: (0, 0), 0: (1, 0), 1: (2, 0), 2: (3, 0), 3: (3, 1),
            4: (3, 2), 5: (3, 3), 6: (2, 3), 7: (1, 3), 8: (0, 3),
            9: (0, 2), 10: (0, 1)}
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{G}" height="{G}" viewBox="0 0 {G} {G}">',
         f'<rect width="{G}" height="{G}" fill="{BG}"/>',
         f'<rect x="2" y="2" width="{G-4}" height="{G-4}" fill="none" stroke="{LINE}" stroke-width="2.5"/>']
    lines = [(s4, 0, s4, s4), (2*s4, 0, 2*s4, s4), (3*s4, 0, 3*s4, s4),
             (s4, 3*s4, s4, 4*s4), (2*s4, 3*s4, 2*s4, 4*s4), (3*s4, 3*s4, 3*s4, 4*s4),
             (0, s4, s4, s4), (0, 2*s4, s4, 2*s4), (0, 3*s4, s4, 3*s4),
             (3*s4, s4, 4*s4, s4), (3*s4, 2*s4, 4*s4, 2*s4), (3*s4, 3*s4, 4*s4, 3*s4),
             (s4, s4, 3*s4, s4), (s4, s4, s4, 3*s4), (3*s4, s4, 3*s4, 3*s4),
             (s4, 3*s4, 3*s4, 3*s4)]
    for x1, y1, x2, y2 in lines:
        p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                 f'stroke="{LINE}" stroke-width="1.6"/>')
    for si in range(12):
        c, r = cell[si]
        x0, y0 = c * s4, r * s4
        p.append(_txt(x0 + 6, y0 + 14, NUM, 9.5, SIGNS[si][:3].upper(), "start"))
        if si == lag:
            p.append(f'<line x1="{x0}" y1="{y0}" x2="{x0+18}" y2="{y0+18}" '
                     f'stroke="{LINE}" stroke-width="1.6"/>')
        bodies = list(placements.get(si, []))
        if si == lag:
            bodies = ["Lagna"] + bodies
        cx, cy = x0 + s4 / 2, y0 + s4 / 2
        start = cy - (len(bodies) - 1) * 8 + 4
        for i, bd in enumerate(bodies):
            p.append(_txt(cx, start + i * 15, LAG if bd == "Lagna" else TXT, 12, bd))
    p.append("</svg>")
    return "\n".join(p)


def render(chart: Chart, out_dir: str, stem: str) -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    n_path = os.path.join(out_dir, f"{stem}_north.png")
    s_path = os.path.join(out_dir, f"{stem}_south.png")
    cairosvg.svg2png(bytestring=north_svg(chart).encode(), write_to=n_path,
                     output_width=1000, output_height=1000)
    cairosvg.svg2png(bytestring=south_svg(chart).encode(), write_to=s_path,
                     output_width=840, output_height=840)
    return n_path, s_path
