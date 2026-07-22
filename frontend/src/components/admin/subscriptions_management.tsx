// frontend/src/components/admin/subscriptions_management.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import { AdminStatsCard } from './shared/admin_stats_card';
import { AdminModal } from './shared/admin_modal';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Internal gating tiers (never shown to end users; fine in the admin panel)
const TIER_LABELS: Record<string, string> = {
  white: 'White (trial / no plan)',
  yellow: 'Yellow (module, Starter, Advocate, EP)',
  blue: 'Blue (Professional)',
};

interface Plan {
  id: string;
  name: string;
  price_monthly: number;
  price_annual: number;
  tier: string;
  includes?: string[];
  eligibility?: string;
}

interface PlansResponse {
  modules: Plan[];
  bundles: Plan[];
  special: Plan[];
}

interface Overview {
  total_users: number;
  by_tier: Record<string, number>;
  paying_users: number;
  by_plan: Record<string, number>;
  mrr_eur: number | null;
  stripe_error: string | null;
}

interface UserSubscription {
  id: string;
  email: string | null;
  full_name?: string;
  subscription_tier: string;
  subscription_expires_at?: string | null;
  stripe_subscription_id?: string | null;
  is_active: boolean;
  is_dormant?: boolean;
  created_at: string;
  role: string;
}

