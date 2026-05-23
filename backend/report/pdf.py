from __future__ import annotations

# ─── Label constants ────────────────────────────────────────────────────────
_LABEL_SPREAD_FX = "Spread FX"

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

import matplotlib

matplotlib.use("Agg")  # backend non-interactif — thread safe
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from backend.config import COPYRIGHT, DISCLAIMER
from backend.report.glossary import GLOSSARY
from backend.report.narrative import generate_all_narratives, generate_metric_interpretations

NAVY = "#142340"
GOLD = "#b8962f"
RED = "#b82424"
GREEN = "#1d8c41"
LIGHT = "#f4f4f8"
GREY = "#666666"


# ─────────────────────────────────────────────────────────────────────────────
# Drawing helpers — Matplotlib (HD, antialiasing, style institutionnel)
# ─────────────────────────────────────────────────────────────────────────────


def _mpl_style():
    """Style matplotlib Goldman Sachs dark."""
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "#f8f9fa",
            "axes.edgecolor": "#cccccc",
            "axes.labelcolor": "#333333",
            "axes.grid": True,
            "grid.color": "#e0e0e0",
            "grid.linewidth": 0.5,
            "grid.alpha": 0.8,
            "xtick.color": "#333333",
            "ytick.color": "#333333",
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.facecolor": "white",
            "legend.edgecolor": "#cccccc",
            "legend.fontsize": 7,
            "font.family": "DejaVu Sans",
            "text.color": "#1a1a1a",
            "lines.linewidth": 1.8,
        }
    )


def _fig_to_image_flowable(fig, width_cm: float = 17.0):
    """Convertit une figure matplotlib en ImageFlowable ReportLab."""
    from reportlab.lib.units import cm
    from reportlab.platypus import Image as RLImage

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    buf.seek(0)
    plt.close(fig)

    img = RLImage(buf, width=width_cm * cm)
    img.hAlign = "LEFT"
    return img


def _line_chart(
    series: list[tuple[str, str, list[float]]],
    width: float = 500,
    height: float = 180,
    y_fmt=None,
):
    _mpl_style()
    fig, ax = plt.subplots(figsize=(10, 3.5), facecolor="white")
    ax.set_facecolor("#f8f9fa")

    dashes = [None, (6, 2), (2, 2), (4, 2, 1, 2)]
    for i, (label, color, vals) in enumerate(series):
        x = list(range(len(vals)))
        ls = "--" if dashes[i % len(dashes)] else "-"
        ax.plot(x, vals, color=color, linewidth=1.8, label=label, linestyle=ls, alpha=0.95)

    if y_fmt:
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: y_fmt(v)))
    ax.legend(loc="upper left", framealpha=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.5)
    return fig


def _area_chart(
    values: list[float],
    color: str,
    width: float = 500,
    height: float = 150,
    y_fmt=None,
):
    _mpl_style()
    fig, ax = plt.subplots(figsize=(10, 3.0), facecolor="white")
    ax.set_facecolor("#f8f9fa")

    x = list(range(len(values)))
    ax.plot(x, values, color=color, linewidth=1.8)
    ax.fill_between(x, values, 0, color=color, alpha=0.25)
    ax.axhline(0, color="#999999", linewidth=0.8)

    if y_fmt:
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: y_fmt(v)))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.5)
    return fig


def _bar_chart(
    labels: list[str],
    values: list[float],
    width: float = 500,
    height: float = 180,
):
    _mpl_style()
    fig, ax = plt.subplots(figsize=(10, max(3.5, len(labels) * 0.5)), facecolor="white")
    ax.set_facecolor("#f8f9fa")

    colors_bar = [GREEN if v >= 0 else RED for v in values]
    y_pos = range(len(labels))
    ax.barh(list(y_pos), values, color=colors_bar, height=0.6, alpha=0.85)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, fontsize=7)
    ax.axvline(0, color="#999999", linewidth=0.8)

    for i, v in enumerate(values):
        ax.text(
            v + (0.3 if v >= 0 else -0.3),
            i,
            f"{v:+.1f}%",
            va="center",
            ha="left" if v >= 0 else "right",
            fontsize=7,
            color="#555555",
        )

    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.5)
    return fig


def _pie_chart(
    labels: list[str],
    values: list[float],
    width: float = 280,
    height: float = 180,
):
    _mpl_style()
    pie_colors = [NAVY, GOLD, "#8a6f9c", "#3e8260"]
    fig, ax = plt.subplots(figsize=(5, 3.5), facecolor="white")
    ax.set_facecolor("#f8f9fa")

    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        colors=pie_colors[: len(values)],
        autopct="%1.0f%%",
        startangle=90,
        textprops={"fontsize": 7, "color": "#555555"},
        wedgeprops={"linewidth": 1, "edgecolor": "white"},
    )
    for at in autotexts:
        at.set_color("#e8e8e8")
        at.set_fontsize(7)

    fig.tight_layout(pad=0.3)
    return fig


# ─── Chart facade functions ────────────────────────────────────────────────


