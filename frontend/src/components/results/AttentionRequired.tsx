import React, { useState, useMemo } from 'react';
import { AlertTriangle, XCircle, Target, HelpCircle, ShieldAlert } from 'lucide-react';
import { type ComplianceCheck } from '../../types';
import { useLanguage } from '../../context/LanguageContext';

interface AttentionRequiredProps {
  failedChecks: ComplianceCheck[];
  reviewChecks: ComplianceCheck[];
  onViewEvidence: (ruleId: string, imageLabel?: string | null) => void;
}

const isCheckMissing = (check: ComplianceCheck): boolean => {
  if (check.field_status === 'MISSING') return true;
  if (check.detected === false && check.status === 'FAIL') return true;
  const val = (check.detected_value || '').trim().toLowerCase();
  if (check.status === 'FAIL' && (!val || val === 'not detected' || val === 'not found' || val === '-' || val === 'null' || val === 'none')) {
    return true;
  }
  const exp = (check.explanation || '').toLowerCase();
  if (check.status === 'FAIL' && (exp.includes('missing') || exp.includes('not found') || exp.includes('absent') || exp.includes('not detected'))) {
    return true;
  }
  return false;
};

const AttentionRequired: React.FC<AttentionRequiredProps> = ({
  failedChecks,
  reviewChecks,
  onViewEvidence,
}) => {
  const { t } = useLanguage();
  const [filterMode, setFilterMode] = useState<'all' | 'missing' | 'issues'>('all');

  const classifiedItems = useMemo(() => {
    return [
      ...failedChecks.map(c => {
        const missing = isCheckMissing(c);
        return {
          ...c,
          isFail: true,
          isMissing: missing,
          category: missing ? 'missing' : 'issue' as 'missing' | 'issue'
        };
      }),
      ...reviewChecks.map(c => {
        const missing = isCheckMissing(c);
        return {
          ...c,
          isFail: false,
          isMissing: missing,
          category: missing ? 'missing' : 'issue' as 'missing' | 'issue'
        };
      })
    ];
  }, [failedChecks, reviewChecks]);

  const missingItems = useMemo(() => classifiedItems.filter(i => i.isMissing), [classifiedItems]);
  const issueItems = useMemo(() => classifiedItems.filter(i => !i.isMissing), [classifiedItems]);

  if (classifiedItems.length === 0) {
    return null;
  }

  const displayedItems = filterMode === 'missing' 
    ? missingItems 
    : filterMode === 'issues' 
    ? issueItems 
    : classifiedItems;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border-2 border-red-200 dark:border-red-900/60 shadow-sm mb-6 overflow-hidden">
      {/* Header Docket Title */}
      <div className="bg-gradient-to-r from-red-50 via-amber-50 to-red-50 dark:from-red-950/40 dark:via-slate-800/60 dark:to-red-950/40 p-4 border-b border-red-200 dark:border-red-900/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-red-600 text-white rounded-xl shadow-xs">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-slate-900 dark:text-slate-100 font-bold uppercase tracking-wider text-sm sm:text-base">
                {t('results.issues_and_missing_docket', { defaultValue: 'Compliance Defects & Missing Declarations Docket' })}
              </h3>
              <span className="px-2 py-0.5 rounded-full text-xs font-black bg-red-600 text-white shadow-2xs">
                {classifiedItems.length} {classifiedItems.length === 1 ? 'DEFECT' : 'DEFECTS'}
              </span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
              {t('results.issues_subtitle', { defaultValue: 'Statutory non-compliances, missing mandatory elements, and red box visual proofs.' })}
            </p>
          </div>
        </div>

        {/* Tab Filters */}
        <div className="flex items-center gap-1.5 bg-white/80 dark:bg-slate-900/80 p-1 rounded-xl border border-red-200/80 dark:border-red-900/50 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setFilterMode('all')}
            className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
              filterMode === 'all'
                ? 'bg-red-600 text-white shadow-2xs font-bold'
                : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            All ({classifiedItems.length})
          </button>
          <button
            type="button"
            onClick={() => setFilterMode('missing')}
            className={`px-3 py-1 rounded-lg transition-all flex items-center gap-1 cursor-pointer ${
              filterMode === 'missing'
                ? 'bg-red-600 text-white shadow-2xs font-bold'
                : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <span>❌ Missing</span>
            <span className="font-mono px-1.5 py-0.2 rounded-full text-[10px] bg-red-100 dark:bg-red-950 text-red-800 dark:text-red-300 font-bold">
              {missingItems.length}
            </span>
          </button>
          <button
            type="button"
            onClick={() => setFilterMode('issues')}
            className={`px-3 py-1 rounded-lg transition-all flex items-center gap-1 cursor-pointer ${
              filterMode === 'issues'
                ? 'bg-red-600 text-white shadow-2xs font-bold'
                : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <span>⚠️ Issues</span>
            <span className="font-mono px-1.5 py-0.2 rounded-full text-[10px] bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 font-bold">
              {issueItems.length}
            </span>
          </button>
        </div>
      </div>
      
      {/* List of Items */}
      <div className="divide-y divide-slate-100 dark:divide-slate-800/80">
        {displayedItems.map((check) => {
          const isMissing = check.isMissing;
          const isFail = check.isFail;

          return (
            <div 
              key={check.rule_id} 
              className={`p-4 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4 ${
                isMissing 
                  ? 'bg-red-50/40 dark:bg-red-950/20 hover:bg-red-50/70 dark:hover:bg-red-950/30' 
                  : 'hover:bg-slate-50 dark:hover:bg-slate-800/40'
              }`}
            >
              <div className="flex-1 flex items-start gap-3.5">
                {isMissing ? (
                  <div className="p-2 rounded-xl bg-red-600 text-white shrink-0 mt-0.5 shadow-xs">
                    <XCircle className="w-5 h-5 stroke-[2.5]" />
                  </div>
                ) : isFail ? (
                  <div className="p-2 rounded-xl bg-rose-100 dark:bg-rose-950/80 text-rose-700 dark:text-rose-300 shrink-0 mt-0.5 border border-rose-300 dark:border-rose-800">
                    <AlertTriangle className="w-5 h-5" />
                  </div>
                ) : (
                  <div className="p-2 rounded-xl bg-amber-100 dark:bg-amber-950/80 text-amber-700 dark:text-amber-300 shrink-0 mt-0.5 border border-amber-300 dark:border-amber-800">
                    <HelpCircle className="w-5 h-5" />
                  </div>
                )}

                <div className="space-y-1.5 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    {/* Badge: Missing vs Defect */}
                    {isMissing ? (
                      <span className="text-[11px] font-black uppercase px-2.5 py-0.5 rounded-full bg-red-600 text-white tracking-wider shadow-2xs">
                        ❌ MISSING DECLARATION
                      </span>
                    ) : isFail ? (
                      <span className="text-[11px] font-black uppercase px-2.5 py-0.5 rounded-full bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-200 border border-rose-300 dark:border-rose-800 tracking-wider">
                        ⚠️ NON-COMPLIANCE DEFECT
                      </span>
                    ) : (
                      <span className="text-[11px] font-black uppercase px-2.5 py-0.5 rounded-full bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-200 border border-amber-300 dark:border-amber-800 tracking-wider">
                        🔍 AUDIT REVIEW REQUIRED
                      </span>
                    )}

                    <span className="font-mono text-xs font-bold text-slate-800 dark:text-slate-200 bg-white dark:bg-slate-800 px-2 py-0.5 rounded border border-slate-300 dark:border-slate-700 shadow-2xs">
                      {check.rule_id}
                    </span>

                    <span className="font-bold text-slate-900 dark:text-slate-100 text-sm">
                      {check.field_label && check.field_label.length > 2 ? check.field_label : (check.field || check.rule_id)}
                    </span>
                  </div>

                  {/* Defect or Missing Explanation */}
                  <p className="text-xs font-medium text-slate-700 dark:text-slate-300 leading-relaxed">
                    {isMissing 
                      ? (check.fail_reason || check.explanation || 'Mandatory statutory declaration was not found on physical packaging artwork.')
                      : (check.fail_reason || check.review_reason || check.explanation || 'Declaration requires verification against statutory standards.')}
                  </p>

                  {/* Detected value / Missing indicator */}
                  <div className="flex items-center gap-3 text-xs flex-wrap">
                    {isMissing ? (
                      <span className="text-[11px] font-mono text-red-700 dark:text-red-400 font-semibold bg-red-100/70 dark:bg-red-950/60 px-2 py-0.5 rounded border border-red-200 dark:border-red-900/60">
                        Status: Not detected anywhere on package
                      </span>
                    ) : check.detected_value ? (
                      <span className="text-[11px] text-slate-600 dark:text-slate-400">
                        Detected: <strong className="font-mono text-slate-900 dark:text-slate-100 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">{check.detected_value}</strong>
                      </span>
                    ) : null}

                    {check.evidence_image_label && (
                      <span className="text-[11px] text-slate-500 font-mono">
                        Panel: <strong>{check.evidence_image_label}</strong>
                      </span>
                    )}

                    {check.regulation_reference && (
                      <span className="text-[11px] text-indigo-700 dark:text-indigo-400 font-medium">
                        ⚖️ {check.regulation_reference}
                      </span>
                    )}
                  </div>
                </div>
              </div>
              
              {/* Direct Jump to Evidence Viewer with Red Box Highlight */}
              <button
                type="button"
                onClick={() => onViewEvidence(check.rule_id, check.evidence_image_label)}
                className="self-start md:self-center shrink-0 flex items-center gap-2 px-3.5 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl text-xs font-bold shadow-xs hover:shadow transition-all cursor-pointer group"
                title={`Inspect ${check.rule_id} with red box on package image`}
              >
                <Target className="w-4 h-4 text-red-100 group-hover:scale-110 transition-transform" />
                <span>{t('results.view_evidence_red_box', { defaultValue: 'View Evidence (Red Box)' })}</span>
              </button>
            </div>
          );
        })}
      </div>

      {/* Footer Info Notice */}
      <div className="bg-slate-50 dark:bg-slate-800/60 px-4 py-2.5 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-600 dark:text-slate-400 flex-wrap gap-2">
        <span className="flex items-center gap-1.5 font-medium">
          <span className="w-2.5 h-2.5 rounded-full bg-red-600 inline-block animate-pulse"></span>
          <span>Clicking <strong>View Evidence (Red Box)</strong> directly focuses the red box on the package image.</span>
        </span>
        <span className="font-mono text-[10px] text-slate-500">
          Legal Metrology (Packaged Commodities) Rules 2011 & FSSAI Labelling Regulations
        </span>
      </div>
    </div>
  );
};

export default AttentionRequired;
