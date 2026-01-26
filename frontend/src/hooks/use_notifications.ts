/**
 * Notifications State Management
 *
 * Zustand store for managing user notifications.
 * Handles fetching, marking as read, and polling for updates.
 */

import { create } from 'zustand';
import axios from 'axios';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api`;

// Types
export interface Notification {
  id: string;
  user_id: string;
  notification_type: string;
  title: string;
  message: string;
  action_url?: string;
  metadata?: Record<string, unknown>;
  related_entity_type?: string;
  related_entity_id?: string;
  priority: 'low' | 'normal' | 'high' | 'urgent';
  is_read: boolean;
  created_at: string;
  read_at?: string;
}

interface NotificationsState {
  notifications: Notification[];
  unreadCount: number;
  isLoading: boolean;
  error: string | null;
  lastFetched: Date | null;

  // Actions
  fetchNotifications: (token: string, unreadOnly?: boolean) => Promise<void>;
  fetchUnreadCount: (token: string) => Promise<void>;
  markAsRead: (token: string, notificationId: string) => Promise<void>;
  markAllAsRead: (token: string) => Promise<void>;
  deleteNotification: (token: string, notificationId: string) => Promise<void>;
  clearError: () => void;
}

export const useNotifications = create<NotificationsState>((set, get) => ({
  notifications: [],
  unreadCount: 0,
  isLoading: false,
  error: null,
  lastFetched: null,

  fetchNotifications: async (token: string, unreadOnly = false) => {
    set({ isLoading: true, error: null });

    try {
      const response = await axios.get(`${API_BASE}/notifications`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { unread_only: unreadOnly, limit: 50 }
      });

      set({
        notifications: response.data.notifications,
        unreadCount: response.data.unread_count,
        isLoading: false,
        lastFetched: new Date()
      });
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to fetch notifications';
      console.error('Failed to fetch notifications:', error);
      set({ error: errorMessage, isLoading: false });
    }
  },

  fetchUnreadCount: async (token: string) => {
    try {
      const response = await axios.get(`${API_BASE}/notifications/unread-count`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      set({ unreadCount: response.data.unread_count });
    } catch (error) {
      console.error('Failed to fetch unread count:', error);
    }
  },

  markAsRead: async (token: string, notificationId: string) => {
    try {
      await axios.post(
        `${API_BASE}/notifications/${notificationId}/read`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );

      // Update local state
      const { notifications, unreadCount } = get();
      const notification = notifications.find(n => n.id === notificationId);

      if (notification && !notification.is_read) {
        set({
          notifications: notifications.map(n =>
            n.id === notificationId
              ? { ...n, is_read: true, read_at: new Date().toISOString() }
              : n
          ),
          unreadCount: Math.max(0, unreadCount - 1)
        });
      }
    } catch (error) {
      console.error('Failed to mark notification as read:', error);
    }
  },

  markAllAsRead: async (token: string) => {
    try {
      await axios.post(
        `${API_BASE}/notifications/read-all`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );

      // Update local state
      const { notifications } = get();
      set({
        notifications: notifications.map(n => ({
          ...n,
          is_read: true,
          read_at: n.read_at || new Date().toISOString()
        })),
        unreadCount: 0
      });
    } catch (error) {
      console.error('Failed to mark all notifications as read:', error);
    }
  },

  deleteNotification: async (token: string, notificationId: string) => {
    try {
      await axios.delete(`${API_BASE}/notifications/${notificationId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      // Update local state
      const { notifications, unreadCount } = get();
      const notification = notifications.find(n => n.id === notificationId);

      set({
        notifications: notifications.filter(n => n.id !== notificationId),
        unreadCount: notification && !notification.is_read
          ? Math.max(0, unreadCount - 1)
          : unreadCount
      });
    } catch (error) {
      console.error('Failed to delete notification:', error);
    }
  },

  clearError: () => set({ error: null })
}));

// Helper to get notification icon based on type
export const getNotificationIcon = (type: string): string => {
  switch (type) {
    case 'status_change':
      return 'mdiAlertCircle';
    case 'deadline':
      return 'mdiCalendarClock';
    case 'new_feed_entry':
      return 'mdiNewspaper';
    case 'policy_update':
      return 'mdiFileDocument';
    case 'amendment_update':
      return 'mdiFileEdit';
    default:
      return 'mdiBell';
  }
};

// Helper to format relative time
export const formatRelativeTime = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short'
  });
};
