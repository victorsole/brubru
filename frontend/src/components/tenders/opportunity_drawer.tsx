// frontend/src/components/tenders/opportunity_drawer.tsx
//
// Phase 3: side drawer that opens when the user clicks any opportunity in
// the unified feed. Hosts the title + meta, an AI brief button, and a
// similar-projects panel for F&T proposals/projects (degrades gracefully
// for TED + ft_tenders).

import { useEffect, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/use_auth';
import type { UnifiedOpportunity } from './unified_opportunity_feed';
import { ClientScorecardPanel } from './client_scorecard_panel';
import './opportunity_drawer.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface OpportunityDrawerProps {
  opportunity: UnifiedOpportunity | null;
  onClose: () => void;
}

interface BriefFields {
  scope: string;
  eligible_applicants: string;
  budget_per_project: string;
  trl_range: string;
  key_dates: string;
  evaluation_criteria: string;
  first_steps: string;
}

interface BriefResponse {
  opportunity_id: string;
  title: string;
  programme: string;
  deadline: string | null;
  brief: BriefFields;
  generated_at: string;
}

interface SimilarProject {
  id: string;
  project_id: string;
  acronym: string | null;
  title: string;
  objective: string | null;
  framework_programme: string | null;
  type_of_action: string | null;
  coordinator_name: string | null;
  coordinator_country: string | null;
  start_date: string | null;
  end_date: string | null;
  eu_contribution: number | null;
  cost_currency: string;
  source_url: string;
}

interface SimilarResponse {
  opportunity_id: string;
  anchor: { programme: string | null; type_of_action: string | null; title: string };
  items: SimilarProject[];
  note?: string;
}

interface FtsRecipient {
  id: number;
  title: string;
  summary: string | null;
  source_url: string;
  document_date: string | null;
}

interface FtsRecipientsResponse {
  opportunity_id: string | null;
  anchor: { programme: string; title: string };
  items: FtsRecipient[];
}

const SOURCE_LABEL: Record<UnifiedOpportunity['source'], { label: string; icon: string }> = {
  ted: { label: 'TED tender', icon: 'mdi-gavel' },
  ft_proposals: { label: 'F&T call for proposals', icon: 'mdi-flask-outline' },
  ft_tenders: { label: 'F&T call for tenders', icon: 'mdi-file-document-outline' },
  ft_projects: { label: 'F&T funded project', icon: 'mdi-trophy-outline' },
  agency: { label: 'Agency procurement', icon: 'mdi-office-building-outline' },
};

const BRIEF_FIELDS: Array<{ key: keyof BriefFields; label: string; icon: string }> = [
  { key: 'scope', label: 'Scope', icon: 'mdi-target' },
  { key: 'eligible_applicants', label: 'Eligible applicants', icon: 'mdi-account-group-outline' },
  { key: 'budget_per_project', label: 'Budget per project', icon: 'mdi-currency-eur' },
  { key: 'trl_range', label: 'TRL range', icon: 'mdi-chart-bell-curve' },
  { key: 'key_dates', label: 'Key dates', icon: 'mdi-calendar-clock' },
  { key: 'evaluation_criteria', label: 'Evaluation criteria', icon: 'mdi-scale-balance' },
  { key: 'first_steps', label: 'First steps', icon: 'mdi-rocket-launch-outline' },
];

