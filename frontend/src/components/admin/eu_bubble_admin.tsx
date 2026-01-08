// frontend/src/components/admin/eu_bubble_admin.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import { AdminStatsCard } from './shared/admin_stats_card';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface BubbleStatus {
  last_refresh_feeds?: string;
  last_refresh_trains?: string;
  feeds_status?: string;
  trains_status?: string;
  entries_fetched?: number;
  enrichment_progress?: number;
}

export const EUBubbleAdmin = () => {
  const { token } = useAuth();
  const [status, setStatus] = useState<BubbleStatus>({});
  const [refreshing, setRefreshing] = useState<Record<string, boolean>>({});

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      // Try to get status from various endpoints
      const trainsStatus = await axios.get(`${API_BASE_URL}/api/bubble/admin/legislative-trains-status`, {
        headers: { Authorization: `Bearer ${token}` }
      }).catch(() => null);

      setStatus({
        last_refresh_trains: trainsStatus?.data?.last_update || 'Never',
        trains_status: trainsStatus?.data?.status || 'Unknown',
        feeds_status: 'Active',
        entries_fetched: 0,
        enrichment_progress: 0
      });
    } catch (err: any) {
      console.error('Failed to fetch status:', err);
    }
  };

  const handleRefreshFeeds = async () => {
    setRefreshing({ ...refreshing, feeds: true });
    try {
      await axios.post(
        `${API_BASE_URL}/api/bubble/admin/refresh-feeds`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      alert('RSS feeds refresh initiated successfully');
      await fetchStatus();
    } catch (err: any) {
      console.error('Failed to refresh feeds:', err);
      alert(err.response?.data?.detail || 'Failed to refresh feeds');
    } finally {
      setRefreshing({ ...refreshing, feeds: false });
    }
  };

  const handleRefreshTrains = async () => {
    setRefreshing({ ...refreshing, trains: true });
    try {
      await axios.post(
        `${API_BASE_URL}/api/bubble/admin/refresh-legislative-trains`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      alert('Legislative trains refresh initiated successfully');
      await fetchStatus();
    } catch (err: any) {
      console.error('Failed to refresh trains:', err);
      alert(err.response?.data?.detail || 'Failed to refresh trains');
    } finally {
      setRefreshing({ ...refreshing, trains: false });
    }
  };

  const handleFetchEntries = async () => {
    setRefreshing({ ...refreshing, entries: true });
    try {
      await axios.post(
        `${API_BASE_URL}/api/bubble/admin/fetch-entries`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      alert('Entry fetching initiated successfully');
      await fetchStatus();
    } catch (err: any) {
      console.error('Failed to fetch entries:', err);
      alert(err.response?.data?.detail || 'Failed to fetch entries');
    } finally {
      setRefreshing({ ...refreshing, entries: false });
    }
  };

  const handleEnrichEntries = async () => {
    setRefreshing({ ...refreshing, enrich: true });
    try {
      await axios.post(
        `${API_BASE_URL}/api/bubble/admin/enrich-entries-ai`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      alert('AI enrichment initiated successfully');
      await fetchStatus();
    } catch (err: any) {
      console.error('Failed to enrich entries:', err);
      alert(err.response?.data?.detail || 'Failed to enrich entries');
    } finally {
      setRefreshing({ ...refreshing, enrich: false });
    }
  };

  return (
    <div className="admin-section">
      <div className="admin-section__header">
        <h2>EU Bubble Admin Controls</h2>
        <button className="btn btn--primary btn--small" onClick={fetchStatus}>
          <span className="mdi mdi-refresh"></span>
          Refresh Status
        </button>
      </div>

      {/* Manual Refresh Controls */}
      <div style={{ marginBottom: '2rem' }}>
        <h3 style={{ margin: '0 0 1rem', fontSize: '1.25rem' }}>Manual Refresh Controls</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
          <button
            className="btn btn--primary"
            onClick={handleRefreshFeeds}
            disabled={refreshing.feeds}
            style={{ padding: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'center' }}
          >
            <span className="mdi mdi-rss"></span>
            {refreshing.feeds ? 'Refreshing...' : 'Refresh RSS Feeds'}
          </button>
          <button
            className="btn btn--primary"
            onClick={handleRefreshTrains}
            disabled={refreshing.trains}
            style={{ padding: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'center' }}
          >
            <span className="mdi mdi-train"></span>
            {refreshing.trains ? 'Refreshing...' : 'Refresh Trains'}
          </button>
          <button
            className="btn btn--primary"
            onClick={handleFetchEntries}
            disabled={refreshing.entries}
            style={{ padding: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'center' }}
          >
            <span className="mdi mdi-download"></span>
            {refreshing.entries ? 'Fetching...' : 'Fetch New Entries'}
          </button>
          <button
            className="btn btn--success"
            onClick={handleEnrichEntries}
            disabled={refreshing.enrich}
            style={{ padding: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'center' }}
          >
            <span className="mdi mdi-robot"></span>
            {refreshing.enrich ? 'Enriching...' : 'Enrich with AI'}
          </button>
        </div>
      </div>

      {/* Status Cards */}
      <div style={{ marginBottom: '2rem' }}>
        <h3 style={{ margin: '0 0 1rem', fontSize: '1.25rem' }}>Scraping Status</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.5rem' }}>
          <AdminStatsCard
            icon="rss"
            title="RSS Feeds Status"
            value={status.feeds_status || 'Unknown'}
            subtitle={status.last_refresh_feeds ? `Last: ${status.last_refresh_feeds}` : 'Never refreshed'}
            variant={status.feeds_status === 'Active' ? 'success' : 'default'}
          />
          <AdminStatsCard
            icon="train"
            title="Legislative Trains"
            value={status.trains_status || 'Unknown'}
            subtitle={status.last_refresh_trains ? `Last: ${status.last_refresh_trains}` : 'Never refreshed'}
            variant={status.trains_status === 'Active' ? 'success' : 'default'}
          />
          <AdminStatsCard
            icon="file-document-multiple"
            title="Entries Fetched"
            value={status.entries_fetched || 0}
            subtitle="Total entries in system"
          />
          {status.enrichment_progress !== undefined && status.enrichment_progress > 0 && (
            <AdminStatsCard
              icon="robot"
              title="AI Enrichment"
              value={`${status.enrichment_progress}%`}
              subtitle="In progress"
              variant="warning"
            />
          )}
        </div>
      </div>

      {/* Information Panel */}
      <div style={{
        background: '#f9fafb',
        border: '1px solid var(--color-border, #e5e7eb)',
        borderRadius: '8px',
        padding: '1.5rem'
      }}>
        <h4 style={{ margin: '0 0 1rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className="mdi mdi-information"></span>
          About EU Bubble Admin Controls
        </h4>
        <ul style={{ margin: 0, paddingLeft: '1.5rem', color: '#6b7280', fontSize: '0.875rem', lineHeight: 1.6 }}>
          <li><strong>Refresh RSS Feeds:</strong> Updates the database with the latest feeds from all institutional sources</li>
          <li><strong>Refresh Trains:</strong> Fetches the latest legislative train schedule and updates file statuses</li>
          <li><strong>Fetch New Entries:</strong> Retrieves new entries from all subscribed feeds</li>
          <li><strong>Enrich with AI:</strong> Uses Claude AI to add summaries and tags to recent entries</li>
        </ul>
        <p style={{ margin: '1rem 0 0', color: '#6b7280', fontSize: '0.875rem' }}>
          <strong>Note:</strong> These operations may take several minutes to complete. The system will continue processing in the background.
        </p>
      </div>
    </div>
  );
};
