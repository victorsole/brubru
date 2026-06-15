/**
 * EC Consultations Tab
 *
 * Main component for the EC Public Consultations tab in My EU Bubble.
 * Displays consultations from the Have Your Say portal with filtering and tracking.
 *
 * Access: Yellow+ tiers
 *
 * Created: January 2026
 */

import React, { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiCalendarCollapseHorizontal,
  mdiMagnify,
  mdiClose,
  mdiCalendarClock,
  mdiDomain,
  mdiTagOutline,
  mdiAccountGroupOutline,
  mdiOpenInNew,
  mdiBookmarkOutline,
  mdiBookmark,
  mdiClockAlertOutline,
  mdiRefresh,
} from '@mdi/js';

import {
  useConsultations,
  CONSULTATION_TYPE_INFO,
  STATUS_INFO,
} from '../../hooks/use_consultations';
import type {
  ConsultationListItem,
  ConsultationStatus,
} from '../../services/consultation_service';
import {
  getStatusLabel,
  formatDaysRemaining,
} from '../../services/consultation_service';
import { ConsultationDetail } from './consultation_detail';
import { MeubHeader } from './meub_header';
import './ec_consultations_tab.css';

// ============================================================================
// Types
// ============================================================================

interface ECConsultationsTabProps {
  className?: string;
}

// ============================================================================
// Component
// ============================================================================