def _chart_nav(nav_data, bench_data):
    series = [("Stratégie", NAVY, [p["nav"] for p in nav_data])]
    if bench_data:
        series.append(("Benchmark", GOLD, [p["nav"] for p in bench_data]))
    return _line_chart(series, y_fmt=lambda v: f"{v:.0f}")


def _chart_drawdown(dd_data):
    return _area_chart([p["drawdown"] * 100 for p in dd_data], RED, y_fmt=lambda v: f"{v:.1f}%")


def _chart_costs(cost_data):
    series = [
        ("Commissions", NAVY, [p["costs"] for p in cost_data]),
        ("Total", GOLD, [p["total"] for p in cost_data]),
    ]
    return _line_chart(series, y_fmt=lambda v: f"{v:.0f}€")


def _chart_allocation(alloc_data):
    series = [
        ("Investi", NAVY, [p["invested"] for p in alloc_data]),
        ("Cash", GOLD, [p["cash"] for p in alloc_data]),
    ]
    return _line_chart(series, y_fmt=lambda v: f"{v:.0f}€")


def _chart_breakdown(breakdown):
    labels = ["Commissions", "Slippage", _LABEL_SPREAD_FX, "TTF"]
    labels = ["Commissions", "Slippage", "Impact marché", _LABEL_SPREAD_FX, "TTF", "Stamp Duty"]
    values = [
        breakdown.get(k, 0)
        for k in ["commission", "slippage", "market_impact", "fx_spread", "ttf", "stamp_duty"]
    ]
    # Filtrer les valeurs nulles
    non_zero = [(l, v) for l, v in zip(labels, values) if v > 0]
    if non_zero:
        labels, values = zip(*non_zero)
        labels, values = list(labels), list(values)
    else:
        labels, values = ["Aucun coût"], [1]
    return _pie_chart(labels, values)


def _chart_stress(stress_data):
    items = [
        (s.get("label", ""), s["total_return"] * 100)
        for s in stress_data
        if s.get("total_return") is not None
    ]
    if not items:
        return None
    labels, vals = zip(*items)
    return _bar_chart(list(labels), list(vals))


# ─── Nouveaux graphiques institutionnels ──────────────────────────────────────


def _chart_rolling_sharpe(rolling_sharpe: list) -> object:
    """Rolling Sharpe 252j — style QuantConnect."""
    if not rolling_sharpe:
        return None
    _mpl_style()
    fig, ax = plt.subplots(figsize=(10, 3.0), facecolor="white")
    ax.set_facecolor("#f8f9fa")
    dates = list(range(len(rolling_sharpe)))
    values = [d["sharpe"] for d in rolling_sharpe]
    ax.plot(dates, values, color=GOLD, linewidth=1.8)
    ax.axhline(0, color="#999999", linewidth=0.8, linestyle="--")
    ax.axhline(1, color=GREEN, linewidth=0.6, linestyle=":", alpha=0.7)
    ax.fill_between(dates, values, 0, where=[v >= 0 for v in values], color=GREEN, alpha=0.15)
    ax.fill_between(dates, values, 0, where=[v < 0 for v in values], color=RED, alpha=0.15)
    ax.set_title("Rolling Sharpe 252j", color="#555555", fontsize=8, pad=4)
    ax.set_ylabel("Sharpe", fontsize=7)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.5)
    return fig


def _chart_rolling_vol(rolling_vol: list) -> object:
    """Rolling Volatilité 63j annualisée."""
    if not rolling_vol:
        return None
    _mpl_style()
    fig, ax = plt.subplots(figsize=(10, 3.0), facecolor="white")
    ax.set_facecolor("#f8f9fa")
    dates = list(range(len(rolling_vol)))
    values = [d["vol"] for d in rolling_vol]
    ax.plot(dates, values, color="#5b8dee", linewidth=1.8)
    ax.fill_between(dates, values, alpha=0.2, color="#5b8dee")
    ax.set_title("Rolling Volatilité 63j (annualisée)", color="#555555", fontsize=8, pad=4)
    ax.set_ylabel("Volatilité %", fontsize=7)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.1f}%"))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.5)
    return fig


def _chart_monthly_heatmap(monthly_returns_list: list) -> object:
    """Monthly Returns Heatmap — style Quantopian."""
    if not monthly_returns_list:
        return None
    _mpl_style()

    import pandas as pd

    df = pd.DataFrame(monthly_returns_list)
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    pivot = df.pivot(index="year", columns="month", values="return")
    pivot.columns = [
        "Jan",
        "Fév",
        "Mar",
        "Avr",
        "Mai",
        "Jun",
        "Jul",
        "Aoû",
        "Sep",
        "Oct",
        "Nov",
        "Déc",
    ][: len(pivot.columns)]

    n_years = len(pivot)
    fig, ax = plt.subplots(figsize=(12, max(2.5, n_years * 0.5)), facecolor="white")
    ax.set_facecolor("#f8f9fa")

    vmax = max(abs(pivot.values[~np.isnan(pivot.values)]).max(), 5)
    im = ax.imshow(pivot.values, cmap="RdYlGn", aspect="auto", vmin=-vmax, vmax=vmax)

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, fontsize=7)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=7)

    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                color = "white" if abs(val) > vmax * 0.6 else "#333"
                ax.text(
                    j,
                    i,
                    f"{val:+.1f}%",
                    ha="center",
                    va="center",
                    fontsize=6,
                    color=color,
                    fontweight="bold",
                )

    plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    ax.set_title("Rendements mensuels (%)", color="#555555", fontsize=8, pad=4)
    fig.tight_layout(pad=0.5)
    return fig


