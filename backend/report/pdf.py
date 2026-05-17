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
from backend.report.narrative import generate_all_narratives

NAVY = "#142340"
GOLD = "#b8962f"
RED = "#b82424"
GREEN = "#1d8c41"
LIGHT = "#f4f4f8"
GREY = "#666666"


# ─────────────────────────────────────────────────────────────────────────────
# Drawing helpers — ReportLab Graphics (pas de PIL, pas de kaleido, pas de cairo)
# ─────────────────────────────────────────────────────────────────────────────


def _line_chart(
    series: list[tuple[str, str, list[float]]],
    width: float = 500,
    height: float = 180,
    y_fmt=None,
):
    from reportlab.graphics.shapes import Drawing, Line, PolyLine, String
    from reportlab.lib import colors as C

    d = Drawing(width, height)
    PL, PR, PT, PB = 55, 20, 15, 30
    W, H = width - PL - PR, height - PT - PB

    all_v = [v for _, _, vs in series for v in vs if v is not None]
    if not all_v:
        d.add(
            String(
                width / 2,
                height / 2,
                "Pas de données",
                fontSize=8,
                textAnchor="middle",
                fillColor=C.HexColor(GREY),
            )
        )
        return d

    lo, hi = min(all_v), max(all_v)
    rng = hi - lo or 1

    def sx(i, n):
        return PL + W * i / max(n - 1, 1)

    def sy(v):
        return PB + H * (v - lo) / rng

    # Grille
    for k in range(5):
        y = PB + H * k / 4
        val = lo + rng * k / 4
        d.add(Line(PL, y, PL + W, y, strokeColor=C.HexColor("#eeeeee"), strokeWidth=0.4))
        lbl = y_fmt(val) if y_fmt else f"{val:.0f}"
        d.add(String(PL - 3, y - 3, lbl, fontSize=6, textAnchor="end", fillColor=C.HexColor(GREY)))

    # Axes
    d.add(Line(PL, PB, PL, PB + H, strokeColor=C.HexColor("#cccccc"), strokeWidth=0.5))
    d.add(Line(PL, PB, PL + W, PB, strokeColor=C.HexColor("#cccccc"), strokeWidth=0.5))

    dashes = [None, [4, 2], [2, 2], [6, 2]]
    for si, (label, color, vals) in enumerate(series):
        pts = []
        for i, v in enumerate(vals):
            if v is not None:
                pts += [sx(i, len(vals)), sy(v)]
        if len(pts) >= 4:
            kw = dict(strokeColor=C.HexColor(color), strokeWidth=1.5, fillColor=None)
            if dashes[si % len(dashes)]:
                kw["strokeDashArray"] = dashes[si % len(dashes)]
            d.add(PolyLine(pts, **kw))
        lx = PL + si * 110
        ly = height - 10
        d.add(Line(lx, ly, lx + 18, ly, strokeColor=C.HexColor(color), strokeWidth=1.5))
        d.add(String(lx + 22, ly - 3, label, fontSize=7, fillColor=C.HexColor("#444")))

    return d


def _area_chart(
    values: list[float],
    color: str,
    width: float = 500,
    height: float = 150,
    y_fmt=None,
):
    from reportlab.graphics.shapes import Drawing, Line, Polygon, PolyLine, String
    from reportlab.lib import colors as C

    d = Drawing(width, height)
    PL, PR, PT, PB = 55, 20, 15, 30
    W, H = width - PL - PR, height - PT - PB

    vals = [v for v in values if v is not None]
    if not vals:
        return d

    lo, hi = min(vals), max(vals)
    if lo >= 0:
        lo = 0
    rng = hi - lo or 1

    def sx(i, n):
        return PL + W * i / max(n - 1, 1)

    def sy(v):
        return PB + H * (v - lo) / rng

    zero_y = sy(0)

    for k in range(5):
        y = PB + H * k / 4
        val = lo + rng * k / 4
        d.add(Line(PL, y, PL + W, y, strokeColor=C.HexColor("#eeeeee"), strokeWidth=0.4))
        lbl = y_fmt(val) if y_fmt else f"{val:.1f}"
        d.add(String(PL - 3, y - 3, lbl, fontSize=6, textAnchor="end", fillColor=C.HexColor(GREY)))

    d.add(Line(PL, PB, PL, PB + H, strokeColor=C.HexColor("#cccccc"), strokeWidth=0.5))
    d.add(Line(PL, zero_y, PL + W, zero_y, strokeColor=C.HexColor("#999"), strokeWidth=0.5))

    n = len(values)
    poly = [PL, zero_y]
    line = []
    for i, v in enumerate(values):
        if v is not None:
            x, y = sx(i, n), sy(v)
            poly += [x, y]
            line += [x, y]
    poly += [sx(n - 1, n), zero_y]

    c = C.HexColor(color)
    fill = C.Color(c.red, c.green, c.blue, 0.3)
    if len(poly) >= 6:
        d.add(Polygon(poly, fillColor=fill, strokeColor=None))
    if len(line) >= 4:
        d.add(PolyLine(line, strokeColor=c, strokeWidth=1.5, fillColor=None))

    return d


