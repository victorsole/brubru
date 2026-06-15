// frontend/src/components/tenders/tenderator_dashboard.tsx
//
// Phase 1: dashboard cockpit shell.
//
// Replaces the page-with-tabs layout. Renders:
//   - slim header
//   - 5 KPI cards top strip with week-over-week deltas
//   - source filter chips (TED only in Phase 1; F&T sources land in Phase 2)
//   - main content column hosting the existing TenderFeed
//   - right rail with Brubru Brief + Urgency (closing 7d) + mini calendar
//
// The Profile, Calendar, and Detail views remain accessible. The
// dashboard is the new default landing surface.

import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../hooks/use_auth';
import { UnifiedOpportunityFeed, type UnifiedOpportunity, type MatchSubSource } from './unified_opportunity_feed';
import { OpportunityDrawer } from './opportunity_drawer';
import { ProgrammesPanel } from './programmes_panel';
import { BodiesPanel } from './bodies_panel';
import { PortalActivityPanel } from './portal_activity_panel';
import type { Tender, TenderMatch, TenderProfile } from '../../pages/tenderator_page';
import './tenderator_dashboard.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export type SourceFilter = 'all' | 'matches' | 'ted' | 'ft_proposals' | 'ft_tenders' | 'ft_projects' | 'agency' | 'programmes';

interface ClosingSoonItem {
  tender_id: number;
  match_id: number;
  publication_number: string;
  title: string;
  deadline: string | null;
  days_left: number;
  estimated_value: number | null;
  currency: string;
  source: string;
}

interface DashboardStats {
  kpis: {
    open_opportunities: number;
    closing_7d: number;
    your_matches: number;
    your_saved: number;
    applied_ytd: number;
  };
  deltas: {
    matches_wow: number;
    saved_wow: number;
    matches_this_week: number;
    saved_this_week: number;
  };
  by_source: {
    ted: number;
    ft_proposals: number;
    ft_tenders: number;
    ft_projects: number;
    agency: number;
  };
  closing_soon: ClosingSoonItem[];
  generated_at: string;
}

interface TenderatorDashboardProps {
  userProfile: TenderProfile;
  onSelectTender: (tender: Tender, match?: TenderMatch) => void;
  onViewChecklist?: (tender: Tender) => void;
  onOpenProfile: () => void;
  onOpenCalendar: () => void;
}

// Map a UnifiedOpportunity onto the existing Tender shape so we can re-use
// the TenderDetail page for non-TED items. F&T-specific fields stay in
// metadata-style attributes the detail page already tolerates.
const unifiedToTender = (opp: UnifiedOpportunity): Tender => ({
  id: opp.source === 'ted' && /^ted:\d+$/.test(opp.id)
    ? Number(opp.id.split(':')[1])
    : -1, // F&T items have no integer tender_id; -1 signals "not in tenders table"
  publication_number: opp.external_id,
  title: opp.title,
  buyer_name: opp.organisation || '',
  buyer_country: opp.country || '',
  estimated_value: opp.budget,
  currency: opp.currency,
  cpv_main: '',
  cpv_codes: [],
  procedure_type: '',
  submission_deadline: opp.deadline,
  publication_date: opp.published_at || '',
  status: opp.status || 'open',
  sme_suitability_score: null,
  description: opp.description || undefined,
  ted_url: opp.source_url,
});

