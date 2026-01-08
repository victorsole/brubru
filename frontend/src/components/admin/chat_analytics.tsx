// frontend/src/components/admin/chat_analytics.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import { AdminStatsCard } from './shared/admin_stats_card';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface ChatAnalytics {
  total_conversations: number;
  total_messages: number;
  active_users_today: number;
  avg_messages_per_conversation: number;
  total_tokens_used?: number;
  avg_response_time_ms?: number;
}

interface RecentChat {
  id: string;
  user_id: string;
  user_email?: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export const ChatAnalytics = () => {
  const { token } = useAuth();
  const [analytics, setAnalytics] = useState<ChatAnalytics | null>(null);
  const [recentChats, setRecentChats] = useState<RecentChat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);

      // Fetch chat list (approximation of analytics)
      const chatsResponse = await axios.get(`${API_BASE_URL}/api/chat/list`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      // Handle both array and object response formats
      let chats: any[] = [];
      if (Array.isArray(chatsResponse.data)) {
        chats = chatsResponse.data;
      } else if (chatsResponse.data.conversations && Array.isArray(chatsResponse.data.conversations)) {
        // Backend returns {conversations: [...], total: ...}
        chats = chatsResponse.data.conversations;
      } else {
        console.warn('Chats response is not an array:', chatsResponse.data);
        setAnalytics({
          total_conversations: 0,
          total_messages: 0,
          active_users_today: 0,
          avg_messages_per_conversation: 0
        });
        setRecentChats([]);
        setError('Invalid response format from server');
        setLoading(false);
        return;
      }

      // Calculate basic analytics with defensive checks
      const totalConversations = chats.length;
      const totalMessages = chats.reduce((sum: number, chat: any) => sum + (chat.message_count || 0), 0);
      const avgMessages = totalConversations > 0 ? Math.round(totalMessages / totalConversations) : 0;

      setAnalytics({
        total_conversations: totalConversations,
        total_messages: totalMessages,
        active_users_today: 0, // Would need additional endpoint
        avg_messages_per_conversation: avgMessages,
        total_tokens_used: 0,
        avg_response_time_ms: 0
      });

      setRecentChats(chats.slice(0, 10));
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch analytics:', err);
      setError(err.response?.data?.detail || 'Failed to load chat analytics');
      setRecentChats([]);
      // Set default values
      setAnalytics({
        total_conversations: 0,
        total_messages: 0,
        active_users_today: 0,
        avg_messages_per_conversation: 0
      });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteChat = async (chatId: string) => {
    if (!confirm('Are you sure you want to delete this conversation?')) return;

    try {
      await axios.delete(`${API_BASE_URL}/api/chat/${chatId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setRecentChats(recentChats.filter(chat => chat.id !== chatId));
      fetchAnalytics(); // Refresh analytics
    } catch (err: any) {
      console.error('Failed to delete chat:', err);
      alert('Failed to delete conversation');
    }
  };

  if (loading) {
    return <div className="admin-section__loading">Loading chat analytics...</div>;
  }

  return (
    <div className="admin-section">
      <div className="admin-section__header">
        <h2>Chat Analytics</h2>
        <button className="btn btn--primary btn--small" onClick={fetchAnalytics}>
          <span className="mdi mdi-refresh"></span>
          Refresh
        </button>
      </div>

      {/* Stats Cards */}
      {analytics && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
          <AdminStatsCard
            icon="forum"
            title="Total Conversations"
            value={analytics.total_conversations}
            subtitle="All time"
          />
          <AdminStatsCard
            icon="message"
            title="Total Messages"
            value={analytics.total_messages}
            subtitle="All time"
          />
          <AdminStatsCard
            icon="chart-line"
            title="Avg Messages/Chat"
            value={analytics.avg_messages_per_conversation}
            subtitle="Per conversation"
            variant="success"
          />
          <AdminStatsCard
            icon="account-clock"
            title="Active Today"
            value={analytics.active_users_today}
            subtitle="Users chatting today"
            variant="warning"
          />
        </div>
      )}

      {/* Additional Metrics */}
      {analytics && (analytics.total_tokens_used || analytics.avg_response_time_ms) ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
          {analytics.total_tokens_used && analytics.total_tokens_used > 0 && (
            <AdminStatsCard
              icon="code-braces"
              title="Total Tokens"
              value={analytics.total_tokens_used.toLocaleString()}
              subtitle="Claude API usage"
            />
          )}
          {analytics.avg_response_time_ms && analytics.avg_response_time_ms > 0 && (
            <AdminStatsCard
              icon="clock-fast"
              title="Avg Response Time"
              value={`${analytics.avg_response_time_ms}ms`}
              subtitle="API latency"
            />
          )}
        </div>
      ) : null}

      {/* Recent Conversations */}
      <div style={{ marginTop: '2rem' }}>
        <h3 style={{ margin: '0 0 1rem', fontSize: '1.25rem' }}>Recent Conversations</h3>
        <div className="admin-section__table-container">
          <table className="admin-section__table">
            <thead>
              <tr>
                <th>Conversation ID</th>
                <th>User</th>
                <th>Messages</th>
                <th>Created</th>
                <th>Last Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {recentChats.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '2rem' }}>
                    {error || 'No conversations found'}
                  </td>
                </tr>
              ) : (
                recentChats.map((chat) => (
                  <tr key={chat.id}>
                    <td>
                      <small className="admin-section__text-muted">
                        {chat.id.substring(0, 8)}...
                      </small>
                    </td>
                    <td>
                      <small className="admin-section__text-muted">
                        {chat.user_email || chat.user_id}
                      </small>
                    </td>
                    <td>{chat.message_count || 0}</td>
                    <td>{new Date(chat.created_at).toLocaleDateString()}</td>
                    <td>{new Date(chat.updated_at).toLocaleString()}</td>
                    <td>
                      <button
                        className="btn btn--secondary btn--small"
                        onClick={() => handleDeleteChat(chat.id)}
                        title="Delete conversation"
                        style={{ color: '#dc2626' }}
                      >
                        <span className="mdi mdi-delete"></span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Information Panel */}
      <div style={{
        marginTop: '2rem',
        background: '#f9fafb',
        border: '1px solid var(--color-border, #e5e7eb)',
        borderRadius: '8px',
        padding: '1.5rem'
      }}>
        <h4 style={{ margin: '0 0 1rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className="mdi mdi-information"></span>
          About Chat Analytics
        </h4>
        <p style={{ margin: 0, color: '#6b7280', fontSize: '0.875rem', lineHeight: 1.6 }}>
          This dashboard shows aggregate statistics about chat usage across all users. Use this data to monitor
          system usage, identify trends, and optimize the chat experience. For detailed per-user analytics,
          check individual user profiles in the User Management section.
        </p>
      </div>
    </div>
  );
};
