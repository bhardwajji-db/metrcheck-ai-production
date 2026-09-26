import React, { useState, useEffect, useMemo } from 'react';
import { 
  ZoomIn, 
  ZoomOut, 
  RotateCcw, 
  MapPin, 
  Layers, 
  Image as ImageIcon, 
  ArrowUp, 
  ShieldCheck, 
  Sparkles,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  FileText,
  ScanSearch,
  AlertTriangle,
  XCircle,
  Eye,
  Crosshair,
  Target,
  ShieldAlert
} from 'lucide-react';
import { 
  type ProductImageEvidence, 
  type ComplianceCheck, 
  type Recommendation, 
  type OCRResult,
  type EvidenceItem as SchemaEvidenceItem,
  type OCRWord
} from '../types';
import api from '../services/api';
import StatusBadge from './ui/StatusBadge';
import { useLanguage } from '../context/LanguageContext';
import { getLocalizedPanelName, isFrontPanel, getCanonicalPanelType } from '../utils/panelHelper';


export interface EvidenceViewerProps {
  analysisId?: string | null;
  images: ProductImageEvidence[];
  checks: ComplianceCheck[];
  recommendations?: Recommendation[];
  ocrResult?: OCRResult;
  selectedRuleId?: string | null;
  selectionNonce?: number;
  onSelectRule?: (ruleId: string) => void;
  onReturnToRecommendations?: () => void;
}

interface InternalEvidenceItem {
  rule_id: string;
  field: string;
  field_label: string;
  title: string;
  domain: string;
  status: string;
  image_index?: number;
  evidence_image_label: string;
  evidence_region: string;
  confidence?: number | null;
  detected_value?: string | null;
  reason?: string | null;
  recommended_action?: string | null;
  corrective_action?: string | null;
  verification_step?: string | null;
  source_name?: string | null;
  source_reference?: string | null;
  source_url?: string | null;
  bbox?: number[] | null;
  geometry_type?: string;
  match_method?: string;
  evidence_status?: string;
  evidence_type?: string;
  explanation?: string | null;
  pass_reason?: string | null;
  fail_reason?: string | null;
  review_reason?: string | null;
  regulation_reference?: string | null;
  reliability_score?: number | null;
  reliability_tier?: string | null;
  field_status?: string | null;
  candidates?: any[];
  quality_score?: number | null;
  language?: string | null;
  script?: string | null;
  evidence_list: SchemaEvidenceItem[];
}

