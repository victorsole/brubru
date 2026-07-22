// frontend/src/components/admin/chat_analytics.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import { AdminStatsCard } from './shared/admin_stats_card';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface DashboardSummary {
  total_messages: number;
  avg_response_time_ms: number;
  avg_tokens_per_message: number;
  total_tokens_used: number;
  knowledge_gap_rate: number;
}

interface DashboardData {
  period: { days: number; start_date: string; end_date: string };
  summary: DashboardSummary;
  providers: Record<string, number>;
  knowledge_gaps: { total: number; by_type: Record<string, number> };
  feedback: { total: number; positive: number; negative: number; hallucination_reports: number };
  daily_breakdown: Array<{ date: string; messages: number; avg_response_time: number; knowledge_gaps: number }>;
}

interface ConversationRow {
  conversation_id: string;
  message_count: number;
  total_tokens: number | null;
  avg_response_time_ms: number;
  knowledge_gap_count: number;
  last_message_at: string | null;
}

export const ChatAnalytics = () => {
  const { token } = useAuth();
  const [days, setDays] = useState(7);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [conversations, setConversations] = useState<ConversationRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAnalytics();
  }, [days]);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      const headers = { Authorization: `Bearer ${token}` };
      const [dashRes, convRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/api/admin/analytics/dashboard`, { headers, params: { days } }),
        axios.get(`${API_BASE_URL}/api/admin/analytics/conversations`, { headers, params: { days, limit: 25 } }),
      ]);
      setDashboard(dashRes.data);
      setConversations(convRes.data.conversations || []);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch chat analytics:', err);
      setError(err.response?.data?.detail || 'Failed to load chat analytics');
    } finally {
      setLoading(false);
    }
  };

  if (loading && !dashboard) {
    return <div className="admin-section__loading">Loading chat analytics...</div>;
  }

  if (error && !dashboard) {
    return (
      <div className="admin-section__error">
        <p>{error}</p>
        <button className="btn btn--primary btn--small" onClick={fetchAnalytics}>Retry</button>
      </div>
    );
  }

  if (!dashboard) return null;

  const providerEntries = Object.entries(dashboard.providers || {}).sort((a, b) => b[1] - a[1]);
  const gapEntries = Object.entries(dashboard.knowledge_gaps?.by_type || {}).sort((a, b) => b[1] - a[1]);

  return (
    <div className="admin-section">
      <div className="admin-section__header">
        <h2>Chat Analytics</h2>
        <div className="admin-section__actions">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="admin-section__filter"
          >
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button className="btn btn--primary btn--small" onClick={fetchAnalytics}>
            <span className="mdi mdi-refresh"></span>
            Refresh
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
        <AdminStatsCard
          icon="message"
          title="Messages"
          value={dashboard.summary.total_messages}
          subtitle={`Last ${dashboard.period.days} days`}
        />
        <AdminStatsCard
          icon="clock-fast"
          title="Avg Response"
          value={`${Math.round(dashboard.summary.avg_response_time_ms)}ms`}
          subtitle="Mean response time"
        />
        <AdminStatsCard
          icon="code-braces"
          title="Tokens"
          value={dashboard.summary.total_tokens_used.toLocaleString()}
          subtitle={`~${Math.round(dashboard.summary.avg_tokens_per_message)} per message`}
        />
        <AdminStatsCard
          icon="alert-circle"
          title="Knowledge Gap Rate"
          value={`${dashboard.summary.knowledge_gap_rate}%`}
          subtitle={`${dashboard.knowledge_gaps.total} gap events`}
          variant={dashboard.summary.knowledge_gap_rate > 10 ? 'warning' : 'success'}
        />
        <AdminStatsCard
          icon="thumb-up"
          title="Feedback"
          value={`${dashboard.feedback.positive} / ${dashboard.feedback.negative}`}
          subtitle={`positive / negative (${dashboard.feedback.hallucination_reports} hallucination reports)`}
          variant={dashboard.feedback.hallucination_reports > 0 ? 'warning' : 'default'}
        />
      </div>

      {/* Provider distribution + gap types */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
        <div style={{ background: 'white', border: '1px solid var(--color-border, #e5e7eb)', borderRadius: '8px', padding: '1.5rem' }}>
          <h4 style={{ margin: '0 0 1rem' }}>Provider Distribution</h4>
          {providerEntries.length === 0 ? (
            <p style={{ color: '#6b7280', fontSize: '0.875rem' }}>No data in this period</p>
          ) : (
            providerEntries.map(([provider, count]) => (
              <div key={provider} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.35rem 0', borderBottom: '1px solid #f3f4f6', fontSize: '0.9rem' }}>
                <span>{provider || 'unknown'}</span>
                <strong>{count}</strong>
              </div>
            ))
          )}
        </div>
        <div style={{ background: 'white', border: '1px solid var(--color-border, #e5e7eb)', borderRadius: '8px', padding: '1.5rem' }}>
          <h4 style={{ margin: '0 0 1rem' }}>Knowledge Gaps by Type</h4>
          {gapEntries.length === 0 ? (
            <p style={{ color: '#6b7280', fontSize: '0.875rem' }}>No knowledge gaps in this period</p>
          ) : (
            gapEntries.map(([type, count]) => (
              <div key={type} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.35rem 0', borderBottom: '1px solid #f3f4f6', fontSize: '0.9rem' }}>
                <span>{type}</span>
                <strong>{count}</strong>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Daily breakdown */}
      <div style={{ marginBottom: '2rem' }}>
        <h3 style={{ margin: '0 0 1rem', fontSize: '1.1rem' }}>Daily Breakdown</h3>
        <div className="admin-section__table-container">
          <table className="admin-section__table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Messages</th>
                <th>Avg Response (ms)</th>
                <th>Knowledge Gaps</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.daily_breakdown.map((d) => (
                <tr key={d.date}>
                  <td>{d.date}</td>
                  <td>{d.messages}</td>
                  <td>{Math.round(d.avg_response_time)}</td>
                  <td>{d.knowledge_gaps}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent conversations (system-wide, anonymised ids) */}
      <div>
        <h3 style={{ margin: '0 0 1rem', fontSize: '1.1rem' }}>Recent Conversations (all users)</h3>
        <div className="admin-section__table-container">
          <table className="admin-section__table">
            <thead>
              <tr>
                <th>Conversation</th>
                <th>Messages</th>
                <th>Tokens</th>
                <th>Avg Response (ms)</th>
                <th>Gaps</th>
                <th>Last Message</th>
              </tr>
            </thead>
            <tbody>
              {conversations.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '2rem' }}>
                    No conversations in this period
                  </td>
                </tr>
              ) : (
                conversations.map((c) => (
                  <tr key={c.conversation_id}>
                    <td>
                      <small className="admin-section__text-muted">
                        {c.conversation_id.substring(0, 8)}...
                      </small>
                    </td>
                    <td>{c.message_count}</td>
                    <td>{c.total_tokens?.toLocaleString() ?? '-'}</td>
                    <td>{Math.round(c.avg_response_time_ms)}</td>
                    <td>{c.knowledge_gap_count}</td>
                    <td>{c.last_message_at ? new Date(c.last_message_at).toLocaleString() : '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
