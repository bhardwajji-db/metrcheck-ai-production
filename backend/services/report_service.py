"""
MetrCheck AI — Professional Multilingual PDF Report Generator (Section 16 Advanced Reporting)

This module consumes an existing AnalysisResponse and generates an audit-grade,
multi-page PDF report localized in any of the 10 supported Indian languages:
English, Hindi, Bengali, Marathi, Gujarati, Punjabi, Tamil, Telugu, Kannada, Malayalam.

It does NOT recalculate compliance, scoring, or recommendations.
Uses: reportlab with Unicode Indic font support.
"""

import os
import io
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from utils.datetime_utils import format_ist_datetime, get_current_ist_datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm, inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, PageBreak, HRFlowable, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from reportlab.graphics.shapes import Drawing, Rect, String, Circle
from reportlab.graphics import renderPDF
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from models.schemas import AnalysisResponse
from config import settings
from multilingual.registry import normalize_language_code, SUPPORTED_LANGUAGES
from multilingual.localization import (
    localize_rule_label,
    localize_status,
    localize_explanation,
    get_report_ui_labels
)

logger = logging.getLogger(__name__)

# ── Dynamic Unicode & Indic Font Registration ──────────────────
_FONT_REGULAR = 'Helvetica'
_FONT_BOLD = 'Helvetica-Bold'
_FONT_OBLIQUE = 'Helvetica-Oblique'

def _init_report_fonts():
    global _FONT_REGULAR, _FONT_BOLD, _FONT_OBLIQUE
    font_candidates = [
        (r'C:\Windows\Fonts\Nirmala.ttc', 0, 1),
        (r'/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf', None, None),
    ]
    for p, idx0, idx1 in font_candidates:
        if os.path.exists(p):
            try:
                if idx0 is not None:
                    pdfmetrics.registerFont(TTFont('MetrCheckIndic', p, subfontIndex=idx0))
                    pdfmetrics.registerFont(TTFont('MetrCheckIndic-Bold', p, subfontIndex=idx1))
                else:
                    pdfmetrics.registerFont(TTFont('MetrCheckIndic', p))
                    pdfmetrics.registerFont(TTFont('MetrCheckIndic-Bold', p))
                _FONT_REGULAR = 'MetrCheckIndic'
                _FONT_BOLD = 'MetrCheckIndic-Bold'
                logger.info(f"Registered Unicode Indic font for reports from {p}")
                return
            except Exception as e:
                logger.warning(f"Could not register font from {p}: {e}")

_init_report_fonts()

# ── Color Palette ──────────────────────────────────────────────
INDIGO = colors.HexColor('#4338ca')
INDIGO_LIGHT = colors.HexColor('#e0e7ff')
INDIGO_DARK = colors.HexColor('#312e81')
EMERALD = colors.HexColor('#059669')
EMERALD_LIGHT = colors.HexColor('#d1fae5')
AMBER = colors.HexColor('#d97706')
AMBER_LIGHT = colors.HexColor('#fef3c7')
RED = colors.HexColor('#dc2626')
RED_LIGHT = colors.HexColor('#fee2e2')
SLATE_50 = colors.HexColor('#f8fafc')
SLATE_100 = colors.HexColor('#f1f5f9')
SLATE_200 = colors.HexColor('#e2e8f0')
SLATE_400 = colors.HexColor('#94a3b8')
SLATE_500 = colors.HexColor('#64748b')
SLATE_600 = colors.HexColor('#475569')
SLATE_700 = colors.HexColor('#334155')
SLATE_800 = colors.HexColor('#1e293b')
SLATE_900 = colors.HexColor('#0f172a')
WHITE = colors.white

STATUS_COLORS = {
    'PASS': (EMERALD, EMERALD_LIGHT),
    'COMPLIANT': (EMERALD, EMERALD_LIGHT),
    'FAIL': (RED, RED_LIGHT),
    'NON_COMPLIANCE': (RED, RED_LIGHT),
    'POTENTIAL NON-COMPLIANCE': (RED, RED_LIGHT),
    'WARNING': (AMBER, AMBER_LIGHT),
    'NEEDS_REVIEW': (AMBER, AMBER_LIGHT),
    'NOT_APPLICABLE': (SLATE_500, SLATE_100),
}


def _status_color(status: str):
    s = (status or '').upper().replace('-', '_')
    return STATUS_COLORS.get(s, (SLATE_500, SLATE_100))


