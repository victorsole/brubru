/**
 * Legislative Updates Widget
 *
 * Shows recent changes to tracked legislative files on the dashboard.
 * Compact widget that links to the full My Tracked Files tab.
 */

import { useEffect, useRef } from 'react';
import Icon from '@mdi/react';
import {
  mdiHistory,
  mdiFileDocumentOutline,
  mdiAlertCircleOutline,
  mdiArrowRight,
  mdiClockOutline,
} from '@mdi/js';
import { useLegislativeTrains } from '../../hooks/use_legislative_trains';
import './legislative_updates_widget.css';

interface LegislativeUpdatesWidgetProps {
  onNavigateToTrackedFiles?: () => void;
}

export const LegislativeUpdatesWidget = ({ onNavigateToTrackedFiles }: LegislativeUpdatesWidgetProps) => {
  const {
    recentChanges,
    trackedFiles,
    isLoadingChanges,
    fetchRecentChanges,
    fetchTrackedFiles,
  } = useLegislativeTrains();

  const hasLoadedRef = useRef(false);

  useEffect(() => {
    if (hasLoadedRef.current) return;
    hasLoadedRef.current = true;

    const loadData = async () => {
      await fetchTrackedFiles();
      await fetchRecentChanges(168); // Last 7 days
    };

    loadData();
  }, []);

  const getChangeIcon = (changeType: string) => {
    switch (changeType) {
      case 'status_change':
        return mdiHistory;
      case 'new_document':
        return mdiFileDocumentOutline;
      case 'blocking':
        return mdiAlertCircleOutline;
      default:
        return mdiClockOutline;
    }
  };

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) {
      return `${diffDays}d ago`;
    }
    if (diffHours > 0) {
      return `${diffHours}h ago`;
    }
    return 'Just now';
  };

  // Don't show widget if no tracked files
  if (trackedFiles.length === 0) {
    return null;
  }

  return (
    <div className="legislative-updates-widget">
      <div className="legislative-updates-widget__header">
        <div className="legislative-updates-widget__title">
          <Icon path={mdiHistory} size={0.9} />
          <h3>Legislative Updates</h3>
        </div>
        <span className="legislative-updates-widget__badge">
          {trackedFiles.length} tracked
        </span>
      </div>

      <div className="legislative-updates-widget__content">
        {isLoadingChanges ? (
          <div className="legislative-updates-widget__loading">
            Loading updates...
          </div>
        ) : recentChanges.length === 0 ? (
          <div className="legislative-updates-widget__empty">
            <p>No recent changes to your tracked files</p>
          </div>
        ) : (
          <div className="legislative-updates-widget__list">
            {recentChanges.slice(0, 4).map((change, idx) => (
              <div
                key={idx}
                className="legislative-updates-widget__item"
                data-type={change.change_type}
              >
                <div className="legislative-updates-widget__item-icon">
                  <Icon path={getChangeIcon(change.change_type)} size={0.7} />
                </div>
                <div className="legislative-updates-widget__item-content">
                  <div className="legislative-updates-widget__item-title">
                    {change.title.length > 60
                      ? `${change.title.substring(0, 60)}...`
                      : change.title}
                  </div>
                  <div className="legislative-updates-widget__item-change">
                    {change.change_type === 'status_change' && (
                      <>
                        {change.old_value?.replace(/_/g, ' ')} →{' '}
                        <strong>{change.new_value?.replace(/_/g, ' ')}</strong>
                      </>
                    )}
                    {change.change_type === 'new_document' && 'New document published'}
                    {change.change_type === 'blocking' && 'Blocked - no progress'}
                  </div>
                </div>
                <div className="legislative-updates-widget__item-time">
                  {formatTimeAgo(change.changed_at)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {onNavigateToTrackedFiles && (
        <button
          className="legislative-updates-widget__view-all"
          onClick={onNavigateToTrackedFiles}
        >
          View all tracked files
          <Icon path={mdiArrowRight} size={0.7} />
        </button>
      )}
    </div>
  );
};
