/**
 * EU Law Comply Management Component
 *
 * Admin interface for managing law clusters and triggering requirement extraction.
 * Includes real-time progress tracking with progress bars.
 */

import { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/use_auth';
import './eu_comply_management.css';

interface ClusterStats {
  id: number;
  name: string;
  policy_area: string;
  description: string;
  law_count: number;
  requirement_count: number;
  extraction_status: 'idle' | 'pending' | 'running' | 'completed' | 'failed';
  extraction_progress: number;
}

interface ExtractionStatus {
  cluster_id: number;
  status: 'idle' | 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  current_law: number;
  total_laws: number;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

export const EUComplyManagement = () => {
  const { token } = useAuth();
  const [clusters, setClusters] = useState<ClusterStats[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [extractingClusters, setExtractingClusters] = useState<Set<number>>(new Set());

  useEffect(() => {
    fetchClusters();
  }, []);

  // Poll for progress updates every 3 seconds
  useEffect(() => {
    if (extractingClusters.size === 0) return;

    const interval = setInterval(() => {
      extractingClusters.forEach((clusterId) => {
        fetchExtractionStatus(clusterId);
      });
    }, 3000);

    return () => clearInterval(interval);
  }, [extractingClusters]);

  const fetchClusters = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('http://localhost:8000/api/admin/eu-comply/clusters/stats', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch cluster stats');
      }

      const data: ClusterStats[] = await response.json();
      setClusters(data);

      // Add running extractions to tracking set
      const running = new Set<number>();
      data.forEach(cluster => {
        if (cluster.extraction_status === 'running' || cluster.extraction_status === 'pending') {
          running.add(cluster.id);
        }
      });
      setExtractingClusters(running);

    } catch (err) {
      console.error('Error fetching clusters:', err);
      setError('Failed to load cluster statistics');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchExtractionStatus = async (clusterId: number) => {
    try {
      const response = await fetch(
        `http://localhost:8000/api/admin/eu-comply/clusters/${clusterId}/extraction-status`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) return;

      const status: ExtractionStatus = await response.json();

      // Update cluster in list
      setClusters(prev => prev.map(cluster =>
        cluster.id === clusterId
          ? {
              ...cluster,
              extraction_status: status.status,
              extraction_progress: status.progress,
            }
          : cluster
      ));

      // Remove from extracting set if completed or failed
      if (status.status === 'completed' || status.status === 'failed') {
        setExtractingClusters(prev => {
          const next = new Set(prev);
          next.delete(clusterId);
          return next;
        });

        // Refresh cluster stats to get updated requirement count
        if (status.status === 'completed') {
          setTimeout(fetchClusters, 1000);
        }
      }

    } catch (err) {
      console.error(`Error fetching extraction status for cluster ${clusterId}:`, err);
    }
  };

  const startExtraction = async (clusterId: number) => {
    try {
      const response = await fetch(
        `http://localhost:8000/api/admin/eu-comply/clusters/${clusterId}/extract`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to start extraction');
      }

      // Add to extracting set
      setExtractingClusters(prev => new Set(prev).add(clusterId));

      // Update cluster status
      setClusters(prev => prev.map(cluster =>
        cluster.id === clusterId
          ? { ...cluster, extraction_status: 'pending' as const, extraction_progress: 0 }
          : cluster
      ));

    } catch (err) {
      console.error('Error starting extraction:', err);
      alert(err instanceof Error ? err.message : 'Failed to start extraction');
    }
  };

  const getStatusColor = (status: ClusterStats['extraction_status']) => {
    switch (status) {
      case 'completed': return '#10b981';
      case 'running': return '#3b82f6';
      case 'pending': return '#f59e0b';
      case 'failed': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const getStatusLabel = (status: ClusterStats['extraction_status']) => {
    switch (status) {
      case 'completed': return 'Completed';
      case 'running': return 'Extracting...';
      case 'pending': return 'Pending...';
      case 'failed': return 'Failed';
      default: return 'Not Started';
    }
  };

  if (isLoading) {
    return (
      <div className="eu-comply-management">
        <div className="eu-comply-management__loading">
          <div className="spinner"></div>
          <p>Loading cluster statistics...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="eu-comply-management">
        <div className="eu-comply-management__error">
          <p>{error}</p>
          <button onClick={fetchClusters} className="button button-primary">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="eu-comply-management">
      <div className="eu-comply-management__header">
        <h2>EU Law Comply - Requirement Extraction</h2>
        <p className="eu-comply-management__subtitle">
          Manage law clusters and extract compliance requirements using AI
        </p>
        <button onClick={fetchClusters} className="button button-secondary">
          <span className="mdi mdi-refresh"></span>
          Refresh
        </button>
      </div>

      <div className="eu-comply-management__stats">
        <div className="stat-card">
          <div className="stat-card__label">Total Clusters</div>
          <div className="stat-card__value">{clusters.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Total Laws</div>
          <div className="stat-card__value">
            {clusters.reduce((sum, c) => sum + c.law_count, 0)}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Total Requirements</div>
          <div className="stat-card__value">
            {clusters.reduce((sum, c) => sum + c.requirement_count, 0)}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Extraction Jobs Running</div>
          <div className="stat-card__value">{extractingClusters.size}</div>
        </div>
      </div>

      <div className="eu-comply-management__clusters">
        {clusters.map((cluster) => (
          <div key={cluster.id} className="cluster-card">
            <div className="cluster-card__header">
              <div>
                <h3 className="cluster-card__name">{cluster.name}</h3>
                <span className="cluster-card__policy">{cluster.policy_area}</span>
              </div>
              <div
                className="cluster-card__status"
                style={{ backgroundColor: getStatusColor(cluster.extraction_status) }}
              >
                {getStatusLabel(cluster.extraction_status)}
              </div>
            </div>

            <p className="cluster-card__description">{cluster.description}</p>

            <div className="cluster-card__stats">
              <div className="cluster-stat">
                <span className="mdi mdi-file-document-multiple"></span>
                <span>{cluster.law_count} laws</span>
              </div>
              <div className="cluster-stat">
                <span className="mdi mdi-gavel"></span>
                <span>{cluster.requirement_count} requirements</span>
              </div>
            </div>

            {(cluster.extraction_status === 'running' || cluster.extraction_status === 'pending') && (
              <div className="cluster-card__progress">
                <div className="progress-bar">
                  <div
                    className="progress-bar__fill"
                    style={{ width: `${cluster.extraction_progress}%` }}
                  ></div>
                </div>
                <span className="progress-label">{cluster.extraction_progress}%</span>
              </div>
            )}

            <div className="cluster-card__actions">
              <button
                onClick={() => startExtraction(cluster.id)}
                disabled={
                  cluster.extraction_status === 'running' ||
                  cluster.extraction_status === 'pending'
                }
                className="button button-primary"
              >
                {cluster.extraction_status === 'running' || cluster.extraction_status === 'pending'
                  ? 'Extracting...'
                  : cluster.requirement_count > 0
                  ? 'Re-extract Requirements'
                  : 'Extract Requirements'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
