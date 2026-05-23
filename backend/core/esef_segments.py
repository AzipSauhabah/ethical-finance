"""
:file: backend/core/esef_segments.py
:brief: Extrait les revenus par segment depuis les rapports annuels ESEF/iXBRL
        déposés sur info-financiere.gouv.fr (OAM français, directive Transparence UE).

        Pipeline :
        1. Recherche le dernier rapport financier annuel via l'API info-financiere.gouv.fr
        2. Télécharge le fichier ZIP ESEF
        3. Extrait le fichier .xhtml (iXBRL)
        4. Parse les balises ix:nonFraction / ix:nonNumeric avec dimension segment
        5. Retourne dict {segment_name: fraction_du_CA}

        Couverture : toutes sociétés cotées sur Euronext Paris (CAC40, SBF120, etc.)
        License des données : Licence Ouverte Etalab 2.0 (réutilisation libre)

        Références :
        - API : https://www.info-financiere.gouv.fr/api/explore/v2.1/
        - ESEF RTS ESMA : règlement délégué 2019/815
        - IFRS 8 : Operating Segments (balises ifrs-full:Revenue avec SegmentsAxis)

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from typing import Optional
from xml.etree import ElementTree as ET

import httpx

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Config API info-financiere.gouv.fr
# ─────────────────────────────────────────────────────────────────────────────

_API_BASE    = "https://www.info-financiere.gouv.fr/api/explore/v2.1"
_DATASET     = "flux-de-documents-info-financiere"
_TIMEOUT     = 30.0
_USER_AGENT  = "ethical-finance-platform contact@sauhabah-advisory.eu"

# Namespaces iXBRL / XBRL
_NS = {
    "ix":       "http://www.xbrl.org/2013/inlineXBRL",
    "xbrli":    "http://www.xbrl.org/2003/instance",
    "ifrs-full":"https://xbrl.ifrs.org/taxonomy/2023-03-23/ifrs-full",
    "link":     "http://www.xbrl.org/2003/linkbase",
    "xlink":    "http://www.w3.org/1999/xlink",
}

# Concepts IFRS qui portent les revenus par segment
_REVENUE_CONCEPTS = {
    "ifrs-full:Revenue",
    "ifrs-full:RevenueFromContractsWithCustomers",
    "ifrs-full:SalesAndOtherOperatingRevenue",
    "ifrs-full:RevenueFromSaleOfGoods",
    "ifrs-full:RevenueFromRenderingOfServices",
}

# Axes de dimension indiquant une décomposition par segment produit/activité
_SEGMENT_AXES = {
    "ifrs-full:SegmentsAxis",
    "ifrs-full:ProductsAndServicesAxis",
    "ifrs-full:TypesOfContractsAxis",
}


# ─────────────────────────────────────────────────────────────────────────────
# Étape 1 : Recherche du rapport annuel via l'API OAM
# ─────────────────────────────────────────────────────────────────────────────

async def _find_annual_report_url(company_name: str) -> Optional[str]:
    """
    Cherche le dernier rapport financier annuel ESEF pour une société.

    Args:
        company_name: Nom ou fragment du nom de la société (ex: "LVMH", "TOTALENERGIES")

    Returns:
        URL de téléchargement du fichier ZIP ESEF, ou None si introuvable.
    """
    params = {
        "where": f'emetteur_nom like "%{company_name.upper()}%" and type_document="Rapport financier annuel"',
        "order_by": "date_depot desc",
        "limit": 1,
        "select": "url_document,emetteur_nom,date_depot,type_document",
    }

    url = f"{_API_BASE}/catalog/datasets/{_DATASET}/records"

    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        log.warning("info-financiere.gouv.fr search failed for '%s': %s", company_name, exc)
        return None

    records = data.get("results", [])
    if not records:
        log.debug("No annual report found for '%s' on info-financiere.gouv.fr", company_name)
        return None

    doc_url = records[0].get("url_document")
    emetteur = records[0].get("emetteur_nom", "?")
    date     = records[0].get("date_depot", "?")
    log.info("ESEF report found: %s — %s — %s", emetteur, date, doc_url)
    return doc_url


# ─────────────────────────────────────────────────────────────────────────────
# Étape 2 : Téléchargement et extraction du ZIP ESEF
# ─────────────────────────────────────────────────────────────────────────────

async def _download_esef_zip(url: str) -> Optional[bytes]:
    """Télécharge le fichier ZIP ESEF."""
    try:
        async with httpx.AsyncClient(
            timeout=60.0,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content
    except Exception as exc:
        log.warning("ESEF ZIP download failed (%s): %s", url, exc)
        return None


def _extract_xhtml_from_zip(zip_bytes: bytes) -> Optional[str]:
    """
    Extrait le contenu du fichier .xhtml principal depuis le ZIP ESEF.
    Le ZIP peut contenir plusieurs fichiers ; on cherche le .xhtml le plus gros
    (c'est le rapport principal, pas les annexes).
    """
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            xhtml_files = [
                name for name in zf.namelist()
                if name.lower().endswith((".xhtml", ".htm", ".html"))
                and not name.startswith("__MACOSX")
            ]

            if not xhtml_files:
                log.debug("No .xhtml file found in ESEF ZIP")
                return None

            # Prend le plus gros fichier (= rapport principal)
            xhtml_files.sort(
                key=lambda n: zf.getinfo(n).file_size,
                reverse=True,
            )
            main_file = xhtml_files[0]
            log.debug("Extracting ESEF file: %s", main_file)
            return zf.read(main_file).decode("utf-8", errors="replace")

    except zipfile.BadZipFile:
        # Certains dépôts sont directement des .xhtml, pas des ZIP
        try:
            return zip_bytes.decode("utf-8", errors="replace")
        except Exception:
            return None
    except Exception as exc:
        log.warning("ESEF ZIP extraction failed: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Étape 3 : Parsing iXBRL — extraction des segments
# ─────────────────────────────────────────────────────────────────────────────

def _parse_ixbrl_segments(xhtml_content: str) -> dict[str, float]:
    """
    Parse un fichier iXBRL et extrait les revenus par segment.

    Stratégie :
    1. Parse le XML/HTML
    2. Cherche les balises ix:nonFraction avec name= un concept revenue
    3. Filtre celles qui ont un contextRef lié à un axe segment
    4. Regroupe par segment, normalise en fractions

    Returns:
        Dict {segment_name: fraction} ou {} si aucun segment trouvé.
    """
    # Nettoie le contenu pour le rendre parsable par ElementTree
    # (supprime les entités HTML non-standard)
    content = _sanitize_xhtml(xhtml_content)

    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        log.debug("XML parse error in ESEF file: %s", exc)
        # Tentative de parsing partiel via regex
        return _parse_ixbrl_segments_regex(xhtml_content)

    # ── Collecte les contextes avec dimension segment ─────────────────────────
    segment_contexts = _extract_segment_contexts(root)
    if not segment_contexts:
        log.debug("No segment contexts found in iXBRL")
        return _parse_ixbrl_segments_regex(xhtml_content)

    # ── Cherche les valeurs de revenus dans ces contextes ─────────────────────
    segment_revenues: dict[str, float] = {}

    # Namespace-aware search pour ix:nonFraction
    for elem in root.iter():
        local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if local != "nonFraction":
            continue

        concept = elem.get("name", "")
        if not _is_revenue_concept(concept):
            continue

        context_ref = elem.get("contextRef", "")
        if context_ref not in segment_contexts:
            continue

        segment_name = segment_contexts[context_ref]
        text = (elem.text or "").strip().replace(",", "").replace("\xa0", "")

        # Gestion du signe (certaines valeurs sont négatives dans iXBRL)
        sign   = elem.get("sign", "")
        scale  = int(elem.get("scale", "0") or "0")

        try:
            value = float(text) * (10 ** scale)
            if sign == "-":
                value = -value
            if value > 0:
                # En cas de doublons, garde le max (plusieurs périodes)
                segment_revenues[segment_name] = max(
                    segment_revenues.get(segment_name, 0), value
                )
        except (ValueError, TypeError):
            continue

    if not segment_revenues:
        return {}

    # Normalise en fractions
    total = sum(segment_revenues.values())
    if total <= 0:
        return {}

    return {k: v / total for k, v in segment_revenues.items()}


def _extract_segment_contexts(root: ET.Element) -> dict[str, str]:
    """
    Parcourt les éléments <xbrli:context> et retourne un dict
    {context_id: segment_member_label} pour les contextes avec dimension segment.
    """
    contexts: dict[str, str] = {}

    for elem in root.iter():
        local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if local != "context":
            continue

        context_id = elem.get("id", "")
        if not context_id:
            continue

        # Cherche les dimensions explicites (xbrli:segment / xbrldi:explicitMember)
        for child in elem.iter():
            child_local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if child_local != "explicitMember":
                continue

            dimension = child.get("dimension", "")
            if not _is_segment_axis(dimension):
                continue

            member = (child.text or "").strip()
            if member:
                label = _clean_member_label(member)
                contexts[context_id] = label
                break

    return contexts


def _is_revenue_concept(concept: str) -> bool:
    """Vérifie si le concept XBRL est un concept de revenu."""
    concept_lower = concept.lower()
    return any(
        rc.lower() in concept_lower or concept_lower in rc.lower()
        for rc in _REVENUE_CONCEPTS
    ) or "revenue" in concept_lower or "turnover" in concept_lower


def _is_segment_axis(dimension: str) -> bool:
    """Vérifie si la dimension est un axe segment."""
    dim_lower = dimension.lower()
    return (
        any(sa.lower() in dim_lower for sa in _SEGMENT_AXES)
        or "segment" in dim_lower
        or "product" in dim_lower
        or "activity" in dim_lower
        or "activit" in dim_lower  # français
        or "branche" in dim_lower
        or "secteur" in dim_lower
    )


def _clean_member_label(member: str) -> str:
    """
    Convertit un membre XBRL en label lisible.
    Ex: "ifrs-full:WinesAndSpiritsMember" → "Wines And Spirits"
        "company:ModeFemmeSegmentMember" → "Mode Femme Segment"
    """
    if ":" in member:
        member = member.split(":")[-1]
    if member.endswith("Member"):
        member = member[:-6]
    if member.endswith("Segment"):
        member = member[:-7]

    # CamelCase → mots séparés
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", member)
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
    return spaced.strip()


def _sanitize_xhtml(content: str) -> str:
    """Nettoie le XHTML pour le rendre parsable par ElementTree."""
    # Supprime la déclaration XML si présente (peut causer des problèmes d'encoding)
    content = re.sub(r"<\?xml[^>]+\?>", "", content)
    # Remplace les entités HTML non-définies dans XML
    entities = {"&nbsp;": "&#160;", "&euro;": "&#8364;", "&copy;": "&#169;"}
    for ent, rep in entities.items():
        content = content.replace(ent, rep)
    return content


# ─────────────────────────────────────────────────────────────────────────────
# Fallback regex (si le XML est trop malformé pour ElementTree)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_ixbrl_segments_regex(content: str) -> dict[str, float]:
    """
    Extraction par regex comme fallback si le parsing XML échoue.
    Moins précis mais robuste sur les fichiers mal formés.
    """
    # Cherche les patterns type: contextRef="Ctx_WinesSpirits_2023" ...>18 450</ix:nonFraction>
    pattern = re.compile(
        r'<ix:nonFraction[^>]+name="([^"]*[Rr]evenue[^"]*)"[^>]*contextRef="([^"]*[Ss]egment[^"]*)"[^>]*>\s*([0-9\s,\.]+)\s*</ix:nonFraction>',
        re.IGNORECASE,
    )

    raw: dict[str, float] = {}
    for match in pattern.finditer(content):
        ctx = match.group(2)
        val_str = match.group(3).replace(",", "").replace(" ", "")
        try:
            val = float(val_str)
            if val > 0:
                raw[ctx] = max(raw.get(ctx, 0), val)
        except ValueError:
            continue

    if not raw:
        return {}

    total = sum(raw.values())
    return {k: v / total for k, v in raw.items()} if total > 0 else {}


# ─────────────────────────────────────────────────────────────────────────────
# Interface publique principale
# ─────────────────────────────────────────────────────────────────────────────

# Mapping ticker → nom société pour l'API info-financiere
# (l'API cherche par nom, pas par ticker)
_TICKER_TO_COMPANY: dict[str, str] = {
    # CAC 40
    "AI.PA":   "AIR LIQUIDE",
    "AIR.PA":  "AIRBUS",
    "ALO.PA":  "ALSTOM",
    "MT.PA":   "ARCELORMITTAL",
    "CS.PA":   "AXA",
    "BNP.PA":  "BNP PARIBAS",
    "EN.PA":   "BOUYGUES",
    "CAP.PA":  "CAPGEMINI",
    "CA.PA":   "CARREFOUR",
    "ACA.PA":  "CREDIT AGRICOLE",
    "BN.PA":   "DANONE",
    "DSY.PA":  "DASSAULT SYSTEMES",
    "ENGI.PA": "ENGIE",
    "EL.PA":   "ESSILORLUXOTTICA",
    "RMS.PA":  "HERMES",
    "KER.PA":  "KERING",
    "LR.PA":   "LEGRAND",
    "OR.PA":   "LOREAL",
    "MC.PA":   "LVMH",
    "ML.PA":   "MICHELIN",
    "ORA.PA":  "ORANGE",
    "RI.PA":   "PERNOD RICARD",
    "PUB.PA":  "PUBLICIS",
    "RNO.PA":  "RENAULT",
    "SAF.PA":  "SAFRAN",
    "SGO.PA":  "SAINT-GOBAIN",
    "SAN.PA":  "SANOFI",
    "SU.PA":   "SCHNEIDER ELECTRIC",
    "GLE.PA":  "SOCIETE GENERALE",
    "STLAM.PA":"STELLANTIS",
    "STM.PA":  "STMICROELECTRONICS",
    "TEP.PA":  "TELEPERFORMANCE",
    "HO.PA":   "THALES",
    "TTE.PA":  "TOTALENERGIES",
    "URW.PA":  "UNIBAIL-RODAMCO",
    "VIE.PA":  "VEOLIA",
    "DG.PA":   "VINCI",
    "VIV.PA":  "VIVENDI",
    "WLN.PA":  "WORLDLINE",
}


async def fetch_segments_from_esef(ticker: str) -> dict[str, float]:
    """
    Extrait les revenus par segment depuis le rapport annuel ESEF
    déposé sur info-financiere.gouv.fr.

    Args:
        ticker: Ticker Euronext (ex: "MC.PA", "TTE.PA")

    Returns:
        Dict {segment_name: fraction_du_CA} ou {} si non disponible.
    """
    # Résolution ticker → nom société
    company_name = _TICKER_TO_COMPANY.get(ticker.upper())
    if not company_name:
        # Tentative avec la partie avant ".PA"
        company_name = ticker.upper().replace(".PA", "").replace(".FP", "")
        log.debug("No exact mapping for %s — trying '%s'", ticker, company_name)

    # 1. Cherche l'URL du rapport annuel
    report_url = await _find_annual_report_url(company_name)
    if not report_url:
        return {}

    # 2. Télécharge le ZIP
    zip_bytes = await _download_esef_zip(report_url)
    if not zip_bytes:
        return {}

    # 3. Extrait le .xhtml
    xhtml_content = _extract_xhtml_from_zip(zip_bytes)
    if not xhtml_content:
        return {}

    # 4. Parse les segments iXBRL
    segments = _parse_ixbrl_segments(xhtml_content)

    if segments:
        log.info(
            "ESEF segments extracted for %s: %d segments — %s",
            ticker,
            len(segments),
            list(segments.keys())[:5],
        )
    else:
        log.info("No segment data found in ESEF report for %s", ticker)

    return segments
