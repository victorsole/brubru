/**
 * Track File Button Component
 *
 * Reusable button for tracking legislative files.
 * Can be used in news sidebar, chat interface, or search results.
 */

import { useState } from 'react';
import Icon from '@mdi/react';
import { mdiStarOutline, mdiStar, mdiLoading } from '@mdi/js';
import { useTranslation } from 'react-i18next';
import { useLegislativeTrains } from '../../hooks/use_legislative_trains';
import './track_file_button.css';

interface TrackFileButtonProps {
  procedureRef?: string;
  carriageId?: string;
  isTracked?: boolean;
  variant?: 'icon' | 'button' | 'compact';
  onTrackChange?: (isTracked: boolean) => void;
}

export const TrackFileButton = ({
  procedureRef,
  carriageId,
  isTracked: initialIsTracked = false,
  variant = 'button',
  onTrackChange,
}: TrackFileButtonProps) => {
  const { t } = useTranslation();
  const { trackFile, untrackFile, isTracking, trackedFiles } = useLegislativeTrains();
  const [localIsTracked, setLocalIsTracked] = useState(initialIsTracked);
  const [error, setError] = useState<string | null>(null);

  // Use procedure ref if available, otherwise carriage ID
  const useCarriageId = !procedureRef && !!carriageId;
  const identifier = procedureRef || carriageId;

  // Check if currently tracked (either from prop or from store)
  const isCurrentlyTracked =
    localIsTracked ||
    trackedFiles.some((f) =>
      (procedureRef && f.oeil_procedure_ref === procedureRef) ||
      (carriageId && f.file_id === carriageId)
    );

  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();

    if (!identifier) {
      setError('No identifier to track');
      return;
    }

    try {
      setError(null);

      if (isCurrentlyTracked) {
        // Untrack
        await untrackFile(identifier, useCarriageId);
        setLocalIsTracked(false);
        onTrackChange?.(false);
      } else {
        await trackFile(identifier, useCarriageId);
        setLocalIsTracked(true);
        onTrackChange?.(true);
      }
    } catch {
      setError('Failed to update tracking');
    }
  };

  if (variant === 'icon') {
    return (
      <button
        className={`track-file-button track-file-button--icon ${
          isCurrentlyTracked ? 'track-file-button--tracked' : ''
        }`}
        onClick={handleClick}
        disabled={isTracking}
        title={isCurrentlyTracked ? t('common.stopTracking') : t('common.trackThisFile')}
      >
        {isTracking ? (
          <Icon path={mdiLoading} size={0.8} spin />
        ) : (
          <Icon path={isCurrentlyTracked ? mdiStar : mdiStarOutline} size={0.8} />
        )}
      </button>
    );
  }

  if (variant === 'compact') {
    return (
      <button
        className={`track-file-button track-file-button--compact ${
          isCurrentlyTracked ? 'track-file-button--tracked' : ''
        }`}
        onClick={handleClick}
        disabled={isTracking}
      >
        {isTracking ? (
          <Icon path={mdiLoading} size={0.6} spin />
        ) : (
          <Icon path={isCurrentlyTracked ? mdiStar : mdiStarOutline} size={0.6} />
        )}
        <span>{isCurrentlyTracked ? t('tracking.tracked') : t('tracking.track')}</span>
      </button>
    );
  }

  return (
    <div className="track-file-button__wrapper">
      <button
        className={`track-file-button track-file-button--full ${
          isCurrentlyTracked ? 'track-file-button--tracked' : ''
        }`}
        onClick={handleClick}
        disabled={isTracking}
      >
        {isTracking ? (
          <>
            <Icon path={mdiLoading} size={0.8} spin />
            <span>{t('tracking.processing')}</span>
          </>
        ) : isCurrentlyTracked ? (
          <>
            <Icon path={mdiStar} size={0.8} />
            <span>{t('tracking.tracking')}</span>
          </>
        ) : (
          <>
            <Icon path={mdiStarOutline} size={0.8} />
            <span>{t('tracking.trackFile')}</span>
          </>
        )}
      </button>
      {error && <div className="track-file-button__error">{error}</div>}
    </div>
  );
};
