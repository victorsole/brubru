// frontend/src/components/tenders/unified_opportunity_feed.tsx
//
// Phase 2: a single feed component that renders any combination of the
// 4 Tenderator sources (TED tenders, F&T calls for proposals, F&T calls
// for tenders, F&T funded projects) behind one shape. The dashboard's
// source-filter chip switches the `source` prop.

import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/use_auth';
import { LensToggle, type LensMode } from '../bubble/lens_toggle';
import './unified_opportunity_feed.css';
import type { SourceFilter } from './tenderator_dashboard';
import { uiDateLocale } from '../../i18n/config';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface UnifiedOpportunity {
  id: string;
  source: 'ted' | 'ft_proposals' | 'ft_tenders' | 'ft_projects' | 'agency' | 'intl_coop';
  external_id: string;
  title: string;
  description: string | null;
  status: string | null;
  deadline: string | null;
  budget: number | null;
  currency: string;
  source_url: string;
  organisation: string | null;
  country: string | null;
  programme: string | null;
  published_at: string | null;
  // Translation overlay (MEUB-news pattern): source language Brubru detected,
  // and — when title/description were served from a translations sidecar —
  // the source language they were translated FROM.
  detected_lang?: string | null;
  translated_from?: string;
  // Only present when the feed was requested with source='matches':
  match_score?: number | null;
  match_id?: number;
  is_saved?: boolean;
  is_applied?: boolean;
  // Only present when source=='intl_coop' (FTS award):
  funding_type?: string | null;
  dg?: string | null;
}

export type MatchSubSource = 'all' | 'ted' | 'ft_proposals' | 'ft_tenders' | 'agency';

interface UnifiedFeedProps {
  source: SourceFilter;
  matchSubSource?: MatchSubSource;
  initialQuery?: string;
  programme?: string;
  // EIC sub-bucket slug (Move 2 of #5): accelerator | pathfinder | transition
  // | step-scale | prize | … Empty string = no narrowing (all EIC).
  eicProgramme?: string;
  // When source=='agency': scope the feed to one body_code (e.g. 'efsa').
  body?: string;
  // External-action lens (Move 1, 15 Jun 2026): narrow every source to EU
  // dev-cooperation contracts; unlocks the FTS-awards 'intl_coop' source.
  externalAction?: boolean;
  // Free-text country narrowing — works with or without the lens.
  beneficiaryCountry?: string;
  // Move 5: narrows source=agency to item_type='framework' (EU-institution FWCs).
  frameworkOnly?: boolean;
  // Controlled lens override. When provided, the feed uses this lens mode
  // instead of its own localStorage state. The dashboard sets this to 'all'
  // when a user clicks an explicit-intent chip (e.g. "Startups & SMEs (EIC)")
  // so an empty Policy-Interest intersection doesn't hide the requested rows.
  lensModeOverride?: LensMode | null;
  onLensModeChange?: (m: LensMode) => void;
  onSelectOpportunity?: (opp: UnifiedOpportunity) => void;
}

const getSourceLabels = (t: any): Record<UnifiedOpportunity['source'], { label: string; icon: string; colour: string; hint: string }> => ({
  ted: {
    label: t('tenderator.unifiedFeed.sourceLabels.ted.label'), icon: 'mdi-gavel', colour: 'tenderator-feed__source--ted',
    hint: t('tenderator.unifiedFeed.sourceLabels.ted.hint')
  },
  ft_proposals: {
    label: t('tenderator.unifiedFeed.sourceLabels.ftProposals.label'), icon: 'mdi-flask-outline', colour: 'tenderator-feed__source--proposals',
    hint: t('tenderator.unifiedFeed.sourceLabels.ftProposals.hint')
  },
  ft_tenders: {
    label: t('tenderator.unifiedFeed.sourceLabels.ftTenders.label'), icon: 'mdi-file-document-outline', colour: 'tenderator-feed__source--tenders',
    hint: t('tenderator.unifiedFeed.sourceLabels.ftTenders.hint')
  },
  ft_projects: {
    label: t('tenderator.unifiedFeed.sourceLabels.ftProjects.label'), icon: 'mdi-trophy-outline', colour: 'tenderator-feed__source--projects',
    hint: t('tenderator.unifiedFeed.sourceLabels.ftProjects.hint')
  },
  agency: {
    label: t('tenderator.unifiedFeed.sourceLabels.agency.label'), icon: 'mdi-office-building-outline', colour: 'tenderator-feed__source--agency',
    hint: t('tenderator.unifiedFeed.sourceLabels.agency.hint')
  },
  intl_coop: {
    label: t('tenderator.unifiedFeed.sourceLabels.intlCoop.label'), icon: 'mdi-handshake-outline', colour: 'tenderator-feed__source--intl',
    hint: t('tenderator.unifiedFeed.sourceLabels.intlCoop.hint')
  },
});