export const SubscriptionsManagement = () => {
  const { token } = useAuth();
  const [users, setUsers] = useState<UserSubscription[]>([]);
  const [plans, setPlans] = useState<PlansResponse | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [tierFilter, setTierFilter] = useState<string>('all');
  const [selectedUser, setSelectedUser] = useState<UserSubscription | null>(null);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [newTier, setNewTier] = useState<string>('');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const headers = { Authorization: `Bearer ${token}` };

      const [overviewRes, plansRes, usersRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/api/admin/subscriptions/overview`, { headers }),
        axios.get(`${API_BASE_URL}/api/subscriptions/plans`, { headers }),
        axios.get(`${API_BASE_URL}/api/admin/users`, { headers, params: { page_size: 200 } }),
      ]);

      setOverview(overviewRes.data);
      setPlans(plansRes.data);
      setUsers(usersRes.data?.users || []);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch subscription data:', err);
      setError(err.response?.data?.detail || 'Failed to load subscription data');
      setUsers([]);
      setOverview(null);
    } finally {
      setLoading(false);
    }
  };

  const handleUpgrade = async () => {
    if (!selectedUser || !newTier) return;

    try {
      await axios.patch(
        `${API_BASE_URL}/api/admin/users/${selectedUser.id}`,
        { subscription_tier: newTier },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      await fetchData();
      setShowUpgradeModal(false);
      setSelectedUser(null);
    } catch (err: any) {
      console.error('Failed to change tier:', err);
      alert(err.response?.data?.detail || 'Failed to update subscription tier');
    }
  };

  const filteredUsers = users.filter(user => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      if (
        !user.email?.toLowerCase().includes(query) &&
        !user.full_name?.toLowerCase().includes(query)
      ) {
        return false;
      }
    }
    if (tierFilter !== 'all' && user.subscription_tier !== tierFilter) return false;
    return true;
  });

  if (loading) {
    return <div className="admin-section__loading">Loading subscription data...</div>;
  }

  if (error) {
    return (
      <div className="admin-section__error">
        <p>{error}</p>
        <button className="btn btn--primary btn--small" onClick={fetchData}>Retry</button>
      </div>
    );
  }

  const planEntries = overview ? Object.entries(overview.by_plan).sort((a, b) => b[1] - a[1]) : [];
  const allPlans: Plan[] = plans ? [...plans.bundles, ...plans.special, ...plans.modules] : [];

  return (
    <div className="admin-section">
      <div className="admin-section__header">
        <h2>Subscriptions &amp; Billing</h2>
        <button className="btn btn--primary btn--small" onClick={fetchData}>
          <span className="mdi mdi-refresh"></span>
          Refresh
        </button>
      </div>

      {/* Stats Cards (server-side, all users) */}
      {overview && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.5rem', marginBottom: '1rem' }}>
          <AdminStatsCard
            icon="account-multiple"
            title="Total Users"
            value={overview.total_users}
            subtitle={`${overview.by_tier.white || 0} on trial / no plan`}
          />
          <AdminStatsCard
            icon="cash-multiple"
            title="MRR (Stripe)"
            value={overview.mrr_eur !== null ? `€${overview.mrr_eur.toLocaleString()}` : 'n/a'}
            subtitle={overview.mrr_eur !== null ? 'Live from active Stripe subscriptions' : 'Stripe unavailable'}
            variant="success"
          />
          <AdminStatsCard
            icon="credit-card-check"
            title="Paying Users"
            value={overview.paying_users}
            subtitle="Active Stripe subscription on file"
          />
          <AdminStatsCard
            icon="star"
            title="Yellow Tier"
            value={overview.by_tier.yellow || 0}
            subtitle="Modules, Starter, Advocate, EP"
            variant="warning"
          />
          <AdminStatsCard
            icon="crown"
            title="Blue Tier"
            value={overview.by_tier.blue || 0}
            subtitle="Professional"
          />
        </div>
      )}

      {overview?.stripe_error && (
        <p style={{ margin: '0 0 1rem', fontSize: '0.8rem', color: '#b45309' }}>
          Stripe data unavailable: {overview.stripe_error}
        </p>
      )}

      {/* Plan breakdown from Stripe */}
      {planEntries.length > 0 && (
        <div style={{ background: 'white', border: '1px solid var(--color-border, #e5e7eb)', borderRadius: '8px', padding: '1.25rem', marginBottom: '2rem' }}>
          <h4 style={{ margin: '0 0 0.75rem' }}>Active Subscriptions by Plan (Stripe)</h4>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
            {planEntries.map(([plan, count]) => (
              <span key={plan} className="admin-section__badge" style={{ fontSize: '0.85rem' }}>
                {plan}: <strong>{count}</strong>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="admin-section__header" style={{ marginTop: '1rem' }}>
        <h3 style={{ margin: 0, fontSize: '1.25rem' }}>User Subscriptions</h3>
        <div className="admin-section__actions">
          <input
            type="text"
            placeholder="Search users..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="admin-section__search"
          />
          <select
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value)}
            className="admin-section__filter"
          >
            <option value="all">All Tiers</option>
            <option value="white">{TIER_LABELS.white}</option>
            <option value="yellow">{TIER_LABELS.yellow}</option>
            <option value="blue">{TIER_LABELS.blue}</option>
          </select>
        </div>
      </div>

      <div className="admin-section__table-container" style={{ marginTop: '1rem' }}>
        <table className="admin-section__table">
          <thead>
            <tr>
              <th>User</th>
              <th>Email</th>
              <th>Tier</th>
              <th>Stripe</th>
              <th>Expires</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }}>
                  No users found
                </td>
              </tr>
            ) : (
              filteredUsers.map((user) => (
                <tr key={user.id}>
                  <td>
                    <strong>{user.full_name || 'N/A'}</strong>
                    {user.is_dormant && (
                      <span className="admin-section__badge" style={{ marginLeft: '0.4rem' }}>dormant</span>
                    )}
                  </td>
                  <td>
                    <small className="admin-section__text-muted">{user.email || '-'}</small>
                  </td>
                  <td>
                    <span className={`admin-section__badge admin-section__badge--${user.subscription_tier}`}>
                      {user.subscription_tier}
                    </span>
                  </td>
                  <td>
                    {user.stripe_subscription_id
                      ? <span className="admin-section__status admin-section__status--active">Subscribed</span>
                      : <small className="admin-section__text-muted">-</small>}
                  </td>
                  <td>
                    {user.subscription_expires_at
                      ? new Date(user.subscription_expires_at).toLocaleDateString()
                      : '-'}
                  </td>
                  <td>
                    <span className={`admin-section__status ${user.is_active ? 'admin-section__status--active' : 'admin-section__status--inactive'}`}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td>
                    <button
                      className="btn btn--secondary btn--small"
                      onClick={() => {
                        setSelectedUser(user);
                        setNewTier(user.subscription_tier);
                        setShowUpgradeModal(true);
                      }}
                      title="Change tier"
                    >
                      <span className="mdi mdi-pencil"></span>
                      Change Tier
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Current plan matrix (source of truth: /api/subscriptions/plans) */}
      <div style={{ marginTop: '3rem' }}>
        <h3 style={{ margin: '0 0 1rem', fontSize: '1.25rem' }}>Plan Matrix (2026 modular pricing)</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.5rem' }}>
          {allPlans.map((plan) => (
            <div key={plan.id} style={{
              background: 'white',
              border: '1px solid var(--color-border, #e5e7eb)',
              borderRadius: '8px',
              padding: '1.25rem'
            }}>
              <h4 style={{ margin: '0 0 0.25rem' }}>{plan.name}</h4>
              <p style={{ margin: '0 0 0.5rem', fontSize: '1.35rem', fontWeight: 700, color: 'var(--color-primary, #003399)' }}>
                €{plan.price_monthly}/month
              </p>
              <p style={{ margin: '0 0 0.5rem', fontSize: '0.8rem', color: '#6b7280' }}>
                €{plan.price_annual}/year · internal tier: {plan.tier}
              </p>
              {plan.includes && (
                <p style={{ margin: 0, fontSize: '0.8rem', color: '#6b7280' }}>
                  Includes: {plan.includes.join(', ')}
                </p>
              )}
              {plan.eligibility && (
                <p style={{ margin: '0.4rem 0 0', fontSize: '0.8rem', color: '#b45309' }}>
                  {plan.eligibility}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Change Tier Modal */}
      <AdminModal
        isOpen={showUpgradeModal}
        onClose={() => setShowUpgradeModal(false)}
        title="Change Internal Gating Tier"
        size="medium"
        footer={
          <>
            <button className="btn btn--secondary btn--small" onClick={() => setShowUpgradeModal(false)}>
              Cancel
            </button>
            <button className="btn btn--primary btn--small" onClick={handleUpgrade}>
              Update Tier
            </button>
          </>
        }
      >
        {selectedUser && (
          <div style={{ display: 'grid', gap: '1.5rem' }}>
            <div>
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>User</h4>
              <p style={{ margin: 0 }}>{selectedUser.email || selectedUser.full_name}</p>
            </div>
            <div>
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>Current Tier</h4>
              <span className={`admin-section__badge admin-section__badge--${selectedUser.subscription_tier}`}>
                {TIER_LABELS[selectedUser.subscription_tier] || selectedUser.subscription_tier}
              </span>
            </div>
            <div>
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>New Tier</h4>
              <select
                value={newTier}
                onChange={(e) => setNewTier(e.target.value)}
                className="admin-section__filter"
                style={{ width: '100%' }}
              >
                <option value="white">{TIER_LABELS.white}</option>
                <option value="yellow">{TIER_LABELS.yellow}</option>
                <option value="blue">{TIER_LABELS.blue}</option>
              </select>
              <p style={{ margin: '0.5rem 0 0', fontSize: '0.75rem', color: '#6b7280' }}>
                Note: this changes internal feature gating only. It does not create or cancel
                a Stripe subscription.
              </p>
            </div>
          </div>
        )}
      </AdminModal>
    </div>
  );
};
