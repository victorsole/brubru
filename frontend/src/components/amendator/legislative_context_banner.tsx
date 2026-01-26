// Legislative Context Banner for Amendator
// Shows tracking information when the loaded document matches a tracked file
import { useState, useEffect } from 'react';
import { useLegislativeTrains } from '../../hooks/use_legislative_trains';
import type { TrackedFile } from '../../hooks/use_legislative_trains';
import './legislative_context_banner.css';

interface LegislativeContextBannerProps {
  documentId: string | null;
  celex?: string;
  onViewDetails?: (carriage_id: string) => void;
}

export const LegislativeContextBanner = ({
  documentId,
  celex,
  onViewDetails
}: LegislativeContextBannerProps) => {
  const { trackedFiles, fetchTrackedFiles, isTracking } = useLegislativeTrains();
  const [matchedFile, setMatchedFile] = useState<TrackedFile | null>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);

  useEffect(() => {
    fetchTrackedFiles();
  }, [fetchTrackedFiles]);

  // Find matching tracked file based on document_id (CELEX)
  useEffect(() => {
    if (!documentId && !celex) {
      setMatchedFile(null);
      return;
    }

    // Normalize the document ID - remove 'eurlex-' prefix
    const normalizedId = documentId?.replace('eurlex-', '') || celex || '';

    // Find a tracked file that has this CELEX
    const matched = trackedFiles.find(file => {
      if (file.celex_numbers) {
        return file.celex_numbers.includes(normalizedId);
      }
      return false;
    });

    setMatchedFile(matched || null);
  }, [documentId, celex, trackedFiles]);

  const handleTrackFile = async () => {
    if (!celex && !documentId) return;
    const celexToTrack = celex || documentId?.replace('eurlex-', '') || '';
    // This would need an API endpoint to track by CELEX
    // For now, we'll just show a message
    console.log('Would track CELEX:', celexToTrack);
  };

  const formatStatus = (status: string) => {
    return status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'adopted':
      case 'completed':
        return 'status--adopted';
      case 'tabled':
      case 'close_to_adoption':
        return 'status--tabled';
      case 'blocked':
        return 'status--blocked';
      case 'withdrawn':
        return 'status--withdrawn';
      default:
        return 'status--announced';
    }
  };

  // Don't render if no document loaded
  if (!documentId && !celex) {
    return null;
  }

  // Render "not tracked" banner
  if (!matchedFile) {
    return (
      <div className="legislative-context-banner legislative-context-banner--not-tracked">
        <div className="legislative-context-banner__content">
          <span className="legislative-context-banner__icon mdi mdi-file-document"></span>
          <span className="legislative-context-banner__text">
            This legislation is <strong>not tracked</strong>
          </span>
        </div>
        <button
          className="legislative-context-banner__track-button button button-sm button-secondary"
          onClick={handleTrackFile}
          disabled={isTracking}
        >
          {isTracking ? 'Tracking...' : 'Track this file'}
        </button>
      </div>
    );
  }

  // Render tracked file banner
  return (
    <div className={`legislative-context-banner legislative-context-banner--tracked ${isCollapsed ? 'legislative-context-banner--collapsed' : ''}`}>
      <div className="legislative-context-banner__header" onClick={() => setIsCollapsed(!isCollapsed)}>
        <span className="legislative-context-banner__icon mdi mdi-file-document"></span>
        <span className="legislative-context-banner__title">
          This legislation is <strong>TRACKED</strong>
        </span>
        <button className="legislative-context-banner__toggle">
          {isCollapsed ? '▼' : '▲'}
        </button>
      </div>

      {!isCollapsed && (
        <div className="legislative-context-banner__details">
          <div className="legislative-context-banner__info-row">
            <span className={`legislative-context-banner__status ${getStatusColor(matchedFile.current_status)}`}>
              {formatStatus(matchedFile.current_status)}
            </span>
            {matchedFile.lead_committee && (
              <span className="legislative-context-banner__committee">
                {matchedFile.lead_committee}
              </span>
            )}
            {matchedFile.days_in_current_status && (
              <span className="legislative-context-banner__days">
                {matchedFile.days_in_current_status} days in status
              </span>
            )}
          </div>

          <h4 className="legislative-context-banner__file-title">
            {matchedFile.title}
          </h4>

          {matchedFile.oeil_procedure_ref && (
            <p className="legislative-context-banner__procedure-ref">
              {matchedFile.oeil_procedure_ref}
            </p>
          )}

          <div className="legislative-context-banner__actions">
            {onViewDetails && (
              <button
                className="legislative-context-banner__action-button button button-sm button-primary"
                onClick={() => onViewDetails(matchedFile.carriage_id)}
              >
                View File Details
              </button>
            )}
            <a
              href={`https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${matchedFile.oeil_procedure_ref}`}
              target="_blank"
              rel="noopener noreferrer"
              className="legislative-context-banner__action-link"
            >
              Open in OEIL →
            </a>
          </div>
        </div>
      )}
    </div>
  );
};
