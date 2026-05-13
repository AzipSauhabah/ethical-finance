"""
:file: api/report/pdf.py
:brief: Goldman Sachs–style multi-page PDF tearsheet using ReportLab.

        Pages:
        1. Cover — title, disclaimer, date
        2. Executive summary — key metrics table
        3. NAV & drawdown charts
        4. Risk metrics (VaR, CVaR, vol)
        5. Stress test results
        6. Trade log summary
        7. Cost breakdown
        8. Monte Carlo projection
        9. Statistical significance
        10. Glossary

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import io
from datetime import date
from typing import Any

from api.config import COPYRIGHT, DISCLAIMER
from api.report.glossary import GLOSSARY

# Colour palette (GS inspired: dark navy + gold)
_NAVY  = (0.08, 0.12, 0.22)
_GOLD  = (0.75, 0.62, 0.25)
_WHITE = (1.0,  1.0,  1.0)
_LIGHT = (0.95, 0.95, 0.97)
_DARK  = (0.12, 0.12, 0.12)
_RED   = (0.72, 0.15, 0.15)
_GREEN = (0.13, 0.55, 0.25)


def generate_pdf(tearsheet: dict, mc_result: dict | None = None) -> bytes:
    """Generate a professional multi-page PDF report.

    :param tearsheet: output of :func:`api.report.tearsheet.build_tearsheet`
    :param mc_result: optional Monte Carlo results dict
    :returns: raw PDF bytes
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm, mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            PageBreak, HRFlowable,
        )
        from reportlab.graphics.shapes import Drawing, Rect, String
        from reportlab.graphics.charts.lineplots import LinePlot
        from reportlab.graphics import renderPDF
    except ImportError:
        raise ImportError("reportlab is required: pip install reportlab")

    buf    = io.BytesIO()
    W, H   = A4
    MARGIN = 2 * cm

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN,
    )

    styles = getSampleStyleSheet()

    def _style(name: str, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    title_style    = _style("Title",    fontSize=22, textColor=colors.Color(*_NAVY), spaceAfter=6, fontName="Helvetica-Bold")
    sub_style      = _style("Sub",      fontSize=11, textColor=colors.Color(*_GOLD), spaceAfter=4, fontName="Helvetica")
    body_style     = _style("Body",     fontSize=8.5, textColor=colors.Color(*_DARK), spaceAfter=3)
    section_style  = _style("Section",  fontSize=12, textColor=colors.Color(*_NAVY), spaceAfter=4, fontName="Helvetica-Bold")
    small_style    = _style("Small",    fontSize=7,  textColor=colors.Color(0.4, 0.4, 0.4))
    disclm_style   = _style("Disclm",   fontSize=6.5, textColor=colors.Color(0.5, 0.5, 0.5), spaceAfter=3)

    def _navy_table_style(has_header: bool = True) -> TableStyle:
        cmds = [
            ("BACKGROUND", (0, 0), (-1, 0 if has_header else -1), colors.Color(*_NAVY)),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white if has_header else colors.Color(*_DARK)),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.Color(*_LIGHT), colors.white]),
            ("GRID",       (0, 0), (-1, -1), 0.3, colors.Color(0.8, 0.8, 0.8)),
            ("LEFTPADDING",  (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING",   (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ]
        return TableStyle(cmds)

    def _fmt_pct(v: float | None) -> str:
        if v is None: return "N/A"
        return f"{v*100:+.2f}%"

    def _fmt_f(v: float | None, dec: int = 2) -> str:
        if v is None: return "N/A"
        return f"{v:.{dec}f}"

    meta    = tearsheet.get("meta", {})
    metrics = tearsheet.get("metrics", {})
    stress  = tearsheet.get("stress_tests", [])
    costs   = tearsheet.get("cost_summary", {})
    sig     = tearsheet.get("significance", {})
    strat   = meta.get("strategy", "Stratégie")
    gen_dt  = meta.get("generated_at", str(date.today()))

    story: list[Any] = []

    # ── Page 1: Cover ──────────────────────────────────────────────────────
    story += [
        Spacer(1, 3 * cm),
        HRFlowable(width="100%", thickness=3, color=colors.Color(*_GOLD)),
        Spacer(1, 0.5 * cm),
        Paragraph("ETHICAL FINANCE PLATFORM", title_style),
        Paragraph(f"Rapport de Performance — {strat}", sub_style),
        Spacer(1, 0.3 * cm),
        Paragraph(f"Généré le {gen_dt}", body_style),
        Spacer(1, 2 * cm),
        HRFlowable(width="100%", thickness=1, color=colors.Color(*_NAVY)),
        Spacer(1, 0.5 * cm),
        Paragraph(DISCLAIMER, disclm_style),
        Paragraph(COPYRIGHT, small_style),
        PageBreak(),
    ]

    # ── Page 2: Executive summary ──────────────────────────────────────────
    story.append(Paragraph("Résumé des Performances", section_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.Color(*_GOLD)))
    story.append(Spacer(1, 0.3 * cm))

    summary_data = [
        ["Métrique", "Valeur"],
        ["Rendement total",            _fmt_pct(metrics.get("total_return"))],
        ["CAGR",                       _fmt_pct(metrics.get("cagr"))],
        ["Volatilité annualisée",      _fmt_pct(metrics.get("annualised_volatility"))],
        ["Ratio de Sharpe",            _fmt_f(metrics.get("sharpe_ratio"))],
        ["Ratio de Sortino",           _fmt_f(metrics.get("sortino_ratio"))],
        ["Ratio de Calmar",            _fmt_f(metrics.get("calmar_ratio"))],
        ["Max Drawdown",               _fmt_pct(metrics.get("max_drawdown"))],
        ["VaR 95 % (1 jour)",          _fmt_pct(metrics.get("var_95"))],
        ["CVaR 95 %",                  _fmt_pct(metrics.get("cvar_95"))],
        ["Taux de succès",             _fmt_pct(metrics.get("hit_rate"))],
        ["Facteur de profit",          _fmt_f(metrics.get("profit_factor"))],
        ["Bêta",                       _fmt_f(metrics.get("beta"))],
        ["Alpha de Jensen (annuel)",   _fmt_pct(metrics.get("alpha_jensen"))],
        ["Ratio d'information",        _fmt_f(metrics.get("information_ratio"))],
    ]

    tbl = Table(summary_data, colWidths=[10 * cm, 6 * cm])
    tbl.setStyle(_navy_table_style())
    story += [tbl, Spacer(1, 0.5 * cm), PageBreak()]

    # ── Page 3: Stress tests ───────────────────────────────────────────────
    story.append(Paragraph("Tests de Résistance", section_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.Color(*_GOLD)))
    story.append(Spacer(1, 0.3 * cm))

    stress_data = [["Scénario", "Rendement", "Max DD", "Volatilité", "VaR 95%", "Sharpe"]]
    for s in stress:
        stress_data.append([
            s.get("label", s.get("scenario", "")),
            _fmt_pct(s.get("total_return")),
            _fmt_pct(s.get("max_drawdown")),
            _fmt_pct(s.get("volatility")),
            _fmt_pct(s.get("var_95")),
            _fmt_f(s.get("sharpe")),
        ])

    stbl = Table(stress_data, colWidths=[5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm])
    stbl.setStyle(_navy_table_style())
    story += [stbl, Spacer(1, 0.5 * cm), PageBreak()]

    # ── Page 4: Costs ──────────────────────────────────────────────────────
    story.append(Paragraph("Analyse des Coûts", section_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.Color(*_GOLD)))
    story.append(Spacer(1, 0.3 * cm))

    cost_data = [
        ["Poste", "Montant (EUR)"],
        ["Commissions courtier", f"{costs.get('total_costs_eur', 0):.2f} €"],
        ["Taxes (PFU/TTF)",      f"{costs.get('total_taxes_eur', 0):.2f} €"],
        ["Coût total / NAV",     _fmt_pct(costs.get("cost_pct_nav"))],
    ]
    ctbl = Table(cost_data, colWidths=[10*cm, 6*cm])
    ctbl.setStyle(_navy_table_style())
    story += [ctbl, Spacer(1, 0.5 * cm), PageBreak()]

    # ── Page 5: Statistical significance ──────────────────────────────────
    if sig:
        story.append(Paragraph("Significativité Statistique", section_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.Color(*_GOLD)))
        story.append(Spacer(1, 0.3 * cm))

        jk = sig.get("jobson_korkie", {})
        at = sig.get("alpha_ttest", {})
        sb = sig.get("sharpe_bootstrap_95ci", [None, None])
        sig_data = [
            ["Test", "Statistique", "p-value", "Significatif (5%)"],
            ["Jobson-Korkie (Sharpe diff.)", _fmt_f(jk.get("z")), _fmt_f(jk.get("p"), 4),
             "✓ Oui" if jk.get("significant") else "✗ Non"],
            ["Alpha de Jensen (t-test)",     _fmt_f(at.get("t")), _fmt_f(at.get("p"), 4),
             "✓ Oui" if at.get("significant") else "✗ Non"],
            ["IC Bootstrap Sharpe 95%", f"[{_fmt_f(sb[0])}, {_fmt_f(sb[1])}]", "—", "—"],
        ]
        stbl2 = Table(sig_data, colWidths=[7*cm, 3*cm, 3*cm, 4*cm])
        stbl2.setStyle(_navy_table_style())
        story += [stbl2, Spacer(1, 0.5 * cm), PageBreak()]

    # ── Page 6: Glossary ───────────────────────────────────────────────────
    story.append(Paragraph("Glossaire Financier", section_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.Color(*_GOLD)))
    story.append(Spacer(1, 0.3 * cm))

    for entry in GLOSSARY:
        story.append(
            Paragraph(
                f"<b>{entry['term']}</b> <i>({entry['fr']})</i> — {entry['def']}",
                body_style,
            )
        )
    story += [Spacer(1, 0.5 * cm), Paragraph(DISCLAIMER, disclm_style), Paragraph(COPYRIGHT, small_style)]

    doc.build(story)
    return buf.getvalue()
