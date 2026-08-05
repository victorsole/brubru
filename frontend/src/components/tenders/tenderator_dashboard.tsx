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
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/use_auth';
import { UnifiedOpportunityFeed, type UnifiedOpportunity, type MatchSubSource } from './unified_opportunity_feed';
import type { LensMode } from '../bubble/lens_toggle';
import { OpportunityDrawer } from './opportunity_drawer';
import { ProgrammesPanel } from './programmes_panel';
import { BodiesPanel } from './bodies_panel';
import { PortalActivityPanel } from './portal_activity_panel';
import { PipelineView } from './pipeline_view';
import type { Tender, TenderMatch, TenderProfile } from '../../pages/tenderator_page';
import './tenderator_dashboard.css';
import { uiDateLocale } from '../../i18n/config';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export type SourceFilter = 'all' | 'matches' | 'ted' | 'ft_proposals' | 'ft_tenders' | 'ft_projects' | 'agency' | 'intl_coop' | 'pipeline';

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
  onOpenTenderDocs?: () => void;
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

const formatNumber = (n: number): string => n.toLocaleString(uiDateLocale());

const renderDelta = (wow: number, t: any): { label: string; cls: string } => {
  if (wow > 0) return { label: `+${wow} ${t('tenderator.dashboard.thisWeek')}`, cls: 'tenderator-dashboard__delta--up' };
  if (wow < 0) return { label: `${wow} ${t('tenderator.dashboard.thisWeek')}`, cls: 'tenderator-dashboard__delta--down' };
  return { label: t('tenderator.dashboard.noChangeThisWeek'), cls: 'tenderator-dashboard__delta--flat' };
};

