// frontend/src/components/admin/outreach_management.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import { AdminStatsCard } from './shared/admin_stats_card';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface RecentSend {
  brief_date: string;
  recipients: number;
  sent_at: string | null;
}

interface DormantProfile {
  id: string;
  full_name: string | null;
  organization: string | null;
  linkedin_url: string | null;
  pre_provisioned_at: string | null;
  claim_token_expires_at: string | null;
}

interface OutreachOverview {
  brief: {
    last_send_at: string | null;
    sends_30d: number;
    recipients_30d: number;
    recent_sends: RecentSend[];
    unsubscribed_users: number;
  };
  eutr: {
    total_orgs: number | null;
    sendable: number | null;
    bounced: number | null;
    unsubscribed: number | null;
  };
  dormant_profiles: {
    pending: DormantProfile[];
    claimed_total: number;
  };
}

export const OutreachManagement = () => {
  const { token } = useAuth();
  const [data, setData] = useState<OutreachOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/admin/outreach/overview`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setData(response.data);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch outreach overview:', err);
      setError(err.response?.data?.detail || 'Failed to load outreach overview');
    } finally {
      setLoading(false);
    }
  };

  if (loading && !data) {
    return <div className="admin-section__loading">Loading outreach data...</div>;
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
        <h2>Outreach</h2>
        <button className="btn btn--primary btn--small" onClick={fetchData}>
          <span className="mdi mdi-refresh"></span>
          Refresh
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
        <AdminStatsCard
          icon="email-newsletter"
          title="Last Brief Send"
          value={data.brief.last_send_at ? new Date(data.brief.last_send_at).toLocaleDateString() : 'Never'}
          subtitle={`${data.brief.recipients_30d} recipients in 30 days`}
        />
        <AdminStatsCard
          icon="email-off"
          title="Unsubscribed"
          value={data.brief.unsubscribed_users}
          subtitle="Registered users opted out of the brief"
          variant={data.brief.unsubscribed_users > 0 ? 'warning' : 'default'}
        />
        <AdminStatsCard
          icon="office-building"
          title="EUTR Sendable"
          value={data.eutr.sendable ?? 'n/a'}
          subtitle={`of ${data.eutr.total_orgs ?? '?'} orgs (verified, not bounced/unsub)`}
        />
        <AdminStatsCard
          icon="email-remove"
          title="EUTR Bounced"
          value={data.eutr.bounced ?? 'n/a'}
          subtitle={`${data.eutr.unsubscribed ?? 0} unsubscribed`}
          variant={(data.eutr.bounced || 0) > 0 ? 'warning' : 'default'}
        />
        <AdminStatsCard
          icon="account-convert"
          title="Claimed Profiles"
          value={data.dormant_profiles.claimed_total}
          subtitle={`${data.dormant_profiles.pending.length} dormant pending`}
          variant="success"
        />
      </div>

      {/* Recent brief sends */}
      <div style={{ marginBottom: '2rem' }}>
        <h3 style={{ margin: '0 0 1rem', fontSize: '1.1rem' }}>Recent Brief Sends</h3>
        <div className="admin-section__table-container">
          <table className="admin-section__table">
            <thead>
              <tr>
                <th>Brief Date</th>
                <th>Recipients</th>
                <th>Sent At</th>
              </tr>
            </thead>
            <tbody>
              {data.brief.recent_sends.length === 0 ? (
                <tr><td colSpan={3} style={{ textAlign: 'center', padding: '1.5rem' }}>No sends logged</td></tr>
              ) : (
                data.brief.recent_sends.map((s) => (
                  <tr key={s.brief_date}>
                    <td><strong>{s.brief_date}</strong></td>
                    <td>{s.recipients}</td>
                    <td>{s.sent_at ? new Date(s.sent_at).toLocaleString() : '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Dormant claim profiles */}
      <div>
        <h3 style={{ margin: '0 0 1rem', fontSize: '1.1rem' }}>Dormant Profiles (pre-provisioned, unclaimed)</h3>
        <div className="admin-section__table-container">
          <table className="admin-section__table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Organisation</th>
                <th>LinkedIn</th>
                <th>Provisioned</th>
                <th>Claim Expires</th>
              </tr>
            </thead>
            <tbody>
              {data.dormant_profiles.pending.length === 0 ? (
                <tr><td colSpan={5} style={{ textAlign: 'center', padding: '1.5rem' }}>No dormant profiles</td></tr>
              ) : (
                data.dormant_profiles.pending.map((p) => (
                  <tr key={p.id}>
                    <td><strong>{p.full_name || '-'}</strong></td>
                    <td>{p.organization || '-'}</td>
                    <td>
                      {p.linkedin_url ? (
                        <a href={p.linkedin_url} target="_blank" rel="noopener noreferrer">
                          <small>{p.linkedin_url.replace('https://www.linkedin.com/in/', '')}</small>
                        </a>
                      ) : '-'}
                    </td>
                    <td>{p.pre_provisioned_at ? new Date(p.pre_provisioned_at).toLocaleDateString() : '-'}</td>
                    <td>
                      {p.claim_token_expires_at ? (
                        <span style={{
                          color: new Date(p.claim_token_expires_at) < new Date() ? '#dc2626' : undefined
                        }}>
                          {new Date(p.claim_token_expires_at).toLocaleDateString()}
                        </span>
                      ) : '-'}
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
