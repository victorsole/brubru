// frontend/src/components/tenders/unified_opportunity_feed.tsx
//
// Phase 2: a single feed component that renders any combination of the
// 4 Tenderator sources (TED tenders, F&T calls for proposals, F&T calls
// for tenders, F&T funded projects) behind one shape. The dashboard's
// source-filter chip switches the `source` prop.

import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/use_auth';
import './unified_opportunity_feed.css';
import type { SourceFilter } from './tenderator_dashboard';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface UnifiedOpportunity {
  id: string;
  source: 'ted' | 'ft_proposals' | 'ft_tenders' | 'ft_projects' | 'agency';
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
}

export type MatchSubSource = 'all' | 'ted' | 'ft_proposals' | 'ft_tenders' | 'agency';

interface UnifiedFeedProps {
  source: SourceFilter;
  matchSubSource?: MatchSubSource;
  initialQuery?: string;
  programme?: string;
  // When source=='agency': scope the feed to one body_code (e.g. 'efsa').
  body?: string;
  onSelectOpportunity?: (opp: UnifiedOpportunity) => void;
}

const SOURCE_LABELS: Record<UnifiedOpportunity['source'], { label: string; icon: string; colour: string }> = {
  ted: { label: 'TED', icon: 'mdi-gavel', colour: 'tenderator-feed__source--ted' },
  ft_proposals: { label: 'Call for proposals', icon: 'mdi-flask-outline', colour: 'tenderator-feed__source--proposals' },
  ft_tenders: { label: 'Call for tenders', icon: 'mdi-file-document-outline', colour: 'tenderator-feed__source--tenders' },
  ft_projects: { label: 'Funded project', icon: 'mdi-trophy-outline', colour: 'tenderator-feed__source--projects' },
  agency: { label: 'Agency', icon: 'mdi-office-building-outline', colour: 'tenderator-feed__source--agency' },
};

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

const formatDeadline = (iso: string | null): string => {
  if (!iso) return 'no deadline';
  const days = daysUntil(iso);
  if (days === null) return 'no deadline';
  if (days < 0) return 'closed';
  if (days === 0) return 'closes today';
  if (days === 1) return 'closes in 1 day';
  if (days <= 30) return `closes in ${days} days`;
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
};

export const UnifiedOpportunityFeed = ({ source, matchSubSource = 'all', initialQuery = '', programme = '', body = '', onSelectOpportunity }: UnifiedFeedProps) => {
  const { token } = useAuth();
  const { i18n } = useTranslation();
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
  // Layer 1: MEUB Policy-Interest personalisation. Default ON, persisted; the
  // backend treats it as a no-op when the user has no interests set.
  const [personalised, setPersonalised] = useState<boolean>(() => {
    try { return localStorage.getItem('tenderator_personalised') !== '0'; } catch { return true; }
  });
  const [personalisedApplied, setPersonalisedApplied] = useState<boolean>(false);
  const [interests, setInterests] = useState<string[]>([]);

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
      if (body && source === 'agency') params.set('body', body);
      params.set('lang', feedLang);
      if (clientFilter) params.set('client_filter', 'true');
      // Only send when OFF — backend default is true.
      if (!personalised) params.set('personalised', 'false');
      const res = await fetch(`${API_URL}/api/tenders/unified-feed?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: 'Feed query failed.' }));
        setError(detail.detail || 'Feed query failed.');
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
      setError('Could not load opportunities.');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [token, source, matchSubSource, page, searchQuery, programme, body, feedLang, clientFilter, personalised]);

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
          placeholder="Search by title, organisation, programme..."
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
            aria-label="Clear search"
          >
            <span className="mdi mdi-close" aria-hidden="true" />
          </button>
        )}
      </div>

      {/* Personalisation pill (Layer 1) — derived from your MEUB Policy
          Interests. Default ON; turning OFF widens the feed back to the
          full catalogue. No-op when the user has no interests set. */}
      <div className="tenderator-feed__personalised">
        <label className="tenderator-feed__personalised-toggle">
          <input
            type="checkbox"
            checked={personalised}
            onChange={(e) => {
              const v = e.target.checked;
              setPersonalised(v);
              try { localStorage.setItem('tenderator_personalised', v ? '1' : '0'); } catch (_) { /* ignore */ }
            }}
          />
          <span>Personalise by my policy interests</span>
        </label>
        {personalised && personalisedApplied && (
          <span
            className="tenderator-feed__personalised-badge"
            title={interests.length ? `Interests: ${interests.join(', ')}` : undefined}
          >
            <span className="mdi mdi-tune-variant" aria-hidden="true" />
            Personalised — {interests.length} interest{interests.length === 1 ? '' : 's'}
          </span>
        )}
        {personalised && !personalisedApplied && (
          <span className="tenderator-feed__personalised-badge tenderator-feed__personalised-badge--inactive">
            <span className="mdi mdi-information-outline" aria-hidden="true" />
            No policy interests set — <a href="/my-eu-bubble?tab=policy-interests">add some in My EU Bubble</a>
          </span>
        )}
      </div>

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
          <span>Filter to my pursuits</span>
        </label>
        {clientFilter && clientFilterApplied && clientFilterSlug && (
          <span className="tenderator-feed__client-filter-badge">
            <span className="mdi mdi-filter-check-outline" aria-hidden="true" />
            Filtered to {clientFilterSlug}
          </span>
        )}
        {clientFilter && !clientFilterApplied && (
          <span className="tenderator-feed__client-filter-badge tenderator-feed__client-filter-badge--inactive">
            <span className="mdi mdi-information-outline" aria-hidden="true" />
            No pursuits filter configured — showing all
          </span>
        )}
      </div>

      {/* Loading / error / empty */}
      {loading && (
        <div className="tenderator-feed__loading">
          <span className="mdi mdi-loading mdi-spin" aria-hidden="true" />
          Loading opportunities...
        </div>
      )}

      {error && !loading && (
        <div className="tenderator-feed__error">
          <span className="mdi mdi-alert-circle-outline" aria-hidden="true" />
          {error}
          <button type="button" onClick={() => void fetchFeed()}>Retry</button>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="tenderator-feed__empty">
          <span className="mdi mdi-magnify-close" aria-hidden="true" />
          <p>No opportunities found for this source and search.</p>
        </div>
      )}

      {/* Items */}
      {!loading && !error && items.length > 0 && (
        <ul className="tenderator-feed__list">
          {items.map((item) => {
            const tag = SOURCE_LABELS[item.source];
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
                    <span className={`tenderator-feed__source ${tag.colour}`}>
                      <span className={`mdi ${tag.icon}`} aria-hidden="true" />
                      {tag.label}
                    </span>
                    {typeof item.match_score === 'number' && (
                      <span className="tenderator-feed__score" title="Match score">
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
                      <span className="tenderator-feed__lang-badge" title={`Original language: ${item.translated_from}`}>
                        <span className="mdi mdi-translate" aria-hidden="true" />
                        translated from {item.translated_from}
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
                        {formatDeadline(item.deadline)}
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
            Previous
          </button>
          <span className="tenderator-feed__page-meta">Page {page}</span>
          <button
            type="button"
            className="tenderator-feed__page-button"
            onClick={() => setPage((p) => p + 1)}
            disabled={items.length < 20}
          >
            Next
            <span className="mdi mdi-chevron-right" aria-hidden="true" />
          </button>
        </div>
      )}
    </div>
  );
};