def _bar_chart(
    labels: list[str],
    values: list[float],
    width: float = 500,
    height: float = 180,
):
    from reportlab.graphics.shapes import Drawing, Line, Rect, String
    from reportlab.lib import colors as C

    d = Drawing(width, height)
    if not labels or not values:
        return d

    PL, PR, PT, PB = 120, 20, 15, 30
    W, H = width - PL - PR, height - PT - PB
    n = len(labels)
    bar_h = min(H / n * 0.7, 20)
    gap = H / n

    mx = max(abs(v) for v in values) or 1
    rng = mx * 2
    zero_x = PL + W * mx / rng

    d.add(Line(zero_x, PB, zero_x, PB + H, strokeColor=C.HexColor("#999"), strokeWidth=0.5))

    for i, (label, val) in enumerate(zip(labels, values)):
        y = PB + H - (i + 0.5) * gap
        bw = W * abs(val) / rng
        col = C.HexColor(GREEN if val >= 0 else RED)
        x = zero_x if val >= 0 else zero_x - bw
        d.add(Rect(x, y - bar_h / 2, bw, bar_h, fillColor=col, strokeColor=None))
        d.add(
            String(
                PL - 3,
                y - 3,
                label[:22],
                fontSize=6,
                textAnchor="end",
                fillColor=C.HexColor("#444"),
            )
        )
        tx = zero_x + (bw + 3 if val >= 0 else -bw - 3)
        d.add(
            String(
                tx,
                y - 3,
                f"{val:+.1f}%",
                fontSize=6,
                textAnchor=("start" if val >= 0 else "end"),
                fillColor=C.HexColor("#444"),
            )
        )
    return d


def _pie_chart(
    labels: list[str],
    values: list[float],
    width: float = 280,
    height: float = 180,
):
    import math

    from reportlab.graphics.shapes import Drawing, String, Wedge
    from reportlab.lib import colors as C

    d = Drawing(width, height)
    cx, cy = width / 2, height / 2
    r = min(width, height) / 2 - 25
    total = sum(values) or 1
    pie_colors = [NAVY, GOLD, "#8a6f9c", "#3e8260"]
    angle = 90.0

    for i, (label, val) in enumerate(zip(labels, values)):
        sweep = 360 * val / total
        col = C.HexColor(pie_colors[i % len(pie_colors)])
        d.add(
            Wedge(
                cx, cy, r, angle, angle - sweep, fillColor=col, strokeColor=C.white, strokeWidth=1
            )
        )
        mid = math.radians(angle - sweep / 2)
        lx = cx + (r + 14) * math.cos(mid)
        ly = cy + (r + 14) * math.sin(mid)
        d.add(
            String(
                lx,
                ly,
                f"{val/total*100:.0f}%",
                fontSize=7,
                textAnchor="middle",
                fillColor=C.HexColor("#444"),
            )
        )
        angle -= sweep

    return d


# ─── Chart facade functions ────────────────────────────────────────────────


def _chart_nav(nav_data, bench_data):
    series = [("Stratégie", NAVY, [p["nav"] for p in nav_data])]
    if bench_data:
        series.append(("Benchmark", GOLD, [p["nav"] for p in bench_data]))
    return _line_chart(series, 500, 200)


def _chart_drawdown(dd_data):
    return _area_chart(
        [p["drawdown"] * 100 for p in dd_data], RED, 500, 150, y_fmt=lambda v: f"{v:.1f}%"
    )


