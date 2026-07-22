// frontend/src/components/admin/user_management.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/use_auth';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface AdminUser {
  id: string;
  email: string | null;
  full_name: string | null;
  organization: string | null;
  role: string;
  subscription_tier: string;
  subscription_expires_at: string | null;
  is_active: boolean;
  is_dormant: boolean;
  created_at: string;
  last_login: string | null;
}

export const UserManagement = () => {
  const { token, impersonate } = useAuth();
  const navigate = useNavigate();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [impersonating, setImpersonating] = useState<string | null>(null);

  useEffect(() => {
    fetchUsers();
  }, [page]);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/admin/users`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { page, page_size: 50, search: searchQuery || undefined }
      });
      setUsers(Array.isArray(response.data?.users) ? response.data.users : []);
      setTotal(response.data?.total || 0);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch users:', err);
      setError(err.response?.data?.detail || 'Failed to load users');
      setUsers([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setPage(1);
    fetchUsers();
  };

  const handleImpersonate = async (user: AdminUser) => {
    if (!confirm(`View Brubru as ${user.email || user.full_name}? Your admin session is kept and you can exit any time from the banner.`)) {
      return;
    }
    try {
      setImpersonating(user.id);
      // 1. Mint the short-lived token for the target user (logged server-side)
      const tokenRes = await axios.post(
        `${API_BASE_URL}/api/admin/users/${user.id}/impersonate`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const targetToken = tokenRes.data.access_token;

      // 2. Fetch the canonical user object with the target token.
      // Use a bare axios instance: the global interceptor in use_auth would
      // otherwise overwrite the Authorization header with the admin token.
      const bareAxios = axios.create();
      const meRes = await bareAxios.get(`${API_BASE_URL}/api/auth/me`, {
        headers: { Authorization: `Bearer ${targetToken}` }
      });

      // 3. Swap the session (admin session is stashed in the auth store)
      impersonate(targetToken, meRes.data);
      navigate('/my-eu-bubble');
    } catch (err: any) {
      console.error('Impersonation failed:', err);
      alert(err.response?.data?.detail || 'Failed to impersonate user');
    } finally {
      setImpersonating(null);
    }
  };

  if (loading && users.length === 0) {
    return <div className="admin-section__loading">Loading users...</div>;
  }

  if (error && users.length === 0) {
    return (
      <div className="admin-section__error">
        <p>{error}</p>
        <button className="btn btn--primary btn--small" onClick={fetchUsers}>Retry</button>
      </div>
    );
  }

  return (
    <div className="admin-section">
      <div className="admin-section__header">
        <h2>User Management</h2>
        <div className="admin-section__actions">
          <input
            type="text"
            placeholder="Search users..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            className="admin-section__search"
          />
          <button className="btn btn--primary btn--small" onClick={handleSearch}>
            Search
          </button>
        </div>
      </div>

      <div className="admin-section__stats">
        <span>Total Users: <strong>{total}</strong></span>
        <span>Showing: <strong>{users.length}</strong></span>
      </div>

      <div className="admin-section__table-container">
        <table className="admin-section__table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Name</th>
              <th>Organisation</th>
              <th>Role</th>
              <th>Tier</th>
              <th>Status</th>
              <th>Created</th>
              <th>Last Login</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>{user.email || <small className="admin-section__text-muted">(no email)</small>}</td>
                <td>
                  {user.full_name || '-'}
                  {user.is_dormant && (
                    <span className="admin-section__badge" style={{ marginLeft: '0.4rem' }}>dormant</span>
                  )}
                </td>
                <td>{user.organization || '-'}</td>
                <td>
                  <span className={`admin-section__badge ${user.role === 'admin' ? 'admin-section__badge--admin' : ''}`}>
                    {user.role}
                  </span>
                </td>
                <td>
                  <span className={`admin-section__badge admin-section__badge--${user.subscription_tier}`}>
                    {user.subscription_tier}
                  </span>
                  {user.subscription_expires_at && (
                    <><br /><small className="admin-section__text-muted">
                      until {new Date(user.subscription_expires_at).toLocaleDateString()}
                    </small></>
                  )}
                </td>
                <td>
                  <span className={`admin-section__status ${user.is_active ? 'admin-section__status--active' : 'admin-section__status--inactive'}`}>
                    {user.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td>{new Date(user.created_at).toLocaleDateString()}</td>
                <td>{user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never'}</td>
                <td>
                  {user.role !== 'admin' && (
                    <button
                      className="btn btn--secondary btn--small"
                      onClick={() => handleImpersonate(user)}
                      disabled={impersonating !== null}
                      title="View Brubru as this user"
                    >
                      <span className="mdi mdi-account-switch"></span>
                      {impersonating === user.id ? '...' : 'Impersonate'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > 50 && (
        <div className="admin-section__pagination">
          <button
            className="btn btn--secondary btn--small"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </button>
          <span>Page {page} of {Math.ceil(total / 50)}</span>
          <button
            className="btn btn--secondary btn--small"
            onClick={() => setPage(p => p + 1)}
            disabled={page >= Math.ceil(total / 50)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};