def _chart_return_distribution(return_distribution: list) -> object:
    """Distribution des rendements journaliers + courbe gaussienne."""
    if not return_distribution:
        return None
    _mpl_style()
    fig, ax = plt.subplots(figsize=(10, 3.5), facecolor="white")
    ax.set_facecolor("#f8f9fa")

    data = np.array(return_distribution)
    ax.hist(
        data,
        bins=80,
        color=NAVY,
        alpha=0.7,
        density=True,
        edgecolor="#1e2d4a",
        linewidth=0.3,
        label="Rendements réels",
    )

    # Courbe gaussienne théorique
    mu, sigma = data.mean(), data.std()
    x = np.linspace(data.min(), data.max(), 300)
    gaussian = np.exp(-0.5 * ((x - mu) / sigma) ** 2) / (sigma * np.sqrt(2 * np.pi))
    ax.plot(x, gaussian, color=GOLD, linewidth=1.8, linestyle="--", label="Gaussienne théorique")

    ax.axvline(0, color="#999999", linewidth=0.8)
    ax.axvline(np.percentile(data, 5), color=RED, linewidth=1.2, linestyle=":", label="VaR 95%")

    ax.set_title("Distribution des rendements journaliers", color="#555555", fontsize=8, pad=4)
    ax.set_xlabel("Rendement journalier %", fontsize=7)
    ax.legend(fontsize=7)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.5)
    return fig


def _chart_underwater(dd_data: list) -> object:
    """Underwater plot — drawdown cumulatif style Zipline."""
    if not dd_data:
        return None
    _mpl_style()
    fig, ax = plt.subplots(figsize=(10, 3.0), facecolor="white")
    ax.set_facecolor("#f8f9fa")

    dates = list(range(len(dd_data)))
    values = [d["drawdown"] * 100 for d in dd_data]

    ax.fill_between(dates, values, 0, color=RED, alpha=0.4)
    ax.plot(dates, values, color=RED, linewidth=1.0, alpha=0.8)
    ax.axhline(0, color="#999999", linewidth=0.5)

    # Annoter le max drawdown
    min_dd = min(values)
    min_idx = values.index(min_dd)
    ax.annotate(
        f"Max DD: {min_dd:.1f}%",
        xy=(min_idx, min_dd),
        xytext=(min_idx + len(dates) * 0.05, min_dd * 0.7),
        color="#f87171",
        fontsize=7,
        arrowprops=dict(arrowstyle="->", color="#f87171", lw=0.8),
    )

    ax.set_title("Underwater Plot (Drawdown cumulatif)", color="#555555", fontsize=8, pad=4)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.1f}%"))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.5)
    return fig


def _chart_rolling_beta(rolling_beta: list) -> object:
    """Rolling Beta 252j vs benchmark."""
    if not rolling_beta:
        return None
    _mpl_style()
    fig, ax = plt.subplots(figsize=(10, 3.0), facecolor="white")
    ax.set_facecolor("#f8f9fa")

    dates = list(range(len(rolling_beta)))
    values = [d["beta"] for d in rolling_beta]

    ax.plot(dates, values, color="#8a6f9c", linewidth=1.8)
    ax.axhline(1.0, color=GOLD, linewidth=0.8, linestyle="--", label="Bêta marché = 1")
    ax.axhline(0.0, color="#999999", linewidth=0.5)
    ax.fill_between(
        dates,
        values,
        1.0,
        where=[v > 1 for v in values],
        color=RED,
        alpha=0.15,
        label="Sur-exposition",
    )
    ax.fill_between(
        dates,
        values,
        1.0,
        where=[v <= 1 for v in values],
        color=GREEN,
        alpha=0.15,
        label="Sous-exposition",
    )

    ax.set_title("Rolling Bêta 252j vs Benchmark", color="#555555", fontsize=8, pad=4)
    ax.legend(fontsize=6)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.5)
    return fig


