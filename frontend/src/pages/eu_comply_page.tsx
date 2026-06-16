// frontend/src/pages/eu_comply_page.tsx
import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LawBrowser } from '../components/eu_comply/law_browser';
import { ComplianceReport } from '../components/eu_comply/compliance_report';
import { ActionPlanTimeline } from '../components/eu_comply/action_plan_timeline';
import { UsageHistory } from '../components/eu_comply/usage_history';
import { FeedbackInvitation } from '../components/shared/feedback_invitation';
import { ComplianceMaturity } from '../components/shared/compliance_maturity';
import { useAuth } from '../hooks/use_auth';
import './eu_comply_page.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// EU Parliament background images
const BACKGROUND_IMAGES = [
  '/assets/backgrounds/eu_flag_wind.jpg',
  '/assets/backgrounds/eu_flags_building.jpg',
  '/assets/backgrounds/european_parliament_esplanade_brussels.jpg',
  '/assets/backgrounds/european_parliament_hemicycle_brussels.jpg',
  '/assets/backgrounds/european_parliament_square_strasbourg.jpg',
  '/assets/backgrounds/european_parliament_strasbourg.jpg',
];

export interface LawCluster {
  id: number;
  name: string;
  policy_area: string;
  description: string;
  applicability: string;
  law_count: number;
  requirement_count: number;
}

export interface ComplianceAnalysis {
  id: number;
  cluster: LawCluster;
  status: 'processing' | 'completed' | 'failed';
  total_requirements: number;
  requirements_met: number;
  requirements_partial: number;
  requirements_gap: number;
  compliance_score: number;
  gap_findings: GapFinding[];
  created_at: string;
  completed_at?: string;
}

export interface GapFinding {
  id: number;
  requirement_id: number;
  article_number: string;
  requirement_text: string;
  status: 'met' | 'partial' | 'gap' | 'not_applicable';
  confidence_score: number;
  evidence_text?: string;
  evidence_source?: string;
  gap_description?: string;
  recommendation?: string;
  priority: number;
  estimated_effort?: string;
  deadline_date?: string;
  deadline_text?: string;
  criticality: string;
}

type ViewState = 'select' | 'upload' | 'results';

interface EUComplyPageProps {
  isSidebarOpen?: boolean;
  setIsSidebarOpen?: (open: boolean) => void;
}

