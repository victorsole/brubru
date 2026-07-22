// frontend/src/components/admin/billing_management.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import { AdminStatsCard } from './shared/admin_stats_card';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface UsageEvent {
  user_email: string | null;
  endpoint: string;
  method: string;
  cost_eur: number;
  status_code: number | null;
  is_sandbox: boolean;
  created_at: string | null;
}

interface TopupEvent {
  user_email: string | null;
  amount_eur: number;
  status: string;
  created_at: string | null;
}

interface KeyRow {
  id: string;
  user_email: string;
  name: string;
  key_prefix: string;
  api_tier: string;
  is_sandbox: boolean;
  last_used_at: string | null;
  revoked: boolean;
  created_at: string | null;
}

interface BillingOverview {
  total_balance_eur: number;
  funded_users: number;
  usage_7d_count: number;
  usage_7d_cost_eur: number;
  active_keys: number;
  recent_usage: UsageEvent[];
  recent_topups: TopupEvent[];
  keys: KeyRow[];
}

export const BillingManagement = () => {
  const { token } = useAuth();
  const [data, setData] = useState<BillingOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/admin/billing/overview`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setData(response.data);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch billing overview:', err);
      setError(err.response?.data?.detail || 'Failed to load billing overview');
    } finally {
      setLoading(false);
    }
  };

  const revokeKey = async (keyId: string) => {
    if (!confirm('Revoke this API key? The holder loses access immediately.')) return;
    try {
      await axios.delete(`${API_BASE_URL}/api/admin/api-keys/${keyId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      await fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to revoke key');
    }
  };

  if (loading && !data) {
    return <div className="admin-section__loading">Loading billing data...</div>;
  }

  if (error && !data) {
    return (
      <div className="admin-section__error">
        <p>{error}</p>
        <button className="btn btn--primary btn--small" onClick={fetchData}>Retry</button>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="admin-section">
      <div className="admin-section__header">
        <h2>Billing &amp; API</h2>
        <button className="btn btn--primary btn--small" onClick={fetchData}>
          <span className="mdi mdi-refresh"></span>
          Refresh
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
        <AdminStatsCard
          icon="wallet"
          title="Credit Balances"
          value={`€${data.total_balance_eur.toLocaleString()}`}
          subtitle={`${data.funded_users} funded users`}
          variant="success"
        />
        <AdminStatsCard
          icon="api"
          title="API Calls (7d)"
          value={data.usage_7d_count}
          subtitle={`€${data.usage_7d_cost_eur} debited (non-sandbox)`}
        />
        <AdminStatsCard
          icon="key"
          title="Active Keys"
          value={data.active_keys}
          subtitle="Non-revoked API keys"
        />
      </div>

      {/* Recent top-ups */}
      <div style={{ marginBottom: '2rem' }}>
        <h3 style={{ margin: '0 0 1rem', fontSize: '1.1rem' }}>Recent Top-ups</h3>
        <div className="admin-section__table-container">
          <table className="admin-section__table">
            <thead>
              <tr>
                <th>User</th>
                <th>Amount</th>
                <th>Status</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_topups.length === 0 ? (
                <tr><td colSpan={4} style={{ textAlign: 'center', padding: '1.5rem' }}>No top-ups yet</td></tr>
              ) : (
                data.recent_topups.map((t, i) => (
                  <tr key={i}>
                    <td><small className="admin-section__text-muted">{t.user_email || '-'}</small></td>
                    <td><strong>€{t.amount_eur}</strong></td>
                    <td>
                      <span className={`admin-section__badge admin-section__badge--${t.status === 'succeeded' ? 'success' : (t.status === 'failed' ? 'error' : 'default')}`}>
                        {t.status}
                      </span>
                    </td>
                    <td>{t.created_at ? new Date(t.created_at).toLocaleString() : '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent usage events */}
      <div style={{ marginBottom: '2rem' }}>
        <h3 style={{ margin: '0 0 1rem', fontSize: '1.1rem' }}>Recent API Usage</h3>
        <div className="admin-section__table-container">
          <table className="admin-section__table">
            <thead>
              <tr>
                <th>User</th>
                <th>Endpoint</th>
                <th>Cost</th>
                <th>Status</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_usage.length === 0 ? (
                <tr><td colSpan={5} style={{ textAlign: 'center', padding: '1.5rem' }}>No usage events yet</td></tr>
              ) : (
                data.recent_usage.map((u, i) => (
                  <tr key={i}>
                    <td><small className="admin-section__text-muted">{u.user_email || (u.is_sandbox ? 'sandbox' : '-')}</small></td>
                    <td><small>{u.method} {u.endpoint.substring(0, 60)}</small></td>
                    <td>€{u.cost_eur}</td>
                    <td>{u.status_code ?? '-'}</td>
                    <td>{u.created_at ? new Date(u.created_at).toLocaleString() : '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* API keys */}
      <div>
        <h3 style={{ margin: '0 0 1rem', fontSize: '1.1rem' }}>API Keys (latest 50)</h3>
        <div className="admin-section__table-container">
          <table className="admin-section__table">
            <thead>
              <tr>
                <th>User</th>
                <th>Name</th>
                <th>Prefix</th>
                <th>Tier</th>
                <th>Last Used</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.keys.length === 0 ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: '1.5rem' }}>No API keys</td></tr>
              ) : (
                data.keys.map((k) => (
                  <tr key={k.id}>
                    <td><small className="admin-section__text-muted">{k.user_email}</small></td>
                    <td>{k.name}{k.is_sandbox && <span className="admin-section__badge" style={{ marginLeft: '0.4rem' }}>sandbox</span>}</td>
                    <td><code style={{ fontSize: '0.8rem' }}>{k.key_prefix}...</code></td>
                    <td>{k.api_tier}</td>
                    <td>{k.last_used_at ? new Date(k.last_used_at).toLocaleString() : 'Never'}</td>
                    <td>
                      <span className={`admin-section__status ${k.revoked ? 'admin-section__status--inactive' : 'admin-section__status--active'}`}>
                        {k.revoked ? 'Revoked' : 'Active'}
                      </span>
                    </td>
                    <td>
                      {!k.revoked && (
                        <button
                          className="btn btn--secondary btn--small"
                          onClick={() => revokeKey(k.id)}
                          style={{ color: '#dc2626' }}
                          title="Revoke key"
                        >
                          <span className="mdi mdi-key-remove"></span>
                        </button>
                      )}
                    </td>
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