def _chart_win_loss(win_loss_data: dict) -> object:
    """Distribution Win vs Loss."""
    if not win_loss_data:
        return None
    _mpl_style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.5), facecolor="white")
    for ax in [ax1, ax2]:
        ax.set_facecolor("#f8f9fa")

    wins = win_loss_data.get("wins", [])
    losses = win_loss_data.get("losses", [])
    hit_rate = win_loss_data.get("hit_rate", 50)

    if wins:
        ax1.hist(
            wins, bins=50, color=GREEN, alpha=0.7, density=True, edgecolor="#0d1528", linewidth=0.3
        )
        ax1.set_title(f"Jours positifs ({hit_rate:.1f}%)", color="#555555", fontsize=8, pad=4)
        ax1.set_xlabel("Rendement %", fontsize=7)
        ax1.spines[["top", "right"]].set_visible(False)

    if losses:
        ax2.hist(
            losses, bins=50, color=RED, alpha=0.7, density=True, edgecolor="#0d1528", linewidth=0.3
        )
        ax2.set_title(f"Jours négatifs ({100-hit_rate:.1f}%)", color="#555555", fontsize=8, pad=4)
        ax2.set_xlabel("Rendement %", fontsize=7)
        ax2.spines[["top", "right"]].set_visible(False)

    fig.suptitle("Distribution Win/Loss", color="#555555", fontsize=9, y=1.02)
    fig.tight_layout(pad=0.5)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Main PDF builder
# ─────────────────────────────────────────────────────────────────────────────


def _pages_cover_summary(tearsheet: dict, styles: dict, narratives: dict, interpretations: dict) -> list:
    """Auto-extracted PDF page builder."""
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import HRFlowable, PageBreak, Paragraph, Spacer, Table, TableStyle
    title_s = styles['title']; subtitle_s = styles['subtitle']; body_s = styles['body']
    small_s = styles['small']; disclm_s = styles['disclaimer']; bold_s = styles['bold']; section_s = styles['section']; hr = styles['hr']; p = styles['p']; f = styles['f']; e = styles['e']; chart = styles['chart']; tbl_style = styles['tbl_style']; section_s = styles['section']; hr = styles['hr']; p2 = styles['p']; f = styles['f']; e = styles['e']; chart = styles['chart']; tbl_style = styles['tbl_style']
    kpi_s = styles['kpi']; kpi_label_s = styles['kpi_label']
    meta = tearsheet['meta']; m = tearsheet['metrics']
    sig = tearsheet.get('significance', {})
    nav = tearsheet.get('nav_chart', []); bnch = tearsheet.get('benchmark_chart', [])
    dd = tearsheet.get('drawdown_chart', []); cc = tearsheet.get('cost_chart', [])
    ac = tearsheet.get('allocation_chart', []); pos = tearsheet.get('positions', {})
    st_ = tearsheet.get('stress_tests', []); cs = tearsheet.get('cost_summary', {})
    bd = tearsheet.get('cost_breakdown', {})
    S: list = []
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
    ["Métrique", "Valeur", "Interprétation"],
    ["Rendement total", p(m.get("total_return")), interpretations.get("cagr", "")[:90]],
    ["CAGR", p(m.get("cagr")), interpretations.get("cagr", "")[:90]],
    [
        "Volatilité annualisée",
        p(m.get("annualised_volatility")),
        interpretations.get("annualised_volatility", "")[:90],
    ],
    ["Sharpe", f(m.get("sharpe_ratio")), interpretations.get("sharpe_ratio", "")[:90]],
    ["Sortino", f(m.get("sortino_ratio")), interpretations.get("sortino_ratio", "")[:90]],
    ["Calmar", f(m.get("calmar_ratio")), interpretations.get("calmar_ratio", "")[:90]],
    ["Omega", f(m.get("omega_ratio")), "Omega > 1 : les gains dominent les pertes."],
    ["Max Drawdown", p(m.get("max_drawdown")), interpretations.get("max_drawdown", "")[:90]],
    [
        "Average Drawdown",
        p(m.get("average_drawdown")),
        "Niveau de stress habituel du portefeuille.",
    ],
    [
        "Recovery Factor",
        f(m.get("recovery_factor")),
        "RF > 3 : stratégie robuste. RF > 1 : viable.",
    ],
    ]
    if "beta" in m:
        rows += [
        ["Bêta", f(m["beta"]), interpretations.get("beta", "")[:90]],
        [
            "Alpha Jensen",
            p(m.get("alpha_jensen")),
            interpretations.get("alpha_jensen", "")[:90],
        ],
        [
            "Information Ratio",
            f(m.get("information_ratio")),
            "IR > 0.5 : surperformance régulière.",
        ],
    ]
    t = Table(rows, colWidths=[5 * cm, 3 * cm, 9 * cm])
    t.setStyle(tbl_style())
    S += [t, PageBreak()]
    return S


