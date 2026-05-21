// frontend/src/components/tenders/client_scorecard_panel.tsx
//
// Layer 3: per-client win-rate scorecard. Lives inside the opportunity
// drawer. When the user has a private_guide_slug with client_submissions
// rows on file, this fetches /api/tenders/client-scorecard with hints
// derived from the current opportunity and renders:
//   - Overall win rate
//   - Top win rates by leading partner
//   - Top win rates by contracting authority
//   - Top-3 lookalike past bids with outcomes + comments
//
// Fail-soft: if scorecard_available=false, render nothing.

import { useEffect, useState } from 'react';
import { useAuth } from '../../hooks/use_auth';
import './client_scorecard_panel.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface LookalikeRow {
  id: string;
  project_title: string;
  contracting_authority: string | null;
  country: string | null;
  programme: string | null;
  lot: string | null;
  outcome: string;
  comments: string | null;
  submission_date: string | null;
  leading_partner: string | null;
  budget_eur: number | null;
}

interface ScorecardResponse {
  slug: string | null;
  scorecard_available: boolean;
  reason?: string;
  overall?: {
    total: number;
    awarded: number;
    not_awarded: number;
    pending: number;
    cancelled: number;
    decided: number;
    win_rate_pct: number | null;
  };
  by_leading_partner?: Array<{
    leading_partner: string;
    awarded: number;
    lost: number;
    pending: number;
    win_rate_pct: number | null;
  }>;
  by_contracting_authority?: Array<{
    contracting_authority: string;
    awarded: number;
    lost: number;
    pending: number;
    win_rate_pct: number | null;
  }>;
  lookalikes?: LookalikeRow[];
}

interface Props {
  opportunity: {
    title: string;
    organisation: string | null;
    country: string | null;
    programme: string | null;
  };
}

const OUTCOME_LABEL: Record<string, string> = {
  awarded: 'Won',
  not_awarded: 'Lost',
  pending: 'Pending',
  cancelled: 'Cancelled',
  withdrawn: 'Withdrawn',
};

const OUTCOME_CLS: Record<string, string> = {
  awarded: 'scorecard__lookalike-outcome--won',
  not_awarded: 'scorecard__lookalike-outcome--lost',
  pending: 'scorecard__lookalike-outcome--pending',
  cancelled: 'scorecard__lookalike-outcome--cancelled',
  withdrawn: 'scorecard__lookalike-outcome--cancelled',
};

