// frontend/src/components/tenders/pipeline_view.tsx
//
// Move 4 (15 Jun 2026): Tenderator pipeline CRM. A kanban view over
// /api/tenders/pipeline. Generic across every opportunity source (TED, F&T
// proposals/tenders/projects, agency, intl_coop). Replaces the Excel
// tracker for orgs like TAS Europrojects.

import { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../../hooks/use_auth';
import { useTranslation } from 'react-i18next';
import './pipeline_view.css';
import { uiDateLocale } from '../../i18n/config';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export type PipelineStatus =
  | 'lead' | 'drafting' | 'submitted' | 'awarded'
  | 'executing' | 'paid' | 'lost' | 'cancelled';

export interface PipelineRow {
  id: number;
  opportunity_id: string;
  source: string;
  title: string;
  organisation: string | null;
  country: string | null;
  programme: string | null;
  deadline: string | null;
  budget: number | null;
  currency: string;
  source_url: string | null;
  status: PipelineStatus;
  next_step: string | null;
  next_step_due: string | null;
  pm_assignee: string | null;
  notes: string | null;
  updated_at: string;
}

interface PipelineResponse {
  items: PipelineRow[];
  counts: Record<PipelineStatus, number>;
  statuses: PipelineStatus[];
}

const STATUS_META_BASE: Record<PipelineStatus, { color: string; icon: string }> = {
  lead:       { color: '#6b7280', icon: 'mdi-eye-outline' },
  drafting:   { color: '#0693e3', icon: 'mdi-pencil-outline' },
  submitted:  { color: '#d97706', icon: 'mdi-send-outline' },
  awarded:    { color: '#059669', icon: 'mdi-trophy-outline' },
  executing:  { color: '#9b51e0', icon: 'mdi-rocket-launch-outline' },
  paid:       { color: '#15803d', icon: 'mdi-currency-eur' },
  lost:       { color: '#dc2626', icon: 'mdi-close-circle-outline' },
  cancelled:  { color: '#9ca3af', icon: 'mdi-cancel' },
};

const formatBudget = (v: number | null): string => {
  if (!v) return '';
  if (v >= 1e6) return `€${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `€${Math.round(v / 1e3)}k`;
  return `€${v}`;
};

const formatDate = (iso: string | null): string => {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString(uiDateLocale(), { day: '2-digit', month: 'short', year: 'numeric' });
};

const daysUntil = (iso: string | null): number | null => {
  if (!iso) return null;
  return Math.round((new Date(iso).getTime() - Date.now()) / (24 * 60 * 60 * 1000));
};

export const PipelineView = () => {
  const { token } = useAuth();
  const { t } = useTranslation();
  const [data, setData] = useState<PipelineResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<number | null>(null);

  const fetchPipeline = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/tenders/pipeline`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setError(t('tenderator.pipelineView.errorFailedToLoad', { status: res.status }));
        return;
      }
      setData(await res.json());
    } catch (e) {
      console.error('pipeline fetch failed:', e);
      setError(t('tenderator.pipelineView.errorCouldNotLoad'));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { void fetchPipeline(); }, [fetchPipeline]);

  const moveTo = async (id: number, status: PipelineStatus) => {
    if (!token) return;
    try {
      await fetch(`${API_URL}/api/tenders/pipeline/${id}`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      });
      void fetchPipeline();
    } catch (e) { console.error(e); }
  };

  const remove = async (id: number) => {
    if (!token) return;
    if (!window.confirm(t('tenderator.pipelineView.confirmRemove'))) return;
    try {
      await fetch(`${API_URL}/api/tenders/pipeline/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      void fetchPipeline();
    } catch (e) { console.error(e); }
  };

  const updateField = async (id: number, body: Partial<PipelineRow>) => {
    if (!token) return;
    try {
      await fetch(`${API_URL}/api/tenders/pipeline/${id}`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      void fetchPipeline();
    } catch (e) { console.error(e); }
  };

  if (loading && !data) {
    return (
      <div className="pipeline-view pipeline-view--loading">
        <span className="mdi mdi-loading mdi-spin" aria-hidden="true" />
        {t('tenderator.pipelineView.loading')}
      </div>
    );
  }
  if (error) {
    return (
      <div className="pipeline-view pipeline-view--error">
        <span className="mdi mdi-alert-circle-outline" aria-hidden="true" />
        {error}
        <button type="button" onClick={() => void fetchPipeline()}>{t('tenderator.pipelineView.buttonRetry')}</button>
      </div>
    );
  }
  if (!data || data.items.length === 0) {
    return (
      <div className="pipeline-view pipeline-view--empty">
        <span className="mdi mdi-clipboard-text-outline" aria-hidden="true" />
        <h3>{t('tenderator.pipelineView.emptyTitle')}</h3>
        <p>{t('tenderator.pipelineView.emptyDescription')}</p>
        <a className="pipeline-view__chat-link" href="/main?q=How%20do%20I%20use%20Brubru%20pipeline%20to%20track%20EU%20bids%3F" title={t('tenderator.pipelineView.askBrubru')}>
          <span className="mdi mdi-message-outline" aria-hidden="true" />
          {t('tenderator.pipelineView.askBrubruHow')}
        </a>
      </div>
    );
  }

  // Group items by status, in canonical order.
  const byStatus: Record<PipelineStatus, PipelineRow[]> = {
    lead: [], drafting: [], submitted: [], awarded: [],
    executing: [], paid: [], lost: [], cancelled: [],
  };
  for (const it of data.items) byStatus[it.status].push(it);

  return (
    <div className="pipeline-view">
      <header className="pipeline-view__header">
        <h2>
          <span className="mdi mdi-view-column-outline" aria-hidden="true" />
          {t('tenderator.pipelineView.headerTitle')}
        </h2>
        <p>
          {t('tenderator.pipelineView.headerCount', { count: data.items.length })}
          {' '}
          {t('tenderator.pipelineView.headerDescription')}
        </p>
      </header>

      <div className="pipeline-view__board">
        {data.statuses.map((s) => {
          const meta = STATUS_META_BASE[s];
          const items = byStatus[s];
          const statusKey = `tenderator.pipelineView.status.${s}`;
          const statusLabel = t(statusKey);
          const statusHint = t(`${statusKey}Hint`);
          return (
            <section
              key={s}
              className={`pipeline-view__column pipeline-view__column--${s}`}
              style={{ borderTopColor: meta.color }}
            >
              <header className="pipeline-view__column-head" title={statusHint}>
                <span className={`mdi ${meta.icon}`} aria-hidden="true" />
                <span className="pipeline-view__column-label">{statusLabel}</span>
                <span className="pipeline-view__column-count">{items.length}</span>
                <span className="mdi mdi-help-circle-outline pipeline-view__column-help" aria-hidden="true" />
              </header>
              <div className="pipeline-view__column-body">
                {items.map((it) => {
                  const isEditing = editing === it.id;
                  const days = daysUntil(it.next_step_due);
                  const urgentCls = days !== null && days <= 7 ? 'pipeline-view__card--urgent' :
                                     days !== null && days <= 30 ? 'pipeline-view__card--warm' : '';
                  return (
                    <article
                      key={it.id}
                      className={`pipeline-view__card ${urgentCls}`}
                    >
                      <div className="pipeline-view__card-head">
                        <span className="pipeline-view__source">{it.source}</span>
                        {it.country && (
                          <span className="pipeline-view__country">{it.country}</span>
                        )}
                        {it.programme && (
                          <span className="pipeline-view__programme">{it.programme}</span>
                        )}
                      </div>
                      <h4 className="pipeline-view__card-title">
                        {it.source_url ? (
                          <a href={it.source_url} target="_blank" rel="noreferrer">
                            {it.title}
                          </a>
                        ) : (
                          it.title
                        )}
                      </h4>
                      {it.organisation && (
                        <div className="pipeline-view__org">{it.organisation}</div>
                      )}
                      <div className="pipeline-view__meta">
                        {it.budget && (
                          <span title={t('tenderator.pipelineView.metaBudget')}><span className="mdi mdi-currency-eur" />{formatBudget(it.budget)}</span>
                        )}
                        {it.deadline && (
                          <span title={t('tenderator.pipelineView.metaBidDeadline')}>
                            <span className="mdi mdi-clock-outline" />
                            {formatDate(it.deadline)}
                          </span>
                        )}
                        {it.pm_assignee && (
                          <span title={t('tenderator.pipelineView.metaPM')}>
                            <span className="mdi mdi-account-outline" />
                            {it.pm_assignee}
                          </span>
                        )}
                      </div>
                      {it.next_step && (
                        <div className="pipeline-view__next-step">
                          <span className="mdi mdi-arrow-right-bold-outline" />
                          {it.next_step}
                          {it.next_step_due && (
                            <span className="pipeline-view__next-step-due">
                              {t('tenderator.pipelineView.nextStepBy')} {formatDate(it.next_step_due)}
                            </span>
                          )}
                        </div>
                      )}
                      {isEditing && (
                        <div className="pipeline-view__editor">
                          <label>
                            {t('tenderator.pipelineView.editorNextStep')}
                            <input
                              type="text"
                              defaultValue={it.next_step || ''}
                              onBlur={(e) => updateField(it.id, { next_step: e.target.value })}
                            />
                          </label>
                          <label>
                            {t('tenderator.pipelineView.editorDue')}
                            <input
                              type="date"
                              defaultValue={it.next_step_due || ''}
                              onBlur={(e) => updateField(it.id, { next_step_due: e.target.value as unknown as string })}
                            />
                          </label>
                          <label>
                            {t('tenderator.pipelineView.editorAssignedTo')}
                            <input
                              type="text"
                              defaultValue={it.pm_assignee || ''}
                              placeholder={t('tenderator.pipelineView.editorAssignedToPlaceholder')}
                              onBlur={(e) => updateField(it.id, { pm_assignee: e.target.value })}
                            />
                          </label>
                          <label>
                            {t('tenderator.pipelineView.editorNotes')}
                            <textarea
                              rows={2}
                              defaultValue={it.notes || ''}
                              onBlur={(e) => updateField(it.id, { notes: e.target.value })}
                            />
                          </label>
                        </div>
                      )}
                      <div className="pipeline-view__actions">
                        <select
                          value={it.status}
                          onChange={(e) => moveTo(it.id, e.target.value as PipelineStatus)}
                          aria-label={t('tenderator.pipelineView.ariaLabelMoveToStage')}
                        >
                          {data.statuses.map((opt) => (
                            <option key={opt} value={opt}>{t(`tenderator.pipelineView.status.${opt}`)}</option>
                          ))}
                        </select>
                        <button
                          type="button"
                          className="pipeline-view__icon-btn"
                          onClick={() => setEditing(isEditing ? null : it.id)}
                          aria-label={isEditing ? t('tenderator.pipelineView.ariaLabelCloseEdit') : t('tenderator.pipelineView.ariaLabelEditDetails')}
                        >
                          <span className={`mdi ${isEditing ? 'mdi-chevron-up' : 'mdi-pencil-outline'}`} />
                        </button>
                        <a
                          href={`/main?q=${encodeURIComponent(`Tell me what you know about ${it.title}`)}`}
                          className="pipeline-view__icon-btn"
                          title={t('tenderator.pipelineView.titleAskBrubruAboutDossier')}
                          aria-label={t('tenderator.pipelineView.ariaLabelAskBrubru')}
                        >
                          <span className="mdi mdi-message-outline" />
                        </a>
                        <button
                          type="button"
                          className="pipeline-view__icon-btn pipeline-view__icon-btn--danger"
                          onClick={() => remove(it.id)}
                          aria-label={t('tenderator.pipelineView.ariaLabelRemove')}
                        >
                          <span className="mdi mdi-trash-can-outline" />
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
};