def _pages_performance_charts(tearsheet: dict, styles: dict, narratives: dict, interpretations: dict) -> list:
    """Auto-extracted PDF page builder."""
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import HRFlowable, PageBreak, Paragraph, Spacer, Table, TableStyle
    title_s = styles['title']; subtitle_s = styles['subtitle']; body_s = styles['body']
    small_s = styles['small']; disclm_s = styles['disclaimer']; bold_s = styles['bold']; section_s = styles['section']; hr = styles['hr']; p = styles['p']; f = styles['f']; e = styles['e']; chart = styles['chart']; tbl_style = styles['tbl_style']; section_s = styles['section']; hr = styles['hr']; p2 = styles['p']; f = styles['f']; e = styles['e']; chart = styles['chart']; tbl_style = styles['tbl_style']
    kpi_s = styles['kpi']; kpi_label_s = styles['kpi_label']
    meta = tearsheet['meta']; m = tearsheet['metrics']
    sig = tearsheet.get('significance', {})
    nav = tearsheet.get('nav_chart', []); bnch = tearsheet.get('benchmark_chart', [])
    dd = tearsheet.get('drawdown_chart', []); cc = tearsheet.get('cost_chart', [])
    ac = tearsheet.get('allocation_chart', []); pos = tearsheet.get('positions', {})
    st_ = tearsheet.get('stress_tests', []); cs = tearsheet.get('cost_summary', {})
    bd = tearsheet.get('cost_breakdown', {})
    S: list = []
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

    # PAGE 6b — ROLLING SHARPE + VOL
    rolling_sharpe = tearsheet.get("rolling_sharpe", [])
    rolling_vol = tearsheet.get("rolling_vol", [])
    rolling_beta = tearsheet.get("rolling_beta", [])
    monthly_returns_list = tearsheet.get("monthly_returns_list", [])
    return_distribution = tearsheet.get("return_distribution", [])
    win_loss_data = tearsheet.get("win_loss_data", {})
    dd_chart = tearsheet.get("drawdown_chart", [])

    if rolling_sharpe or rolling_vol:
        S += [
            Paragraph("Métriques glissantes — Sharpe et Volatilité", section_s),
            hr(),
            Spacer(1, 0.3 * cm),
            Paragraph(
                "Le Sharpe glissant (252j) mesure l'évolution de l'efficience de la stratégie "
                "dans le temps. Un Sharpe > 1 de façon stable indique une génération d'alpha "
                "robuste et non liée à un régime de marché particulier. "
                "La volatilité glissante (63j) permet d'identifier les périodes de stress.",
                body_s,
            ),
            Spacer(1, 0.3 * cm),
    ]
    if rolling_sharpe:
        S += [chart(_chart_rolling_sharpe(rolling_sharpe)), Spacer(1, 0.3 * cm)]
    if rolling_vol:
        S += [chart(_chart_rolling_vol(rolling_vol)), Spacer(1, 0.3 * cm)]
    S += [PageBreak()]

    # PAGE 6c — MONTHLY HEATMAP
    if monthly_returns_list:
        S += [
            Paragraph("Heatmap des rendements mensuels", section_s),
            hr(),
            Spacer(1, 0.3 * cm),
            Paragraph(
                "La heatmap affiche le rendement de chaque mois de l'année (rouge = perte, "
                "vert = gain). Elle permet d'identifier les saisonnalités, les années "
                "difficiles et la régularité de la stratégie dans le temps. "
                "Une stratégie robuste présente une majorité de cellules vertes "
                "sans concentration des pertes sur un seul mois ou une seule année.",
                body_s,
            ),
            Spacer(1, 0.3 * cm),
            chart(_chart_monthly_heatmap(monthly_returns_list), width_cm=17.0),
            PageBreak(),
    ]

    # PAGE 6d — RETURN DISTRIBUTION
    if return_distribution:
        S += [
            Paragraph("Distribution des rendements journaliers", section_s),
            hr(),
            Spacer(1, 0.3 * cm),
            Paragraph(
                "L'histogramme compare la distribution réelle des rendements journaliers "
                "à la distribution gaussienne théorique (pointillés dorés). "
                "Un excès de kurtosis positif (queues épaisses) signifie que les événements "
                "extrêmes sont plus fréquents que prévu par la loi normale — "
                "ce que les modèles VaR paramétriques sous-estiment systématiquement. "
                "La ligne rouge indique la VaR historique à 95%.",
                body_s,
            ),
            Spacer(1, 0.3 * cm),
            chart(_chart_return_distribution(return_distribution)),
            PageBreak(),
    ]

    # PAGE 6e — UNDERWATER + ROLLING BETA
    S += [
    Paragraph("Underwater Plot et Bêta glissant", section_s),
    hr(),
    Spacer(1, 0.3 * cm),
    Paragraph(
        "L'Underwater Plot (ou 'drawdown cumulatif') montre les périodes pendant lesquelles "
        "le portefeuille est en dessous de son plus haut historique. La profondeur "
        "indique l'ampleur de la perte latente, la largeur indique la durée de récupération. "
        "Le Bêta glissant mesure l'exposition au risque systématique (marché) dans le temps. "
        "Un Bêta > 1 indique une sur-exposition au marché, < 1 une sous-exposition.",
        body_s,
    ),
    Spacer(1, 0.3 * cm),
    ]
    if dd_chart:
        S += [chart(_chart_underwater(dd_chart)), Spacer(1, 0.3 * cm)]
        if rolling_beta:
            S += [chart(_chart_rolling_beta(rolling_beta))]
        S += [PageBreak()]

    # PAGE 6f — WIN/LOSS DISTRIBUTION
    if win_loss_data:
        S += [
            Paragraph("Distribution Win / Loss", section_s),
            hr(),
            Spacer(1, 0.3 * cm),
            Paragraph(
                "La distribution des jours positifs (gauche) et négatifs (droite) permet "
                "d'analyser l'asymétrie des rendements. Une stratégie idéale présente "
                "des gains plus grands que les pertes (profit factor > 1) même avec "
                "un taux de réussite modéré. Le taux de réussite seul est insuffisant : "
                "une stratégie avec 40% de gains peut être très profitable si les gains "
                "sont en moyenne 2× plus grands que les pertes.",
                body_s,
            ),
            Spacer(1, 0.3 * cm),
            chart(_chart_win_loss(win_loss_data)),
            PageBreak(),
    ]


    return S


