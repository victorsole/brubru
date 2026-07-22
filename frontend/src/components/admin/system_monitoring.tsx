// frontend/src/components/admin/system_monitoring.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface ActivityLog {
  id: string;
  admin_user_id: string | null;
  action_type: string;
  target_type: string | null;
  target_id: string | null;
  action_details: any;
  created_at: string;
}

interface SyncSource {
  key: string;
  label: string;
  tier: string;
  status: string;
  last_run_at: string | null;
  last_success_at: string | null;
  items_added: number | null;
  stale: boolean;
}

interface SyncFailure {
  source_key: string;
  tier: string | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
}

interface SyncHealth {
  sources: SyncSource[];
  stale_count: number;
  recent_failures: SyncFailure[];
}

export const SystemMonitoring = () => {
  const { token } = useAuth();
  const [activityLogs, setActivityLogs] = useState<ActivityLog[]>([]);
  const [syncHealth, setSyncHealth] = useState<SyncHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [activeTab, setActiveTab] = useState<'sync' | 'logs'>('sync');
  const [runningTier, setRunningTier] = useState<string | null>(null);
  const [runMessage, setRunMessage] = useState<string | null>(null);

  useEffect(() => {
    if (activeTab === 'logs') {
      fetchActivityLogs();
    } else {
      fetchSyncHealth();
    }
  }, [page, activeTab]);

  const fetchActivityLogs = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/admin/activity-log`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { page, page_size: 50 }
      });
      setActivityLogs(response.data.logs);
      setTotal(response.data.total);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch activity logs:', err);
      setError(err.response?.data?.detail || 'Failed to load activity logs');
    } finally {
      setLoading(false);
    }
  };

  const fetchSyncHealth = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/admin/sync/health`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSyncHealth(response.data);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch sync health:', err);
      setError(err.response?.data?.detail || 'Failed to load sync health');
    } finally {
      setLoading(false);
    }
  };

  const runSyncTier = async (tier: 'fast' | 'warm') => {
    if (!confirm(`Run the '${tier}' sync tier now? Sources run one by one in the background.`)) return;
    try {
      setRunningTier(tier);
      const response = await axios.post(
        `${API_BASE_URL}/api/admin/sync/run/${tier}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setRunMessage(response.data.message);
    } catch (err: any) {
      setRunMessage(err.response?.data?.detail || `Failed to start ${tier} sync`);
    } finally {
      setRunningTier(null);
    }
  };

  if (loading && activityLogs.length === 0 && !syncHealth) {
    return <div className="admin-section__loading">Loading monitoring data...</div>;
  }

  if (error && activityLogs.length === 0 && !syncHealth) {
    return (
      <div className="admin-section__error">
        <p>{error}</p>
        <button
          className="btn btn--primary btn--small"
          onClick={() => activeTab === 'logs' ? fetchActivityLogs() : fetchSyncHealth()}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="admin-section">
      <div className="admin-section__header">
        <h2>Ops &amp; Monitoring</h2>
        <div className="admin-section__actions">
          <button
            className={`btn btn--small ${activeTab === 'sync' ? 'btn--primary' : 'btn--secondary'}`}
            onClick={() => setActiveTab('sync')}
          >
            Sync Health
          </button>
          <button
            className={`btn btn--small ${activeTab === 'logs' ? 'btn--primary' : 'btn--secondary'}`}
            onClick={() => setActiveTab('logs')}
          >
            Activity Logs
          </button>
        </div>
      </div>

      {activeTab === 'sync' && syncHealth && (
        <>
          <div className="admin-section__stats">
            <span>Sources: <strong>{syncHealth.sources.length}</strong></span>
            <span>Stale: <strong style={{ color: syncHealth.stale_count > 0 ? '#dc2626' : undefined }}>
              {syncHealth.stale_count}
            </strong></span>
            <span style={{ marginLeft: 'auto', display: 'flex', gap: '0.5rem' }}>
              <button
                className="btn btn--secondary btn--small"
                onClick={() => runSyncTier('fast')}
                disabled={runningTier !== null}
              >
                <span className="mdi mdi-play"></span>
                {runningTier === 'fast' ? 'Starting...' : 'Run fast tier'}
              </button>
              <button
                className="btn btn--secondary btn--small"
                onClick={() => runSyncTier('warm')}
                disabled={runningTier !== null}
              >
                <span className="mdi mdi-play"></span>
                {runningTier === 'warm' ? 'Starting...' : 'Run warm tier'}
              </button>
              <button className="btn btn--primary btn--small" onClick={fetchSyncHealth}>
                <span className="mdi mdi-refresh"></span>
                Refresh
              </button>
            </span>
          </div>

          {runMessage && (
            <p style={{ margin: '0.5rem 0', fontSize: '0.875rem', color: '#374151' }}>
              {runMessage} Refresh to see freshness updates as sources finish.
            </p>
          )}

          <div className="admin-section__table-container">
            <table className="admin-section__table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Tier</th>
                  <th>Status</th>
                  <th>Last Success</th>
                  <th>Items Added</th>
                  <th>Freshness</th>
                </tr>
              </thead>
              <tbody>
                {syncHealth.sources.map((s) => (
                  <tr key={s.key}>
                    <td><strong>{s.label}</strong><br /><small className="admin-section__text-muted">{s.key}</small></td>
                    <td>{s.tier}</td>
                    <td>
                      <span className={`admin-section__badge admin-section__badge--${s.status === 'success' ? 'success' : (s.status === 'never' ? 'default' : 'error')}`}>
                        {s.status}
                      </span>
                    </td>
                    <td>{s.last_success_at ? new Date(s.last_success_at).toLocaleString() : 'Never'}</td>
                    <td>{s.items_added ?? '-'}</td>
                    <td>
                      <span className={`admin-section__status ${s.stale ? 'admin-section__status--inactive' : 'admin-section__status--active'}`}>
                        {s.stale ? 'Stale' : 'Fresh'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {syncHealth.recent_failures.length > 0 && (
            <div style={{ marginTop: '2rem' }}>
              <h3 style={{ margin: '0 0 1rem', fontSize: '1.1rem' }}>Recent Failures</h3>
              <div className="admin-section__table-container">
                <table className="admin-section__table">
                  <thead>
                    <tr>
                      <th>Source</th>
                      <th>Tier</th>
                      <th>When</th>
                      <th>Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {syncHealth.recent_failures.map((f, i) => (
                      <tr key={`${f.source_key}-${i}`}>
                        <td><strong>{f.source_key}</strong></td>
                        <td>{f.tier || '-'}</td>
                        <td>{f.started_at ? new Date(f.started_at).toLocaleString() : '-'}</td>
                        <td>
                          <small className="admin-section__text-error">
                            {(f.error || '').substring(0, 120)}
                          </small>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {activeTab === 'logs' && (
        <>
          <div className="admin-section__stats">
            <span>Total Logs: <strong>{total}</strong></span>
            <span>Showing: <strong>{activityLogs.length}</strong></span>
          </div>

          <div className="admin-section__table-container">
            <table className="admin-section__table">
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Target Type</th>
                  <th>Target ID</th>
                  <th>Details</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {activityLogs.map((log) => (
                  <tr key={log.id}>
                    <td>
                      <span className="admin-section__badge">
                        {log.action_type.replace('_', ' ')}
                      </span>
                    </td>
                    <td>{log.target_type || '-'}</td>
                    <td>
                      <small className="admin-section__text-muted">
                        {log.target_id ? log.target_id.substring(0, 8) + '...' : '-'}
                      </small>
                    </td>
                    <td>
                      <small className="admin-section__text-muted">
                        {log.action_details ? JSON.stringify(log.action_details).substring(0, 80) + '...' : '-'}
                      </small>
                    </td>
                    <td>{new Date(log.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {total > 50 && (
            <div className="admin-section__pagination">
              <button
                className="btn btn--secondary btn--small"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </button>
              <span>Page {page} of {Math.ceil(total / 50)}</span>
              <button
                className="btn btn--secondary btn--small"
                onClick={() => setPage(p => p + 1)}
                disabled={page >= Math.ceil(total / 50)}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};
