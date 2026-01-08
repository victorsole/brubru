// frontend/src/components/admin/user_management.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface User {
  id: string;
  email: string;
  full_name: string | null;
  organization: string | null;
  role: string;
  subscription_tier: string;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

export const UserManagement = () => {
  const { token } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

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
      setUsers([]); // Reset to empty array on error
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setPage(1);
    fetchUsers();
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
        <span>Showing: <strong>{Array.isArray(users) ? users.length : 0}</strong></span>
      </div>

      <div className="admin-section__table-container">
        <table className="admin-section__table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Name</th>
              <th>Organization</th>
              <th>Role</th>
              <th>Tier</th>
              <th>Status</th>
              <th>Created</th>
              <th>Last Login</th>
            </tr>
          </thead>
          <tbody>
            {Array.isArray(users) && users.map((user) => (
              <tr key={user.id}>
                <td>{user.email}</td>
                <td>{user.full_name || '-'}</td>
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
                </td>
                <td>
                  <span className={`admin-section__status ${user.is_active ? 'admin-section__status--active' : 'admin-section__status--inactive'}`}>
                    {user.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td>{new Date(user.created_at).toLocaleDateString()}</td>
                <td>{user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never'}</td>
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