def _pages_costs_allocation(tearsheet: dict, styles: dict, narratives: dict, interpretations: dict) -> list:
    """Auto-extracted PDF page builder."""
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import HRFlowable, PageBreak, Paragraph, Spacer, Table, TableStyle
    title_s = styles['title']; subtitle_s = styles['subtitle']; body_s = styles['body']
    small_s = styles['small']; disclm_s = styles['disclaimer']; bold_s = styles['bold']; section_s = styles['section']; hr = styles['hr']; p = styles['p']; f = styles['f']; e = styles['e']; chart = styles['chart']; tbl_style = styles['tbl_style']; section_s = styles['section']; hr = styles['hr']; p2 = styles['p']; f = styles['f']; e = styles['e']; chart = styles['chart']; tbl_style = styles['tbl_style']
    kpi_s = styles['kpi']; kpi_label_s = styles['kpi_label']
    meta = tearsheet['meta']; m = tearsheet['metrics']
    sig = tearsheet.get('significance', {})
    nav = tearsheet.get('nav_chart', []); bnch = tearsheet.get('benchmark_chart', [])
    dd = tearsheet.get('drawdown_chart', []); cc = tearsheet.get('cost_chart', [])
    ac = tearsheet.get('allocation_chart', []); pos = tearsheet.get('positions', {})
    st_ = tearsheet.get('stress_tests', []); cs = tearsheet.get('cost_summary', {})
    bd = tearsheet.get('cost_breakdown', {})
    S: list = []
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
    ["Commissions courtage", e(bd.get("commission"))],
    ["Slippage bid-ask", e(bd.get("slippage"))],
    ["Impact marché", e(bd.get("market_impact"))],
    [_LABEL_SPREAD_FX, e(bd.get("fx_spread"))],
    ["TTF (Tobin Tax FR)", e(bd.get("ttf"))],
    ["Stamp Duty (UK/BE/IT)", e(bd.get("stamp_duty"))],
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
    return S


def _pages_analysis(tearsheet: dict, styles: dict, narratives: dict, interpretations: dict) -> list:
    """Auto-extracted PDF page builder."""
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import HRFlowable, PageBreak, Paragraph, Spacer, Table, TableStyle
    title_s = styles['title']; subtitle_s = styles['subtitle']; body_s = styles['body']
    small_s = styles['small']; disclm_s = styles['disclaimer']; bold_s = styles['bold']; section_s = styles['section']; hr = styles['hr']; p = styles['p']; f = styles['f']; e = styles['e']; chart = styles['chart']; tbl_style = styles['tbl_style']; section_s = styles['section']; hr = styles['hr']; p2 = styles['p']; f = styles['f']; e = styles['e']; chart = styles['chart']; tbl_style = styles['tbl_style']
    kpi_s = styles['kpi']; kpi_label_s = styles['kpi_label']
    meta = tearsheet['meta']; m = tearsheet['metrics']
    sig = tearsheet.get('significance', {})
    nav = tearsheet.get('nav_chart', []); bnch = tearsheet.get('benchmark_chart', [])
    dd = tearsheet.get('drawdown_chart', []); cc = tearsheet.get('cost_chart', [])
    ac = tearsheet.get('allocation_chart', []); pos = tearsheet.get('positions', {})
    st_ = tearsheet.get('stress_tests', []); cs = tearsheet.get('cost_summary', {})
    bd = tearsheet.get('cost_breakdown', {})
    S: list = []
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
                "Tous les coûts réels (commission, slippage, impact marché, TTF, stamp duty, spread FX) sont inclus.",
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


    return S