export const ClientScorecardPanel = ({ opportunity }: Props) => {
  const { token } = useAuth();
  const [data, setData] = useState<ScorecardResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) return;
    const ctrl = new AbortController();
    const params = new URLSearchParams();
    if (opportunity.organisation) params.set('ca', opportunity.organisation);
    if (opportunity.country) params.set('country', opportunity.country);
    if (opportunity.programme) params.set('programme', opportunity.programme);
    // First word of the title as a soft keyword hint
    const firstWord = (opportunity.title || '').split(/\s+/)[0];
    if (firstWord && firstWord.length > 3) params.set('keyword', firstWord);
    params.set('lookalike_limit', '3');

    setLoading(true);
    fetch(`${API_URL}/api/tenders/scorecard/client?${params.toString()}`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: ctrl.signal,
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: ScorecardResponse | null) => {
        if (d) setData(d);
      })
      .catch(() => { /* network / abort */ })
      .finally(() => setLoading(false));
    return () => ctrl.abort();
  }, [token, opportunity.title, opportunity.organisation, opportunity.country, opportunity.programme]);

  if (loading && !data) return null;
  if (!data || !data.scorecard_available) return null;
  if (!data.overall) return null;

  const wr = data.overall.win_rate_pct;
  const topLead = (data.by_leading_partner || [])
    .filter((r) => (r.awarded + r.lost) >= 2)
    .slice(0, 4);
  const topCA = (data.by_contracting_authority || [])
    .filter((r) => (r.awarded + r.lost) >= 2)
    .slice(0, 4);
  const lookalikes = data.lookalikes || [];

  return (
    <div className="scorecard-panel">
      <div className="scorecard-panel__header">
        <span className="mdi mdi-chart-arc" aria-hidden="true" />
        <span className="scorecard-panel__title">Your win-rate intel</span>
        <span className="scorecard-panel__subtitle">from your internal tracker</span>
      </div>

      {/* Overall band */}
      <div className="scorecard-panel__overall">
        <div className="scorecard-panel__stat">
          <span className="scorecard-panel__stat-value">
            {wr !== null ? `${wr}%` : 'n/a'}
          </span>
          <span className="scorecard-panel__stat-label">Win rate on decided</span>
        </div>
        <div className="scorecard-panel__stat">
          <span className="scorecard-panel__stat-value">{data.overall.awarded}</span>
          <span className="scorecard-panel__stat-label">Awarded</span>
        </div>
        <div className="scorecard-panel__stat">
          <span className="scorecard-panel__stat-value">{data.overall.not_awarded}</span>
          <span className="scorecard-panel__stat-label">Lost</span>
        </div>
        <div className="scorecard-panel__stat">
          <span className="scorecard-panel__stat-value">{data.overall.pending}</span>
          <span className="scorecard-panel__stat-label">Pending</span>
        </div>
      </div>

      {/* Breakdowns */}
      {(topLead.length > 0 || topCA.length > 0) && (
        <div className="scorecard-panel__breakdowns">
          {topLead.length > 0 && (
            <div className="scorecard-panel__breakdown">
              <div className="scorecard-panel__breakdown-title">By leading partner</div>
              <ul className="scorecard-panel__breakdown-list">
                {topLead.map((r) => (
                  <li key={r.leading_partner}>
                    <span className="scorecard-panel__breakdown-name">{r.leading_partner}</span>
                    <span className="scorecard-panel__breakdown-stat">
                      {r.awarded}W / {r.lost}L
                      {r.win_rate_pct !== null && ` · ${r.win_rate_pct}%`}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {topCA.length > 0 && (
            <div className="scorecard-panel__breakdown">
              <div className="scorecard-panel__breakdown-title">By contracting authority</div>
              <ul className="scorecard-panel__breakdown-list">
                {topCA.map((r) => (
                  <li key={r.contracting_authority}>
                    <span className="scorecard-panel__breakdown-name">{r.contracting_authority}</span>
                    <span className="scorecard-panel__breakdown-stat">
                      {r.awarded}W / {r.lost}L
                      {r.win_rate_pct !== null && ` · ${r.win_rate_pct}%`}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Lookalikes */}
      {lookalikes.length > 0 && (
        <div className="scorecard-panel__lookalikes">
          <div className="scorecard-panel__lookalikes-title">Lookalike past bids</div>
          <ul className="scorecard-panel__lookalikes-list">
            {lookalikes.map((r) => (
              <li key={r.id} className="scorecard-panel__lookalike">
                <div className="scorecard-panel__lookalike-head">
                  <span
                    className={`scorecard-panel__lookalike-outcome ${OUTCOME_CLS[r.outcome] || ''}`}
                  >
                    {OUTCOME_LABEL[r.outcome] || r.outcome}
                  </span>
                  <span className="scorecard-panel__lookalike-title">{r.project_title}</span>
                </div>
                <div className="scorecard-panel__lookalike-meta">
                  {r.contracting_authority && <span>{r.contracting_authority}</span>}
                  {r.country && <span>{r.country}</span>}
                  {r.programme && <span>{r.programme}{r.lot ? ` · ${r.lot}` : ''}</span>}
                  {r.leading_partner && <span>lead: {r.leading_partner}</span>}
                </div>
                {r.comments && (
                  <div className="scorecard-panel__lookalike-comment">
                    "{r.comments.slice(0, 240)}{r.comments.length > 240 ? '…' : ''}"
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