export const EUComplyPage = ({ isSidebarOpen }: EUComplyPageProps) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [viewState, setViewState] = useState<ViewState>('select');
  const [selectedCluster, setSelectedCluster] = useState<LawCluster | null>(null);
  const [analysisResult, setAnalysisResult] = useState<ComplianceAnalysis | null>(null);
  const [uploadedDocuments, setUploadedDocuments] = useState<File[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isHistorySidebarOpen, setIsHistorySidebarOpen] = useState(true);
  const [backgroundImage, setBackgroundImage] = useState('');
  const [isMobile, setIsMobile] = useState(false);

  // Check if mobile on mount and resize
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 1200);
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Close sidebar by default on mobile
  useEffect(() => {
    if (isMobile) {
      setIsHistorySidebarOpen(false);
    }
  }, [isMobile]);

  // Select random background on mount
  useEffect(() => {
    const randomIndex = Math.floor(Math.random() * BACKGROUND_IMAGES.length);
    setBackgroundImage(BACKGROUND_IMAGES[randomIndex]);
  }, []);

  const handleClusterSelect = (cluster: LawCluster) => {
    setSelectedCluster(cluster);
    setViewState('upload');
    setAnalysisResult(null);
    setUploadedDocuments([]);
  };

  const handleDocumentUpload = (files: File[]) => {
    setUploadedDocuments(files);
  };

  const handleAnalyzeCompliance = async () => {
    if (!selectedCluster || uploadedDocuments.length === 0) {
      return;
    }

    setIsAnalyzing(true);

    try {
      // Create FormData for file upload
      const formData = new FormData();
      formData.append('cluster_id', selectedCluster.id.toString());
      uploadedDocuments.forEach(file => {
        formData.append('documents', file);
      });

      // Call backend API
      const response = await fetch(`${API_BASE_URL}/api/eu-law-comply/analyze`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${useAuth.getState().token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Analysis failed');
      }

      const initialResult = await response.json();

      // The backend runs analysis asynchronously - poll until completed
      const analysisId = initialResult.id;
      const token = useAuth.getState().token;
      let attempts = 0;
      const maxAttempts = 60; // 2 minutes max

      while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        attempts++;

        const pollResponse = await fetch(`${API_BASE_URL}/api/eu-law-comply/analysis/${analysisId}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });

        if (!pollResponse.ok) continue;

        const pollResult = await pollResponse.json();

        if (pollResult.status === 'completed') {
          setAnalysisResult(pollResult);
          setViewState('results');
          return;
        } else if (pollResult.status === 'failed') {
          throw new Error('Analysis failed on the server');
        }
      }

      throw new Error('Analysis timed out');
    } catch (error) {
      console.error('Compliance analysis error:', error);
      alert(t('comply.errorAnalysis'));
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleBackToSelection = () => {
    setViewState('select');
    setSelectedCluster(null);
    setAnalysisResult(null);
    setUploadedDocuments([]);
  };

  const handleBackToUpload = () => {
    setViewState('upload');
    setAnalysisResult(null);
  };

  const handleAskChatbot = (finding: GapFinding) => {
    // Generate a contextual question about the compliance finding
    const question = `I need help with ${finding.article_number} compliance. The requirement is: "${finding.requirement_text}". ${
      finding.gap_description ? `The gap identified is: ${finding.gap_description}. ` : ''
    }${finding.recommendation ? `Current recommendation: ${finding.recommendation}. ` : ''}How can I address this compliance requirement?`;

    // Navigate to main chatbot with pre-filled question
    navigate('/chat', {
      state: {
        initialQuestion: question,
        source: 'eu_comply',
        findingId: finding.id
      }
    });
  };

  const handleSelectPastAnalysis = async (analysisId: number) => {
    try {
      // Fetch the analysis details
      const response = await fetch(`${API_BASE_URL}/api/eu-law-comply/analysis/${analysisId}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${useAuth.getState().token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch analysis');
      }

      const result: ComplianceAnalysis = await response.json();
      setAnalysisResult(result);
      setSelectedCluster(result.cluster);
      setViewState('results');
    } catch (error) {
      console.error('Error fetching past analysis:', error);
      alert(t('comply.errorLoadPast'));
    }
  };

  const toggleHistorySidebar = () => {
    setIsHistorySidebarOpen(!isHistorySidebarOpen);
  };

  return (
    <div className={`eu-comply-page ${isSidebarOpen ? '' : 'sidebar-closed'}`}>
      {/* Background Image with Rotation */}
      {backgroundImage && (
        <>
          <img
            className="eu-comply-page__background-image"
            src={backgroundImage}
            alt="EU Parliament"
          />
          <div className="eu-comply-page__background-overlay"></div>
        </>
      )}

      <div className="eu-comply-page__layout">
        <div className="eu-comply-page__container">
          {/* Header */}
          <div className="eu-comply-page__header">
            <div className="eu-comply-page__header-content">
              <img
                src="/assets/brubru_eulawcomply.png"
                alt="EU Law Comply"
                className="eu-comply-page__mascot"
              />
              <div>
                <h1 className="eu-comply-page__title">{t('comply.title')}</h1>
                <p className="eu-comply-page__subtitle">{t('comply.subtitle')}</p>
              </div>
            </div>
            <div className="eu-comply-page__header-actions">
              <div className="eu-comply-page__tier-notice">
                <span className="mdi mdi-information-outline"></span>
                {t('comply.tierNotice')}
              </div>
              <button
                className="eu-comply-page__sidebar-toggle"
                onClick={toggleHistorySidebar}
                title={isHistorySidebarOpen ? t('common.hideHistory') : t('common.showHistory')}
              >
                <span className={`mdi ${isHistorySidebarOpen ? 'mdi-chevron-right' : 'mdi-chevron-left'}`}></span>
              </button>
            </div>
          </div>

        {/* Compliance Maturity card — only on the selection landing view,
            so it does not clutter the analysis flow. */}
        {viewState === 'select' && <ComplianceMaturity />}

        {/* Main Content */}
        {viewState === 'select' && (
          <LawBrowser onSelectCluster={handleClusterSelect} />
        )}

        {viewState === 'upload' && selectedCluster && (
          <div className="eu-comply-page__upload-section">
            <button
              className="eu-comply-page__back-button"
              onClick={handleBackToSelection}
            >
              <span className="mdi mdi-arrow-left"></span>
              {t('comply.backToClusters')}
            </button>

            <div className="eu-comply-page__cluster-info">
              <h2>{selectedCluster.name}</h2>
              <div className="eu-comply-page__cluster-stats">
                <div className="eu-comply-page__stat">
                  <span className="mdi mdi-file-document-multiple"></span>
                  <span>{selectedCluster.law_count} {t('comply.relatedLaws')}</span>
                </div>
                <div className="eu-comply-page__stat">
                  <span className="mdi mdi-gavel"></span>
                  <span>{selectedCluster.requirement_count} {t('comply.requirements')}</span>
                </div>
              </div>
              <p className="eu-comply-page__cluster-description">
                {selectedCluster.description}
              </p>
              <p className="eu-comply-page__cluster-applicability">
                <strong>{t('comply.appliesTo')}</strong> {selectedCluster.applicability}
              </p>
            </div>

            <div className="eu-comply-page__upload-box">
              <h3>{t('comply.uploadCompanyDocs')}</h3>
              <p>{t('comply.uploadHint')}</p>

              <input
                type="file"
                accept=".pdf,.docx,.txt"
                multiple
                onChange={(e) => {
                  const files = Array.from(e.target.files || []);
                  handleDocumentUpload(files);
                }}
                style={{ marginBottom: '1rem' }}
              />

              {uploadedDocuments.length > 0 && (
                <div className="eu-comply-page__uploaded-files">
                  <h4>{t('comply.uploadedFiles')}</h4>
                  <ul>
                    {uploadedDocuments.map((file, idx) => (
                      <li key={idx}>
                        <span className="mdi mdi-file-document"></span>
                        {file.name}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <button
                className="eu-comply-page__analyze-button"
                onClick={handleAnalyzeCompliance}
                disabled={uploadedDocuments.length === 0 || isAnalyzing}
              >
                {isAnalyzing ? (
                  <>
                    <span className="mdi mdi-loading mdi-spin"></span>
                    {t('comply.analyzing')}
                  </>
                ) : (
                  <>
                    <span className="mdi mdi-chart-line"></span>
                    {t('comply.analyzeCompliance')}
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {viewState === 'results' && analysisResult && (
          <div className="eu-comply-page__results-section">
            <button
              className="eu-comply-page__back-button"
              onClick={handleBackToUpload}
            >
              <span className="mdi mdi-arrow-left"></span>
              {t('comply.uploadMoreDocs')}
            </button>

            <ComplianceReport
              analysis={analysisResult}
              onAskChatbot={handleAskChatbot}
            />

            <ActionPlanTimeline
              gapFindings={(analysisResult.gap_findings || []).filter(
                f => f.status === 'gap' || f.status === 'partial'
              )}
            />
          </div>
        )}
        </div>

        {/* History Sidebar - Desktop (in-page) */}
        {!isMobile && isHistorySidebarOpen && (
          <div className="eu-comply-page__history-sidebar">
            <UsageHistory
              onSelectAnalysis={handleSelectPastAnalysis}
              selectedAnalysisId={analysisResult?.id}
            />
            <FeedbackInvitation
              featureName={t('comply.feedbackTitle')}
              featureDescription={t('comply.feedbackDescription')}
              variant="sidebar"
            />
          </div>
        )}
      </div>

      {/* History Sidebar - Mobile (portal to body for proper z-index) */}
      {isMobile && isHistorySidebarOpen && createPortal(
        <>
          <div
            className="eu-comply-page__sidebar-overlay"
            onClick={toggleHistorySidebar}
            aria-hidden="true"
          />
          <div className="eu-comply-page__history-sidebar eu-comply-page__history-sidebar--mobile">
            <button
              className="eu-comply-page__sidebar-close"
              onClick={toggleHistorySidebar}
              aria-label={t('common.closeSidebar')}
            >
              <span className="mdi mdi-close"></span>
            </button>
            <UsageHistory
              onSelectAnalysis={handleSelectPastAnalysis}
              selectedAnalysisId={analysisResult?.id}
            />
            <FeedbackInvitation
              featureName={t('comply.feedbackTitle')}
              featureDescription={t('comply.feedbackDescription')}
              variant="sidebar"
            />
          </div>
        </>,
        document.body
      )}
    </div>
  );
};