def _pages_islamic_finance(tearsheet: dict, styles: dict, narratives: dict, interpretations: dict) -> list:
    """Page Finance Islamique — Conformite AAOIFI."""
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import HRFlowable, PageBreak, Paragraph, Spacer, Table, TableStyle

    title_s = styles['title']; subtitle_s = styles['subtitle']; body_s = styles['body']
    small_s = styles['small']; section_s = styles['section']; bold_s = styles['bold']
    tbl_style = styles['tbl_style']

    S = []
    meta = tearsheet.get('meta', {})
    tickers = meta.get('tickers', [])
    screening = tearsheet.get('screening', {})

    S += [
        Paragraph("Finance Islamique — Conformite AAOIFI", title_s),
        HRFlowable(width="100%", thickness=2, color=colors.HexColor(GOLD)),
        Spacer(1, 0.3 * cm),
        Paragraph(
            "Analyse de conformite aux standards AAOIFI (Accounting and Auditing Organisation "
            "for Islamic Financial Institutions). Quatre criteres cumulatifs obligatoires.",
            body_s
        ),
        Spacer(1, 0.4 * cm),
    ]

    # Tableau des criteres AAOIFI
    CRITERIA = [
        ("1", "Secteur d'activite",
         "Exclusion des secteurs non-conformes : alcool, tabac, armement, jeux, intérets.",
         "Blacklist sectorielle"),
        ("2", "Ratio dette portant interets",
         "Dette ST + LT / capitalisation boursiere <= 33%.",
         "ESEF / SEC EDGAR"),
        ("3", "Ratio liquidites portant interets",
         "Tresorerie + actifs financiers / capitalisation <= 33%.",
         "ESEF / SEC EDGAR"),
        ("4", "Revenus non-permissibles",
         "Revenus haram / chiffre d'affaires total <= 5%.",
         "Segments ESEF / Rapports annuels"),
    ]

    header = ["Critere", "Nom", "Description", "Source"]
    rows = [header] + [[c[0], c[1], c[2], c[3]] for c in CRITERIA]
    t = Table(rows, colWidths=[1.2*cm, 4.5*cm, 9.0*cm, 3.5*cm])
    ts = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor(NAVY)),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.HexColor("#f0f4f8"), colors.white]),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ])
    t.setStyle(ts)
    S += [t, Spacer(1, 0.5*cm)]

    # Resultats par ticker
    if tickers and screening:
        S += [
            Paragraph("Resultats par titre", section_s),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
            Spacer(1, 0.3*cm),
        ]

        ticker_header = ["Ticker", "Conformite", "C1 Secteur", "C2 Dette", "C3 Liquidites", "C4 Revenus", "Details"]
        ticker_rows = [ticker_header]

        for ticker in tickers:
            info = screening.get(ticker, {})
            is_sharia = info.get('is_sharia')
            sharia = info.get('sharia', {})
            checks = sharia.get('checks', [])

            verdict = "CONFORME" if is_sharia else ("NON CONFORME" if is_sharia is False else "N/D")

            def get_check(n):
                c = next((x for x in checks if x.get('name','').startswith(str(n)+'.')), None)
                if not c:
                    return "N/D"
                return "OK" if c.get('passed') else "KO"

            # Details critere 4
            haram = info.get('haram_revenue_ratio')
            debt  = info.get('sharia_debt_ratio')
            detail = ""
            if haram is not None:
                detail += f"Haram: {haram*100:.1f}% "
            if debt is not None:
                detail += f"Dette: {debt*100:.1f}%"

            ticker_rows.append([
                ticker,
                verdict,
                get_check(1),
                get_check(2),
                get_check(3),
                get_check(4),
                detail or "—",
            ])

        # Couleurs conditionnelles
        style_cmds = [
            ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor(NAVY)),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]
        for i, row in enumerate(ticker_rows[1:], 1):
            verdict = row[1]
            if verdict == "CONFORME":
                style_cmds.append(("BACKGROUND", (1, i), (1, i), colors.HexColor("#d4edda")))
                style_cmds.append(("TEXTCOLOR",  (1, i), (1, i), colors.HexColor("#155724")))
            elif verdict == "NON CONFORME":
                style_cmds.append(("BACKGROUND", (1, i), (1, i), colors.HexColor("#f8d7da")))
                style_cmds.append(("TEXTCOLOR",  (1, i), (1, i), colors.HexColor("#721c24")))
            # Couleurs OK/KO
            for col in range(2, 6):
                val = row[col]
                if val == "OK":
                    style_cmds.append(("TEXTCOLOR", (col, i), (col, i), colors.HexColor("#155724")))
                elif val == "KO":
                    style_cmds.append(("TEXTCOLOR", (col, i), (col, i), colors.HexColor("#721c24")))
            # Alternance lignes
            if i % 2 == 0:
                style_cmds.append(("BACKGROUND", (0, i), (0, i), colors.HexColor("#f0f4f8")))
                style_cmds.append(("BACKGROUND", (2, i), (-1, i), colors.HexColor("#f0f4f8")))

        tt = Table(ticker_rows, colWidths=[2.0*cm, 2.8*cm, 2.0*cm, 2.0*cm, 2.5*cm, 2.5*cm, 4.4*cm])
        tt.setStyle(TableStyle(style_cmds))
        S += [tt, Spacer(1, 0.5*cm)]

    # Note methodologique
    S += [
        Paragraph("Note methodologique", section_s),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD)),
        Spacer(1, 0.2*cm),
        Paragraph(
            "<b>Sources des donnees :</b> Les donnees de conformite proviennent de "
            "filings ESEF (European Single Electronic Format) via filings.xbrl.org, "
            "des declarations SEC EDGAR pour les societes US, et des rapports annuels "
            "publics pour les donnees de segments de revenus non couvertes par les "
            "taxonomies standard.",
            body_s
        ),
        Spacer(1, 0.2*cm),
        Paragraph(
            "<b>Limites :</b> Les donnees de segments sont mises a jour annuellement "
            "apres la publication des rapports annuels. Les ratios de dette et de "
            "liquidites sont actualises hebdomadairement. La conformite Finance Islamique "
            "ne constitue pas un avis juridique ou religieux.",
            body_s
        ),
        Spacer(1, 0.2*cm),
        Paragraph(
            "<b>Reference :</b> AAOIFI — Accounting and Auditing Organisation for "
            "Islamic Financial Institutions. Standards FAS et Governance Standards.",
            small_s
        ),
        PageBreak(),
    ]

    return S

