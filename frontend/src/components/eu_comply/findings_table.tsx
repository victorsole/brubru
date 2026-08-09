// frontend/src/components/eu_comply/findings_table.tsx
//
// Tabular cited review of an analysis's gap findings.
//
// Replaces the accordion, in which every finding was a collapsed card and the
// evidence, gap description and recommendation were only reachable by expanding
// one row at a time -- so a 38-requirement analysis was 38 clicks, and a
// 401-requirement one was unusable. The pattern here is the one Mike OSS calls
// "tabular review": one row per obligation, the review verdict readable at a
// glance, and every cell traceable back to the document and quote it came from.
//
// Two rules the table enforces:
//   1. Exception-first. The default filter is gaps + partials + anything the
//      model was not confident about. Nobody needs to scroll 38 rows to find
//      the 6 that matter.
//   2. Never imply evidence that does not exist. A finding with no evidence
//      text says so in the cell; it does not render an empty quote box that
//      reads as "checked and clean".

import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import type { GapFinding } from '../../pages/eu_comply_page';
import { useAuth } from '../../hooks/use_auth';
import './findings_table.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/** Persistent remediation state for a finding (compliance_actions). */
export interface FindingAction {
  id: number;
  gap_finding_id: number;
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
  assigned_to?: string | null;
  due_date?: string | null;
  resolution_notes?: string | null;
}

const ACTION_STATUSES: FindingAction['status'][] = [
  'pending', 'in_progress', 'completed', 'cancelled',
];

// Below this the model's own confidence is low enough that the verdict should
// be reviewed by a human rather than acted on. Mirrors the escalation-trigger
// pattern the production-legal-AI literature describes: confidence is routing
// information, not decoration.
const LOW_CONFIDENCE_PCT = 60;

type StatusFilter = 'attention' | 'all' | 'met' | 'partial' | 'gap' | 'not_applicable';
type SortKey = 'priority' | 'criticality' | 'status' | 'deadline' | 'confidence' | 'article';

interface FindingsTableProps {
  findings: GapFinding[];
  onAskChatbot: (finding: GapFinding) => void;
  /** Analysis id, used to load and persist per-finding remediation state. */
  analysisId?: number;
}

const CRITICALITY_RANK: Record<string, number> = {
  critical: 0,
  important: 1,
  recommended: 2,
};

const STATUS_RANK: Record<string, number> = {
  gap: 0,
  partial: 1,
  not_applicable: 2,
  met: 3,
};

const statusIcon = (status: string): string => {
  switch (status) {
    case 'met': return 'mdi-check-circle';
    case 'partial': return 'mdi-alert-circle';
    case 'gap': return 'mdi-close-circle';
    default: return 'mdi-minus-circle';
  }
};

