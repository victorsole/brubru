// frontend/src/pages/eu_comply_page.tsx
import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LawBrowser } from '../components/eu_comply/law_browser';
import { ComplianceReport } from '../components/eu_comply/compliance_report';
import { ActionPlanTimeline } from '../components/eu_comply/action_plan_timeline';
import { UsageHistory } from '../components/eu_comply/usage_history';
import { ClusterRequirementsPreview } from '../components/eu_comply/cluster_requirements_preview';
import { WorkspaceList } from '../components/eu_comply/workspace_list';
import { ReusableDocuments } from '../components/eu_comply/reusable_documents';
import { RunDiff } from '../components/eu_comply/run_diff';
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
  /** Who the obligation binds. Anything other than 'economic_operator'
   *  explains a not_applicable verdict that would otherwise look arbitrary. */
  addressee?: string;
}

type ViewState = 'select' | 'upload' | 'results';

const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.txt'];

const formatBytes = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const fileIcon = (name: string): string => {
  const n = name.toLowerCase();
  if (n.endsWith('.pdf')) return 'mdi-file-pdf-box';
  if (n.endsWith('.docx') || n.endsWith('.doc')) return 'mdi-file-word-box';
  return 'mdi-file-document-outline';
};

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
  // Documents from an earlier run of this package, selected for re-use. Kept
  // separate from uploadedDocuments because they are already stored server-side
  // and travel as ids, not as file bodies.
  const [reuseIds, setReuseIds] = useState<string[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  // Closed by default. The sidebar holds ~25% of the page width for the entire
  // scroll length, and for every user without a past analysis it renders
  // "No compliance analyses yet" -- an empty column beside the actual product.
  // The header toggle opens it, and that state is remembered per session.
  const [isHistorySidebarOpen, setIsHistorySidebarOpen] = useState(false);
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
    setReuseIds([]);
    setUploadError(null);
  };

  /** Open a package straight from the workspace list, which only knows its id. */
  const handleOpenWorkspace = async (clusterId: number) => {
    setUploadError(null);
    try {
      const r = await fetch(`${API_BASE_URL}/api/eu-law-comply/clusters/${clusterId}`, {
        headers: { Authorization: `Bearer ${useAuth.getState().token}` },
      });
      if (!r.ok) throw new Error(String(r.status));
      handleClusterSelect(await r.json());
    } catch {
      // Leave the user on the catalogue rather than in a half-open package.
      setUploadError(t('comply.workspaces.openFailed',
        'Could not open that package. Please pick it from the list below.'));
    }
  };

  // Append rather than replace, and drop anything the backend would reject with
  // a 400 anyway (it validates the same extension list). Dedupe on name+size so
  // dropping the same file twice does not queue it twice.
  const addFiles = (incoming: File[]) => {
    const accepted = incoming.filter((f) =>
      ACCEPTED_EXTENSIONS.some((ext) => f.name.toLowerCase().endsWith(ext))
    );
    const rejected = incoming.length - accepted.length;
    if (rejected > 0) {
      setUploadError(
        t('comply.unsupportedFiles', {
          defaultValue: '{{count}} file(s) skipped. Only PDF, DOCX and TXT can be analysed.',
          count: rejected,
        })
      );
    } else {
      setUploadError(null);
    }
    setUploadedDocuments((prev) => {
      const seen = new Set(prev.map((f) => `${f.name}:${f.size}`));
      return [...prev, ...accepted.filter((f) => !seen.has(`${f.name}:${f.size}`))];
    });
  };

  const removeFile = (index: number) => {
    setUploadedDocuments((prev) => prev.filter((_, i) => i !== index));
  };

  const handleAnalyzeCompliance = async () => {
    // Either source is enough on its own: a fresh upload, a document re-used
    // from a previous run, or both together.
    if (!selectedCluster || (uploadedDocuments.length === 0 && reuseIds.length === 0)) {
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
      if (reuseIds.length > 0) {
        formData.append('reuse_document_ids', reuseIds.join(','));
      }

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
      // The backend checks requirements one at a time, ~4s each (two OpenAI
      // calls per requirement). The old 60-attempt / 2-minute ceiling only fit
      // clusters up to ~28 requirements, so 30 of the 62 packages -- including
      // GDPR at 401 -- reported "Analysis timed out" while the backend was
      // still running and would go on to complete successfully. Poll for 15
      // minutes; the analysis is recoverable from history either way.
      const maxAttempts = 450; // 15 minutes at 2s

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
    setReuseIds([]);
    setUploadError(null);
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

      {/* The layout grid is `1fr 350px`. When the history sidebar is closed the
          second column still reserved 350px, leaving a dead strip beside the
          content. Collapse to a single column unless the sidebar is showing. */}
      <div
        className={`eu-comply-page__layout${
          !isMobile && isHistorySidebarOpen ? '' : ' eu-comply-page__layout--full'
        }`}
      >
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

        {/* Compliance Maturity — only on the selection landing view, and
            collapsed, so the score stays glanceable without owning the fold. */}
        {viewState === 'select' && <ComplianceMaturity collapsible />}

        {/* Main Content */}
        {/* Returning users first: the packages already worked on, with their
            latest score and open actions. Renders nothing on a first visit. */}
        {viewState === 'select' && <WorkspaceList onOpen={handleOpenWorkspace} />}

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

            {/* Workspace header: the facts a user needs to confirm they picked
                the right package, as chips rather than three stacked paragraphs.
                The full scope text is behind a disclosure -- it runs to CN-code
                length on several clusters and used to push the upload control
                below the fold. */}
            <div className="comply-workspace__head">
              <h2 className="comply-workspace__title">{selectedCluster.name}</h2>
              <div className="comply-workspace__chips">
                <span className="comply-workspace__chip">
                  <span className="mdi mdi-label-outline"></span>
                  {selectedCluster.policy_area}
                </span>
                <span className="comply-workspace__chip">
                  <span className="mdi mdi-file-document-multiple-outline"></span>
                  {selectedCluster.law_count} {t('comply.relatedLaws')}
                </span>
                <span className="comply-workspace__chip comply-workspace__chip--accent">
                  <span className="mdi mdi-gavel"></span>
                  {selectedCluster.requirement_count} {t('comply.requirements')}
                </span>
              </div>
              <p className="comply-workspace__description">
                {selectedCluster.description}
              </p>
              {selectedCluster.applicability && (
                <details className="comply-workspace__scope">
                  <summary>{t('comply.appliesTo')}</summary>
                  <p>{selectedCluster.applicability}</p>
                </details>
              )}
            </div>

            {/* Let the user see the obligations BEFORE handing over internal
                documents. The endpoint existed and was called by nothing. */}
            <ClusterRequirementsPreview
              clusterId={selectedCluster.id}
              requirementCount={selectedCluster.requirement_count}
            />

            {/* Documents this package was checked against before. Re-checking
                after remediation is the point of a durable workspace, and until
                now it asked the user to find the same file again. */}
            <ReusableDocuments
              clusterId={selectedCluster.id}
              selected={reuseIds}
              onChange={setReuseIds}
            />

            {/* Drag-and-drop zone. This was a raw <input type="file">, which is
                unstyleable across browsers and read as an unfinished form. */}
            <div
              className={`comply-dropzone${isDragging ? ' comply-dropzone--active' : ''}${
                uploadedDocuments.length ? ' comply-dropzone--compact' : ''
              }`}
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                addFiles(Array.from(e.dataTransfer.files || []));
              }}
            >
              <input
                id="comply-file-input"
                type="file"
                accept=".pdf,.docx,.doc,.txt"
                multiple
                className="comply-dropzone__input"
                onChange={(e) => {
                  addFiles(Array.from(e.target.files || []));
                  e.target.value = '';
                }}
              />
              <label htmlFor="comply-file-input" className="comply-dropzone__label">
                <span className="mdi mdi-cloud-upload-outline comply-dropzone__icon"></span>
                <span className="comply-dropzone__primary">
                  {t('comply.dropzoneTitle', 'Drag your policy documents here')}
                </span>
                <span className="comply-dropzone__secondary">
                  {t('comply.dropzoneBrowse', 'or click to browse')}
                </span>
                <span className="comply-dropzone__formats">
                  {t('comply.dropzoneFormats', 'PDF, DOCX or TXT')}
                </span>
              </label>
            </div>

            {uploadError && (
              <p className="comply-dropzone__error" role="alert">
                <span className="mdi mdi-alert-circle-outline"></span>
                {uploadError}
              </p>
            )}

            {uploadedDocuments.length > 0 && (
              <ul className="comply-filelist">
                {uploadedDocuments.map((file, idx) => (
                  <li className="comply-filelist__item" key={`${file.name}-${idx}`}>
                    <span className={`mdi ${fileIcon(file.name)} comply-filelist__icon`}></span>
                    <span className="comply-filelist__name" title={file.name}>{file.name}</span>
                    <span className="comply-filelist__size">{formatBytes(file.size)}</span>
                    <button
                      type="button"
                      className="comply-filelist__remove"
                      onClick={() => removeFile(idx)}
                      aria-label={t('comply.removeFile', { defaultValue: 'Remove {{name}}', name: file.name })}
                    >
                      <span className="mdi mdi-close"></span>
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <div className="comply-actionbar">
              <div className="comply-actionbar__summary">
                {uploadedDocuments.length + reuseIds.length === 0
                  ? t('comply.actionbarEmpty', 'Add at least one document to run the analysis')
                  : t('comply.actionbarReady', {
                      defaultValue:
                        '{{docs}} document(s) will be checked against {{reqs}} requirements',
                      // Re-used documents count towards the total: the summary
                      // has to match what the run will actually read, or the
                      // action bar says "0 documents" on a re-use-only run.
                      docs: uploadedDocuments.length + reuseIds.length,
                      reqs: selectedCluster.requirement_count,
                    })}
              </div>
              <button
                className="eu-comply-page__analyze-button"
                onClick={handleAnalyzeCompliance}
                disabled={(uploadedDocuments.length === 0 && reuseIds.length === 0) || isAnalyzing}
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

            {isAnalyzing && (
              <p className="comply-actionbar__note">
                <span className="mdi mdi-information-outline"></span>
                {t('comply.analysingNote', {
                  defaultValue:
                    'Checking {{reqs}} requirements one by one. Large packages can take several minutes; you can leave this page and reopen the analysis from your history.',
                  reqs: selectedCluster.requirement_count,
                })}
              </p>
            )}
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

            {/* What moved since the last check. A score on its own has no
                direction; this says whether the remediation work landed.
                Renders nothing when there is no earlier run to compare. */}
            <RunDiff analysisId={analysisResult.id} />

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