def _pages_methodology(tearsheet: dict, styles: dict, narratives: dict, interpretations: dict) -> list:
    """Auto-extracted PDF page builder."""
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import HRFlowable, PageBreak, Paragraph, Spacer, Table, TableStyle
    title_s = styles['title']; subtitle_s = styles['subtitle']; body_s = styles['body']
    small_s = styles['small']; disclm_s = styles['disclaimer']; bold_s = styles['bold']; section_s = styles['section']; hr = styles['hr']; p = styles['p']; f = styles['f']; e = styles['e']; chart = styles['chart']; tbl_style = styles['tbl_style']; section_s = styles['section']; hr = styles['hr']; p2 = styles['p']; f = styles['f']; e = styles['e']; chart = styles['chart']; tbl_style = styles['tbl_style']
    kpi_s = styles['kpi']; kpi_label_s = styles['kpi_label']
    meta = tearsheet['meta']; m = tearsheet['metrics']
    sig = tearsheet.get('significance', {})
    nav = tearsheet.get('nav_chart', []); bnch = tearsheet.get('benchmark_chart', [])
    dd = tearsheet.get('drawdown_chart', []); cc = tearsheet.get('cost_chart', [])
    ac = tearsheet.get('allocation_chart', []); pos = tearsheet.get('positions', {})
    st_ = tearsheet.get('stress_tests', []); cs = tearsheet.get('cost_summary', {})
    bd = tearsheet.get('cost_breakdown', {})
    S: list = []
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


    return S

def generate_pdf(tearsheet: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )


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
    bold_s = st("Bd", fontSize=9, textColor=colors.black, fontName="Helvetica-Bold", leading=12)

    kpi_s = st("K", fontSize=22, textColor=colors.HexColor(GOLD), fontName="Helvetica-Bold", spaceAfter=0)
    kpi_label_s = st("KL", fontSize=7, textColor=colors.HexColor(GREY), fontName="Helvetica", spaceAfter=2)




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






    buf = io.BytesIO()


    _base_styles = getSampleStyleSheet()

    def st(name, **kw):
        return ParagraphStyle(name, parent=_base_styles["Normal"], **kw)

    def hr():
        return HRFlowable(width="100%", thickness=1, color=colors.HexColor(GOLD))

    def p(v):
        return "N/A" if v is None else f"{v*100:+.2f}%"

    def f(v, d=2):
        return "N/A" if v is None else f"{v:.{d}f}"

    def e(v):
        return "N/A" if v is None else f"{v:,.2f} €".replace(",", " ")

    def chart(fig, width_cm: float = 17.0, aspect: float = 0.40):
        """Convertit une figure matplotlib en Flowable ReportLab."""
        if fig is None:
            return Spacer(1, 0.1 * cm)
        return _fig_to_image_flowable(fig, width_cm)

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





    # Dict custom passe aux sous-fonctions _pages_*
    styles = {
        "title":      title_s,
        "subtitle":   subtitle_s,
        "section":    section_s,
        "body":       body_s,
        "small":      small_s,
        "disclaimer": disclm_s,
        "bold":       bold_s,
        "kpi":        kpi_s,
        "kpi_label":  kpi_label_s,
        "hr":         hr,
        "p":          p,
        "f":          f,
        "e":          e,
        "chart":      chart,
        "tbl_style":  tbl_style,
    }


    meta = tearsheet["meta"]
    narratives = generate_all_narratives(tearsheet)
    m = tearsheet["metrics"]
    interpretations = generate_metric_interpretations(m)
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
    S += _pages_cover_summary(tearsheet, styles, narratives, interpretations)
    S += _pages_performance_charts(tearsheet, styles, narratives, interpretations)
    S += _pages_costs_allocation(tearsheet, styles, narratives, interpretations)
    S += _pages_analysis(tearsheet, styles, narratives, interpretations)
    S += _pages_islamic_finance(tearsheet, styles, narratives, interpretations)
    S += _pages_methodology(tearsheet, styles, narratives, interpretations)
    doc.build(S)
    return buf.getvalue()