export const FindingsTable = ({ findings, onAskChatbot, analysisId }: FindingsTableProps) => {
  const { t } = useTranslation();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('attention');
  const [criticalityFilter, setCriticalityFilter] = useState<string>('all');
  const [query, setQuery] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('priority');
  const [sortAsc, setSortAsc] = useState(true);
  const [selected, setSelected] = useState<GapFinding | null>(null);
  const [actions, setActions] = useState<Record<number, FindingAction>>({});

  // Remediation state lives in compliance_actions, so it survives a reload and
  // a re-run of the analysis. Without this the table is a snapshot you cannot
  // act on.
  useEffect(() => {
    if (!analysisId) return;
    const token = useAuth.getState().token;
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(
          `${API_BASE_URL}/api/eu-law-comply/analysis/${analysisId}/actions`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!r.ok) return;
        const d = await r.json();
        if (!cancelled) setActions(d.actions || {});
      } catch { /* silent: the column just stays empty */ }
    })();
    return () => { cancelled = true; };
  }, [analysisId]);

  const saveAction = async (findingId: number, next: FindingAction['status']) => {
    const token = useAuth.getState().token;
    if (!token) return;
    // Optimistic: the control should not feel laggy on a 300ms round trip.
    const previous = actions[findingId];
    setActions((a) => ({ ...a, [findingId]: { ...(a[findingId] || {} as FindingAction), gap_finding_id: findingId, status: next } }));
    try {
      const r = await fetch(
        `${API_BASE_URL}/api/eu-law-comply/findings/${findingId}/action`,
        {
          method: 'PUT',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: next }),
        },
      );
      if (!r.ok) throw new Error(String(r.status));
      const saved = await r.json();
      setActions((a) => ({ ...a, [findingId]: saved }));
    } catch {
      // Roll back rather than leave the UI claiming a state the server rejected.
      setActions((a) => {
        const copy = { ...a };
        if (previous) copy[findingId] = previous; else delete copy[findingId];
        return copy;
      });
    }
  };

  const counts = useMemo(() => {
    const c = { met: 0, partial: 0, gap: 0, not_applicable: 0, lowConfidence: 0 };
    findings.forEach((f) => {
      if (f.status in c) (c as Record<string, number>)[f.status] += 1;
      if (f.confidence_score != null && f.confidence_score < LOW_CONFIDENCE_PCT) c.lowConfidence += 1;
    });
    return c;
  }, [findings]);

  const attentionCount = counts.gap + counts.partial + counts.lowConfidence;

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    let out = findings.filter((f) => {
      if (statusFilter === 'attention') {
        const needsReview =
          f.status === 'gap' ||
          f.status === 'partial' ||
          (f.confidence_score != null && f.confidence_score < LOW_CONFIDENCE_PCT);
        if (!needsReview) return false;
      } else if (statusFilter !== 'all' && f.status !== statusFilter) {
        return false;
      }
      if (criticalityFilter !== 'all' && f.criticality !== criticalityFilter) return false;
      if (!q) return true;
      return (
        (f.requirement_text || '').toLowerCase().includes(q) ||
        (f.article_number || '').toLowerCase().includes(q) ||
        (f.gap_description || '').toLowerCase().includes(q) ||
        (f.recommendation || '').toLowerCase().includes(q)
      );
    });

    const dir = sortAsc ? 1 : -1;
    out = [...out].sort((a, b) => {
      switch (sortKey) {
        case 'criticality':
          return dir * ((CRITICALITY_RANK[a.criticality] ?? 9) - (CRITICALITY_RANK[b.criticality] ?? 9));
        case 'status':
          return dir * ((STATUS_RANK[a.status] ?? 9) - (STATUS_RANK[b.status] ?? 9));
        case 'confidence':
          return dir * ((a.confidence_score ?? -1) - (b.confidence_score ?? -1));
        case 'deadline': {
          // Undated obligations sort last in both directions: an absent deadline
          // is not "the year 0", and letting it lead the table would bury the
          // dated ones that actually have a clock running.
          const av = a.deadline_date ? Date.parse(a.deadline_date) : Number.POSITIVE_INFINITY;
          const bv = b.deadline_date ? Date.parse(b.deadline_date) : Number.POSITIVE_INFINITY;
          if (av === bv) return 0;
          if (!Number.isFinite(av)) return 1;
          if (!Number.isFinite(bv)) return -1;
          return dir * (av - bv);
        }
        case 'article':
          return dir * (a.article_number || '').localeCompare(b.article_number || '');
        default:
          return dir * ((a.priority ?? 9) - (b.priority ?? 9));
      }
    });
    return out;
  }, [findings, statusFilter, criticalityFilter, query, sortKey, sortAsc]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc((v) => !v);
    else { setSortKey(key); setSortAsc(true); }
  };

  const sortIndicator = (key: SortKey) =>
    sortKey === key ? (sortAsc ? 'mdi-arrow-up' : 'mdi-arrow-down') : 'mdi-unfold-more-horizontal';

  return (
    <div className="findings-table">
      <div className="findings-table__toolbar">
        <div className="findings-table__filters" role="group" aria-label={t('comply.report.filterAll')}>
          <button
            className={`findings-table__pill${statusFilter === 'attention' ? ' is-active' : ''}`}
            onClick={() => setStatusFilter('attention')}
          >
            <span className="mdi mdi-flag-outline"></span>
            {t('comply.report.needsAttention', 'Needs attention')} ({attentionCount})
          </button>
          <button
            className={`findings-table__pill${statusFilter === 'gap' ? ' is-active' : ''} status-gap`}
            onClick={() => setStatusFilter('gap')}
          >
            {t('comply.report.filterGap')} ({counts.gap})
          </button>
          <button
            className={`findings-table__pill${statusFilter === 'partial' ? ' is-active' : ''} status-partial`}
            onClick={() => setStatusFilter('partial')}
          >
            {t('comply.report.filterPartial')} ({counts.partial})
          </button>
          <button
            className={`findings-table__pill${statusFilter === 'met' ? ' is-active' : ''} status-met`}
            onClick={() => setStatusFilter('met')}
          >
            {t('comply.report.filterMet')} ({counts.met})
          </button>
          <button
            className={`findings-table__pill${statusFilter === 'all' ? ' is-active' : ''}`}
            onClick={() => setStatusFilter('all')}
          >
            {t('comply.report.filterAll')} ({findings.length})
          </button>
        </div>

        <div className="findings-table__tools">
          <select
            className="findings-table__select"
            value={criticalityFilter}
            onChange={(e) => setCriticalityFilter(e.target.value)}
            aria-label={t('comply.report.criticality', 'Criticality')}
          >
            <option value="all">{t('comply.report.allCriticalities', 'All criticalities')}</option>
            <option value="critical">{t('comply.report.criticalityCritical')}</option>
            <option value="important">{t('comply.report.criticalityImportant')}</option>
            <option value="recommended">{t('comply.report.criticalityRecommended')}</option>
          </select>
          <div className="findings-table__search">
            <span className="mdi mdi-magnify"></span>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('comply.report.searchFindings', 'Search obligations')}
              aria-label={t('comply.report.searchFindings', 'Search obligations')}
            />
          </div>
        </div>
      </div>

      {counts.lowConfidence > 0 && statusFilter === 'attention' && (
        <p className="findings-table__note">
          <span className="mdi mdi-information-outline"></span>
          {t('comply.report.lowConfidenceNote', {
            defaultValue:
              '{{count}} finding(s) are included because the analysis was under {{pct}}% confident, not because a gap was found. Review these yourself.',
            count: counts.lowConfidence,
            pct: LOW_CONFIDENCE_PCT,
          })}
        </p>
      )}

      <div className="findings-table__scroll">
        <table className="findings-table__table">
          <thead>
            <tr>
              <th className="col-status">
                <button onClick={() => toggleSort('status')}>
                  {t('comply.report.status', 'Status')} <span className={`mdi ${sortIndicator('status')}`}></span>
                </button>
              </th>
              <th className="col-article">
                <button onClick={() => toggleSort('article')}>
                  {t('comply.report.article', 'Article')} <span className={`mdi ${sortIndicator('article')}`}></span>
                </button>
              </th>
              <th className="col-obligation">{t('comply.report.obligation', 'Obligation')}</th>
              <th className="col-crit">
                <button onClick={() => toggleSort('criticality')}>
                  {t('comply.report.criticality', 'Criticality')} <span className={`mdi ${sortIndicator('criticality')}`}></span>
                </button>
              </th>
              <th className="col-deadline">
                <button onClick={() => toggleSort('deadline')}>
                  {t('comply.report.deadline')} <span className={`mdi ${sortIndicator('deadline')}`}></span>
                </button>
              </th>
              <th className="col-conf">
                <button onClick={() => toggleSort('confidence')}>
                  {t('comply.report.confidence')} <span className={`mdi ${sortIndicator('confidence')}`}></span>
                </button>
              </th>
              <th className="col-evidence">{t('comply.report.evidenceFound')}</th>
              <th className="col-action">{t('comply.report.action', 'Action')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => {
              const low = f.confidence_score != null && f.confidence_score < LOW_CONFIDENCE_PCT;
              return (
                <tr
                  key={f.id}
                  className={`findings-table__row status-${f.status}`}
                  onClick={() => setSelected(f)}
                  tabIndex={0}
                  role="button"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelected(f); }
                  }}
                >
                  <td className="col-status">
                    <span className={`findings-table__status status-${f.status}`}>
                      <span className={`mdi ${statusIcon(f.status)}`}></span>
                      {t(`comply.report.status_${f.status}`, f.status.replace('_', ' '))}
                    </span>
                  </td>
                  <td className="col-article"><code>{f.article_number}</code></td>
                  <td className="col-obligation">
                    <span className="findings-table__obligation">{f.requirement_text}</span>
                  </td>
                  <td className="col-crit">
                    <span className={`findings-table__crit criticality-${f.criticality}`}>
                      {f.criticality}
                    </span>
                  </td>
                  <td className="col-deadline">
                    {f.deadline_date
                      ? new Date(f.deadline_date).toLocaleDateString()
                      : <span className="findings-table__muted">—</span>}
                  </td>
                  <td className="col-conf">
                    {f.confidence_score == null ? (
                      <span className="findings-table__muted">—</span>
                    ) : (
                      <span className={`findings-table__conf${low ? ' is-low' : ''}`}>
                        <span className="findings-table__conf-bar">
                          <span style={{ width: `${Math.min(100, Math.max(0, f.confidence_score))}%` }} />
                        </span>
                        {Math.round(f.confidence_score)}%
                        {low && <span className="mdi mdi-flag-outline" title={t('comply.report.lowConfidence', 'Low confidence — review manually') as string}></span>}
                      </span>
                    )}
                  </td>
                  <td className="col-action">
                    {actions[f.id]
                      ? <span className={`findings-table__action action-${actions[f.id].status}`}>
                          {t(`comply.report.action_${actions[f.id].status}`, actions[f.id].status.replace('_', ' '))}
                        </span>
                      : <span className="findings-table__muted">—</span>}
                  </td>
                  <td className="col-evidence">
                    {f.evidence_text ? (
                      <span className="findings-table__cited">
                        <span className="mdi mdi-format-quote-close"></span>
                        {f.evidence_source || t('comply.report.citedInDoc', 'Cited in document')}
                      </span>
                    ) : (
                      <span className="findings-table__muted">
                        {t('comply.report.noEvidence', 'Nothing found in your documents')}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {rows.length === 0 && (
          <div className="findings-table__empty">
            <span className="mdi mdi-file-search-outline"></span>
            <p>
              {statusFilter === 'attention'
                ? t('comply.report.nothingToReview', 'Nothing needs your attention in this analysis.')
                : t('comply.report.noFindings')}
            </p>
          </div>
        )}
      </div>

      {selected && createPortal(
        <FindingDrawer
          finding={selected}
          action={actions[selected.id]}
          onSetAction={analysisId ? (st) => saveAction(selected.id, st) : undefined}
          onClose={() => setSelected(null)}
          onAskChatbot={onAskChatbot}
        />,
        document.body
      )}
    </div>
  );
};

