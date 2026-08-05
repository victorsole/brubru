// frontend/src/components/tenders/opportunity_drawer.tsx
//
// Phase 3: side drawer that opens when the user clicks any opportunity in
// the unified feed. Hosts the title + meta, an AI brief button, and a
// similar-projects panel for F&T proposals/projects (degrades gracefully
// for TED + ft_tenders).

import { useEffect, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/use_auth';
import type { UnifiedOpportunity } from './unified_opportunity_feed';
import { ClientScorecardPanel } from './client_scorecard_panel';
import './opportunity_drawer.css';
import { uiDateLocale } from '../../i18n/config';

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

// Move 2: country-anchored FTS summary (drawer "Past EU aid in this country").
interface IntlCoopWinner {
  name: string;
  count: number;
  amount_eur: number;
}
interface IntlCoopRecent {
  id: number;
  beneficiary: string;
  amount_eur: number | null;
  funding_type: string;
  dg: string;
  subject: string | null;
  document_date: string | null;
  source_url: string;
}
interface IntlCoopSummary {
  country: string;
  programme: string | null;
  years_back: number;
  count: number;
  total_amount_eur: number | null;
  avg_amount_eur: number | null;
  top_winners: IntlCoopWinner[];
  recent: IntlCoopRecent[];
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

interface EicGrantee {
  name: string;
  country: string | null;
  country_name: string | null;
  theme_name: string | null;
  description: string | null;
  source_url: string;
}

// Note: SOURCE_LABEL and BRIEF_FIELDS labels are now i18n keys.
// The component reads them using useTranslation() below.
const SOURCE_LABEL_KEYS: Record<UnifiedOpportunity['source'], { labelKey: string; icon: string }> = {
  ted: { labelKey: 'tenderator.opportunityDrawer.sourceLabels.ted', icon: 'mdi-gavel' },
  ft_proposals: { labelKey: 'tenderator.opportunityDrawer.sourceLabels.ftProposals', icon: 'mdi-flask-outline' },
  ft_tenders: { labelKey: 'tenderator.opportunityDrawer.sourceLabels.ftTenders', icon: 'mdi-file-document-outline' },
  ft_projects: { labelKey: 'tenderator.opportunityDrawer.sourceLabels.ftProjects', icon: 'mdi-trophy-outline' },
  agency: { labelKey: 'tenderator.opportunityDrawer.sourceLabels.agency', icon: 'mdi-office-building-outline' },
  intl_coop: { labelKey: 'tenderator.opportunityDrawer.sourceLabels.intlCoop', icon: 'mdi-handshake-outline' },
};

const BRIEF_FIELDS_KEYS: Array<{ key: keyof BriefFields; labelKey: string; icon: string }> = [
  { key: 'scope', labelKey: 'tenderator.opportunityDrawer.briefFields.scope', icon: 'mdi-target' },
  { key: 'eligible_applicants', labelKey: 'tenderator.opportunityDrawer.briefFields.eligibleApplicants', icon: 'mdi-account-group-outline' },
  { key: 'budget_per_project', labelKey: 'tenderator.opportunityDrawer.briefFields.budgetPerProject', icon: 'mdi-currency-eur' },
  { key: 'trl_range', labelKey: 'tenderator.opportunityDrawer.briefFields.trlRange', icon: 'mdi-chart-bell-curve' },
  { key: 'key_dates', labelKey: 'tenderator.opportunityDrawer.briefFields.keyDates', icon: 'mdi-calendar-clock' },
  { key: 'evaluation_criteria', labelKey: 'tenderator.opportunityDrawer.briefFields.evaluationCriteria', icon: 'mdi-scale-balance' },
  { key: 'first_steps', labelKey: 'tenderator.opportunityDrawer.briefFields.firstSteps', icon: 'mdi-rocket-launch-outline' },
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
    return new Date(iso).toLocaleDateString(uiDateLocale(), { day: '2-digit', month: 'short', year: 'numeric' });
  } catch {
    return iso;
  }
};

export const OpportunityDrawer = ({ opportunity, onClose }: OpportunityDrawerProps) => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const navigate = useNavigate();
  const [brief, setBrief] = useState<BriefResponse | null>(null);
  const [briefLoading, setBriefLoading] = useState(false);
  const [briefError, setBriefError] = useState<string | null>(null);
  const [similar, setSimilar] = useState<SimilarResponse | null>(null);
  const [similarLoading, setSimilarLoading] = useState(false);
  const [recipients, setRecipients] = useState<FtsRecipientsResponse | null>(null);
  const [recipientsLoading, setRecipientsLoading] = useState(false);
  const [intlSummary, setIntlSummary] = useState<IntlCoopSummary | null>(null);
  const [intlSummaryLoading, setIntlSummaryLoading] = useState(false);
  // EIC Fund investees (Move 4 of #5, 15 Jun 2026). Surfaces 5 EIC Fund
  // portfolio companies when the opportunity is an EIC call — concrete
  // social proof on calls that otherwise have 0 ft_funded_projects.
  const [eicGrantees, setEicGrantees] = useState<EicGrantee[] | null>(null);
  const [eicGranteesLoading, setEicGranteesLoading] = useState(false);
  // Move 4: pipeline add state. Tracks whether THIS opportunity is already
  // in the user's pipeline (we don't fetch the entire pipeline; the POST is
  // idempotent so re-adding is a no-op refresh of the snapshot).
  const [addingToPipeline, setAddingToPipeline] = useState(false);
  const [pipelineAdded, setPipelineAdded] = useState(false);

  // Reset state when opportunity changes
  useEffect(() => {
    setBrief(null);
    setBriefError(null);
    setSimilar(null);
    setRecipients(null);
    setEicGrantees(null);
  }, [opportunity?.id]);

  // Detect EIC opportunities by topic_id prefix. The opportunity's id is
  // formatted "<source>:<pk>" so we check the external_id (the raw topic_id).
  const isEicOpportunity = (() => {
    const t = (opportunity?.external_id || '').toUpperCase();
    const title = (opportunity?.title || '').toUpperCase();
    if (t.startsWith('HORIZON-EIC')) return true;
    if (t.startsWith('HORIZON-WIDERA') && t.includes('ACCESS') && title.includes('EIC')) return true;
    return false;
  })();

  // Classify the EIC opportunity into its sub-bucket so the grantees endpoint
  // can theme-narrow (only STEP-scale gets narrowed today — see backend
  // _EIC_BUCKET_TO_THEMES). Everything else returns any-sector samples.
  const eicBucket = (() => {
    const t = (opportunity?.external_id || '').toUpperCase();
    if (t.includes('-ACCELERATOR')) return 'accelerator';
    if (t.includes('-PATHFINDER'))  return 'pathfinder';
    if (t.includes('-TRANSITION')) return 'transition';
    if (t.includes('-STEP') || t.includes('-SCALEUP')) return 'step-scale';
    if (t.includes('-AIC-'))       return 'advanced-challenges';
    if (t.includes('-PRIZE-'))     return 'prize';
    if (t.includes('-BAS-') || t.includes('-TALENTS') || t.includes('-WOMENTECH')) return 'business-services';
    if (t.startsWith('HORIZON-WIDERA')) return 'pre-accelerator';
    return '';
  })();

  // Auto-fetch EIC Fund grantees for EIC opportunities
  const fetchEicGrantees = useCallback(async () => {
    if (!opportunity || !token || !isEicOpportunity) return;
    setEicGranteesLoading(true);
    try {
      const params = new URLSearchParams({ limit: '5' });
      if (eicBucket) params.set('bucket', eicBucket);
      const res = await fetch(`${API_URL}/api/tenders/eic-fund-grantees?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setEicGrantees(data.items || []);
      }
    } catch (e) {
      console.error('eic-fund-grantees fetch failed:', e);
    } finally {
      setEicGranteesLoading(false);
    }
  }, [opportunity, token, isEicOpportunity, eicBucket]);

  useEffect(() => {
    fetchEicGrantees();
  }, [fetchEicGrantees]);

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

  // Move 2: "Won this before" — country-anchored FTS summary. Fires when the
  // opportunity carries a country (intl_coop rows always do; ft_projects do;
  // others rarely). Detects programme from intl_coop's programme tag.
  const fetchIntlSummary = useCallback(async () => {
    setIntlSummary(null);
    if (!opportunity || !token) return;
    const country = opportunity.country;
    if (!country || country.length < 2) return;
    setIntlSummaryLoading(true);
    try {
      const params = new URLSearchParams({ country, years_back: '5' });
      // Map short programme tags from intl_coop serialiser to summary keys.
      const prog = (opportunity.programme || '').toLowerCase();
      if (prog.includes('ndici')) params.set('programme', 'ndici');
      else if (prog.includes('ipa')) params.set('programme', 'ipa3');
      else if (prog.includes('humanitarian')) params.set('programme', 'humanitarian');
      const res = await fetch(`${API_URL}/api/tenders/intl-coop-summary?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setIntlSummary(data);
      }
    } catch (e) {
      console.error('intl-coop-summary fetch failed:', e);
    } finally {
      setIntlSummaryLoading(false);
    }
  }, [opportunity, token]);

  useEffect(() => {
    void fetchIntlSummary();
  }, [fetchIntlSummary]);

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
        const err = await res.json().catch(() => ({ detail: t('tenderator.opportunityDrawer.errors.briefGenerationFailed') }));
        setBriefError(err.detail || t('tenderator.opportunityDrawer.errors.briefGenerationFailed'));
        return;
      }
      const data = await res.json();
      setBrief(data);
    } catch (e) {
      console.error('brief fetch failed:', e);
      setBriefError(t('tenderator.opportunityDrawer.errors.briefGenerationFailed'));
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

  const handleAddToPipeline = async () => {
    if (!token || !opportunity) return;
    setAddingToPipeline(true);
    try {
      const res = await fetch(`${API_URL}/api/tenders/pipeline`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          opportunity_id: opportunity.id,
          source: opportunity.source,
          title: opportunity.title,
          organisation: opportunity.organisation,
          country: opportunity.country,
          programme: opportunity.programme,
          deadline: opportunity.deadline,
          budget: opportunity.budget,
          currency: opportunity.currency,
          source_url: opportunity.source_url,
          status: 'lead',
        }),
      });
      if (res.ok) setPipelineAdded(true);
    } catch (e) {
      console.error('add-to-pipeline failed:', e);
    } finally {
      setAddingToPipeline(false);
    }
  };

  const tagKey = SOURCE_LABEL_KEYS[opportunity.source];
  const tag = { label: t(tagKey.labelKey), icon: tagKey.icon };

  return createPortal(
    <div
      className="opportunity-drawer__overlay"
      role="dialog"
      aria-modal="true"
      aria-label={t('tenderator.opportunityDrawer.ariaLabel.opportunityDetails', { title: opportunity.title })}
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
          {opportunity.translated_from && (
            <span
              className="opportunity-drawer__lang-badge"
              title={t('tenderator.opportunityDrawer.translationNotice', { language: opportunity.translated_from })}
            >
              <span className="mdi mdi-translate" aria-hidden="true" />
              {t('tenderator.opportunityDrawer.translatedFrom', { language: opportunity.translated_from })}
            </span>
          )}
          <button
            type="button"
            className="opportunity-drawer__close"
            onClick={onClose}
            aria-label={t('tenderator.opportunityDrawer.closeDrawer')}
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
                <dt>{t('tenderator.opportunityDrawer.metaLabels.reference')}</dt>
                <dd className="opportunity-drawer__meta-mono">{opportunity.external_id}</dd>
              </div>
            )}
            {opportunity.programme && (
              <div>
                <dt>{t('tenderator.opportunityDrawer.metaLabels.programme')}</dt>
                <dd>{opportunity.programme}</dd>
              </div>
            )}
            {opportunity.organisation && (
              <div>
                <dt>
                  {opportunity.source === 'ft_projects'
                    ? t('tenderator.opportunityDrawer.metaLabels.coordinator')
                    : opportunity.source === 'agency'
                    ? t('tenderator.opportunityDrawer.metaLabels.agency')
                    : t('tenderator.opportunityDrawer.metaLabels.organisation')}
                </dt>
                <dd>{opportunity.organisation}</dd>
              </div>
            )}
            {opportunity.country && (
              <div>
                <dt>{t('tenderator.opportunityDrawer.metaLabels.country')}</dt>
                <dd>{opportunity.country}</dd>
              </div>
            )}
            {opportunity.budget && (
              <div>
                <dt>{opportunity.source === 'ft_projects' ? t('tenderator.opportunityDrawer.metaLabels.euContribution') : t('tenderator.opportunityDrawer.metaLabels.budget')}</dt>
                <dd>{formatValue(opportunity.budget, opportunity.currency)}</dd>
              </div>
            )}
            {opportunity.deadline && (
              <div>
                <dt>{opportunity.source === 'ft_projects' ? t('tenderator.opportunityDrawer.metaLabels.endDate') : t('tenderator.opportunityDrawer.metaLabels.deadline')}</dt>
                <dd>{formatDate(opportunity.deadline)}</dd>
              </div>
            )}
            {opportunity.published_at && (
              <div>
                <dt>{opportunity.source === 'ft_projects' ? t('tenderator.opportunityDrawer.metaLabels.startDate') : t('tenderator.opportunityDrawer.metaLabels.published')}</dt>
                <dd>{formatDate(opportunity.published_at)}</dd>
              </div>
            )}
            {opportunity.status && (
              <div>
                <dt>{t('tenderator.opportunityDrawer.metaLabels.status')}</dt>
                <dd>{opportunity.status}</dd>
              </div>
            )}
          </dl>

          {opportunity.description && (
            <section className="opportunity-drawer__section">
              <h3>
                <span className="mdi mdi-text-box-outline" aria-hidden="true" />
                {t('tenderator.opportunityDrawer.sections.description')}
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

          {/* AI Brief — only for sources the /brief endpoint can resolve.
              agency + intl_coop are not in the brief resolver; clicking the
              CTA would 400. Hide the whole section instead of showing a
              broken CTA. Fix for audit finding #2 (15 Jun 2026). */}
          {(['ted','ft_proposals','ft_tenders','ft_projects'] as const).includes(opportunity.source as any) && (
          <section className="opportunity-drawer__section">
            <h3>
              <span className="mdi mdi-robot-outline" aria-hidden="true" />
              {t('tenderator.opportunityDrawer.sections.brubruBrief')}
            </h3>
            {!brief && !briefLoading && (
              <button
                type="button"
                className="opportunity-drawer__brief-cta"
                onClick={handleGenerateBrief}
              >
                <span className="mdi mdi-flash-outline" aria-hidden="true" />
                {t('tenderator.opportunityDrawer.actions.generateBrief')}
              </button>
            )}
            {briefLoading && (
              <div className="opportunity-drawer__brief-loading">
                <span className="mdi mdi-loading mdi-spin" aria-hidden="true" />
                {t('tenderator.opportunityDrawer.states.readingCall')}
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
                {BRIEF_FIELDS_KEYS.map((f) => (
                  <div key={f.key} className="opportunity-drawer__brief-field">
                    <dt>
                      <span className={`mdi ${f.icon}`} aria-hidden="true" />
                      {t(f.labelKey)}
                    </dt>
                    <dd>{brief.brief[f.key]}</dd>
                  </div>
                ))}
              </dl>
            )}
          </section>
          )}

          {/* Similar projects — only for F&T sources. For intl_coop the
              equivalent intel (past grantees in this country) lives in
              the Move-2 "Past EU aid in this country" panel above, so
              we don't double-render. Agency + TED don't have a
              ft_funded_projects link. */}
          {(opportunity.source === 'ft_proposals' || opportunity.source === 'ft_projects') && (
            <section className="opportunity-drawer__section">
              <h3>
                <span className="mdi mdi-account-network-outline" aria-hidden="true" />
                {t('tenderator.opportunityDrawer.sections.pastGrantees')}
              </h3>
              {similarLoading && (
                <div className="opportunity-drawer__similar-loading">
                  <span className="mdi mdi-loading mdi-spin" aria-hidden="true" />
                  {t('tenderator.opportunityDrawer.states.searchingCordis')}
                </div>
              )}
              {!similarLoading && similar && similar.items.length === 0 && (
                <p className="opportunity-drawer__similar-empty">
                  {similar.note || t('tenderator.opportunityDrawer.states.noMatchingProjects')}
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

          {/* Move 4 of #5 (15 Jun 2026): EIC Fund invested companies. Shown
              only for EIC opportunities (HORIZON-EIC-* and EIC-pre-accelerator
              under HORIZON-WIDERA). Pulls 5 randomly-sampled companies from
              the 255-row scraped portfolio. STEP-Scale narrows to
              strategic-tech themes; other buckets are any-sector. */}
          {isEicOpportunity && (eicGranteesLoading || (eicGrantees && eicGrantees.length > 0)) && (
            <section className="opportunity-drawer__section opportunity-drawer__section--eic-fund">
              <h3>
                <span className="mdi mdi-rocket-launch-outline" aria-hidden="true" />
                {t('tenderator.opportunityDrawer.sections.eicFundPortfolio')}
              </h3>
              {eicGranteesLoading && (
                <div className="opportunity-drawer__similar-loading">
                  <span className="mdi mdi-loading mdi-spin" aria-hidden="true" />
                  {t('tenderator.opportunityDrawer.states.samplingEicFund')}
                </div>
              )}
              {!eicGranteesLoading && eicGrantees && eicGrantees.length > 0 && (
                <>
                  <p className="opportunity-drawer__eic-fund-intro">
                    {t('tenderator.opportunityDrawer.text.eicFundIntro')}
                  </p>
                  <ul className="opportunity-drawer__eic-fund-list">
                    {eicGrantees.map((g, i) => (
                      <li key={`${g.name}-${i}`} className="opportunity-drawer__eic-fund-item">
                        <a
                          href={g.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="opportunity-drawer__eic-fund-name"
                        >
                          {g.name}
                        </a>
                        <div className="opportunity-drawer__eic-fund-meta">
                          {g.country_name && <span>{g.country_name}</span>}
                          {g.theme_name && <span>{g.theme_name}</span>}
                        </div>
                        {g.description && (
                          <p className="opportunity-drawer__eic-fund-desc">{g.description}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </section>
          )}

          {/* Move 2 (15 Jun 2026): "Past EU aid in this country" — anchored
              on the opportunity.country, aggregated across NDICI/IPA III/HUMA
              (or just one when the opportunity is itself an intl_coop row).
              Surfaces the top 5 winners + the 5 most recent awards + total
              and average commitment so the user has competitive context at
              a glance. Hides cleanly when no country / no matches. */}
          {(intlSummaryLoading || (intlSummary && intlSummary.count > 0)) && (
            <section className="opportunity-drawer__section">
              <h3>
                <span className="mdi mdi-earth" aria-hidden="true" />
                {t('tenderator.opportunityDrawer.sections.pastEuAid', { country: intlSummary?.country || opportunity.country })}
                {intlSummary?.programme && (
                  <span className="opportunity-drawer__intl-prog-tag">
                    {intlSummary.programme === 'ndici' ? 'NDICI'
                      : intlSummary.programme === 'ipa3' ? 'IPA III'
                      : intlSummary.programme === 'humanitarian' ? t('tenderator.opportunityDrawer.programmeLabels.humanitarian')
                      : intlSummary.programme}
                  </span>
                )}
              </h3>
              {intlSummaryLoading && (
                <div className="opportunity-drawer__similar-loading">
                  <span className="mdi mdi-loading mdi-spin" aria-hidden="true" />
                  {t('tenderator.opportunityDrawer.states.checkingFinancialTransparency')}
                </div>
              )}
              {!intlSummaryLoading && intlSummary && intlSummary.count > 0 && (
                <>
                  <div className="opportunity-drawer__intl-stats">
                    <div className="opportunity-drawer__intl-stat">
                      <span className="opportunity-drawer__intl-stat-value">{intlSummary.count}</span>
                      <span className="opportunity-drawer__intl-stat-label">{t('tenderator.opportunityDrawer.stats.pastAwards', { years: intlSummary.years_back })}</span>
                    </div>
                    {intlSummary.total_amount_eur ? (
                      <div className="opportunity-drawer__intl-stat">
                        <span className="opportunity-drawer__intl-stat-value">
                          €{(intlSummary.total_amount_eur / 1e6).toFixed(1)}M
                        </span>
                        <span className="opportunity-drawer__intl-stat-label">{t('tenderator.opportunityDrawer.stats.totalEuCommitment')}</span>
                      </div>
                    ) : null}
                    {intlSummary.avg_amount_eur ? (
                      <div className="opportunity-drawer__intl-stat">
                        <span className="opportunity-drawer__intl-stat-value">
                          €{intlSummary.avg_amount_eur >= 1e6
                            ? `${(intlSummary.avg_amount_eur / 1e6).toFixed(1)}M`
                            : `${Math.round(intlSummary.avg_amount_eur / 1e3)}k`}
                        </span>
                        <span className="opportunity-drawer__intl-stat-label">{t('tenderator.opportunityDrawer.stats.average')}</span>
                      </div>
                    ) : null}
                  </div>

                  {intlSummary.top_winners.length > 0 && (
                    <div className="opportunity-drawer__intl-winners">
                      <h4 className="opportunity-drawer__intl-subheading">{t('tenderator.opportunityDrawer.sections.topWinners')}</h4>
                      <ul className="opportunity-drawer__intl-winner-list">
                        {intlSummary.top_winners.map((w) => (
                          <li key={w.name} className="opportunity-drawer__intl-winner">
                            <a
                              className="opportunity-drawer__intl-winner-name"
                              href={`/main?q=${encodeURIComponent(
                                t('tenderator.opportunityDrawer.queries.askAboutOrganisation', { name: w.name })
                              )}`}
                              title={t('tenderator.opportunityDrawer.titles.askAboutOrganisation')}
                            >
                              {w.name}
                            </a>
                            <span className="opportunity-drawer__intl-winner-meta">
                              {w.count}× · €{w.amount_eur >= 1e6
                                ? `${(w.amount_eur / 1e6).toFixed(1)}M`
                                : `${Math.round(w.amount_eur / 1e3)}k`}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {intlSummary.recent.length > 0 && (
                    <div className="opportunity-drawer__intl-recent">
                      <h4 className="opportunity-drawer__intl-subheading">{t('tenderator.opportunityDrawer.sections.recentAwards')}</h4>
                      <ul className="opportunity-drawer__intl-recent-list">
                        {intlSummary.recent.map((r) => (
                          <li key={r.id} className="opportunity-drawer__intl-recent-item">
                            <a
                              href={r.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="opportunity-drawer__intl-recent-title"
                            >
                              {r.subject || r.beneficiary}
                            </a>
                            <div className="opportunity-drawer__intl-recent-meta">
                              {r.beneficiary && <span>{r.beneficiary}</span>}
                              {r.amount_eur ? (
                                <span>· €{r.amount_eur >= 1e6
                                  ? `${(r.amount_eur / 1e6).toFixed(1)}M`
                                  : `${Math.round(r.amount_eur / 1e3)}k`}</span>
                              ) : null}
                              {r.funding_type && <span>· {r.funding_type}</span>}
                              {r.document_date && (
                                <span>· {new Date(r.document_date).getFullYear()}</span>
                              )}
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
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
                {t('tenderator.opportunityDrawer.sections.winnersPastEuMoney')}
              </h3>
              {recipientsLoading && (
                <div className="opportunity-drawer__similar-loading">
                  <span className="mdi mdi-loading mdi-spin" aria-hidden="true" />
                  {t('tenderator.opportunityDrawer.states.checkingFinancialTransparencyRecipients')}
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
            {t('tenderator.opportunityDrawer.actions.discussWithBrubru')}
          </button>
          <button
            type="button"
            className={`opportunity-drawer__action opportunity-drawer__action--pipeline ${pipelineAdded ? 'opportunity-drawer__action--added' : ''}`}
            onClick={handleAddToPipeline}
            disabled={addingToPipeline || pipelineAdded}
            title={pipelineAdded ? t('tenderator.opportunityDrawer.titles.alreadyInPipeline') : t('tenderator.opportunityDrawer.titles.trackOpportunity')}
          >
            <span className={`mdi ${pipelineAdded ? 'mdi-check' : addingToPipeline ? 'mdi-loading mdi-spin' : 'mdi-clipboard-plus-outline'}`} aria-hidden="true" />
            {pipelineAdded ? t('tenderator.opportunityDrawer.actions.addedToPipeline') : addingToPipeline ? t('tenderator.opportunityDrawer.states.adding') : t('tenderator.opportunityDrawer.actions.addToPipeline')}
          </button>
          {opportunity.source_url && (
            <a
              href={opportunity.source_url}
              target="_blank"
              rel="noreferrer"
              className="opportunity-drawer__action opportunity-drawer__action--primary"
            >
              <span className="mdi mdi-open-in-new" aria-hidden="true" />
              {t('tenderator.opportunityDrawer.actions.openOriginal')}
            </a>
          )}
        </footer>
      </div>
    </div>,
    document.body,
  );
};
