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
import { RowSkeleton } from '../shared/skeleton';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
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
  mdiBookOpenPageVariantOutline,
  mdiArrowRight,
} from '@mdi/js';
import axios from 'axios';
import { useLegislativeTrains } from '../../hooks/use_legislative_trains';
import { getDeepDiveForProcedure, getDeepDiveUrl } from '../../utils/deep_dive_map';
import { StagePipeline } from './stage_pipeline';
import { TrackFileButton } from '../shared/track_file_button';
import { PersonalisedImpact } from '../shared/personalised_impact';
import { FutureComplyPreview } from '../shared/future_comply_preview';
import { RegulatoryCascade } from '../shared/regulatory_cascade';
import CommitteeDocumentsCard from './committee_documents_card';
import LegislativeJourneyPanel from './legislative_journey_panel';
import { getEultUrl, getRegDelUrl } from '../../utils/eu_links';
import './legislative_file_detail.css';
import { uiDateLocale } from '../../i18n/config';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface FileMeeting {
  id: string;
  title: string;
  start_date: string;
  start_time?: string;
  institution?: string;
  ep_committee_code?: string;
  source_url?: string;
  agenda_url?: string;
}

interface Amendment {
  id: string;
  element_type: string;
  position_text: string;
  amendment_type: string;
  status: string;
  created_at: string;
}