const formatValue = (value: number | null, currency: string = 'EUR'): string | null => {
  if (!value) return null;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M ${currency}`;
  if (value >= 1_000) return `${Math.round(value / 1_000)}k ${currency}`;
  return `${value} ${currency}`;
};

const formatDate = (iso: string | null): string | null => {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  } catch {
    return iso;
  }
};

export const OpportunityDrawer = ({ opportunity, onClose }: OpportunityDrawerProps) => {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [brief, setBrief] = useState<BriefResponse | null>(null);
  const [briefLoading, setBriefLoading] = useState(false);
  const [briefError, setBriefError] = useState<string | null>(null);
  const [similar, setSimilar] = useState<SimilarResponse | null>(null);
  const [similarLoading, setSimilarLoading] = useState(false);
  const [recipients, setRecipients] = useState<FtsRecipientsResponse | null>(null);
  const [recipientsLoading, setRecipientsLoading] = useState(false);

  // Reset state when opportunity changes
  useEffect(() => {
    setBrief(null);
    setBriefError(null);
    setSimilar(null);
    setRecipients(null);
  }, [opportunity?.id]);

  // Auto-fetch similar projects for F&T proposals + projects
  const fetchSimilar = useCallback(async () => {
    if (!opportunity || !token) return;
    if (opportunity.source !== 'ft_proposals' && opportunity.source !== 'ft_projects') return;
    setSimilarLoading(true);
    try {
      const params = new URLSearchParams({ opportunity_id: opportunity.id, limit: '5' });
      const res = await fetch(`${API_URL}/api/tenders/similar-projects?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setSimilar(data);
      }
    } catch (e) {
      console.error('similar-projects fetch failed:', e);
    } finally {
      setSimilarLoading(false);
    }
  }, [opportunity, token]);

  useEffect(() => {
    void fetchSimilar();
  }, [fetchSimilar]);

  // Step 6: FTS recipients ("who's won this kind of money before?"). Anchored
  // on the opportunity's programme; fetched for any source — TED tenders also
  // get useful recipient overlap via the keyword anchor.
  const fetchRecipients = useCallback(async () => {
    if (!opportunity || !token) return;
    setRecipientsLoading(true);
    try {
      const params = new URLSearchParams({ opportunity_id: opportunity.id, limit: '6' });
      // Use the opportunity's programme as a coarse anchor when the
      // opportunity_id alone doesn't resolve a programme on the server
      // (e.g. TED / ft_tenders / agency rows). Adds an extra ILIKE filter.
      if (opportunity.programme && !opportunity.id.startsWith('ft_proposals:') && !opportunity.id.startsWith('ft_projects:')) {
        params.set('programme', opportunity.programme);
      }
      const res = await fetch(`${API_URL}/api/tenders/recipients?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setRecipients(data);
      }
    } catch (e) {
      console.error('fts recipients fetch failed:', e);
    } finally {
      setRecipientsLoading(false);
    }
  }, [opportunity, token]);

  useEffect(() => {
    void fetchRecipients();
  }, [fetchRecipients]);

  // Close on Escape
  useEffect(() => {
    if (!opportunity) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [opportunity, onClose]);

  if (!opportunity) return null;

  const handleGenerateBrief = async () => {
    if (!token) return;
    setBriefLoading(true);
    setBriefError(null);
    try {
      const res = await fetch(`${API_URL}/api/tenders/brief`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ opportunity_id: opportunity.id }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Brief generation failed.' }));
        setBriefError(err.detail || 'Brief generation failed.');
        return;
      }
      const data = await res.json();
      setBrief(data);
    } catch (e) {
      console.error('brief fetch failed:', e);
      setBriefError('Brief generation failed.');
    } finally {
      setBriefLoading(false);
    }
  };

  const handleAskBrubru = () => {
    navigate('/main', {
      state: {
        initialQuestion:
          `I want to discuss this EU opportunity: "${opportunity.title}" ` +
          `(${opportunity.external_id}, ${opportunity.programme || opportunity.source}). ` +
          'Walk me through what to do first.',
        source: 'tenderator',
      },
    });
  };

  const tag = SOURCE_LABEL[opportunity.source];

  return createPortal(
    <div
      className="opportunity-drawer__overlay"
      role="dialog"
      aria-modal="true"
      aria-label={`Opportunity details: ${opportunity.title}`}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="opportunity-drawer">
        <header className="opportunity-drawer__header">
          <span className={`opportunity-drawer__source-tag`}>
            <span className={`mdi ${tag.icon}`} aria-hidden="true" />
            {tag.label}
          </span>
          <button
            type="button"
            className="opportunity-drawer__close"
            onClick={onClose}
            aria-label="Close drawer"
          >
            <span className="mdi mdi-close" aria-hidden="true" />
          </button>
        </header>

        <div className="opportunity-drawer__body">
          {/* Title + meta */}
          <h2 className="opportunity-drawer__title">{opportunity.title}</h2>
          <dl className="opportunity-drawer__meta">
            {opportunity.external_id && (
              <div>
                <dt>Reference</dt>
                <dd className="opportunity-drawer__meta-mono">{opportunity.external_id}</dd>
              </div>
            )}
            {opportunity.programme && (
              <div>
                <dt>Programme</dt>
                <dd>{opportunity.programme}</dd>
              </div>
            )}
            {opportunity.organisation && (
              <div>
                <dt>
                  {opportunity.source === 'ft_projects'
                    ? 'Coordinator'
                    : opportunity.source === 'agency'
                    ? 'Agency'
                    : 'Organisation'}
                </dt>
                <dd>{opportunity.organisation}</dd>
              </div>
            )}
            {opportunity.country && (
              <div>
                <dt>Country</dt>
                <dd>{opportunity.country}</dd>
              </div>
            )}
            {opportunity.budget && (
              <div>
                <dt>{opportunity.source === 'ft_projects' ? 'EU contribution' : 'Budget'}</dt>
                <dd>{formatValue(opportunity.budget, opportunity.currency)}</dd>
              </div>
            )}
            {opportunity.deadline && (
              <div>
                <dt>{opportunity.source === 'ft_projects' ? 'End date' : 'Deadline'}</dt>
                <dd>{formatDate(opportunity.deadline)}</dd>
              </div>
            )}
            {opportunity.published_at && (
              <div>
                <dt>{opportunity.source === 'ft_projects' ? 'Start date' : 'Published'}</dt>
                <dd>{formatDate(opportunity.published_at)}</dd>
              </div>
            )}
            {opportunity.status && (
              <div>
                <dt>Status</dt>
                <dd>{opportunity.status}</dd>
              </div>
            )}
          </dl>

          {opportunity.description && (
            <section className="opportunity-drawer__section">
              <h3>
                <span className="mdi mdi-text-box-outline" aria-hidden="true" />
                Description
              </h3>
              <p className="opportunity-drawer__description">{opportunity.description}</p>
            </section>
          )}

          {/* Client win-rate scorecard (Layer 3) — renders nothing if the
              user has no private guide / no submissions data on file. */}
          <ClientScorecardPanel
            opportunity={{
              title: opportunity.title,
              organisation: opportunity.organisation,
              country: opportunity.country,
              programme: opportunity.programme,
            }}
          />

          {/* AI Brief */}
          <section className="opportunity-drawer__section">
            <h3>
              <span className="mdi mdi-robot-outline" aria-hidden="true" />
              Brubru brief
            </h3>
            {!brief && !briefLoading && (
              <button
                type="button"
                className="opportunity-drawer__brief-cta"
                onClick={handleGenerateBrief}
              >
                <span className="mdi mdi-flash-outline" aria-hidden="true" />
                Generate a one-page brief
              </button>
            )}
            {briefLoading && (
              <div className="opportunity-drawer__brief-loading">
                <span className="mdi mdi-loading mdi-spin" aria-hidden="true" />
                Reading the call and extracting the seven key fields...
              </div>
            )}
            {briefError && (
              <div className="opportunity-drawer__brief-error">
                <span className="mdi mdi-alert-circle-outline" aria-hidden="true" />
                {briefError}
              </div>
            )}
            {brief && (
              <dl className="opportunity-drawer__brief-fields">
                {BRIEF_FIELDS.map((f) => (
                  <div key={f.key} className="opportunity-drawer__brief-field">
                    <dt>
                      <span className={`mdi ${f.icon}`} aria-hidden="true" />
                      {f.label}
                    </dt>
                    <dd>{brief.brief[f.key]}</dd>
                  </div>
                ))}
              </dl>
            )}
          </section>

          {/* Similar projects */}
          {(opportunity.source === 'ft_proposals' || opportunity.source === 'ft_projects') && (
            <section className="opportunity-drawer__section">
              <h3>
                <span className="mdi mdi-account-network-outline" aria-hidden="true" />
                Past grantees on similar calls
              </h3>
              {similarLoading && (
                <div className="opportunity-drawer__similar-loading">
                  <span className="mdi mdi-loading mdi-spin" aria-hidden="true" />
                  Searching CORDIS for projects that won under the same programme and action type...
                </div>
              )}
              {!similarLoading && similar && similar.items.length === 0 && (
                <p className="opportunity-drawer__similar-empty">
                  {similar.note || 'No matching projects found.'}
                </p>
              )}
              {!similarLoading && similar && similar.items.length > 0 && (
                <ul className="opportunity-drawer__similar-list">
                  {similar.items.map((p) => (
                    <li key={p.id} className="opportunity-drawer__similar-item">
                      <div className="opportunity-drawer__similar-head">
                        {p.acronym && <span className="opportunity-drawer__similar-acronym">{p.acronym}</span>}
                        <span className="opportunity-drawer__similar-coord">
                          {p.coordinator_name} {p.coordinator_country && `(${p.coordinator_country})`}
                        </span>
                      </div>
                      <a href={p.source_url} target="_blank" rel="noreferrer" className="opportunity-drawer__similar-title">
                        {p.title}
                      </a>
                      {p.objective && (
                        <p className="opportunity-drawer__similar-objective">{p.objective}</p>
                      )}
                      <div className="opportunity-drawer__similar-meta">
                        {p.framework_programme && <span>{p.framework_programme}</span>}
                        {p.type_of_action && <span>{p.type_of_action}</span>}
                        {p.eu_contribution && (
                          <span>{formatValue(p.eu_contribution, p.cost_currency)}</span>
                        )}
                        {p.start_date && p.end_date && (
                          <span>{formatDate(p.start_date)} - {formatDate(p.end_date)}</span>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {/* Step 6: FTS recipients — who has won this kind of EU money
              before (Funder's Lens evidence pack). Hides cleanly when the
              endpoint returns no matches. */}
          {(recipientsLoading || (recipients && recipients.items.length > 0)) && (
            <section className="opportunity-drawer__section">
              <h3>
                <span className="mdi mdi-trophy-award" aria-hidden="true" />
                Who has won this kind of EU money before
              </h3>
              {recipientsLoading && (
                <div className="opportunity-drawer__similar-loading">
                  <span className="mdi mdi-loading mdi-spin" aria-hidden="true" />
                  Checking the EU Financial Transparency System for past direct-management recipients...
                </div>
              )}
              {!recipientsLoading && recipients && recipients.items.length > 0 && (
                <ul className="opportunity-drawer__similar-list">
                  {recipients.items.map((r) => (
                    <li key={r.id} className="opportunity-drawer__similar-item">
                      <a href={r.source_url} target="_blank" rel="noreferrer" className="opportunity-drawer__similar-title">
                        {r.title}
                      </a>
                      {r.summary && (
                        <p className="opportunity-drawer__similar-objective">{r.summary}</p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </div>

        <footer className="opportunity-drawer__footer">
          <button
            type="button"
            className="opportunity-drawer__action opportunity-drawer__action--secondary"
            onClick={handleAskBrubru}
          >
            <span className="mdi mdi-chat-processing-outline" aria-hidden="true" />
            Discuss with Brubru
          </button>
          {opportunity.source_url && (
            <a
              href={opportunity.source_url}
              target="_blank"
              rel="noreferrer"
              className="opportunity-drawer__action opportunity-drawer__action--primary"
            >
              <span className="mdi mdi-open-in-new" aria-hidden="true" />
              Open original
            </a>
          )}
        </footer>
      </div>
    </div>,
    document.body,
  );
};
