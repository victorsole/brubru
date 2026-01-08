// frontend/src/components/admin/admin_dashboard.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import { AdminStatsCard } from './shared/admin_stats_card';
import './admin_dashboard.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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
  total_amendments?: number;
  total_documents?: number;
  total_chat_messages?: number;
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
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      // Fetch additional stats
      const [amendmentsRes, documentsRes, chatsRes] = await Promise.allSettled([
        axios.get(`${API_BASE_URL}/api/amendments`, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        axios.get(`${API_BASE_URL}/api/documents`, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        axios.get(`${API_BASE_URL}/api/chat/list`, {
          headers: { Authorization: `Bearer ${token}` }
        })
      ]);

      // Calculate stats from responses
      let totalAmendments = 0;
      let totalDocuments = 0;
      let totalChatMessages = 0;

      if (amendmentsRes.status === 'fulfilled' && Array.isArray(amendmentsRes.value.data)) {
        totalAmendments = amendmentsRes.value.data.length;
      }

      if (documentsRes.status === 'fulfilled') {
        if (Array.isArray(documentsRes.value.data)) {
          totalDocuments = documentsRes.value.data.length;
        } else if (documentsRes.value.data.total_documents !== undefined) {
          totalDocuments = documentsRes.value.data.total_documents;
        }
      }

      if (chatsRes.status === 'fulfilled' && Array.isArray(chatsRes.value.data)) {
        totalChatMessages = chatsRes.value.data.reduce((sum: number, chat: any) => sum + (chat.message_count || 0), 0);
      }

      const enhancedStats = {
        ...response.data,
        total_amendments: totalAmendments,
        total_documents: totalDocuments,
        total_chat_messages: totalChatMessages
      };

      setStats(enhancedStats);
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

  return (
    <div className="admin-dashboard">
      <div className="admin-dashboard__header">
        <h2>System Overview</h2>
        <button className="btn btn--secondary btn--small" onClick={fetchStats}>
          <span className="mdi mdi-refresh"></span>
          Refresh
        </button>
      </div>

      <div className="admin-dashboard__grid">
        <AdminStatsCard
          icon="account-group"
          title="Total Users"
          value={stats.total_users}
          subtitle={`${stats.active_users_7d} active in last 7 days`}
        />

        <AdminStatsCard
          icon="rss"
          title="RSS Feeds"
          value={stats.total_feeds}
          subtitle={`${stats.active_feeds} active feeds`}
        />

        <AdminStatsCard
          icon="file-document-multiple"
          title="RSS Entries"
          value={stats.total_entries}
          subtitle={`${stats.entries_today} added today`}
        />

        <AdminStatsCard
          icon="bell-ring"
          title="Subscriptions"
          value={stats.total_subscriptions}
          subtitle="Total active subscriptions"
        />

        <AdminStatsCard
          icon="comment-text"
          title="Feedback"
          value={stats.total_feedback}
          subtitle={`${stats.unresolved_feedback} unresolved`}
          variant={stats.unresolved_feedback > 0 ? 'warning' : 'default'}
        />

        <AdminStatsCard
          icon="check-circle"
          title="System Status"
          value="Healthy"
          subtitle="All systems operational"
          variant="success"
        />

        {stats.total_amendments !== undefined && stats.total_amendments > 0 && (
          <AdminStatsCard
            icon="file-edit"
            title="Amendments"
            value={stats.total_amendments}
            subtitle="Total amendments created"
          />
        )}

        {stats.total_documents !== undefined && stats.total_documents > 0 && (
          <AdminStatsCard
            icon="file-cabinet"
            title="Documents"
            value={stats.total_documents}
            subtitle="Total documents uploaded"
          />
        )}

        {stats.total_chat_messages !== undefined && stats.total_chat_messages > 0 && (
          <AdminStatsCard
            icon="message"
            title="Chat Messages"
            value={stats.total_chat_messages}
            subtitle="Total messages sent"
          />
        )}
      </div>

      <div className="admin-dashboard__info">
        <p>
          Welcome to the Brubru Admin Panel. Use the navigation tabs above to manage all aspects of the system,
          including users, content, subscriptions, and system monitoring.
        </p>
      </div>
    </div>
  );
};