interface FindingDrawerProps {
  finding: GapFinding;
  action?: FindingAction;
  onSetAction?: (status: FindingAction['status']) => void;
  onClose: () => void;
  onAskChatbot: (f: GapFinding) => void;
}

// Portalled to document.body: this page is wrapped in an AnimatedPage whose
// framer-motion transform creates a containing block, so a position:fixed
// overlay rendered inside it scopes to that box instead of the viewport.
const FindingDrawer = ({ finding, action, onSetAction, onClose, onAskChatbot }: FindingDrawerProps) => {
  const { t } = useTranslation();
  const low = finding.confidence_score != null && finding.confidence_score < LOW_CONFIDENCE_PCT;

  return (
    <>
      <div className="finding-drawer__overlay" onClick={onClose} aria-hidden="true" />
      <aside
        className="finding-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={finding.article_number}
      >
        <header className="finding-drawer__head">
          <div>
            <span className={`findings-table__status status-${finding.status}`}>
              <span className={`mdi ${statusIcon(finding.status)}`}></span>
              {t(`comply.report.status_${finding.status}`, finding.status.replace('_', ' '))}
            </span>
            <code className="finding-drawer__article">{finding.article_number}</code>
          </div>
          <button className="finding-drawer__close" onClick={onClose} aria-label={t('common.closeSidebar', 'Close')}>
            <span className="mdi mdi-close"></span>
          </button>
        </header>

        <div className="finding-drawer__body">
          <section>
            <h4>{t('comply.report.obligation', 'Obligation')}</h4>
            <p className="finding-drawer__requirement">{finding.requirement_text}</p>
            <div className="finding-drawer__meta">
              <span className={`findings-table__crit criticality-${finding.criticality}`}>{finding.criticality}</span>
              {finding.deadline_date && (
                <span className="finding-drawer__deadline">
                  <span className="mdi mdi-calendar-clock"></span>
                  {t('comply.report.deadline')} {new Date(finding.deadline_date).toLocaleDateString()}
                </span>
              )}
              {finding.estimated_effort && (
                <span className="finding-drawer__effort">
                  <span className="mdi mdi-timer-sand"></span>{finding.estimated_effort}
                </span>
              )}
            </div>
          </section>

          {/* The citation. Where there is none, say so plainly rather than
              rendering an empty quote box that reads as a clean result. */}
          <section>
            <h4><span className="mdi mdi-format-quote-close"></span> {t('comply.report.evidenceFound')}</h4>
            {finding.evidence_text ? (
              <blockquote className="finding-drawer__quote">
                {finding.evidence_text}
                {finding.evidence_source && (
                  <cite>{t('comply.report.evidenceSource')} {finding.evidence_source}</cite>
                )}
              </blockquote>
            ) : (
              <p className="finding-drawer__none">
                {t('comply.report.noEvidenceLong', 'No passage in the documents you uploaded addresses this obligation.')}
              </p>
            )}
          </section>

          {finding.gap_description && (
            <section>
              <h4><span className="mdi mdi-alert-outline"></span> {t('comply.report.gapAnalysis')}</h4>
              <p>{finding.gap_description}</p>
            </section>
          )}

          {finding.recommendation && (
            <section>
              <h4><span className="mdi mdi-lightbulb-outline"></span> {t('comply.report.recommendation')}</h4>
              <p>{finding.recommendation}</p>
            </section>
          )}

          {finding.confidence_score != null && (
            <section className={`finding-drawer__confidence${low ? ' is-low' : ''}`}>
              <h4>{t('comply.report.confidence')} {Math.round(finding.confidence_score)}%</h4>
              {low && (
                <p>
                  {t('comply.report.lowConfidenceExplain',
                    'The analysis was not confident about this verdict. Treat it as a prompt to check the source text yourself, not as a conclusion.')}
                </p>
              )}
            </section>
          )}
        </div>

        {onSetAction && (
          <div className="finding-drawer__triage">
            <h4>{t('comply.report.remediation', 'Remediation')}</h4>
            <div className="finding-drawer__triage-buttons" role="group">
              {ACTION_STATUSES.map((st) => (
                <button
                  key={st}
                  type="button"
                  className={`finding-drawer__triage-btn action-${st}${action?.status === st ? ' is-active' : ''}`}
                  onClick={() => onSetAction(st)}
                  aria-pressed={action?.status === st}
                >
                  {t(`comply.report.action_${st}`, st.replace('_', ' '))}
                </button>
              ))}
            </div>
            <p className="finding-drawer__triage-note">
              {t('comply.report.remediationNote',
                'Saved against this finding, so it survives a reload and a re-run of the analysis.')}
            </p>
          </div>
        )}

        <footer className="finding-drawer__foot">
          <button className="finding-drawer__ask" onClick={() => onAskChatbot(finding)}>
            <span className="mdi mdi-chat-question-outline"></span>
            {t('comply.report.askChatbot')}
          </button>
        </footer>
      </aside>
    </>
  );
};
