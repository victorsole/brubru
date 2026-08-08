// frontend/src/components/eu_comply/law_browser.tsx
//
// Search-first cluster browser.
//
// The previous version rendered every cluster three times over: a "For you"
// block of 6, a "Popular" block of 6, and then the full catalogue. With 61
// clusters that was 73 cards, 135 interactive elements and 57k characters of
// text on one screen -- 25,685px of scroll at 1440px, 51,597px at 393px. Cards
// were unbounded, so a China BEV card ran ~900px of CN codes next to a 377px
// one, and the grid was visibly ragged.
//
// This version: one search box, one "For you" row capped at 3, one paginated
// grid that starts at 9 and grows on demand, and cards clamped to a fixed
// height so the grid reads as a grid. Everything a card used to dump inline
// (full description, "Applies to" scope, explainer link) belongs on the
// cluster's own page, not in a catalogue tile.

import { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/use_auth';
import type { LawCluster } from '../../pages/eu_comply_page';
import { getEucanonUrl } from '../../utils/eucanon_map';
import './law_browser.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const PAGE_SIZE = 9;
const FOR_YOU_MAX = 3;

interface LawBrowserProps {
  onSelectCluster: (cluster: LawCluster) => void;
}

type ForMeCluster = LawCluster & { matches_interests?: boolean; matches_tracked?: boolean };

export const LawBrowser = ({ onSelectCluster }: LawBrowserProps) => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [clusters, setClusters] = useState<LawCluster[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPolicyArea, setSelectedPolicyArea] = useState<string>('all');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forMe, setForMe] = useState<ForMeCluster[]>([]);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  useEffect(() => {
    fetchClusters();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Phase-3 bridge: compliance clusters in your interests / containing files you track.
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${API_BASE_URL}/api/eu-law-comply/clusters/for-me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) return;
        const d = await r.json();
        if (!cancelled) setForMe(Array.isArray(d.clusters) ? d.clusters : []);
      } catch { /* silent: the section just won't render */ }
    })();
    return () => { cancelled = true; };
  }, [token]);

  const fetchClusters = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/eu-law-comply/clusters`, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        credentials: 'include',
      });

      if (!response.ok) {
        setError(
          response.status === 401
            ? t('comply.browser.errorLogin')
            : t('comply.browser.errorFetch')
        );
        setClusters([]);
        return;
      }

      const data: LawCluster[] = await response.json();
      setClusters(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Error fetching clusters:', err);
      setError(t('comply.browser.errorLoad'));
      setClusters([]);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredClusters = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return clusters.filter((c) => {
      if (selectedPolicyArea !== 'all' && c.policy_area !== selectedPolicyArea) return false;
      if (!query) return true;
      return (
        (c.name || '').toLowerCase().includes(query) ||
        (c.description || '').toLowerCase().includes(query) ||
        (c.applicability || '').toLowerCase().includes(query) ||
        (c.policy_area || '').toLowerCase().includes(query)
      );
    });
  }, [clusters, searchQuery, selectedPolicyArea]);

  // Reset pagination whenever the result set changes, otherwise a narrow search
  // silently inherits a large visibleCount from a previous broad one.
  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [searchQuery, selectedPolicyArea]);

  const policyAreas = useMemo(
    () => Array.from(new Set(clusters.map((c) => c.policy_area).filter(Boolean))).sort(),
    [clusters]
  );

  const isBrowsing = searchQuery.trim() !== '' || selectedPolicyArea !== 'all';
  const visible = filteredClusters.slice(0, visibleCount);
  const remaining = filteredClusters.length - visible.length;

  if (isLoading) {
    return (
      <div className="law-browser law-browser--loading">
        <span className="mdi mdi-loading mdi-spin"></span>
        <p>{t('comply.browser.loading')}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="law-browser law-browser--error">
        <span className="mdi mdi-alert-circle"></span>
        <p>{error}</p>
        <button onClick={fetchClusters}>{t('comply.browser.tryAgain')}</button>
      </div>
    );
  }

  return (
    <div className="law-browser">
      {/* Search first: the catalogue is 60+ packages, so the primary action is
          finding yours, not scrolling past all of them. */}
      <div className="law-browser__controls">
        <div className="law-browser__search">
          <span className="mdi mdi-magnify"></span>
          <input
            type="text"
            placeholder={t('comply.browser.searchPlaceholder')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="law-browser__search-input"
            aria-label={t('comply.browser.searchPlaceholder')}
          />
          {searchQuery && (
            <button
              type="button"
              className="law-browser__search-clear"
              onClick={() => setSearchQuery('')}
              aria-label={t('comply.browser.clearFilters')}
            >
              <span className="mdi mdi-close"></span>
            </button>
          )}
        </div>

        <div className="law-browser__filter">
          <label htmlFor="policy-area-filter" className="law-browser__filter-label">
            <span className="mdi mdi-filter-variant"></span>
            <span className="law-browser__filter-label-text">
              {t('comply.browser.policyArea')}
            </span>
          </label>
          <select
            id="policy-area-filter"
            value={selectedPolicyArea}
            onChange={(e) => setSelectedPolicyArea(e.target.value)}
            className="law-browser__filter-select"
          >
            <option value="all">{t('comply.browser.allAreas')}</option>
            {policyAreas.map((area) => (
              <option key={area} value={area}>{area}</option>
            ))}
          </select>
        </div>
      </div>

      {/* "For you" only when the user is not actively searching, and capped at 3.
          Any more and it competes with the catalogue instead of shortcutting it. */}
      {forMe.length > 0 && !isBrowsing && (
        <section className="law-browser__section law-browser__section--forme">
          <h2 className="law-browser__section-title">
            <span className="mdi mdi-creation"></span>
            {t('comply.browser.forYou', 'For you')}
          </h2>
          <div className="law-browser__grid">
            {forMe.slice(0, FOR_YOU_MAX).map((cluster) => (
              <ClusterCard
                key={`forme-${cluster.id}`}
                cluster={cluster}
                onSelect={onSelectCluster}
                badge={
                  cluster.matches_tracked
                    ? t('comply.browser.fromTracked', 'Touches a file you track')
                    : undefined
                }
              />
            ))}
          </div>
        </section>
      )}

      <section className="law-browser__section">
        <div className="law-browser__section-head">
          <h2 className="law-browser__section-title">
            <span className="mdi mdi-view-list"></span>
            {isBrowsing
              ? t('comply.browser.results', 'Results')
              : t('comply.browser.allPackages')}
          </h2>
          <span className="law-browser__results-count">
            {t('comply.browser.showing', {
              filtered: visible.length,
              total: filteredClusters.length,
            })}
          </span>
        </div>

        <div className="law-browser__grid">
          {visible.map((cluster) => (
            <ClusterCard
              key={cluster.id}
              cluster={cluster}
              onSelect={onSelectCluster}
            />
          ))}
        </div>

        {remaining > 0 && (
          <button
            type="button"
            className="law-browser__show-more"
            onClick={() => setVisibleCount((n) => n + PAGE_SIZE * 2)}
          >
            <span className="mdi mdi-chevron-down"></span>
            {t('comply.browser.showMore', {
              defaultValue: 'Show {{count}} more',
              count: remaining,
            })}
          </button>
        )}

        {filteredClusters.length === 0 && (
          <div className="law-browser__no-results">
            <span className="mdi mdi-file-search-outline"></span>
            <p>{t('comply.browser.noResults')}</p>
            <button onClick={() => { setSearchQuery(''); setSelectedPolicyArea('all'); }}>
              {t('comply.browser.clearFilters')}
            </button>
          </div>
        )}
      </section>
    </div>
  );
};

interface ClusterCardProps {
  cluster: LawCluster;
  onSelect: (cluster: LawCluster) => void;
  badge?: string;
}

const ClusterCard = ({ cluster, onSelect, badge }: ClusterCardProps) => {
  const { t } = useTranslation();
  const eucanonUrl = getEucanonUrl(cluster);

  return (
    <div
      className="cluster-card"
      onClick={() => onSelect(cluster)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect(cluster);
        }
      }}
    >
      {badge && (
        <span className="cluster-card__badge">
          <span className="mdi mdi-bookmark-check"></span> {badge}
        </span>
      )}

      <h3 className="cluster-card__title">{cluster.name}</h3>

      <div className="cluster-card__policy-area">
        <span className="mdi mdi-label-outline"></span>
        {cluster.policy_area}
      </div>

      {/* Clamped, not truncated at the data layer: the full description is on
          the cluster page. Card descriptions used to run to full legal scope. */}
      <p className="cluster-card__description">{cluster.description}</p>

      <div className="cluster-card__footer">
        <div className="cluster-card__stats">
          <span className="cluster-card__stat">
            <span className="mdi mdi-file-document-multiple-outline"></span>
            {cluster.law_count} {t('comply.browser.laws')}
          </span>
          <span className="cluster-card__stat">
            <span className="mdi mdi-gavel"></span>
            {cluster.requirement_count} {t('comply.browser.requirements')}
          </span>
        </div>

        {eucanonUrl && (
          <a
            href={eucanonUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="cluster-card__eucanon-icon"
            onClick={(e) => e.stopPropagation()}
            title={t('comply.browser.eucanonReminder') as string}
            aria-label={t('comply.browser.eucanonAria') as string}
          >
            <span className="mdi mdi-book-open-variant-outline"></span>
          </a>
        )}
      </div>
    </div>
  );
};
