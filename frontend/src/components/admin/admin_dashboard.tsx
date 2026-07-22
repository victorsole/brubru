// frontend/src/components/admin/admin_dashboard.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import { AdminStatsCard } from './shared/admin_stats_card';
import './admin_dashboard.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const WAPU_TARGET = 10; // Phase A target (see strategy: 10 -> 25 -> 50)

interface SystemStats {
  total_users: number;
  active_users_7d: number;
  total_feeds: number;
  active_feeds: number;
  total_entries: number;
  entries_today: number;
  total_subscriptions: number;
  total_feedback: number;
  unresolved_feedback: number;
  signups_7d: number;
  signups_30d: number;
  paying_users: number;
  wapu_7d: number;
  dormant_profiles: number;
  sync_failures_24h: number;
  brief_sends_7d: number;
}

export const AdminDashboard = () => {
  const { token } = useAuth();
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/admin/stats`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setStats(response.data);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch stats:', err);
      setError(err.response?.data?.detail || 'Failed to load system statistics');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="admin-dashboard">
        <div className="admin-dashboard__loading">Loading statistics...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="admin-dashboard">
        <div className="admin-dashboard__error">
          <p>{error}</p>
          <button className="btn btn--primary btn--small" onClick={fetchStats}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!stats) {
    return null;
  }

  const syncHealthy = stats.sync_failures_24h === 0;

  return (
    <div className="admin-dashboard">
      <div className="admin-dashboard__header">
        <h2>Business Overview</h2>
        <button className="btn btn--secondary btn--small" onClick={fetchStats}>
          <span className="mdi mdi-refresh"></span>
          Refresh
        </button>
      </div>

      {/* North star + growth row */}
      <div className="admin-dashboard__grid">
        <AdminStatsCard
          icon="target"
          title="WAPU (7 days)"
          value={`${stats.wapu_7d} / ${WAPU_TARGET}`}
          subtitle="Weekly Active Paid Users vs Phase A target"
          variant={stats.wapu_7d >= WAPU_TARGET ? 'success' : 'warning'}
        />
        <AdminStatsCard
          icon="cash-multiple"
          title="Paying Users"
          value={stats.paying_users}
          subtitle="Users on a paid tier"
          variant="success"
        />
        <AdminStatsCard
          icon="account-plus"
          title="Signups"
          value={stats.signups_7d}
          subtitle={`last 7 days (${stats.signups_30d} in 30 days)`}
        />
        <AdminStatsCard
          icon="account-group"
          title="Total Users"
          value={stats.total_users}
          subtitle={`${stats.active_users_7d} logged in within 7 days`}
        />
        <AdminStatsCard
          icon="account-clock"
          title="Dormant Profiles"
          value={stats.dormant_profiles}
          subtitle="Pre-provisioned, awaiting claim"
        />
      </div>

      <div className="admin-dashboard__header" style={{ marginTop: '2rem' }}>
        <h2>Operations</h2>
      </div>

      <div className="admin-dashboard__grid">
        <AdminStatsCard
          icon={syncHealthy ? 'check-circle' : 'alert-circle'}
          title="Sync Health"
          value={syncHealthy ? 'Healthy' : `${stats.sync_failures_24h} failures`}
          subtitle={syncHealthy ? 'No failed sync runs in 24h' : 'Failed sync runs in last 24h (see Ops tab)'}
          variant={syncHealthy ? 'success' : 'warning'}
        />
        <AdminStatsCard
          icon="email-newsletter"
          title="Brief Sends"
          value={stats.brief_sends_7d}
          subtitle="Brubru Brief emails sent in 7 days"
        />
        <AdminStatsCard
          icon="rss"
          title="RSS Feeds"
          value={stats.total_feeds}
          subtitle={`${stats.active_feeds} active, ${stats.entries_today} entries today`}
        />
        <AdminStatsCard
          icon="bell-ring"
          title="Feed Subscriptions"
          value={stats.total_subscriptions}
          subtitle="Active user feed subscriptions"
        />
        <AdminStatsCard
          icon="comment-text"
          title="Feedback"
          value={stats.total_feedback}
          subtitle={`${stats.unresolved_feedback} unresolved`}
          variant={stats.unresolved_feedback > 0 ? 'warning' : 'default'}
        />
      </div>

      <div className="admin-dashboard__info">
        <p>
          WAPU counts users on a paid tier with at least one core action (chat, amendment or
          document) in the last 7 days. Sync health reads the sync_runs ledger; open the Ops
          tab for the per-source freshness table.
        </p>
      </div>
    </div>
  );
};