export const TenderatorDashboard = ({
  userProfile,
  onSelectTender,
  onViewChecklist: _onViewChecklist,
  onOpenProfile,
  onOpenCalendar,
  onOpenTenderDocs,
}: TenderatorDashboardProps) => {
  const { t } = useTranslation();
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
    (['all','matches','ted','ft_proposals','ft_tenders','ft_projects','agency','intl_coop','pipeline'] as SourceFilter[])
      .includes(incomingSourceParam) ? incomingSourceParam : null;
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [source, setSource] = useState<SourceFilter>(validInitialSource || 'all');
  const [error, setError] = useState<string | null>(null);
  const [drawerOpp, setDrawerOpp] = useState<UnifiedOpportunity | null>(null);
  // Selected EU funding programme code (e.g. EU4H). Filters the proposals feed
  // by topic_id prefix. Only applied while the proposals source is active.
  const [programmeCode, setProgrammeCode] = useState<string>('');
  // Lens override (Move 1 of #5, 15 Jun 2026). When the user clicks an
  // explicit-intent chip ("Startups & SMEs (EIC)") we set this to 'all' so a
  // stale Policy-Interest lens can't intersect EIC topics down to zero. The
  // LensToggle inside the feed can still flip the user back to 'pi' — its
  // onLensModeChange callback writes through this state.
  const [lensOverride, setLensOverride] = useState<LensMode | null>(null);
  // EIC sub-bucket (Move 2 of #5, 15 Jun 2026). One of: '' (All EIC) |
  // 'accelerator' | 'pathfinder' | 'transition' | 'step-scale' | 'prize'.
  // Sent to the unified-feed endpoint as the eic_programme query param. Only
  // meaningful when programmeCode === 'EIC'; cleared when navigating away.
  const [eicBucket, setEicBucket] = useState<string>('');
  // Clear the lens override the moment the user navigates off the EIC chip
  // (different programme code or different source). Without this, the
  // override would leak across chips.
  useEffect(() => {
    if (programmeCode !== 'EIC' || source !== 'ft_proposals') {
      setLensOverride(null);
      setEicBucket('');
    }
  }, [programmeCode, source]);
  // Selected agency body slug (e.g. 'efsa'). Only applied while the agency
  // source is active. Carried via URL on Chat → Tenderator deep links.
  const [agencyBody, setAgencyBody] = useState<string>(incomingBody);
  const [matchSubSource, setMatchSubSource] = useState<MatchSubSource>('all');
  // External-action lens (Move 1, 15 Jun 2026): narrow every source to EU
  // development-cooperation contracts (DG INTPA/NEAR/ECHO/FPI/EEAS + NDICI/
  // IPA III/HUMA programmes) and unlock the FTS-awards source. Persisted +
  // restored from localStorage. When ON, a beneficiary-country dropdown
  // appears below the chip row.
  const [externalAction, setExternalAction] = useState<boolean>(() => {
    try { return localStorage.getItem('tenderator_external_action') === '1'; } catch { return false; }
  });
  const [beneficiaryCountry, setBeneficiaryCountry] = useState<string>(() => {
    try { return localStorage.getItem('tenderator_benef_country') || ''; } catch { return ''; }
  });
  // Move 5 (15 Jun 2026): framework_only lens — narrows source=agency to
  // item_type='framework' (EU-institution Framework Contracts).
  const [frameworkOnly, setFrameworkOnly] = useState<boolean>(() => {
    try { return localStorage.getItem('tenderator_framework_only') === '1'; } catch { return false; }
  });

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
        setError(t('tenderator.dashboard.errorLoadingMetrics'));
      }
    } catch (e) {
      console.error('dashboard-stats fetch failed:', e);
      setError(t('tenderator.dashboard.errorLoadingMetrics'));
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
            <h1 className="tenderator-dashboard__title">{t('tenderator.dashboard.title')}</h1>
            <p className="tenderator-dashboard__subtitle">
              {t('tenderator.dashboard.subtitle')}
            </p>
          </div>
        </div>
        <div className="tenderator-dashboard__header-actions">
          <button
            type="button"
            className="tenderator-dashboard__icon-button"
            onClick={onOpenCalendar}
            title={t('tenderator.dashboard.calendarButton')}
            aria-label={t('tenderator.dashboard.openCalendar')}
          >
            <span className="mdi mdi-calendar-month" aria-hidden="true" />
          </button>
          <button
            type="button"
            className="tenderator-dashboard__icon-button"
            onClick={onOpenProfile}
            title={t('tenderator.dashboard.profileButton')}
            aria-label={t('tenderator.dashboard.openProfile')}
          >
            <span className="mdi mdi-account-cog-outline" aria-hidden="true" />
          </button>
          <span className="tenderator-dashboard__tier-badge">
            <span className="mdi mdi-star-circle" aria-hidden="true" />
            {t('tenderator.dashboard.tierProfessional')}
          </span>
        </div>
      </header>

      {/* KPI strip */}
      <section className="tenderator-dashboard__kpis" aria-label={t('tenderator.dashboard.kpisLabel')}>
        <div className="tenderator-dashboard__kpi tenderator-dashboard__kpi--primary">
          <span className="tenderator-dashboard__kpi-label">{t('tenderator.dashboard.kpi.openOpportunities')}</span>
          <span className="tenderator-dashboard__kpi-value">
            {kpis ? formatNumber(kpis.open_opportunities) : '...'}
          </span>
          <span className="tenderator-dashboard__kpi-meta">{t('tenderator.dashboard.kpi.acrossAllSources')}</span>
        </div>
        <div className="tenderator-dashboard__kpi tenderator-dashboard__kpi--urgent">
          <span className="tenderator-dashboard__kpi-label">{t('tenderator.dashboard.kpi.closingIn7Days')}</span>
          <span className="tenderator-dashboard__kpi-value">
            {kpis ? formatNumber(kpis.closing_7d) : '...'}
          </span>
          <span className="tenderator-dashboard__kpi-meta">{t('tenderator.dashboard.kpi.inYourPortfolio')}</span>
        </div>
        <div className="tenderator-dashboard__kpi">
          <span className="tenderator-dashboard__kpi-label">{t('tenderator.dashboard.kpi.yourMatches')}</span>
          <span className="tenderator-dashboard__kpi-value">
            {kpis ? formatNumber(kpis.your_matches) : '...'}
          </span>
          {deltas && (
            <span className={`tenderator-dashboard__delta ${renderDelta(deltas.matches_wow, t).cls}`}>
              <span className="mdi mdi-trending-up" aria-hidden="true" />
              {renderDelta(deltas.matches_wow, t).label}
            </span>
          )}
        </div>
        <div className="tenderator-dashboard__kpi">
          <span className="tenderator-dashboard__kpi-label">{t('tenderator.dashboard.kpi.saved')}</span>
          <span className="tenderator-dashboard__kpi-value">
            {kpis ? formatNumber(kpis.your_saved) : '...'}
          </span>
          {deltas && (
            <span className={`tenderator-dashboard__delta ${renderDelta(deltas.saved_wow, t).cls}`}>
              <span className="mdi mdi-bookmark-outline" aria-hidden="true" />
              {renderDelta(deltas.saved_wow, t).label}
            </span>
          )}
        </div>
        <div className="tenderator-dashboard__kpi">
          <span className="tenderator-dashboard__kpi-label">{t('tenderator.dashboard.kpi.appliedYTD')}</span>
          <span className="tenderator-dashboard__kpi-value">
            {kpis ? formatNumber(kpis.applied_ytd) : '...'}
          </span>
          <span className="tenderator-dashboard__kpi-meta">{t('tenderator.dashboard.kpi.inYear', { year: new Date().getFullYear() })}</span>
        </div>
      </section>

      {/* Tender Docs entry banner — placed under the KPIs so it has its own
          breathing room rather than competing with the icon-only header
          buttons. This is the primary entry into the Tender Docs surface. */}
      {onOpenTenderDocs && (
        <button
          type="button"
          className="tenderator-dashboard__tender-docs-banner"
          onClick={onOpenTenderDocs}
        >
          <span className="tenderator-dashboard__tender-docs-banner-icon" aria-hidden="true">
            <span className="mdi mdi-file-document-edit-outline" />
          </span>
          <span className="tenderator-dashboard__tender-docs-banner-body">
            <span className="tenderator-dashboard__tender-docs-banner-title">
              {t('tenderator.dashboard.tenderDocs')}
            </span>
            <span className="tenderator-dashboard__tender-docs-banner-sub">
              {t('tenderator.dashboard.tenderDocsDescription')}
            </span>
          </span>
          <span className="tenderator-dashboard__tender-docs-banner-cta">
            {t('tenderator.dashboard.open')}
            <span className="mdi mdi-arrow-right" aria-hidden="true" />
          </span>
        </button>
      )}

      {/* Chip strip — three labelled groups (View / Sources / Lenses) so the
          11 chips are no longer one undifferentiated row. Lenses + sources
          collapse to the pipeline-only minimum when source='pipeline'. */}
      <div className="tenderator-dashboard__chip-groups">

        {/* GROUP A — Views (what you are looking at) */}
        <section className="tenderator-dashboard__chip-group" aria-label={t('tenderator.dashboard.viewLabel')}>
          <span className="tenderator-dashboard__chip-group-label">{t('tenderator.dashboard.view')}</span>
          <div className="tenderator-dashboard__chip-group-row">
            <button
              type="button"
              className={`tenderator-dashboard__chip ${source === 'all' ? 'tenderator-dashboard__chip--active' : ''}`}
              onClick={() => setSource('all')}
              title={t('tenderator.dashboard.chips.allSources.tooltip')}
            >
              <span className="mdi mdi-view-grid-outline" aria-hidden="true" />
              {t('tenderator.dashboard.chips.allSources.label')}
              {bySource && (
                <span className="tenderator-dashboard__chip-count">
                  {formatNumber((bySource.ted || 0) + (bySource.ft_proposals || 0) + (bySource.ft_tenders || 0) + (bySource.agency || 0))}
                </span>
              )}
            </button>
            <button
              type="button"
              className={`tenderator-dashboard__chip ${source === 'matches' ? 'tenderator-dashboard__chip--active' : ''} tenderator-dashboard__chip--matches`}
              onClick={() => setSource('matches')}
              title={t('tenderator.dashboard.chips.yourMatches.tooltip')}
            >
              <span className="mdi mdi-star-outline" aria-hidden="true" />
              {t('tenderator.dashboard.chips.yourMatches.label')}
              {kpis && <span className="tenderator-dashboard__chip-count">{formatNumber(kpis.your_matches)}</span>}
            </button>
            <button
              type="button"
              className={`tenderator-dashboard__chip ${source === 'pipeline' ? 'tenderator-dashboard__chip--active' : ''} tenderator-dashboard__chip--pipeline`}
              onClick={() => setSource('pipeline')}
              title={t('tenderator.dashboard.chips.myPipeline.tooltip')}
            >
              <span className="mdi mdi-view-column-outline" aria-hidden="true" />
              {t('tenderator.dashboard.chips.myPipeline.label')}
            </button>
          </div>
        </section>

        {/* GROUP B — Sources (which feed, when not in pipeline view) */}
        {source !== 'pipeline' && (
          <section className="tenderator-dashboard__chip-group" aria-label={t('tenderator.dashboard.sourceLabel')}>
            <span className="tenderator-dashboard__chip-group-label">{t('tenderator.dashboard.source')}</span>
            <div className="tenderator-dashboard__chip-group-row">
              <button
                type="button"
                className={`tenderator-dashboard__chip ${source === 'ted' ? 'tenderator-dashboard__chip--active' : ''}`}
                onClick={() => setSource('ted')}
                title={t('tenderator.dashboard.chips.tedTenders.tooltip')}
              >
                <span className="mdi mdi-gavel" aria-hidden="true" />
                {t('tenderator.dashboard.chips.tedTenders.label')}
                {bySource && <span className="tenderator-dashboard__chip-count">{formatNumber(bySource.ted)}</span>}
              </button>
              <button
                type="button"
                className={`tenderator-dashboard__chip ${source === 'ft_proposals' && programmeCode !== 'EIC' ? 'tenderator-dashboard__chip--active' : ''}`}
                onClick={() => { setProgrammeCode(''); setSource('ft_proposals'); }}
                title={t('tenderator.dashboard.chips.callsForProposals.tooltip')}
              >
                <span className="mdi mdi-flask-outline" aria-hidden="true" />
                {t('tenderator.dashboard.chips.callsForProposals.label')}
                {bySource && <span className="tenderator-dashboard__chip-count">{formatNumber(bySource.ft_proposals)}</span>}
              </button>
              <button
                type="button"
                className={`tenderator-dashboard__chip ${source === 'ft_tenders' ? 'tenderator-dashboard__chip--active' : ''}`}
                onClick={() => setSource('ft_tenders')}
                title={t('tenderator.dashboard.chips.callsForTenders.tooltip')}
              >
                <span className="mdi mdi-file-document-outline" aria-hidden="true" />
                {t('tenderator.dashboard.chips.callsForTenders.label')}
                {bySource && <span className="tenderator-dashboard__chip-count">{formatNumber(bySource.ft_tenders)}</span>}
              </button>
              <button
                type="button"
                className={`tenderator-dashboard__chip ${source === 'ft_projects' ? 'tenderator-dashboard__chip--active' : ''}`}
                onClick={() => setSource('ft_projects')}
                title={t('tenderator.dashboard.chips.fundedProjects.tooltip')}
              >
                <span className="mdi mdi-trophy-outline" aria-hidden="true" />
                {t('tenderator.dashboard.chips.fundedProjects.label')}
                {bySource && <span className="tenderator-dashboard__chip-count">{formatNumber(bySource.ft_projects)}</span>}
              </button>
              <button
                type="button"
                className={`tenderator-dashboard__chip ${source === 'agency' ? 'tenderator-dashboard__chip--active' : ''}`}
                onClick={() => { setProgrammeCode(''); setAgencyBody(''); setSource('agency'); }}
                title={t('tenderator.dashboard.chips.agencyProcurement.tooltip')}
              >
                <span className="mdi mdi-office-building-outline" aria-hidden="true" />
                {t('tenderator.dashboard.chips.agencyProcurement.label')}
                {bySource && <span className="tenderator-dashboard__chip-count">{formatNumber(bySource.agency)}</span>}
              </button>
            </div>
          </section>
        )}

        {/* GROUP C — Lenses (refinements that compose with whichever source is active) */}
        {source !== 'pipeline' && (
          <section className="tenderator-dashboard__chip-group" aria-label={t('tenderator.dashboard.lensLabel')}>
            <span className="tenderator-dashboard__chip-group-label">{t('tenderator.dashboard.lens')}</span>
            <div className="tenderator-dashboard__chip-group-row">
              <button
                type="button"
                className={`tenderator-dashboard__chip ${source === 'ft_proposals' && programmeCode === 'EIC' ? 'tenderator-dashboard__chip--active' : ''}`}
                onClick={() => { setAgencyBody(''); setProgrammeCode('EIC'); setSource('ft_proposals'); setLensOverride('all'); }}
                title={t('tenderator.dashboard.chips.eicStartups.tooltip')}
              >
                <span className="mdi mdi-rocket-launch-outline" aria-hidden="true" />
                {t('tenderator.dashboard.chips.eicStartups.label')}
              </button>
              <button
                type="button"
                className={`tenderator-dashboard__chip ${(frameworkOnly && source === 'agency') ? 'tenderator-dashboard__chip--active' : ''} tenderator-dashboard__chip--framework`}
                onClick={() => {
                  const next = !frameworkOnly;
                  setFrameworkOnly(next);
                  if (next) setSource('agency');
                  try { localStorage.setItem('tenderator_framework_only', next ? '1' : '0'); } catch (_) { /* ignore */ }
                }}
                title={t('tenderator.dashboard.chips.frameworkContracts.tooltip')}
              >
                <span className="mdi mdi-file-tree-outline" aria-hidden="true" />
                {t('tenderator.dashboard.chips.frameworkContracts.label')}
              </button>
              <button
                type="button"
                className={`tenderator-dashboard__chip ${externalAction ? 'tenderator-dashboard__chip--active' : ''} tenderator-dashboard__chip--external`}
                onClick={() => {
                  const next = !externalAction;
                  setExternalAction(next);
                  try { localStorage.setItem('tenderator_external_action', next ? '1' : '0'); } catch (_) { /* ignore */ }
                }}
                title={t('tenderator.dashboard.chips.developmentCooperation.tooltip')}
              >
                <span className="mdi mdi-handshake-outline" aria-hidden="true" />
                {t('tenderator.dashboard.chips.developmentCooperation.label')}
              </button>
            </div>
          </section>
        )}
      </div>

      {/* EIC 2026 at-a-glance tile — visible only when the EIC lens is active.
          Static budget data from eic.ec.europa.eu/eic-2026-work-programme_en.
          Total 2026 budget: €1.4B across 5 funding strands + prizes. */}
      {source === 'ft_proposals' && programmeCode === 'EIC' && (
        <section className="tenderator-dashboard__eic-glance" aria-label={t('tenderator.dashboard.eicGlanceLabel')}>
          <div className="tenderator-dashboard__eic-glance-title">
            <span className="mdi mdi-information-outline" aria-hidden="true" />
            {t('tenderator.dashboard.eicGlanceTitle')}
          </div>
          <ul className="tenderator-dashboard__eic-glance-list">
            <li><strong>€634M</strong> {t('tenderator.dashboard.eicAccelerator')}</li>
            <li><strong>€300M</strong> {t('tenderator.dashboard.eicStep')}</li>
            <li><strong>€262M</strong> {t('tenderator.dashboard.eicPathfinder')}</li>
            <li><strong>€100M</strong> {t('tenderator.dashboard.eicTransition')}</li>
            <li><strong>€6M</strong> {t('tenderator.dashboard.eicAdvancedInnovation')}</li>
            <li>+ {t('tenderator.dashboard.eicPrizes')}</li>
          </ul>
        </section>
      )}

      {/* EIC sub-bucket chips — visible only when the EIC lens is active.
          Each chip narrows the feed to one HORIZON-EIC topic family. */}
      {source === 'ft_proposals' && programmeCode === 'EIC' && (
        <section className="tenderator-dashboard__eic-subchips" aria-label={t('tenderator.dashboard.eicSubchipsLabel')}>
          {[
            { slug: '',                    labelKey: 'tenderator.dashboard.eicAllLabel',        titleKey: 'tenderator.dashboard.eicAllTitle' },
            { slug: 'accelerator',         labelKey: 'tenderator.dashboard.eicAcceleratorLabel', titleKey: 'tenderator.dashboard.eicAcceleratorTitle' },
            { slug: 'pathfinder',          labelKey: 'tenderator.dashboard.eicPathfinderLabel',  titleKey: 'tenderator.dashboard.eicPathfinderTitle' },
            { slug: 'transition',          labelKey: 'tenderator.dashboard.eicTransitionLabel',  titleKey: 'tenderator.dashboard.eicTransitionTitle' },
            { slug: 'step-scale',          labelKey: 'tenderator.dashboard.eicStepLabel',        titleKey: 'tenderator.dashboard.eicStepTitle' },
            { slug: 'prize',               labelKey: 'tenderator.dashboard.eicPrizesLabel',      titleKey: 'tenderator.dashboard.eicPrizesTitle' },
          ].map((b) => (
            <button
              key={b.slug || 'all'}
              type="button"
              className={`tenderator-dashboard__chip tenderator-dashboard__chip--eic ${eicBucket === b.slug ? 'tenderator-dashboard__chip--active' : ''}`}
              onClick={() => setEicBucket(b.slug)}
              title={t(b.titleKey)}
            >
              {t(b.labelKey)}
            </button>
          ))}
        </section>
      )}

      {/* External-action sub-control: beneficiary-country narrowing. Visible
          only when the lens is on. Works in combination with chips + search. */}
      {externalAction && source !== 'pipeline' && (
        <section className="tenderator-dashboard__external-controls">
          <label className="tenderator-dashboard__country-label" htmlFor="beneficiary-country">
            <span className="mdi mdi-map-marker-outline" aria-hidden="true" />
            {t('tenderator.dashboard.implementingCountry')}
          </label>
          <input
            id="beneficiary-country"
            list="tenderator-dashboard__country-options"
            type="text"
            className="tenderator-dashboard__country-input"
            value={beneficiaryCountry}
            onChange={(e) => {
              const v = e.target.value;
              setBeneficiaryCountry(v);
              try { localStorage.setItem('tenderator_benef_country', v); } catch (_) { /* ignore */ }
            }}
            placeholder={t('tenderator.dashboard.countryPlaceholder')}
          />
          <datalist id="tenderator-dashboard__country-options">
            <option value="Ukraine" />
            <option value="Morocco" />
            <option value="Türkiye" />
            <option value="Egypt" />
            <option value="Moldova" />
            <option value="Serbia" />
            <option value="North Macedonia" />
            <option value="Albania" />
            <option value="Bosnia and Herzegovina" />
            <option value="Montenegro" />
            <option value="Kosovo" />
            <option value="Georgia" />
            <option value="Armenia" />
            <option value="Tunisia" />
            <option value="Lebanon" />
            <option value="Jordan" />
            <option value="Pakistan" />
            <option value="Bangladesh" />
            <option value="Cambodia" />
            <option value="Vietnam" />
            <option value="Nigeria" />
            <option value="Senegal" />
            <option value="Ethiopia" />
            <option value="Kenya" />
            <option value="Tanzania" />
            <option value="Uganda" />
            <option value="Cameroon" />
            <option value="Colombia" />
            <option value="Peru" />
            <option value="Ecuador" />
            <option value="Brazil" />
            <option value="Mexico" />
          </datalist>
          {beneficiaryCountry && (
            <button
              type="button"
              className="tenderator-dashboard__country-clear"
              onClick={() => {
                setBeneficiaryCountry('');
                try { localStorage.setItem('tenderator_benef_country', ''); } catch (_) { /* ignore */ }
              }}
              aria-label={t('tenderator.dashboard.clearCountry')}
            >
              <span className="mdi mdi-close" aria-hidden="true" />
            </button>
          )}
          {/* Chat narrator deep-link: ask Brubru about external-action market */}
          <a
            className="tenderator-dashboard__ask-brubru"
            href={`/main?q=${encodeURIComponent(
              beneficiaryCountry
                ? t('tenderator.dashboard.askBrubru.specific', { country: beneficiaryCountry })
                : t('tenderator.dashboard.askBrubru.general')
            )}`}
            title={t('tenderator.dashboard.askBrubruAboutMarket')}
          >
            <span className="mdi mdi-message-outline" aria-hidden="true" />
            {t('tenderator.dashboard.askBrubruLabel')}
          </a>
        </section>
      )}

      {/* Error banner */}
      {error && (
        <div className="tenderator-dashboard__error">
          <span className="mdi mdi-alert-circle-outline" aria-hidden="true" />
          {error}
          <button type="button" onClick={() => void fetchStats()}>{t('tenderator.dashboard.retry')}</button>
        </div>
      )}

      {/* Main grid: feed + right rail */}
      <div className="tenderator-dashboard__grid">
        <main className="tenderator-dashboard__main">
          {source === 'matches' && (
            <div className="tenderator-dashboard__sub-chips" role="group" aria-label={t('tenderator.dashboard.filterMatchesBySourceLabel')}>
              <span className="tenderator-dashboard__sub-chips-label">
                <span className="mdi mdi-filter-variant" aria-hidden="true" />
                {t('tenderator.dashboard.matchIn')}
              </span>
              <button
                type="button"
                className={`tenderator-dashboard__sub-chip ${matchSubSource === 'all' ? 'tenderator-dashboard__sub-chip--active' : ''}`}
                onClick={() => setMatchSubSource('all')}
              >
                {t('tenderator.dashboard.all')}
              </button>
              <button
                type="button"
                className={`tenderator-dashboard__sub-chip ${matchSubSource === 'ted' ? 'tenderator-dashboard__sub-chip--active' : ''}`}
                onClick={() => setMatchSubSource('ted')}
              >
                <span className="mdi mdi-gavel" aria-hidden="true" />
                {t('tenderator.dashboard.ted')}
              </button>
              <button
                type="button"
                className={`tenderator-dashboard__sub-chip ${matchSubSource === 'ft_proposals' ? 'tenderator-dashboard__sub-chip--active' : ''}`}
                onClick={() => setMatchSubSource('ft_proposals')}
              >
                <span className="mdi mdi-flask-outline" aria-hidden="true" />
                {t('tenderator.dashboard.callsForProposalsShort')}
              </button>
              <button
                type="button"
                className={`tenderator-dashboard__sub-chip ${matchSubSource === 'ft_tenders' ? 'tenderator-dashboard__sub-chip--active' : ''}`}
                onClick={() => setMatchSubSource('ft_tenders')}
              >
                <span className="mdi mdi-file-document-outline" aria-hidden="true" />
                {t('tenderator.dashboard.callsForTendersShort')}
              </button>
              <button
                type="button"
                className={`tenderator-dashboard__sub-chip ${matchSubSource === 'agency' ? 'tenderator-dashboard__sub-chip--active' : ''}`}
                onClick={() => setMatchSubSource('agency')}
                title={t('tenderator.dashboard.agenciesTitle')}
              >
                <span className="mdi mdi-office-building-outline" aria-hidden="true" />
                {t('tenderator.dashboard.agencies')}
              </button>
            </div>
          )}
          {source === 'pipeline' ? (
            <PipelineView />
          ) : (
            <UnifiedOpportunityFeed
              source={source}
              matchSubSource={matchSubSource}
              programme={source === 'ft_proposals' ? programmeCode : ''}
              eicProgramme={source === 'ft_proposals' && programmeCode === 'EIC' ? eicBucket : ''}
              body={source === 'agency' ? agencyBody : ''}
              externalAction={externalAction}
              beneficiaryCountry={beneficiaryCountry}
              frameworkOnly={frameworkOnly}
              lensModeOverride={lensOverride}
              onLensModeChange={(m) => setLensOverride(m)}
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
          )}
        </main>

        <aside className="tenderator-dashboard__rail">
          {/* Brubru Brief */}
          <div className="tenderator-dashboard__brief">
            <div className="tenderator-dashboard__brief-lede">
              <span className="mdi mdi-bell-ring-outline" aria-hidden="true" />
              {t('tenderator.dashboard.brubruNoticed')}
            </div>
            {kpis && kpis.closing_7d > 0 ? (
              <button
                type="button"
                className="tenderator-dashboard__brief-card"
                onClick={() =>
                  handleAskBrubru(
                    t('tenderator.dashboard.briefQuery', { count: kpis.closing_7d })
                  )
                }
              >
                <span className="tenderator-dashboard__brief-spoken">
                  {kpis.closing_7d === 1
                    ? t('tenderator.dashboard.briefSingle')
                    : t('tenderator.dashboard.briefMultiple', { count: kpis.closing_7d })}
                </span>
                <span className="tenderator-dashboard__brief-cta">
                  {t('tenderator.dashboard.tellMeMore')}
                  <span className="mdi mdi-arrow-right" aria-hidden="true" />
                </span>
              </button>
            ) : (
              <p className="tenderator-dashboard__brief-quiet">
                {t('tenderator.dashboard.nothingUrgent')}
              </p>
            )}
          </div>

          {/* Urgency: closing soon */}
          <div className="tenderator-dashboard__urgency">
            <div className="tenderator-dashboard__urgency-header">
              <span className="mdi mdi-clock-alert-outline" aria-hidden="true" />
              {t('tenderator.dashboard.closingSoon')}
            </div>
            {closingSoon.length === 0 ? (
              <p className="tenderator-dashboard__urgency-empty">
                {t('tenderator.dashboard.noUrgentItems')}
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
                            ? t('tenderator.dashboard.today')
                            : item.days_left === 1
                            ? t('tenderator.dashboard.oneDay')
                            : t('tenderator.dashboard.daysLeft', { count: item.days_left })}
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
                {t('tenderator.dashboard.sourcesBrubruWatches')}
              </div>
              <ul className="tenderator-dashboard__sources-list">
                <li><span>{t('tenderator.dashboard.sources.tedTenders')}</span><span>{formatNumber(bySource.ted)}</span></li>
                <li><span>{t('tenderator.dashboard.sources.ftProposals')}</span><span>{formatNumber(bySource.ft_proposals)}</span></li>
                <li><span>{t('tenderator.dashboard.sources.ftTenders')}</span><span>{formatNumber(bySource.ft_tenders)}</span></li>
                <li><span>{t('tenderator.dashboard.sources.ftProjects')}</span><span>{formatNumber(bySource.ft_projects)}</span></li>
                <li><span>{t('tenderator.dashboard.sources.agencyProcurement')}</span><span>{formatNumber(bySource.agency)}</span></li>
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