def _chart_costs(cost_data):
    series = [
        ("Commissions", NAVY, [p["costs"] for p in cost_data]),
        ("Total", GOLD, [p["total"] for p in cost_data]),
    ]
    return _line_chart(series, 500, 160, y_fmt=lambda v: f"{v:.0f}€")


def _chart_allocation(alloc_data):
    series = [
        ("Investi", NAVY, [p["invested"] for p in alloc_data]),
        ("Cash", GOLD, [p["cash"] for p in alloc_data]),
    ]
    return _line_chart(series, 500, 160, y_fmt=lambda v: f"{v:.0f}€")


def _chart_breakdown(breakdown):
    labels = ["Commissions", "Slippage", "Spread FX", "TTF"]
    values = [breakdown.get(k, 0) for k in ["commission", "slippage", "fx_spread", "ttf"]]
    return _pie_chart(labels, values, 280, 180)


def _chart_stress(stress_data):
    items = [
        (s.get("label", ""), s["total_return"] * 100)
        for s in stress_data
        if s.get("total_return") is not None
    ]
    if not items:
        from reportlab.graphics.shapes import Drawing

        return Drawing(500, 150)
    labels, vals = zip(*items)
    return _bar_chart(list(labels), list(vals), 500, 180)


# ─────────────────────────────────────────────────────────────────────────────
# Main PDF builder
# ─────────────────────────────────────────────────────────────────────────────