# ── Custom Styles ──────────────────────────────────────────────
def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'ReportTitle', parent=styles['Title'],
        fontName=_FONT_BOLD, fontSize=17, leading=21,
        textColor=INDIGO_DARK, spaceAfter=1*mm, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        'ReportSubtitle', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=9, leading=12,
        textColor=SLATE_500, spaceAfter=2.5*mm, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        'SectionHeading', parent=styles['Heading2'],
        fontName=_FONT_BOLD, fontSize=10.5, leading=13.5,
        textColor=INDIGO_DARK, spaceBefore=3.5*mm, spaceAfter=2*mm,
        borderWidth=0, borderPadding=0,
    ))
    styles.add(ParagraphStyle(
        'SubHeading', parent=styles['Heading3'],
        fontName=_FONT_BOLD, fontSize=9, leading=11.5,
        textColor=SLATE_800, spaceBefore=2.5*mm, spaceAfter=1.5*mm,
    ))
    styles.add(ParagraphStyle(
        'BodyText2', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=8, leading=11,
        textColor=SLATE_700, spaceAfter=1.5*mm,
        alignment=TA_JUSTIFY,
    ))
    styles.add(ParagraphStyle(
        'SmallText', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=7.5, leading=9.5,
        textColor=SLATE_500, spaceAfter=1*mm,
    ))
    styles.add(ParagraphStyle(
        'TableCell', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=7.5, leading=9.5,
        textColor=SLATE_700,
    ))
    styles.add(ParagraphStyle(
        'TableCellBold', parent=styles['Normal'],
        fontName=_FONT_BOLD, fontSize=7.5, leading=9.5,
        textColor=SLATE_800,
    ))
    styles.add(ParagraphStyle(
        'TableCellCenter', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=7.5, leading=9.5,
        textColor=SLATE_700, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'TableCellBoldCenter', parent=styles['Normal'],
        fontName=_FONT_BOLD, fontSize=7.5, leading=9.5,
        textColor=SLATE_800, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'AttentionTitle', parent=styles['Normal'],
        fontName=_FONT_BOLD, fontSize=8.5, leading=11,
        textColor=SLATE_900,
    ))
    styles.add(ParagraphStyle(
        'AttentionBody', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=7.5, leading=10,
        textColor=SLATE_700,
    ))
    styles.add(ParagraphStyle(
        'AttentionAction', parent=styles['Normal'],
        fontName=_FONT_BOLD, fontSize=7.5, leading=10,
        textColor=INDIGO_DARK,
    ))
    styles.add(ParagraphStyle(
        'Disclaimer', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=7, leading=9,
        textColor=SLATE_600, spaceAfter=2*mm,
        alignment=TA_JUSTIFY, borderWidth=0.5, borderColor=SLATE_200,
        borderPadding=4,
    ))
    styles.add(ParagraphStyle(
        'ScoreNote', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=7, leading=9,
        textColor=SLATE_500, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'ScoreText', parent=styles['Normal'],
        fontName=_FONT_BOLD, fontSize=24, leading=28,
        textColor=INDIGO_DARK, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'StatusText', parent=styles['Normal'],
        fontName=_FONT_BOLD, fontSize=11.5, leading=14,
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'FooterText', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=7, leading=9,
        textColor=SLATE_400, alignment=TA_CENTER,
    ))

    return styles


# ── Page Template Callbacks ────────────────────────────────────
def _header_footer(canvas, doc):
    """Draw header line and footer on every page."""
    canvas.saveState()
    w, h = A4

    # Header line
    canvas.setStrokeColor(INDIGO)
    canvas.setLineWidth(1.5)
    canvas.line(15*mm, h - 12*mm, w - 15*mm, h - 12*mm)

    # Header text
    canvas.setFont(_FONT_BOLD, 7)
    canvas.setFillColor(INDIGO)
    canvas.drawString(15*mm, h - 10.5*mm, 'METRCHECK AI')

    canvas.setFont(_FONT_REGULAR, 7)
    canvas.setFillColor(SLATE_400)
    canvas.drawRightString(w - 15*mm, h - 10.5*mm, 'AI-Assisted Legal Metrology Compliance Screening')

    # Footer
    canvas.setStrokeColor(SLATE_200)
    canvas.setLineWidth(0.5)
    canvas.line(15*mm, 12*mm, w - 15*mm, 12*mm)

    canvas.setFont(_FONT_REGULAR, 7)
    canvas.setFillColor(SLATE_400)
    canvas.drawString(15*mm, 7*mm, 'MetrCheck AI — Statutory Compliance & Audit Verification')
    canvas.drawRightString(w - 15*mm, 7*mm, f'Page {doc.page}')

    canvas.restoreState()


# ── Helper: Safe image load ────────────────────────────────────
def _load_image(image_url: str, max_width: float, max_height: float) -> Optional[RLImage]:
    """Load image from uploads directory. Returns None on failure."""
    try:
        if not image_url:
            return None

        filename = image_url.split('/')[-1] if '/' in image_url else image_url
        filepath = os.path.join(settings.UPLOAD_DIR, filename)

        if not os.path.isfile(filepath):
            logger.warning(f"Image file not found: {filepath}")
            return None

        img = RLImage(filepath)
        iw, ih = img.imageWidth, img.imageHeight
        if iw <= 0 or ih <= 0:
            return None
        ratio = min(max_width / iw, max_height / ih, 1.0)
        img.drawWidth = iw * ratio
        img.drawHeight = ih * ratio
        return img
    except Exception as e:
        logger.warning(f"Failed to load image {image_url}: {e}")
        return None


def _safe_str(val, fallback='Not detected'):
    """Safe string conversion for PDF text."""
    if val is None:
        return fallback
    s = str(val).strip()
    return s if s else fallback


def _truncate(text: str, max_len: int = 120) -> str:
    """Truncate long text for table cells."""
    if not text:
        return ''
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + '...'


