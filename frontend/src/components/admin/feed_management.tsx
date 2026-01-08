// frontend/src/components/admin/feed_management.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface Feed {
  id: string;
  name: string;
  url: string;
  feed_type: string;
  institution: string | null;
  is_active: boolean;
  last_fetched_at: string | null;
  entry_count: number;
  subscriber_count: number;
  created_at: string;
}

export const FeedManagement = () => {
  const { token } = useAuth();
  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetchFeeds();
  }, []);

  const fetchFeeds = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/admin/feeds`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { search: searchQuery || undefined }
      });
      setFeeds(response.data);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch feeds:', err);
      setError(err.response?.data?.detail || 'Failed to load feeds');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    fetchFeeds();
  };

  if (loading && feeds.length === 0) {
    return <div className="admin-section__loading">Loading feeds...</div>;
  }

  if (error && feeds.length === 0) {
    return (
      <div className="admin-section__error">
        <p>{error}</p>
        <button className="btn btn--primary btn--small" onClick={fetchFeeds}>Retry</button>
      </div>
    );
  }

  return (
    <div className="admin-section">
      <div className="admin-section__header">
        <h2>Feed Management</h2>
        <div className="admin-section__actions">
          <input
            type="text"
            placeholder="Search feeds..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            className="admin-section__search"
          />
          <button className="btn btn--primary btn--small" onClick={handleSearch}>
            Search
          </button>
          <button className="btn btn--success btn--small" onClick={fetchFeeds}>
            Refresh
          </button>
        </div>
      </div>

      <div className="admin-section__stats">
        <span>Total Feeds: <strong>{feeds.length}</strong></span>
        <span>Active: <strong>{feeds.filter(f => f.is_active).length}</strong></span>
        <span>Total Entries: <strong>{feeds.reduce((sum, f) => sum + f.entry_count, 0)}</strong></span>
      </div>

      <div className="admin-section__table-container">
        <table className="admin-section__table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Institution</th>
              <th>Type</th>
              <th>Status</th>
              <th>Entries</th>
              <th>Subscribers</th>
              <th>Last Fetched</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {feeds.map((feed) => (
              <tr key={feed.id}>
                <td>
                  <strong>{feed.name}</strong>
                  <br />
                  <small className="admin-section__url">{feed.url}</small>
                </td>
                <td>{feed.institution || '-'}</td>
                <td>
                  <span className="admin-section__badge">
                    {feed.feed_type}
                  </span>
                </td>
                <td>
                  <span className={`admin-section__status ${feed.is_active ? 'admin-section__status--active' : 'admin-section__status--inactive'}`}>
                    {feed.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td>{feed.entry_count}</td>
                <td>{feed.subscriber_count}</td>
                <td>
                  {feed.last_fetched_at
                    ? new Date(feed.last_fetched_at).toLocaleString()
                    : 'Never'}
                </td>
                <td>{new Date(feed.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
