/**
 * Consultation Detail Modal
 *
 * Displays full details of a public consultation.
 * Uses createPortal to escape z-index stacking context issues.
 * Includes AI Analysis and Proposal Generation features.
 *
 * Created: January 2026
 */

import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiClose,
  mdiCalendarClock,
  mdiOpenInNew,
  mdiBookmarkOutline,
  mdiBookmark,
  mdiFileDocumentOutline,
  mdiLinkVariant,
  mdiInformationOutline,
  mdiClockAlertOutline,
  mdiCheckCircleOutline,
  mdiRobotOutline,
  mdiLightbulbOnOutline,
  mdiChevronDown,
  mdiChevronUp,
  mdiLoading,
  mdiAlertCircleOutline,
} from '@mdi/js';

import type {
  ConsultationDetail as ConsultationDetailType,
  ConsultationAnalysis,
  ProposalSet,
} from '../../services/consultation_service';
import {
  formatDaysRemaining,
  consultationService,
} from '../../services/consultation_service';
import {
  STATUS_INFO,
  CONSULTATION_TYPE_INFO,
} from '../../hooks/use_consultations';
import { useAuth } from '../../hooks/use_auth';

// ============================================================================
// Styles
// ============================================================================

const styles = {
  overlay: {
    position: 'fixed' as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: 'rgba(0, 0, 0, 0.5)',
    backdropFilter: 'blur(4px)',
    zIndex: 10001,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '1rem',
  },
  modal: {
    background: 'white',
    borderRadius: '12px',
    maxWidth: '900px',
    width: '100%',
    maxHeight: '90vh',
    overflow: 'hidden',
    boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3)',
    display: 'flex',
    flexDirection: 'column' as const,
  },
  header: {
    background: 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)',
    color: 'white',
    padding: '1.5rem',
    position: 'relative' as const,
  },
  closeBtn: {
    position: 'absolute' as const,
    top: '1rem',
    right: '1rem',
    background: 'rgba(255, 255, 255, 0.2)',
    border: 'none',
    borderRadius: '50%',
    width: '36px',
    height: '36px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    color: 'white',
    transition: 'background 0.2s',
  },
  title: {
    fontSize: '1.25rem',
    fontWeight: 600,
    margin: '0 2.5rem 0.5rem 0',
    lineHeight: 1.4,
    // Explicit white: the global `h1..h6 { color: var(--color-text) }` rule in
    // styles/globals.css otherwise beats the white inherited from the header.
    color: 'white',
  },
  badges: {
    display: 'flex',
    gap: '0.5rem',
    flexWrap: 'wrap' as const,
    marginTop: '0.75rem',
  },
  badge: {
    padding: '0.25rem 0.75rem',
    borderRadius: '12px',
    fontSize: '0.75rem',
    fontWeight: 600,
    background: 'rgba(255, 255, 255, 0.2)',
  },
  content: {
    padding: '1.5rem',
    overflowY: 'auto' as const,
    flex: 1,
  },
  section: {
    marginBottom: '1.5rem',
  },
  sectionTitle: {
    fontSize: '0.875rem',
    fontWeight: 600,
    color: '#374151',
    marginBottom: '0.75rem',
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  meta: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '1rem',
    marginBottom: '1.5rem',
  },
  metaItem: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '0.25rem',
  },
  metaLabel: {
    fontSize: '0.75rem',
    color: '#6b7280',
    fontWeight: 500,
  },
  metaValue: {
    fontSize: '0.875rem',
    color: '#111827',
  },
  description: {
    fontSize: '0.9375rem',
    color: '#374151',
    lineHeight: 1.7,
    marginBottom: '1.5rem',
  },
  documentList: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '0.5rem',
  },
  documentItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    padding: '0.75rem',
    background: '#f9fafb',
    borderRadius: '8px',
    fontSize: '0.875rem',
    color: '#374151',
    textDecoration: 'none',
    transition: 'background 0.2s',
  },
  legislationList: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '0.5rem',
  },
  legislationItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    fontSize: '0.875rem',
    color: '#0693e3',
  },
  footer: {
    padding: '1rem 1.5rem',
    borderTop: '1px solid #e5e7eb',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '1rem',
  },
  footerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    fontSize: '0.875rem',
    color: '#6b7280',
  },
  footerActions: {
    display: 'flex',
    gap: '0.5rem',
  },
  btn: {
    padding: '0.625rem 1.25rem',
    borderRadius: '6px',
    border: 'none',
    fontSize: '0.875rem',
    fontWeight: 500,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    transition: 'all 0.2s',
  },
  btnPrimary: {
    background: '#f97316',
    color: 'white',
  },
  btnSecondary: {
    background: '#f3f4f6',
    color: '#374151',
  },
  btnTracked: {
    background: '#059669',
    color: 'white',
  },
  outcome: {
    background: '#dbeafe',
    padding: '1rem',
    borderRadius: '8px',
    marginBottom: '1.5rem',
  },
  outcomeTitle: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    fontSize: '0.875rem',
    fontWeight: 600,
    color: '#1e40af',
    marginBottom: '0.5rem',
  },
  outcomeText: {
    fontSize: '0.875rem',
    color: '#1e3a8a',
    lineHeight: 1.6,
  },
  aiSection: {
    background: 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)',
    border: '1px solid #f59e0b',
    borderRadius: '12px',
    marginBottom: '1.5rem',
    overflow: 'hidden',
  },
  aiSectionBlue: {
    background: 'linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%)',
    border: '1px solid #3b82f6',
  },
  aiHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '1rem',
    cursor: 'pointer',
    gap: '0.75rem',
  },
  aiHeaderTitle: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    fontWeight: 600,
    fontSize: '0.9375rem',
  },
  aiContent: {
    padding: '0 1rem 1rem 1rem',
  },
  aiSummary: {
    fontSize: '0.9375rem',
    lineHeight: 1.7,
    marginBottom: '1rem',
  },
  aiList: {
    paddingLeft: '1.25rem',
    margin: '0.5rem 0',
  },
  aiListItem: {
    marginBottom: '0.5rem',
    fontSize: '0.875rem',
    lineHeight: 1.5,
  },
  aiSubheading: {
    fontWeight: 600,
    fontSize: '0.875rem',
    marginTop: '1rem',
    marginBottom: '0.5rem',
    color: '#374151',
  },
  generateBtn: {
    padding: '0.625rem 1.25rem',
    borderRadius: '6px',
    border: 'none',
    fontSize: '0.875rem',
    fontWeight: 500,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    background: '#f59e0b',
    color: 'white',
    transition: 'all 0.2s',
  },
  generateBtnBlue: {
    background: '#3b82f6',
  },
  loadingSpinner: {
    animation: 'spin 1s linear infinite',
  },
  proposalCard: {
    background: 'white',
    border: '1px solid #e5e7eb',
    borderRadius: '8px',
    padding: '1rem',
    marginBottom: '1rem',
  },
  proposalHeader: {
    fontWeight: 600,
    fontSize: '0.875rem',
    color: '#3b82f6',
    marginBottom: '0.5rem',
  },
  proposalResponse: {
    fontSize: '0.875rem',
    lineHeight: 1.7,
    color: '#374151',
    marginBottom: '0.75rem',
    whiteSpace: 'pre-wrap' as const,
  },
  tierBadge: {
    padding: '0.125rem 0.5rem',
    borderRadius: '10px',
    fontSize: '0.625rem',
    fontWeight: 600,
    textTransform: 'uppercase' as const,
  },
  errorBox: {
    background: '#fef2f2',
    border: '1px solid #fca5a5',
    borderRadius: '8px',
    padding: '0.75rem',
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    color: '#dc2626',
    fontSize: '0.875rem',
  },
};

