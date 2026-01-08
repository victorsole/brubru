// frontend/src/components/admin/subscriptions_management.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import { AdminStatsCard } from './shared/admin_stats_card';
import { AdminModal } from './shared/admin_modal';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface SubscriptionTier {
  id: string;
  name: string;
  price_monthly?: number;
  price_yearly?: number;
  features?: Record<string, any>;
  limits?: {
    api_calls_per_day?: number;
    documents_per_month?: number;
    amendments_per_month?: number;
    storage_gb?: number;
  };
}

interface UserSubscription {
  id: string;  // Backend uses 'id', not 'user_id'
  email: string;  // Backend uses 'email', not 'user_email'
  full_name?: string;  // Backend uses 'full_name', not 'user_name'
  subscription_tier: string;
  is_active: boolean;
  created_at: string;
  last_login?: string;
  role: string;
  is_verified: boolean;
  policy_interests?: string[];
}

interface SubscriptionStats {
  by_tier: Record<string, number>;
  total_users: number;
  mrr?: number;
  churn_rate?: number;
  growth_rate?: number;
}

export const SubscriptionsManagement = () => {
  const { token } = useAuth();
  const [users, setUsers] = useState<UserSubscription[]>([]);
  const [tiers, setTiers] = useState<SubscriptionTier[]>([]);
  const [stats, setStats] = useState<SubscriptionStats | null>(null);
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

      // Fetch tiers
      const tiersResponse = await axios.get(`${API_BASE_URL}/api/subscriptions/tiers`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTiers(tiersResponse.data);

      // Fetch users with their subscriptions
      const usersResponse = await axios.get(`${API_BASE_URL}/api/admin/users`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { page_size: 200 } // Get users (max allowed by backend)
      });
      // Backend returns array directly, not wrapped in {users: [...]}
      const usersArray = Array.isArray(usersResponse.data) ? usersResponse.data : (usersResponse.data.users || []);
      setUsers(usersArray);

      // Calculate stats
      calculateStats(usersArray);

      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch data:', err);
      // Handle different error response formats
      let errorMessage = 'Failed to load subscription data';
      if (err.response?.data?.detail) {
        // If detail is an array (validation errors), stringify it
        if (Array.isArray(err.response.data.detail)) {
          errorMessage = err.response.data.detail.map((e: any) => e.msg || JSON.stringify(e)).join(', ');
        } else if (typeof err.response.data.detail === 'string') {
          errorMessage = err.response.data.detail;
        } else {
          errorMessage = JSON.stringify(err.response.data.detail);
        }
      }
      setError(errorMessage);
      setUsers([]);
      setTiers([]);
      setStats(null);
    } finally {
      setLoading(false);
    }
  };

  const calculateStats = (usersList: UserSubscription[]) => {
    const byTier: Record<string, number> = {};
    usersList.forEach(user => {
      const tier = user.subscription_tier || 'white';
      byTier[tier] = (byTier[tier] || 0) + 1;
    });

    // Calculate MRR (Monthly Recurring Revenue) - simplified
    const tierPrices: Record<string, number> = {
      white: 0,
      yellow: 29,
      blue: 99
    };

    const mrr = Object.entries(byTier).reduce((sum, [tier, count]) => {
      return sum + (tierPrices[tier] || 0) * count;
    }, 0);

    setStats({
      by_tier: byTier,
      total_users: usersList.length,
      mrr: mrr,
      churn_rate: 0, // Would need historical data
      growth_rate: 0 // Would need historical data
    });
  };

  const handleUpgrade = async () => {
    if (!selectedUser || !newTier) return;

    try {
      await axios.patch(
        `${API_BASE_URL}/api/admin/users/${selectedUser.id}`,
        { subscription_tier: newTier },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      // Refresh data
      await fetchData();
      setShowUpgradeModal(false);
      setSelectedUser(null);
      alert('User subscription tier updated successfully');
    } catch (err: any) {
      console.error('Failed to upgrade user:', err);
      alert(err.response?.data?.detail || 'Failed to update subscription tier');
    }
  };

  // Defensive check to ensure users is an array
  const filteredUsers = Array.isArray(users) ? users.filter(user => {
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
  }) : [];

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

  return (
    <div className="admin-section">
      <div className="admin-section__header">
        <h2>Subscriptions & Billing</h2>
        <button className="btn btn--primary btn--small" onClick={fetchData}>
          <span className="mdi mdi-refresh"></span>
          Refresh
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
          <AdminStatsCard
            icon="account-multiple"
            title="Total Users"
            value={stats.total_users}
            subtitle={`${stats.by_tier.white || 0} free users`}
          />
          <AdminStatsCard
            icon="cash-multiple"
            title="Monthly Recurring Revenue"
            value={`€${stats.mrr?.toLocaleString() || 0}`}
            subtitle="Estimated MRR"
            variant="success"
          />
          <AdminStatsCard
            icon="star"
            title="Yellow Tier"
            value={stats.by_tier.yellow || 0}
            subtitle="Professional users"
            variant="warning"
          />
          <AdminStatsCard
            icon="crown"
            title="Blue Tier"
            value={stats.by_tier.blue || 0}
            subtitle="Enterprise users"
            variant="default"
          />
        </div>
      )}

      <div className="admin-section__header" style={{ marginTop: '2rem' }}>
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
            <option value="white">White (Free)</option>
            <option value="yellow">Yellow (Pro)</option>
            <option value="blue">Blue (Enterprise)</option>
          </select>
        </div>
      </div>

      <div className="admin-section__table-container" style={{ marginTop: '1rem' }}>
        <table className="admin-section__table">
          <thead>
            <tr>
              <th>User</th>
              <th>Email</th>
              <th>Current Tier</th>
              <th>Status</th>
              <th>Member Since</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ textAlign: 'center', padding: '2rem' }}>
                  No users found
                </td>
              </tr>
            ) : (
              filteredUsers.map((user) => (
                <tr key={user.id}>
                  <td>
                    <strong>{user.full_name || 'N/A'}</strong>
                  </td>
                  <td>
                    <small className="admin-section__text-muted">{user.email}</small>
                  </td>
                  <td>
                    <span className={`admin-section__badge admin-section__badge--${user.subscription_tier}`}>
                      {user.subscription_tier}
                    </span>
                  </td>
                  <td>
                    <span className={`admin-section__status ${user.is_active ? 'admin-section__status--active' : 'admin-section__status--inactive'}`}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td>{new Date(user.created_at).toLocaleDateString()}</td>
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

      {/* Subscription Tiers Info */}
      <div style={{ marginTop: '3rem' }}>
        <h3 style={{ margin: '0 0 1rem', fontSize: '1.25rem' }}>Subscription Tiers</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem' }}>
          {tiers.map((tier) => (
            <div key={tier.id} style={{
              background: 'white',
              border: '1px solid var(--color-border, #e5e7eb)',
              borderRadius: '8px',
              padding: '1.5rem'
            }}>
              <h4 style={{ margin: '0 0 0.5rem', textTransform: 'capitalize' }}>{tier.name}</h4>
              {tier.price_monthly !== undefined && (
                <p style={{ margin: '0 0 1rem', fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-primary, #003399)' }}>
                  €{tier.price_monthly}/month
                </p>
              )}
              {tier.price_yearly !== undefined && (
                <p style={{ margin: '0 0 1rem', fontSize: '0.875rem', color: '#6b7280' }}>
                  or €{tier.price_yearly}/year
                </p>
              )}
              {tier.limits && (
                <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>
                  <p style={{ margin: '0.5rem 0' }}>
                    <strong>Limits:</strong>
                  </p>
                  <ul style={{ margin: '0.5rem 0', paddingLeft: '1.5rem' }}>
                    {tier.limits.api_calls_per_day && (
                      <li>{tier.limits.api_calls_per_day} API calls/day</li>
                    )}
                    {tier.limits.documents_per_month && (
                      <li>{tier.limits.documents_per_month} documents/month</li>
                    )}
                    {tier.limits.amendments_per_month && (
                      <li>{tier.limits.amendments_per_month} amendments/month</li>
                    )}
                    {tier.limits.storage_gb && (
                      <li>{tier.limits.storage_gb} GB storage</li>
                    )}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Change Tier Modal */}
      <AdminModal
        isOpen={showUpgradeModal}
        onClose={() => setShowUpgradeModal(false)}
        title="Change Subscription Tier"
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
              <p style={{ margin: 0 }}>{selectedUser.email}</p>
            </div>
            <div>
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>Current Tier</h4>
              <span className={`admin-section__badge admin-section__badge--${selectedUser.subscription_tier}`}>
                {selectedUser.subscription_tier}
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
                <option value="white">White (Free)</option>
                <option value="yellow">Yellow (Professional)</option>
                <option value="blue">Blue (Enterprise)</option>
              </select>
            </div>
          </div>
        )}
      </AdminModal>
    </div>
  );
};