const formatValue = (value: number | null, currency: string = 'EUR'): string | null => {
  if (!value) return null;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M ${currency}`;
  if (value >= 1_000) return `${Math.round(value / 1_000)}k ${currency}`;
  return `${value} ${currency}`;
};

const daysUntil = (iso: string | null): number | null => {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  return Math.round(ms / (24 * 60 * 60 * 1000));
};

const formatDeadline = (iso: string | null, t: any): string => {
  if (!iso) return t('tenderator.unifiedFeed.deadlineNoDeadline');
  const days = daysUntil(iso);
  if (days === null) return t('tenderator.unifiedFeed.deadlineNoDeadline');
  if (days < 0) return t('tenderator.unifiedFeed.deadlineClosed');
  if (days === 0) return t('tenderator.unifiedFeed.deadlineToday');
  if (days === 1) return t('tenderator.unifiedFeed.deadlineOneDay');
  if (days <= 30) return t('tenderator.unifiedFeed.deadlineDays', { days });
  return new Date(iso).toLocaleDateString(uiDateLocale(), { day: '2-digit', month: 'short', year: 'numeric' });
};

export const UnifiedOpportunityFeed = ({ source, matchSubSource = 'all', initialQuery = '', programme = '', eicProgramme = '', body = '', externalAction = false, beneficiaryCountry = '', frameworkOnly = false, lensModeOverride = null, onLensModeChange, onSelectOpportunity }: UnifiedFeedProps) => {
  const { token } = useAuth();
  const { t, i18n } = useTranslation();
  // Brubru's 6 — falls back to 'en' for any other UI locale.
  const _BRUBRU_LANGS = ['en', 'es', 'ca', 'fr', 'it', 'nl'];
  const uiLang = (i18n.language || 'en').slice(0, 2).toLowerCase();
  const feedLang = _BRUBRU_LANGS.includes(uiLang) ? uiLang : 'en';
  const [items, setItems] = useState<UnifiedOpportunity[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState(initialQuery);
  const [pendingQuery, setPendingQuery] = useState(initialQuery);
  const [page, setPage] = useState(1);
  const [clientFilter, setClientFilter] = useState<boolean>(() => {
    try { return localStorage.getItem('tenderator_client_filter') === '1'; } catch { return false; }
  });
  const [clientFilterApplied, setClientFilterApplied] = useState<boolean>(false);
  const [clientFilterSlug, setClientFilterSlug] = useState<string | null>(null);
  // Layer 1: MEUB Policy-Interest personalisation lens. Mirrors the shared
  // bubble <LensToggle> pattern (News/Votes/OJ/PQ). 'all' = unfiltered feed,
  // 'pi' = narrow by user.policy_interests via the crosswalk. 'files' (hard
  // lens via tracked carriages) is not wired on Tenderator yet, so hasFiles
  // is false and the segment hides. Backend default is personalised=true, so
  // we only send the param when mode='all'.
  const [internalMode, setInternalMode] = useState<LensMode>(() => {
    try {
      const v = localStorage.getItem('tenderator_lens_mode');
      return v === 'all' ? 'all' : 'pi';
    } catch { return 'pi'; }
  });
  // When the dashboard supplies lensModeOverride (e.g. user clicked an
  // explicit-intent chip like "Startups & SMEs (EIC)"), that value wins over
  // the feed's own state — so a stale personalised lens can't hide the rows
  // the user just asked for.
  const mode: LensMode = lensModeOverride ?? internalMode;
  const personalised = mode === 'pi';
  const setLensMode = (m: LensMode) => {
    setInternalMode(m);
    try { localStorage.setItem('tenderator_lens_mode', m); } catch (_) { /* ignore */ }
    onLensModeChange?.(m);
  };
  const [personalisedApplied, setPersonalisedApplied] = useState<boolean>(false);
  const [interests, setInterests] = useState<string[]>([]);
  const sourceLabels = getSourceLabels(t);

  // If the URL ?q= changes (deep-link from Chat), pick it up.
  useEffect(() => {
    if (initialQuery && initialQuery !== searchQuery) {
      setSearchQuery(initialQuery);
      setPendingQuery(initialQuery);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery]);

  const fetchFeed = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        source,
        limit: '20',
        page: String(page),
      });
      if (source === 'matches' && matchSubSource && matchSubSource !== 'all') {
        params.set('match_source', matchSubSource);
      }
      if (searchQuery.trim()) params.set('q', searchQuery.trim());
      if (programme) params.set('programme', programme);
      if (eicProgramme) params.set('eic_programme', eicProgramme);
      if (body && source === 'agency') params.set('body', body);
      params.set('lang', feedLang);
      if (clientFilter) params.set('client_filter', 'true');
      // Only send when OFF — backend default is true.
      if (!personalised) params.set('personalised', 'false');
      if (externalAction) params.set('external_action', 'true');
      if (beneficiaryCountry) params.set('beneficiary_country', beneficiaryCountry);
      if (frameworkOnly) params.set('framework_only', 'true');
      const res = await fetch(`${API_URL}/api/tenders/unified-feed?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: t('tenderator.unifiedFeed.errorFeedQuery') }));
        setError(detail.detail || t('tenderator.unifiedFeed.errorFeedQuery'));
        setItems([]);
        return;
      }
      const data = await res.json();
      setItems(data.items || []);
      setClientFilterApplied(Boolean(data.client_filter_applied));
      setClientFilterSlug(data.client_filter_slug || null);
      setPersonalisedApplied(Boolean(data.personalised_applied));
      setInterests(Array.isArray(data.interests) ? data.interests : []);
    } catch (e) {
      console.error('unified-feed fetch failed:', e);
      setError(t('tenderator.unifiedFeed.errorLoadFailed'));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [token, source, matchSubSource, page, searchQuery, programme, eicProgramme, body, feedLang, clientFilter, personalised, externalAction, beneficiaryCountry, frameworkOnly]);

  useEffect(() => {
    setPage(1);
  }, [source]);

  useEffect(() => {
    void fetchFeed();
  }, [fetchFeed]);

  return (
    <div className="tenderator-feed">
      {/* Search bar */}
      <div className="tenderator-feed__search">
        <span className="mdi mdi-magnify" aria-hidden="true" />
        <input
          type="text"
          className="tenderator-feed__search-input"
          placeholder={t('tenderator.unifiedFeed.searchPlaceholder')}
          value={pendingQuery}
          onChange={(e) => setPendingQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              setSearchQuery(pendingQuery);
            }
          }}
        />
        {pendingQuery && (
          <button
            type="button"
            className="tenderator-feed__search-clear"
            onClick={() => {
              setPendingQuery('');
              setSearchQuery('');
            }}
            aria-label={t('tenderator.unifiedFeed.searchClear')}
          >
            <span className="mdi mdi-close" aria-hidden="true" />
          </button>
        )}
      </div>

      {/* Personalisation lens (Layer 1) — shared <LensToggle> mirroring the
          News/Votes/OJ/PQ pattern. "My files" hidden (no tracked-files hard
          lens on Tenderator yet). When the user has no interests, the
          component renders null and we surface a hint instead. */}
      {personalisedApplied ? (
        <div className="tenderator-feed__lens">
          <LensToggle
            mode={mode}
            onChange={setLensMode}
            hasPi={true}
            hasFiles={false}
          />
          {mode === 'pi' && interests.length > 0 && (
            <span
              className="tenderator-feed__lens-meta"
              title={`${t('tenderator.unifiedFeed.interests')}: ${interests.join(', ')}`}
            >
              {t('tenderator.unifiedFeed.interestCount', { count: interests.length })}
            </span>
          )}
        </div>
      ) : (
        personalised && (
          <div className="tenderator-feed__lens tenderator-feed__lens--empty">
            <span className="mdi mdi-information-outline" aria-hidden="true" />
            {t('tenderator.unifiedFeed.noInterestsSet')} <a href="/my-eu-bubble?tab=policy-interests">{t('tenderator.unifiedFeed.addInterestsCTA')}</a>.
          </div>
        )
      )}

      {/* Client-pursuits filter toggle (Layer 2) — only useful for users
          with a configured private guide; harmless if no filter is set. */}
      <div className="tenderator-feed__client-filter">
        <label className="tenderator-feed__client-filter-toggle">
          <input
            type="checkbox"
            checked={clientFilter}
            onChange={(e) => {
              const v = e.target.checked;
              setClientFilter(v);
              try { localStorage.setItem('tenderator_client_filter', v ? '1' : '0'); } catch (_) { /* ignore */ }
            }}
          />
          <span>{t('tenderator.unifiedFeed.filterToPursuits')}</span>
        </label>
        {clientFilter && clientFilterApplied && clientFilterSlug && (
          <span className="tenderator-feed__client-filter-badge">
            <span className="mdi mdi-filter-check-outline" aria-hidden="true" />
            {t('tenderator.unifiedFeed.filteredTo', { slug: clientFilterSlug })}
          </span>
        )}
        {clientFilter && !clientFilterApplied && (
          <span className="tenderator-feed__client-filter-badge tenderator-feed__client-filter-badge--inactive">
            <span className="mdi mdi-information-outline" aria-hidden="true" />
            {t('tenderator.unifiedFeed.noPursuitFilter')}
          </span>
        )}
      </div>

      {/* Loading / error / empty */}
      {loading && (
        <div className="tenderator-feed__loading">
          <span className="mdi mdi-loading mdi-spin" aria-hidden="true" />
          {t('tenderator.unifiedFeed.loadingOpportunities')}
        </div>
      )}

      {error && !loading && (
        <div className="tenderator-feed__error">
          <span className="mdi mdi-alert-circle-outline" aria-hidden="true" />
          {error}
          <button type="button" onClick={() => void fetchFeed()}>{t('tenderator.unifiedFeed.retry')}</button>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="tenderator-feed__empty">
          <span className="mdi mdi-magnify-close" aria-hidden="true" />
          <p>{t('tenderator.unifiedFeed.noOpportunitiesFound')}</p>
        </div>
      )}

      {/* Items */}
      {!loading && !error && items.length > 0 && (
        <ul className="tenderator-feed__list">
          {items.map((item) => {
            const tag = sourceLabels[item.source];
            const days = daysUntil(item.deadline);
            const urgencyCls =
              days !== null && days >= 0 && days <= 7
                ? 'tenderator-feed__item--urgent'
                : days !== null && days >= 0 && days <= 30
                ? 'tenderator-feed__item--warm'
                : '';
            return (
              <li key={item.id} className={`tenderator-feed__item ${urgencyCls}`}>
                <button
                  type="button"
                  className="tenderator-feed__item-button"
                  onClick={() => onSelectOpportunity?.(item)}
                >
                  <div className="tenderator-feed__item-head">
                    <span className={`tenderator-feed__source ${tag.colour}`} title={tag.hint}>
                      <span className={`mdi ${tag.icon}`} aria-hidden="true" />
                      {tag.label}
                    </span>
                    {typeof item.match_score === 'number' && (
                      <span className="tenderator-feed__score" title={t('tenderator.unifiedFeed.matchScore')}>
                        <span className="mdi mdi-star" aria-hidden="true" />
                        {Math.round(item.match_score)}
                      </span>
                    )}
                    {item.programme && (
                      <span className="tenderator-feed__programme">{item.programme}</span>
                    )}
                    {item.external_id && (
                      <span className="tenderator-feed__ref">{item.external_id}</span>
                    )}
                    {item.translated_from && (
                      <span className="tenderator-feed__lang-badge" title={t('tenderator.unifiedFeed.translatedFromLang', { lang: item.translated_from })}>
                        <span className="mdi mdi-translate" aria-hidden="true" />
                        {t('tenderator.unifiedFeed.translatedFromShort', { lang: item.translated_from })}
                      </span>
                    )}
                  </div>
                  <div className="tenderator-feed__item-title">{item.title}</div>
                  {item.description && (
                    <div className="tenderator-feed__item-desc">{item.description}</div>
                  )}
                  <div className="tenderator-feed__item-meta">
                    {item.organisation && (
                      <span className="tenderator-feed__meta-item">
                        <span className="mdi mdi-domain" aria-hidden="true" />
                        {item.organisation}
                      </span>
                    )}
                    {item.country && (
                      <span className="tenderator-feed__meta-item">
                        <span className="mdi mdi-map-marker-outline" aria-hidden="true" />
                        {item.country}
                      </span>
                    )}
                    {item.budget && (
                      <span className="tenderator-feed__meta-item">
                        <span className="mdi mdi-currency-eur" aria-hidden="true" />
                        {formatValue(item.budget, item.currency)}
                      </span>
                    )}
                    {item.deadline && (
                      <span className={`tenderator-feed__meta-item tenderator-feed__deadline ${urgencyCls}`}>
                        <span className="mdi mdi-clock-outline" aria-hidden="true" />
                        {formatDeadline(item.deadline, t)}
                      </span>
                    )}
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {/* Pagination (TED / single-source modes only; "all" mode is fixed mix) */}
      {!loading && !error && items.length > 0 && source !== 'all' && (
        <div className="tenderator-feed__pagination">
          <button
            type="button"
            className="tenderator-feed__page-button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
          >
            <span className="mdi mdi-chevron-left" aria-hidden="true" />
            {t('tenderator.unifiedFeed.previous')}
          </button>
          <span className="tenderator-feed__page-meta">{t('tenderator.unifiedFeed.pageNumber', { page })}</span>
          <button
            type="button"
            className="tenderator-feed__page-button"
            onClick={() => setPage((p) => p + 1)}
            disabled={items.length < 20}
          >
            {t('tenderator.unifiedFeed.next')}
            <span className="mdi mdi-chevron-right" aria-hidden="true" />
          </button>
        </div>
      )}
    </div>
  );
};
