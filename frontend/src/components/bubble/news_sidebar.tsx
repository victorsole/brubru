/**
 * News Sidebar Component
 *
 * Displays RSS feed entries from user's subscribed feeds.
 * Part of My EU Bubble - Phase 3: Frontend
 */

import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import { mdiRefresh, mdiCog, mdiChevronDown, mdiChevronUp, mdiDatabaseRefresh, mdiTrain, mdiDownload, mdiRobotOutline } from '@mdi/js';
import { useBubble } from '../../hooks/use_bubble';
import { useAuth } from '../../hooks/use_auth';
import './news_sidebar.css';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api`;

export const NewsSidebar = () => {
  const { t } = useTranslation();
  const {
    feedEntries,
    unreadCount,
    isLoadingFeeds,
    availableSources,
    fetchLatestFeeds,
    fetchAvailableSources,
    markAsRead,
    saveEntry,
  } = useBubble();

  const { token } = useAuth();

  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [showUnreadOnly, setShowUnreadOnly] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefreshTime, setLastRefreshTime] = useState<Date>(new Date());
  const [showAdminControls, setShowAdminControls] = useState(false);
  const [isRefreshingFeeds, setIsRefreshingFeeds] = useState(false);
  const [isRefreshingTrains, setIsRefreshingTrains] = useState(false);
  const [isFetchingEntries, setIsFetchingEntries] = useState(false);
  const [trainProgress, setTrainProgress] = useState(0);
  const [trainStatus, setTrainStatus] = useState<string>('');
  const [isEnrichingAI, setIsEnrichingAI] = useState(false);

  // Memoized refresh function
  const refreshFeeds = useCallback(() => {
    setIsRefreshing(true);
    fetchLatestFeeds({
      sources: selectedSources.length > 0 ? selectedSources : undefined,
      unread_only: showUnreadOnly,
    }).finally(() => {
      setIsRefreshing(false);
      setLastRefreshTime(new Date());
    });
  }, [selectedSources, showUnreadOnly, fetchLatestFeeds]);

  useEffect(() => {
    // Fetch available sources on mount
    fetchAvailableSources();
  }, []);

  useEffect(() => {
    // Fetch feeds when filters change
    refreshFeeds();
  }, [selectedSources, showUnreadOnly]);

  useEffect(() => {
    // Auto-refresh feeds every 5 minutes
    const AUTO_REFRESH_INTERVAL = 5 * 60 * 1000; // 5 minutes
    const intervalId = setInterval(refreshFeeds, AUTO_REFRESH_INTERVAL);

    // Cleanup on unmount
    return () => clearInterval(intervalId);
  }, [refreshFeeds]);

  const handleSourceToggle = (source: string) => {
    setSelectedSources(prev =>
      prev.includes(source)
        ? prev.filter(s => s !== source)
        : [...prev, source]
    );
  };

  const handleAllSources = () => {
    setSelectedSources([]);
  };

  const handleEntryClick = async (entry: typeof feedEntries[0]) => {
    if (!entry.is_read) {
      await markAsRead(entry.id);
    }
    window.open(entry.link, '_blank');
  };

  const handleSaveEntry = async (e: React.MouseEvent, entryId: string) => {
    e.stopPropagation();
    await saveEntry(entryId);
  };

  const handleRefreshFeedsDatabase = async () => {
    setIsRefreshingFeeds(true);
    try {
      const response = await fetch(`${API_BASE}/bubble/admin/refresh-feeds`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token && { Authorization: `Bearer ${token}` }) },
      });

      if (response.ok) {
        const data = await response.json();
        alert(data.message + '\n\n' + data.note);
        // Refresh the available sources after a delay
        setTimeout(() => {
          fetchAvailableSources();
          refreshFeeds();
        }, 3000);
      } else {
        alert('Failed to refresh feeds database');
      }
    } catch (error) {
      console.error('Error refreshing feeds database:', error);
      alert('Failed to refresh feeds database');
    } finally {
      setIsRefreshingFeeds(false);
    }
  };

  const handleRefreshLegislativeTrains = async () => {
    setIsRefreshingTrains(true);
    setTrainProgress(0);
    setTrainStatus('Starting...');

    try {
      const response = await fetch(`${API_BASE}/bubble/admin/refresh-legislative-trains`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token && { Authorization: `Bearer ${token}` }) },
      });

      if (response.ok) {
        // Start polling for progress
        const pollInterval = setInterval(async () => {
          try {
            const statusResponse = await fetch(`${API_BASE}/bubble/admin/legislative-trains-status`, {
              headers: { ...(token && { Authorization: `Bearer ${token}` }) },
            });
            if (statusResponse.ok) {
              const status = await statusResponse.json();
              setTrainProgress(status.progress);
              setTrainStatus(status.current_step);

              // Stop polling when complete or failed
              if (status.status === 'completed') {
                clearInterval(pollInterval);
                setIsRefreshingTrains(false);
                setTrainStatus('Completed!');
                setTimeout(() => {
                  setTrainProgress(0);
                  setTrainStatus('');
                }, 3000);
              } else if (status.status === 'failed') {
                clearInterval(pollInterval);
                setIsRefreshingTrains(false);
                setTrainStatus('Failed');
                alert('Legislative train scraping failed: ' + status.error);
                setTimeout(() => {
                  setTrainProgress(0);
                  setTrainStatus('');
                }, 3000);
              }
            }
          } catch (error) {
            console.error('Error checking progress:', error);
          }
        }, 1000); // Poll every second

        // Cleanup after 10 minutes (timeout)
        setTimeout(() => {
          clearInterval(pollInterval);
          if (isRefreshingTrains) {
            setIsRefreshingTrains(false);
            setTrainProgress(0);
            setTrainStatus('');
          }
        }, 10 * 60 * 1000);
      } else {
        const errorData = await response.json();
        alert('Failed to refresh legislative trains: ' + (errorData.detail || 'Unknown error'));
        setIsRefreshingTrains(false);
        setTrainProgress(0);
        setTrainStatus('');
      }
    } catch (error) {
      console.error('Error refreshing legislative trains:', error);
      alert('Failed to refresh legislative trains');
      setIsRefreshingTrains(false);
      setTrainProgress(0);
      setTrainStatus('');
    }
  };

  const handleFetchNewEntries = async () => {
    setIsFetchingEntries(true);
    try {
      const response = await fetch(`${API_BASE}/bubble/admin/fetch-entries`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token && { Authorization: `Bearer ${token}` }) },
      });

      if (response.ok) {
        const data = await response.json();
        alert(data.message + '\n\n' + data.note);
        // Auto-refresh the feed after a delay
        setTimeout(() => {
          refreshFeeds();
        }, 5000);
      } else {
        alert('Failed to fetch new entries');
      }
    } catch (error) {
      console.error('Error fetching new entries:', error);
      alert('Failed to fetch new entries');
    } finally {
      setIsFetchingEntries(false);
    }
  };

  const handleAIEnrichment = async () => {
    setIsEnrichingAI(true);
    try {
      const response = await fetch(`${API_BASE}/bubble/admin/enrich-entries-ai?hours=24&limit=50`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token && { Authorization: `Bearer ${token}` }) },
      });

      if (response.ok) {
        const data = await response.json();
        alert(`${data.message}\n\nStats:\n- Processed: ${data.stats.processed}\n- Enriched: ${data.stats.enriched}\n- Failed: ${data.stats.failed}`);
        // Auto-refresh the feed after enrichment
        setTimeout(() => {
          refreshFeeds();
        }, 2000);
      } else {
        const errorData = await response.json();
        alert('AI enrichment failed: ' + (errorData.detail || 'Unknown error'));
      }
    } catch (error) {
      console.error('Error enriching entries:', error);
      alert('Failed to enrich entries with AI');
    } finally {
      setIsEnrichingAI(false);
    }
  };

  return (
    <div className="news-sidebar">
      {/* Header */}
      <div className="news-sidebar__header">
        <div className="news-sidebar__header-left">
          <h3>{t('bubble.news.latestUpdates')}</h3>
          {unreadCount > 0 && (
            <span className="news-sidebar__unread-badge">{unreadCount}</span>
          )}
        </div>
        <button
          className={`news-sidebar__refresh-btn ${isRefreshing ? 'news-sidebar__refresh-btn--spinning' : ''}`}
          onClick={refreshFeeds}
          disabled={isRefreshing}
          title={`${t('bubble.news.lastUpdated')} ${lastRefreshTime.toLocaleTimeString()}`}
        >
          <Icon path={mdiRefresh} size={0.8} />
        </button>
      </div>

      {/* Filters */}
      <div className="news-sidebar__filters">
        <div className="news-sidebar__filter-group">
          <label className="news-sidebar__checkbox">
            <input
              type="checkbox"
              checked={showUnreadOnly}
              onChange={(e) => setShowUnreadOnly(e.target.checked)}
            />
            <span>{t('bubble.news.unreadOnly')}</span>
          </label>
        </div>

        <div className="news-sidebar__sources">
          <p className="news-sidebar__sources-label">{t('bubble.news.sources')}</p>

          {/* All Sources Button */}
          <button
            className={`news-sidebar__source-chip news-sidebar__source-chip--all ${
              selectedSources.length === 0 ? 'news-sidebar__source-chip--active' : ''
            }`}
            onClick={handleAllSources}
          >
            {t('bubble.news.all')}
          </button>

          {availableSources.map(source => (
            <label key={source} className="news-sidebar__source-chip">
              <input
                type="checkbox"
                checked={selectedSources.includes(source)}
                onChange={() => handleSourceToggle(source)}
              />
              <span>
                {source}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Admin Controls */}
      <div className="news-sidebar__admin">
        <button
          className="news-sidebar__admin-toggle"
          onClick={() => setShowAdminControls(!showAdminControls)}
        >
          <Icon path={mdiCog} size={0.7} />
          <span>{t('bubble.news.adminControls')}</span>
          <Icon path={showAdminControls ? mdiChevronUp : mdiChevronDown} size={0.7} />
        </button>

        {showAdminControls && (
          <div className="news-sidebar__admin-panel">
            <button
              className="news-sidebar__admin-btn news-sidebar__admin-btn--primary"
              onClick={handleFetchNewEntries}
              disabled={isFetchingEntries}
            >
              <Icon
                path={mdiDownload}
                size={0.8}
                className={isFetchingEntries ? 'spinning' : ''}
              />
              <span>{t('bubble.news.fetchNewEntries')}</span>
            </button>

            <button
              className="news-sidebar__admin-btn"
              onClick={handleRefreshFeedsDatabase}
              disabled={isRefreshingFeeds}
            >
              <Icon
                path={mdiDatabaseRefresh}
                size={0.8}
                className={isRefreshingFeeds ? 'spinning' : ''}
              />
              <span>{t('bubble.news.refreshSources')}</span>
            </button>

            <button
              className="news-sidebar__admin-btn"
              onClick={handleRefreshLegislativeTrains}
              disabled={isRefreshingTrains}
              style={{
                position: 'relative',
                overflow: 'hidden'
              }}
            >
              {isRefreshingTrains && (
                <div
                  style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    height: '100%',
                    width: `${trainProgress}%`,
                    background: 'rgba(6, 147, 227, 0.2)',
                    transition: 'width 0.3s ease',
                    zIndex: 0
                  }}
                />
              )}
              <Icon
                path={mdiTrain}
                size={0.8}
                className={isRefreshingTrains ? 'spinning' : ''}
                style={{ position: 'relative', zIndex: 1 }}
              />
              <span style={{ position: 'relative', zIndex: 1 }}>
                {isRefreshingTrains
                  ? `${trainProgress}% - ${trainStatus}`
                  : t('bubble.news.refreshTrains')}
              </span>
            </button>

            <button
              className="news-sidebar__admin-btn news-sidebar__admin-btn--ai"
              onClick={handleAIEnrichment}
              disabled={isEnrichingAI}
            >
              <Icon
                path={mdiRobotOutline}
                size={0.8}
                className={isEnrichingAI ? 'spinning' : ''}
              />
              <span>
                {isEnrichingAI ? t('bubble.news.enrichingAi') : t('bubble.news.aiEnrichEntries')}
              </span>
            </button>

            <p className="news-sidebar__admin-note" dangerouslySetInnerHTML={{ __html: t('bubble.news.fetchHelp') }} />
          </div>
        )}
      </div>

      {/* Feed Entries */}
      <div className="news-sidebar__entries">
        {isLoadingFeeds ? (
          <div className="news-sidebar__loading">{t('newsSidebar.loadingFeeds')}</div>
        ) : feedEntries.length === 0 ? (
          <div className="news-sidebar__empty">
            <p>{t('bubble.news.noEntries')}</p>
            <small>{t('bubble.news.tryFilters')}</small>
          </div>
        ) : (
          feedEntries.map(entry => (
            <div
              key={entry.id}
              className={`news-sidebar__entry ${!entry.is_read ? 'news-sidebar__entry--unread' : ''}`}
              onClick={() => handleEntryClick(entry)}
            >
              {/* Source badge */}
              <div className="news-sidebar__entry-header">
                <span className="news-sidebar__entry-source">
                  {entry.institution || 'News'}
                </span>
                <span className="news-sidebar__entry-time">
                  {formatTimeAgo(entry.published_at)}
                </span>
              </div>

              {/* Title */}
              <h4 className="news-sidebar__entry-title">{entry.title}</h4>

              {/* Summary */}
              {(entry.ai_summary || entry.summary) && (
                <p className="news-sidebar__entry-summary">
                  {entry.ai_summary || entry.summary}
                </p>
              )}

              {/* Categories */}
              {entry.categories && entry.categories.length > 0 && (
                <div className="news-sidebar__entry-categories">
                  {entry.categories.slice(0, 2).map((cat, idx) => (
                    <span key={idx} className="news-sidebar__entry-category">
                      {cat}
                    </span>
                  ))}
                </div>
              )}

              {/* Actions */}
              <div className="news-sidebar__entry-actions">
                <button
                  className={`news-sidebar__action-btn ${entry.is_saved ? 'news-sidebar__action-btn--active' : ''}`}
                  onClick={(e) => handleSaveEntry(e, entry.id)}
                  title={t('bubble.news.save')}
                >
                  {entry.is_saved ? '★' : '☆'}
                </button>
              </div>

              {/* Unread indicator */}
              {!entry.is_read && (
                <div className="news-sidebar__unread-dot" />
              )}
            </div>
          ))
        )}
      </div>

      {/* Load More */}
      {feedEntries.length > 0 && (
        <button
          className="news-sidebar__load-more"
          onClick={() => fetchLatestFeeds({
            sources: selectedSources.length > 0 ? selectedSources : undefined,
            unread_only: showUnreadOnly,
            limit: 100,
          })}
        >
          Load More
        </button>
      )}
    </div>
  );
};

// Helper function to format time ago
function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;

  return date.toLocaleDateString();
}