// ============================================================================
// Types
// ============================================================================

interface ConsultationDetailProps {
  consultation: ConsultationDetailType;
  onClose: () => void;
  onTrack: () => void;
  onUntrack: () => void;
  isTracking: boolean;
}

// ============================================================================
// Component
// ============================================================================

export const ConsultationDetail: React.FC<ConsultationDetailProps> = ({
  consultation,
  onClose,
  onTrack,
  onUntrack,
  isTracking,
}) => {
  const { t } = useTranslation();
  const { user } = useAuth();

  // AI state
  const [analysis, setAnalysis] = useState<ConsultationAnalysis | null>(null);
  const [proposals, setProposals] = useState<ProposalSet | null>(null);
  const [analysisExpanded, setAnalysisExpanded] = useState(false);
  const [proposalsExpanded, setProposalsExpanded] = useState(false);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [loadingProposals, setLoadingProposals] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [proposalsError, setProposalsError] = useState<string | null>(null);

  const statusInfo = STATUS_INFO[consultation.status] || { name: 'Unknown', color: '#6b7280' };
  const typeInfo = CONSULTATION_TYPE_INFO[consultation.consultation_type] || {
    name: 'Initiative',
    color: '#6b7280',
  };

  const isUrgent = consultation.is_closing_soon && consultation.status === 'open';
  const isBlue = user?.subscription_tier === 'blue' || user?.subscription_tier === 'admin';
  const isYellowPlus = isBlue || user?.subscription_tier === 'yellow';

  // Fetch AI analysis
  const handleGetAnalysis = async () => {
    if (analysis) {
      setAnalysisExpanded(!analysisExpanded);
      return;
    }

    setLoadingAnalysis(true);
    setAnalysisError(null);
    try {
      const result = await consultationService.getAnalysis(consultation.id);
      setAnalysis(result);
      setAnalysisExpanded(true);
    } catch (err) {
      setAnalysisError('Failed to generate analysis. Please try again.');
      console.error('Analysis error:', err);
    } finally {
      setLoadingAnalysis(false);
    }
  };

  // Generate AI proposals
  const handleGenerateProposals = async () => {
    if (proposals) {
      setProposalsExpanded(!proposalsExpanded);
      return;
    }

    setLoadingProposals(true);
    setProposalsError(null);
    try {
      const result = await consultationService.generateProposals(consultation.id);
      setProposals(result);
      setProposalsExpanded(true);
    } catch (err) {
      setProposalsError('Failed to generate proposals. Please try again.');
      console.error('Proposals error:', err);
    } finally {
      setLoadingProposals(false);
    }
  };

  // Handle overlay click to close
  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  // Handle escape key
  React.useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  const modalContent = (
    <div style={styles.overlay} onClick={handleOverlayClick}>
      <div style={styles.modal}>
        {/* Header */}
        <div style={styles.header}>
          <button
            style={styles.closeBtn}
            onClick={onClose}
            title={t('common.close', 'Close')}
          >
            <Icon path={mdiClose} size={0.9} />
          </button>

          <h2 style={styles.title}>{consultation.title}</h2>

          <div style={styles.badges}>
            {isUrgent && (
              <span style={{ ...styles.badge, background: '#fef2f2', color: '#dc2626' }}>
                <Icon path={mdiClockAlertOutline} size={0.5} style={{ marginRight: '0.25rem' }} />
                {t('bubble.consultations.closingSoon', 'Closing Soon')}
              </span>
            )}
            <span style={{ ...styles.badge, background: `${statusInfo.color}30`, color: 'white' }}>
              {statusInfo.name}
            </span>
            <span style={styles.badge}>{typeInfo.name}</span>
            {consultation.is_tracked && (
              <span style={{ ...styles.badge, background: '#dcfce7', color: '#059669' }}>
                <Icon path={mdiCheckCircleOutline} size={0.5} style={{ marginRight: '0.25rem' }} />
                {t('bubble.consultations.tracked', 'Tracked')}
              </span>
            )}
          </div>
        </div>

        {/* Content */}
        <div style={styles.content}>
          {/* Meta info */}
          <div style={styles.meta}>
            <div style={styles.metaItem}>
              <span style={styles.metaLabel}>
                {t('bubble.consultations.dg', 'Directorate-General')}
              </span>
              <span style={styles.metaValue}>
                {consultation.dg_name || `DG ${consultation.dg_responsible}` || '-'}
              </span>
            </div>
            <div style={styles.metaItem}>
              <span style={styles.metaLabel}>
                {t('bubble.consultations.deadline', 'Deadline')}
              </span>
              <span style={{ ...styles.metaValue, color: isUrgent ? '#dc2626' : '#111827' }}>
                {consultation.end_date
                  ? new Date(consultation.end_date).toLocaleDateString()
                  : '-'}
                {consultation.days_remaining !== undefined && consultation.status === 'open' && (
                  <span> ({formatDaysRemaining(consultation.days_remaining)})</span>
                )}
              </span>
            </div>
            <div style={styles.metaItem}>
              <span style={styles.metaLabel}>
                {t('bubble.consultations.responses', 'Responses')}
              </span>
              <span style={styles.metaValue}>
                {consultation.feedback_count.toLocaleString()}
              </span>
            </div>
            <div style={styles.metaItem}>
              <span style={styles.metaLabel}>
                {t('bubble.consultations.policyAreas', 'Policy Areas')}
              </span>
              <span style={styles.metaValue}>
                {consultation.policy_areas.length > 0
                  ? consultation.policy_areas.join(', ')
                  : '-'}
              </span>
            </div>
          </div>

          {/* Outcome (if published) */}
          {consultation.outcome_summary && (
            <div style={styles.outcome}>
              <div style={styles.outcomeTitle}>
                <Icon path={mdiInformationOutline} size={0.7} />
                {t('bubble.consultations.outcomePublished', 'Outcome Published')}
              </div>
              <p style={styles.outcomeText}>{consultation.outcome_summary}</p>
            </div>
          )}

          {/* Description */}
          {(consultation.full_description || consultation.description) && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>
                <Icon path={mdiInformationOutline} size={0.7} />
                {t('bubble.consultations.description', 'Description')}
              </h3>
              <p style={styles.description}>
                {consultation.full_description || consultation.description}
              </p>
            </div>
          )}

          {/* AI Analysis Section (Yellow+ tier) */}
          {isYellowPlus && (
            <div style={styles.aiSection}>
              <div style={styles.aiHeader} onClick={handleGetAnalysis}>
                <div style={styles.aiHeaderTitle}>
                  <Icon path={mdiRobotOutline} size={0.9} color="#f59e0b" />
                  <span>{t('bubble.consultations.aiAnalysis', 'AI Analysis')}</span>
                  <span style={{ ...styles.tierBadge, background: '#fef3c7', color: '#92400e' }}>
                    Yellow+
                  </span>
                </div>
                {loadingAnalysis ? (
                  <Icon path={mdiLoading} size={0.8} spin />
                ) : (
                  <Icon path={analysis && analysisExpanded ? mdiChevronUp : mdiChevronDown} size={0.8} />
                )}
              </div>

              {analysisError && (
                <div style={{ padding: '0 1rem 1rem' }}>
                  <div style={styles.errorBox}>
                    <Icon path={mdiAlertCircleOutline} size={0.8} />
                    {analysisError}
                  </div>
                </div>
              )}

              {!analysis && !loadingAnalysis && !analysisError && (
                <div style={{ padding: '0 1rem 1rem', textAlign: 'center' as const }}>
                  <p style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.75rem' }}>
                    {t('bubble.consultations.analysisDescription',
                      'Get AI-powered analysis of this consultation including key questions, requirements, and recommended focus areas.'
                    )}
                  </p>
                  <button
                    style={styles.generateBtn}
                    onClick={handleGetAnalysis}
                    disabled={loadingAnalysis}
                  >
                    <Icon path={mdiRobotOutline} size={0.8} />
                    {t('bubble.consultations.getAnalysis', 'Get AI Analysis')}
                  </button>
                </div>
              )}

              {analysis && analysisExpanded && (
                <div style={styles.aiContent}>
                  <p style={styles.aiSummary}>{analysis.executive_summary}</p>

                  {analysis.key_questions.length > 0 && (
                    <>
                      <h4 style={styles.aiSubheading}>
                        {t('bubble.consultations.keyQuestions', 'Key Questions')}
                      </h4>
                      <ul style={styles.aiList}>
                        {analysis.key_questions.map((q, i) => (
                          <li key={i} style={styles.aiListItem}>{q}</li>
                        ))}
                      </ul>
                    </>
                  )}

                  {analysis.recommended_focus_areas.length > 0 && (
                    <>
                      <h4 style={styles.aiSubheading}>
                        {t('bubble.consultations.focusAreas', 'Recommended Focus Areas')}
                      </h4>
                      <ul style={styles.aiList}>
                        {analysis.recommended_focus_areas.map((a, i) => (
                          <li key={i} style={styles.aiListItem}>{a}</li>
                        ))}
                      </ul>
                    </>
                  )}

                  {analysis.stakeholder_categories.length > 0 && (
                    <>
                      <h4 style={styles.aiSubheading}>
                        {t('bubble.consultations.targetStakeholders', 'Target Stakeholders')}
                      </h4>
                      <p style={{ fontSize: '0.875rem', color: '#374151' }}>
                        {analysis.stakeholder_categories.join(', ')}
                      </p>
                    </>
                  )}

                  {analysis.submission_requirements && (
                    <>
                      <h4 style={styles.aiSubheading}>
                        {t('bubble.consultations.submissionRequirements', 'Submission Requirements')}
                      </h4>
                      <p style={{ fontSize: '0.875rem', color: '#374151' }}>
                        {analysis.submission_requirements}
                      </p>
                    </>
                  )}
                </div>
              )}
            </div>
          )}

          {/* AI Proposals Section (Blue tier only) */}
          {isYellowPlus && (
            <div style={{ ...styles.aiSection, ...styles.aiSectionBlue }}>
              <div style={styles.aiHeader} onClick={isBlue ? handleGenerateProposals : undefined}>
                <div style={styles.aiHeaderTitle}>
                  <Icon path={mdiLightbulbOnOutline} size={0.9} color="#3b82f6" />
                  <span>{t('bubble.consultations.aiProposals', 'AI Response Proposals')}</span>
                  <span style={{ ...styles.tierBadge, background: '#dbeafe', color: '#1e40af' }}>
                    Blue
                  </span>
                </div>
                {isBlue && (
                  loadingProposals ? (
                    <Icon path={mdiLoading} size={0.8} spin />
                  ) : (
                    <Icon path={proposals && proposalsExpanded ? mdiChevronUp : mdiChevronDown} size={0.8} />
                  )
                )}
              </div>

              {proposalsError && (
                <div style={{ padding: '0 1rem 1rem' }}>
                  <div style={styles.errorBox}>
                    <Icon path={mdiAlertCircleOutline} size={0.8} />
                    {proposalsError}
                  </div>
                </div>
              )}

              {!isBlue && (
                <div style={{ padding: '0 1rem 1rem', textAlign: 'center' as const }}>
                  <p style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.75rem' }}>
                    {t('bubble.consultations.proposalsUpgrade',
                      'Upgrade to Professional to generate personalised response proposals based on your documents and interests.'
                    )}
                  </p>
                </div>
              )}

              {isBlue && !proposals && !loadingProposals && !proposalsError && (
                <div style={{ padding: '0 1rem 1rem', textAlign: 'center' as const }}>
                  <p style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.75rem' }}>
                    {t('bubble.consultations.proposalsDescription',
                      'Generate personalised response proposals tailored to your organisation and documents.'
                    )}
                  </p>
                  <button
                    style={{ ...styles.generateBtn, ...styles.generateBtnBlue }}
                    onClick={handleGenerateProposals}
                    disabled={loadingProposals}
                  >
                    <Icon path={mdiLightbulbOnOutline} size={0.8} />
                    {t('bubble.consultations.generateProposals', 'Generate Proposals')}
                  </button>
                </div>
              )}

              {proposals && proposalsExpanded && (
                <div style={styles.aiContent}>
                  <p style={styles.aiSummary}>
                    <strong>{t('bubble.consultations.strategy', 'Strategy')}:</strong> {proposals.overall_strategy}
                  </p>
                  <p style={{ fontSize: '0.875rem', color: '#374151', marginBottom: '1rem' }}>
                    <strong>{t('bubble.consultations.tone', 'Recommended Tone')}:</strong> {proposals.recommended_tone}
                  </p>

                  {proposals.key_messages.length > 0 && (
                    <>
                      <h4 style={styles.aiSubheading}>
                        {t('bubble.consultations.keyMessages', 'Key Messages')}
                      </h4>
                      <ul style={styles.aiList}>
                        {proposals.key_messages.map((m, i) => (
                          <li key={i} style={styles.aiListItem}>{m}</li>
                        ))}
                      </ul>
                    </>
                  )}

                  <h4 style={styles.aiSubheading}>
                    {t('bubble.consultations.proposals', 'Proposals')} ({proposals.proposals.length})
                  </h4>

                  {proposals.proposals.map((proposal) => (
                    <div key={proposal.id} style={styles.proposalCard}>
                      <div style={styles.proposalHeader}>
                        {proposal.question_addressed}
                      </div>
                      <div style={styles.proposalResponse}>
                        {proposal.proposed_response}
                      </div>
                      {proposal.supporting_arguments.length > 0 && (
                        <div style={{ fontSize: '0.8125rem', color: '#6b7280' }}>
                          <strong>{t('bubble.consultations.arguments', 'Arguments')}:</strong>
                          <ul style={{ ...styles.aiList, marginTop: '0.25rem' }}>
                            {proposal.supporting_arguments.map((arg, i) => (
                              <li key={i} style={{ marginBottom: '0.25rem' }}>{arg}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Documents */}
          {consultation.documents && consultation.documents.length > 0 && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>
                <Icon path={mdiFileDocumentOutline} size={0.7} />
                {t('bubble.consultations.documents', 'Documents')}
                <span style={{ fontWeight: 400, color: '#6b7280' }}>
                  ({consultation.documents.length})
                </span>
              </h3>
              <div style={styles.documentList}>
                {consultation.documents.map((doc, index) => (
                  <a
                    key={index}
                    href={doc.file_url || '#'}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={styles.documentItem}
                  >
                    <Icon path={mdiFileDocumentOutline} size={0.7} color="#6b7280" />
                    <span style={{ flex: 1 }}>{doc.title}</span>
                    {doc.file_format && (
                      <span style={{ color: '#9ca3af', fontSize: '0.75rem' }}>
                        {doc.file_format.toUpperCase()}
                      </span>
                    )}
                    <Icon path={mdiOpenInNew} size={0.6} color="#6b7280" />
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Related legislation */}
          {(consultation.com_references.length > 0 || consultation.celex_numbers.length > 0) && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>
                <Icon path={mdiLinkVariant} size={0.7} />
                {t('bubble.consultations.relatedLegislation', 'Related Legislation')}
              </h3>
              <div style={styles.legislationList}>
                {consultation.com_references.map((ref, index) => (
                  <div key={`com-${index}`} style={styles.legislationItem}>
                    <Icon path={mdiFileDocumentOutline} size={0.6} />
                    {ref}
                  </div>
                ))}
                {consultation.celex_numbers.map((celex, index) => (
                  <a
                    key={`celex-${index}`}
                    href={`https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:${celex}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ ...styles.legislationItem, textDecoration: 'none' }}
                  >
                    <Icon path={mdiLinkVariant} size={0.6} />
                    {celex}
                    <Icon path={mdiOpenInNew} size={0.5} />
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={styles.footer}>
          <div style={styles.footerLeft}>
            <Icon path={mdiCalendarClock} size={0.7} />
            {t('bubble.consultations.lastUpdated', 'Last updated')}:{' '}
            {new Date(consultation.last_updated).toLocaleDateString()}
          </div>

          <div style={styles.footerActions}>
            <button
              style={{
                ...styles.btn,
                ...(consultation.is_tracked ? styles.btnTracked : styles.btnSecondary),
              }}
              onClick={consultation.is_tracked ? onUntrack : onTrack}
              disabled={isTracking}
            >
              <Icon
                path={consultation.is_tracked ? mdiBookmark : mdiBookmarkOutline}
                size={0.8}
              />
              {consultation.is_tracked
                ? t('bubble.consultations.untrack', 'Untrack')
                : t('bubble.consultations.track', 'Track')}
            </button>

            {consultation.portal_url && (
              <a
                href={consultation.portal_url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ ...styles.btn, ...styles.btnPrimary, textDecoration: 'none' }}
              >
                <Icon path={mdiOpenInNew} size={0.8} />
                {consultation.source === 'agency'
                  ? (consultation.body_name
                      ? t('bubble.consultations.openOnAgencyNamed', 'Open on {{agency}}', { agency: consultation.body_name })
                      : t('bubble.consultations.openOnAgency', 'Open on its agency website'))
                  : t('bubble.consultations.openInPortal', 'Open in Have Your Say')}
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  // Use portal to render outside parent stacking context
  return createPortal(modalContent, document.body);
};

export default ConsultationDetail;
