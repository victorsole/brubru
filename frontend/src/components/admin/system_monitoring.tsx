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

interface ScraperStatus {
  scraper_name: string;
  is_active: boolean;
  last_run_at: string | null;
  last_run_status: string | null;
  entries_added: number;
  error_message: string | null;
}

export const SystemMonitoring = () => {
  const { token } = useAuth();
  const [activityLogs, setActivityLogs] = useState<ActivityLog[]>([]);
  const [scraperStatus, setScraperStatus] = useState<ScraperStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [activeTab, setActiveTab] = useState<'logs' | 'scrapers'>('logs');

  useEffect(() => {
    if (activeTab === 'logs') {
      fetchActivityLogs();
    } else {
      fetchScraperStatus();
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

  const fetchScraperStatus = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/admin/scrapers/status`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setScraperStatus(response.data);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch scraper status:', err);
      setError(err.response?.data?.detail || 'Failed to load scraper status');
    } finally {
      setLoading(false);
    }
  };

  if (loading && (activityLogs.length === 0 && scraperStatus.length === 0)) {
    return <div className="admin-section__loading">Loading monitoring data...</div>;
  }

  if (error && (activityLogs.length === 0 && scraperStatus.length === 0)) {
    return (
      <div className="admin-section__error">
        <p>{error}</p>
        <button
          className="btn btn--primary btn--small"
          onClick={() => activeTab === 'logs' ? fetchActivityLogs() : fetchScraperStatus()}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="admin-section">
      <div className="admin-section__header">
        <h2>System Monitoring</h2>
        <div className="admin-section__actions">
          <button
            className={`btn btn--small ${activeTab === 'logs' ? 'btn--primary' : 'btn--secondary'}`}
            onClick={() => setActiveTab('logs')}
          >
            Activity Logs
          </button>
          <button
            className={`btn btn--small ${activeTab === 'scrapers' ? 'btn--primary' : 'btn--secondary'}`}
            onClick={() => setActiveTab('scrapers')}
          >
            Scrapers
          </button>
        </div>
      </div>

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

      {activeTab === 'scrapers' && (
        <>
          <div className="admin-section__stats">
            <span>Total Scrapers: <strong>{scraperStatus.length}</strong></span>
            <span>Active: <strong>{scraperStatus.filter(s => s.is_active).length}</strong></span>
          </div>

          <div className="admin-section__table-container">
            <table className="admin-section__table">
              <thead>
                <tr>
                  <th>Scraper Name</th>
                  <th>Status</th>
                  <th>Last Run</th>
                  <th>Last Status</th>
                  <th>Entries Added</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {scraperStatus.map((scraper) => (
                  <tr key={scraper.scraper_name}>
                    <td>
                      <strong>{scraper.scraper_name}</strong>
                    </td>
                    <td>
                      <span className={`admin-section__status ${scraper.is_active ? 'admin-section__status--active' : 'admin-section__status--inactive'}`}>
                        {scraper.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>
                      {scraper.last_run_at
                        ? new Date(scraper.last_run_at).toLocaleString()
                        : 'Never'}
                    </td>
                    <td>
                      {scraper.last_run_status && (
                        <span className={`admin-section__badge admin-section__badge--${scraper.last_run_status === 'success' ? 'success' : 'error'}`}>
                          {scraper.last_run_status}
                        </span>
                      )}
                    </td>
                    <td>{scraper.entries_added || 0}</td>
                    <td>
                      {scraper.error_message && (
                        <small className="admin-section__text-error">
                          {scraper.error_message.substring(0, 50)}
                          {scraper.error_message.length > 50 && '...'}
                        </small>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};
