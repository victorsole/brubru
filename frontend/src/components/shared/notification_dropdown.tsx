/**
 * Notification Dropdown Component
 *
 * Bell icon with dropdown panel showing recent notifications.
 * Used in My EU Bubble header.
 */

import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiBell,
  mdiBellOutline,
  mdiAlertCircle,
  mdiCalendarClock,
  mdiNewspaper,
  mdiFileDocument,
  mdiFileEdit,
  mdiCheckAll
} from '@mdi/js';
import { useNotifications, formatRelativeTime, type Notification } from '../../hooks/use_notifications';
import { useAuth } from '../../hooks/use_auth';
import './notification_dropdown.css';

// Get icon for notification type
const getIconPath = (type: string): string => {
  switch (type) {
    case 'status_change':
      return mdiAlertCircle;
    case 'deadline':
      return mdiCalendarClock;
    case 'new_feed_entry':
      return mdiNewspaper;
    case 'policy_update':
      return mdiFileDocument;
    case 'amendment_update':
      return mdiFileEdit;
    default:
      return mdiBell;
  }
};

// Get color for priority
const getPriorityColor = (priority: string): string => {
  switch (priority) {
    case 'urgent':
      return '#dc2626';
    case 'high':
      return '#ea580c';
    case 'normal':
      return '#0693E3';
    default:
      return '#6b7280';
  }
};

export const NotificationDropdown = () => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const {
    notifications,
    unreadCount,
    isLoading,
    fetchNotifications,
    fetchUnreadCount,
    markAsRead,
    markAllAsRead
  } = useNotifications();

  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Fetch notifications on mount and set up polling
  useEffect(() => {
    if (token) {
      fetchNotifications(token);

      // Poll for unread count every 60 seconds
      const interval = setInterval(() => {
        fetchUnreadCount(token);
      }, 60000);

      return () => clearInterval(interval);
    }
  }, [token, fetchNotifications, fetchUnreadCount]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Refresh notifications when dropdown opens
  useEffect(() => {
    if (isOpen && token) {
      fetchNotifications(token);
    }
  }, [isOpen, token, fetchNotifications]);

  const handleToggle = () => {
    setIsOpen(!isOpen);
  };

  const handleNotificationClick = (notification: Notification) => {
    if (token && !notification.is_read) {
      markAsRead(token, notification.id);
    }

    // Navigate to action URL if present
    if (notification.action_url) {
      window.location.href = notification.action_url;
    }

    setIsOpen(false);
  };

  const handleMarkAllRead = () => {
    if (token) {
      markAllAsRead(token);
    }
  };

  // Calculate dropdown position
  const getDropdownStyle = (): React.CSSProperties => {
    if (!buttonRef.current) return {};

    const rect = buttonRef.current.getBoundingClientRect();
    return {
      position: 'fixed',
      top: `${rect.bottom + 8}px`,
      right: `${window.innerWidth - rect.right}px`,
      zIndex: 10000
    };
  };

  const dropdownContent = isOpen && (
    <div
      ref={dropdownRef}
      className="notification-dropdown__panel"
      style={getDropdownStyle()}
    >
      <div className="notification-dropdown__header">
        <h3>{t('notifications.title')}</h3>
        {unreadCount > 0 && (
          <button
            className="notification-dropdown__mark-all"
            onClick={handleMarkAllRead}
            title={t('common.markAllRead')}
          >
            <Icon path={mdiCheckAll} size={0.8} />
            <span>{t('notifications.markAllRead')}</span>
          </button>
        )}
      </div>

      <div className="notification-dropdown__list">
        {isLoading && notifications.length === 0 ? (
          <div className="notification-dropdown__empty">
            {t('common.loading')}
          </div>
        ) : notifications.length === 0 ? (
          <div className="notification-dropdown__empty">
            <Icon path={mdiBellOutline} size={2} color="#9ca3af" />
            <p>{t('notifications.noNotifications')}</p>
          </div>
        ) : (
          notifications.slice(0, 10).map((notification) => (
            <div
              key={notification.id}
              className={`notification-dropdown__item ${
                !notification.is_read ? 'notification-dropdown__item--unread' : ''
              }`}
              onClick={() => handleNotificationClick(notification)}
            >
              <div
                className="notification-dropdown__icon"
                style={{ color: getPriorityColor(notification.priority) }}
              >
                <Icon path={getIconPath(notification.notification_type)} size={1} />
              </div>
              <div className="notification-dropdown__content">
                <div className="notification-dropdown__title">
                  {notification.title}
                </div>
                <div className="notification-dropdown__message">
                  {notification.message}
                </div>
                <div className="notification-dropdown__time">
                  {formatRelativeTime(notification.created_at)}
                </div>
              </div>
              {!notification.is_read && (
                <div className="notification-dropdown__unread-dot" />
              )}
            </div>
          ))
        )}
      </div>

      {notifications.length > 10 && (
        <div className="notification-dropdown__footer">
          <button className="notification-dropdown__view-all">
            {t('notifications.viewAll')}
          </button>
        </div>
      )}
    </div>
  );

  return (
    <div className="notification-dropdown">
      <button
        ref={buttonRef}
        className={`notification-dropdown__trigger ${isOpen ? 'notification-dropdown__trigger--active' : ''}`}
        onClick={handleToggle}
        aria-label={unreadCount > 0 ? t('notifications.ariaUnread', { count: unreadCount }) : t('notifications.ariaNone')}
      >
        <Icon
          path={unreadCount > 0 ? mdiBell : mdiBellOutline}
          size={1.1}
          color={unreadCount > 0 ? '#0693E3' : '#6b7280'}
        />
        {unreadCount > 0 && (
          <span className="notification-dropdown__badge">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {/* Render dropdown via portal to escape stacking context */}
      {createPortal(dropdownContent, document.body)}
    </div>
  );
};
