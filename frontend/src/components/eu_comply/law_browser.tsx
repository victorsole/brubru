// frontend/src/components/eu_comply/law_browser.tsx
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/use_auth';
import type { LawCluster } from '../../pages/eu_comply_page';
import { getEucanonUrl } from '../../utils/eucanon_map';
import './law_browser.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface LawBrowserProps {
  onSelectCluster: (cluster: LawCluster) => void;
}

type ForMeCluster = LawCluster & { matches_interests?: boolean; matches_tracked?: boolean };

export const LawBrowser = ({ onSelectCluster }: LawBrowserProps) => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [clusters, setClusters] = useState<LawCluster[]>([]);
  const [filteredClusters, setFilteredClusters] = useState<LawCluster[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPolicyArea, setSelectedPolicyArea] = useState<string>('all');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forMe, setForMe] = useState<ForMeCluster[]>([]);

  useEffect(() => {
    fetchClusters();
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

  useEffect(() => {
    filterClusters();
  }, [searchQuery, selectedPolicyArea, clusters]);

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
        if (response.status === 401) {
          setError(t('comply.browser.errorLogin'));
        } else {
          setError(t('comply.browser.errorFetch'));
        }
        setClusters([]);
        setFilteredClusters([]);
        return;
      }

      const data: LawCluster[] = await response.json();
      setClusters(Array.isArray(data) ? data : []);
      setFilteredClusters(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Error fetching clusters:', err);
      setError(t('comply.browser.errorLoad'));
      setClusters([]);
      setFilteredClusters([]);
    } finally {
      setIsLoading(false);
    }
  };

  const filterClusters = () => {
    let filtered = [...clusters];

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        cluster =>
          cluster.name.toLowerCase().includes(query) ||
          cluster.description.toLowerCase().includes(query) ||
          cluster.applicability.toLowerCase().includes(query)
      );
    }

    // Filter by policy area
    if (selectedPolicyArea !== 'all') {
      filtered = filtered.filter(
        cluster => cluster.policy_area === selectedPolicyArea
      );
    }

    setFilteredClusters(filtered);
  };

  const getPolicyAreas = (): string[] => {
    const areas = new Set(clusters.map(c => c.policy_area));
    return Array.from(areas).sort();
  };

  const getPriorityIcon = (lawCount: number): string => {
    if (lawCount >= 30) return 'mdi-star';
    if (lawCount >= 10) return 'mdi-star-half-full';
    return 'mdi-star-outline';
  };

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
      {/* Search and Filter */}
      <div className="law-browser__controls">
        <div className="law-browser__search">
          <span className="mdi mdi-magnify"></span>
          <input
            type="text"
            placeholder={t('comply.browser.searchPlaceholder')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="law-browser__search-input"
          />
        </div>

        <div className="law-browser__filter">
          <label htmlFor="policy-area-filter">
            <span className="mdi mdi-filter-variant"></span>
            {t('comply.browser.policyArea')}
          </label>
          <select
            id="policy-area-filter"
            value={selectedPolicyArea}
            onChange={(e) => setSelectedPolicyArea(e.target.value)}
            className="law-browser__filter-select"
          >
            <option value="all">{t('comply.browser.allAreas')}</option>
            {getPolicyAreas().map(area => (
              <option key={area} value={area}>{area}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Phase-3 bridge: clusters in your interests / containing files you track */}
      {forMe.length > 0 && searchQuery === '' && selectedPolicyArea === 'all' && (
        <div className="law-browser__section law-browser__section--forme">
          <h2 className="law-browser__section-title">
            <span className="mdi mdi-creation"></span>
            {t('comply.browser.forYou', 'For you')}
          </h2>
          <div className="law-browser__grid">
            {forMe.slice(0, 6).map(cluster => (
              <div key={cluster.id} className="law-browser__forme-card">
                {cluster.matches_tracked && (
                  <span className="law-browser__forme-chip is-tracked">
                    <span className="mdi mdi-bookmark-check"></span> {t('comply.browser.fromTracked', 'Touches a file you track')}
                  </span>
                )}
                <ClusterCard
                  cluster={cluster}
                  onSelect={onSelectCluster}
                  priorityIcon={getPriorityIcon(cluster.law_count)}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Results Count */}
      <div className="law-browser__results-count">
        {t('comply.browser.showing', { filtered: filteredClusters.length, total: clusters.length })}
      </div>

      {/* Popular Clusters Section */}
      {searchQuery === '' && selectedPolicyArea === 'all' && (
        <div className="law-browser__section">
          <h2 className="law-browser__section-title">
            <span className="mdi mdi-fire"></span>
            {t('comply.browser.popular')}
          </h2>
          <div className="law-browser__grid">
            {filteredClusters
              .filter(c => c.law_count >= 20)
              .slice(0, 6)
              .map(cluster => (
                <ClusterCard
                  key={cluster.id}
                  cluster={cluster}
                  onSelect={onSelectCluster}
                  priorityIcon={getPriorityIcon(cluster.law_count)}
                />
              ))}
          </div>
        </div>
      )}

      {/* All Clusters Section */}
      <div className="law-browser__section">
        {searchQuery === '' && selectedPolicyArea === 'all' && (
          <h2 className="law-browser__section-title">
            <span className="mdi mdi-view-list"></span>
            {t('comply.browser.allPackages')}
          </h2>
        )}
        <div className="law-browser__grid">
          {filteredClusters.map(cluster => (
            <ClusterCard
              key={cluster.id}
              cluster={cluster}
              onSelect={onSelectCluster}
              priorityIcon={getPriorityIcon(cluster.law_count)}
            />
          ))}
        </div>
      </div>

      {filteredClusters.length === 0 && (
        <div className="law-browser__no-results">
          <span className="mdi mdi-file-search-outline"></span>
          <p>{t('comply.browser.noResults')}</p>
          <button onClick={() => { setSearchQuery(''); setSelectedPolicyArea('all'); }}>
            {t('comply.browser.clearFilters')}
          </button>
        </div>
      )}
    </div>
  );
};

interface ClusterCardProps {
  cluster: LawCluster;
  onSelect: (cluster: LawCluster) => void;
  priorityIcon: string;
}

const ClusterCard = ({ cluster, onSelect, priorityIcon }: ClusterCardProps) => {
  const { t } = useTranslation();
  return (
    <div
      className="cluster-card"
      onClick={() => onSelect(cluster)}
      role="button"
      tabIndex={0}
      onKeyPress={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          onSelect(cluster);
        }
      }}
    >
      <div className="cluster-card__header">
        <h3 className="cluster-card__title">{cluster.name}</h3>
        <span className={`mdi ${priorityIcon} cluster-card__priority-icon`}></span>
      </div>

      <div className="cluster-card__policy-area">
        <span className="mdi mdi-label-outline"></span>
        {cluster.policy_area}
      </div>

      <p className="cluster-card__description">
        {cluster.description}
      </p>

      <div className="cluster-card__stats">
        <div className="cluster-card__stat">
          <span className="mdi mdi-file-document-multiple-outline"></span>
          <span>{cluster.law_count} {t('comply.browser.laws')}</span>
        </div>
        <div className="cluster-card__stat">
          <span className="mdi mdi-gavel"></span>
          <span>{cluster.requirement_count} {t('comply.browser.requirements')}</span>
        </div>
      </div>

      <div className="cluster-card__applicability">
        <strong>{t('comply.appliesTo')}</strong> {cluster.applicability}
      </div>

      {getEucanonUrl(cluster) && (
        <a
          href={getEucanonUrl(cluster) as string}
          target="_blank"
          rel="noopener noreferrer"
          className="cluster-card__eucanon-link"
          onClick={(e) => e.stopPropagation()}
          aria-label={t('comply.browser.eucanonAria') as string}
        >
          <span className="mdi mdi-book-open-variant-outline"></span>
          <span>{t('comply.browser.eucanonReminder')}</span>
          <span className="mdi mdi-open-in-new"></span>
        </a>
      )}

      <div className="cluster-card__action">
        <span>{t('comply.browser.selectPackage')}</span>
        <span className="mdi mdi-arrow-right"></span>
      </div>
    </div>
  );
};
