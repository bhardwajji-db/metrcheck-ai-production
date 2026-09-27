import os
import uuid
import time
import logging
from datetime import datetime
from utils.datetime_utils import get_current_utc_iso
from fastapi import UploadFile, HTTPException
from config import settings
from ocr.factory import get_ocr_engine
from extraction.llm_extractor import llm_extractor
from compliance.engine import engine as compliance_engine
from compliance.rules.legal_metrology import compute_font_size_and_readability
from database.db import save_analysis
from typing import List, Optional
from models.schemas import AnalysisResponse, OCRResult, ProductInfo, ComplianceResult, ProductImageEvidence
from services.image_service import process_and_save_image
from integrations.fssai.verifier import fssai_verifier
from integrations.gs1.verifier import gs1_verifier
from integrations.cross_checker import cross_check_engine
from services.calibration_service import calibration_service
from vision.pipeline import vision_pipeline
from services.integrity_service import compute_analysis_integrity_hash
from version import SYSTEM_VERSION, OCR_PIPELINE_VERSION, COMPLIANCE_RULESET_VERSION

logger = logging.getLogger(__name__)

QUALIFYING_REVIEW_STATUSES = {
    "REVIEW REQUIRED",
    "POTENTIAL NON-COMPLIANCE",
    "FAIL",
    "NON_COMPLIANT",
    "NEEDS_REVIEW"
}

async def _auto_ingest_officer_review(analysis_id: str, compliance_status: str):
    """
    Phase A-01.3: Automatically incepts an officer review task in PENDING_REVIEW state
    for qualifying compliance verdicts (REVIEW REQUIRED, POTENTIAL NON-COMPLIANCE, FAIL),
    preserving the immutable AI snapshot and tenant organization boundaries.
    Idempotent: will not create duplicate reviews if one already exists.
    """
    if not analysis_id:
        return
    st = str(compliance_status or "").strip().upper()
    if st in QUALIFYING_REVIEW_STATUSES:
        try:
            from services.review_service import get_or_create_review
            await get_or_create_review(analysis_id)
        except Exception as rev_err:
            logger.warning(f"[REVIEW INGESTION] Could not auto-create officer review for {analysis_id}: {rev_err}")

