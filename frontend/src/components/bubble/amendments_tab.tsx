/**
 * Amendments Tab Component
 *
 * Three sub-tabs:
 * - My Amendments: User's drafted amendments from the Amendator
 * - MEP Amendments: EP committee amendments dashboard
 * - Comparative Analysis: User vs MEP alignment (Phase 4)
 *
 * Part of My EU Bubble - Amendments tab
 */

import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import Icon from '@mdi/react';
import {
  mdiFileDocumentOutline,
  mdiViewList,
  mdiViewModule,
  mdiPencilOutline,
  mdiOpenInNew,
  mdiAccountGroupOutline,
  mdiScaleBalance,
  mdiFileEdit,
} from '@mdi/js';
import { useAuth } from '../../hooks/use_auth';
import { useLegislativeTrains } from '../../hooks/use_legislative_trains';
import type { TrackedFile } from '../../hooks/use_legislative_trains';
import { MEPAmendmentsTab } from './mep_amendments_tab';
import { MEPComparativeTab } from './mep_comparative_tab';
import { LegislativeFileDetail } from './legislative_file_detail';
import { plainLanguageTypeKey } from '../../utils/procedure_type';
import { MeubHeader } from './meub_header';
import './amendments_tab.css';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api`;

/**
 * The CELEX an amendment was drafted against.
 *
 * `document_id` is stored as "eurlex-<celex>" for anything loaded from
 * EUR-Lex; otherwise the tracked file carries the CELEX list. Needed to hand
 * the amendment back to the Amendator, which hydrates a law from
 * ?celex=<celex> and scrolls to ?amendmentId=<id>.
 */
const celexOf = (amendment: Amendment, trackedFile: TrackedFile | null): string | null => {
  const fromDoc = amendment.document_id?.startsWith('eurlex-')
    ? amendment.document_id.slice('eurlex-'.length)
    : null;
  return fromDoc || trackedFile?.celex_numbers?.[0] || null;
};

/**
 * The action that was missing from every amendment card: a way back into the
 * Amendator to keep working on it. The cards carried only a status dropdown,
 * so a drafted amendment could be re-labelled but never reopened.
 *
 * The Amendator hydrates a law from ?celex= and scrolls to ?amendmentId=.
 * Where no CELEX can be resolved there is nothing to hydrate, so the card
 * says so instead of offering a button that would land on an empty editor.
 */
function AmendmentOpen({ amendment, trackedFile, navigate, t }: {
  amendment: Amendment;
  trackedFile: TrackedFile | null;
  navigate: (to: string) => void;
  t: TFunction;
}) {
  const celex = celexOf(amendment, trackedFile);
  if (!celex) {
    return (
      <span className="amendments-tab__open-note">
        {t('amendmentsTab.noSourceLaw', 'Source law unknown')}
      </span>
    );
  }
  return (
    <button
      type="button"
      className="amendments-tab__open-btn"
      onClick={() => navigate(
        `/amendator?celex=${encodeURIComponent(celex)}&amendmentId=${encodeURIComponent(amendment.id)}`,
      )}
      title={t('amendmentsTab.openInAmendator', 'Open in the Amendator')}
    >
      <Icon path={mdiFileEdit} size={0.7} />
      {t('amendmentsTab.openInAmendator', 'Open in the Amendator')}
    </button>
  );
}

interface Amendment {
  id: string;
  document_id: string;
  document_filename: string;
  element_type: string;
  element_number: string;
  position_text: string;
  amendment_type: string;
  original_text: string;
  proposed_text: string;
  justification: string;
  status: string;
  created_at: string;
  updated_at: string;
  carriage_id?: string;
  procedure_reference?: string;
}

interface AmendmentGroup {
  trackedFile: TrackedFile | null;
  amendments: Amendment[];
  groupId: string;
}

type AmendmentSubTab = 'my-amendments' | 'mep-amendments' | 'comparative';

export const AmendmentsTab = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { token } = useAuth();
  const [searchParams] = useSearchParams();
  // Deep-link from My Tracked Files: ?tab=amendments&procedure=<oeil_ref>
  const initialProcedure = searchParams.get('procedure') || undefined;
  const { trackedFiles, fetchTrackedFiles, fetchFileDetail } = useLegislativeTrains();
  const [amendments, setAmendments] = useState<Amendment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [documentFilter, setDocumentFilter] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'list' | 'grouped'>('grouped');
  const [activeSubTab, setActiveSubTab] = useState<AmendmentSubTab>(
    initialProcedure ? 'mep-amendments' : 'my-amendments',
  );

  useEffect(() => {
    fetchAmendments();
    fetchTrackedFiles();
  }, []);

  const fetchAmendments = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/amendments`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setAmendments(data.amendments || []);
      } else {
        console.error('[ERROR] Failed to fetch amendments, status:', response.status);
      }
    } catch (error) {
      console.error('[ERROR] Error fetching amendments:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredAmendments = amendments.filter(amendment => {
    if (statusFilter !== 'all' && amendment.status !== statusFilter) return false;
    if (documentFilter !== 'all' && amendment.document_id !== documentFilter) return false;
    return true;
  });

  const handleStatusChange = async (id: string, newStatus: string) => {
    try {
      const response = await fetch(`${API_BASE}/amendments/${id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status: newStatus }),
      });

      if (response.ok) {
        // Refresh amendments list
        fetchAmendments();
      }
    } catch (error) {
      console.error('Error updating amendment status:', error);
    }
  };

  const uniqueDocuments = [...new Set(amendments.map(a => a.document_id))];

  const statusCounts = {
    all: amendments.length,
    draft: amendments.filter(a => a.status === 'draft').length,
    candidate: amendments.filter(a => a.status === 'candidate').length,
    tabled: amendments.filter(a => a.status === 'tabled').length,
    adopted: amendments.filter(a => a.status === 'adopted').length,
    rejected: amendments.filter(a => a.status === 'rejected').length,
    withdrawn: amendments.filter(a => a.status === 'withdrawn').length,
  };

  // Group amendments by tracked file
  const groupAmendmentsByTrackedFile = (): AmendmentGroup[] => {
    const groups: Map<string, AmendmentGroup> = new Map();

    filteredAmendments.forEach(amendment => {
      // Try to find matching tracked file by carriage_id or CELEX
      let matchedFile: TrackedFile | null = null;
      let groupId = 'untracked';

      if (amendment.carriage_id) {
        matchedFile = trackedFiles.find(f => f.carriage_id === amendment.carriage_id) || null;
        groupId = amendment.carriage_id;
      }

      // If no carriage_id match, try to match by CELEX
      if (!matchedFile && amendment.document_id) {
        const normalizedCelex = amendment.document_id.replace('eurlex-', '');
        matchedFile = trackedFiles.find(f =>
          f.celex_numbers?.includes(normalizedCelex)
        ) || null;
        if (matchedFile) {
          groupId = matchedFile.carriage_id;
        } else {
          groupId = `doc-${amendment.document_id}`;
        }
      }

      if (!groups.has(groupId)) {
        groups.set(groupId, {
          trackedFile: matchedFile,
          amendments: [],
          groupId,
        });
      }
      groups.get(groupId)!.amendments.push(amendment);
    });

    // Sort: tracked files first (by title), then untracked (by doc id)
    return Array.from(groups.values()).sort((a, b) => {
      if (a.trackedFile && !b.trackedFile) return -1;
      if (!a.trackedFile && b.trackedFile) return 1;
      if (a.trackedFile && b.trackedFile) {
        // Group by committee first, then by title (matches MTF ordering).
        const ca = a.trackedFile.lead_committee || '';
        const cb = b.trackedFile.lead_committee || '';
        return ca.localeCompare(cb) || a.trackedFile.title.localeCompare(b.trackedFile.title);
      }
      return a.groupId.localeCompare(b.groupId);
    });
  };

  const amendmentGroups = groupAmendmentsByTrackedFile();

  const getStatusColor = (status: string) => {
    const statusMap: Record<string, string> = {
      announced: '#9e9e9e',
      legislative_initiative: '#2196f3',
      tabled: '#ff9800',
      close_to_adoption: '#4caf50',
      completed: '#4caf50',
      blocked: '#f44336',
      withdrawn: '#757575',
    };
    return statusMap[status] || '#9e9e9e';
  };

  return (
    <div className="amendments-tab">
      {/* Sub-tabs: My Amendments | MEP Amendments | Comparative Analysis */}
      <div className="amendments-tab__sub-tabs">
        <button
          className={`amendments-tab__sub-tab ${activeSubTab === 'my-amendments' ? 'amendments-tab__sub-tab--active' : ''}`}
          onClick={() => setActiveSubTab('my-amendments')}
        >
          {t('amendmentsTab.myAmendments')}
        </button>
        <button
          className={`amendments-tab__sub-tab ${activeSubTab === 'mep-amendments' ? 'amendments-tab__sub-tab--active' : ''}`}
          onClick={() => setActiveSubTab('mep-amendments')}
        >
          <Icon path={mdiAccountGroupOutline} size={0.7} />
          {t('amendmentsTab.mepAmendments')}
        </button>
        <button
          className={`amendments-tab__sub-tab ${activeSubTab === 'comparative' ? 'amendments-tab__sub-tab--active' : ''}`}
          onClick={() => setActiveSubTab('comparative')}
        >
          <Icon path={mdiScaleBalance} size={0.7} />
          {t('amendmentsTab.comparativeAnalysis')}
        </button>
      </div>

      {/* MEP Amendments sub-tab */}
      {activeSubTab === 'mep-amendments' && <MEPAmendmentsTab initialProcedure={initialProcedure} />}

      {/* Comparative Analysis sub-tab */}
      {activeSubTab === 'comparative' && <MEPComparativeTab />}

      {/* My Amendments sub-tab (existing content) */}
      {activeSubTab === 'my-amendments' && (
      <>
      {/* Header. The title uses the same string as the sidebar: it read
          "My Amendments" here and "Amendments" in the navigation. */}
      <MeubHeader
        icon={mdiFileEdit}
        title={t('bubble.amendments', 'Amendments')}
        aside={
          <>
            <div className="amendments-tab__summary">
              <span className="amendments-tab__summary-item">
                {t('amendmentsTab.total')}: <strong>{amendments.length}</strong>
              </span>
              <span className="amendments-tab__summary-item">
                {t('amendmentsTab.documents')}: <strong>{uniqueDocuments.length}</strong>
              </span>
            </div>
            <div className="amendments-tab__view-toggle">
              <button
                className={`amendments-tab__view-btn ${viewMode === 'grouped' ? 'amendments-tab__view-btn--active' : ''}`}
                onClick={() => setViewMode('grouped')}
                title={t('amendmentsTab.groupByFile')}
              >
                <Icon path={mdiViewModule} size={0.8} />
                {t('amendmentsTab.grouped')}
              </button>
              <button
                className={`amendments-tab__view-btn ${viewMode === 'list' ? 'amendments-tab__view-btn--active' : ''}`}
                onClick={() => setViewMode('list')}
                title={t('amendmentsTab.listView')}
              >
                <Icon path={mdiViewList} size={0.8} />
                {t('amendmentsTab.list')}
              </button>
            </div>
          </>
        }
      />

      {/* Document Filter */}
      {uniqueDocuments.length > 1 && (
        <div className="amendments-tab__document-filter">
          <label>{t('amendmentsTab.filterByDocument')}</label>
          <select
            value={documentFilter}
            onChange={(e) => setDocumentFilter(e.target.value)}
            className="amendments-tab__filter-select"
          >
            <option value="all">{t('amendmentsTab.allDocuments')}</option>
            {uniqueDocuments.map(docId => (
              <option key={docId} value={docId}>{docId}</option>
            ))}
          </select>
        </div>
      )}

      {/* Status Filters */}
      <div className="amendments-tab__status-filters">
        {[
          { value: 'all', label: t('amendmentsTab.statusAll'), color: '#666' },
          { value: 'draft', label: t('amendmentsTab.statusDraft'), color: '#999' },
          { value: 'candidate', label: t('amendmentsTab.statusCandidate'), color: '#f57c00' },
          { value: 'tabled', label: t('amendmentsTab.statusTabled'), color: '#059669' },
          { value: 'adopted', label: t('amendmentsTab.statusAdopted'), color: '#2e7d32' },
          { value: 'rejected', label: t('amendmentsTab.statusRejected'), color: '#dc3545' },
          { value: 'withdrawn', label: t('amendmentsTab.statusWithdrawn'), color: '#6b7280' },
        ].map(status => (
          <button
            key={status.value}
            className={`amendments-tab__status-btn ${
              statusFilter === status.value ? 'amendments-tab__status-btn--active' : ''
            }`}
            style={{ '--status-color': status.color } as any}
            onClick={() => setStatusFilter(status.value)}
          >
            {status.label}
            <span className="amendments-tab__status-count">
              {statusCounts[status.value as keyof typeof statusCounts]}
            </span>
          </button>
        ))}
      </div>

      {/* Amendments List */}
      <div className="amendments-tab__content">
        {isLoading ? (
          <div className="amendments-tab__loading">{t('amendmentsTab.loadingAmendments')}</div>
        ) : filteredAmendments.length === 0 ? (
          <div className="amendments-tab__empty">
            <p>{t('amendmentsTab.noAmendmentsFound')}</p>
            <small>{t('amendmentsTab.createInAmendator')}</small>
          </div>
        ) : viewMode === 'grouped' ? (
          /* Grouped View */
          <div className="amendments-tab__grouped">
            {amendmentGroups.map(group => (
              <div key={group.groupId} className="amendments-tab__group">
                {/* Group Header */}
                <div className="amendments-tab__group-header">
                  {group.trackedFile ? (
                    <>
                      <div className="amendments-tab__group-info">
                        <div className="amendments-tab__group-status-row">
                          <span
                            className="amendments-tab__group-status"
                            style={{ backgroundColor: getStatusColor(group.trackedFile.current_status) }}
                          >
                            {group.trackedFile.current_status.replace(/_/g, ' ')}
                          </span>
                          {group.trackedFile.lead_committee && (
                            <span className="amendments-tab__group-committee">
                              {group.trackedFile.lead_committee}
                            </span>
                          )}
                          {plainLanguageTypeKey(group.trackedFile.oeil_procedure_ref) && (
                            <span className="amendments-tab__group-kind">
                              {t(`myFilesTab.${plainLanguageTypeKey(group.trackedFile.oeil_procedure_ref)}`)}
                            </span>
                          )}
                          {group.trackedFile.oeil_procedure_ref && (
                            <span className="amendments-tab__group-ref">
                              {group.trackedFile.oeil_procedure_ref}
                            </span>
                          )}
                          <span className="amendments-tab__group-count">
                            {group.amendments.length} amendment{group.amendments.length !== 1 ? 's' : ''}
                          </span>
                        </div>
                        <h3 className="amendments-tab__group-title">
                          <button
                            type="button"
                            className="amendments-tab__group-title-btn"
                            onClick={() => fetchFileDetail(group.trackedFile!.file_id)}
                          >
                            <Icon path={mdiFileDocumentOutline} size={0.9} />
                            {group.trackedFile.title}
                          </button>
                        </h3>
                      </div>
                      <div className="amendments-tab__group-actions">
                        <button
                          className="amendments-tab__group-action-btn"
                          onClick={() => {
                            const celex = group.trackedFile?.celex_numbers?.[0];
                            navigate(celex ? `/amendator?celex=${encodeURIComponent(celex)}` : '/amendator');
                          }}
                          title={t('amendmentsTab.draftMore')}
                        >
                          <Icon path={mdiPencilOutline} size={0.7} />
                        </button>
                        {group.trackedFile.oeil_procedure_ref && (
                          <a
                            href={`https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${group.trackedFile.oeil_procedure_ref}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="amendments-tab__group-action-btn"
                            title={t('amendmentsTab.viewInOeil')}
                          >
                            <Icon path={mdiOpenInNew} size={0.7} />
                          </a>
                        )}
                      </div>
                    </>
                  ) : (
                    <div className="amendments-tab__group-info amendments-tab__group-info--untracked">
                      <h3 className="amendments-tab__group-title amendments-tab__group-title--untracked">
                        <Icon path={mdiFileDocumentOutline} size={0.9} />
                        {group.amendments[0]?.document_filename || group.groupId.replace('doc-', '')}
                      </h3>
                      <span className="amendments-tab__group-count">
                        {group.amendments.length} amendment{group.amendments.length !== 1 ? 's' : ''}
                      </span>
                    </div>
                  )}
                </div>

                {/* Group Amendments */}
                <div className="amendments-tab__group-list">
                  {group.amendments.map(amendment => (
                    <div
                      key={amendment.id}
                      className="amendments-tab__card amendments-tab__card--compact"
                      data-status={amendment.status}
                    >
                      <div className="amendments-tab__card-header">
                        <div className="amendments-tab__card-status" data-status={amendment.status}>
                          {amendment.status}
                        </div>
                        <span className="amendments-tab__meta-badge amendments-tab__meta-badge--type">
                          {amendment.amendment_type.toUpperCase()}
                        </span>
                        <span className="amendments-tab__meta-text">
                          {amendment.position_text}
                        </span>
                        <div className="amendments-tab__card-date">
                          {new Date(amendment.updated_at).toLocaleDateString()}
                        </div>
                      </div>
                      <div className="amendments-tab__card-content-section">
                        {amendment.original_text && amendment.amendment_type !== 'addition' && (
                          <div className="amendments-tab__text-block">
                            <strong>{t('amendmentsTab.original')}</strong>
                            <p>{amendment.original_text.slice(0, 100)}{amendment.original_text.length > 100 ? '...' : ''}</p>
                          </div>
                        )}
                        {amendment.proposed_text && amendment.amendment_type !== 'suppression' && (
                          <div className="amendments-tab__text-block">
                            <strong>{t('amendmentsTab.proposed')}</strong>
                            <p><em><strong>{amendment.proposed_text.slice(0, 100)}{amendment.proposed_text.length > 100 ? '...' : ''}</strong></em></p>
                          </div>
                        )}
                      </div>
                      <div className="amendments-tab__card-actions">
                        <select
                          value={amendment.status}
                          onChange={(e) => handleStatusChange(amendment.id, e.target.value)}
                          className="amendments-tab__status-select"
                        >
                          <option value="draft">{t('amendmentsTab.statusDraft')}</option>
                          <option value="candidate">{t('amendmentsTab.statusCandidate')}</option>
                          <option value="tabled">{t('amendmentsTab.statusTabled')}</option>
                          <option value="adopted">{t('amendmentsTab.statusAdopted')}</option>
                          <option value="rejected">{t('amendmentsTab.statusRejected')}</option>
                          <option value="withdrawn">{t('amendmentsTab.statusWithdrawn')}</option>
                        </select>
                        <AmendmentOpen
                          amendment={amendment}
                          trackedFile={group.trackedFile}
                          navigate={navigate}
                          t={t}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          /* List View */
          <div className="amendments-tab__list">
            {filteredAmendments.map(amendment => {
              return (
                <div
                  key={amendment.id}
                  className="amendments-tab__card"
                  data-status={amendment.status}
                >
                  {/* Header */}
                  <div className="amendments-tab__card-header">
                    <div className="amendments-tab__card-status" data-status={amendment.status}>
                      {amendment.status}
                    </div>
                    <div className="amendments-tab__card-date">
                      {new Date(amendment.updated_at).toLocaleDateString()}
                    </div>
                  </div>

                  {/* Position & Type */}
                  <div className="amendments-tab__card-meta">
                    <span className="amendments-tab__meta-badge amendments-tab__meta-badge--type">
                      {amendment.amendment_type.toUpperCase()}
                    </span>
                    <span className="amendments-tab__meta-text">
                      {amendment.position_text}
                    </span>
                  </div>

                  {/* Document Reference */}
                  <div className="amendments-tab__card-refs">
                    <span className="amendments-tab__ref">
                      Document: {amendment.document_filename || amendment.document_id}
                    </span>
                  </div>

                  {/* Amendment Content */}
                  <div className="amendments-tab__card-content-section">
                    {amendment.original_text && amendment.amendment_type !== 'addition' && (
                      <div className="amendments-tab__text-block">
                        <strong>{t('amendmentsTab.original')}</strong>
                        <p>{amendment.original_text.slice(0, 150)}{amendment.original_text.length > 150 ? '...' : ''}</p>
                      </div>
                    )}
                    {amendment.proposed_text && amendment.amendment_type !== 'suppression' && (
                      <div className="amendments-tab__text-block">
                        <strong>{t('amendmentsTab.proposed')}</strong>
                        <p><em><strong>{amendment.proposed_text.slice(0, 150)}{amendment.proposed_text.length > 150 ? '...' : ''}</strong></em></p>
                      </div>
                    )}
                  </div>

                  {/* Justification */}
                  {amendment.justification && (
                    <div className="amendments-tab__justification">
                      <strong>{t('amendmentsTab.justification')}</strong>
                      <p>{amendment.justification.slice(0, 100)}{amendment.justification.length > 100 ? '...' : ''}</p>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="amendments-tab__card-actions">
                    <select
                      value={amendment.status}
                      onChange={(e) => handleStatusChange(amendment.id, e.target.value)}
                      className="amendments-tab__status-select"
                    >
                      <option value="draft">{t('amendmentsTab.statusDraft')}</option>
                      <option value="candidate">{t('amendmentsTab.statusCandidate')}</option>
                      <option value="tabled">{t('amendmentsTab.statusTabled')}</option>
                      <option value="adopted">{t('amendmentsTab.statusAdopted')}</option>
                      <option value="rejected">{t('amendmentsTab.statusRejected')}</option>
                      <option value="withdrawn">{t('amendmentsTab.statusWithdrawn')}</option>
                    </select>
                    <AmendmentOpen
                      amendment={amendment}
                      trackedFile={null}
                      navigate={navigate}
                      t={t}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      </>
      )}

      {/* The group title calls fetchFileDetail, which sets `selectedFile` in the
          legislative-trains store. Without this mount nothing rendered, so that
          click did nothing at all. */}
      <LegislativeFileDetail />
    </div>
  );
};