export const ECConsultationsTab: React.FC<ECConsultationsTabProps> = ({ className }) => {
  const { t } = useTranslation();

  const {
    consultations,
    totalItems,
    filters,
    limit,
    offset,
    isLoadingConsultations,
    dgs,
    policyAreas,
    fetchConsultations,
    fetchReferenceData,
    fetchTrackedConsultations,
    setFilters,
    setPage,
    clearFilters,
    trackConsultation,
    untrackConsultation,
    fetchConsultationDetail,
    selectedConsultation,
    closeDetail,
    isTracking,
  } = useConsultations();

  const [searchQuery, setSearchQuery] = useState('');
  const [showDetail, setShowDetail] = useState(false);

  // Load data on mount
  useEffect(() => {
    fetchConsultations();
    fetchReferenceData();
    fetchTrackedConsultations();
  }, []);

  // Handle search
  const handleSearch = useCallback(() => {
    setFilters({ ...filters, search: searchQuery || undefined });
  }, [searchQuery, filters, setFilters]);

  // Handle search on Enter
  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  // Handle Policy-Interest lens (shared MEUB toggle)
  const handlePiToggle = (mine: boolean) => {
    setFilters({ ...filters, my_interests: mine });
  };

  // Handle status filter
  const handleStatusFilter = (status: ConsultationStatus | undefined) => {
    setFilters({ ...filters, status });
  };

  // Handle DG filter
  const handleDGFilter = (dg: string) => {
    setFilters({ ...filters, dg: dg || undefined });
  };

  // Handle policy area filter
  const handlePolicyAreaFilter = (policyArea: string) => {
    setFilters({ ...filters, policy_area: policyArea || undefined });
  };

  // Handle card click
  const handleCardClick = async (consultation: ConsultationListItem) => {
    await fetchConsultationDetail(consultation.id);
    setShowDetail(true);
  };

  // Handle track/untrack
  const handleTrackToggle = async (e: React.MouseEvent, consultation: ConsultationListItem) => {
    e.stopPropagation();
    if (consultation.is_tracked) {
      await untrackConsultation(consultation.id);
    } else {
      await trackConsultation(consultation.id);
    }
  };

  // Handle external link
  const handleOpenExternal = (e: React.MouseEvent, url: string) => {
    e.stopPropagation();
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  // Close detail modal
  const handleCloseDetail = () => {
    setShowDetail(false);
    closeDetail();
  };

  // Calculate pagination
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(totalItems / limit);

  return (
    <div className={`ec-consultations-tab ${className || ''}`}>
      {/* Header */}
      <MeubHeader
        icon={mdiCalendarCollapseHorizontal}
        accent="#f97316"
        title={t('bubble.consultations.title', 'EU Public Consultations')}
        subtitle={t(
          'bubble.consultations.subtitle',
          'Every open EU consultation in one place: the Commission’s Have Your Say and every EU agency'
        )}
      />

      {/* Filters */}
      <div className="ec-consultations-tab__filters">
        {/* Policy-Interest lens (My interests | All) — shared across MEUB */}
        <div className="ec-consultations-tab__pi-toggle" role="tablist">
          <button
            role="tab"
            aria-selected={filters.my_interests !== false}
            className={filters.my_interests !== false ? 'is-active' : ''}
            onClick={() => handlePiToggle(true)}
          >
            {t('bubble.consultations.myInterests', 'My interests')}
          </button>
          <button
            role="tab"
            aria-selected={filters.my_interests === false}
            className={filters.my_interests === false ? 'is-active' : ''}
            onClick={() => handlePiToggle(false)}
          >
            {t('bubble.consultations.all', 'All')}
          </button>
        </div>

        {/* Status chips */}
        <div className="ec-consultations-tab__filter-group">
          <span className="ec-consultations-tab__filter-label">
            {t('bubble.consultations.status', 'Status')}:
          </span>
          <div className="ec-consultations-tab__status-chips">
            {(['open', 'closed', 'outcome_published'] as ConsultationStatus[]).map((status) => (
              <button
                key={status}
                className={`ec-consultations-tab__status-chip ${
                  filters.status === status ? 'ec-consultations-tab__status-chip--active' : ''
                }`}
                onClick={() => handleStatusFilter(status === filters.status ? undefined : status)}
              >
                {getStatusLabel(status)}
              </button>
            ))}
          </div>
        </div>

        {/* DG dropdown */}
        <div className="ec-consultations-tab__filter-group">
          <span className="ec-consultations-tab__filter-label">
            {t('bubble.consultations.body', 'Body')}:
          </span>
          <select
            className="ec-consultations-tab__dropdown"
            value={filters.dg || ''}
            onChange={(e) => handleDGFilter(e.target.value)}
          >
            <option value="">{t('bubble.consultations.allBodies', 'All bodies')}</option>
            {dgs.map((dg) => (
              <option key={dg.code} value={dg.code}>
                {dg.code} - {dg.name}
              </option>
            ))}
          </select>
        </div>

        {/* Policy area dropdown */}
        <div className="ec-consultations-tab__filter-group">
          <span className="ec-consultations-tab__filter-label">
            {t('bubble.consultations.policyArea', 'Policy Area')}:
          </span>
          <select
            className="ec-consultations-tab__dropdown"
            value={filters.policy_area || ''}
            onChange={(e) => handlePolicyAreaFilter(e.target.value)}
          >
            <option value="">{t('bubble.consultations.allAreas', 'All Areas')}</option>
            {policyAreas.map((area) => (
              <option key={area.code} value={area.code}>
                {area.name}
              </option>
            ))}
          </select>
        </div>

        {/* Search */}
        <div className="ec-consultations-tab__filter-group" style={{ flex: 1 }}>
          <input
            type="text"
            className="ec-consultations-tab__search"
            placeholder={t('bubble.consultations.search', 'Search consultations...')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleSearchKeyDown}
          />
          <button
            className="ec-consultations-tab__status-chip"
            onClick={handleSearch}
            title={t('common.search', 'Search')}
          >
            <Icon path={mdiMagnify} size={0.8} />
          </button>
        </div>

        {/* Clear filters */}
        {(filters.status || filters.dg || filters.policy_area || filters.search) && (
          <button className="ec-consultations-tab__clear-filters" onClick={clearFilters}>
            <Icon path={mdiClose} size={0.7} />
            {t('bubble.consultations.clearFilters', 'Clear')}
          </button>
        )}
      </div>

      {/* Loading */}
      {isLoadingConsultations ? (
        <div className="ec-consultations-tab__loading">
          <Icon path={mdiRefresh} size={1.5} spin />
          <span style={{ marginLeft: '0.5rem' }}>
            {t('common.loading', 'Loading...')}
          </span>
        </div>
      ) : consultations.length === 0 ? (
        /* Empty state */
        <div className="ec-consultations-tab__empty">
          <Icon
            path={mdiCalendarCollapseHorizontal}
            size={3}
            className="ec-consultations-tab__empty-icon"
          />
          <p>{t('bubble.consultations.noResults', 'No consultations found')}</p>
          <button
            className="ec-consultations-tab__status-chip"
            onClick={clearFilters}
          >
            {t('bubble.consultations.clearFilters', 'Clear filters')}
          </button>
        </div>
      ) : (
        /* Consultation list */
        <>
          <div className="ec-consultations-tab__list">
            {consultations.map((consultation) => (
              <ConsultationCard
                key={consultation.id}
                consultation={consultation}
                onClick={() => handleCardClick(consultation)}
                onTrackToggle={(e) => handleTrackToggle(e, consultation)}
                onOpenExternal={(e) =>
                  consultation.portal_url && handleOpenExternal(e, consultation.portal_url)
                }
                isTracking={isTracking}
              />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="ec-consultations-tab__pagination">
              <button
                className="ec-consultations-tab__pagination-btn"
                onClick={() => setPage(Math.max(0, offset - limit))}
                disabled={offset === 0}
              >
                {t('common.previous', 'Previous')}
              </button>
              <span className="ec-consultations-tab__pagination-info">
                {t('common.pageOf', 'Page {{current}} of {{total}}', {
                  current: currentPage,
                  total: totalPages,
                })}
              </span>
              <button
                className="ec-consultations-tab__pagination-btn"
                onClick={() => setPage(offset + limit)}
                disabled={currentPage >= totalPages}
              >
                {t('common.next', 'Next')}
              </button>
            </div>
          )}
        </>
      )}

      {/* Detail modal */}
      {showDetail && selectedConsultation && (
        <ConsultationDetail
          consultation={selectedConsultation}
          onClose={handleCloseDetail}
          onTrack={() => trackConsultation(selectedConsultation.id)}
          onUntrack={() => untrackConsultation(selectedConsultation.id)}
          isTracking={isTracking}
        />
      )}
    </div>
  );
};

// ============================================================================
// Consultation Card Component
// ============================================================================

interface ConsultationCardProps {
  consultation: ConsultationListItem;
  onClick: () => void;
  onTrackToggle: (e: React.MouseEvent) => void;
  onOpenExternal: (e: React.MouseEvent) => void;
  isTracking: boolean;
}

const ConsultationCard: React.FC<ConsultationCardProps> = ({
  consultation,
  onClick,
  onTrackToggle,
  onOpenExternal,
  isTracking,
}) => {
  const { t } = useTranslation();

  const statusInfo = STATUS_INFO[consultation.status] || { name: 'Unknown', color: '#6b7280' };
  const typeInfo = CONSULTATION_TYPE_INFO[consultation.consultation_type] || {
    name: 'Initiative',
    color: '#6b7280',
  };

  const isUrgent = consultation.is_closing_soon && consultation.status === 'open';

  return (
    <div
      className={`consultation-card ${consultation.is_tracked ? 'consultation-card--tracked' : ''}`}
      onClick={onClick}
    >
      <div className="consultation-card__header">
        <h3 className="consultation-card__title">{consultation.title}</h3>
        <div className="consultation-card__badges">
          {isUrgent && (
            <span className="consultation-card__badge consultation-card__badge--closing-soon">
              <Icon path={mdiClockAlertOutline} size={0.5} />
              {t('bubble.consultations.closingSoon', 'Closing Soon')}
            </span>
          )}
          <span
            className={`consultation-card__badge consultation-card__badge--status-${consultation.status.replace('_', '-')}`}
            style={{ backgroundColor: `${statusInfo.color}20`, color: statusInfo.color }}
          >
            {statusInfo.name}
          </span>
          <span className="consultation-card__badge consultation-card__badge--type">
            {typeInfo.name}
          </span>
        </div>
      </div>

      <div className="consultation-card__meta">
        {consultation.dg_responsible && (
          <span className="consultation-card__meta-item">
            <Icon path={mdiDomain} size={0.6} className="consultation-card__meta-icon" />
            {consultation.dg_name || `DG ${consultation.dg_responsible}`}
          </span>
        )}
        {consultation.policy_areas.length > 0 && (
          <span className="consultation-card__meta-item">
            <Icon path={mdiTagOutline} size={0.6} className="consultation-card__meta-icon" />
            {consultation.policy_areas.slice(0, 2).join(', ')}
            {consultation.policy_areas.length > 2 && ` +${consultation.policy_areas.length - 2}`}
          </span>
        )}
        {consultation.feedback_count > 0 && (
          <span className="consultation-card__meta-item">
            <Icon path={mdiAccountGroupOutline} size={0.6} className="consultation-card__meta-icon" />
            {consultation.feedback_count.toLocaleString()}{' '}
            {t('bubble.consultations.responses', 'responses')}
          </span>
        )}
      </div>

      <div className="consultation-card__footer">
        <div
          className={`consultation-card__deadline ${
            isUrgent
              ? 'consultation-card__deadline--urgent'
              : 'consultation-card__deadline--normal'
          }`}
        >
          <Icon path={mdiCalendarClock} size={0.7} />
          {consultation.end_date ? (
            <>
              {t('bubble.consultations.deadline', 'Deadline')}:{' '}
              {new Date(consultation.end_date).toLocaleDateString()}
              {consultation.days_remaining !== undefined && consultation.days_remaining <= 30 && (
                <span> ({formatDaysRemaining(consultation.days_remaining)})</span>
              )}
            </>
          ) : (
            t('bubble.consultations.noDeadline', 'No deadline')
          )}
        </div>

        <div className="consultation-card__actions">
          <button
            className={`consultation-card__action-btn ${
              consultation.is_tracked
                ? 'consultation-card__action-btn--tracked'
                : 'consultation-card__action-btn--secondary'
            }`}
            onClick={onTrackToggle}
            disabled={isTracking}
            title={
              consultation.is_tracked
                ? t('bubble.consultations.untrack', 'Stop tracking')
                : t('bubble.consultations.track', 'Track this consultation')
            }
          >
            <Icon
              path={consultation.is_tracked ? mdiBookmark : mdiBookmarkOutline}
              size={0.7}
            />
            {consultation.is_tracked
              ? t('bubble.consultations.tracked', 'Tracked')
              : t('bubble.consultations.track', 'Track')}
          </button>

          {consultation.portal_url && (
            <button
              className="consultation-card__action-btn consultation-card__action-btn--primary"
              onClick={onOpenExternal}
              title={t('bubble.consultations.openPortal', 'Open in Have Your Say')}
            >
              <Icon path={mdiOpenInNew} size={0.7} />
              {t('bubble.consultations.view', 'View')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default ECConsultationsTab;