async def analyze_products(
    files: List[UploadFile],
    labels: Optional[List[str]] = None,
    owner_user_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    product_id: Optional[str] = None
) -> AnalysisResponse:
    start_total_time = time.perf_counter()
    analysis_id = str(uuid.uuid4())
    ocr_engine = get_ocr_engine()
    
    default_labels = ["Front", "Back", "Side 1", "Side 2", "Side 3", "Side 4"]
    image_evidences: List[ProductImageEvidence] = []
    all_words = []
    total_processing_time = 0.0

    # ── Phase 1 (fast, sequential): save + quality-assess each image ──
    pending: List[tuple] = []  # (evidence, image_path) to OCR in Phase 2
    for idx, file in enumerate(files):
        label = "Front"
        if labels and idx < len(labels) and labels[idx]:
            label = str(labels[idx]).strip()
        elif idx < len(default_labels):
            label = default_labels[idx]
        else:
            label = f"Image {idx+1}"

        safe_label = label.lower().replace(' ', '_')
        image_filename = f"{analysis_id}_{safe_label}_{file.filename}"
        image_path = os.path.join(settings.UPLOAD_DIR, image_filename)

        t_pre0 = time.perf_counter()
        # 1. Save and preprocess image
        await process_and_save_image(file, image_path)

        # 1b. Assess image quality
        from ocr.quality import assess_image_quality
        quality_data = assess_image_quality(image_path)
        t_pre = (time.perf_counter() - t_pre0) * 1000
        logger.info(f"[PERF] {label} image preprocessing: {t_pre:.1f} ms")

        ev = ProductImageEvidence(
            filename=image_filename,
            image_url=f"/api/images/{image_filename}",
            label=label,
            image_quality=quality_data,
            quality_warning=quality_data.get('warning')
        )
        image_evidences.append(ev)
        pending.append((ev, image_path))

    # ── Phase 2: Sequential OCR & Vision pipeline with explicit garbage collection ──
    # Sequential execution ensures container resident memory (RSS) stays strictly under 512MB
    # even when users analyze 4+ high-resolution product panels simultaneously.
    import gc
    t_ocr_all0 = time.perf_counter()
    ocr_results = []
    for idx, (ev, _path) in enumerate(pending):
        ocr_res = await ocr_engine.extract(_path)
        ocr_results.append(ocr_res)
        logger.info(f"[PERF] {ev.label} OCR: {ocr_res.processing_time * 1000:.1f} ms (passes: {ocr_res.ocr_passes})")

        total_processing_time += ocr_res.processing_time
        all_words.extend(ocr_res.words)
        ev.ocr_text = ocr_res.full_text
        ev.words = ocr_res.words
        ev.word_count = ocr_res.word_count or len(ocr_res.words) or len(ocr_res.full_text.split())
        ev.average_confidence = ocr_res.average_confidence
        ev.preprocessing_variant = ocr_res.preprocessing_variant

        # Run Computer Vision Intelligence Pipeline per-image
        try:
            t_vis0 = time.perf_counter()
            words_dict = [w.model_dump() if hasattr(w, 'model_dump') else w for w in ocr_res.words]
            ev.vision_analysis = vision_pipeline.analyze_image(
                image_path=_path,
                ocr_text=ocr_res.full_text,
                words=words_dict,
                image_index=idx,
                image_label=ev.label
            )
            t_vis = (time.perf_counter() - t_vis0) * 1000
            logger.info(f"[PERF] {ev.label} Computer Vision Analysis: {t_vis:.1f} ms")
        except Exception as e:
            logger.warning(f"[VISION] Failed for image {ev.label}: {e}")

        # Explicitly release image tensors, intermediate crop buffers, and trigger garbage collection
        gc.collect()
        try:
            import ctypes
            ctypes.CDLL('libc.so.6').malloc_trim(0)
        except Exception:
            pass

    t_ocr_all = (time.perf_counter() - t_ocr_all0) * 1000
    logger.info(f"[PERF] Combined OCR & Vision Phase: {t_ocr_all:.1f} ms")

    # 4. Combine OCR text across all images
    if len(image_evidences) == 1:
        combined_text = image_evidences[0].ocr_text
    else:
        combined_text = "\n\n".join([
            f"=== [{ev.label.upper()} LABEL] ===\n{ev.ocr_text}"
            for ev in image_evidences
        ])
        
    avg_conf = round(sum(ev.average_confidence for ev in image_evidences) / len(image_evidences), 1) if image_evidences else 0.0
    total_words = sum(ev.word_count for ev in image_evidences)
    total_regions = sum(r.regions_processed for r in ocr_results) if ocr_results else 0
    
    # Check overall quality warnings
    quality_warnings = [ev.quality_warning for ev in image_evidences if ev.quality_warning]
    combined_quality_warning = " | ".join(quality_warnings) if quality_warnings else None

    primary_ocr = ocr_results[0] if ocr_results else None
    active_engine_name = primary_ocr.engine if primary_ocr else "PaddleOCR (PP-OCRv4)"
    active_variant = primary_ocr.preprocessing_variant if primary_ocr else "Deep Learning Det + Rec"
    ocr_passes_count = sum(r.ocr_passes for r in ocr_results) if ocr_results else 1

    # 5. Extract structured info from combined OCR text with per-image provenance
    t_ext0 = time.perf_counter()
    product_info = llm_extractor.extract(combined_text, images=image_evidences)
    t_ext = (time.perf_counter() - t_ext0) * 1000
    logger.info(f"[PERF] Structured Extraction: {t_ext:.1f} ms")

    combined_ocr_result = OCRResult(
        full_text=combined_text,
        words=all_words,
        language="eng",
        processing_time=round(total_processing_time, 2),
        average_confidence=avg_conf,
        word_count=total_words,
        engine=active_engine_name,
        preprocessing_variant=active_variant,
        regions_processed=total_regions,
        ocr_passes=ocr_passes_count,
        multilingual=getattr(product_info, 'multilingual', None)
    )
    
    # 6. Compliance check with visual proof localization
    t_comp0 = time.perf_counter()
    comp_result_dict = compliance_engine.check(product_info, ocr_text=combined_text, images=image_evidences, analysis_id=analysis_id)
    compliance_result = ComplianceResult(**comp_result_dict)
    t_comp = (time.perf_counter() - t_comp0) * 1000
    logger.info(f"[PERF] Compliance & Evidence: {t_comp:.1f} ms")
    
    # 6B. Physical Calibration & Rule 12 Font Size Analysis
    t_font0 = time.perf_counter()
    primary_img_path = pending[0][1] if pending else None
    calibration_result = None
    if primary_img_path:
        calibration_result = calibration_service.detect_aruco_marker(primary_img_path)

    font_size_analysis = compute_font_size_and_readability(
        product_info=product_info,
        ocr_result=combined_ocr_result,
        images=image_evidences,
        checks=compliance_result.checks,
        calibration_result=calibration_result
    )
    t_font = (time.perf_counter() - t_font0) * 1000
    logger.info(f"[PERF] Calibration & Font Size Analysis: {t_font:.1f} ms")
    
    # 6C. External Verifications (FSSAI Licence & GS1 Barcode)
    fssai_verification = await fssai_verifier.verify(product_info.fssai_license)
    barcode_val = product_info.barcode_detected or getattr(product_info, 'barcode', None) or (product_info.other_declarations.get('barcode') if product_info.other_declarations else None)
    gs1_verification = await gs1_verifier.verify(barcode_val)

    # 6D. Cross-Checking & Statutory Consistency Evaluation (Section 13)
    qr_payload_val = None
    for ev in image_evidences:
        if ev.vision_analysis and ev.vision_analysis.qr_code and ev.vision_analysis.qr_code.detected:
            qr_payload_val = ev.vision_analysis.qr_code.decoded_payload
            if qr_payload_val:
                break

    external_verification = cross_check_engine.evaluate_all(
        extracted_data=product_info.model_dump(),
        fssai_record=fssai_verification,
        gs1_record=gs1_verification,
        qr_payload=qr_payload_val,
        barcode_detected=barcode_val,
        offline_mode=False
    )

    primary_filename = image_evidences[0].filename if image_evidences else ""
    primary_image_url = image_evidences[0].image_url if image_evidences else "/placeholder.png"
    created_at = get_current_utc_iso()
    
    # 7. Save to DB
    # 7. Compute deterministic cryptographic integrity hash (Section 15)
    extracted_dict = product_info.model_dump()
    compliance_dict = compliance_result.model_dump()
    integrity_hash = compute_analysis_integrity_hash(
        analysis_id=analysis_id,
        created_at=created_at,
        product_name=product_info.product_name or 'Unknown Product',
        score=compliance_result.score,
        status=compliance_result.status,
        extracted_data=extracted_dict,
        compliance_result=compliance_dict
    )

    # 8. Save to DB
    t_db0 = time.perf_counter()
    db_data = {
        'id': analysis_id,
        'product_name': product_info.product_name or 'Unknown Product',
        'image_filename': primary_filename,
        'ocr_text': combined_text,
        'extracted_data': extracted_dict,
        'compliance_result': compliance_dict,
        'score': compliance_result.score,
        'status': compliance_result.status,
        'created_at': created_at,
        'images': [ev.model_dump() for ev in image_evidences],
        'owner_user_id': owner_user_id or "",
        'organization_id': organization_id or "",
        'product_id': product_id or "",
        'integrity_hash': integrity_hash,
        'system_version': SYSTEM_VERSION,
        'ocr_engine_version': OCR_PIPELINE_VERSION,
        'ruleset_version': COMPLIANCE_RULESET_VERSION,
    }
    await save_analysis(db_data)
    await _auto_ingest_officer_review(analysis_id, compliance_result.status)
    t_db = (time.perf_counter() - t_db0) * 1000
    logger.info(f"[PERF] DB Save: {t_db:.1f} ms")

    t_total_analysis = (time.perf_counter() - start_total_time) * 1000
    logger.info(f"[PERF] TOTAL Backend Analysis: {t_total_analysis:.1f} ms ({t_total_analysis/1000:.2f} s)")
    
    return AnalysisResponse(
        id=analysis_id,
        product_name=db_data['product_name'],
        image_url=primary_image_url,
        images=image_evidences,
        ocr_result=combined_ocr_result,
        product_info=product_info,
        compliance_result=compliance_result,
        recommendations=compliance_result.recommendations,
        created_at=created_at,
        image_quality_warning=combined_quality_warning,
        font_size_analysis=font_size_analysis,
        fssai_verification=fssai_verification,
        gs1_verification=gs1_verification,
        calibration_result=calibration_result,
        owner_user_id=owner_user_id or "",
        organization_id=organization_id or "",
        multilingual=getattr(product_info, 'multilingual', None),
        vision_analysis=image_evidences[0].vision_analysis if image_evidences else None,
        external_verification=external_verification,
        integrity_hash=integrity_hash,
        system_version=SYSTEM_VERSION,
        ocr_engine_version=OCR_PIPELINE_VERSION,
        ruleset_version=COMPLIANCE_RULESET_VERSION
    )

