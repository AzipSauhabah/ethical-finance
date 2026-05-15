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

import os

# Force plotly à utiliser kaleido depuis les deps installées
try:
    import kaleido

    os.environ["KALEIDO_SCOPE_PLOTLY"] = "1"
except ImportError:
    pass

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
# Chart renderers (plotly → PNG bytes)
# ─────────────────────────────────────────────────────────────────────────────


def _plotly_to_png(fig, width: int = 825, height: int = 385) -> bytes | None:
    """Convert a plotly figure to PNG bytes via kaleido. Returns None if unavailable."""
    try:
        import plotly.io as pio

        return pio.to_image(
            fig, format="png", width=width, height=height, scale=1.5, engine="kaleido"
        )
    except Exception as e:
        import logging

        logging.getLogger("api").warning("kaleido unavailable: %s", e)
        return None

    pio.kaleido.scope.default_format = "png"
    return pio.to_image(fig, format="png", width=width, height=height, scale=1.5, engine="kaleido")


def _chart_nav_vs_benchmark(nav_data: list[dict], bench_data: list[dict]) -> bytes:
    import plotly.graph_objects as go

    fig = go.Figure()
    if nav_data:
        fig.add_trace(
            go.Scatter(
                x=[d["date"] for d in nav_data],
                y=[d["nav"] for d in nav_data],
                mode="lines",
                name="Stratégie",
                line=dict(color=NAVY, width=2),
            )
        )
    if bench_data:
        fig.add_trace(
            go.Scatter(
                x=[d["date"] for d in bench_data],
                y=[d["nav"] for d in bench_data],
                mode="lines",
                name="Benchmark",
                line=dict(color=GOLD, width=1.5, dash="dash"),
            )
        )
    fig.update_layout(
        margin=dict(l=50, r=20, t=20, b=50),
        xaxis_title="Date",
        yaxis_title="NAV (€)",
        legend=dict(x=0, y=1),
        plot_bgcolor="white",
        xaxis=dict(showgrid=True, gridcolor="#e0e0e0"),
        yaxis=dict(showgrid=True, gridcolor="#e0e0e0"),
    )
    return _plotly_to_png(fig)


def _chart_drawdown(dd_data: list[dict]) -> bytes:
    import plotly.graph_objects as go

    fig = go.Figure()
    if dd_data:
        x = [d["date"] for d in dd_data]
        y = [d["drawdown"] * 100 for d in dd_data]
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines",
                name="Drawdown",
                line=dict(color=RED, width=1.5),
                fill="tozeroy",
                fillcolor="rgba(184,36,36,0.2)",
            )
        )
    fig.update_layout(
        margin=dict(l=50, r=20, t=20, b=50),
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        plot_bgcolor="white",
        xaxis=dict(showgrid=True, gridcolor="#e0e0e0"),
        yaxis=dict(showgrid=True, gridcolor="#e0e0e0"),
    )
    return _plotly_to_png(fig, height=300)


def _chart_costs(cost_data: list[dict]) -> bytes:
    import plotly.graph_objects as go

    fig = go.Figure()
    if cost_data:
        x = [d["date"] for d in cost_data]
        fig.add_trace(
            go.Scatter(
                x=x,
                y=[d["costs"] for d in cost_data],
                mode="lines",
                name="Commissions + slippage",
                line=dict(color=NAVY, width=1.5),
                fill="tozeroy",
                fillcolor="rgba(20,35,64,0.5)",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x,
                y=[d["total"] for d in cost_data],
                mode="lines",
                name="Total (+ taxes)",
                line=dict(color=GOLD, width=1.5),
            )
        )
    fig.update_layout(
        margin=dict(l=50, r=20, t=20, b=50),
        xaxis_title="Date",
        yaxis_title="Cumul (€)",
        plot_bgcolor="white",
        xaxis=dict(showgrid=True, gridcolor="#e0e0e0"),
        yaxis=dict(showgrid=True, gridcolor="#e0e0e0"),
    )
    return _plotly_to_png(fig, height=300)