export default function EvidenceViewer({
  analysisId,
  images = [],
  checks = [],
  recommendations = [],
  ocrResult,
  selectedRuleId,
  selectionNonce,
  onSelectRule,
  onReturnToRecommendations
}: EvidenceViewerProps) {
  const { t } = useLanguage();
  // Normalize images
  const safeImages = useMemo(() => (images && images.length > 0 ? images : []), [images]);
  
  // Assemble complete evidence items by merging check, evidence list, and recommendation data
  const recMap = useMemo(() => {
    const map = new Map<string, Recommendation>();
    (recommendations || []).forEach(r => {
      if (r.rule_id) map.set(r.rule_id, r);
    });
    return map;
  }, [recommendations]);

  const evidenceItems: InternalEvidenceItem[] = useMemo(() => {
    return (checks || []).map(check => {
      const rec = recMap.get(check.rule_id);
      const evList: SchemaEvidenceItem[] = (check.evidence && check.evidence.length > 0)
        ? check.evidence
        : (rec?.evidence && rec.evidence.length > 0 ? rec.evidence : []);
      const primaryEv: SchemaEvidenceItem | undefined = evList[0];
      const imgLabel = primaryEv?.image_label || check.evidence_image_label || rec?.evidence_image_label || 'Back';

      let imgIdx = primaryEv?.image_index;
      if (typeof imgIdx !== 'number' && safeImages.length > 0) {
        const targetType = getCanonicalPanelType(imgLabel);
        if (targetType !== 'other') {
          const canonicalIdx = safeImages.findIndex((img, i) => getCanonicalPanelType(img.label, i) === targetType);
          if (canonicalIdx !== -1) imgIdx = canonicalIdx;
        }
        if (typeof imgIdx !== 'number') {
          const lowerLbl = imgLabel.toLowerCase();
          const found = safeImages.findIndex(img => (img.label || '').toLowerCase().includes(lowerLbl) || lowerLbl.includes((img.label || '').toLowerCase()));
          imgIdx = found !== -1 ? found : (isFrontPanel(imgLabel) ? 0 : Math.min(1, safeImages.length - 1));
        }
      }

      return {
        rule_id: check.rule_id,
        field: check.field,
        field_label: check.field_label || check.rule_id,
        title: rec?.title || check.field_label || check.rule_id,
        domain: check.domain || (check.rule_id.startsWith('FS-') ? 'FSSAI' : 'LEGAL_METROLOGY'),
        status: (check.status || 'PASS').toUpperCase(),
        image_index: imgIdx,
        evidence_image_label: imgLabel,
        evidence_region: check.evidence_region || rec?.evidence_region || 'general_evidence',
        confidence: check.confidence ?? primaryEv?.confidence ?? rec?.confidence ?? null,
        detected_value: check.detected_value,
        reason: check.reason || check.explanation || rec?.issue || null,
        recommended_action: rec?.recommended_action || check.recommendation || null,
        corrective_action: rec?.corrective_action || null,
        verification_step: rec?.verification_step || null,
        source_name: check.source_name || rec?.source_name || null,
        source_reference: check.source_reference || rec?.source_reference || null,
        source_url: check.source_url || rec?.source_url || null,
        bbox: primaryEv?.bbox || check.bbox || rec?.bbox || null,
        geometry_type: primaryEv?.geometry_type || (primaryEv?.bbox || check.bbox ? 'WORD_UNION' : 'NONE'),
        match_method: primaryEv?.match_method || 'DIRECT_OCR',
        evidence_status: primaryEv?.evidence_status || (check.status === 'PASS' ? 'VERIFIED' : 'NEEDS_REVIEW'),
        evidence_type: primaryEv?.evidence_type || (primaryEv?.bbox ? 'DIRECT_OCR' : (check.rule_id === 'LM-009' ? 'DERIVED_FIELD' : (check.status === 'NOT_APPLICABLE' ? 'PROVISO_DELEGATION' : 'NONE'))),
        explanation: primaryEv?.explanation || check.explanation || null,
        pass_reason: check.pass_reason || null,
        fail_reason: check.fail_reason || null,
        review_reason: check.review_reason || null,
        regulation_reference: check.regulation_reference || primaryEv?.regulation_reference || null,
        reliability_score: check.reliability_score ?? primaryEv?.reliability_score ?? null,
        reliability_tier: check.reliability_tier || primaryEv?.reliability_tier || null,
        field_status: check.field_status || null,
        candidates: check.candidates || [],
        quality_score: primaryEv?.quality_score ?? (primaryEv?.bbox ? 90.0 : 0.0),
        language: primaryEv?.language || (check as any).language || null,
        script: primaryEv?.script || (check as any).script || null,
        evidence_list: evList,
      };
    });
  }, [checks, recMap, safeImages]);

  // Helper to reliably find image panel index for any evidence item
  const findImageIndexForItem = (item?: InternalEvidenceItem | null): number => {
    if (!item || safeImages.length === 0) return 0;

    // 1. If explicit valid image_index is provided and within range
    if (typeof item.image_index === 'number' && item.image_index >= 0 && item.image_index < safeImages.length) {
      return item.image_index;
    }

    // 2. Exact or substring match against image labels using canonical panel types
    const targetLabel = (item.evidence_image_label || '').trim();
    if (targetLabel) {
      const targetType = getCanonicalPanelType(targetLabel);
      if (targetType !== 'other') {
        const canonicalIdx = safeImages.findIndex((img, i) => getCanonicalPanelType(img.label, i) === targetType);
        if (canonicalIdx !== -1) return canonicalIdx;
      }

      const exactIdx = safeImages.findIndex(img => (img.label || '').trim().toLowerCase() === targetLabel.toLowerCase());
      if (exactIdx !== -1) return exactIdx;

      const subIdx = safeImages.findIndex(img => {
        const imgLabel = (img.label || '').trim().toLowerCase();
        const tgt = targetLabel.toLowerCase();
        return imgLabel.includes(tgt) || tgt.includes(imgLabel);
      });
      if (subIdx !== -1) return subIdx;
    }

    // 3. Fallback: rule-specific preference (Front for LM-002, FS-002; Back for others)
    if (['LM-002', 'FS-002'].includes(item.rule_id)) {
      const frontIdx = safeImages.findIndex((img, i) => isFrontPanel(img.label, i));
      if (frontIdx !== -1) return frontIdx;
    } else {
      const backIdx = safeImages.findIndex((img, i) => getCanonicalPanelType(img.label, i) === 'back');
      if (backIdx !== -1) return backIdx;
    }

    return 0;
  };

  // Active image index & controls
  const [selectedImageIndex, setSelectedImageIndex] = useState<number>(0);
  const [showCombinedOCR, setShowCombinedOCR] = useState<boolean>(false);
  const [filterByImage, setFilterByImage] = useState<boolean>(false);
  
  // Overlay Toggles
  const [highlightActiveOnly, setHighlightActiveOnly] = useState<boolean>(true);
  const [showAllBBoxes, setShowAllBBoxes] = useState<boolean>(false);
  const [showRawTokens, setShowRawTokens] = useState<boolean>(false);
  const [showIssuesOnly, setShowIssuesOnly] = useState<boolean>(false);

  // Authenticated Image Loading State
  const [imgSrcMap, setImgSrcMap] = useState<Record<number, string>>({});
  const [imgLoadingMap, setImgLoadingMap] = useState<Record<number, boolean>>({});
  const [imgErrorMap, setImgErrorMap] = useState<Record<number, boolean>>({});
  const createdBlobUrlsRef = React.useRef<Set<string>>(new Set());

  // Natural image dimensions state
  const [imgDimensions, setImgDimensions] = useState<{ [key: number]: { width: number; height: number } }>({});

  // Active finding rule ID & active evidence index within finding
  const [activeRuleId, setActiveRuleId] = useState<string>(
    selectedRuleId || (evidenceItems[0]?.rule_id ?? '')
  );
  const [activeEvidenceIndex, setActiveEvidenceIndex] = useState<number>(0);

  // Zoom controls
  const [zoomLevel, setZoomLevel] = useState<number>(1.0);

  // Hover state for interactive bounding box tooltips
  const [hoveredRuleId, setHoveredRuleId] = useState<string | null>(null);

  // Fetch authenticated image blob URLs when safeImages changes
  useEffect(() => {
    let isCancelled = false;

    safeImages.forEach((img, idx) => {
      if (!img?.image_url) return;

      if (img.image_url.startsWith('data:') || img.image_url.startsWith('blob:')) {
        setImgSrcMap(prev => ({ ...prev, [idx]: img.image_url }));
        setImgLoadingMap(prev => ({ ...prev, [idx]: false }));
        setImgErrorMap(prev => ({ ...prev, [idx]: false }));
        return;
      }

      if (!imgSrcMap[idx]) {
        setImgLoadingMap(prev => ({ ...prev, [idx]: true }));
        api.fetchImageBlobUrl(img.image_url)
          .then((resolvedUrl) => {
            if (!isCancelled && resolvedUrl) {
              if (resolvedUrl.startsWith('blob:')) {
                createdBlobUrlsRef.current.add(resolvedUrl);
              }
              setImgSrcMap(prev => ({ ...prev, [idx]: resolvedUrl }));
              setImgLoadingMap(prev => ({ ...prev, [idx]: false }));
              setImgErrorMap(prev => ({ ...prev, [idx]: false }));
            }
          })
          .catch(() => {
            if (!isCancelled) {
              setImgErrorMap(prev => ({ ...prev, [idx]: true }));
              setImgLoadingMap(prev => ({ ...prev, [idx]: false }));
            }
          });
      }
    });

    return () => {
      isCancelled = true;
    };
  }, [safeImages, imgSrcMap]);

  // Cleanup object URLs on unmount
  useEffect(() => {
    return () => {
      createdBlobUrlsRef.current.forEach(url => {
        try {
          URL.revokeObjectURL(url);
        } catch {
          // ignore
        }
      });
      createdBlobUrlsRef.current.clear();
    };
  }, []);

  // Reset all state when switching analysis to prevent cross-analysis state leakage
  useEffect(() => {
    setActiveRuleId(selectedRuleId || (evidenceItems[0]?.rule_id ?? ''));
    setSelectedImageIndex(0);
    setActiveEvidenceIndex(0);
    setZoomLevel(1.0);
    setHoveredRuleId(null);
    setImgSrcMap({});
    setImgLoadingMap({});
    setImgErrorMap({});
  }, [analysisId]);

  // Synchronize when selectedRuleId or selectionNonce changes (e.g. parent View Evidence click)
  useEffect(() => {
    if (selectedRuleId) {
      setActiveRuleId(selectedRuleId);
      setActiveEvidenceIndex(0);
      const targetItem = evidenceItems.find(i => i.rule_id === selectedRuleId);
      if (targetItem && safeImages.length > 0) {
        const foundIdx = findImageIndexForItem(targetItem);
        setSelectedImageIndex(foundIdx);
        setShowCombinedOCR(false);
      }
    }
  }, [selectedRuleId, selectionNonce, evidenceItems, safeImages]);

  // Current active image & active finding
  const activeImage = safeImages[selectedImageIndex] || safeImages[0];
  const activeFinding = evidenceItems.find(i => i.rule_id === activeRuleId) || evidenceItems[0];

  // Active sub-evidence item (for multi-evidence rules like LM-001 name+address, LM-005 phone+email)
  const currentEvidence = useMemo(() => {
    if (!activeFinding) return null;
    if (activeFinding.evidence_list && activeFinding.evidence_list.length > activeEvidenceIndex) {
      return activeFinding.evidence_list[activeEvidenceIndex];
    }
    return null;
  }, [activeFinding, activeEvidenceIndex]);

  const activeBBox = currentEvidence?.bbox ?? activeFinding?.bbox ?? null;
  const activeEvidenceStatus = currentEvidence?.evidence_status ?? activeFinding?.evidence_status ?? 'DETECTED';
  const activeMatchMethod = currentEvidence?.match_method ?? activeFinding?.match_method ?? 'DIRECT_OCR';
  const activeQualityScore = currentEvidence?.quality_score ?? activeFinding?.quality_score ?? (activeBBox ? 90.0 : 0.0);
  const activeEvidenceLabel = currentEvidence?.image_label ?? activeFinding?.evidence_image_label ?? 'Back';

  // Whether active finding belongs to the currently visible image panel
  const isFindingOnCurrentPanel = useMemo(() => {
    if (!activeFinding || !activeImage) return false;
    const targetIdx = currentEvidence?.image_index ?? activeFinding.image_index;
    if (typeof targetIdx === 'number' && targetIdx >= 0 && targetIdx < safeImages.length) {
      return targetIdx === selectedImageIndex;
    }
    const findingLabel = (activeEvidenceLabel || '').trim().toLowerCase();
    const currentLabel = (activeImage.label || '').trim().toLowerCase();
    return findingLabel === currentLabel || currentLabel.includes(findingLabel) || findingLabel.includes(currentLabel);
  }, [activeFinding, currentEvidence, activeEvidenceLabel, activeImage, selectedImageIndex, safeImages.length]);

  // Handler for image natural size capture on load
  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>, idx: number) => {
    const target = e.currentTarget;
    setImgDimensions(prev => ({
      ...prev,
      [idx]: {
        width: target.naturalWidth || 800,
        height: target.naturalHeight || 1200
      }
    }));
  };

  // Select finding handler
  const handleSelectFinding = (item: InternalEvidenceItem) => {
    setActiveRuleId(item.rule_id);
    setActiveEvidenceIndex(0);
    if (onSelectRule) onSelectRule(item.rule_id);

    // Switch image tab if this finding belongs to another image
    if (safeImages.length > 0) {
      const foundIdx = findImageIndexForItem(item);
      if (foundIdx !== selectedImageIndex) {
        setSelectedImageIndex(foundIdx);
        setShowCombinedOCR(false);
      }
    }
  };

  // Filtered evidence items for findings list
  const displayedFindings = useMemo(() => {
    let list = evidenceItems;
    if (showIssuesOnly) {
      list = list.filter(item => {
        const s = (item.status || '').toUpperCase();
        return s === 'FAIL' || s === 'NON_COMPLIANT' || s === 'VIOLATION' || s === 'MISSING' || s === 'NEEDS_REVIEW' || s === 'WARNING';
      });
    }
    if (filterByImage && activeImage) {
      const currentLabel = (activeImage.label || '').trim().toLowerCase();
      list = list.filter(item => {
        const itemLabel = (item.evidence_image_label || '').trim().toLowerCase();
        return item.image_index === selectedImageIndex || itemLabel === currentLabel || currentLabel.includes(itemLabel) || itemLabel.includes(currentLabel);
      });
    }
    return list;
  }, [evidenceItems, showIssuesOnly, filterByImage, activeImage, selectedImageIndex]);

  const currentFindingIndex = displayedFindings.findIndex(i => i.rule_id === activeFinding?.rule_id);

  const handlePrevFinding = () => {
    if (currentFindingIndex > 0) {
      handleSelectFinding(displayedFindings[currentFindingIndex - 1]);
    }
  };

  const handleNextFinding = () => {
    if (currentFindingIndex < displayedFindings.length - 1) {
      handleSelectFinding(displayedFindings[currentFindingIndex + 1]);
    }
  };

  // Zoom handlers
  const handleZoomIn = () => setZoomLevel(prev => Math.min(3.0, +(prev + 0.25).toFixed(2)));
  const handleZoomOut = () => setZoomLevel(prev => Math.max(0.5, +(prev - 0.25).toFixed(2)));
  const handleResetZoom = () => setZoomLevel(1.0);
  const handleFitToggle = () => setZoomLevel(prev => prev === 1.0 ? 1.5 : 1.0);

  // Format clean detected value
  const getFormattedDetectedValue = () => {
    if (!activeFinding?.detected_value || activeFinding.detected_value.trim() === '') {
      return t('evidence.not_reliably_detected', { defaultValue: 'Not reliably detected' });
    }
    return activeFinding.detected_value;
  };

  const isReviewRequired = activeFinding?.status === 'NEEDS_REVIEW' || activeFinding?.status === 'WARNING';
  const isFail = 
    activeFinding?.status === 'FAIL' || 
    activeFinding?.status === 'NON_COMPLIANT' || 
    activeFinding?.status === 'VIOLATION' || 
    activeFinding?.status === 'MISSING';

  const isMissingDeclaration = useMemo(() => {
    if (!activeFinding) return false;
    if (activeFinding.field_status === 'MISSING' || activeFinding.status === 'MISSING') return true;
    if (isFail && !activeBBox) return true;
    const val = (activeFinding.detected_value || '').trim().toLowerCase();
    if (isFail && (!val || val === 'not detected' || val === 'not found' || val === '-' || val === 'null' || val === 'none')) {
      return true;
    }
    const r = (activeFinding.reason || activeFinding.fail_reason || '').toLowerCase();
    if (isFail && (r.includes('missing') || r.includes('not found') || r.includes('absent') || r.includes('not detected'))) {
      return true;
    }
    return false;
  }, [activeFinding, isFail, activeBBox]);

  const issuesCount = useMemo(() => {
    return evidenceItems.filter(i => {
      const s = (i.status || '').toUpperCase();
      return s === 'FAIL' || s === 'NON_COMPLIANT' || s === 'VIOLATION' || s === 'MISSING' || s === 'NEEDS_REVIEW' || s === 'WARNING';
    }).length;
  }, [evidenceItems]);

  // Active image natural dimension
  const currentDim = imgDimensions[selectedImageIndex] || { width: 800, height: 1200 };

  // Statutory missing declaration inspection zone coordinates (custom tailored by rule)
  const missingInspectionZone = useMemo(() => {
    const w = currentDim.width || 800;
    const h = currentDim.height || 1200;
    // Front panel items (Net Quantity, Commodity Name) under Rule 7/8
    if (['LM-002', 'LM-003', 'FS-002'].includes(activeFinding?.rule_id || '')) {
      return {
        x: Math.round(w * 0.08),
        y: Math.round(h * 0.68),
        w: Math.round(w * 0.84),
        h: Math.round(h * 0.24)
      };
    }
    // General / back panel items (MRP, FSSAI, Manufacturer, Consumer Care, Date)
    return {
      x: Math.round(w * 0.08),
      y: Math.round(h * 0.28),
      w: Math.round(w * 0.84),
      h: Math.round(h * 0.36)
    };
  }, [currentDim, activeFinding?.rule_id]);

  // Collect bounding boxes strictly on current active image panel
  const boxesOnCurrentPanel = useMemo(() => {
    if (!activeImage || safeImages.length === 0) return [];
    const currentIdx = selectedImageIndex;
    const currentLabel = (activeImage.label || '').trim().toLowerCase();

    return evidenceItems.filter(item => {
      if (!item.bbox || !Array.isArray(item.bbox) || item.bbox.length !== 4) return false;
      if (typeof item.image_index === 'number' && item.image_index >= 0 && item.image_index < safeImages.length) {
        return item.image_index === currentIdx;
      }
      const itemLabel = (item.evidence_image_label || '').trim().toLowerCase();
      return itemLabel === currentLabel || currentLabel.includes(itemLabel) || itemLabel.includes(currentLabel);
    });
  }, [evidenceItems, activeImage, selectedImageIndex, safeImages.length]);

  // Status colors helper
  const getStatusStrokeColor = (status: string) => {
    const s = (status || '').toUpperCase();
    if (s === 'PASS' || s === 'COMPLIANT' || s === 'VERIFIED') return '#10b981'; // emerald-500
    if (s === 'NEEDS_REVIEW' || s === 'WARNING') return '#f59e0b'; // amber-500
    if (s === 'FAIL' || s === 'NON_COMPLIANT' || s === 'VIOLATION' || s === 'MISSING' || s === 'NOT_FOUND') return '#ef4444'; // red-500
    return '#6366f1'; // indigo-500
  };

  const getStatusFillColor = (status: string) => {
    const s = (status || '').toUpperCase();
    if (s === 'PASS' || s === 'COMPLIANT' || s === 'VERIFIED') return 'rgba(16, 185, 129, 0.18)';
    if (s === 'NEEDS_REVIEW' || s === 'WARNING') return 'rgba(245, 158, 11, 0.22)';
    if (s === 'FAIL' || s === 'NON_COMPLIANT' || s === 'VIOLATION' || s === 'MISSING' || s === 'NOT_FOUND') return 'rgba(239, 68, 68, 0.25)';
    return 'rgba(99, 102, 241, 0.18)';
  };

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 overflow-hidden" tabIndex={0}>
      {/* 1. Header Bar: Evidence Inspector Title & Context */}
      <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-800/50 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 rounded-xl border border-indigo-100 dark:border-indigo-800/60 shadow-2xs">
            <ScanSearch className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100 tracking-tight">
                {t('evidence.title', { defaultValue: 'Evidence Viewer & Visual Proof System' })}
              </h2>
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-indigo-100 dark:bg-indigo-950/70 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800/60">
                {t('evidence.badge_phase', { defaultValue: 'Phase 3 Visual Proof' })}
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              {t('evidence.subtitle', { defaultValue: 'Deterministic OCR bounding boxes and statutory proof links directly mapped onto packaging artwork.' })}
            </p>
          </div>
        </div>

        {/* Action Controls & Navigation */}
        <div className="flex items-center gap-2 flex-wrap">
          {displayedFindings.length > 1 && (
            <div className="flex items-center bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg p-0.5 shadow-2xs">
              <button
                type="button"
                onClick={handlePrevFinding}
                disabled={currentFindingIndex <= 0}
                className="p-1.5 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white disabled:opacity-30 disabled:cursor-not-allowed rounded hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                title={t('evidence.prev_finding', { defaultValue: 'Previous finding' })}
                aria-label={t('evidence.prev_finding', { defaultValue: 'Previous finding' })}
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-xs font-mono font-semibold text-slate-700 dark:text-slate-300 px-2 select-none border-x border-slate-100 dark:border-slate-800">
                {currentFindingIndex >= 0 ? currentFindingIndex + 1 : 1} of {displayedFindings.length}
              </span>
              <button
                type="button"
                onClick={handleNextFinding}
                disabled={currentFindingIndex >= displayedFindings.length - 1}
                className="p-1.5 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white disabled:opacity-30 disabled:cursor-not-allowed rounded hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                title={t('evidence.next_finding', { defaultValue: 'Next finding' })}
                aria-label={t('evidence.next_finding', { defaultValue: 'Next finding' })}
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}

          {onReturnToRecommendations && (
            <button
              type="button"
              onClick={onReturnToRecommendations}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-lg text-xs font-semibold shadow-2xs transition-all cursor-pointer"
            >
              <ArrowUp className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
              <span>{t('evidence.back_to_top', { defaultValue: 'Back to Top' })}</span>
            </button>
          )}
        </div>
      </div>

      {/* 2. Image Tabs, Overlay Toggles & Zoom Controls */}
      <div className="px-6 py-3 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-wrap items-center justify-between gap-3">
        {/* Package Image Tabs */}
        <div className="flex items-center gap-2 flex-wrap" role="tablist" aria-label="Package Image Panels">
          <span className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider mr-1">
            {t('evidence.package_faces', { defaultValue: 'Package Faces:' })}
          </span>
          {safeImages.map((img, idx) => {
            const isSelected = !showCombinedOCR && selectedImageIndex === idx;
            return (
              <button
                key={idx}
                role="tab"
                aria-selected={isSelected}
                onClick={() => {
                  setSelectedImageIndex(idx);
                  setShowCombinedOCR(false);
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-indigo-600 text-white shadow-xs'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 border border-transparent'
                }`}
              >
                <ImageIcon className="w-3.5 h-3.5" />
                <span>{getLocalizedPanelName(img.label, idx, t)}</span>
                {img.word_count ? (
                  <span className={`text-[10px] px-1.5 py-0.2 rounded-full ${isSelected ? 'bg-indigo-500 text-white' : 'bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300'}`}>
                    {img.word_count}w
                  </span>
                ) : null}
              </button>
            );
          })}

          {safeImages.length > 1 && (
            <button
              type="button"
              onClick={() => setShowCombinedOCR(prev => !prev)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                showCombinedOCR
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>{showCombinedOCR ? t('evidence.hide_ocr', { defaultValue: 'Hide OCR' }) : t('evidence.combined_ocr', { defaultValue: 'Combined OCR Text' })}</span>
            </button>
          )}
        </div>

        {/* Visual Proof Layer Controls & Zoom Bar */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* Overlay Toggle Buttons */}
          <div className="flex items-center bg-slate-100 dark:bg-slate-800 p-1 rounded-lg border border-slate-200 dark:border-slate-700 text-xs font-semibold gap-1">
            <button
              type="button"
              onClick={() => {
                setHighlightActiveOnly(true);
                setShowAllBBoxes(false);
                setShowIssuesOnly(false);
              }}
              className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                highlightActiveOnly && !showAllBBoxes && !showIssuesOnly
                  ? 'bg-indigo-600 text-white shadow-2xs'
                  : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
              }`}
              title="Highlight only the selected compliance finding"
            >
              <Crosshair className="w-3.5 h-3.5 inline mr-1" />
              {t('evidence.active_finding', { defaultValue: 'Active Finding' })}
            </button>

            {issuesCount > 0 && (
              <button
                type="button"
                onClick={() => {
                  setShowIssuesOnly(prev => {
                    const next = !prev;
                    if (next) {
                      setHighlightActiveOnly(false);
                      setShowAllBBoxes(true);
                    }
                    return next;
                  });
                }}
                className={`px-2.5 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
                  showIssuesOnly
                    ? 'bg-red-600 text-white shadow-2xs font-bold'
                    : 'text-red-700 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 font-semibold'
                }`}
                title="Show red boxes for all issues and missing items"
              >
                <span className="w-2 h-2 rounded-full bg-red-500 inline-block animate-pulse"></span>
                <span>🔴 Issues & Missing ({issuesCount})</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => {
                setShowAllBBoxes(prev => !prev);
                setHighlightActiveOnly(false);
              }}
              className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                showAllBBoxes
                  ? 'bg-indigo-600 text-white shadow-2xs'
                  : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
              }`}
              title="Show all statutory finding boxes on this panel"
            >
              <Eye className="w-3.5 h-3.5 inline mr-1" />
              {t('evidence.all_rules', { defaultValue: 'All Rules' })} ({boxesOnCurrentPanel.length})
            </button>

            <button
              type="button"
              onClick={() => setShowRawTokens(prev => !prev)}
              className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                showRawTokens
                  ? 'bg-indigo-600 text-white shadow-2xs'
                  : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
              }`}
              title="Display fine bounding boxes for all OCR word tokens"
            >
              {t('evidence.raw_ocr_boxes', { defaultValue: 'Raw OCR Boxes' })}
            </button>
          </div>

          {/* Zoom & Canvas Controls */}
          <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg border border-slate-200 dark:border-slate-700">
            <button
              type="button"
              onClick={handleZoomOut}
              title="Zoom out (25%)"
              aria-label="Zoom out"
              className="p-1.5 rounded hover:bg-white dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={handleFitToggle}
              title="Toggle 100% / 150%"
              className="text-xs font-mono font-semibold text-slate-700 dark:text-slate-300 px-2 min-w-[50px] text-center select-none hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors cursor-pointer"
            >
              {Math.round(zoomLevel * 100)}%
            </button>
            <button
              type="button"
              onClick={handleZoomIn}
              title="Zoom in (25%)"
              aria-label="Zoom in"
              className="p-1.5 rounded hover:bg-white dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={handleResetZoom}
              title="Reset Zoom & View"
              aria-label="Reset View"
              className="p-1.5 rounded hover:bg-white dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition-colors ml-0.5 cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* 3. Main Split View: Left Interactive Canvas (7 Cols) & Right Finding Details (5 Cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-0 divide-y lg:divide-y-0 lg:divide-x divide-slate-200 dark:divide-slate-800">
        
        {/* Left Side: Package Artwork Inspection Canvas with Interactive Overlays */}
        <div className="lg:col-span-7 p-6 flex flex-col justify-between bg-slate-900/5 dark:bg-slate-950/40 min-h-[540px]">
          
          {/* Top Canvas Bar */}
          <div className="w-full mb-3 flex items-center justify-between text-xs gap-2 flex-wrap">
            <div className="flex items-center gap-2 font-medium text-slate-700 dark:text-slate-300">
              <MapPin className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0" />
              <span>{t('evidence.inspecting', { defaultValue: 'Inspecting:' })}</span>
              <span className="font-mono font-bold text-slate-900 dark:text-slate-100 bg-white dark:bg-slate-800 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-700 shadow-2xs">
                {activeFinding?.rule_id || t('evidence.screening_overview', { defaultValue: 'Screening Overview' })}
              </span>
              <span className="text-slate-600 dark:text-slate-400 truncate max-w-[200px] font-semibold">
                {activeFinding?.title}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
                {t('evidence.face', { defaultValue: 'Face:' })} {getLocalizedPanelName(activeImage?.label, selectedImageIndex, t)}
              </span>
              {activeBBox && (
                <span className="text-[10px] font-mono text-indigo-600 dark:text-indigo-400 font-bold bg-indigo-50 dark:bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-200 dark:border-indigo-800/60">
                  [{activeBBox.join(', ')}]
                </span>
              )}
            </div>
          </div>

          {/* Interactive Package Image & SVG Overlay Canvas */}
          <div 
            className="relative w-full max-h-[560px] flex items-center justify-center overflow-auto rounded-xl bg-slate-950 p-4 border border-slate-800 shadow-inner"
          >
            {imgLoadingMap[selectedImageIndex] && !imgSrcMap[selectedImageIndex] ? (
              <div className="py-20 flex flex-col items-center justify-center text-slate-400 space-y-3">
                <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                <span className="text-xs font-semibold text-slate-300">{t('evidence.loading_image', { defaultValue: 'Loading evidence image...' })}</span>
                <span className="text-[11px] text-slate-500 font-mono">{t('evidence.panel', { defaultValue: 'Panel:' })} {getLocalizedPanelName(activeImage?.label, selectedImageIndex, t)}</span>
              </div>
            ) : (activeImage?.image_url && imgSrcMap[selectedImageIndex] && !imgErrorMap[selectedImageIndex]) ? (
              <div 
                className="relative inline-block transition-transform duration-150 origin-center"
                style={{ transform: `scale(${zoomLevel})` }}
              >
                {/* Floating Hover Tooltip */}
                {hoveredRuleId && (
                  <div className="absolute top-3 left-3 z-20 bg-slate-900/90 text-white text-xs px-3 py-1.5 rounded-lg border border-slate-700 shadow-lg backdrop-blur-sm pointer-events-none flex items-center gap-2">
                    <span className="font-mono font-bold text-indigo-400">{hoveredRuleId}</span>
                    <span className="text-slate-300 truncate max-w-[220px]">
                      {evidenceItems.find(i => i.rule_id === hoveredRuleId)?.title}
                    </span>
                  </div>
                )}

                {/* 1. Underlying Base Package Image */}
                <img
                  src={imgSrcMap[selectedImageIndex]}
                  alt={`${getLocalizedPanelName(activeImage?.label, selectedImageIndex, t)} Package View`}
                  className="max-h-[480px] max-w-full object-contain rounded select-none shadow-md block"
                  onLoad={(e) => handleImageLoad(e, selectedImageIndex)}
                  onError={() => {
                    setImgErrorMap(prev => ({ ...prev, [selectedImageIndex]: true }));
                    setImgLoadingMap(prev => ({ ...prev, [selectedImageIndex]: false }));
                  }}
                />

                {/* 2. Scaled SVG Overlay with Bounding Boxes & Interactive Highlights */}
                <svg
                  className="absolute inset-0 w-full h-full pointer-events-auto"
                  viewBox={`0 0 ${currentDim.width} ${currentDim.height}`}
                  preserveAspectRatio="xMidYMid meet"
                >
                  <defs>
                    {/* Pulsing filter for active finding */}
                    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                      <feGaussianBlur stdDeviation="4" result="blur" />
                      <feComposite in="SourceGraphic" in2="blur" operator="over" />
                    </filter>
                    <filter id="red-glow" x="-30%" y="-30%" width="160%" height="160%">
                      <feDropShadow dx="0" dy="0" stdDeviation="6" floodColor="#ef4444" floodOpacity="0.85" />
                    </filter>
                  </defs>

                  {/* 2A. Raw OCR Word Token Boxes (if toggled on) */}
                  {showRawTokens && activeImage.words && activeImage.words.map((w: OCRWord, wIdx: number) => {
                    const bx = w.bbox[0];
                    const by = w.bbox[1];
                    const bw = Math.max(1, w.bbox[2] - w.bbox[0]);
                    const bh = Math.max(1, w.bbox[3] - w.bbox[1]);
                    return (
                      <rect
                        key={`raw-word-${wIdx}`}
                        x={bx}
                        y={by}
                        width={bw}
                        height={bh}
                        fill="rgba(99, 102, 241, 0.06)"
                        stroke="rgba(99, 102, 241, 0.45)"
                        strokeWidth="1.2"
                        strokeDasharray="3 3"
                        className="pointer-events-none"
                      />
                    );
                  })}

                  {/* 2B. All Rules Bounding Boxes on this Panel (if toggled on) */}
                  {showAllBBoxes && (showIssuesOnly 
                    ? boxesOnCurrentPanel.filter(i => {
                        const s = (i.status || '').toUpperCase();
                        return s === 'FAIL' || s === 'NON_COMPLIANT' || s === 'VIOLATION' || s === 'MISSING' || s === 'NEEDS_REVIEW' || s === 'WARNING';
                      })
                    : boxesOnCurrentPanel
                  ).map((item, bIdx) => {
                    if (!item.bbox) return null;
                    const bx = item.bbox[0];
                    const by = item.bbox[1];
                    const bw = Math.max(2, item.bbox[2] - item.bbox[0]);
                    const bh = Math.max(2, item.bbox[3] - item.bbox[1]);
                    const isSelected = item.rule_id === activeFinding?.rule_id;
                    const strokeColor = getStatusStrokeColor(item.status);
                    const fillColor = getStatusFillColor(item.status);
                    const isItemFail = item.status === 'FAIL' || item.status === 'NON_COMPLIANT' || item.status === 'VIOLATION' || item.status === 'MISSING';

                    return (
                      <g 
                        key={`all-box-${item.rule_id}-${bIdx}`}
                        className="cursor-pointer transition-opacity hover:opacity-100"
                        onClick={() => handleSelectFinding(item)}
                        onMouseEnter={() => setHoveredRuleId(item.rule_id)}
                        onMouseLeave={() => setHoveredRuleId(null)}
                      >
                        <rect
                          x={bx}
                          y={by}
                          width={bw}
                          height={bh}
                          fill={fillColor}
                          stroke={strokeColor}
                          strokeWidth={isSelected ? "3.5" : (isItemFail ? "2.5" : "1.8")}
                          rx="3"
                          filter={isItemFail ? "url(#red-glow)" : undefined}
                        />
                        {/* Rule Label Tag at top-left of box */}
                        <rect
                          x={bx}
                          y={Math.max(0, by - 16)}
                          width={Math.max(50, item.rule_id.length * 8 + (isItemFail ? 20 : 8))}
                          height="15"
                          fill={strokeColor}
                          rx="2"
                        />
                        <text
                          x={bx + 4}
                          y={Math.max(11, by - 4)}
                          fill="#ffffff"
                          fontSize="10"
                          fontFamily="monospace"
                          fontWeight="bold"
                        >
                          {isItemFail ? '❌ ' : ''}{item.rule_id}
                        </text>
                      </g>
                    );
                  })}

                  {/* 2C. Active Selected Rule Bounding Box (High Visibility & Pulsing Highlight) */}
                  {isFindingOnCurrentPanel && activeBBox && (
                    <g 
                      className="cursor-pointer"
                      onMouseEnter={() => setHoveredRuleId(activeFinding.rule_id)}
                      onMouseLeave={() => setHoveredRuleId(null)}
                    >
                      {/* Pulsing Outer Aura */}
                      <rect
                        x={activeBBox[0] - 4}
                        y={activeBBox[1] - 4}
                        width={Math.max(8, activeBBox[2] - activeBBox[0] + 8)}
                        height={Math.max(8, activeBBox[3] - activeBBox[1] + 8)}
                        fill="none"
                        stroke={isFail ? "#ef4444" : getStatusStrokeColor(activeFinding.status)}
                        strokeWidth={isFail ? "4" : "2.5"}
                        strokeDasharray={isFail ? "6 3" : "4 2"}
                        rx="6"
                        opacity="0.9"
                        filter={isFail ? "url(#red-glow)" : "url(#glow)"}
                        className="animate-pulse"
                      />

                      {/* Main Solid Box */}
                      <rect
                        x={activeBBox[0]}
                        y={activeBBox[1]}
                        width={Math.max(2, activeBBox[2] - activeBBox[0])}
                        height={Math.max(2, activeBBox[3] - activeBBox[1])}
                        fill={isFail ? "rgba(239, 68, 68, 0.28)" : getStatusFillColor(activeFinding.status)}
                        stroke={isFail ? "#dc2626" : getStatusStrokeColor(activeFinding.status)}
                        strokeWidth={isFail ? "4" : "3.5"}
                        rx="4"
                      />

                      {/* Prominent High-Contrast Label Tag */}
                      <g transform={`translate(${activeBBox[0]}, ${Math.max(0, activeBBox[1] - 24)})`}>
                        <rect
                          x="0"
                          y="0"
                          width={Math.max(85, activeFinding.rule_id.length * 9 + (isFail ? 95 : (currentEvidence?.field_type ? 65 : 45)))}
                          height="22"
                          fill={isFail ? "#dc2626" : "#0f172a"}
                          stroke={isFail ? "#fca5a5" : getStatusStrokeColor(activeFinding.status)}
                          strokeWidth="1.5"
                          rx="4"
                          filter={isFail ? "url(#red-glow)" : "url(#glow)"}
                        />
                        <circle
                          cx="10"
                          cy="11"
                          r="4"
                          fill={isFail ? "#ffffff" : getStatusStrokeColor(activeFinding.status)}
                        />
                        <text
                          x="20"
                          y="15"
                          fill="#ffffff"
                          fontSize="11"
                          fontFamily="monospace"
                          fontWeight="bold"
                        >
                          {isFail ? '❌ DEFECT: ' : ''}{activeFinding.rule_id}{currentEvidence?.field_type ? ` [${currentEvidence.field_type}]` : ''} · {activeFinding.status}
                        </text>
                      </g>
                    </g>
                  )}

                  {/* 2D. Active Missing Mandatory Declaration Inspection Red Box */}
                  {isFindingOnCurrentPanel && isMissingDeclaration && !activeBBox && (
                    <g className="cursor-pointer">
                      {/* Pulsing red aura frame */}
                      <rect
                        x={missingInspectionZone.x}
                        y={missingInspectionZone.y}
                        width={missingInspectionZone.w}
                        height={missingInspectionZone.h}
                        fill="rgba(239, 68, 68, 0.16)"
                        stroke="#dc2626"
                        strokeWidth="3.5"
                        strokeDasharray="10 6"
                        rx="8"
                        filter="url(#red-glow)"
                        className="animate-pulse"
                      />

                      {/* 4 Corner Crosshairs */}
                      <path
                        d={`M ${missingInspectionZone.x} ${missingInspectionZone.y + 24} L ${missingInspectionZone.x} ${missingInspectionZone.y} L ${missingInspectionZone.x + 24} ${missingInspectionZone.y}
                            M ${missingInspectionZone.x + missingInspectionZone.w - 24} ${missingInspectionZone.y} L ${missingInspectionZone.x + missingInspectionZone.w} ${missingInspectionZone.y} L ${missingInspectionZone.x + missingInspectionZone.w} ${missingInspectionZone.y + 24}
                            M ${missingInspectionZone.x} ${missingInspectionZone.y + missingInspectionZone.h - 24} L ${missingInspectionZone.x} ${missingInspectionZone.y + missingInspectionZone.h} L ${missingInspectionZone.x + 24} ${missingInspectionZone.y + missingInspectionZone.h}
                            M ${missingInspectionZone.x + missingInspectionZone.w - 24} ${missingInspectionZone.y + missingInspectionZone.h} L ${missingInspectionZone.x + missingInspectionZone.w} ${missingInspectionZone.y + missingInspectionZone.h} L ${missingInspectionZone.x + missingInspectionZone.w} ${missingInspectionZone.y + missingInspectionZone.h - 24}`}
                        fill="none"
                        stroke="#ef4444"
                        strokeWidth="4"
                        strokeLinecap="round"
                      />

                      {/* Prominent Red Tag on Top */}
                      <g transform={`translate(${missingInspectionZone.x}, ${Math.max(4, missingInspectionZone.y - 28)})`}>
                        <rect
                          x="0"
                          y="0"
                          width={Math.min(missingInspectionZone.w, Math.max(300, (activeFinding?.rule_id?.length || 6) * 10 + 220))}
                          height="26"
                          fill="#dc2626"
                          stroke="#b91c1c"
                          strokeWidth="1.5"
                          rx="6"
                          filter="url(#red-glow)"
                        />
                        <text
                          x="12"
                          y="18"
                          fill="#ffffff"
                          fontSize="12"
                          fontFamily="monospace"
                          fontWeight="bold"
                        >
                          ❌ MISSING MANDATORY: {activeFinding?.rule_id}
                        </text>
                      </g>

                      {/* Center Defect Alert Card */}
                      <g transform={`translate(${missingInspectionZone.x + missingInspectionZone.w / 2 - Math.min(230, missingInspectionZone.w / 2 - 10)}, ${missingInspectionZone.y + missingInspectionZone.h / 2 - 32})`}>
                        <rect
                          x="0"
                          y="0"
                          width={Math.min(460, missingInspectionZone.w - 20)}
                          height="64"
                          fill="#7f1d1d"
                          fillOpacity="0.94"
                          stroke="#ef4444"
                          strokeWidth="2"
                          rx="8"
                          filter="url(#red-glow)"
                        />
                        <text
                          x={Math.min(460, missingInspectionZone.w - 20) / 2}
                          y="24"
                          textAnchor="middle"
                          fill="#ffffff"
                          fontSize="13"
                          fontFamily="sans-serif"
                          fontWeight="bold"
                        >
                          ⚠️ MANDATORY STATUTORY DECLARATION MISSING
                        </text>
                        <text
                          x={Math.min(460, missingInspectionZone.w - 20) / 2}
                          y="42"
                          textAnchor="middle"
                          fill="#fca5a5"
                          fontSize="11"
                          fontFamily="sans-serif"
                          fontWeight="600"
                        >
                          {activeFinding?.title} — Not found anywhere on this package panel
                        </text>
                        <text
                          x={Math.min(460, missingInspectionZone.w - 20) / 2}
                          y="56"
                          textAnchor="middle"
                          fill="#fecaca"
                          fontSize="10"
                          fontFamily="monospace"
                        >
                          Legal Metrology Rules 2011 / FSSAI Labelling Violation
                        </text>
                      </g>
                    </g>
                  )}
                </svg>

                {/* Non-Visual / Derived Finding Notice on Image Canvas */}
                {(!activeBBox || !isFindingOnCurrentPanel) && !isMissingDeclaration && (
                  <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-20 bg-slate-900/95 text-white text-xs px-3.5 py-1.5 rounded-xl border border-slate-700 shadow-xl backdrop-blur-md flex items-center gap-2 max-w-[92%] pointer-events-none">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                    <span className="text-slate-300 text-[11px] font-medium truncate">
                      {!isFindingOnCurrentPanel 
                        ? `Evidence located on ${activeEvidenceLabel || 'another'} panel (switch package face above)`
                        : activeFinding?.rule_id === 'LM-009'
                        ? 'Cross-field declaration consistency check — synthesized across packaging fields'
                        : activeFinding?.status === 'NOT_APPLICABLE'
                        ? 'Statutory food proviso delegates requirement to FSSAI (Rule FS-005)'
                        : 'Declaration evaluated via OCR text; no isolated bounding box'}
                    </span>
                  </div>
                )}

                {/* Interactive Switch Panel Button for Defect / Missing Evidence on other panels */}
                {!isFindingOnCurrentPanel && (
                  <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-20 pointer-events-auto">
                    <button
                      type="button"
                      onClick={() => {
                        const foundIdx = findImageIndexForItem(activeFinding);
                        setSelectedImageIndex(foundIdx);
                        setShowCombinedOCR(false);
                      }}
                      className="bg-red-600 hover:bg-red-700 text-white text-xs font-bold px-4 py-2 rounded-xl border border-red-300 shadow-2xl flex items-center gap-2 cursor-pointer transition-transform hover:scale-105 active:scale-95 animate-pulse"
                    >
                      <Target className="w-4 h-4 text-white" />
                      <span>Evidence is on the {activeEvidenceLabel} panel — Click here to switch panel & view Red Box</span>
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="py-20 flex flex-col items-center justify-center text-slate-400 dark:text-slate-500 space-y-2 text-center p-6">
                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-slate-500 mb-1">
                  <ImageIcon className="w-8 h-8 stroke-[1.5]" />
                </div>
                <span className="text-sm font-bold text-slate-300">{t('evidence.image_unavailable', { defaultValue: 'Evidence image unavailable' })}</span>
                <span className="text-xs text-slate-500 max-w-sm">
                  {t('evidence.image_unavailable_desc', { label: getLocalizedPanelName(activeImage?.label, selectedImageIndex, t), defaultValue: 'The package image could not be loaded.' })}
                </span>
              </div>
            )}
          </div>

          {/* Canvas Footer Bar */}
          <div className="w-full mt-3 pt-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 flex-wrap gap-2">
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
              <span className="font-semibold text-slate-700 dark:text-slate-300">
                {t('evidence.live_boxes', { defaultValue: 'Live PaddleOCR Visual Bounding Boxes' })}
              </span>
              <span className="text-slate-400 dark:text-slate-600">•</span>
              <span className="font-mono">{t('evidence.resolution', { defaultValue: 'Resolution:' })} {currentDim.width} x {currentDim.height}px</span>
            </span>
            <span className="font-mono text-[10px]">
              {t('evidence.zoom', { defaultValue: 'Zoom:' })} {Math.round(zoomLevel * 100)}%
            </span>
          </div>
        </div>

        {/* Right Side: Finding Details & Statutory Evidence Chain (5 Cols) */}
        <div className="lg:col-span-5 p-6 flex flex-col space-y-5 bg-white dark:bg-slate-900">
          
          {/* Finding Header */}
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                {t('evidence.finding_details', { defaultValue: 'Finding Details' })}
              </h3>
              <p className="text-xs text-slate-400 dark:text-slate-500">
                {t('evidence.audit_trail', { defaultValue: 'Statutory audit trail & evidence chain' })}
              </p>
            </div>
            {activeFinding?.status && (
              <StatusBadge status={activeFinding.status} />
            )}
          </div>

          {/* Evidence Details Content */}
          {activeFinding ? (
            <div className="space-y-4">
              
              {/* Evidence Chain Flow (5-Stage Trust Pipeline) */}
              <div className="bg-slate-50 dark:bg-slate-800/50 border border-slate-200/80 dark:border-slate-700/70 rounded-xl p-3">
                <div className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1">
                  <Sparkles className="w-3 h-3 text-indigo-500 dark:text-indigo-400" /> {t('evidence.evidence_chain', { defaultValue: 'Statutory Evidence Chain' })}
                </div>
                <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-600 dark:text-slate-300 overflow-x-auto pb-1">
                  <span className="px-2 py-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-md font-semibold text-slate-800 dark:text-slate-200 shrink-0">
                    📸 {activeEvidenceLabel || 'Package'}
                  </span>
                  <span className="text-slate-400 shrink-0">→</span>
                  <span className="px-2 py-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-md text-slate-700 dark:text-slate-300 shrink-0 font-mono">
                    📐 {currentEvidence?.geometry_type || activeFinding.geometry_type || 'BBOX'}
                  </span>
                  <span className="text-slate-400 shrink-0">→</span>
                  <span className="px-2 py-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-md font-semibold text-slate-800 dark:text-slate-200 shrink-0">
                    📝 {activeFinding.field_label || activeFinding.field}
                  </span>
                  <span className="text-slate-400 shrink-0">→</span>
                  <span className="px-2 py-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-md font-mono font-bold text-indigo-700 dark:text-indigo-300 shrink-0">
                    ⚖️ {activeFinding.rule_id}
                  </span>
                  <span className="text-slate-400 shrink-0">→</span>
                  <span className="shrink-0">
                    <StatusBadge status={activeFinding.status} size="sm" />
                  </span>
                </div>
              </div>

              {/* Finding Title, Domain, Evidence Status & Method Badges */}
              <div>
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className="font-mono text-xs font-bold px-2 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded border border-slate-200 dark:border-slate-700">
                    {activeFinding.rule_id}
                  </span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                    activeFinding.domain === 'FSSAI' 
                      ? 'bg-orange-50 dark:bg-orange-950/60 text-orange-700 dark:text-orange-300 border border-orange-200 dark:border-orange-800/60'
                      : 'bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800/60'
                  }`}>
                    {activeFinding.domain.replace(/_/g, ' ')}
                  </span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                    activeEvidenceStatus === 'VERIFIED'
                      ? 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300'
                      : activeEvidenceStatus === 'NEEDS_REVIEW' || activeEvidenceStatus === 'CONTEXTUAL'
                      ? 'bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                  }`}>
                    {t('evidence.evidence_label', { defaultValue: 'Evidence:' })} {activeEvidenceStatus}
                  </span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800/60">
                    {activeMatchMethod.replace(/_/g, ' ')}
                  </span>
                  {activeQualityScore > 0 && (
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-mono">
                      Q-Score: {Math.round(activeQualityScore)}%
                    </span>
                  )}
                  {activeFinding.reliability_tier && (
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase font-mono ${
                      activeFinding.reliability_tier === 'HIGH'
                        ? 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700'
                        : activeFinding.reliability_tier === 'MEDIUM'
                        ? 'bg-blue-100 dark:bg-blue-950/60 text-blue-800 dark:text-blue-300 border border-blue-300 dark:border-blue-700'
                        : activeFinding.reliability_tier === 'LOW'
                        ? 'bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-700'
                        : 'bg-rose-100 dark:bg-rose-950/60 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-700'
                    }`}>
                      🛡️ {t('evidence.reliability', { defaultValue: 'Reliability:' })} {activeFinding.reliability_tier} ({Math.round(activeFinding.reliability_score ?? 0)}%)
                    </span>
                  )}
                  {(currentEvidence?.language || activeFinding.language) && (
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800/60 font-mono">
                      🌐 {(currentEvidence?.language || activeFinding.language)?.toUpperCase()}
                      {(currentEvidence?.script || activeFinding.script) ? ` · ${currentEvidence?.script || activeFinding.script}` : ''}
                    </span>
                  )}
                </div>
                <h4 className="text-base font-bold text-slate-900 dark:text-slate-100 leading-snug">
                  {activeFinding.title}
                </h4>
              </div>

              {/* Multi-Evidence Item Switcher (e.g. Phone vs Email, Name vs Address) */}
              {activeFinding.evidence_list && activeFinding.evidence_list.length > 1 && (
                <div className="bg-slate-100/90 dark:bg-slate-800/80 p-2.5 rounded-xl border border-slate-200 dark:border-slate-700">
                  <div className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 flex items-center justify-between">
                    <span>{t('evidence.multi_item_proof', { defaultValue: 'Multi-Item Statutory Proof' })} ({activeFinding.evidence_list.length})</span>
                    <span className="text-[10px] text-indigo-600 dark:text-indigo-400 font-semibold">{t('evidence.select_item_highlight', { defaultValue: 'Select item to highlight' })}</span>
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    {activeFinding.evidence_list.map((ev, evIdx) => {
                      const isEvSelected = activeEvidenceIndex === evIdx;
                      return (
                        <button
                          key={ev.id || `ev-${evIdx}`}
                          type="button"
                          onClick={() => {
                            setActiveEvidenceIndex(evIdx);
                            if (typeof ev.image_index === 'number' && ev.image_index >= 0 && ev.image_index < safeImages.length) {
                              setSelectedImageIndex(ev.image_index);
                            }
                          }}
                          className={`px-3 py-1.5 text-xs rounded-lg font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
                            isEvSelected 
                              ? 'bg-indigo-600 text-white shadow-xs font-semibold' 
                              : 'bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-600'
                          }`}
                        >
                          <span>{ev.field_type || `Item ${evIdx + 1}`}</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                            isEvSelected ? 'bg-indigo-700 text-indigo-100' : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
                          }`}>
                            {ev.evidence_status || 'DETECTED'}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Status & Confidence Dual Badges */}
              <div className="grid grid-cols-2 gap-2.5">
                <div className="p-3 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl">
                  <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-1">
                    {t('evidence.screening_status', { defaultValue: 'Screening Status' })}
                  </span>
                  <div>
                    <StatusBadge status={activeFinding.status} />
                  </div>
                </div>

                <div className="p-3 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl">
                  <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-1">
                    {t('evidence.ocr_confidence', { defaultValue: 'OCR Confidence' })}
                  </span>
                  <div className="text-xs font-semibold">
                    {activeFinding.confidence !== null && activeFinding.confidence !== undefined ? (
                      <span className={`px-2 py-0.5 rounded font-mono ${
                        activeFinding.confidence >= 80 
                          ? 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300' 
                          : activeFinding.confidence >= 50 
                          ? 'bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300' 
                          : 'bg-red-100 dark:bg-red-950/60 text-red-800 dark:text-red-300'
                      }`}>
                        {Math.round(activeFinding.confidence)}% {t('evidence.certainty', { defaultValue: 'Certainty' })}
                      </span>
                    ) : (
                      <span className="text-slate-400 dark:text-slate-500 italic font-normal">{t('evidence.not_measured', { defaultValue: 'Not measured' })}</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Detected Value */}
              <div>
                <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-1">
                  {t('evidence.detected_declaration_value', { defaultValue: 'Detected Declaration Value:' })}
                </span>
                <div className="p-2.5 bg-slate-100/80 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs font-mono text-slate-800 dark:text-slate-200 select-all">
                  {getFormattedDetectedValue()}
                </div>
              </div>

              {/* Missing Declaration Alert Banner */}
              {isMissingDeclaration && (
                <div className="p-3.5 bg-red-50 dark:bg-red-950/40 border-2 border-red-300 dark:border-red-800 rounded-xl text-xs flex items-start gap-2.5 shadow-2xs">
                  <ShieldAlert className="w-5 h-5 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
                  <div className="text-red-950 dark:text-red-200 space-y-1">
                    <strong className="block font-bold text-sm text-red-900 dark:text-red-100 flex items-center gap-1.5">
                      <span>❌ Mandatory Statutory Declaration Missing</span>
                    </strong>
                    <p className="text-xs text-red-800 dark:text-red-300 leading-relaxed font-medium">
                      {activeFinding.fail_reason || activeFinding.reason || 'This mandatory statutory declaration was not found in the packaging OCR text. A red inspection frame has been projected on the packaging artwork to indicate where this mandatory declaration is required by law.'}
                    </p>
                  </div>
                </div>
              )}

              {/* Semantic Evidence Banner when Visual BBox is Unavailable and not missing */}
              {!activeBBox && !isMissingDeclaration && (
                <div className="p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 rounded-xl text-xs flex items-start gap-2.5">
                  <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                  <div className="text-amber-900 dark:text-amber-200 space-y-0.5">
                    <strong className="block font-semibold">{t('evidence.semantic_evidence_title', { defaultValue: 'Semantic evidence — precise visual location unavailable' })}</strong>
                    <p className="text-[11px] text-amber-800 dark:text-amber-300 leading-relaxed">
                      {activeFinding.explanation || (
                        activeFinding.rule_id === 'LM-009' 
                          ? 'Cross-field declaration consistency check evaluated across packaging fields without single isolated rectangular coordinates.'
                          : activeFinding.status === 'NOT_APPLICABLE'
                          ? 'Date marking for food commodity delegates to FSSAI Regulation 5(10) (Rule FS-005).'
                          : 'Declaration was evaluated via OCR text, but does not have a verified isolated rectangular bounding box.'
                      )}
                    </p>
                  </div>
                </div>
              )}

              {/* Evidence Bounding Box Coordinates & Geometry */}
              <div>
                <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-1">
                  {t('evidence.visual_evidence_box_title', { defaultValue: 'Visual Evidence Bounding Box & Panel:' })}
                </span>
                <div className="p-3 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl text-xs font-medium text-slate-700 dark:text-slate-300 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <MapPin className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400 shrink-0" />
                      <span>{activeEvidenceLabel} {t('evidence.panel_word', { defaultValue: 'Panel' })}</span>
                    </span>
                    <span className="font-mono text-[11px] text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-100 dark:border-indigo-800/60">
                      {isMissingDeclaration && !activeBBox ? 'RED_MISSING_FRAME' : (currentEvidence?.geometry_type || activeFinding.geometry_type || (activeBBox ? 'TOKEN_UNION' : 'NON_VISUAL'))}
                    </span>
                  </div>
                  {activeBBox ? (
                    <div className="font-mono text-[11px] text-slate-600 dark:text-slate-400 pt-1.5 border-t border-slate-200 dark:border-slate-700 flex justify-between items-center">
                      <span>{t('evidence.coordinates', { defaultValue: 'Coordinates:' })}</span>
                      <span className="bg-white dark:bg-slate-900 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-700 font-bold text-slate-800 dark:text-slate-200">
                        [x1: {activeBBox[0]}, y1: {activeBBox[1]}, x2: {activeBBox[2]}, y2: {activeBBox[3]}]
                      </span>
                    </div>
                  ) : isMissingDeclaration ? (
                    <div className="text-red-800 dark:text-red-300 bg-red-50/80 dark:bg-red-950/40 p-2.5 rounded-lg border border-red-200 dark:border-red-900/60 text-[11px] leading-relaxed">
                      <strong>Projected Red Box Inspection Frame:</strong> [x: {missingInspectionZone.x}, y: {missingInspectionZone.y}, w: {missingInspectionZone.w}, h: {missingInspectionZone.h}] — Mandatory statutory declaration not found on package face.
                    </div>
                  ) : activeFinding.rule_id === 'LM-009' ? (
                    <div className="text-indigo-800 dark:text-indigo-300 bg-indigo-50/70 dark:bg-indigo-950/40 p-2.5 rounded-lg border border-indigo-200 dark:border-indigo-900/60 text-[11px] leading-relaxed">
                      <strong>{t('evidence.cross_field_title', { defaultValue: 'Cross-Field Consistency:' })}</strong> Evaluated by cross-referencing Maximum Retail Price (MRP), Net Quantity, and unit price declarations across panels.
                    </div>
                  ) : activeFinding.status === 'NOT_APPLICABLE' ? (
                    <div className="text-slate-700 dark:text-slate-300 bg-slate-100/80 dark:bg-slate-800/80 p-2.5 rounded-lg border border-slate-200 dark:border-slate-700 text-[11px] leading-relaxed">
                      <strong>{t('evidence.food_proviso_title', { defaultValue: 'Statutory Food Proviso:' })}</strong> Date marking for food commodities is governed under FSSAI Regulation 5(10) (Rule FS-005) under the Rule 6(1)(d) proviso.
                    </div>
                  ) : (
                    <div className="text-amber-800 dark:text-amber-300 bg-amber-50/70 dark:bg-amber-950/40 p-2.5 rounded-lg border border-amber-200 dark:border-amber-900/60 text-[11px] leading-relaxed">
                      <strong>{t('evidence.manual_verification_title', { defaultValue: 'Manual Verification Required:' })}</strong> Declaration was not directly localized into an isolated OCR bounding box on packaging. Auditor should inspect physical container.
                    </div>
                  )}
                </div>
              </div>

              {/* Grounded Pass Rationale */}
              {activeFinding.status === 'PASS' && (activeFinding.pass_reason || activeFinding.reason) && (
                <div className="p-3 bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/60 rounded-xl text-xs space-y-1">
                  <strong className="text-emerald-950 dark:text-emerald-200 font-bold flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                    {t('evidence.pass_rationale', { defaultValue: 'Verified Pass Rationale' })}
                  </strong>
                  <p className="text-emerald-900 dark:text-emerald-300 leading-relaxed font-medium">
                    {activeFinding.pass_reason || activeFinding.reason}
                  </p>
                </div>
              )}

              {/* Grounded Review Required */}
              {isReviewRequired && (activeFinding.review_reason || activeFinding.reason) && (
                <div className="p-3 bg-amber-50/70 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/60 rounded-xl text-xs space-y-1">
                  <strong className="text-amber-950 dark:text-amber-200 font-bold flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
                    {t('evidence.review_rationale', { defaultValue: 'Audit Review Rationale' })}
                  </strong>
                  <p className="text-amber-900 dark:text-amber-300 leading-relaxed font-medium">
                    {activeFinding.review_reason || activeFinding.reason}
                  </p>
                </div>
              )}

              {/* Grounded Statutory Failure */}
              {isFail && (activeFinding.fail_reason || activeFinding.reason) && (
                <div className="p-3 bg-red-50/70 dark:bg-red-950/30 border border-red-200 dark:border-red-800/60 rounded-xl text-xs space-y-1">
                  <strong className="text-red-950 dark:text-red-200 font-bold flex items-center gap-1.5">
                    <XCircle className="w-3.5 h-3.5 text-red-600 dark:text-red-400 shrink-0" />
                    {t('evidence.fail_issue', { defaultValue: 'Statutory Non-Compliance Issue' })}
                  </strong>
                  <p className="text-red-900 dark:text-red-300 leading-relaxed font-medium">
                    {activeFinding.fail_reason || activeFinding.reason}
                  </p>
                </div>
              )}

              {/* Extraction Candidates Breakdown */}
              {activeFinding.candidates && activeFinding.candidates.length > 1 && (
                <div className="bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 rounded-xl p-3">
                  <div className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2">
                    {t('evidence.candidates', { defaultValue: 'Extraction Candidates' })} ({activeFinding.candidates.length})
                  </div>
                  <div className="space-y-1.5">
                    {activeFinding.candidates.map((cand: any, cIdx: number) => (
                      <div key={cIdx} className="flex items-center justify-between text-xs font-mono bg-white dark:bg-slate-800 p-2 rounded border border-slate-200 dark:border-slate-700">
                        <span className="font-semibold text-slate-800 dark:text-slate-200 truncate mr-2">{cand.value || cand.raw_text}</span>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300">{cand.source || 'OCR'}</span>
                          <span className="text-[10px] font-bold text-indigo-600 dark:text-indigo-400">{Math.round((cand.confidence ?? 0) * (cand.confidence <= 1.0 ? 100 : 1))}%</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommended Action & Verification Step */}
              {activeFinding.recommended_action && (
                <div className="p-3 bg-indigo-50/70 dark:bg-indigo-950/30 border border-indigo-100 dark:border-indigo-900/60 rounded-xl text-xs space-y-1.5">
                  <strong className="text-indigo-950 dark:text-indigo-200 font-bold flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0" />
                    {t('evidence.recommended_action', { defaultValue: 'Recommended Action:' })}
                  </strong>
                  <p className="text-indigo-900 dark:text-indigo-300 leading-relaxed font-medium">
                    {activeFinding.recommended_action}
                  </p>

                  {activeFinding.verification_step && (
                    <div className="pt-1.5 border-t border-indigo-100/80 dark:border-indigo-900/60 text-[11px] text-indigo-800 dark:text-indigo-300">
                      <span className="font-semibold">{t('evidence.what_to_verify', { defaultValue: 'What to Verify:' })} </span>
                      {activeFinding.verification_step}
                    </div>
                  )}
                </div>
              )}

              {/* Statutory Legal Source Citation */}
              {(activeFinding.source_name || activeFinding.source_reference) && (
                <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
                  <span className="font-medium">{t('evidence.legal_reference', { defaultValue: 'Legal Reference:' })}</span>
                  <div className="flex items-center gap-1 text-slate-700 dark:text-slate-300">
                    <span>
                      {activeFinding.source_name ? `${activeFinding.source_name} — ` : ''}{activeFinding.source_reference}
                    </span>
                    {activeFinding.source_url && (
                      <a 
                        href={activeFinding.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 ml-1"
                        title="View official statutory text"
                      >
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="p-8 text-center text-slate-400 dark:text-slate-500 text-xs">
              {t('evidence.select_finding_prompt', { defaultValue: 'Select a statutory finding below to inspect its evidence details.' })}
            </div>
          )}

          {/* Finding Selector List */}
          <div className="pt-4 border-t border-slate-200 dark:border-slate-800 flex-1 flex flex-col">
            <div className="flex items-center justify-between mb-2.5">
              <span className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                {t('evidence.all_findings', { defaultValue: 'All Findings on Label' })} ({displayedFindings.length})
              </span>
              <button
                type="button"
                onClick={() => setFilterByImage(!filterByImage)}
                className="text-[11px] text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 font-semibold cursor-pointer"
              >
                {filterByImage ? t('evidence.show_all_images', { defaultValue: 'Show all images' }) : t('evidence.filter_active_image', { defaultValue: 'Filter by active image' })}
              </button>
            </div>

            <div className="space-y-1.5 overflow-y-auto max-h-[220px] pr-1">
              {displayedFindings.map(item => {
                const isSelected = item.rule_id === activeRuleId;
                const isItemFail = item.status === 'FAIL' || item.status === 'NON_COMPLIANT' || item.status === 'VIOLATION' || item.status === 'MISSING';
                const statusColor = 
                  item.status === 'PASS' ? 'bg-emerald-500' :
                  item.status === 'FAIL' ? 'bg-red-500' :
                  item.status === 'WARNING' ? 'bg-amber-500' :
                  item.status === 'NEEDS_REVIEW' ? 'bg-indigo-500' : 'bg-slate-400';

                return (
                  <button
                    key={item.rule_id}
                    type="button"
                    onClick={() => handleSelectFinding(item)}
                    className={`w-full text-left p-2.5 rounded-xl border text-xs transition-all flex items-center justify-between gap-2 cursor-pointer ${
                      isSelected
                        ? (isItemFail ? 'bg-red-50 dark:bg-red-950/70 border-red-500 dark:border-red-600 shadow-2xs font-semibold' : 'bg-indigo-50/90 dark:bg-indigo-950/60 border-indigo-300 dark:border-indigo-700 shadow-2xs')
                        : (isItemFail ? 'bg-red-50/30 dark:bg-red-950/20 hover:bg-red-50/60 dark:hover:bg-red-950/40 border-red-200/80 dark:border-red-900/50' : 'bg-slate-50/50 dark:bg-slate-800/40 hover:bg-slate-100 dark:hover:bg-slate-800 border-slate-200 dark:border-slate-700')
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className={`w-2.5 h-2.5 rounded-full ${statusColor} shrink-0 ${isItemFail ? 'animate-pulse' : ''}`}></span>
                      <span className={`font-mono font-bold ${isItemFail ? 'text-red-700 dark:text-red-400' : 'text-slate-700 dark:text-slate-300'}`}>{item.rule_id}</span>
                      <span className="truncate text-slate-800 dark:text-slate-200 font-medium">{item.title}</span>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      {isItemFail && (
                        <span className="text-[10px] font-bold text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-950 px-1.5 py-0.2 rounded border border-red-300 dark:border-red-800">
                          RED BOX
                        </span>
                      )}
                      {item.bbox && !isItemFail && (
                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" title="Visual BBox Available"></span>
                      )}
                      <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono bg-white dark:bg-slate-900 px-1.5 py-0.5 rounded border border-slate-100 dark:border-slate-800">
                        {item.evidence_image_label}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

        </div>
      </div>

      {/* 4. Raw OCR Text Drawer (Toggled by Combined OCR button) */}
      {showCombinedOCR && (
        <div className="p-5 border-t border-slate-200 dark:border-slate-800 bg-slate-900 text-slate-100">
          <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-indigo-400" />
              <span className="text-xs font-mono font-bold text-indigo-400 uppercase tracking-wider">
                {t('evidence.raw_ocr_stream', { defaultValue: 'Raw OCR Text Stream' })}
              </span>
            </div>
            <span className="text-xs text-slate-400 font-mono">
              {activeImage?.word_count || ocrResult?.words?.length || 0} {t('evidence.words_extracted', { defaultValue: 'words extracted' })}
            </span>
          </div>
          <pre className="text-xs font-mono leading-relaxed overflow-y-auto max-h-[200px] whitespace-pre-wrap text-slate-200 p-3 bg-slate-950 rounded-lg border border-slate-800">
            {activeImage?.ocr_text || ocrResult?.full_text || t('evidence.no_ocr_text', { defaultValue: 'No OCR text available for this image.' })}
          </pre>
        </div>
      )}
    </div>
  );
}

