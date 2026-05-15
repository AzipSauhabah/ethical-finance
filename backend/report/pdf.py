from __future__ import annotations

"""
:file: backend/report/pdf.py
:brief: Institutional-grade multi-page PDF tearsheet (Goldman Sachs style).

Layout (12 pages):
  1. Cover
  2. Executive Summary
  3. Performance overview (NAV vs benchmark chart)
  4. Drawdown analysis (chart)
  5. Risk metrics (VaR/CVaR table + distribution)
  6. Stress tests (table with bars)
  7. Cost analysis (cumulative costs chart + breakdown)
  8. Cash vs invested allocation over time
  9. Trade log (sample)
 10. Statistical significance
 11. Final positions
 12. Glossary + disclaimer

Charts are rendered with matplotlib → PNG → embedded in ReportLab.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

import io
from typing import Any

from backend.config import COPYRIGHT, DISCLAIMER
from backend.report.glossary import GLOSSARY

NAVY = "#142340"
GOLD = "#b8962f"
RED = "#b82424"
GREEN = "#1d8c41"
LIGHT = "#f4f4f8"
GREY = "#666666"


# ─────────────────────────────────────────────────────────────────────────────
# Chart renderers (ReportLab pur — sans kaleido ni matplotlib)
# ─────────────────────────────────────────────────────────────────────────────


def _rl_line_chart(
    series: list[tuple[str, str, list[float]]],  # (label, color_hex, values)
    width: float = 500,
    height: float = 180,
    y_fmt=None,
) -> bytes:
    """Génère un graphique en ligne avec ReportLab graphics."""
    from reportlab.graphics import renderPM
    from reportlab.graphics.shapes import Drawing, Line, PolyLine, String
    from reportlab.lib import colors as rl_colors

    d = Drawing(width, height)
    pad_l, pad_r, pad_t, pad_b = 55, 20, 15, 30

    all_vals = [v for _, _, vals in series for v in vals if v is not None]
    if not all_vals:
        return _empty_chart(width, height, "Pas de données")

    min_v, max_v = min(all_vals), max(all_vals)
    rng = max_v - min_v or 1

    w = width - pad_l - pad_r
    h = height - pad_t - pad_b

    def sx(i, n):
        return pad_l + w * i / max(n - 1, 1)

    def sy(v):
        return pad_b + h * (v - min_v) / rng

    # Axes
    d.add(
        Line(
            pad_l,
            pad_b,
            pad_l,
            pad_b + h,
            strokeColor=rl_colors.HexColor("#cccccc"),
            strokeWidth=0.5,
        )
    )
    d.add(
        Line(
            pad_l,
            pad_b,
            pad_l + w,
            pad_b,
            strokeColor=rl_colors.HexColor("#cccccc"),
            strokeWidth=0.5,
        )
    )

    # Grille horizontale (5 lignes)
    for i in range(1, 5):
        y = pad_b + h * i / 4
        val = min_v + rng * i / 4
        d.add(
            Line(pad_l, y, pad_l + w, y, strokeColor=rl_colors.HexColor("#eeeeee"), strokeWidth=0.3)
        )
        label = y_fmt(val) if y_fmt else f"{val:.0f}"
        d.add(
            String(
                pad_l - 4,
                y - 3,
                label,
                fontSize=6,
                textAnchor="end",
                fillColor=rl_colors.HexColor(GREY),
            )
        )

    # Min/Max labels Y
    d.add(
        String(
            pad_l - 4,
            pad_b - 3,
            y_fmt(min_v) if y_fmt else f"{min_v:.0f}",
            fontSize=6,
            textAnchor="end",
            fillColor=rl_colors.HexColor(GREY),
        )
    )

    # Séries
    dash_patterns = [None, [4, 2], [2, 2], [6, 2]]
    for si, (label, color_hex, vals) in enumerate(series):
        pts = []
        for i, v in enumerate(vals):
            if v is not None:
                pts += [sx(i, len(vals)), sy(v)]
        if len(pts) >= 4:
            kw = dict(strokeColor=rl_colors.HexColor(color_hex), strokeWidth=1.5, fillColor=None)
            if dash_patterns[si % len(dash_patterns)]:
                kw["strokeDashArray"] = dash_patterns[si % len(dash_patterns)]
            d.add(PolyLine(pts, **kw))

        # Légende
        lx = pad_l + si * 120
        ly = height - 10
        d.add(Line(lx, ly, lx + 20, ly, strokeColor=rl_colors.HexColor(color_hex), strokeWidth=1.5))
        d.add(String(lx + 24, ly - 3, label, fontSize=7, fillColor=rl_colors.HexColor("#444444")))

    buf = io.BytesIO()
    renderPM.drawToFile(d, buf, fmt="PNG", dpi=150)
    buf.seek(0)
    return buf.read()


def _rl_area_chart(
    values: list[float],
    color_hex: str,
    width: float = 500,
    height: float = 150,
    y_fmt=None,
    fill_alpha: float = 0.3,
) -> bytes:
    """Graphique en aire remplie."""
    from reportlab.graphics import renderPM
    from reportlab.graphics.shapes import Drawing, Line, Polygon, PolyLine, String
    from reportlab.lib import colors as rl_colors

    d = Drawing(width, height)
    pad_l, pad_r, pad_t, pad_b = 55, 20, 15, 30

    vals = [v for v in values if v is not None]
    if not vals:
        return _empty_chart(width, height, "Pas de données")

    min_v, max_v = min(vals), max(vals)
    if min_v >= 0:
        min_v = 0
    rng = max_v - min_v or 1
    w = width - pad_l - pad_r
    h = height - pad_t - pad_b

    def sx(i, n):
        return pad_l + w * i / max(n - 1, 1)

    def sy(v):
        return pad_b + h * (v - min_v) / rng

    zero_y = sy(0)

    # Axes
    d.add(
        Line(
            pad_l,
            pad_b,
            pad_l,
            pad_b + h,
            strokeColor=rl_colors.HexColor("#cccccc"),
            strokeWidth=0.5,
        )
    )
    d.add(
        Line(
            pad_l,
            zero_y,
            pad_l + w,
            zero_y,
            strokeColor=rl_colors.HexColor("#999999"),
            strokeWidth=0.5,
        )
    )

    # Grille
    for i in range(1, 5):
        y = pad_b + h * i / 4
        val = min_v + rng * i / 4
        d.add(
            Line(pad_l, y, pad_l + w, y, strokeColor=rl_colors.HexColor("#eeeeee"), strokeWidth=0.3)
        )
        label = y_fmt(val) if y_fmt else f"{val:.1f}"
        d.add(
            String(
                pad_l - 4,
                y - 3,
                label,
                fontSize=6,
                textAnchor="end",
                fillColor=rl_colors.HexColor(GREY),
            )
        )

    # Aire
    n = len(values)
    poly_pts = [pad_l, zero_y]
    line_pts = []
    for i, v in enumerate(values):
        if v is not None:
            x, y = sx(i, n), sy(v)
            poly_pts += [x, y]
            line_pts += [x, y]
    poly_pts += [sx(n - 1, n), zero_y]

    c = rl_colors.HexColor(color_hex)
    fill_c = rl_colors.Color(c.red, c.green, c.blue, fill_alpha)
    if len(poly_pts) >= 6:
        d.add(Polygon(poly_pts, fillColor=fill_c, strokeColor=None))
    if len(line_pts) >= 4:
        d.add(PolyLine(line_pts, strokeColor=c, strokeWidth=1.5, fillColor=None))

    buf = io.BytesIO()
    renderPM.drawToFile(d, buf, fmt="PNG", dpi=150)
    buf.seek(0)
    return buf.read()


def _rl_bar_chart(
    labels: list[str],
    values: list[float],
    width: float = 500,
    height: float = 180,
) -> bytes:
    """Graphique en barres horizontales."""
    from reportlab.graphics import renderPM
    from reportlab.graphics.shapes import Drawing, Line, Rect, String
    from reportlab.lib import colors as rl_colors

    d = Drawing(width, height)
    if not labels or not values:
        return _empty_chart(width, height, "Pas de données")

    pad_l, pad_r, pad_t, pad_b = 120, 20, 15, 30
    w = width - pad_l - pad_r
    h = height - pad_t - pad_b
    n = len(labels)
    bar_h = min(h / n * 0.7, 20)
    gap = h / n

    min_v, max_v = min(values), max(values)
    rng = max(abs(min_v), abs(max_v)) * 2 or 1
    zero_x = pad_l + w * abs(min_v) / rng if min_v < 0 else pad_l

    d.add(
        Line(
            zero_x,
            pad_b,
            zero_x,
            pad_b + h,
            strokeColor=rl_colors.HexColor("#999999"),
            strokeWidth=0.5,
        )
    )

    for i, (label, val) in enumerate(zip(labels, values)):
        y = pad_b + h - (i + 0.5) * gap
        bar_w = w * abs(val) / rng
        color = rl_colors.HexColor(GREEN if val >= 0 else RED)
        x = zero_x if val >= 0 else zero_x - bar_w
        d.add(Rect(x, y - bar_h / 2, bar_w, bar_h, fillColor=color, strokeColor=None))
        d.add(
            String(
                pad_l - 4,
                y - 3,
                label[:20],
                fontSize=6,
                textAnchor="end",
                fillColor=rl_colors.HexColor("#444444"),
            )
        )
        d.add(
            String(
                zero_x + (bar_w + 4 if val >= 0 else -bar_w - 4),
                y - 3,
                f"{val:+.1f}%",
                fontSize=6,
                textAnchor="start" if val >= 0 else "end",
                fillColor=rl_colors.HexColor("#444444"),
            )
        )

    buf = io.BytesIO()
    renderPM.drawToFile(d, buf, fmt="PNG", dpi=150)
    buf.seek(0)
    return buf.read()


def _rl_pie_chart(
    labels: list[str], values: list[float], width: float = 300, height: float = 200
) -> bytes:
    """Camembert ReportLab."""
    import math

    from reportlab.graphics import renderPM
    from reportlab.graphics.shapes import Drawing, String, Wedge
    from reportlab.lib import colors as rl_colors

    d = Drawing(width, height)
    cx, cy, r = width / 2, height / 2, min(width, height) / 2 - 30
    total = sum(values) or 1
    pie_colors = [NAVY, GOLD, "#8a6f9c", "#3e8260"]
    angle = 90.0

    for i, (label, val) in enumerate(zip(labels, values)):
        sweep = 360 * val / total
        c = rl_colors.HexColor(pie_colors[i % len(pie_colors)])
        d.add(
            Wedge(
                cx,
                cy,
                r,
                angle,
                angle - sweep,
                fillColor=c,
                strokeColor=rl_colors.white,
                strokeWidth=1,
            )
        )
        mid = math.radians(angle - sweep / 2)
        lx = cx + (r + 15) * math.cos(mid)
        ly = cy + (r + 15) * math.sin(mid)
        pct = f"{val/total*100:.0f}%"
        d.add(
            String(
                lx,
                ly,
                pct,
                fontSize=7,
                textAnchor="middle",
                fillColor=rl_colors.HexColor("#444444"),
            )
        )
        angle -= sweep

    buf = io.BytesIO()
    renderPM.drawToFile(d, buf, fmt="PNG", dpi=150)
    buf.seek(0)
    return buf.read()


def _empty_chart(width: float, height: float, msg: str = "Pas de données") -> bytes:
    from reportlab.graphics import renderPM
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.lib import colors as rl_colors

    d = Drawing(width, height)
    d.add(
        String(
            width / 2,
            height / 2,
            msg,
            fontSize=9,
            textAnchor="middle",
            fillColor=rl_colors.HexColor(GREY),
        )
    )
    buf = io.BytesIO()
    renderPM.drawToFile(d, buf, fmt="PNG", dpi=150)
    buf.seek(0)
    return buf.read()


def _chart_nav_vs_benchmark(nav_data: list[dict], bench_data: list[dict]) -> bytes:
    series = [("Stratégie", NAVY, [p["nav"] for p in nav_data])]
    if bench_data:
        series.append(("Benchmark", GOLD, [p["nav"] for p in bench_data]))
    return _rl_line_chart(series, width=500, height=200)


def _chart_drawdown(dd_data: list[dict]) -> bytes:
    vals = [p["drawdown"] * 100 for p in dd_data]
    return _rl_area_chart(vals, RED, width=500, height=150, y_fmt=lambda v: f"{v:.1f}%")


def _chart_costs(cost_data: list[dict]) -> bytes:
    series = [
        ("Commissions", NAVY, [p["costs"] for p in cost_data]),
        ("Total", GOLD, [p["total"] for p in cost_data]),
    ]
    return _rl_line_chart(series, width=500, height=160, y_fmt=lambda v: f"{v:.0f}€")


def _chart_allocation(alloc_data: list[dict]) -> bytes:
    series = [
        ("Investi", NAVY, [p["invested"] for p in alloc_data]),
        ("Cash", GOLD, [p["cash"] for p in alloc_data]),
    ]
    return _rl_line_chart(series, width=500, height=160, y_fmt=lambda v: f"{v:.0f}€")


def _chart_cost_breakdown(breakdown: dict) -> bytes:
    labels = ["Commissions", "Slippage", "Spread FX", "TTF"]
    values = [
        breakdown.get("commission", 0),
        breakdown.get("slippage", 0),
        breakdown.get("fx_spread", 0),
        breakdown.get("ttf", 0),
    ]
    return _rl_pie_chart(labels, values, width=300, height=200)


def _chart_stress_bars(stress_data: list[dict]) -> bytes:
    items = [
        (s.get("label", ""), s["total_return"] * 100)
        for s in stress_data
        if s.get("total_return") is not None
    ]
    if not items:
        return _empty_chart(500, 150, "Pas de données stress")
    labels, vals = zip(*items)
    return _rl_bar_chart(list(labels), list(vals), width=500, height=180)


# ─────────────────────────────────────────────────────────────────────────────
# Main PDF builder
# ─────────────────────────────────────────────────────────────────────────────


def generate_pdf(tearsheet: dict) -> bytes:
    """Build the institutional-grade PDF report. Returns raw bytes."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable,
        Image,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Sauhabah Ethical Finance — {tearsheet['meta']['strategy']}",
        author="Sauhabah Ethical Finance Platform",
    )
    styles = getSampleStyleSheet()

    def st(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    title_s = st(
        "Title",
        fontSize=24,
        textColor=colors.HexColor(NAVY),
        fontName="Helvetica-Bold",
        spaceAfter=8,
    )
    subtitle_s = st(
        "Subtl", fontSize=12, textColor=colors.HexColor(GOLD), fontName="Helvetica", spaceAfter=4
    )
    section_s = st(
        "Sec",
        fontSize=14,
        textColor=colors.HexColor(NAVY),
        fontName="Helvetica-Bold",
        spaceAfter=6,
        spaceBefore=4,
    )
    body_s = st("Body", fontSize=9, textColor=colors.black, leading=12, spaceAfter=4)
    small_s = st("Small", fontSize=7, textColor=colors.HexColor(GREY))
    disclm_s = st("Disclm", fontSize=7, textColor=colors.HexColor(GREY), leading=10)

    def tbl_style(header: bool = True) -> TableStyle:
        return TableStyle(
            [
                (
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY))
                    if header
                    else ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(LIGHT))
                ),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white if header else colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor(LIGHT), colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )

    def fmt_pct(v):
        return "N/A" if v is None else f"{v*100:+.2f}%"

    def fmt_f(v, d=2):
        return "N/A" if v is None else f"{v:.{d}f}"

    def fmt_eur(v):
        return "N/A" if v is None else f"{v:,.2f} €".replace(",", " ")

    def rl_image(data: bytes | None, width_cm: float = 17.0, aspect: float = 0.45):
        if not data:
            return Spacer(1, 0.1 * cm)
        return Image(io.BytesIO(data), width=width_cm * cm, height=width_cm * cm * aspect)

    meta = tearsheet["meta"]
    m = tearsheet["metrics"]
    sig = tearsheet.get("significance", {})
    stress = tearsheet.get("stress_tests", [])
    costs = tearsheet.get("cost_summary", {})
    breakd = tearsheet.get("cost_breakdown", {})
    nav_ch = tearsheet.get("nav_chart", [])
    bench_ch = tearsheet.get("benchmark_chart", [])
    dd_ch = tearsheet.get("drawdown_chart", [])
    cost_ch = tearsheet.get("cost_chart", [])
    alloc_ch = tearsheet.get("allocation_chart", [])
    positions = tearsheet.get("positions", {})

    story: list[Any] = []

    # PAGE 1: COVER
    story += [
        Spacer(1, 4 * cm),
        HRFlowable(width="100%", thickness=4, color=colors.HexColor(GOLD)),
        Spacer(1, 0.4 * cm),
        Paragraph("ETHICAL FINANCE PLATFORM", title_s),
        Paragraph("SAUHABAH", subtitle_s),
        Spacer(1, 0.5 * cm),
        Paragraph("Rapport de performance institutionnel", body_s),
        Paragraph(f"<b>Stratégie :</b> {meta['strategy']}", body_s),
        Paragraph(f"<b>Date d'émission :</b> {meta['generated_at']}", body_s),
        Spacer(1, 1 * cm),
        HRFlowable(width="60%", thickness=0.5, color=colors.HexColor(NAVY)),
        Spacer(1, 5 * cm),
        Paragraph("AVERTISSEMENT", subtitle_s),
        Paragraph(DISCLAIMER, disclm_s),
        Spacer(1, 0.5 * cm),
        Paragraph(COPYRIGHT, small_s),
        PageBreak(),
    ]

    # PAGE 2: EXECUTIVE SUMMARY
    story += [
        Paragraph("Résumé exécutif", section_s),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
        Spacer(1, 0.3 * cm),
    ]
    summary_data = [
        ["Métrique", "Valeur"],
        ["Rendement total", fmt_pct(m.get("total_return"))],
        ["CAGR (annualisé)", fmt_pct(m.get("cagr"))],
        ["Volatilité annualisée", fmt_pct(m.get("annualised_volatility"))],
        ["Ratio de Sharpe", fmt_f(m.get("sharpe_ratio"))],
        ["Ratio de Sortino", fmt_f(m.get("sortino_ratio"))],
        ["Ratio de Calmar", fmt_f(m.get("calmar_ratio"))],
        ["Ratio Omega", fmt_f(m.get("omega_ratio"))],
        ["Max Drawdown", fmt_pct(m.get("max_drawdown"))],
        ["Average Drawdown", fmt_pct(m.get("average_drawdown"))],
        ["Recovery Factor", fmt_f(m.get("recovery_factor"))],
    ]
    if "beta" in m:
        summary_data += [
            ["Bêta vs benchmark", fmt_f(m["beta"])],
            ["Alpha de Jensen (annualisé)", fmt_pct(m.get("alpha_jensen"))],
            ["Information Ratio", fmt_f(m.get("information_ratio"))],
        ]
    tbl = Table(summary_data, colWidths=[10 * cm, 7 * cm])
    tbl.setStyle(tbl_style())
    story += [tbl, PageBreak()]

    # PAGE 3: NAV vs BENCHMARK
    story += [
        Paragraph("Performance — NAV vs Benchmark", section_s),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
        Spacer(1, 0.3 * cm),
        Paragraph("Évolution de la valeur du portefeuille (NAV) comparée au benchmark.", body_s),
        Spacer(1, 0.3 * cm),
        rl_image(_chart_nav_vs_benchmark(nav_ch, bench_ch), aspect=0.4),
        PageBreak(),
    ]

    # PAGE 4: DRAWDOWN
    story += [
        Paragraph("Analyse du drawdown", section_s),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
        Spacer(1, 0.3 * cm),
        Paragraph(
            f"<b>Max Drawdown :</b> {fmt_pct(m.get('max_drawdown'))}<br/>"
            f"<b>Average Drawdown :</b> {fmt_pct(m.get('average_drawdown'))}<br/>"
            f"<b>Recovery Factor :</b> {fmt_f(m.get('recovery_factor'))}",
            body_s,
        ),
        Spacer(1, 0.3 * cm),
        rl_image(_chart_drawdown(dd_ch), aspect=0.3),
        PageBreak(),
    ]

    # PAGE 5: RISK
    story += [
        Paragraph("Métriques de risque", section_s),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
        Spacer(1, 0.3 * cm),
    ]
    risk_data = [
        ["Métrique", "Valeur quotidienne", "Annualisée (≈)"],
        [
            "VaR historique 95 %",
            fmt_pct(m.get("var_95")),
            fmt_pct((m.get("var_95") or 0) * (252**0.5)),
        ],
        [
            "CVaR historique 95 %",
            fmt_pct(m.get("cvar_95")),
            fmt_pct((m.get("cvar_95") or 0) * (252**0.5)),
        ],
        [
            "VaR historique 99 %",
            fmt_pct(m.get("var_99")),
            fmt_pct((m.get("var_99") or 0) * (252**0.5)),
        ],
        [
            "CVaR historique 99 %",
            fmt_pct(m.get("cvar_99")),
            fmt_pct((m.get("cvar_99") or 0) * (252**0.5)),
        ],
        ["VaR paramétrique 95 %", fmt_pct(m.get("var_parametric_95")), "—"],
        ["Skewness", fmt_f(m.get("skewness"), 3), "—"],
        ["Excess Kurtosis", fmt_f(m.get("excess_kurtosis"), 3), "—"],
        ["Tail Ratio", fmt_f(m.get("tail_ratio")), "—"],
        ["Hit Rate", fmt_pct(m.get("hit_rate")), "—"],
        ["Profit Factor", fmt_f(m.get("profit_factor")), "—"],
    ]
    tbl = Table(risk_data, colWidths=[8 * cm, 4.5 * cm, 4.5 * cm])
    tbl.setStyle(tbl_style())
    story += [tbl, PageBreak()]

    # PAGE 6: STRESS TESTS
    story += [
        Paragraph("Tests de résistance historiques", section_s),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
        Spacer(1, 0.3 * cm),
        rl_image(_chart_stress_bars(stress), aspect=0.36),
        Spacer(1, 0.3 * cm),
    ]
    if stress:
        sd = [["Scénario", "Période", "Rendement", "Max DD", "Volatilité", "Sharpe"]]
        for s in stress:
            if s.get("n_days", 0) > 0:
                sd.append(
                    [
                        s.get("label", ""),
                        f"{s.get('start', '')} → {s.get('end', '')}",
                        fmt_pct(s.get("total_return")),
                        fmt_pct(s.get("max_drawdown")),
                        fmt_pct(s.get("volatility")),
                        fmt_f(s.get("sharpe")),
                    ]
                )
        tbl = Table(sd, colWidths=[3.5 * cm, 4.5 * cm, 2.5 * cm, 2.2 * cm, 2.5 * cm, 1.8 * cm])
        tbl.setStyle(tbl_style())
        story += [tbl]
    story += [PageBreak()]

    # PAGE 7: COSTS OVER TIME
    story += [
        Paragraph("Évolution des coûts dans le temps", section_s),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
        Spacer(1, 0.3 * cm),
        rl_image(_chart_costs(cost_ch), aspect=0.32),
        Spacer(1, 0.3 * cm),
        Paragraph(
            f"<b>Coûts totaux :</b> {fmt_eur(costs.get('total_costs_eur'))}  ·  "
            f"<b>Taxes totales :</b> {fmt_eur(costs.get('total_taxes_eur'))}  ·  "
            f"<b>Coût / NAV initial :</b> {fmt_pct(costs.get('cost_pct_nav'))}",
            body_s,
        ),
        PageBreak(),
    ]

    # PAGE 8: COST BREAKDOWN
    story += [
        Paragraph("Décomposition des coûts", section_s),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
        Spacer(1, 0.3 * cm),
        rl_image(_chart_cost_breakdown(breakd), width_cm=10, aspect=0.67),
        Spacer(1, 0.3 * cm),
    ]
    cb_data = [
        ["Poste", "Montant"],
        ["Commissions courtier", fmt_eur(breakd.get("commission"))],
        ["Slippage (bid-ask)", fmt_eur(breakd.get("slippage"))],
        ["Spread FX (EUR/USD)", fmt_eur(breakd.get("fx_spread"))],
        ["TTF (taxe FR)", fmt_eur(breakd.get("ttf"))],
        ["Taxes capitales (PFU/PEA)", fmt_eur(costs.get("total_taxes_eur"))],
    ]
    tbl = Table(cb_data, colWidths=[10 * cm, 7 * cm])
    tbl.setStyle(tbl_style())
    story += [tbl, PageBreak()]

    # PAGE 9: ALLOCATION
    story += [
        Paragraph("Allocation Cash vs Investi", section_s),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
        Spacer(1, 0.3 * cm),
        rl_image(_chart_allocation(alloc_ch), aspect=0.32),
        PageBreak(),
    ]

    # PAGE 10: STATISTICAL SIGNIFICANCE
    if sig:
        story += [
            Paragraph("Significativité statistique", section_s),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
            Spacer(1, 0.3 * cm),
        ]
        jk = sig.get("jobson_korkie", {})
        at = sig.get("alpha_ttest", {})
        sb = sig.get("sharpe_bootstrap_95ci", [None, None])
        sig_data = [
            ["Test", "Statistique", "p-value", "Significatif (5%)"],
            [
                "Jobson-Korkie (Sharpe vs bench.)",
                fmt_f(jk.get("z")),
                fmt_f(jk.get("p"), 4),
                "✓ Oui" if jk.get("significant") else "✗ Non",
            ],
            [
                "Alpha Jensen (t-test)",
                fmt_f(at.get("t")),
                fmt_f(at.get("p"), 4),
                "✓ Oui" if at.get("significant") else "✗ Non",
            ],
            ["Sharpe — IC bootstrap 95 %", f"[{fmt_f(sb[0])} ; {fmt_f(sb[1])}]", "—", "—"],
        ]
        tbl = Table(sig_data, colWidths=[7 * cm, 3 * cm, 3 * cm, 4 * cm])
        tbl.setStyle(tbl_style())
        story += [tbl, PageBreak()]

    # PAGE 11: FINAL POSITIONS
    if positions and positions.get("positions"):
        story += [
            Paragraph("Positions finales du portefeuille", section_s),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
            Spacer(1, 0.3 * cm),
            Paragraph(
                f"<b>NAV final :</b> {fmt_eur(positions.get('nav_eur'))}  ·  "
                f"<b>Cash :</b> {fmt_eur(positions.get('cash_eur'))}  ·  "
                f"<b>Investi :</b> {fmt_eur(positions.get('invested_eur'))}  ·  "
                f"<b>Rendement :</b> {fmt_pct(positions.get('total_return'))}",
                body_s,
            ),
            Spacer(1, 0.3 * cm),
        ]
        pos_data = [["Ticker", "Parts", "Prix EUR", "Valeur EUR", "Coût moyen", "P&L latent"]]
        for t, p in positions["positions"].items():
            pos_data.append(
                [
                    t,
                    str(p.get("shares", 0)),
                    fmt_f(p.get("price_eur")),
                    fmt_eur(p.get("value_eur")),
                    fmt_eur(p.get("avg_cost")),
                    fmt_eur(p.get("unrealised")),
                ]
            )
        tbl = Table(pos_data, colWidths=[2.5 * cm, 2 * cm, 2.5 * cm, 3.5 * cm, 3 * cm, 3 * cm])
        tbl.setStyle(tbl_style())
        story += [tbl, PageBreak()]

    # PAGE 12: GLOSSARY + DISCLAIMER
    story += [
        Paragraph("Glossaire financier", section_s),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
        Spacer(1, 0.3 * cm),
    ]
    for entry in GLOSSARY:
        story.append(
            Paragraph(
                f"<b>{entry['term']}</b> <i>({entry['fr']})</i> — {entry['def']}",
                body_s,
            )
        )
    story += [
        Spacer(1, 0.5 * cm),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor(NAVY)),
        Spacer(1, 0.3 * cm),
        Paragraph("Avertissement réglementaire", subtitle_s),
        Paragraph(DISCLAIMER, disclm_s),
        Spacer(1, 0.3 * cm),
        Paragraph(COPYRIGHT, small_s),
    ]

    doc.build(story)
    return buf.getvalue()
