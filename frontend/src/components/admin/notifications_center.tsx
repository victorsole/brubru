// frontend/src/components/admin/notifications_center.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import { AdminStatsCard } from './shared/admin_stats_card';
import { AdminModal } from './shared/admin_modal';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface Notification {
  id: string;
  user_id: string;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export const NotificationsCenter = () => {
  const { token } = useAuth();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newNotification, setNewNotification] = useState({
    type: 'system',
    title: '',
    message: '',
    target: 'all'
  });

  useEffect(() => {
    fetchNotifications();
  }, []);

  const fetchNotifications = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/notifications`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      // Handle both array and object response formats
      if (Array.isArray(response.data)) {
        setNotifications(response.data);
        setError(null);
      } else if (response.data.notifications && Array.isArray(response.data.notifications)) {
        // Backend returns {notifications: [...], unread_count: ..., total: ...}
        setNotifications(response.data.notifications);
        setError(null);
      } else {
        console.warn('Notifications response is not an array:', response.data);
        setNotifications([]);
        setError('Invalid response format from server');
      }
    } catch (err: any) {
      console.error('Failed to fetch notifications:', err);
      setError(err.response?.data?.detail || 'Failed to load notifications');
      setNotifications([]);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateNotification = async () => {
    if (!newNotification.title || !newNotification.message) {
      alert('Please fill in all fields');
      return;
    }

    try {
      // This would require a backend endpoint to create notifications for all users
      // For now, we'll show a placeholder
      alert('Notification functionality coming soon. This would send notifications to users based on the target criteria.');
      setShowCreateModal(false);
      setNewNotification({
        type: 'system',
        title: '',
        message: '',
        target: 'all'
      });
    } catch (err: any) {
      console.error('Failed to create notification:', err);
      alert('Failed to send notification');
    }
  };

  const handleDeleteNotification = async (id: string) => {
    if (!confirm('Are you sure you want to delete this notification?')) return;

    try {
      await axios.delete(`${API_BASE_URL}/api/notifications/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setNotifications(notifications.filter(n => n.id !== id));
    } catch (err: any) {
      console.error('Failed to delete notification:', err);
      alert('Failed to delete notification');
    }
  };

  // Defensive checks to ensure notifications is an array
  const filteredNotifications = Array.isArray(notifications) ? notifications.filter(notif => {
    if (typeFilter !== 'all' && notif.type !== typeFilter) return false;
    return true;
  }) : [];

  const stats = {
    total: Array.isArray(notifications) ? notifications.length : 0,
    unread: Array.isArray(notifications) ? notifications.filter(n => !n.is_read).length : 0,
    system: Array.isArray(notifications) ? notifications.filter(n => n.type === 'system').length : 0,
    feature: Array.isArray(notifications) ? notifications.filter(n => n.type === 'feature').length : 0
  };

  if (loading) {
    return <div className="admin-section__loading">Loading notifications...</div>;
  }

  return (
    <div className="admin-section">
      <div className="admin-section__header">
        <h2>Notifications Center</h2>
        <div className="admin-section__actions">
          <button
            className="btn btn--success btn--small"
            onClick={() => setShowCreateModal(true)}
          >
            <span className="mdi mdi-plus"></span>
            Create Notification
          </button>
          <button className="btn btn--primary btn--small" onClick={fetchNotifications}>
            <span className="mdi mdi-refresh"></span>
            Refresh
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
        <AdminStatsCard
          icon="bell"
          title="Total Sent"
          value={stats.total}
          subtitle="All notifications"
        />
        <AdminStatsCard
          icon="bell-ring"
          title="Unread"
          value={stats.unread}
          subtitle="Pending read"
          variant="warning"
        />
        <AdminStatsCard
          icon="information"
          title="System"
          value={stats.system}
          subtitle="System announcements"
        />
        <AdminStatsCard
          icon="star"
          title="Features"
          value={stats.feature}
          subtitle="Feature updates"
          variant="success"
        />
      </div>

      <div className="admin-section__header" style={{ marginTop: '2rem' }}>
        <h3 style={{ margin: 0, fontSize: '1.25rem' }}>All Notifications</h3>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="admin-section__filter"
        >
          <option value="all">All Types</option>
          <option value="system">System</option>
          <option value="feature">Feature</option>
          <option value="maintenance">Maintenance</option>
        </select>
      </div>

      <div className="admin-section__table-container" style={{ marginTop: '1rem' }}>
        <table className="admin-section__table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Title</th>
              <th>Message</th>
              <th>Status</th>
              <th>Sent</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredNotifications.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ textAlign: 'center', padding: '2rem' }}>
                  {error ? error : 'No notifications found'}
                </td>
              </tr>
            ) : (
              filteredNotifications.map((notif) => (
                <tr key={notif.id}>
                  <td>
                    <span className={`admin-section__badge admin-section__badge--${notif.type}`}>
                      {notif.type}
                    </span>
                  </td>
                  <td><strong>{notif.title}</strong></td>
                  <td>
                    <div style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {notif.message?.substring(0, 100)}
                      {notif.message?.length > 100 ? '...' : ''}
                    </div>
                  </td>
                  <td>
                    <span className={`admin-section__status ${notif.is_read ? 'admin-section__status--inactive' : 'admin-section__status--active'}`}>
                      {notif.is_read ? 'Read' : 'Unread'}
                    </span>
                  </td>
                  <td>{new Date(notif.created_at).toLocaleString()}</td>
                  <td>
                    <button
                      className="btn btn--secondary btn--small"
                      onClick={() => handleDeleteNotification(notif.id)}
                      title="Delete"
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

      {/* Create Notification Modal */}
      <AdminModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Create Notification"
        size="medium"
        footer={
          <>
            <button className="btn btn--secondary btn--small" onClick={() => setShowCreateModal(false)}>
              Cancel
            </button>
            <button className="btn btn--primary btn--small" onClick={handleCreateNotification}>
              Send Notification
            </button>
          </>
        }
      >
        <div style={{ display: 'grid', gap: '1.5rem' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem', fontWeight: 600 }}>
              Type
            </label>
            <select
              value={newNotification.type}
              onChange={(e) => setNewNotification({ ...newNotification, type: e.target.value })}
              className="admin-section__filter"
              style={{ width: '100%' }}
            >
              <option value="system">System Announcement</option>
              <option value="feature">Feature Update</option>
              <option value="maintenance">Maintenance Alert</option>
            </select>
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem', fontWeight: 600 }}>
              Target Audience
            </label>
            <select
              value={newNotification.target}
              onChange={(e) => setNewNotification({ ...newNotification, target: e.target.value })}
              className="admin-section__filter"
              style={{ width: '100%' }}
            >
              <option value="all">All Users</option>
              <option value="white">White Tier Only</option>
              <option value="yellow">Yellow Tier Only</option>
              <option value="blue">Blue Tier Only</option>
            </select>
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem', fontWeight: 600 }}>
              Title
            </label>
            <input
              type="text"
              value={newNotification.title}
              onChange={(e) => setNewNotification({ ...newNotification, title: e.target.value })}
              className="admin-section__search"
              style={{ width: '100%' }}
              placeholder="Notification title"
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem', fontWeight: 600 }}>
              Message
            </label>
            <textarea
              value={newNotification.message}
              onChange={(e) => setNewNotification({ ...newNotification, message: e.target.value })}
              style={{
                width: '100%',
                padding: '0.5rem 0.75rem',
                border: '1px solid var(--color-border, #d1d5db)',
                borderRadius: '6px',
                fontSize: '0.875rem',
                minHeight: '120px',
                fontFamily: 'inherit'
              }}
              placeholder="Notification message"
            />
          </div>
        </div>
      </AdminModal>
    </div>
  );
};
