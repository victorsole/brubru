/**
 * Legislative File Detail Modal
 *
 * Shows detailed information about a legislative file including:
 * - AI-generated summary (British English)
 * - Policy area classifications
 * - Extracted entities
 * - Status and timeline
 * - Cross-references (OEIL, CELEX, EUR-Lex)
 */

import Icon from '@mdi/react';
import {
  mdiClose,
  mdiRobotOutline,
  mdiFileDocument,
  mdiTag,
  mdiAccountGroup,
  mdiCalendar,
  mdiLinkVariant,
} from '@mdi/js';
import { useLegislativeTrains } from '../../hooks/use_legislative_trains';
import './legislative_file_detail.css';

export const LegislativeFileDetail = () => {
  const {
    selectedFile,
    isLoadingFileDetail,
    isAnalyzing,
    analyzeFile,
    closeFileDetail,
  } = useLegislativeTrains();

  if (!selectedFile) return null;

  const handleAnalyze = async () => {
    try {
      await analyzeFile(selectedFile.file_id);
      // Success - data will refresh automatically
    } catch (error) {
      alert('Failed to analyze file. Please try again.');
    }
  };

  const getStatusColor = (status: string) => {
    const statusMap: Record<string, string> = {
      'announced': '#9e9e9e',
      'legislative_initiative': '#2196f3',
      'tabled': '#ff9800',
      'close_to_adoption': '#4caf50',
      'completed': '#4caf50',
      'blocked': '#f44336',
      'withdrawn': '#757575',
    };
    return statusMap[status] || '#9e9e9e';
  };

  return (
    <div className="legislative-file-modal">
      <div className="legislative-file-modal__overlay" onClick={closeFileDetail} />
      <div className="legislative-file-modal__content">
        {/* Header */}
        <div className="legislative-file-modal__header">
          <div className="legislative-file-modal__header-left">
            <Icon path={mdiFileDocument} size={1.2} />
            <h2>{selectedFile.title}</h2>
          </div>
          <button
            className="legislative-file-modal__close"
            onClick={closeFileDetail}
            title="Close"
          >
            <Icon path={mdiClose} size={0.9} />
          </button>
        </div>

        {isLoadingFileDetail ? (
          <div className="legislative-file-modal__loading">
            Loading file details...
          </div>
        ) : (
          <div className="legislative-file-modal__body">
            {/* Status */}
            <div className="legislative-file-detail__section">
              <h3>Status</h3>
              <div className="legislative-file-detail__status-row">
                <span
                  className="legislative-file-detail__status"
                  style={{ backgroundColor: getStatusColor(selectedFile.current_status) }}
                >
                  {selectedFile.current_status.replace(/_/g, ' ')}
                </span>
                {selectedFile.is_blocked && (
                  <span className="legislative-file-detail__blocked">⚠️ Blocked</span>
                )}
                {selectedFile.days_in_current_status && (
                  <span className="legislative-file-detail__days">
                    {selectedFile.days_in_current_status} days in current status
                  </span>
                )}
              </div>
            </div>

            {/* Description */}
            {selectedFile.description && (
              <div className="legislative-file-detail__section">
                <h3>Description</h3>
                <p>{selectedFile.description}</p>
              </div>
            )}

            {/* AI Summary */}
            {selectedFile.ai_summary && (
              <div className="legislative-file-detail__section legislative-file-detail__section--ai">
                <div className="legislative-file-detail__section-header">
                  <Icon path={mdiRobotOutline} size={0.9} />
                  <h3>AI Summary</h3>
                </div>
                <div className="legislative-file-detail__ai-box">
                  <p>{selectedFile.ai_summary}</p>
                  {selectedFile.enriched_at && (
                    <div className="legislative-file-detail__enriched-date">
                      Enriched: {new Date(selectedFile.enriched_at).toLocaleDateString()}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Policy Classifications */}
            {selectedFile.ai_policy_classifications && selectedFile.ai_policy_classifications.length > 0 && (
              <div className="legislative-file-detail__section">
                <div className="legislative-file-detail__section-header">
                  <Icon path={mdiTag} size={0.9} />
                  <h3>Policy Areas</h3>
                </div>
                <div className="legislative-file-detail__policies">
                  {selectedFile.ai_policy_classifications.map((classification, idx) => (
                    <div key={idx} className="legislative-file-detail__policy">
                      <span className="legislative-file-detail__policy-name">
                        {classification.label}
                      </span>
                      <span className="legislative-file-detail__policy-score">
                        {Math.round(classification.score * 100)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Extracted Entities */}
            {selectedFile.ai_entities && selectedFile.ai_entities.length > 0 && (
              <div className="legislative-file-detail__section">
                <div className="legislative-file-detail__section-header">
                  <Icon path={mdiAccountGroup} size={0.9} />
                  <h3>Key Entities</h3>
                </div>
                <div className="legislative-file-detail__entities">
                  {selectedFile.ai_entities.map((entity, idx) => (
                    <span key={idx} className="legislative-file-detail__entity">
                      {entity.text}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Committees */}
            {(selectedFile.lead_committee || (selectedFile.committees && selectedFile.committees.length > 0)) && (
              <div className="legislative-file-detail__section">
                <h3>Committees</h3>
                <div className="legislative-file-detail__committees">
                  {selectedFile.lead_committee && (
                    <span className="legislative-file-detail__committee legislative-file-detail__committee--lead">
                      {selectedFile.lead_committee} (Lead)
                    </span>
                  )}
                  {selectedFile.committees && selectedFile.committees.map((committee, idx) => (
                    <span key={idx} className="legislative-file-detail__committee">
                      {committee}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Cross-references */}
            <div className="legislative-file-detail__section">
              <div className="legislative-file-detail__section-header">
                <Icon path={mdiLinkVariant} size={0.9} />
                <h3>References</h3>
              </div>
              <div className="legislative-file-detail__references">
                {selectedFile.oeil_procedure_ref && (
                  <div className="legislative-file-detail__reference">
                    <strong>OEIL Procedure:</strong>
                    <a
                      href={`https://oeil.secure.europarl.europa.eu/oeil/popups/ficheprocedure.do?reference=${selectedFile.oeil_procedure_ref}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {selectedFile.oeil_procedure_ref}
                    </a>
                  </div>
                )}
                {selectedFile.celex_numbers && selectedFile.celex_numbers.length > 0 && (
                  <div className="legislative-file-detail__reference">
                    <strong>CELEX:</strong>
                    {selectedFile.celex_numbers.join(', ')}
                  </div>
                )}
                {selectedFile.legal_text_url && (
                  <div className="legislative-file-detail__reference">
                    <strong>Legal Text:</strong>
                    <a href={selectedFile.legal_text_url} target="_blank" rel="noopener noreferrer">
                      View on EUR-Lex
                    </a>
                  </div>
                )}
              </div>
            </div>

            {/* Temporal Data */}
            <div className="legislative-file-detail__section legislative-file-detail__section--meta">
              <div className="legislative-file-detail__section-header">
                <Icon path={mdiCalendar} size={0.9} />
                <h3>Timeline</h3>
              </div>
              <div className="legislative-file-detail__timeline">
                {selectedFile.first_seen && (
                  <div className="legislative-file-detail__timeline-item">
                    <strong>First Seen:</strong>
                    <span>{new Date(selectedFile.first_seen).toLocaleDateString()}</span>
                  </div>
                )}
                {selectedFile.last_updated && (
                  <div className="legislative-file-detail__timeline-item">
                    <strong>Last Updated:</strong>
                    <span>{new Date(selectedFile.last_updated).toLocaleDateString()}</span>
                  </div>
                )}
              </div>
            </div>

            {/* AI Analyze Button */}
            {!selectedFile.ai_summary && (
              <div className="legislative-file-detail__actions">
                <button
                  className="legislative-file-detail__analyze-btn"
                  onClick={handleAnalyze}
                  disabled={isAnalyzing}
                >
                  <Icon path={mdiRobotOutline} size={0.9} />
                  {isAnalyzing ? 'Analyzing...' : 'AI Analyze This File'}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