def generate_pdf(tearsheet: dict) -> bytes:
    from reportlab.graphics import renderPDF as _rl
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Flowable,
        HRFlowable,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    class DrawFlowable(Flowable):
        """Intègre un Drawing ReportLab directement dans le PDF — zéro dépendance externe."""

        def __init__(self, drawing: Drawing, width_cm: float, aspect: float):
            Flowable.__init__(self)
            self._d = drawing
            self.width = width_cm * cm
            self.height = width_cm * cm * aspect

        def draw(self):
            sx = self.width / self._d.width if self._d.width else 1
            sy = self.height / self._d.height if self._d.height else 1
            self.canv.saveState()
            self.canv.scale(sx, sy)
            _rl.draw(self._d, self.canv, 0, 0)
            self.canv.restoreState()

    def chart(drawing: Drawing, width_cm: float = 17.0, aspect: float = 0.40):
        if drawing is None:
            return Spacer(1, 0.1 * cm)
        return DrawFlowable(drawing, width_cm, aspect)

    buf = io.BytesIO()
    styles = getSampleStyleSheet()

    def st(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    title_s = st(
        "T", fontSize=20, textColor=colors.HexColor(NAVY), fontName="Helvetica-Bold", spaceAfter=8
    )
    subtitle_s = st(
        "S", fontSize=12, textColor=colors.HexColor(GOLD), fontName="Helvetica", spaceAfter=4
    )
    section_s = st(
        "H",
        fontSize=14,
        textColor=colors.HexColor(NAVY),
        fontName="Helvetica-Bold",
        spaceAfter=6,
        spaceBefore=4,
    )
    body_s = st("B", fontSize=9, textColor=colors.black, leading=12, spaceAfter=4)
    small_s = st("Sm", fontSize=7, textColor=colors.HexColor(GREY))
    disclm_s = st("D", fontSize=7, textColor=colors.HexColor(GREY), leading=10)

    def tbl_style():
        return TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
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

    def p(v):
        return "N/A" if v is None else f"{v*100:+.2f}%"

    def f(v, d=2):
        return "N/A" if v is None else f"{v:.{d}f}"

    def e(v):
        return "N/A" if v is None else f"{v:,.2f} €".replace(",", " ")

    def hr():
        return HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD))

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Sauhabah — {tearsheet['meta']['strategy']}",
        author="Sauhabah Ethical Finance Platform",
    )

    meta = tearsheet["meta"]
    narratives = generate_all_narratives(tearsheet)
    m = tearsheet["metrics"]
    sig = tearsheet.get("significance", {})
    st_ = tearsheet.get("stress_tests", [])
    cs = tearsheet.get("cost_summary", {})
    bd = tearsheet.get("cost_breakdown", {})
    nav = tearsheet.get("nav_chart", [])
    bnch = tearsheet.get("benchmark_chart", [])
    dd = tearsheet.get("drawdown_chart", [])
    cc = tearsheet.get("cost_chart", [])
    ac = tearsheet.get("allocation_chart", [])
    pos = tearsheet.get("positions", {})

    S: list[Any] = []

    # PAGE 1 — COVER
    S += [
        Spacer(1, 4 * cm),
        HRFlowable(width="100%", thickness=4, color=colors.HexColor(GOLD)),
        Spacer(1, 0.4 * cm),
        Paragraph("ETHICAL FINANCE PLATFORM", title_s),
        Paragraph("SAUHABAH", subtitle_s),
        Spacer(1, 0.5 * cm),
        Paragraph("Rapport de performance institutionnel", body_s),
        Paragraph(f"<b>Stratégie :</b> {meta['strategy']}", body_s),
        Paragraph(f"<b>Date :</b> {meta['generated_at']}", body_s),
        Spacer(1, 1 * cm),
        HRFlowable(width="60%", thickness=0.5, color=colors.HexColor(NAVY)),
        Spacer(1, 5 * cm),
        Paragraph("AVERTISSEMENT", subtitle_s),
        Paragraph(DISCLAIMER, disclm_s),
        Spacer(1, 0.5 * cm),
        Paragraph(COPYRIGHT, small_s),
        PageBreak(),
    ]

    # PAGE 2 — EXECUTIVE SUMMARY
    S += [Paragraph("Résumé exécutif", section_s), hr(), Spacer(1, 0.3 * cm)]
    S += [Paragraph(narratives["executive_summary"], body_s), Spacer(1, 0.4 * cm)]
    rows = [
        ["Métrique", "Valeur"],
        ["Rendement total", p(m.get("total_return"))],
        ["CAGR", p(m.get("cagr"))],
        ["Volatilité annualisée", p(m.get("annualised_volatility"))],
        ["Sharpe", f(m.get("sharpe_ratio"))],
        ["Sortino", f(m.get("sortino_ratio"))],
        ["Calmar", f(m.get("calmar_ratio"))],
        ["Omega", f(m.get("omega_ratio"))],
        ["Max Drawdown", p(m.get("max_drawdown"))],
        ["Average Drawdown", p(m.get("average_drawdown"))],
        ["Recovery Factor", f(m.get("recovery_factor"))],
    ]
    if "beta" in m:
        rows += [
            ["Bêta", f(m["beta"])],
            ["Alpha Jensen", p(m.get("alpha_jensen"))],
            ["Information Ratio", f(m.get("information_ratio"))],
        ]
    t = Table(rows, colWidths=[10 * cm, 7 * cm])
    t.setStyle(tbl_style())
    S += [t, PageBreak()]

    # PAGE 3 — NAV vs BENCHMARK
    S += [
        Paragraph("Performance — NAV vs Benchmark", section_s),
        hr(),
        Spacer(1, 0.3 * cm),
        Paragraph(narratives["performance"], body_s),
        Spacer(1, 0.3 * cm),
        chart(_chart_nav(nav, bnch), aspect=0.40),
        PageBreak(),
    ]

    # PAGE 4 — DRAWDOWN
    S += [
        Paragraph("Analyse du drawdown", section_s),
        hr(),
        Spacer(1, 0.3 * cm),
        Paragraph(narratives["drawdown"], body_s),
        Spacer(1, 0.2 * cm),
        Paragraph(
            f"<b>Max DD :</b> {p(m.get('max_drawdown'))}  "
            f"<b>Avg DD :</b> {p(m.get('average_drawdown'))}  "
            f"<b>Recovery :</b> {f(m.get('recovery_factor'))}",
            body_s,
        ),
        Spacer(1, 0.3 * cm),
        chart(_chart_drawdown(dd), aspect=0.30),
        PageBreak(),
    ]

    # PAGE 5 — RISK
    S += [Paragraph("Métriques de risque", section_s), hr(), Spacer(1, 0.3 * cm)]
    S += [Paragraph(narratives["risk"], body_s), Spacer(1, 0.3 * cm)]
    risk = [
        ["Métrique", "Quotidien", "Annualisé (≈)"],
        ["VaR hist. 95%", p(m.get("var_95")), p((m.get("var_95") or 0) * (252**0.5))],
        ["CVaR hist. 95%", p(m.get("cvar_95")), p((m.get("cvar_95") or 0) * (252**0.5))],
        ["VaR hist. 99%", p(m.get("var_99")), p((m.get("var_99") or 0) * (252**0.5))],
        ["CVaR hist. 99%", p(m.get("cvar_99")), p((m.get("cvar_99") or 0) * (252**0.5))],
        ["VaR param. 95%", p(m.get("var_parametric_95")), "—"],
        ["Skewness", f(m.get("skewness"), 3), "—"],
        ["Kurtosis excès", f(m.get("excess_kurtosis"), 3), "—"],
        ["Tail Ratio", f(m.get("tail_ratio")), "—"],
        ["Hit Rate", p(m.get("hit_rate")), "—"],
        ["Profit Factor", f(m.get("profit_factor")), "—"],
    ]
    t = Table(risk, colWidths=[8 * cm, 4.5 * cm, 4.5 * cm])
    t.setStyle(tbl_style())
    S += [t, PageBreak()]

    # PAGE 6 — STRESS TESTS
    S += [
        Paragraph("Tests de résistance historiques", section_s),
        hr(),
        Spacer(1, 0.3 * cm),
        Paragraph(narratives["stress_tests"], body_s),
        Spacer(1, 0.3 * cm),
        chart(_chart_stress(st_), aspect=0.36),
        Spacer(1, 0.3 * cm),
    ]
    if st_:
        sd = [["Scénario", "Période", "Return", "Max DD", "Vol", "Sharpe"]]
        for s in st_:
            if s.get("n_days", 0) > 0:
                sd.append(
                    [
                        s.get("label", ""),
                        f"{s.get('start','')} → {s.get('end','')}",
                        p(s.get("total_return")),
                        p(s.get("max_drawdown")),
                        p(s.get("volatility")),
                        f(s.get("sharpe")),
                    ]
                )
        t = Table(sd, colWidths=[5.5 * cm, 4.5 * cm, 2.0 * cm, 2.0 * cm, 2.0 * cm, 1.5 * cm])
        t.setStyle(tbl_style())
        S += [t]
    S += [PageBreak()]

    # PAGE 7 — COSTS
    S += [
        Paragraph("Évolution des coûts", section_s),
        hr(),
        Spacer(1, 0.3 * cm),
        chart(_chart_costs(cc), aspect=0.32),
        Spacer(1, 0.3 * cm),
        Paragraph(narratives["costs"], body_s),
        Spacer(1, 0.2 * cm),
        Paragraph(
            f"<b>Coûts :</b> {e(cs.get('total_costs_eur'))}  "
            f"<b>Taxes :</b> {e(cs.get('total_taxes_eur'))}  "
            f"<b>% NAV :</b> {p(cs.get('cost_pct_nav'))}",
            body_s,
        ),
        PageBreak(),
    ]

    # PAGE 8 — COST BREAKDOWN
    S += [
        Paragraph("Décomposition des coûts", section_s),
        hr(),
        Spacer(1, 0.3 * cm),
        chart(_chart_breakdown(bd), width_cm=10, aspect=0.65),
        Spacer(1, 0.3 * cm),
    ]
    cb = [
        ["Poste", "Montant"],
        ["Commissions", e(bd.get("commission"))],
        ["Slippage", e(bd.get("slippage"))],
        ["Spread FX", e(bd.get("fx_spread"))],
        ["TTF", e(bd.get("ttf"))],
        ["Taxes PFU/PEA", e(cs.get("total_taxes_eur"))],
    ]
    t = Table(cb, colWidths=[10 * cm, 7 * cm])
    t.setStyle(tbl_style())
    S += [t, PageBreak()]

    # PAGE 9 — ALLOCATION
    S += [
        Paragraph("Allocation Cash vs Investi", section_s),
        hr(),
        Spacer(1, 0.3 * cm),
        chart(_chart_allocation(ac), aspect=0.32),
        PageBreak(),
    ]

    # PAGE 10 — SIGNIFICANCE
    if sig:
        jk = sig.get("jobson_korkie", {})
        at = sig.get("alpha_ttest", {})
        sb = sig.get("sharpe_bootstrap_95ci", [None, None])
        S += [Paragraph("Significativité statistique", section_s), hr(), Spacer(1, 0.3 * cm)]
        sd = [
            ["Test", "Stat", "p-value", "Sig. 5%"],
            [
                "Jobson-Korkie",
                f(jk.get("z")),
                f(jk.get("p"), 4),
                "✓" if jk.get("significant") else "✗",
            ],
            [
                "Alpha Jensen t-test",
                f(at.get("t")),
                f(at.get("p"), 4),
                "✓" if at.get("significant") else "✗",
            ],
            ["Sharpe bootstrap 95%", f"[{f(sb[0])} ; {f(sb[1])}]", "—", "—"],
        ]
        t = Table(sd, colWidths=[7 * cm, 3 * cm, 3 * cm, 4 * cm])
        t.setStyle(tbl_style())
        S += [t, PageBreak()]

    # PAGE 11 — POSITIONS
    if pos and pos.get("positions"):
        S += [
            Paragraph("Positions finales", section_s),
            hr(),
            Spacer(1, 0.3 * cm),
            Paragraph(
                f"<b>NAV :</b> {e(pos.get('nav_eur'))}  "
                f"<b>Cash :</b> {e(pos.get('cash_eur'))}  "
                f"<b>Investi :</b> {e(pos.get('invested_eur'))}  "
                f"<b>Return :</b> {p(pos.get('total_return'))}",
                body_s,
            ),
            Spacer(1, 0.3 * cm),
        ]
        pd_ = [["Ticker", "Parts", "Prix €", "Valeur €", "Coût moy.", "P&L"]]
        for tk, pp in pos["positions"].items():
            pd_.append(
                [
                    tk,
                    str(pp.get("shares", 0)),
                    f(pp.get("price_eur")),
                    e(pp.get("value_eur")),
                    e(pp.get("avg_cost")),
                    e(pp.get("unrealised")),
                ]
            )
        t = Table(pd_, colWidths=[2.5 * cm, 2 * cm, 2.5 * cm, 3.5 * cm, 3 * cm, 3 * cm])
        t.setStyle(tbl_style())
        S += [t, PageBreak()]

    # PAGE 12 — TRADES DÉTAILLÉS
    trades = tearsheet.get("trades", {})
    trade_list = trades.get("sample", [])
    if trade_list:
        S += [
            Paragraph("Journal des trades", section_s),
            hr(),
            Spacer(1, 0.3 * cm),
            Paragraph(
                f"<b>{trades.get('count', 0)} trades</b> exécutés sur la période. "
                "Tous les coûts réels (commission, slippage, TTF, spread FX) sont inclus.",
                body_s,
            ),
            Spacer(1, 0.3 * cm),
        ]
        # Tableau par blocs de 30 trades max par page
        headers = ["Date", "Ticker", "Côté", "Parts", "Prix €", "Notionnel €", "Coût €", "P&L €"]
        chunk_size = 30
        for chunk_start in range(0, min(len(trade_list), 300), chunk_size):
            chunk = trade_list[chunk_start : chunk_start + chunk_size]
            td_data = [headers]
            for tr in chunk:
                side = tr.get("side", "")
                td_data.append(
                    [
                        str(tr.get("date", "")),
                        str(tr.get("ticker", "")),
                        side.upper(),
                        str(tr.get("shares", 0)),
                        f(tr.get("price_eur")),
                        e(tr.get("notional_eur")),
                        e(tr.get("total_cost")),
                        e(tr.get("pnl")),
                    ]
                )
            t = Table(
                td_data,
                colWidths=[
                    2.2 * cm,
                    1.8 * cm,
                    1.2 * cm,
                    1.2 * cm,
                    2.2 * cm,
                    2.8 * cm,
                    2.0 * cm,
                    2.0 * cm,
                ],
            )
            ts_ = tbl_style()
            # Colorise les lignes buy/sell
            for i, tr in enumerate(chunk, 1):
                if tr.get("side") == "buy":
                    ts_.add("BACKGROUND", (2, i), (2, i), colors.HexColor("#e8f5e9"))
                else:
                    ts_.add("BACKGROUND", (2, i), (2, i), colors.HexColor("#ffebee"))
            t.setStyle(ts_)
            S += [t, Spacer(1, 0.3 * cm)]
        if len(trade_list) > 300:
            S += [
                Paragraph(
                    f"... et {len(trade_list) - 300} trades supplémentaires non affichés.", body_s
                )
            ]
        S += [PageBreak()]

    # PAGE 12a — RISQUE PAR POSITION
    risk_pos = tearsheet.get("risk_by_position", {})
    if risk_pos:
        S += [
            Paragraph("Risque par position — VaR et contribution", section_s),
            hr(),
            Spacer(1, 0.3 * cm),
            Paragraph(
                "La VaR (Valeur a Risque) est calculee par simulation historique sur les rendements "
                "journaliers de chaque titre. La contribution au risque mesure l impact de chaque "
                "position sur le risque global du portefeuille, pondere par son poids.",
                body_s,
            ),
            Spacer(1, 0.3 * cm),
        ]
        risk_data = [
            [
                "Ticker",
                "Poids",
                "Valeur EUR",
                "VaR 95% jour",
                "CVaR 95% jour",
                "VaR EUR",
                "Contrib. risque",
            ]
        ]
        for ticker, r in sorted(
            risk_pos.items(), key=lambda x: abs(x[1].get("var_95_eur", 0)), reverse=True
        ):
            risk_data.append(
                [
                    ticker,
                    f"{r.get('weight', 0)*100:.1f}%",
                    e(r.get("value_eur")),
                    f"{r.get('var_95_daily', 0)*100:.2f}%",
                    f"{r.get('cvar_95_daily', 0)*100:.2f}%",
                    e(r.get("var_95_eur")),
                    f"{r.get('contribution_pct', 0)*100:.3f}%",
                ]
            )
        t = Table(
            risk_data,
            colWidths=[2.0 * cm, 1.8 * cm, 2.8 * cm, 2.2 * cm, 2.5 * cm, 2.5 * cm, 2.6 * cm],
        )
        t.setStyle(tbl_style())
        S += [
            t,
            Spacer(1, 0.3 * cm),
            Paragraph(
                "Note : la VaR historique ne capture pas les evenements hors de l historique observe. "
                "La CVaR (Expected Shortfall) mesure la perte moyenne au-dela du seuil VaR — "
                "elle est plus conservative et recommandee par Bale III.",
                small_s,
            ),
            PageBreak(),
        ]

    # PAGE 12b — SECTION ML
    tearsheet.get("ml_info", {})
    S += [
        Paragraph("Intelligence artificielle et signaux ML", section_s),
        hr(),
        Spacer(1, 0.3 * cm),
        Paragraph(
            "EPR5 utilise deux modeles d apprentissage automatique complementaires pour generer "
            "des signaux directionnels sur chaque titre. Les deux modeles sont entraines en "
            "walk-forward strict : uniquement sur les donnees passees, reentraine tous les 60 jours. "
            "Le score final combine 60% RandomForest + 40% LSTM TensorFlow.",
            body_s,
        ),
        Spacer(1, 0.2 * cm),
        Paragraph("<b>Modele 1 — RandomForest (scikit-learn)</b>", body_s),
        Paragraph(
            "50 arbres, profondeur max 4, class_weight=balanced. "
            "Features statiques : rendements 1j/5j/20j/60j, volatilite, RSI, position MM20/50/200, momentum. "
            "Label : rendement a 20j > +5%. Score = probabilite classe positive.",
            body_s,
        ),
        Spacer(1, 0.2 * cm),
        Paragraph("<b>Modele 2 — LSTM TensorFlow (nouveau)</b>", body_s),
        Paragraph(
            "Reseau recurrent a memoire longue : Input(30j x 11 features) → LSTM(64) → Dropout → "
            "LSTM(32) → Dropout → Dense(16, ReLU) → Dense(1, sigmoid). "
            "Horizon de prediction : 5 jours. Seuil positif : rendement > +2%. "
            "Le LSTM capte les dependances temporelles (momentum, regimes de volatilite) "
            "que le RandomForest ignore car il traite les features de facon statique.",
            body_s,
        ),
        Spacer(1, 0.2 * cm),
        Paragraph("<b>Score combine</b> : score_final = 0.6 x RF + 0.4 x LSTM", body_s),
        Spacer(1, 0.3 * cm),
        Paragraph("<b>Features utilisees (indicateurs techniques)</b>", body_s),
    ]
    features_data = [
        ["Feature", "Description", "Fenetre"],
        ["ret_1", "Rendement 1 jour", "1j"],
        ["ret_5", "Rendement 5 jours", "5j"],
        ["ret_20", "Rendement 20 jours", "20j"],
        ["vol_10", "Volatilite realisee", "10j"],
        ["vol_20", "Volatilite realisee", "20j"],
        ["rsi_14", "RSI normalise [0,1]", "14j"],
        ["ema_ratio", "EMA20/EMA50 - 1 (tendance)", "20/50j"],
        ["macd_hist", "Histogramme MACD normalise", "12/26/9j"],
        ["bb_pos", "Position dans les bandes Bollinger [0,1]", "20j"],
        ["mom_20", "Momentum 20 jours", "20j"],
        ["mom_60", "Momentum 60 jours", "60j"],
    ]
    t = Table(features_data, colWidths=[3 * cm, 9 * cm, 3.5 * cm])
    t.setStyle(tbl_style())
    S += [t, Spacer(1, 0.3 * cm)]

    S += [
        Paragraph("<b>Modeles utilises</b>", body_s),
        Paragraph(
            "LightGBM (Light Gradient Boosting Machine) — deux configurations : "
            "(1) RF-like : 200 arbres, profondeur 5, bagging. "
            "(2) GBDT : 300 arbres, profondeur 4, boosting sequentiel. "
            "La variable cible est le signe du rendement a 5 jours avec un seuil de 1% "
            "(classes : +1 achat, -1 vente, 0 neutre).",
            body_s,
        ),
        Spacer(1, 0.2 * cm),
        Paragraph("<b>Hypotheses et limites du ML</b>", body_s),
        Paragraph(
            "1. Les modeles supposent que les patterns historiques se repetent. "
            "Cette hypothese est fragile en periode de rupture de regime (crise, changement macro). "
            "2. Le split 70/30 introduit un biais temporel : le modele est entrained sur une periode "
            "qui peut avoir un regime different du test. "
            "3. Aucune regularisation dynamique n est appliquee : les modeles ne se reajustent pas "
            "aux nouvelles donnees au fil du temps (pas de rolling refit). "
            "4. Les features sont purement techniques : aucune donnee fondamentale ou macro "
            "n est utilisee dans les signaux ML (sauf pour EPR5 qui utilise des ratios fondamentaux). "
            "5. Le threshold de 1% filtre le bruit mais peut eliminer des signaux valides "
            "en periode de faible volatilite.",
            body_s,
        ),
        Spacer(1, 0.2 * cm),
        Paragraph("<b>Interpretation des signaux</b>", body_s),
        Paragraph(
            "+1 (Achat) : le modele predit un rendement > +1% sur 5 jours. "
            "-1 (Vente/Short) : rendement predit < -1%. "
            "0 (Neutre) : rendement predit dans la plage [-1%, +1%], pas de position. "
            "Les signaux sont generes une fois par jour apres la cloture et executes "
            "a la cloture du jour suivant.",
            body_s,
        ),
        PageBreak(),
    ]

    # PAGE 13 — METHODOLOGIE
    from backend.report.glossary import LIMITATIONS_TEXT, METHODOLOGY_TEXT

    S += [
        Paragraph("Methodologie et hypotheses", section_s),
        hr(),
        Spacer(1, 0.3 * cm),
    ]
    for para in METHODOLOGY_TEXT.split("\n\n"):
        if para.strip():
            if para.strip().startswith(("1.", "2.", "3.", "4.", "5.")):
                S.append(Paragraph(para.strip(), body_s))
            else:
                S.append(Paragraph(para.strip(), body_s))
            S.append(Spacer(1, 0.15 * cm))
    S += [PageBreak()]

    # PAGE 14 — LIMITES DU MODELE
    S += [
        Paragraph("Limites du modele et avertissements", section_s),
        hr(),
        Spacer(1, 0.3 * cm),
    ]
    for para in LIMITATIONS_TEXT.split("\n\n"):
        if para.strip():
            S.append(Paragraph(para.strip(), body_s))
            S.append(Spacer(1, 0.15 * cm))
    S += [PageBreak()]

    # PAGE 15 — GLOSSARY
    S += [Paragraph("Glossaire financier", section_s), hr(), Spacer(1, 0.3 * cm)]
    for entry in GLOSSARY:
        S.append(
            Paragraph(f"<b>{entry['term']}</b> <i>({entry['fr']})</i> — {entry['def']}", body_s)
        )
    S += [
        Spacer(1, 0.5 * cm),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor(NAVY)),
        Spacer(1, 0.3 * cm),
        Paragraph("Avertissement réglementaire", subtitle_s),
        Paragraph(DISCLAIMER, disclm_s),
        Spacer(1, 0.3 * cm),
        Paragraph(COPYRIGHT, small_s),
    ]

    doc.build(S)
    return buf.getvalue()