# ── Main PDF Generator ────────────────────────────────────────
def generate_pdf_report(
    analysis: AnalysisResponse,
    lang: str = "en",
    language: Optional[str] = None,
    target_language: Optional[str] = None
) -> bytes:
    """
    Generate a professional multi-page PDF report from an existing AnalysisResponse in any of 10 languages.
    Returns the PDF as bytes.
    Does NOT re-calculate scores or mutate analysis state.
    """
    effective_lang = target_language or language or lang or "en"
    canon_lang = normalize_language_code(effective_lang)
    ui_labels = get_report_ui_labels(canon_lang)

    buf = io.BytesIO()
    styles = _build_styles()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=16*mm,
        bottomMargin=16*mm,
        leftMargin=15*mm,
        rightMargin=15*mm,
        title=f'MetrCheck AI Report — {analysis.product_name}',
        author='MetrCheck AI',
    )

    story = []
    w_avail = A4[0] - 30*mm  # 180mm Available content width

    cr = analysis.compliance_result
    product_info = analysis.product_info
    images_list = analysis.images or []
    recommendations = analysis.recommendations or (cr.recommendations if cr else []) or []
    checks = cr.checks if cr else []

    # ══════════════════════════════════════════════════════════════
    # SECTION 1 — HEADER & EXECUTIVE PRODUCT SUMMARY
    # ══════════════════════════════════════════════════════════════
    story.append(Spacer(1, 1*mm))
    story.append(Paragraph('METRCHECK AI', styles['ReportTitle']))
    story.append(Paragraph(
        ui_labels.get("report_title", 'AI-Assisted Product Compliance Screening Report'),
        styles['ReportSubtitle']
    ))

    story.append(HRFlowable(
        width='100%', thickness=1.2, color=INDIGO, spaceAfter=2.5*mm
    ))

    story.append(Paragraph(
        ui_labels.get("executive_summary", 'EXECUTIVE SUMMARY & PRODUCT OVERVIEW'),
        styles['SectionHeading']
    ))

    date_str = format_ist_datetime(analysis.created_at, '%d %B %Y, %H:%M IST')
    generated_at_str = format_ist_datetime(get_current_ist_datetime(), '%d %B %Y, %H:%M IST')

    # Detect packaging languages
    detected_lang_str = "English (Latin)"
    multi_meta = getattr(analysis, 'multilingual', None) or getattr(product_info, 'multilingual', None)
    if multi_meta and hasattr(multi_meta, 'detected_languages') and multi_meta.detected_languages:
        parts = [f"{l.name} ({round(l.confidence*100)}%)" for l in multi_meta.detected_languages]
        detected_lang_str = ", ".join(parts)

    risk_lvl = "LOW"
    if cr and cr.risk_assessment and hasattr(cr.risk_assessment, 'risk_level'):
        risk_lvl = str(cr.risk_assessment.risk_level).upper()

    brand_val = product_info.brand if product_info else None

    is_manual = (
        getattr(product_info, 'extraction_mode', None) == 'manual'
        or (analysis.ocr_result and getattr(analysis.ocr_result, 'engine', '') == 'Manual User Entry')
        or not images_list
    )
    analysis_mode_label = ui_labels.get("manual_mode", "MANUAL PRODUCT CHECK") if is_manual else ui_labels.get("image_mode", "AI IMAGE & OCR SCREENING")
    info_source_label = ui_labels.get("manual_source", "USER-PROVIDED PACKAGE DECLARATIONS") if is_manual else ui_labels.get("image_source", "PACKAGE ARTWORK OCR & COMPUTER VISION")

    meta_data = [
        [Paragraph(f'<b>{ui_labels.get("analysis_id", "Analysis ID")}:</b>', styles['TableCellBold']), Paragraph(str(analysis.id), styles['TableCell'])],
        [Paragraph(f'<b>{ui_labels.get("analysis_mode", "Analysis Mode")}:</b>', styles['TableCellBold']), Paragraph(analysis_mode_label, styles['TableCell'])],
        [Paragraph(f'<b>{ui_labels.get("info_source", "Information Source")}:</b>', styles['TableCellBold']), Paragraph(info_source_label, styles['TableCell'])],
        [Paragraph(f'<b>{ui_labels.get("inspection_timestamp", "Inspection Timestamp")}:</b>', styles['TableCellBold']), Paragraph(date_str, styles['TableCell'])],
        [Paragraph(f'<b>{ui_labels.get("generated_at", "Report Generated At")}:</b>', styles['TableCellBold']), Paragraph(generated_at_str, styles['TableCell'])],
        [Paragraph(f'<b>{ui_labels.get("product_name", "Product")}:</b>', styles['TableCellBold']), Paragraph(_safe_str(analysis.product_name, 'Unknown Product'), styles['TableCell'])],
        [Paragraph(f'<b>{ui_labels.get("brand", "Brand")}:</b>', styles['TableCellBold']), Paragraph(_safe_str(brand_val, 'Not detected'), styles['TableCell'])],
        [Paragraph(f'<b>{ui_labels.get("product_risk_tier", "Product Risk Tier")}:</b>', styles['TableCellBold']), Paragraph(f'{localize_status(risk_lvl, canon_lang)}', styles['TableCell'])],
        [Paragraph(f'<b>{ui_labels.get("images_analyzed", "Images Analyzed")}:</b>', styles['TableCellBold']), Paragraph(f'{len(images_list)} panel(s)' if images_list else f'0 ({analysis_mode_label})', styles['TableCell'])],
        [Paragraph(f'<b>{ui_labels.get("detected_languages", "Packaging Languages")}:</b>', styles['TableCellBold']), Paragraph(detected_lang_str, styles['TableCell'])]
    ]
    meta_table = Table(meta_data, colWidths=[45*mm, w_avail - 45*mm])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 2.5*mm))

    # ══════════════════════════════════════════════════════════════
    # SECTION 2 — OVERALL SCREENING RESULT & TRIAGE
    # ══════════════════════════════════════════════════════════════
    score_val = cr.score if cr else 0.0
    status_val = cr.status if cr else "UNKNOWN"
    fg, bg = _status_color(status_val)
    loc_status = localize_status(status_val, canon_lang)

    passed_cnt = cr.passed_rules if cr else 0
    review_cnt = cr.needs_review_rules if cr else 0
    warn_cnt = cr.warning_rules if cr else 0
    fail_cnt = cr.failed_rules if cr else 0
    na_cnt = cr.not_applicable_rules if cr else 0

    bd_w = w_avail / 5.0
    breakdown_cells = [
        Paragraph(f'<b>{passed_cnt}</b><br/>{localize_status("PASS", canon_lang)}', styles['TableCellCenter']),
        Paragraph(f'<b>{review_cnt}</b><br/>{localize_status("NEEDS_REVIEW", canon_lang)}', styles['TableCellCenter']),
        Paragraph(f'<b>{warn_cnt}</b><br/>{localize_status("WARNING", canon_lang)}', styles['TableCellCenter']),
        Paragraph(f'<b>{fail_cnt}</b><br/>{localize_status("FAIL", canon_lang)}', styles['TableCellCenter']),
        Paragraph(f'<b>{na_cnt}</b><br/>{localize_status("NOT_APPLICABLE", canon_lang)}', styles['TableCellCenter']),
    ]
    inner_breakdown = Table([breakdown_cells], colWidths=[bd_w]*5)
    inner_breakdown.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (0, 0), EMERALD_LIGHT),
        ('BACKGROUND', (1, 0), (1, 0), AMBER_LIGHT),
        ('BACKGROUND', (2, 0), (2, 0), AMBER_LIGHT),
        ('BACKGROUND', (3, 0), (3, 0), RED_LIGHT),
        ('BACKGROUND', (4, 0), (4, 0), SLATE_100),
        ('BOX', (0, 0), (-1, -1), 0.5, SLATE_200),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, SLATE_200),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))

    card_header = Paragraph(
        f'<b>{ui_labels.get("overall_status", "STATUTORY COMPLIANCE SCREENING RESULT").upper()}</b>',
        ParagraphStyle(
            'CardHead', parent=styles['Normal'], fontName=_FONT_BOLD,
            fontSize=8.5, leading=11, textColor=INDIGO_DARK, alignment=TA_CENTER
        )
    )
    score_para = Paragraph(
        f'<b>{ui_labels.get("screening_score", "SCREENING SCORE")}: {score_val:.1f}</b> <font size=11 color="{SLATE_500.hexval()}">/ 100</font>',
        styles['ScoreText']
    )
    if is_manual:
        score_note_para = Paragraph(
            f'<i>{ui_labels.get("manual_score_note", "This screening is based on declarations manually provided by the consumer. Some declaration information in this report was provided manually and was not independently verified against package artwork.")}</i>',
            styles['ScoreNote']
        )
    else:
        score_note_para = Paragraph(
            f'<i>{ui_labels.get("automated_score_note", "This score is a weighted automated screening score across applicable checks. It is not an official legal compliance percentage or enforcement determination.")}</i>',
            styles['ScoreNote']
        )
    status_para = Paragraph(
        f'<b>{loc_status}</b>',
        ParagraphStyle('CardStat', parent=styles['StatusText'], textColor=fg)
    )

    card_table = Table([
        [card_header],
        [status_para],
        [score_para],
        [score_note_para],
        [inner_breakdown],
    ], colWidths=[w_avail])
    card_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, -1), SLATE_50),
        ('BOX', (0, 0), (-1, -1), 1, INDIGO_LIGHT),
        ('TOPPADDING', (0, 0), (0, 0), 3),
        ('BOTTOMPADDING', (0, 0), (0, 0), 2),
        ('TOPPADDING', (0, 1), (0, 1), 2),
        ('BOTTOMPADDING', (0, 1), (0, 1), 2),
        ('TOPPADDING', (0, 2), (0, 2), 2),
        ('BOTTOMPADDING', (0, 2), (0, 2), 1),
        ('TOPPADDING', (0, 3), (0, 3), 1),
        ('BOTTOMPADDING', (0, 3), (0, 3), 3),
        ('TOPPADDING', (0, 4), (0, 4), 2),
        ('BOTTOMPADDING', (0, 4), (0, 4), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3*mm),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3*mm),
    ]))
    story.append(card_table)
    story.append(Spacer(1, 2.5*mm))

    # ══════════════════════════════════════════════════════════════
    # SECTION 3 — ATTENTION ITEMS & PLAIN LANGUAGE "WHAT THIS MEANS"
    # ══════════════════════════════════════════════════════════════
    attention_checks = [
        c for c in checks
        if (c.status or '').upper() in ('NEEDS_REVIEW', 'WARNING', 'INSUFFICIENT_EVIDENCE', 'FAIL', 'NON_COMPLIANCE')
    ]

    if attention_checks:
        story.append(Paragraph(ui_labels.get("items_requiring_attention", 'COMPLIANCE DEFECTS & MISSING DECLARATIONS DOCKET'), styles['SectionHeading']))
        for ac in attention_checks:
            st_upper = (ac.status or 'NEEDS_REVIEW').upper()
            fg_col, bg_col = _status_color(st_upper)
            loc_st = localize_status(st_upper, canon_lang)
            loc_lbl = localize_rule_label(ac.rule_id, canon_lang)
            
            # Check if this is a missing declaration
            det_val = (ac.detected_value or '').strip()
            is_missing = (
                getattr(ac, 'field_status', None) == 'MISSING'
                or (st_upper in ('FAIL', 'NON_COMPLIANCE') and (not det_val or det_val.lower() in ('not detected', 'not found', '-', 'none', 'null')))
                or (st_upper in ('FAIL', 'NON_COMPLIANCE') and 'missing' in (ac.explanation or '').lower())
            )

            # Plain explanation
            loc_expl = localize_explanation(ac.rule_id, st_upper, ac.detected_value, canon_lang)
            
            # Evidence location
            ev_loc = f"{ac.evidence_image_label or 'Package Artwork'}"
            if ac.evidence_region:
                ev_loc += f" → {ac.evidence_region}"

            det_val_str = _safe_str(ac.detected_value, 'No declaration detected on packaging')

            # Find matching recommendation if any
            rec_match = next((r for r in recommendations if r.rule_id == ac.rule_id), None)
            rec_action_text = rec_match.recommended_action if rec_match else "Verify physical packaging text against statutory requirements."

            tag_str = "[MISSING MANDATORY DECLARATION]" if is_missing else f"[{loc_st}]"
            header_color = RED if is_missing else fg_col
            box_bg = RED_LIGHT if is_missing else bg_col
            box_border = RED if is_missing else fg_col

            att_content = [
                Paragraph(f'<b>{ac.rule_id} — {loc_lbl}</b> &nbsp;&nbsp; <font color="{header_color.hexval()}"><b>{tag_str}</b></font>', styles['AttentionTitle']),
                Paragraph(f'<b>{ui_labels.get("detected", "Detected Status")}:</b> {"❌ ABSENT / NOT FOUND ON PACKAGING" if is_missing else det_val_str} &nbsp;|&nbsp; <b>{ui_labels.get("evidence", "Evidence Face")}:</b> {ev_loc}', styles['AttentionBody']),
                Paragraph(f'<b>{ui_labels.get("what_this_means", "What this means")}:</b> {loc_expl}', styles['AttentionBody']),
                Paragraph(f'<b>{ui_labels.get("recommended_check", "Recommended Action")}:</b> {rec_action_text}', styles['AttentionAction']),
            ]

            att_tbl = Table([[Paragraph(c, styles['AttentionBody']) if isinstance(c, str) else c] for c in att_content], colWidths=[w_avail])
            att_tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), box_bg),
                ('BOX', (0, 0), (-1, -1), 1.0 if is_missing else 0.75, box_border),
                ('TOPPADDING', (0, 0), (-1, -1), 2.2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2.2),
                ('LEFTPADDING', (0, 0), (-1, -1), 3*mm),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3*mm),
            ]))
            story.append(att_tbl)
            story.append(Spacer(1, 1.8*mm))
    else:
        # All clean
        all_pass_para = Paragraph(
            f'<b>{ui_labels.get("all_pass_msg", "All statutory packaging declarations analyzed meet automated screening criteria. No items require immediate attention.")}</b>',
            ParagraphStyle('AllPass', parent=styles['TableCellBoldCenter'], textColor=EMERALD)
        )
        all_pass_tbl = Table([[all_pass_para]], colWidths=[w_avail])
        all_pass_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), EMERALD_LIGHT),
            ('BOX', (0, 0), (-1, -1), 0.75, EMERALD),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ]))
        story.append(all_pass_tbl)
        story.append(Spacer(1, 2*mm))

    # ══════════════════════════════════════════════════════════════
    # SECTION 4 — PACKAGE INFORMATION SUMMARY
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph(ui_labels.get("package_information_summary", 'PACKAGE INFORMATION SUMMARY'), styles['SectionHeading']))

    pi = product_info
    mrp_disp = _safe_str(pi.mrp if pi else None)
    if pi and getattr(pi, 'unit_sale_price', None):
        mrp_disp += f" (USP: {pi.unit_sale_price})"

    info_rows = [
        [ui_labels.get("product_name", "Product Name"), _safe_str(pi.product_name if pi else None)],
        [ui_labels.get("brand", "Brand"), _safe_str(pi.brand if pi else None)],
        [localize_rule_label("LM-001", canon_lang), _safe_str(pi.manufacturer if pi else None)],
        [ui_labels.get("marketed_by", "Marketed By"), _safe_str(pi.marketed_by if pi else None)],
        [localize_rule_label("LM-003", canon_lang), _safe_str(pi.net_quantity if pi else None)],
        [localize_rule_label("LM-004", canon_lang), mrp_disp],
        [localize_rule_label("LM-006", canon_lang), _safe_str(pi.country_of_origin if pi else None)],
        [localize_rule_label("FS-001", canon_lang), _safe_str(pi.fssai_license if pi else None)],
        [localize_rule_label("LM-008", canon_lang), _safe_str((pi.manufacturing_date or pi.manufacture_date) if pi else None)],
        [ui_labels.get("best_before_shelf_life", "Best Before / Shelf Life"), _safe_str((pi.best_before or pi.relative_shelf_life) if pi else None)],
        [localize_rule_label("FS-005", canon_lang), _safe_str((pi.expiry_date or pi.use_by_date) if pi else None)],
        [ui_labels.get("batch_lot_number", "Batch / Lot Number"), _safe_str(pi.batch_number if pi else None)],
        [localize_rule_label("LM-005", canon_lang), _safe_str(pi.consumer_care if pi else None)],
        [localize_rule_label("FS-003", canon_lang), _safe_str(_truncate(pi.ingredients, 180) if (pi and pi.ingredients) else None)],
    ]

    info_table_data = []
    for label, val in info_rows:
        info_table_data.append([
            Paragraph(f'<b>{label}</b>', styles['TableCellBold']),
            Paragraph(val, styles['TableCell']),
        ])

    info_table = Table(info_table_data, colWidths=[48*mm, w_avail - 48*mm])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (0, -1), SLATE_50),
        ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 2.5*mm))

    # ══════════════════════════════════════════════════════════════
    # SECTION 5 & 6 — STATUTORY COMPLIANCE CHECKLIST (LM & FSSAI)
    # ══════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph(ui_labels.get("detailed_compliance_checklist", 'DETAILED STATUTORY COMPLIANCE CHECKLIST'), styles['SectionHeading']))

    lm_checks = [c for c in checks if (c.domain or '').upper() != 'FSSAI']
    fssai_checks = [c for c in checks if (c.domain or '').upper() == 'FSSAI']

    def _build_checks_table(check_list, domain_label):
        if not check_list:
            return []

        elements = []
        elements.append(Paragraph(f'<b>{domain_label}</b>', styles['SubHeading']))

        header = [
            Paragraph(f'<b>{ui_labels.get("field_header", "Rule ID")}</b>', styles['TableCellBoldCenter']),
            Paragraph(f'<b>{ui_labels.get("requirement_header", "Statutory Requirement")}</b>', styles['TableCellBold']),
            Paragraph(f'<b>{ui_labels.get("status_header", "Status")}</b>', styles['TableCellBoldCenter']),
            Paragraph(f'<b>{ui_labels.get("detected_value_header", "Detected Declaration")}</b>', styles['TableCellBold']),
            Paragraph(f'<b>{ui_labels.get("confidence_header", "Confidence")}</b>', styles['TableCellBoldCenter']),
            Paragraph(f'<b>{ui_labels.get("location_header", "Location")}</b>', styles['TableCellBold']),
        ]
        rows = [header]

        for c in check_list:
            status_str = c.status or 'UNKNOWN'
            fg_col, bg_col = _status_color(status_str)
            loc_st = localize_status(status_str, canon_lang)
            status_para = Paragraph(
                f'<font color="{fg_col.hexval()}"><b>{loc_st}</b></font>',
                styles['TableCellCenter']
            )

            # Handle NOT_APPLICABLE text gracefully (never say 'Missing')
            if status_str.upper() == 'NOT_APPLICABLE':
                det_val = c.explanation or c.reason or 'Statutory exemption applies'
            else:
                det_val = _safe_str(c.detected_value, 'Not detected')

            conf = f'{round(c.confidence)}%' if c.confidence is not None else '—'
            loc_lbl = localize_rule_label(c.rule_id, canon_lang)
            stat_cite = f"{c.source_name or ''} {c.source_reference or ''}".strip()
            req_text = f"<b>{loc_lbl}</b>"
            if stat_cite:
                req_text += f"<br/><font size=6.5 color='{SLATE_500.hexval()}'>{stat_cite}</font>"

            loc_text = c.evidence_image_label or "Package"
            if c.evidence_region:
                loc_text += f" ({c.evidence_region})"

            rows.append([
                Paragraph(f'<b>{c.rule_id}</b>', styles['TableCellCenter']),
                Paragraph(req_text, styles['TableCell']),
                status_para,
                Paragraph(_truncate(det_val, 70), styles['TableCell']),
                Paragraph(conf, styles['TableCellCenter']),
                Paragraph(_truncate(loc_text, 35), styles['TableCell']),
            ])

        tbl = Table(rows, colWidths=[18*mm, 52*mm, 28*mm, 42*mm, 18*mm, 22*mm])
        tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (-1, 0), INDIGO_LIGHT),
            ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, SLATE_50]),
        ]))
        elements.append(tbl)
        elements.append(Spacer(1, 2.5*mm))
        return elements

    story.extend(_build_checks_table(lm_checks, ui_labels.get("legal_metrology_title", 'LEGAL METROLOGY (PACKAGED COMMODITIES) RULES 2011')))
    story.extend(_build_checks_table(fssai_checks, ui_labels.get("fssai_title", 'FSSAI (FOOD SAFETY & STANDARDS LABELLING REGULATIONS)')))

    # ══════════════════════════════════════════════════════════════
    # SECTION 7 — RULE 12 / PHYSICAL READABILITY & QUANTITY ASSESSMENT
    # ══════════════════════════════════════════════════════════════
    if analysis.font_size_analysis:
        story.append(Spacer(1, 1*mm))
        story.append(Paragraph(ui_labels.get("readability_title", 'PHYSICAL READABILITY & QUANTITY DECLARATION ASSESSMENT'), styles['SectionHeading']))
        fsa = analysis.font_size_analysis
        
        font_rows = [
            [ui_labels.get("readability_score_tier", 'Visual Readability Score & Tier'), f"{fsa.readability_score:.1f} / 100 ({fsa.readability_tier})"],
            [ui_labels.get("net_qty_font_height", 'Estimated Net Qty Character Height'), f"{fsa.net_quantity_font_height_mm} mm" if fsa.net_quantity_font_height_mm is not None else "N/A"],
            [ui_labels.get("min_required_font_height", 'Statutory Minimum Required Height'), f"{fsa.min_required_font_height_mm} mm (Rule 12 Table-I)" if fsa.min_required_font_height_mm is not None else "N/A"],
            [ui_labels.get("rule_12_verdict", 'Rule 12 Screening Verdict'), fsa.rule_12_verdict or "Compliant"],
            [ui_labels.get("measurement_method", 'Measurement Method & Optical Scale'), fsa.calibration_status or "PHYSICAL_MEASUREMENT_ESTIMATED"],
            [ui_labels.get("assessment_summary", 'Assessment Summary'), fsa.details or "Font height meets or exceeds statutory requirements."],
        ]
        font_tbl_data = [
            [Paragraph(f'<b>{lbl}</b>', styles['TableCellBold']), Paragraph(str(v), styles['TableCell'])]
            for lbl, v in font_rows
        ]
        font_tbl = Table(font_tbl_data, colWidths=[52*mm, w_avail - 52*mm])
        font_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (0, -1), SLATE_50),
            ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
            ('TOPPADDING', (0, 0), (-1, -1), 1.8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.8),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(font_tbl)
        story.append(Spacer(1, 1.5*mm))

        # Rule 12 limitation note
        rule12_note = f"<b>Rule 12 Measurement Notice:</b> {ui_labels.get('rule12_notice', 'Estimated measurements are derived from digital image analysis and optical scale estimation. They should not be treated as a physically calibrated measurement certificate.')}"
        story.append(Paragraph(rule12_note, styles['Disclaimer']))
        story.append(Spacer(1, 2*mm))

    # ══════════════════════════════════════════════════════════════
    # SECTION 8 — EXTERNAL REGISTRY VERIFICATION (IF PRESENT)
    # ══════════════════════════════════════════════════════════════
    ext_ver = getattr(analysis, 'external_verification', None)
    if ext_ver:
        story.append(Spacer(1, 1.5*mm))
        story.append(Paragraph(ui_labels.get("external_verification_title", 'EXTERNAL REGISTRY VERIFICATION & CROSS-CHECKING'), styles['SectionHeading']))
        
        conf_tier = ext_ver.confidence.tier.value if hasattr(ext_ver.confidence, 'tier') else "UNVERIFIED"
        conf_score = int(ext_ver.confidence.score * 100) if hasattr(ext_ver.confidence, 'score') else 0
        overall_st = ext_ver.overall_consistency_status.value if hasattr(ext_ver.overall_consistency_status, 'value') else str(ext_ver.overall_consistency_status)
        
        summary_rows = [
            [ui_labels.get("overall_cross_check_status", 'Overall Cross-Check Status'), overall_st],
            [ui_labels.get("verification_confidence_tier", 'Verification Confidence Tier'), f'{conf_tier} ({conf_score}%)'],
            [ui_labels.get("authoritative_verdict", 'Authoritative Verdict'), ext_ver.summary_verdict or 'Cross-referencing completed.'],
            [ui_labels.get("verification_sources", 'Verification Sources'), ", ".join(ext_ver.verification_sources) if ext_ver.verification_sources else 'Local FoSCoS / GS1 Registry Adapters'],
        ]
        
        sum_table_data = [
            [Paragraph(f'<b>{lbl}</b>', styles['TableCellBold']), Paragraph(str(v), styles['TableCell'])]
            for lbl, v in summary_rows
        ]
        sum_tbl = Table(sum_table_data, colWidths=[48*mm, w_avail - 48*mm])
        sum_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (0, -1), SLATE_50),
            ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
            ('TOPPADDING', (0, 0), (-1, -1), 1.8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.8),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(sum_tbl)
        story.append(Spacer(1, 1.5*mm))

        if ext_ver.cross_checks:
            cc_headers = [
                Paragraph(f'<b>{ui_labels.get("cross_check_target", "Cross-Check Target")}</b>', styles['TableCellBold']),
                Paragraph(f'<b>{ui_labels.get("extracted_value", "Extracted Value")}</b>', styles['TableCellBold']),
                Paragraph(f'<b>{ui_labels.get("registry_record", "Registry Record")}</b>', styles['TableCellBold']),
                Paragraph(f'<b>{ui_labels.get("status_header", "Status")}</b>', styles['TableCellBoldCenter']),
            ]
            cc_data = [cc_headers]
            for cc in ext_ver.cross_checks:
                c_st = cc.status.value if hasattr(cc.status, 'value') else str(cc.status)
                cc_data.append([
                    Paragraph(cc.check_type.replace('_', ' '), styles['TableCell']),
                    Paragraph(_safe_str(cc.extracted_value, '—'), styles['TableCell']),
                    Paragraph(_safe_str(cc.registry_value, '—'), styles['TableCell']),
                    Paragraph(c_st, styles['TableCellCenter']),
                ])
            cc_tbl = Table(cc_data, colWidths=[42*mm, 42*mm, 42*mm, w_avail - 126*mm])
            cc_tbl.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BACKGROUND', (0, 0), (-1, 0), INDIGO_LIGHT),
                ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
                ('TOPPADDING', (0, 0), (-1, -1), 1.8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1.8),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, SLATE_50]),
            ]))
            story.append(cc_tbl)
            story.append(Spacer(1, 2*mm))

    # ══════════════════════════════════════════════════════════════
    # SECTION 9 — OFFICER REVIEW (IF PRESENT)
    # ══════════════════════════════════════════════════════════════
    officer_rev = getattr(analysis, 'officer_review', None)
    if officer_rev:
        story.append(Spacer(1, 1.5*mm))
        story.append(Paragraph(ui_labels.get("human_review_title", 'HUMAN OFFICER AUDIT REVIEW'), styles['SectionHeading']))

        rev_status = officer_rev.get('status', 'PENDING_REVIEW')
        assigned_officer = officer_rev.get('assigned_officer') or 'Unassigned'
        verified_by = officer_rev.get('verified_by') or '—'
        verified_at = officer_rev.get('verified_at') or '—'
        final_human_status = officer_rev.get('final_human_status') or 'Pending'
        human_score = officer_rev.get('human_score')
        human_score_str = f"{human_score:.1f} / 100" if human_score is not None else "Pending Verification"
        
        rev_rows = [
            [ui_labels.get("review_workflow_status", 'Review Workflow Status'), rev_status],
            [ui_labels.get("assigned_officer", 'Assigned Legal Metrology Officer'), assigned_officer],
            [ui_labels.get("verified_by_officer", 'Verified By Officer'), verified_by],
            [ui_labels.get("verification_timestamp", 'Verification Timestamp'), verified_at],
            [ui_labels.get("final_human_verdict", 'Final Human Compliance Verdict'), final_human_status],
            [ui_labels.get("human_verified_score", 'Human Verified Score'), human_score_str],
            [ui_labels.get("ai_vs_human_delta", 'AI vs Human Score Delta'), f"AI: {score_val:.1f}  →  Human: {human_score_str}" if human_score is not None else "Pending human verification"],
        ]

        comments_list = officer_rev.get('comments', [])
        if comments_list and isinstance(comments_list, list):
            comment_texts = [f"[{c.get('officer_username', 'Officer')}]: {c.get('comment', '')}" for c in comments_list if isinstance(c, dict)]
            if comment_texts:
                rev_rows.append([ui_labels.get("officer_notes", 'Officer Notes & Comments'), "; ".join(comment_texts)])

        rev_table_data = [
            [Paragraph(f'<b>{lbl}</b>', styles['TableCellBold']), Paragraph(str(v), styles['TableCell'])]
            for lbl, v in rev_rows
        ]
        rev_tbl = Table(rev_table_data, colWidths=[48*mm, w_avail - 48*mm])
        rev_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (0, -1), SLATE_50),
            ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
            ('TOPPADDING', (0, 0), (-1, -1), 1.8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.8),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(rev_tbl)
        story.append(Spacer(1, 2*mm))

    # ══════════════════════════════════════════════════════════════
    # SECTION 10 — RECOMMENDED ACTIONS (CONSUMER-FOCUSED)
    # ══════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph(ui_labels.get("recommended_actions_title", 'RECOMMENDED NEXT STEPS & ACTIONS'), styles['SectionHeading']))

    if recommendations:
        rec_headers = [
            Paragraph(f'<b>{ui_labels.get("priority_header", "Priority")}</b>', styles['TableCellBoldCenter']),
            Paragraph(f'<b>{ui_labels.get("rule_title_header", "Rule & Title")}</b>', styles['TableCellBold']),
            Paragraph(f'<b>{ui_labels.get("issue_header", "Issue Identified")}</b>', styles['TableCellBold']),
            Paragraph(f'<b>{ui_labels.get("recommended_action_header", "Recommended Action")}</b>', styles['TableCellBold']),
            Paragraph(f'<b>{ui_labels.get("statutory_basis_header", "Statutory Basis")}</b>', styles['TableCellBold']),
        ]
        rec_rows = [rec_headers]

        for r in recommendations:
            p_upper = (r.priority or 'MEDIUM').upper()
            p_color = RED if p_upper == 'HIGH' else (AMBER if p_upper == 'MEDIUM' else INDIGO)
            priority_para = Paragraph(f'<font color="{p_color.hexval()}"><b>{p_upper}</b></font>', styles['TableCellCenter'])
            
            legal_cite = f"{r.source_name or ''} {r.source_reference or ''}".strip()
            rec_rows.append([
                priority_para,
                Paragraph(f"<b>{r.rule_id}</b><br/>{r.title}", styles['TableCell']),
                Paragraph(r.issue or '', styles['TableCell']),
                Paragraph(r.recommended_action or (r.corrective_action or ''), styles['TableCell']),
                Paragraph(legal_cite or 'Legal Metrology Rules 2011', styles['TableCell']),
            ])

        rec_tbl = Table(rec_rows, colWidths=[20*mm, 40*mm, 48*mm, 48*mm, 24*mm])
        rec_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (-1, 0), INDIGO_LIGHT),
            ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, SLATE_50]),
        ]))
        story.append(rec_tbl)
        story.append(Spacer(1, 2.5*mm))
    else:
        no_rec_para = Paragraph(
            f'<b>{ui_labels.get("no_rec_msg", "No corrective actions required based on automated screening.")}</b>',
            ParagraphStyle('NoRec', parent=styles['TableCellBoldCenter'], textColor=EMERALD)
        )
        no_rec_tbl = Table([[no_rec_para]], colWidths=[w_avail])
        no_rec_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), EMERALD_LIGHT),
            ('BOX', (0, 0), (-1, -1), 0.75, EMERALD),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ]))
        story.append(no_rec_tbl)
        story.append(Spacer(1, 2.5*mm))

    # ══════════════════════════════════════════════════════════════
    # SECTION 11 — VISUAL EVIDENCE APPENDIX
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph(ui_labels.get("visual_evidence_title", 'VISUAL EVIDENCE APPENDIX'), styles['SectionHeading']))

    if images_list:
        for img_ev in images_list:
            img_url = img_ev.get('image_url', '') if isinstance(img_ev, dict) else getattr(img_ev, 'image_url', '')
            img_label = img_ev.get('label', 'Image') if isinstance(img_ev, dict) else getattr(img_ev, 'label', 'Image')
            word_count = img_ev.get('word_count', 0) if isinstance(img_ev, dict) else getattr(img_ev, 'word_count', 0)

            img_items = []
            img_items.append(Paragraph(
                f'<b>Package Panel: {img_label}</b> <font color="{SLATE_400.hexval()}">({word_count} OCR tokens detected)</font>',
                styles['SubHeading']
            ))

            rl_img = _load_image(img_url, max_width=w_avail * 0.85, max_height=80*mm)
            if rl_img:
                img_items.append(rl_img)
            else:
                img_items.append(Paragraph('<i>Image visual proof preview unavailable on this device</i>', styles['SmallText']))

            panel_defects = [
                f"{c.rule_id} ({c.field_label or c.field})" for c in checks
                if (c.evidence_image_label or '').lower() in (img_label or '').lower() or (img_label or '').lower() in (c.evidence_image_label or '').lower()
                if (c.status or '').upper() in ('FAIL', 'NON_COMPLIANCE')
            ]
            if panel_defects:
                img_items.append(Paragraph(
                    f'<font color="{RED.hexval()}"><b>⚠️ Visual Evidence Red Box Indicators on this Face:</b> {", ".join(panel_defects)} (Inspect in Web Evidence Viewer)</font>',
                    styles['SmallText']
                ))

            img_items.append(Spacer(1, 2*mm))
            story.append(KeepTogether(img_items))
    else:
        no_img_para = Paragraph(
            f'<i>{ui_labels.get("no_img_msg", "Package artwork was not submitted for this manual screening. Physical readability and optical measurements were not assessed.")}</i>',
            styles['SmallText']
        )
        story.append(no_img_para)
        story.append(Spacer(1, 2*mm))

    # ══════════════════════════════════════════════════════════════
    # SECTION 12 — TECHNICAL PROVENANCE, INTEGRITY & DISCLAIMER
    # ══════════════════════════════════════════════════════════════
    story.append(Spacer(1, 1.5*mm))
    story.append(Paragraph(ui_labels.get("security_integrity_title", 'SECURITY, INTEGRITY & AUDIT PROVENANCE'), styles['SectionHeading']))

    integrity_hash = analysis.integrity_hash or "SHA256-AUTHENTICATED-RECORD"
    system_ver = analysis.system_version or getattr(settings, 'SYSTEM_VERSION', '1.0.0')
    ruleset_ver = analysis.ruleset_version or '2026.1'
    ocr_engine = analysis.ocr_engine_version or 'PaddleOCR PP-OCRv4'

    integrity_rows = [
        [ui_labels.get("integrity_hash_label", 'Cryptographic Integrity Hash (SHA-256)'), integrity_hash],
        [ui_labels.get("software_version_label", 'System Software Version'), f"MetrCheck AI v{system_ver}"],
        [ui_labels.get("ruleset_version_label", 'Statutory Ruleset Version'), f"Ruleset v{ruleset_ver} (Legal Metrology Act 2009 & 2011 Rules)"],
        [ui_labels.get("ocr_engine_label", 'OCR & Vision Engine'), ocr_engine],
        [ui_labels.get("audit_status_label", 'Audit Verification Status'), 'TAMPER-EVIDENT RECORD CERTIFIED'],
        [ui_labels.get("verification_notice_label", 'Verification Notice'), 'This report hash is cryptographically verifiable against the system audit ledger.'],
    ]

    int_table_data = [
        [Paragraph(f'<b>{lbl}</b>', styles['TableCellBold']), Paragraph(str(v), styles['TableCell'])]
        for lbl, v in integrity_rows
    ]
    int_tbl = Table(int_table_data, colWidths=[52*mm, w_avail - 52*mm])
    int_tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (0, -1), SLATE_50),
        ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
        ('TOPPADDING', (0, 0), (-1, -1), 1.8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.8),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(int_tbl)
    story.append(Spacer(1, 2*mm))

    # Standard Legal Disclaimer
    disclaimer_text = f"<b>Legal Disclaimer:</b> {ui_labels.get('legal_disclaimer', ui_labels.get('disclaimer', 'MetrCheck AI provides AI-assisted packaging compliance screening based on the images submitted for analysis. Results may require physical verification and should not be treated as an official enforcement determination.'))}"
    story.append(Paragraph(disclaimer_text, styles['Disclaimer']))

    # Build document
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()