const formatValue = (value: number | null, currency: string = 'EUR'): string => {
  if (!value) return '';
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M ${currency}`;
  if (value >= 1_000) return `${Math.round(value / 1_000)}k ${currency}`;
  return `${value} ${currency}`;
};

const formatNumber = (n: number): string => n.toLocaleString('en-GB');

const renderDelta = (wow: number): { label: string; cls: string } => {
  if (wow > 0) return { label: `+${wow} this week`, cls: 'tenderator-dashboard__delta--up' };
  if (wow < 0) return { label: `${wow} this week`, cls: 'tenderator-dashboard__delta--down' };
  return { label: 'no change this week', cls: 'tenderator-dashboard__delta--flat' };
};

export const TenderatorDashboard = ({
  userProfile,
  onSelectTender,
  onViewChecklist: _onViewChecklist,
  onOpenProfile,
  onOpenCalendar,
}: TenderatorDashboardProps) => {
  const profileUpdatedAt = userProfile?.updated_at || '';
  const { token } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const incomingQuery = searchParams.get('q') || '';
  // Chat → Tenderator deep links can ship a `source` (e.g. 'agency') and a
  // `body` (e.g. 'efsa') so the dashboard opens directly on the right view.
  const incomingSourceParam = searchParams.get('source') as SourceFilter | null;
  const incomingBody = searchParams.get('body') || '';
  const validInitialSource: SourceFilter | null = incomingSourceParam &&
    (['all','matches','ted','ft_proposals','ft_tenders','ft_projects','agency'] as SourceFilter[])
      .includes(incomingSourceParam) ? incomingSourceParam : null;
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [source, setSource] = useState<SourceFilter>(validInitialSource || 'all');
  const [error, setError] = useState<string | null>(null);
  const [drawerOpp, setDrawerOpp] = useState<UnifiedOpportunity | null>(null);
  // Selected EU funding programme code (e.g. EU4H). Filters the proposals feed
  // by topic_id prefix. Only applied while the proposals source is active.
  const [programmeCode, setProgrammeCode] = useState<string>('');
  // Selected agency body slug (e.g. 'efsa'). Only applied while the agency
  // source is active. Carried via URL on Chat → Tenderator deep links.
  const [agencyBody, setAgencyBody] = useState<string>(incomingBody);
  const [matchSubSource, setMatchSubSource] = useState<MatchSubSource>('all');

  const fetchStats = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_URL}/api/tenders/dashboard-stats`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const d = await res.json();
        setStats(d);
        setError(null);
      } else {
        setError('Could not load dashboard metrics.');
      }
    } catch (e) {
      console.error('dashboard-stats fetch failed:', e);
      setError('Could not load dashboard metrics.');
    }
  }, [token]);

  useEffect(() => {
    void fetchStats();
    // profileUpdatedAt in the dep list forces a refetch when the user
    // saves their profile so KPI cards reflect the new match count.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchStats, profileUpdatedAt]);

  const handleAskBrubru = (query: string) => {
    navigate('/main', { state: { initialQuestion: query, source: 'tenderator' } });
  };

  const kpis = stats?.kpis;
  const deltas = stats?.deltas;
  const closingSoon = stats?.closing_soon || [];
  const bySource = stats?.by_source;

  return (
    <div className="tenderator-dashboard">
      {/* Header */}
      <header className="tenderator-dashboard__header">
        <div className="tenderator-dashboard__header-left">
          <span className="mdi mdi-piggy-bank-outline tenderator-dashboard__header-icon" aria-hidden="true" />
          <div>
            <h1 className="tenderator-dashboard__title">Tenderator</h1>
            <p className="tenderator-dashboard__subtitle">
              EU funding and procurement, all in one place.
            </p>
          </div>
        </div>
        <div className="tenderator-dashboard__header-actions">
          <button
            type="button"
            className="tenderator-dashboard__icon-button"
            onClick={onOpenCalendar}
            title="Calendar"
            aria-label="Open calendar"
          >
            <span className="mdi mdi-calendar-month" aria-hidden="true" />
          </button>
          <button
            type="button"
            className="tenderator-dashboard__icon-button"
            onClick={onOpenProfile}
            title="Profile"
            aria-label="Open profile"
          >
            <span className="mdi mdi-account-cog-outline" aria-hidden="true" />
          </button>
          <span className="tenderator-dashboard__tier-badge">
            <span className="mdi mdi-star-circle" aria-hidden="true" />
            Professional
          </span>
        </div>
      </header>

      {/* KPI strip */}
      <section className="tenderator-dashboard__kpis" aria-label="Tenderator key metrics">
        <div className="tenderator-dashboard__kpi tenderator-dashboard__kpi--primary">
          <span className="tenderator-dashboard__kpi-label">Open opportunities</span>
          <span className="tenderator-dashboard__kpi-value">
            {kpis ? formatNumber(kpis.open_opportunities) : '...'}
          </span>
          <span className="tenderator-dashboard__kpi-meta">across all sources</span>
        </div>
        <div className="tenderator-dashboard__kpi tenderator-dashboard__kpi--urgent">
          <span className="tenderator-dashboard__kpi-label">Closing in 7 days</span>
          <span className="tenderator-dashboard__kpi-value">
            {kpis ? formatNumber(kpis.closing_7d) : '...'}
          </span>
          <span className="tenderator-dashboard__kpi-meta">in your portfolio</span>
        </div>
        <div className="tenderator-dashboard__kpi">
          <span className="tenderator-dashboard__kpi-label">Your matches</span>
          <span className="tenderator-dashboard__kpi-value">
            {kpis ? formatNumber(kpis.your_matches) : '...'}
          </span>
          {deltas && (
            <span className={`tenderator-dashboard__delta ${renderDelta(deltas.matches_wow).cls}`}>
              <span className="mdi mdi-trending-up" aria-hidden="true" />
              {renderDelta(deltas.matches_wow).label}
            </span>
          )}
        </div>
        <div className="tenderator-dashboard__kpi">
          <span className="tenderator-dashboard__kpi-label">Saved</span>
          <span className="tenderator-dashboard__kpi-value">
            {kpis ? formatNumber(kpis.your_saved) : '...'}
          </span>
          {deltas && (
            <span className={`tenderator-dashboard__delta ${renderDelta(deltas.saved_wow).cls}`}>
              <span className="mdi mdi-bookmark-outline" aria-hidden="true" />
              {renderDelta(deltas.saved_wow).label}
            </span>
          )}
        </div>
        <div className="tenderator-dashboard__kpi">
          <span className="tenderator-dashboard__kpi-label">Applied YTD</span>
          <span className="tenderator-dashboard__kpi-value">
            {kpis ? formatNumber(kpis.applied_ytd) : '...'}
          </span>
          <span className="tenderator-dashboard__kpi-meta">in {new Date().getFullYear()}</span>
        </div>
      </section>

      {/* Source filter chips */}
      <section className="tenderator-dashboard__chips" aria-label="Source filter">
        <button
          type="button"
          className={`tenderator-dashboard__chip ${source === 'matches' ? 'tenderator-dashboard__chip--active' : ''} tenderator-dashboard__chip--matches`}
          onClick={() => setSource('matches')}
          title="Tenders ranked for your profile"
        >
          <span className="mdi mdi-star-outline" aria-hidden="true" />
          Your matches
          {kpis && <span className="tenderator-dashboard__chip-count">{formatNumber(kpis.your_matches)}</span>}
        </button>
        <button
          type="button"
          className={`tenderator-dashboard__chip ${source === 'all' ? 'tenderator-dashboard__chip--active' : ''}`}
          onClick={() => setSource('all')}
        >
          <span className="mdi mdi-view-grid-outline" aria-hidden="true" />
          All sources
          {bySource && (
            <span className="tenderator-dashboard__chip-count">
              {formatNumber((bySource.ted || 0) + (bySource.ft_proposals || 0) + (bySource.ft_tenders || 0) + (bySource.agency || 0))}
            </span>
          )}
        </button>
        <button
          type="button"
          className={`tenderator-dashboard__chip ${source === 'ted' ? 'tenderator-dashboard__chip--active' : ''}`}
          onClick={() => setSource('ted')}
        >
          <span className="mdi mdi-gavel" aria-hidden="true" />
          TED tenders
          {bySource && <span className="tenderator-dashboard__chip-count">{formatNumber(bySource.ted)}</span>}
        </button>
        <button
          type="button"
          className={`tenderator-dashboard__chip ${source === 'ft_proposals' ? 'tenderator-dashboard__chip--active' : ''}`}
          onClick={() => { setProgrammeCode(''); setSource('ft_proposals'); }}
        >
          <span className="mdi mdi-flask-outline" aria-hidden="true" />
          Calls for proposals
          {bySource && <span className="tenderator-dashboard__chip-count">{formatNumber(bySource.ft_proposals)}</span>}
        </button>
        <button
          type="button"
          className={`tenderator-dashboard__chip ${source === 'ft_tenders' ? 'tenderator-dashboard__chip--active' : ''}`}
          onClick={() => setSource('ft_tenders')}
        >
          <span className="mdi mdi-file-document-outline" aria-hidden="true" />
          Calls for tenders
          {bySource && <span className="tenderator-dashboard__chip-count">{formatNumber(bySource.ft_tenders)}</span>}
        </button>
        <button
          type="button"
          className={`tenderator-dashboard__chip ${source === 'ft_projects' ? 'tenderator-dashboard__chip--active' : ''}`}
          onClick={() => setSource('ft_projects')}
        >
          <span className="mdi mdi-trophy-outline" aria-hidden="true" />
          Funded projects
          {bySource && <span className="tenderator-dashboard__chip-count">{formatNumber(bySource.ft_projects)}</span>}
        </button>
        <button
          type="button"
          className={`tenderator-dashboard__chip ${source === 'agency' ? 'tenderator-dashboard__chip--active' : ''}`}
          onClick={() => { setProgrammeCode(''); setAgencyBody(''); setSource('agency'); }}
          title="Tenders, grants and calls for expression of interest published by EU agencies on their own sites — below TED threshold, not on the central F&T Portal."
        >
          <span className="mdi mdi-office-building-outline" aria-hidden="true" />
          Agency procurement
          {bySource && <span className="tenderator-dashboard__chip-count">{formatNumber(bySource.agency)}</span>}
        </button>
        {/* Step 6: dedicated startup/SME chip — pre-filters proposals to the EIC programme
            (EIC Accelerator, Pathfinder, Transition, STEP, prizes). */}
        <button
          type="button"
          className={`tenderator-dashboard__chip ${source === 'ft_proposals' && programmeCode === 'EIC' ? 'tenderator-dashboard__chip--active' : ''}`}
          onClick={() => { setAgencyBody(''); setProgrammeCode('EIC'); setSource('ft_proposals'); }}
          title="EIC funding for startups + SMEs — Accelerator, Pathfinder, Transition, STEP, prizes."
        >
          <span className="mdi mdi-rocket-launch-outline" aria-hidden="true" />
          Startups &amp; SMEs (EIC)
        </button>
      </section>

      {/* Error banner */}
      {error && (
        <div className="tenderator-dashboard__error">
          <span className="mdi mdi-alert-circle-outline" aria-hidden="true" />
          {error}
          <button type="button" onClick={() => void fetchStats()}>Retry</button>
        </div>
      )}

      {/* Main grid: feed + right rail */}
      <div className="tenderator-dashboard__grid">
        <main className="tenderator-dashboard__main">
          {source === 'matches' && (
            <div className="tenderator-dashboard__sub-chips" role="group" aria-label="Filter matches by source">
              <span className="tenderator-dashboard__sub-chips-label">
                <span className="mdi mdi-filter-variant" aria-hidden="true" />
                Match in
              </span>
              <button
                type="button"
                className={`tenderator-dashboard__sub-chip ${matchSubSource === 'all' ? 'tenderator-dashboard__sub-chip--active' : ''}`}
                onClick={() => setMatchSubSource('all')}
              >
                All
              </button>
              <button
                type="button"
                className={`tenderator-dashboard__sub-chip ${matchSubSource === 'ted' ? 'tenderator-dashboard__sub-chip--active' : ''}`}
                onClick={() => setMatchSubSource('ted')}
              >
                <span className="mdi mdi-gavel" aria-hidden="true" />
                TED
              </button>
              <button
                type="button"
                className={`tenderator-dashboard__sub-chip ${matchSubSource === 'ft_proposals' ? 'tenderator-dashboard__sub-chip--active' : ''}`}
                onClick={() => setMatchSubSource('ft_proposals')}
              >
                <span className="mdi mdi-flask-outline" aria-hidden="true" />
                Calls for proposals
              </button>
              <button
                type="button"
                className={`tenderator-dashboard__sub-chip ${matchSubSource === 'ft_tenders' ? 'tenderator-dashboard__sub-chip--active' : ''}`}
                onClick={() => setMatchSubSource('ft_tenders')}
              >
                <span className="mdi mdi-file-document-outline" aria-hidden="true" />
                Calls for tenders
              </button>
              <button
                type="button"
                className={`tenderator-dashboard__sub-chip ${matchSubSource === 'agency' ? 'tenderator-dashboard__sub-chip--active' : ''}`}
                onClick={() => setMatchSubSource('agency')}
                title="Decentralised EU agency procurement (EFCA, EMA, EFSA, Eurojust, ETF, Cedefop, …)"
              >
                <span className="mdi mdi-office-building-outline" aria-hidden="true" />
                Agencies
              </button>
            </div>
          )}
          <UnifiedOpportunityFeed
            source={source}
            matchSubSource={matchSubSource}
            programme={source === 'ft_proposals' ? programmeCode : ''}
            body={source === 'agency' ? agencyBody : ''}
            initialQuery={incomingQuery}
            onSelectOpportunity={(opp) => {
              // For TED tenders with a real tenders.id, keep the existing
              // full-page TenderDetail route so saved/dismissed flows work.
              // For F&T sources (no tenders.id), open the drawer.
              if (opp.source === 'ted' && /^ted:\d+$/.test(opp.id)) {
                onSelectTender(unifiedToTender(opp));
              } else {
                setDrawerOpp(opp);
              }
            }}
          />
        </main>

        <aside className="tenderator-dashboard__rail">
          {/* Brubru Brief */}
          <div className="tenderator-dashboard__brief">
            <div className="tenderator-dashboard__brief-lede">
              <span className="mdi mdi-bell-ring-outline" aria-hidden="true" />
              Brubru noticed
            </div>
            {kpis && kpis.closing_7d > 0 ? (
              <button
                type="button"
                className="tenderator-dashboard__brief-card"
                onClick={() =>
                  handleAskBrubru(
                    `Walk me through the ${kpis.closing_7d} tenders closing in the next 7 days. ` +
                    'Tell me which one I should look at first.'
                  )
                }
              >
                <span className="tenderator-dashboard__brief-spoken">
                  {kpis.closing_7d === 1
                    ? '1 of your matched tenders closes in the next 7 days.'
                    : `${kpis.closing_7d} of your matched tenders close in the next 7 days.`}
                </span>
                <span className="tenderator-dashboard__brief-cta">
                  Tell me more
                  <span className="mdi mdi-arrow-right" aria-hidden="true" />
                </span>
              </button>
            ) : (
              <p className="tenderator-dashboard__brief-quiet">
                Nothing urgent on your watch this week. I will tell you when a deadline is coming.
              </p>
            )}
          </div>

          {/* Urgency: closing soon */}
          <div className="tenderator-dashboard__urgency">
            <div className="tenderator-dashboard__urgency-header">
              <span className="mdi mdi-clock-alert-outline" aria-hidden="true" />
              Closing soon
            </div>
            {closingSoon.length === 0 ? (
              <p className="tenderator-dashboard__urgency-empty">
                No saved or matched items with a deadline in the next 14 days.
              </p>
            ) : (
              <ul className="tenderator-dashboard__urgency-list">
                {closingSoon.map((item) => {
                  const sev =
                    item.days_left <= 3
                      ? 'tenderator-dashboard__urgency-item--red'
                      : item.days_left <= 7
                      ? 'tenderator-dashboard__urgency-item--amber'
                      : 'tenderator-dashboard__urgency-item--green';
                  return (
                    <li key={item.tender_id} className={`tenderator-dashboard__urgency-item ${sev}`}>
                      <button
                        type="button"
                        className="tenderator-dashboard__urgency-button"
                        onClick={() =>
                          onSelectTender(
                            {
                              id: item.tender_id,
                              publication_number: item.publication_number,
                              title: item.title,
                              buyer_name: '',
                              buyer_country: '',
                              estimated_value: item.estimated_value,
                              currency: item.currency,
                              cpv_main: '',
                              cpv_codes: [],
                              procedure_type: '',
                              submission_deadline: item.deadline,
                              publication_date: '',
                              status: 'open',
                              sme_suitability_score: null,
                            } as Tender,
                          )
                        }
                      >
                        <span className="tenderator-dashboard__urgency-days">
                          {item.days_left === 0
                            ? 'today'
                            : item.days_left === 1
                            ? '1 day'
                            : `${item.days_left} days`}
                        </span>
                        <span className="tenderator-dashboard__urgency-title">{item.title}</span>
                        {item.estimated_value && (
                          <span className="tenderator-dashboard__urgency-value">
                            {formatValue(item.estimated_value, item.currency)}
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {/* By-source counts */}
          {bySource && (
            <div className="tenderator-dashboard__sources">
              <div className="tenderator-dashboard__sources-header">
                <span className="mdi mdi-database-outline" aria-hidden="true" />
                Sources Brubru watches
              </div>
              <ul className="tenderator-dashboard__sources-list">
                <li><span>TED tenders</span><span>{formatNumber(bySource.ted)}</span></li>
                <li><span>F&amp;T calls for proposals</span><span>{formatNumber(bySource.ft_proposals)}</span></li>
                <li><span>F&amp;T calls for tenders</span><span>{formatNumber(bySource.ft_tenders)}</span></li>
                <li><span>F&amp;T funded projects</span><span>{formatNumber(bySource.ft_projects)}</span></li>
                <li><span>Agency procurement</span><span>{formatNumber(bySource.agency)}</span></li>
              </ul>
            </div>
          )}

          {/* Phase 5: EU funding programmes catalogue */}
          <ProgrammesPanel
            onPickProgramme={(p) => {
              setProgrammeCode(p.programme_code);
              setSource('ft_proposals');
            }}
          />

          {/* F&T Portal activity: latest news + upcoming events (15 Jun 2026) */}
          <PortalActivityPanel />

          {/* Step 5 (All EU): EU agencies running their own procurement */}
          <BodiesPanel
            activeBodyCode={source === 'agency' ? agencyBody : ''}
            onPickBody={(b) => {
              setProgrammeCode('');
              setAgencyBody(b.body_code);
              setSource('agency');
            }}
          />
        </aside>
      </div>

      {/* Opportunity drawer (Phase 3): brief + similar projects */}
      <OpportunityDrawer opportunity={drawerOpp} onClose={() => setDrawerOpp(null)} />
    </div>
  );
};
