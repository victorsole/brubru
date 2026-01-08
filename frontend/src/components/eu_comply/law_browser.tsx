// frontend/src/components/eu_comply/law_browser.tsx
import { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/use_auth';
import type { LawCluster } from '../../pages/eu_comply_page';
import './law_browser.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface LawBrowserProps {
  onSelectCluster: (cluster: LawCluster) => void;
}

export const LawBrowser = ({ onSelectCluster }: LawBrowserProps) => {
  const { token } = useAuth();
  const [clusters, setClusters] = useState<LawCluster[]>([]);
  const [filteredClusters, setFilteredClusters] = useState<LawCluster[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPolicyArea, setSelectedPolicyArea] = useState<string>('all');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchClusters();
  }, []);

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
          setError('Please log in to access EU Law Comply');
        } else {
          setError('Failed to fetch clusters');
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
      setError('Failed to load compliance packages. Please try again.');
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
        <p>Loading compliance packages...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="law-browser law-browser--error">
        <span className="mdi mdi-alert-circle"></span>
        <p>{error}</p>
        <button onClick={fetchClusters}>Try Again</button>
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
            placeholder="Search: DSA, GDPR, AI Act, FinTech..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="law-browser__search-input"
          />
        </div>

        <div className="law-browser__filter">
          <label htmlFor="policy-area-filter">
            <span className="mdi mdi-filter-variant"></span>
            Policy Area:
          </label>
          <select
            id="policy-area-filter"
            value={selectedPolicyArea}
            onChange={(e) => setSelectedPolicyArea(e.target.value)}
            className="law-browser__filter-select"
          >
            <option value="all">All Areas</option>
            {getPolicyAreas().map(area => (
              <option key={area} value={area}>{area}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Results Count */}
      <div className="law-browser__results-count">
        Showing {filteredClusters.length} of {clusters.length} compliance packages
      </div>

      {/* Popular Clusters Section */}
      {searchQuery === '' && selectedPolicyArea === 'all' && (
        <div className="law-browser__section">
          <h2 className="law-browser__section-title">
            <span className="mdi mdi-fire"></span>
            Popular Compliance Packages
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
            All Compliance Packages
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
          <p>No compliance packages found matching your search.</p>
          <button onClick={() => { setSearchQuery(''); setSelectedPolicyArea('all'); }}>
            Clear filters
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
          <span>{cluster.law_count} laws</span>
        </div>
        <div className="cluster-card__stat">
          <span className="mdi mdi-gavel"></span>
          <span>{cluster.requirement_count} requirements</span>
        </div>
      </div>

      <div className="cluster-card__applicability">
        <strong>Applies to:</strong> {cluster.applicability}
      </div>

      <div className="cluster-card__action">
        <span>Select Package</span>
        <span className="mdi mdi-arrow-right"></span>
      </div>
    </div>
  );
};
