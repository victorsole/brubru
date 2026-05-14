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

import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import Icon from '@mdi/react';
import {
  mdiClose,
  mdiRobotOutline,
  mdiFileDocument,
  mdiTag,
  mdiAccountGroup,
  mdiCalendar,
  mdiLinkVariant,
  mdiAccountTieOutline,
  mdiChevronDown,
  mdiChevronUp,
  mdiPencilOutline,
  mdiPlus,
} from '@mdi/js';
import axios from 'axios';
import { useLegislativeTrains } from '../../hooks/use_legislative_trains';
import { StagePipeline } from './stage_pipeline';
import { TrackFileButton } from '../shared/track_file_button';
import { PersonalisedImpact } from '../shared/personalised_impact';
import { FutureComplyPreview } from '../shared/future_comply_preview';
import { RegulatoryCascade } from '../shared/regulatory_cascade';
import { getEultUrl, getRegDelUrl } from '../../utils/eu_links';
import './legislative_file_detail.css';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface Amendment {
  id: string;
  element_type: string;
  position_text: string;
  amendment_type: string;
  status: string;
  created_at: string;
}

export const LegislativeFileDetail = () => {
  const navigate = useNavigate();
  const {
    selectedFile,
    isLoadingFileDetail,
    isAnalyzing,
    keyPlayers,
    isLoadingKeyPlayers,
    timelineEvents,
    isLoadingTimeline,
    analyzeFile,
    closeFileDetail,
    fetchKeyPlayers,
    fetchTimeline,
  } = useLegislativeTrains();

  // Amendments state
  const [amendments, setAmendments] = useState<Amendment[]>([]);
  const [isLoadingAmendments, setIsLoadingAmendments] = useState(false);
  const [isAmendmentsExpanded, setIsAmendmentsExpanded] = useState(true);

  // Fetch amendments for the carriage
  const fetchAmendments = async (carriageId: string) => {
    setIsLoadingAmendments(true);
    try {
      const response = await axios.get(`${API_BASE}/api/legislative-train/carriages/${carriageId}/amendments`);
      setAmendments(response.data.amendments || []);
    } catch (error) {
      console.error('Failed to fetch amendments:', error);
      setAmendments([]);
    } finally {
      setIsLoadingAmendments(false);
    }
  };

  // Fetch key players, timeline, and amendments when file is selected
  useEffect(() => {
    if (selectedFile?.id) {
      fetchKeyPlayers(selectedFile.id);
      fetchTimeline(selectedFile.id);
      fetchAmendments(selectedFile.id);
    }
  }, [selectedFile?.id]);

  // Collapsible sections state
  const [isActorsExpanded, setIsActorsExpanded] = useState(true);

  // Filter out invalid/placeholder key players
  const validKeyPlayers = useMemo(() => {
    const placeholders = ['commission dg', 'commissioner', 'dg', 'n/a', 'unknown'];
    return keyPlayers.filter(player => {
      const name = player.name?.trim().toLowerCase() || '';
      if (!name || name.length < 3) return false;
      return !placeholders.includes(name);
    });
  }, [keyPlayers]);

  // Don't render if no file selected
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

  // Use portal to render at document.body level, escaping parent stacking contexts
  return createPortal(
    <div className="legislative-file-modal">
      <div className="legislative-file-modal__overlay" onClick={closeFileDetail} />
      <div className="legislative-file-modal__content">
        {/* Header */}
        <div className="legislative-file-modal__header">
          <div className="legislative-file-modal__header-left">
            <Icon path={mdiFileDocument} size={1.2} />
            <h2>{selectedFile.title}</h2>
          </div>
          <div className="legislative-file-modal__header-right">
            {selectedFile.oeil_procedure_ref && (
              <TrackFileButton
                procedureRef={selectedFile.oeil_procedure_ref}
                variant="button"
              />
            )}
            <button
              className="legislative-file-modal__close"
              onClick={closeFileDetail}
              title="Close"
            >
              <Icon path={mdiClose} size={0.9} />
            </button>
          </div>
        </div>

        {isLoadingFileDetail ? (
          <div className="legislative-file-modal__loading">
            Loading file details...
          </div>
        ) : (
          <div className="legislative-file-modal__body">
            {/* Stage Pipeline */}
            <div className="legislative-file-detail__section legislative-file-detail__section--pipeline">
              <h3>Legislative Progress</h3>
              <StagePipeline currentStatus={selectedFile.current_status} />
            </div>

            {/* Personalised Impact — "what this means for you" */}
            {selectedFile.oeil_procedure_ref && (
              <PersonalisedImpact procedureRef={selectedFile.oeil_procedure_ref} />
            )}

            {/* Future-Comply preview — for in-flight proposals */}
            {selectedFile.oeil_procedure_ref && (
              <FutureComplyPreview procedureRef={selectedFile.oeil_procedure_ref} />
            )}

            {/* Regulatory cascade — secondary acts + related in-flight files */}
            {selectedFile.oeil_procedure_ref && (
              <RegulatoryCascade procedureRef={selectedFile.oeil_procedure_ref} />
            )}

            {/* Status */}
            <div className="legislative-file-detail__section">
              <h3>Current Status</h3>
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

            {/* Key Actors - Collapsible */}
            {(validKeyPlayers.length > 0 || isLoadingKeyPlayers) && (
              <div className="legislative-file-detail__section legislative-file-detail__section--collapsible">
                <button
                  className="legislative-file-detail__section-header legislative-file-detail__section-header--clickable"
                  onClick={() => setIsActorsExpanded(!isActorsExpanded)}
                >
                  <div className="legislative-file-detail__section-header-left">
                    <Icon path={mdiAccountTieOutline} size={0.9} />
                    <h3>Key Actors {validKeyPlayers.length > 0 && `(${validKeyPlayers.length})`}</h3>
                  </div>
                  <Icon
                    path={isActorsExpanded ? mdiChevronUp : mdiChevronDown}
                    size={0.9}
                    className="legislative-file-detail__collapse-icon"
                  />
                </button>
                {isActorsExpanded && (
                  <>
                    {isLoadingKeyPlayers ? (
                      <div className="legislative-file-detail__loading-inline">Loading...</div>
                    ) : (
                      <div className="legislative-file-detail__actors">
                        {validKeyPlayers.map((player, idx) => (
                          <div key={idx} className="legislative-file-detail__actor">
                            {player.photo_url && (
                              <img
                                src={player.photo_url}
                                alt={player.name}
                                className="legislative-file-detail__actor-photo"
                              />
                            )}
                            <div className="legislative-file-detail__actor-info">
                              <div className="legislative-file-detail__actor-name">
                                {player.name}
                              </div>
                              <div className="legislative-file-detail__actor-role">
                                {player.role}
                                {player.political_group && ` (${player.political_group})`}
                                {player.country && `, ${player.country}`}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

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
                      href={`https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${selectedFile.oeil_procedure_ref}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {selectedFile.oeil_procedure_ref}
                    </a>
                    {getEultUrl(selectedFile.oeil_procedure_ref) && (
                      <>
                        {' | '}
                        <a
                          href={getEultUrl(selectedFile.oeil_procedure_ref)!}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          EU Law Tracker
                        </a>
                      </>
                    )}
                    {getRegDelUrl(selectedFile.oeil_procedure_ref) && (
                      <>
                        {' | '}
                        <a
                          href={getRegDelUrl(selectedFile.oeil_procedure_ref)!}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          RegDel Register
                        </a>
                      </>
                    )}
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

            {/* Key Events Timeline */}
            <div className="legislative-file-detail__section legislative-file-detail__section--meta">
              <div className="legislative-file-detail__section-header">
                <Icon path={mdiCalendar} size={0.9} />
                <h3>Key Events</h3>
              </div>
              <div className="legislative-file-detail__timeline">
                {isLoadingTimeline ? (
                  <div className="legislative-file-detail__loading-small">Loading events...</div>
                ) : timelineEvents.length > 0 ? (
                  <div className="legislative-file-detail__events">
                    {timelineEvents.map((event, idx) => (
                      <div key={idx} className="legislative-file-detail__event">
                        <div className="legislative-file-detail__event-date">
                          {new Date(event.date).toLocaleDateString('en-GB', {
                            day: 'numeric',
                            month: 'short',
                            year: 'numeric'
                          })}
                        </div>
                        <div className="legislative-file-detail__event-content">
                          <div className="legislative-file-detail__event-type">
                            {event.event_type}
                          </div>
                          {event.description && (
                            <div className="legislative-file-detail__event-desc">
                              {event.description}
                            </div>
                          )}
                          {event.result && (
                            <div className="legislative-file-detail__event-result">
                              Result: {event.result}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="legislative-file-detail__timeline-basic">
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
                )}
              </div>
            </div>

            {/* Amendments Section */}
            <div className="legislative-file-detail__section legislative-file-detail__section--collapsible">
              <button
                className="legislative-file-detail__section-header legislative-file-detail__section-header--clickable"
                onClick={() => setIsAmendmentsExpanded(!isAmendmentsExpanded)}
              >
                <div className="legislative-file-detail__section-header-left">
                  <Icon path={mdiPencilOutline} size={0.9} />
                  <h3>Your Amendments {amendments.length > 0 && `(${amendments.length})`}</h3>
                </div>
                <Icon
                  path={isAmendmentsExpanded ? mdiChevronUp : mdiChevronDown}
                  size={0.9}
                  className="legislative-file-detail__collapse-icon"
                />
              </button>
              {isAmendmentsExpanded && (
                <>
                  {isLoadingAmendments ? (
                    <div className="legislative-file-detail__loading-inline">Loading amendments...</div>
                  ) : amendments.length === 0 ? (
                    <div className="legislative-file-detail__amendments-empty">
                      <p>No amendments drafted yet for this file.</p>
                      <button
                        className="legislative-file-detail__draft-btn"
                        onClick={() => {
                          closeFileDetail();
                          navigate('/amendator');
                        }}
                      >
                        <Icon path={mdiPlus} size={0.8} />
                        Draft Amendment
                      </button>
                    </div>
                  ) : (
                    <div className="legislative-file-detail__amendments">
                      {amendments.map((amendment) => (
                        <div key={amendment.id} className="legislative-file-detail__amendment">
                          <div className="legislative-file-detail__amendment-header">
                            <span className={`legislative-file-detail__amendment-type legislative-file-detail__amendment-type--${amendment.amendment_type}`}>
                              {amendment.amendment_type}
                            </span>
                            <span className={`legislative-file-detail__amendment-status legislative-file-detail__amendment-status--${amendment.status}`}>
                              {amendment.status}
                            </span>
                          </div>
                          <div className="legislative-file-detail__amendment-position">
                            {amendment.position_text || `${amendment.element_type}`}
                          </div>
                          <div className="legislative-file-detail__amendment-date">
                            Created {new Date(amendment.created_at).toLocaleDateString()}
                          </div>
                        </div>
                      ))}
                      <button
                        className="legislative-file-detail__draft-btn legislative-file-detail__draft-btn--more"
                        onClick={() => {
                          closeFileDetail();
                          navigate('/amendator');
                        }}
                      >
                        <Icon path={mdiPencilOutline} size={0.8} />
                        Draft More Amendments
                      </button>
                    </div>
                  )}
                </>
              )}
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
    </div>,
    document.body
  );
};
