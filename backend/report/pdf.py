"""
:file: api/report/pdf.py
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

from __future__ import annotations

import io
from typing import Any

from backend.config import COPYRIGHT, DISCLAIMER
from backend.report.glossary import GLOSSARY

# Goldman-inspired palette
NAVY = "#142340"
GOLD = "#b8962f"
RED = "#b82424"
GREEN = "#1d8c41"
LIGHT = "#f4f4f8"
GREY = "#666666"


# ─────────────────────────────────────────────────────────────────────────────
# Chart renderers (matplotlib → PNG bytes)
# ─────────────────────────────────────────────────────────────────────────────


def _chart_nav_vs_benchmark(nav_data: list[dict], bench_data: list[dict]) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.5, 3.5), dpi=110)
    if nav_data:
        x = [d["date"] for d in nav_data]
        y = [d["nav"] for d in nav_data]
        ax.plot(x, y, color=NAVY, linewidth=1.8, label="Stratégie")
    if bench_data:
        x = [d["date"] for d in bench_data]
        y = [d["nav"] for d in bench_data]
        ax.plot(x, y, color=GOLD, linewidth=1.4, linestyle="--", label="Benchmark")
    ax.set_xlabel("Date", fontsize=8)
    ax.set_ylabel("NAV (€)", fontsize=8)
    ax.tick_params(axis="x", labelsize=6, rotation=45)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="upper left", frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    # Show every Nth tick
    if nav_data and len(nav_data) > 12:
        step = len(nav_data) // 12
        for i, lbl in enumerate(ax.get_xticklabels()):
            if i % step != 0:
                lbl.set_visible(False)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _chart_drawdown(dd_data: list[dict]) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.5, 2.8), dpi=110)
    if dd_data:
        x = [d["date"] for d in dd_data]
        y = [d["drawdown"] * 100 for d in dd_data]
        ax.fill_between(x, y, 0, color=RED, alpha=0.25)
        ax.plot(x, y, color=RED, linewidth=1.2)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_xlabel("Date", fontsize=8)
    ax.set_ylabel("Drawdown (%)", fontsize=8)
    ax.tick_params(axis="x", labelsize=6, rotation=45)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(True, alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if dd_data and len(dd_data) > 12:
        step = len(dd_data) // 12
        for i, lbl in enumerate(ax.get_xticklabels()):
            if i % step != 0:
                lbl.set_visible(False)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _chart_costs(cost_data: list[dict]) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.5, 3.0), dpi=110)
    if cost_data:
        x = [d["date"] for d in cost_data]
        c = [d["costs"] for d in cost_data]
        [d["taxes"] for d in cost_data]
        tot = [d["total"] for d in cost_data]
        ax.fill_between(x, c, 0, color=NAVY, alpha=0.6, label="Commissions + slippage")
        ax.fill_between(x, tot, c, color=GOLD, alpha=0.6, label="Taxes (PFU/TTF)")
        ax.plot(x, tot, color="black", linewidth=1.0)
    ax.set_xlabel("Date", fontsize=8)
    ax.set_ylabel("Cumul (€)", fontsize=8)
    ax.tick_params(axis="x", labelsize=6, rotation=45)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="upper left", frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if cost_data and len(cost_data) > 12:
        step = len(cost_data) // 12
        for i, lbl in enumerate(ax.get_xticklabels()):
            if i % step != 0:
                lbl.set_visible(False)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _chart_allocation(alloc_data: list[dict]) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.5, 3.0), dpi=110)
    if alloc_data:
        x = [d["date"] for d in alloc_data]
        cash = [d["cash"] for d in alloc_data]
        inv = [d["invested"] for d in alloc_data]
        ax.stackplot(x, inv, cash, labels=["Investi", "Cash"], colors=[NAVY, GOLD], alpha=0.85)
    ax.set_xlabel("Date", fontsize=8)
    ax.set_ylabel("Allocation (€)", fontsize=8)
    ax.tick_params(axis="x", labelsize=6, rotation=45)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="upper left", frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if alloc_data and len(alloc_data) > 12:
        step = len(alloc_data) // 12
        for i, lbl in enumerate(ax.get_xticklabels()):
            if i % step != 0:
                lbl.set_visible(False)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _chart_cost_breakdown(breakdown: dict) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5.0, 3.0), dpi=110)
    labels = ["Commissions", "Slippage", "Spread FX", "TTF"]
    values = [
        breakdown.get("commission", 0),
        breakdown.get("slippage", 0),
        breakdown.get("fx_spread", 0),
        breakdown.get("ttf", 0),
    ]
    colors = [NAVY, GOLD, "#8a6f9c", "#3e8260"]
    if sum(values) > 0:
        ax.pie(
            values,
            labels=labels,
            autopct="%1.1f%%",
            colors=colors,
            textprops={"fontsize": 8},
            startangle=90,
        )
    else:
        ax.text(
            0.5,
            0.5,
            "Aucun coût",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=10,
            color=GREY,
        )
    ax.set_title("Décomposition des coûts", fontsize=10, color=NAVY)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _chart_stress_bars(stress_data: list[dict]) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.5, 3.0), dpi=110)
    labels = [
        s.get("label", s.get("scenario", ""))
        for s in stress_data
        if s.get("total_return") is not None
    ]
    rets = [s["total_return"] * 100 for s in stress_data if s.get("total_return") is not None]
    if labels:
        colors = [GREEN if r >= 0 else RED for r in rets]
        ax.barh(labels, rets, color=colors, alpha=0.8)
        ax.axvline(0, color="black", linewidth=0.5)
    ax.set_xlabel("Rendement total (%)", fontsize=8)
    ax.tick_params(axis="y", labelsize=8)
    ax.tick_params(axis="x", labelsize=7)
    ax.grid(True, alpha=0.3, axis="x")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Main PDF builder
# ─────────────────────────────────────────────────────────────────────────────


def generate_pdf(tearsheet: dict) -> bytes:
    """Build the institutional-grade PDF report.  Returns raw bytes."""
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
    st("Badge", fontSize=8, textColor=colors.white, backColor=colors.HexColor(NAVY), alignment=1)

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

    def png_image(data: bytes, width_cm: float = 17.0):
        return Image(io.BytesIO(data), width=width_cm * cm, height=width_cm * cm * 0.45)

    def small_png(data: bytes, width_cm: float = 11.0):
        return Image(io.BytesIO(data), width=width_cm * cm, height=width_cm * cm * 0.7)

    # Pull data
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
    tearsheet.get("trades", {})
    positions = tearsheet.get("positions", {})

    story: list[Any] = []

    # ═══ PAGE 1: COVER ════════════════════════════════════════════════════
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

    # ═══ PAGE 2: EXECUTIVE SUMMARY ════════════════════════════════════════
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

    # ═══ PAGE 3: NAV vs BENCHMARK ═════════════════════════════════════════
    story += [
        Paragraph("Performance — NAV vs Benchmark", section_s),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
        Spacer(1, 0.3 * cm),
        Paragraph(
            "Évolution de la valeur du portefeuille (NAV) comparée au benchmark sur "
            "la période complète du backtest. La NAV intègre les coûts réels de "
            "transaction et la fiscalité française.",
            body_s,
        ),
        Spacer(1, 0.3 * cm),
        png_image(_chart_nav_vs_benchmark(nav_ch, bench_ch)),
        PageBreak(),
    ]

    # ═══ PAGE 4: DRAWDOWN ═════════════════════════════════════════════════
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
        png_image(_chart_drawdown(dd_ch)),
        PageBreak(),
    ]

    # ═══ PAGE 5: RISK (VaR/CVaR) ═════════════════════════════════════════
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

    # ═══ PAGE 6: STRESS TESTS ════════════════════════════════════════════
    story += [
        Paragraph("Tests de résistance historiques", section_s),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
        Spacer(1, 0.3 * cm),
        Paragraph(
            "Performance reconstruite sur les cinq grandes crises de marché. "
            "Chaque scénario applique la stratégie sur sa fenêtre temporelle exacte.",
            body_s,
        ),
        Spacer(1, 0.2 * cm),
        png_image(_chart_stress_bars(stress)),
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

    # ═══ PAGE 7: COSTS OVER TIME ══════════════════════════════════════════
    story += [
        Paragraph("Évolution des coûts dans le temps", section_s),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
        Spacer(1, 0.3 * cm),
        Paragraph(
            "Cumul des coûts de transaction (commissions courtier, slippage, spread "
            "FX) et de la fiscalité française (PFU 30 %, TTF 0,1 %) sur la période. "
            "Ces frais sont déduits de la NAV à chaque transaction.",
            body_s,
        ),
        Spacer(1, 0.2 * cm),
        png_image(_chart_costs(cost_ch)),
        Spacer(1, 0.3 * cm),
        Paragraph(
            f"<b>Coûts totaux :</b> {fmt_eur(costs.get('total_costs_eur'))}  ·  "
            f"<b>Taxes totales :</b> {fmt_eur(costs.get('total_taxes_eur'))}  ·  "
            f"<b>Coût / NAV initial :</b> {fmt_pct(costs.get('cost_pct_nav'))}",
            body_s,
        ),
        PageBreak(),
    ]

    # ═══ PAGE 8: COST BREAKDOWN ═══════════════════════════════════════════
    story += [
        Paragraph("Décomposition des coûts", section_s),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
        Spacer(1, 0.3 * cm),
        small_png(_chart_cost_breakdown(breakd)),
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

    # ═══ PAGE 9: ALLOCATION (Cash vs Invested) ════════════════════════════
    story += [
        Paragraph("Allocation Cash vs Investi", section_s),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
        Spacer(1, 0.3 * cm),
        Paragraph(
            "Le cash en attente n'est pas rémunéré dans le backtest, conformément à la "
            "réalité d'un compte-titres. Une stratégie peut volontairement conserver "
            "du cash dans l'attente d'un signal.",
            body_s,
        ),
        Spacer(1, 0.2 * cm),
        png_image(_chart_allocation(alloc_ch)),
        PageBreak(),
    ]

    # ═══ PAGE 10: STATISTICAL SIGNIFICANCE ════════════════════════════════
    if sig:
        story += [
            Paragraph("Significativité statistique", section_s),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
            Spacer(1, 0.3 * cm),
            Paragraph(
                "Tests statistiques permettant de distinguer la chance de la "
                "compétence (seuil de significativité : p &lt; 0,05).",
                body_s,
            ),
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

    # ═══ PAGE 11: FINAL POSITIONS ═════════════════════════════════════════
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

    # ═══ PAGE 12: GLOSSARY + DISCLAIMER ═══════════════════════════════════
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