async def analyze_product(file: UploadFile) -> AnalysisResponse:
    return await analyze_products([file], ["Front"])


async def analyze_text(
    text: str,
    owner_user_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    product_id: Optional[str] = None
) -> AnalysisResponse:
    """Analyze raw product listing or label text without images."""
    analysis_id = str(uuid.uuid4())
    
    # 1. Extract structured info from input text
    product_info = llm_extractor.extract(text)
    
    # 2. Compliance check
    comp_result_dict = compliance_engine.check(product_info, ocr_text=text, images=[])
    compliance_result = ComplianceResult(**comp_result_dict)
    
    # 3. Create minimal OCRResult for text input
    ocr_res = OCRResult(
        full_text=text,
        words=[],
        language="eng",
        processing_time=0.0,
        average_confidence=0.0,
        word_count=len(text.split()),
        engine="Product Listing Text Input",
        preprocessing_variant="None",
        regions_processed=0,
        ocr_passes=1
    )
    
    # 4. Font size analysis placeholder for text
    font_size_analysis = compute_font_size_and_readability(
        product_info=product_info,
        ocr_result=ocr_res,
        images=[],
        checks=compliance_result.checks
    )

    # 5. External Cross-Checking for text mode
    fssai_match = None
    if product_info.fssai_license:
        fssai_match = await fssai_verifier.verify(product_info.fssai_license)
    fssai_verification = fssai_match

    barcode_val = product_info.barcode_detected or getattr(product_info, 'barcode', None) or (product_info.other_declarations.get('barcode') if product_info.other_declarations else None)
    gs1_match = None
    if barcode_val:
        gs1_match = await gs1_verifier.verify(barcode_val)
    gs1_verification = gs1_match

    external_verification = cross_check_engine.evaluate_all(
        extracted_data=product_info.model_dump(),
        fssai_record=fssai_verification,
        gs1_record=gs1_verification,
        qr_payload=None,
        barcode_detected=barcode_val,
        offline_mode=False
    )

    created_at = get_current_utc_iso()
    extracted_dict = product_info.model_dump()
    compliance_dict = compliance_result.model_dump()

    # Deterministic cryptographic integrity hash
    integrity_hash = compute_analysis_integrity_hash(
        analysis_id=analysis_id,
        created_at=created_at,
        product_name=product_info.product_name or 'Unknown Product',
        score=compliance_result.score,
        status=compliance_result.status,
        extracted_data=extracted_dict,
        compliance_result=compliance_dict
    )

    # 6. Save to DB
    db_data = {
        'id': analysis_id,
        'product_name': product_info.product_name or 'Unknown Product',
        'image_filename': "",
        'ocr_text': text,
        'extracted_data': extracted_dict,
        'compliance_result': compliance_dict,
        'score': compliance_result.score,
        'status': compliance_result.status,
        'created_at': created_at,
        'images': [],
        'owner_user_id': owner_user_id or "",
        'organization_id': organization_id or "",
        'product_id': product_id or "",
        'integrity_hash': integrity_hash,
        'system_version': SYSTEM_VERSION,
        'ocr_engine_version': OCR_PIPELINE_VERSION,
        'ruleset_version': COMPLIANCE_RULESET_VERSION,
    }
    await save_analysis(db_data)
    await _auto_ingest_officer_review(analysis_id, compliance_result.status)
    
    return AnalysisResponse(
        id=analysis_id,
        product_name=db_data['product_name'],
        image_url="/placeholder.png",
        images=[],
        ocr_result=ocr_res,
        product_info=product_info,
        compliance_result=compliance_result,
        recommendations=compliance_result.recommendations,
        created_at=created_at,
        image_quality_warning=None,
        font_size_analysis=font_size_analysis,
        fssai_verification=fssai_verification,
        gs1_verification=gs1_verification,
        calibration_result=None,
        owner_user_id=owner_user_id or "",
        organization_id=organization_id or "",
    )