export const LegislativeFileDetail = () => {
  const { t, i18n } = useTranslation();
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

  // Meetings on this file. Committee-agenda events carry the procedure
  // references of the items on their agenda, so a dossier's diary is a real
  // query: 223 procedures have at least one scheduled or past meeting.
  const [meetings, setMeetings] = useState<FileMeeting[]>([]);
  const [isLoadingMeetings, setIsLoadingMeetings] = useState(false);

  const fetchMeetings = async (procedureRef: string) => {
    // A year back and two years forward: far enough to catch the whole of a
    // normal file's committee cycle, near enough that the list stays a diary
    // rather than an archive.
    const from = new Date();
    from.setFullYear(from.getFullYear() - 1);
    const to = new Date();
    to.setFullYear(to.getFullYear() + 2);
    setIsLoadingMeetings(true);
    try {
      const response = await axios.get(`${API_BASE}/api/eu-calendar/events`, {
        params: {
          date_from: from.toISOString().slice(0, 10),
          date_to: to.toISOString().slice(0, 10),
          procedure: procedureRef,
          limit: 25,
        },
      });
      // Upcoming first (soonest at the top), then past meetings most-recent
      // first. The next date is the thing a user is looking for.
      const today = new Date(new Date().toDateString()).getTime();
      const rows: FileMeeting[] = response.data.events || [];
      rows.sort((a, b) => {
        const ta = new Date(a.start_date).getTime();
        const tb = new Date(b.start_date).getTime();
        const aFuture = ta >= today;
        const bFuture = tb >= today;
        if (aFuture !== bFuture) return aFuture ? -1 : 1;
        return aFuture ? ta - tb : tb - ta;
      });
      setMeetings(rows);
    } catch {
      setMeetings([]);
    } finally {
      setIsLoadingMeetings(false);
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

  // Keyed on the procedure reference, not the file id: the detail arrives in
  // two stages and the reference is absent from the first one, so an effect
  // watching only the id would never see it.
  useEffect(() => {
    setMeetings([]);
    if (selectedFile?.oeil_procedure_ref) {
      fetchMeetings(selectedFile.oeil_procedure_ref);
    }
  }, [selectedFile?.oeil_procedure_ref]);

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

  // Heading and official title, derived once.
  //
  // Some carriage titles carry the CELEX glued to the front
  // ("CELEX:32019R0005R(03): Corrigendum to ..."). That is a database
  // identifier, not part of the act's name, so it is stripped here the same
  // way services/legislative/title_display.py strips it server-side. It is not
  // shown anywhere in the header: a CELEX means nothing to a reader, and the
  // cross-references section below already links out to the act by it.
  const celexPrefix = selectedFile.title.match(
    /^CELEX:\s*[0-9]{5}[A-Z]{1,2}[0-9]{4}(?:R\(\d{2}\))?\s*:\s*/,
  );
  const officialTitle = celexPrefix
    ? selectedFile.title.slice(celexPrefix[0].length).trim() || selectedFile.title
    : selectedFile.title;
  const headerTitle = selectedFile.short_title?.trim() || officialTitle;
  // Only repeat the official title when it says more than the heading does.
  const headerSubtitle = headerTitle === officialTitle ? null : officialTitle;

  // If this file has a published Brubru deep-dive, surface a link to it so the
  // modal becomes the jumping-off point to the exhaustive analysis. Matched by
  // OEIL procedure ref via the shared deep-dive map (reusable for every file).
  const deepDive = selectedFile.oeil_procedure_ref
    ? getDeepDiveForProcedure(selectedFile.oeil_procedure_ref)
    : undefined;

  // Transposition deadlines apply ONLY to directives (regulations are directly
  // applicable). Detect from the title or a directive-type CELEX (5 digits + "L").
  const isDirective =
    /\bdirective\b/i.test(selectedFile.title || '') ||
    (selectedFile.celex_numbers || []).some((c) => /^\d{5}L\d/i.test(c));

  // CEN/CENELEC standards apply ONLY to acts that reference harmonised standards
  // (product / technical legislation). Detect from the act's own text signals.
  const cenRelevant = /harmonis(?:e|ed) standard|harmoniz(?:e|ed) standard|\bCEN\b|CENELEC|\bETSI\b|standardis(?:ation|ed) request|European standard/i.test(
    `${selectedFile.title || ''} ${selectedFile.ai_summary || ''} ${selectedFile.description || ''}`,
  );

  const handleAnalyze = async () => {
    try {
      await analyzeFile(selectedFile.file_id);
      // Success - data will refresh automatically
    } catch (error) {
      alert(t('fileDetail.analyzeFailed', 'Failed to analyse file. Please try again.'));
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
          {/* The heading is the short name; the full official title sits
              beneath it. Rendering `title` as the heading put 400-500
              characters of legal prose (opening with the raw
              "CELEX:32019R0005R(03):" database prefix) across the top of the
              modal. Nothing is hidden: the official title is still here, and
              the CELEX is its own reference chip. */}
          <div className="legislative-file-modal__header-left">
            <Icon path={mdiFileDocument} size={1.2} />
            <div className="legislative-file-modal__heading">
              <h2>{headerTitle}</h2>
              {headerSubtitle && (
                <p className="legislative-file-modal__official-title">{headerSubtitle}</p>
              )}
            </div>
          </div>
          <div className="legislative-file-modal__header-right">
            {deepDive && (
              <a
                href={getDeepDiveUrl(deepDive)}
                target="_blank"
                rel="noopener noreferrer"
                className="legislative-file-modal__deepdive-link"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 14px',
                  fontSize: '13px',
                  fontWeight: 600,
                  color: '#ffffff',
                  background: 'linear-gradient(135deg, #0693e3, #9b51e0)',
                  borderRadius: '6px',
                  textDecoration: 'none',
                }}
              >
                <Icon path={mdiBookOpenPageVariantOutline} size={0.8} />
                {t('fileDetail.readDeepDive', 'Read the deep dive')}
              </a>
            )}
            {selectedFile.oeil_procedure_ref && (
              <TrackFileButton
                procedureRef={selectedFile.oeil_procedure_ref}
                variant="button"
              />
            )}
            <button
              type="button"
              className="legislative-file-modal__ask"
              onClick={() => {
                const ref = selectedFile.oeil_procedure_ref
                  ? ` (${selectedFile.oeil_procedure_ref})` : '';
                const q = t('fileDetail.askPrompt', {
                  title: selectedFile.title, ref,
                  defaultValue: `Tell me about ${selectedFile.title}${ref}: where it stands, who is driving it, and what I should do.`,
                });
                navigate(`/chat?q=${encodeURIComponent(q)}&autofire=1`);
              }}
              title={t('fileDetail.askTitle', 'Ask Brubru about this file')}
            >
              <Icon path={mdiRobotOutline} size={0.8} />
              {t('fileDetail.ask', 'Ask Brubru')}
            </button>
            <button
              className="legislative-file-modal__close"
              onClick={closeFileDetail}
              title={t('fileDetail.closeTitle')}
            >
              <Icon path={mdiClose} size={0.9} />
            </button>
          </div>
        </div>

        {isLoadingFileDetail ? (
          <div className="legislative-file-modal__loading">
            {t('fileDetail.loading')}
          </div>
        ) : (
          <div className="legislative-file-modal__body">
            {/* Stage Pipeline */}
            <div className="legislative-file-detail__section legislative-file-detail__section--pipeline">
              <h3>{t('fileDetail.legislativeProgress')}</h3>
              <StagePipeline currentStatus={selectedFile.current_status} />
            </div>

            {/* EP Legislative Train — editorial "state of play" narrative */}
            {selectedFile.legislative_train_summary && (
              <div className="legislative-file-detail__section legislative-file-detail__train">
                <h3>{t('fileDetail.legislativeTrain')}</h3>
                <div className="legislative-file-detail__train-body">
                  {selectedFile.legislative_train_summary.split('\n\n').map((para, i) => (
                    <p key={i}>{para}</p>
                  ))}
                </div>
                {selectedFile.legislative_train_url && (
                  <a
                    className="legislative-file-detail__train-source"
                    href={selectedFile.legislative_train_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {t('fileDetail.legislativeTrainSource')}
                  </a>
                )}
              </div>
            )}

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
              <RegulatoryCascade
                procedureRef={selectedFile.oeil_procedure_ref}
                isDirective={isDirective}
                cenRelevant={cenRelevant}
              />
            )}

            {/* Legislative journey - AI comparison summary + CTA to Position Analysis */}
            <div className="legislative-file-detail__section">
              <LegislativeJourneyPanel
                carriageId={selectedFile.id}
                mode="compact"
                onOpenFullAnalysis={selectedFile.oeil_procedure_ref ? () => {
                  closeFileDetail();
                  navigate(`/my-eu-bubble?tab=position_analysis&ref=${encodeURIComponent(selectedFile.oeil_procedure_ref!)}`);
                } : undefined}
              />
            </div>

            {/* This file, across the rest of My EU Bubble.
                The modal is the one screen reachable from Overview, My Tracked
                Files, Amendments and the Legislative Train, which makes it the
                natural crossroads for a file. It linked out to OEIL six times
                and into Brubru almost not at all, so a reader who wanted the
                amendments or the forecast for the file in front of them had to
                go back to the sidebar, open the right tab and find it again.
                Only surfaces that can actually receive a file are offered:
                Votes and Amendments take ?procedure=, Predictions and Position
                Analysis take ?ref=. The Calendar is answered inline below
                instead, because its views are month-bound and a filtered jump
                would land on an empty month. Transcripts carry no usable
                procedure reference (1 row of 492), so there is nothing to link
                to and it is deliberately absent. */}
            {selectedFile.oeil_procedure_ref && (
              <div className="legislative-file-detail__section">
                <h3 className="legislative-file-detail__section-title">
                  {t('fileDetail.acrossBrubru', 'This file across Brubru')}
                </h3>
                <div className="legislative-file-detail__crosslinks">
                  {([
                    ['votes', `tab=votes&procedure=`, t('bubble.tabs.votes', 'Votes')],
                    ['amendments', `tab=amendments&procedure=`, t('bubble.amendments', 'Amendments')],
                    ['predictions', `tab=predictions&ref=`, t('bubble.tabs.predictions', 'Predictions')],
                    ['position_analysis', `tab=position_analysis&ref=`, t('bubble.tabs.positionAnalysis', 'Position Analysis')],
                  ] as [string, string, string][]).map(([key, qs, label]) => (
                    <button
                      key={key}
                      type="button"
                      className="legislative-file-detail__crosslink"
                      onClick={() => {
                        closeFileDetail();
                        navigate(`/my-eu-bubble?${qs}${encodeURIComponent(selectedFile.oeil_procedure_ref!)}`);
                      }}
                    >
                      {label}
                      <Icon path={mdiArrowRight} size={0.6} />
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Meetings on this file */}
            {(isLoadingMeetings || meetings.length > 0) && (
              <div className="legislative-file-detail__section">
                <h3 className="legislative-file-detail__section-title">
                  {t('fileDetail.meetings', 'Meetings on this file')}
                </h3>
                {isLoadingMeetings ? (
                  <RowSkeleton count={3} />
                ) : (
                <div className="legislative-file-detail__meetings">
                  {meetings.map((meeting) => {
                    const when = new Date(meeting.start_date);
                    const isUpcoming = when >= new Date(new Date().toDateString());
                    return (
                      <button
                        key={meeting.id}
                        type="button"
                        className={`legislative-file-detail__meeting${isUpcoming ? ' legislative-file-detail__meeting--upcoming' : ''}`}
                        onClick={() => {
                          closeFileDetail();
                          navigate(`/my-eu-bubble?tab=eu_calendar&date=${meeting.start_date.slice(0, 10)}`);
                        }}
                      >
                        <span className="legislative-file-detail__meeting-date">
                          {when.toLocaleDateString(i18n.language, { day: 'numeric', month: 'short', year: 'numeric' })}
                        </span>
                        <span className="legislative-file-detail__meeting-title">
                          {meeting.title}
                        </span>
                        <Icon path={mdiArrowRight} size={0.6} />
                      </button>
                    );
                  })}
                </div>
                )}
              </div>
            )}

            {/* Status */}
            <div className="legislative-file-detail__section">
              <h3>{t('fileDetail.currentStatus')}</h3>
              <div className="legislative-file-detail__status-row">
                <span
                  className="legislative-file-detail__status"
                  style={{ backgroundColor: getStatusColor(selectedFile.current_status) }}
                >
                  {selectedFile.current_status.replace(/_/g, ' ')}
                </span>
                {selectedFile.is_blocked && (
                  <span className="legislative-file-detail__blocked">⚠️ {t('myFilesTab.blocked')}</span>
                )}
                {selectedFile.days_in_current_status && (
                  <span className="legislative-file-detail__days">
                    {t('myFilesTab.daysInStatus', { n: selectedFile.days_in_current_status })}
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
                      <div className="legislative-file-detail__loading-inline">{t('fileDetail.loading')}</div>
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
                <h3>{t('fileDetail.description')}</h3>
                <p>{selectedFile.description}</p>
              </div>
            )}

            {/* AI Summary */}
            {selectedFile.ai_summary && (
              <div className="legislative-file-detail__section legislative-file-detail__section--ai">
                <div className="legislative-file-detail__section-header">
                  <Icon path={mdiRobotOutline} size={0.9} />
                  <h3>{t('fileDetail.aiSummary')}</h3>
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
                  <h3>{t('fileDetail.policyAreas')}</h3>
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
                  <h3>{t('fileDetail.keyEntities')}</h3>
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
                <h3>{t('fileDetail.committees')}</h3>
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
                <h3>{t('fileDetail.references')}</h3>
              </div>
              <div className="legislative-file-detail__references">
                {selectedFile.oeil_procedure_ref && (
                  <div className="legislative-file-detail__reference">
                    <strong>{t('fileDetail.oeilProcedure')}</strong>
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
                          {t('myFilesTab.euLawTracker')}
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
                          {t('myFilesTab.regDel')}
                        </a>
                      </>
                    )}
                  </div>
                )}
                {selectedFile.celex_numbers && selectedFile.celex_numbers.length > 0 && (
                  <div className="legislative-file-detail__reference">
                    <strong>{t('fileDetail.celexLabel')}</strong>
                    {selectedFile.celex_numbers.join(', ')}
                  </div>
                )}
                {selectedFile.legal_text_url && (
                  <div className="legislative-file-detail__reference">
                    <strong>{t('fileDetail.legalText')}</strong>
                    <a href={selectedFile.legal_text_url} target="_blank" rel="noopener noreferrer">
                      {t('fileDetail.viewOnEurlex', 'View on EUR-Lex')}
                    </a>
                  </div>
                )}
              </div>
            </div>

            {/* Key Events Timeline */}
            <div className="legislative-file-detail__section legislative-file-detail__section--meta">
              <div className="legislative-file-detail__section-header">
                <Icon path={mdiCalendar} size={0.9} />
                <h3>{t('fileDetail.keyEvents')}</h3>
              </div>
              <div className="legislative-file-detail__timeline">
                {isLoadingTimeline ? (
                  <div className="legislative-file-detail__loading-small">{t('fileDetail.loadingEvents')}</div>
                ) : timelineEvents.length > 0 ? (
                  <div className="legislative-file-detail__events">
                    {timelineEvents.map((event, idx) => (
                      <div key={idx} className="legislative-file-detail__event">
                        <div className="legislative-file-detail__event-date">
                          {new Date(event.date).toLocaleDateString(uiDateLocale(), {
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
                        <strong>{t('fileDetail.firstSeen')}</strong>
                        <span>{new Date(selectedFile.first_seen).toLocaleDateString()}</span>
                      </div>
                    )}
                    {selectedFile.last_updated && (
                      <div className="legislative-file-detail__timeline-item">
                        <strong>{t('myFilesTab.cardLastUpdate')}</strong>
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
                    <div className="legislative-file-detail__loading-inline">{t('fileDetail.loadingAmendments')}</div>
                  ) : amendments.length === 0 ? (
                    <div className="legislative-file-detail__amendments-empty">
                      <p>{t('fileDetail.noAmendmentsDrafted')}</p>
                      <button
                        className="legislative-file-detail__draft-btn"
                        onClick={() => {
                          closeFileDetail();
                          navigate('/amendator');
                        }}
                      >
                        <Icon path={mdiPlus} size={0.8} />
                        {t('myFilesTab.draftAmendment', 'Draft Amendment')}
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
                        {t('amendmentsTab.draftMore', 'Draft More Amendments')}
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* EP committee documents on this dossier (draft report, amendments,
                opinions, compromises) - surfaced from ep_emeeting_documents by
                OEIL procedure. Renders nothing when the file has none. */}
            <CommitteeDocumentsCard carriageId={selectedFile.id} compact />

            {/* AI Analyze Button */}
            {!selectedFile.ai_summary && (
              <div className="legislative-file-detail__actions">
                <button
                  className="legislative-file-detail__analyze-btn"
                  onClick={handleAnalyze}
                  disabled={isAnalyzing}
                >
                  <Icon path={mdiRobotOutline} size={0.9} />
                  {isAnalyzing ? t('fileDetail.analysing', 'Analysing...') : t('fileDetail.aiAnalyze', 'AI Analyse This File')}
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