def _chart_allocation(alloc_data: list[dict]) -> bytes:
    import plotly.graph_objects as go

    fig = go.Figure()
    if alloc_data:
        x = [d["date"] for d in alloc_data]
        fig.add_trace(
            go.Scatter(
                x=x,
                y=[d["invested"] for d in alloc_data],
                mode="lines",
                name="Investi",
                line=dict(color=NAVY, width=0),
                fill="tozeroy",
                fillcolor="rgba(20,35,64,0.7)",
                stackgroup="one",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x,
                y=[d["cash"] for d in alloc_data],
                mode="lines",
                name="Cash",
                line=dict(color=GOLD, width=0),
                fill="tonexty",
                fillcolor="rgba(184,150,47,0.7)",
                stackgroup="one",
            )
        )
    fig.update_layout(
        margin=dict(l=50, r=20, t=20, b=50),
        xaxis_title="Date",
        yaxis_title="Allocation (€)",
        plot_bgcolor="white",
        xaxis=dict(showgrid=True, gridcolor="#e0e0e0"),
        yaxis=dict(showgrid=True, gridcolor="#e0e0e0"),
    )
    return _plotly_to_png(fig, height=300)


def _chart_cost_breakdown(breakdown: dict) -> bytes:
    import plotly.graph_objects as go

    labels = ["Commissions", "Slippage", "Spread FX", "TTF"]
    values = [
        breakdown.get("commission", 0),
        breakdown.get("slippage", 0),
        breakdown.get("fx_spread", 0),
        breakdown.get("ttf", 0),
    ]
    colors = [NAVY, GOLD, "#8a6f9c", "#3e8260"]
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            marker=dict(colors=colors),
            textinfo="label+percent",
            textfont=dict(size=11),
        )
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=False,
    )
    return _plotly_to_png(fig, width=500, height=350)


def _chart_stress_bars(stress_data: list[dict]) -> bytes:
    import plotly.graph_objects as go

    items = [
        (s.get("label", s.get("scenario", "")), s["total_return"] * 100)
        for s in stress_data
        if s.get("total_return") is not None
    ]
    if not items:
        fig = go.Figure()
        return _plotly_to_png(fig, height=200)
    labels, rets = zip(*items)
    bar_colors = [GREEN if r >= 0 else RED for r in rets]
    fig = go.Figure(
        go.Bar(
            x=list(rets),
            y=list(labels),
            orientation="h",
            marker=dict(color=bar_colors),
        )
    )
    fig.update_layout(
        margin=dict(l=150, r=20, t=20, b=50),
        xaxis_title="Rendement total (%)",
        plot_bgcolor="white",
        xaxis=dict(showgrid=True, gridcolor="#e0e0e0", zeroline=True, zerolinecolor="black"),
    )
    return _plotly_to_png(fig, height=300)


# ─────────────────────────────────────────────────────────────────────────────
# Main PDF builder — ReportLab inchangé
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

    def png_image(data, width_cm: float = 17.0):
        if data is None:
            return Spacer(1, 0.1 * cm)
        return Image(io.BytesIO(data), width=width_cm * cm, height=width_cm * cm * 0.45)

    def small_png(data, width_cm: float = 11.0):
        if data is None:
            return Spacer(1, 0.1 * cm)
        return Image(io.BytesIO(data), width=width_cm * cm, height=width_cm * cm * 0.7)

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
        *([png_image(img)] if (img := _chart_nav_vs_benchmark(nav_ch, bench_ch)) else []),
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
        *([png_image(img)] if (img := _chart_drawdown(dd_ch)) else []),
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
        *([png_image(img)] if (img := _chart_stress_bars(stress)) else []),
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
        *([png_image(img)] if (img := _chart_costs(cost_ch)) else []),
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
        *([small_png(img)] if (img := _chart_cost_breakdown(breakd)) else []),
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
        *([png_image(img)] if (img := _chart_allocation(alloc_ch)) else []),
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