from models.manual_check_schemas import ManualProductCheckRequest

async def analyze_manual(
    req: ManualProductCheckRequest,
    owner_user_id: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> AnalysisResponse:
    """Analyze manually entered package declarations without images (NU-06)."""
    analysis_id = str(uuid.uuid4())
    is_food = (req.product_type.upper() == "FOOD")
    
    # Construct combined manufacturer address if provided
    mfg_combined = None
    if req.manufacturer_name or req.manufacturer_address:
        parts = [p.strip() for p in [req.manufacturer_name, req.manufacturer_address] if p and p.strip()]
        mfg_combined = ", ".join(parts) if parts else None
        
    packer_combined = None
    if req.packer_name or req.packer_address:
        parts = [p.strip() for p in [req.packer_name, req.packer_address] if p and p.strip()]
        packer_combined = ", ".join(parts) if parts else None

    # Construct consumer care summary if phone/email/address provided
    care_parts = []
    if req.consumer_care_phone:
        care_parts.append(f"Phone: {req.consumer_care_phone.strip()}")
    if req.consumer_care_email:
        care_parts.append(f"Email: {req.consumer_care_email.strip()}")
    if req.consumer_care_address:
        care_parts.append(f"Address: {req.consumer_care_address.strip()}")
    consumer_care_combined = ", ".join(care_parts) if care_parts else None

    # Clean dates
    mfg_date = req.manufacture_date.strip() if req.manufacture_date else None
    exp_date = req.expiry_date.strip() if req.expiry_date else None
    best_before = req.best_before.strip() if req.best_before else None

    product_info = ProductInfo(
        product_name=req.product_name.strip(),
        brand=req.brand.strip() if req.brand else None,
        category=req.category.strip() if req.category else None,
        is_food=is_food,
        net_quantity=req.net_quantity.strip() if req.net_quantity else None,
        mrp=req.mrp.strip() if req.mrp else None,
        unit_sale_price=req.unit_sale_price.strip() if req.unit_sale_price else None,
        manufacture_date=mfg_date,
        manufacturing_date=mfg_date,
        expiry_date=exp_date,
        best_before=best_before,
        batch_number=req.batch_number.strip() if req.batch_number else None,
        country_of_origin=req.country_of_origin.strip() if req.country_of_origin else "India",
        manufacturer=mfg_combined,
        manufacturer_name=req.manufacturer_name.strip() if req.manufacturer_name else None,
        manufacturer_address=req.manufacturer_address.strip() if req.manufacturer_address else None,
        packer=packer_combined,
        packer_name=req.packer_name.strip() if req.packer_name else None,
        packer_address=req.packer_address.strip() if req.packer_address else None,
        consumer_care=consumer_care_combined,
        consumer_care_phone=req.consumer_care_phone.strip() if req.consumer_care_phone else None,
        consumer_care_email=req.consumer_care_email.strip() if req.consumer_care_email else None,
        # Food specific
        fssai_license=req.fssai_license.strip() if (is_food and req.fssai_license) else None,
        ingredients=req.ingredients.strip() if (is_food and req.ingredients) else None,
        allergen_info=req.allergen_info.strip() if (is_food and req.allergen_info) else None,
        nutritional_info=req.nutritional_info.strip() if (is_food and req.nutritional_info) else None,
        nutrition_panel_detected=True if (is_food and req.nutritional_info) else None,
        extraction_mode="manual"
    )

    # Compliance check on existing authoritative engine
    comp_result_dict = compliance_engine.check(product_info, ocr_text="", images=[], analysis_id=analysis_id)
    compliance_result = ComplianceResult(**comp_result_dict)

    # Minimal OCRResult indicating manual entry
    ocr_res = OCRResult(
        full_text="[Manual Product Check — User-Provided Package Declarations]",
        words=[],
        language="eng",
        processing_time=0.0,
        average_confidence=0.0,
        word_count=0,
        engine="Manual User Entry",
        preprocessing_variant="None",
        regions_processed=0,
        ocr_passes=0
    )

    # Font size analysis (returns NOT_ASSESSED for manual mode)
    font_size_analysis = compute_font_size_and_readability(
        product_info=product_info,
        ocr_result=ocr_res,
        images=[],
        checks=compliance_result.checks
    )

    # External Cross-Checking for FSSAI if provided
    fssai_verification = None
    if product_info.fssai_license:
        fssai_verification = await fssai_verifier.verify(product_info.fssai_license)

    external_verification = cross_check_engine.evaluate_all(
        extracted_data=product_info.model_dump(),
        fssai_record=fssai_verification,
        gs1_record=None,
        qr_payload=None,
        barcode_detected=None,
        offline_mode=False
    )

    created_at = get_current_utc_iso()
    extracted_dict = product_info.model_dump()
    compliance_dict = compliance_result.model_dump()

    # Deterministic cryptographic integrity hash
    integrity_hash = compute_analysis_integrity_hash(
        analysis_id=analysis_id,
        created_at=created_at,
        product_name=product_info.product_name or 'Unknown Product',
        score=compliance_result.score,
        status=compliance_result.status,
        extracted_data=extracted_dict,
        compliance_result=compliance_dict
    )

    # Save to database
    db_data = {
        'id': analysis_id,
        'product_name': product_info.product_name or 'Unknown Product',
        'image_filename': "",
        'ocr_text': "[Manual Product Check — User-Provided Package Declarations]",
        'extracted_data': extracted_dict,
        'compliance_result': compliance_dict,
        'score': compliance_result.score,
        'status': compliance_result.status,
        'created_at': created_at,
        'images': [],
        'owner_user_id': owner_user_id or "",
        'organization_id': organization_id or "",
        'product_id': "",
        'integrity_hash': integrity_hash,
        'system_version': SYSTEM_VERSION,
        'ocr_engine_version': "None (Manual Entry)",
        'ruleset_version': COMPLIANCE_RULESET_VERSION,
    }
    await save_analysis(db_data)
    await _auto_ingest_officer_review(analysis_id, compliance_result.status)

    return AnalysisResponse(
        id=analysis_id,
        product_name=db_data['product_name'],
        image_url="/placeholder.png",
        images=[],
        ocr_result=ocr_res,
        product_info=product_info,
        compliance_result=compliance_result,
        recommendations=compliance_result.recommendations,
        created_at=created_at,
        image_quality_warning=None,
        font_size_analysis=font_size_analysis,
        fssai_verification=fssai_verification,
        gs1_verification=None,
        calibration_result=None,
        owner_user_id=owner_user_id or "",
        organization_id=organization_id or "",
        external_verification=external_verification,
        integrity_hash=integrity_hash,
        system_version=SYSTEM_VERSION,
        ocr_engine_version="None (Manual Entry)",
        ruleset_version=COMPLIANCE_RULESET_VERSION
    )

