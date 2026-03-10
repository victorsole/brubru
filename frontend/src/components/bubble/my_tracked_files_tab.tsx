/**
 * My Tracked Files Tab Component
 *
 * Personal watchlist of tracked legislative files.
 * Shows tracked files with status, recent changes, and quick actions.
 * Part of My EU Bubble - Legislative Tracking Enhancement
 */

import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import Icon from '@mdi/react';
import {
  mdiFileDocumentOutline,
  mdiAlertCircleOutline,
  mdiClockOutline,
  mdiAccountGroupOutline,
  mdiPlus,
  mdiRefresh,
  mdiTrashCanOutline,
  mdiOpenInNew,
  mdiHistory,
  mdiMagnify,
  mdiClose,
  mdiStarOutline,
  mdiLoading,
  mdiPencilOutline,
  mdiAccountTieOutline,
  mdiFilterVariant,
  mdiTextBoxCheckOutline,
  mdiFileDocumentMultipleOutline,
} from '@mdi/js';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useLegislativeTrains } from '../../hooks/use_legislative_trains';
import type { TrackedFile } from '../../hooks/use_legislative_trains';
import { useCommitteeWork, PROCEDURE_TYPE_INFO, STATUS_INFO } from '../../hooks/use_committee_work';
import type { CommitteeWorkItem } from '../../hooks/use_committee_work';
import { useTextsAdopted } from '../../hooks/use_texts_adopted';
import type { TextAdopted as TextAdoptedType } from '../../hooks/use_texts_adopted';
import { TextAdoptedCard } from './text_adopted_card';
import { useCommissionDocuments } from '../../hooks/use_commission_documents';
import type { CommissionDocType } from '../../hooks/use_commission_documents';
import { getEultUrl } from '../../utils/eu_links';
import { CommissionDocumentCard } from './commission_document_card';
import { LegislativeFileDetail } from './legislative_file_detail';
import './my_tracked_files_tab.css';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface SearchableFile {
  id: string;
  title: string;
  current_status: string;
  oeil_procedure_ref?: string;
}

export const MyTrackedFilesTab = () => {
  const navigate = useNavigate();
  const {
    trackedFiles,
    recentChanges,
    isLoadingTrackedFiles,
    fetchTrackedFiles,
    fetchRecentChanges,
    untrackFile,
    fetchFileDetail,
    trackFile,
    isTracking,
  } = useLegislativeTrains();

  // Committee Work hook
  const {
    items: committeeWorkItems,
    committees,
    isLoadingItems: isLoadingCommitteeWork,
    fetchItems: fetchCommitteeWorkItems,
    fetchCommittees,
    filters: committeeFilters,
    setFilters: setCommitteeFilters,
  } = useCommitteeWork();

  // Texts Adopted hook
  const {
    items: textsAdoptedItems,
    isLoadingItems: isLoadingTextsAdopted,
    fetchItems: fetchTextsAdoptedItems,
    filters: textsAdoptedFilters,
    setFilters: setTextsAdoptedFilters,
  } = useTextsAdopted();

  // Commission Documents hook
  const {
    items: commissionDocItems,
    isLoadingItems: isLoadingCommissionDocs,
    fetchItems: fetchCommissionDocItems,
    filters: commissionDocFilters,
    setFilters: setCommissionDocFilters,
  } = useCommissionDocuments();

  const hasLoadedRef = useRef(false);
  const [activeTab, setActiveTab] = useState<'legislative' | 'committee' | 'texts_adopted' | 'commission_docs'>('legislative');
  const [amendmentCounts, setAmendmentCounts] = useState<Record<string, number>>({});
  const [showAddModal, setShowAddModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [availableFiles, setAvailableFiles] = useState<SearchableFile[]>([]);
  const [isLoadingFiles, setIsLoadingFiles] = useState(false);
  const [trackingFileId, setTrackingFileId] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [sortOrder, setSortOrder] = useState<'newest' | 'oldest' | 'alphabetical'>('newest');
  const ITEMS_PER_PAGE = 50;

  // OEIL direct tracking state
  const [oeilProcedureRef, setOeilProcedureRef] = useState('');
  const [isTrackingOeil, setIsTrackingOeil] = useState(false);
  const [oeilTrackError, setOeilTrackError] = useState<string | null>(null);
  const [oeilTrackSuccess, setOeilTrackSuccess] = useState<string | null>(null);

  // Fetch amendment counts for tracked files
  const fetchAmendmentCounts = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/legislative-train/tracked/amendment-counts`);
      setAmendmentCounts(response.data.amendment_counts || {});
    } catch (error) {
      console.error('Failed to fetch amendment counts:', error);
    }
  };

  useEffect(() => {
    if (hasLoadedRef.current) return;
    hasLoadedRef.current = true;

    const loadData = async () => {
      await fetchTrackedFiles();
      await fetchRecentChanges(168); // Last 7 days
      await fetchAmendmentCounts();
      // Load committee work data
      await fetchCommittees();
      await fetchCommitteeWorkItems();
      // Load texts adopted data
      await fetchTextsAdoptedItems();
      // Load commission documents data
      await fetchCommissionDocItems();
    };

    loadData();
  }, []);

  const handleRefresh = async () => {
    if (activeTab === 'legislative') {
      await fetchTrackedFiles();
      await fetchRecentChanges(168);
    } else if (activeTab === 'committee') {
      await fetchCommitteeWorkItems();
    } else if (activeTab === 'texts_adopted') {
      await fetchTextsAdoptedItems();
    } else {
      await fetchCommissionDocItems();
    }
  };

  const handleUntrack = async (file: TrackedFile) => {
    if (window.confirm('Are you sure you want to stop tracking this file?')) {
      try {
        // Use procedure ref if available, otherwise use carriage_id (UUID)
        const useCarriageId = !file.oeil_procedure_ref;
        const identifier = file.oeil_procedure_ref || file.carriage_id;
        await untrackFile(identifier, useCarriageId);
      } catch {
        alert('Failed to untrack file. Please try again.');
      }
    }
  };

  // Load available files when modal opens
  const loadAvailableFiles = async () => {
    setIsLoadingFiles(true);
    try {
      const response = await axios.get<{ carriages: SearchableFile[]; total: number }>(
        `${API_BASE}/api/legislative-train/carriages?limit=500`
      );
      setAvailableFiles(response.data.carriages || []);
    } catch (error) {
      console.error('Failed to load files:', error);
    } finally {
      setIsLoadingFiles(false);
    }
  };

  // Open modal and load files
  const handleOpenAddModal = () => {
    setShowAddModal(true);
    setSearchQuery('');
    if (availableFiles.length === 0) {
      loadAvailableFiles();
    }
  };

  // Track a file from the modal - always use UUID for reliability
  const handleTrackFromModal = async (file: SearchableFile) => {
    setTrackingFileId(file.id);
    try {
      // Always use UUID (carriage ID) for tracking - more reliable than procedure ref
      await trackFile(file.id, true);
    } catch (error: unknown) {
      // Show specific error message
      const axiosError = error as { response?: { status?: number; data?: { detail?: string } } };
      if (axiosError.response?.status === 401) {
        alert('Please log in to track files.');
      } else {
        alert(axiosError.response?.data?.detail || 'Failed to track file. Please try again.');
      }
    } finally {
      setTrackingFileId(null);
    }
  };

  // Track an OEIL procedure directly (not from Legislative Train)
  const handleTrackOeilProcedure = async () => {
    if (!oeilProcedureRef.trim()) {
      setOeilTrackError('Please enter a procedure reference');
      return;
    }

    // Validate format: YYYY/NNNN(XXX)
    const procedurePattern = /^\d{4}\/\d{4}\([A-Z]{3}\)$/;
    if (!procedurePattern.test(oeilProcedureRef.trim())) {
      setOeilTrackError('Invalid format. Use: YYYY/NNNN(XXX) e.g., 2024/0176(COD)');
      return;
    }

    setIsTrackingOeil(true);
    setOeilTrackError(null);
    setOeilTrackSuccess(null);

    try {
      const response = await axios.post(
        `${API_BASE}/api/legislative-train/track/oeil?procedure_ref=${encodeURIComponent(oeilProcedureRef.trim())}`
      );

      setOeilTrackSuccess(`Now tracking: ${response.data.title || oeilProcedureRef}`);
      setOeilProcedureRef('');

      // Refresh tracked files
      await fetchTrackedFiles();
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string }; status?: number } };
      if (axiosError.response?.status === 404) {
        setOeilTrackError('Procedure not found in OEIL. Check the reference.');
      } else if (axiosError.response?.status === 401) {
        setOeilTrackError('Please log in to track procedures.');
      } else {
        setOeilTrackError(axiosError.response?.data?.detail || 'Failed to track procedure');
      }
    } finally {
      setIsTrackingOeil(false);
    }
  };

  // Compute available statuses from data
  const availableStatuses = Array.from(
    new Set(availableFiles.map(f => f.current_status))
  ).sort();

  // Parse procedure reference to extract year and number for sorting
  // Format: YYYY/NNNN(TYPE) e.g., 2018/0332(COD)
  const parseProcedureRef = (ref: string | undefined): { year: number; number: number } => {
    if (!ref) return { year: 0, number: 0 };
    const match = ref.match(/^(\d{4})\/(\d{4})\(/);
    if (match) {
      return {
        year: parseInt(match[1], 10),
        number: parseInt(match[2], 10)
      };
    }
    return { year: 0, number: 0 };
  };

  // Filter files based on search query and status
  const filteredFiles = availableFiles.filter((file) => {
    // Status filter
    if (statusFilter !== 'all' && file.current_status !== statusFilter) {
      return false;
    }
    // Search query filter
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      file.title.toLowerCase().includes(query) ||
      (file.oeil_procedure_ref?.toLowerCase().includes(query))
    );
  });

  // Sort filtered files based on sortOrder
  const sortedFiles = [...filteredFiles].sort((a, b) => {
    if (sortOrder === 'alphabetical') {
      return a.title.localeCompare(b.title);
    }

    const refA = parseProcedureRef(a.oeil_procedure_ref);
    const refB = parseProcedureRef(b.oeil_procedure_ref);

    // Primary sort by year, secondary by number
    if (refA.year !== refB.year) {
      return sortOrder === 'newest' ? refB.year - refA.year : refA.year - refB.year;
    }
    // Same year, sort by proposal number
    return sortOrder === 'newest' ? refB.number - refA.number : refA.number - refB.number;
  });

  // Pagination calculations (use sortedFiles)
  const totalPages = Math.ceil(sortedFiles.length / ITEMS_PER_PAGE);
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
  const endIndex = startIndex + ITEMS_PER_PAGE;
  const paginatedFiles = sortedFiles.slice(startIndex, endIndex);

  // Reset to page 1 when search query, status filter, or sort order changes
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, statusFilter, sortOrder]);

  // Check if a file is already tracked
  const isAlreadyTracked = (file: SearchableFile) => {
    return trackedFiles.some(
      (tf) => tf.file_id === file.id || tf.oeil_procedure_ref === file.oeil_procedure_ref
    );
  };

  const getStatusColor = (status: string) => {
    const statusMap: Record<string, string> = {
      announced: '#9e9e9e',
      legislative_initiative: '#2196f3',
      tabled: '#ff9800',
      close_to_adoption: '#4caf50',
      completed: '#4caf50',
      adopted: '#4caf50',
      blocked: '#f44336',
      withdrawn: '#757575',
    };
    return statusMap[status] || '#9e9e9e';
  };

  const getChangeIcon = (changeType: string) => {
    switch (changeType) {
      case 'status_change':
        return mdiHistory;
      case 'new_document':
        return mdiFileDocumentOutline;
      case 'blocking':
        return mdiAlertCircleOutline;
      default:
        return mdiClockOutline;
    }
  };

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) {
      return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    }
    if (diffHours > 0) {
      return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    }
    return 'Just now';
  };

  return (
    <div className="my-tracked-files-tab">
      {/* Header */}
      <div className="my-tracked-files-tab__header">
        <div className="my-tracked-files-tab__header-left">
          <h2>My Files</h2>
          <p className="my-tracked-files-tab__subtitle">
            {activeTab === 'legislative'
              ? `${trackedFiles.length} file${trackedFiles.length !== 1 ? 's' : ''} tracked`
              : activeTab === 'committee'
              ? `${committeeWorkItems.length} committee work items`
              : activeTab === 'texts_adopted'
              ? `${textsAdoptedItems.length} adopted texts`
              : `${commissionDocItems.length} Commission documents`
            }
          </p>
        </div>
        <div className="my-tracked-files-tab__header-actions">
          <button
            className="my-tracked-files-tab__btn my-tracked-files-tab__btn--secondary"
            onClick={handleRefresh}
            disabled={isLoadingTrackedFiles || isLoadingCommitteeWork || isLoadingTextsAdopted || isLoadingCommissionDocs}
          >
            <Icon path={mdiRefresh} size={0.8} />
            Refresh
          </button>
          {activeTab === 'legislative' && (
            <button
              className="my-tracked-files-tab__btn my-tracked-files-tab__btn--primary"
              onClick={handleOpenAddModal}
            >
              <Icon path={mdiPlus} size={0.8} />
              Track File
            </button>
          )}
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="my-tracked-files-tab__tabs">
        <button
          className={`my-tracked-files-tab__tab ${activeTab === 'legislative' ? 'my-tracked-files-tab__tab--active' : ''}`}
          onClick={() => setActiveTab('legislative')}
        >
          <Icon path={mdiFileDocumentOutline} size={0.8} />
          Legislative Train
        </button>
        <button
          className={`my-tracked-files-tab__tab ${activeTab === 'committee' ? 'my-tracked-files-tab__tab--active' : ''}`}
          onClick={() => setActiveTab('committee')}
        >
          <Icon path={mdiAccountGroupOutline} size={0.8} />
          Committee Work
        </button>
        <button
          className={`my-tracked-files-tab__tab ${activeTab === 'texts_adopted' ? 'my-tracked-files-tab__tab--active' : ''}`}
          onClick={() => setActiveTab('texts_adopted')}
        >
          <Icon path={mdiTextBoxCheckOutline} size={0.8} />
          Texts Adopted
        </button>
        <button
          className={`my-tracked-files-tab__tab ${activeTab === 'commission_docs' ? 'my-tracked-files-tab__tab--active' : ''}`}
          onClick={() => setActiveTab('commission_docs')}
        >
          <Icon path={mdiFileDocumentMultipleOutline} size={0.8} />
          Commission Docs
        </button>
      </div>

      {/* Legislative Files Tab Content */}
      {activeTab === 'legislative' && (
        <>
          {/* Recent Changes Section */}
          {recentChanges.length > 0 && (
            <div className="my-tracked-files-tab__changes">
              <h3 className="my-tracked-files-tab__section-title">
                <Icon path={mdiHistory} size={0.9} />
                Recent Changes (Last 7 days)
              </h3>
              <div className="my-tracked-files-tab__changes-list">
                {recentChanges.slice(0, 5).map((change, idx) => (
                  <div key={idx} className="my-tracked-files-tab__change-item">
                    <div
                      className="my-tracked-files-tab__change-icon"
                      data-type={change.change_type}
                    >
                      <Icon path={getChangeIcon(change.change_type)} size={0.8} />
                    </div>
                    <div className="my-tracked-files-tab__change-content">
                      <div className="my-tracked-files-tab__change-title">
                        {change.title}
                      </div>
                      <div className="my-tracked-files-tab__change-description">
                        {change.change_type === 'status_change' && (
                          <>
                            Status changed: {change.old_value?.replace(/_/g, ' ')} →{' '}
                            <strong>{change.new_value?.replace(/_/g, ' ')}</strong>
                          </>
                        )}
                        {change.change_type === 'new_document' && change.description}
                        {change.change_type === 'blocking' && 'File blocked - no progress for 9+ months'}
                      </div>
                    </div>
                    <div className="my-tracked-files-tab__change-time">
                      {formatTimeAgo(change.changed_at)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tracked Files List */}
          <div className="my-tracked-files-tab__files">
            <h3 className="my-tracked-files-tab__section-title">
              <Icon path={mdiFileDocumentOutline} size={0.9} />
              Tracked Legislative Files
            </h3>

            {isLoadingTrackedFiles ? (
          <div className="my-tracked-files-tab__loading">
            Loading tracked files...
          </div>
        ) : trackedFiles.length === 0 ? (
          <div className="my-tracked-files-tab__empty">
            <Icon path={mdiFileDocumentOutline} size={2} color="#ccc" />
            <h4>No tracked files yet</h4>
            <p>Start tracking legislative files to monitor their progress</p>
            <button
              className="my-tracked-files-tab__btn my-tracked-files-tab__btn--primary"
              onClick={handleOpenAddModal}
            >
              <Icon path={mdiPlus} size={0.8} />
              Track Your First File
            </button>
          </div>
        ) : (
          <div className="my-tracked-files-tab__files-list">
            {trackedFiles.map((file) => (
              <TrackedFileCard
                key={file.id}
                file={file}
                onViewDetail={() => fetchFileDetail(file.file_id)}
                onUntrack={() => handleUntrack(file)}
                onDraftAmendment={() => {
                  // Navigate to Amendator - the TrackedFilesLoader will be available there
                  navigate('/amendator');
                }}
                getStatusColor={getStatusColor}
                amendmentCount={amendmentCounts[file.carriage_id]}
              />
            ))}
          </div>
        )}
          </div>
        </>
      )}

      {/* Committee Work Tab Content */}
      {activeTab === 'committee' && (
        <div className="my-tracked-files-tab__committee-work">
          {/* Committee Filter */}
          <div className="my-tracked-files-tab__committee-filter">
            <Icon path={mdiFilterVariant} size={0.8} />
            <select
              value={committeeFilters.committee_code || ''}
              onChange={(e) => setCommitteeFilters({ ...committeeFilters, committee_code: e.target.value || undefined })}
            >
              <option value="">All Committees ({committeeWorkItems.length})</option>
              {committees.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.code} - {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Committee Work Items List */}
          {isLoadingCommitteeWork ? (
            <div className="my-tracked-files-tab__loading">
              <Icon path={mdiLoading} size={1} spin />
              Loading committee work items...
            </div>
          ) : committeeWorkItems.length === 0 ? (
            <div className="my-tracked-files-tab__empty">
              <Icon path={mdiAccountGroupOutline} size={2} color="#ccc" />
              <h4>No committee work items</h4>
              <p>
                {committeeFilters.committee_code
                  ? `No items found for ${committeeFilters.committee_code}`
                  : 'Select a committee to view work in progress'
                }
              </p>
            </div>
          ) : (
            <div className="my-tracked-files-tab__committee-list">
              {committeeWorkItems.map((item) => (
                <CommitteeWorkCard key={item.id} item={item} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Texts Adopted Tab Content */}
      {activeTab === 'texts_adopted' && (
        <div className="my-tracked-files-tab__texts-adopted">
          {/* Filters */}
          <div className="my-tracked-files-tab__texts-adopted-filters">
            <div className="my-tracked-files-tab__texts-adopted-filter">
              <Icon path={mdiFilterVariant} size={0.8} />
              <select
                value={textsAdoptedFilters.parliamentary_term || ''}
                onChange={(e) => setTextsAdoptedFilters({
                  ...textsAdoptedFilters,
                  parliamentary_term: e.target.value ? parseInt(e.target.value) : undefined
                })}
              >
                <option value="">All Terms</option>
                <option value="10">Term 10 (2024-2029)</option>
                <option value="9">Term 9 (2019-2024)</option>
                <option value="8">Term 8 (2014-2019)</option>
                <option value="7">Term 7 (2009-2014)</option>
                <option value="6">Term 6 (2004-2009)</option>
                <option value="5">Term 5 (1999-2004)</option>
                <option value="4">Term 4 (1994-1999)</option>
              </select>
            </div>
            <div className="my-tracked-files-tab__texts-adopted-filter">
              <select
                value={textsAdoptedFilters.text_type || ''}
                onChange={(e) => setTextsAdoptedFilters({
                  ...textsAdoptedFilters,
                  text_type: e.target.value ? e.target.value as TextAdoptedType['text_type'] : undefined
                })}
              >
                <option value="">All Types</option>
                <option value="resolution">Resolution</option>
                <option value="legislative_resolution">Legislative Resolution</option>
                <option value="decision">Decision</option>
                <option value="recommendation">Recommendation</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div className="my-tracked-files-tab__texts-adopted-search">
              <Icon path={mdiMagnify} size={0.8} />
              <input
                type="text"
                placeholder="Search texts..."
                value={textsAdoptedFilters.search || ''}
                onChange={(e) => setTextsAdoptedFilters({
                  ...textsAdoptedFilters,
                  search: e.target.value || undefined
                })}
              />
            </div>
          </div>

          {/* Items List */}
          {isLoadingTextsAdopted ? (
            <div className="my-tracked-files-tab__loading">
              <Icon path={mdiLoading} size={1} spin />
              Loading adopted texts...
            </div>
          ) : textsAdoptedItems.length === 0 ? (
            <div className="my-tracked-files-tab__empty">
              <Icon path={mdiTextBoxCheckOutline} size={2} color="#ccc" />
              <h4>No adopted texts found</h4>
              <p>
                {textsAdoptedFilters.search || textsAdoptedFilters.text_type || textsAdoptedFilters.parliamentary_term
                  ? 'Try adjusting your filters'
                  : 'Sync texts adopted data to populate this tab'
                }
              </p>
            </div>
          ) : (
            <div className="my-tracked-files-tab__texts-adopted-list">
              {textsAdoptedItems.map((item) => (
                <TextAdoptedCard key={item.id} item={item} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Commission Documents Tab Content */}
      {activeTab === 'commission_docs' && (
        <div className="my-tracked-files-tab__commission-docs">
          {/* Filters */}
          <div className="my-tracked-files-tab__commission-docs-filters">
            <div className="my-tracked-files-tab__commission-docs-filter">
              <Icon path={mdiFilterVariant} size={0.8} />
              <select
                value={commissionDocFilters.doc_type || ''}
                onChange={(e) => setCommissionDocFilters({
                  ...commissionDocFilters,
                  doc_type: e.target.value ? e.target.value as CommissionDocType : undefined
                })}
              >
                <option value="">All Types</option>
                <option value="COM">COM (Proposals)</option>
                <option value="SWD">SWD (Staff Working)</option>
                {/* <option value="SEC">SEC (Secretariat)</option> */}
                {/* <option value="C">C (Delegated Acts)</option> */}
                <option value="JOIN">JOIN (Joint Docs)</option>
                <option value="OJ">OJ (Official Journal)</option>
                {/* <option value="PV">PV (Minutes)</option> — will be used in EU Calendar */}
              </select>
            </div>
            <div className="my-tracked-files-tab__commission-docs-search">
              <Icon path={mdiMagnify} size={0.8} />
              <input
                type="text"
                placeholder="Search documents..."
                value={commissionDocFilters.search || ''}
                onChange={(e) => setCommissionDocFilters({
                  ...commissionDocFilters,
                  search: e.target.value || undefined
                })}
              />
            </div>
          </div>

          {/* Items List */}
          {isLoadingCommissionDocs ? (
            <div className="my-tracked-files-tab__loading">
              <Icon path={mdiLoading} size={1} spin />
              Loading Commission documents...
            </div>
          ) : commissionDocItems.length === 0 ? (
            <div className="my-tracked-files-tab__empty">
              <Icon path={mdiFileDocumentMultipleOutline} size={2} color="#ccc" />
              <h4>No Commission documents found</h4>
              <p>
                {commissionDocFilters.search || commissionDocFilters.doc_type
                  ? 'Try adjusting your filters'
                  : 'Sync Commission documents to populate this tab'
                }
              </p>
            </div>
          ) : (
            <div className="my-tracked-files-tab__commission-docs-list">
              {commissionDocItems.map((item) => (
                <CommissionDocumentCard key={item.id} item={item} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Add File Modal - Search and Track (uses portal to escape stacking context) */}
      {showAddModal && createPortal(
        <div className="my-tracked-files-tab__modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="my-tracked-files-tab__modal my-tracked-files-tab__modal--search" onClick={(e) => e.stopPropagation()}>
            <div className="my-tracked-files-tab__modal-header">
              <h3>Track a Legislative File</h3>
              <button
                className="my-tracked-files-tab__modal-close"
                onClick={() => setShowAddModal(false)}
              >
                <Icon path={mdiClose} size={0.9} />
              </button>
            </div>

            {/* Track OEIL Procedure Directly */}
            <div className="my-tracked-files-tab__oeil-track">
              <h4>Track Any EU Procedure</h4>
              <p className="my-tracked-files-tab__oeil-track-hint">
                Enter an OEIL procedure reference to track legislation not in the Legislative Train.
                Find references on <a href="https://oeil.europarl.europa.eu" target="_blank" rel="noopener noreferrer">OEIL</a>.
              </p>
              <div className="my-tracked-files-tab__oeil-track-input">
                <input
                  type="text"
                  placeholder="e.g., 2024/0176(COD)"
                  value={oeilProcedureRef}
                  onChange={(e) => {
                    setOeilProcedureRef(e.target.value.toUpperCase());
                    setOeilTrackError(null);
                    setOeilTrackSuccess(null);
                  }}
                  onKeyDown={(e) => e.key === 'Enter' && handleTrackOeilProcedure()}
                />
                <button
                  className="my-tracked-files-tab__oeil-track-btn"
                  onClick={handleTrackOeilProcedure}
                  disabled={isTrackingOeil || !oeilProcedureRef.trim()}
                >
                  {isTrackingOeil ? (
                    <Icon path={mdiLoading} size={0.8} spin />
                  ) : (
                    <Icon path={mdiPlus} size={0.8} />
                  )}
                  Track
                </button>
              </div>
              {oeilTrackError && (
                <div className="my-tracked-files-tab__oeil-track-error">
                  <Icon path={mdiAlertCircleOutline} size={0.7} />
                  {oeilTrackError}
                </div>
              )}
              {oeilTrackSuccess && (
                <div className="my-tracked-files-tab__oeil-track-success">
                  <Icon path={mdiStarOutline} size={0.7} />
                  {oeilTrackSuccess}
                </div>
              )}
            </div>

            <div className="my-tracked-files-tab__modal-divider">
              <span>or browse Commission priorities</span>
            </div>

            {/* Search and Filter */}
            <div className="my-tracked-files-tab__search-filters">
              <div className="my-tracked-files-tab__search-input">
                <Icon path={mdiMagnify} size={0.9} />
                <input
                  type="text"
                  placeholder="Search by title or procedure reference..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  autoFocus
                />
                {searchQuery && (
                  <button onClick={() => setSearchQuery('')}>
                    <Icon path={mdiClose} size={0.7} />
                  </button>
                )}
              </div>
              <div className="my-tracked-files-tab__filter-row">
                <div className="my-tracked-files-tab__status-filter">
                  <label>Status:</label>
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                  >
                    <option value="all">All ({availableFiles.length})</option>
                    {availableStatuses.map(status => {
                      const count = availableFiles.filter(f => f.current_status === status).length;
                      return (
                        <option key={status} value={status}>
                          {status.replace(/_/g, ' ')} ({count})
                        </option>
                      );
                    })}
                  </select>
                </div>
                <div className="my-tracked-files-tab__sort-filter">
                  <label>Sort:</label>
                  <select
                    value={sortOrder}
                    onChange={(e) => setSortOrder(e.target.value as 'newest' | 'oldest' | 'alphabetical')}
                  >
                    <option value="newest">Newest first</option>
                    <option value="oldest">Oldest first</option>
                    <option value="alphabetical">A-Z</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Files List */}
            <div className="my-tracked-files-tab__search-results">
              {isLoadingFiles ? (
                <div className="my-tracked-files-tab__search-loading">
                  <Icon path={mdiLoading} size={1} spin />
                  Loading legislative files...
                </div>
              ) : sortedFiles.length === 0 ? (
                <div className="my-tracked-files-tab__search-empty">
                  {searchQuery ? 'No files match your search' : 'No files available'}
                </div>
              ) : (
                <div className="my-tracked-files-tab__search-list">
                  {paginatedFiles.map((file) => {
                    const alreadyTracked = isAlreadyTracked(file);
                    const isCurrentlyTracking = trackingFileId === file.id;

                    return (
                      <div
                        key={file.id}
                        className={`my-tracked-files-tab__search-item ${alreadyTracked ? 'my-tracked-files-tab__search-item--tracked' : ''}`}
                      >
                        <div className="my-tracked-files-tab__search-item-content">
                          <div className="my-tracked-files-tab__search-item-title">
                            {file.title}
                          </div>
                          <div className="my-tracked-files-tab__search-item-meta">
                            <span
                              className="my-tracked-files-tab__search-item-status"
                              style={{ backgroundColor: getStatusColor(file.current_status) }}
                            >
                              {file.current_status.replace(/_/g, ' ')}
                            </span>
                            {file.oeil_procedure_ref && (
                              <span className="my-tracked-files-tab__search-item-ref">
                                {file.oeil_procedure_ref}
                              </span>
                            )}
                          </div>
                        </div>
                        <button
                          className="my-tracked-files-tab__search-item-track"
                          onClick={() => handleTrackFromModal(file)}
                          disabled={alreadyTracked || isCurrentlyTracking || isTracking}
                          title={alreadyTracked ? 'Already tracked' : 'Track this file'}
                        >
                          {isCurrentlyTracking ? (
                            <Icon path={mdiLoading} size={0.8} spin />
                          ) : (
                            <Icon path={mdiStarOutline} size={0.8} />
                          )}
                          {alreadyTracked ? 'Tracked' : 'Track'}
                        </button>
                      </div>
                    );
                  })}
                  {/* Pagination controls */}
                  {sortedFiles.length > ITEMS_PER_PAGE && (
                    <div className="my-tracked-files-tab__pagination">
                      <span className="my-tracked-files-tab__pagination-info">
                        Showing {startIndex + 1}-{Math.min(endIndex, sortedFiles.length)} of {sortedFiles.length}
                      </span>
                      <div className="my-tracked-files-tab__pagination-controls">
                        <button
                          className="my-tracked-files-tab__pagination-btn"
                          onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                          disabled={currentPage === 1}
                        >
                          Previous
                        </button>
                        <span className="my-tracked-files-tab__pagination-pages">
                          Page {currentPage} of {totalPages}
                        </span>
                        <button
                          className="my-tracked-files-tab__pagination-btn"
                          onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                          disabled={currentPage === totalPages}
                        >
                          Next
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* File Detail Modal */}
      <LegislativeFileDetail />
    </div>
  );
};

// Tracked File Card Component
interface TrackedFileCardProps {
  file: TrackedFile;
  onViewDetail: () => void;
  onUntrack: () => void;
  onDraftAmendment: () => void;
  getStatusColor: (status: string) => string;
  amendmentCount?: number;
}

const TrackedFileCard = ({ file, onViewDetail, onUntrack, onDraftAmendment, getStatusColor, amendmentCount }: TrackedFileCardProps) => {
  const oeilUrl = file.oeil_procedure_ref
    ? `https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${encodeURIComponent(file.oeil_procedure_ref)}`
    : null;
  const eultUrl = file.oeil_procedure_ref ? getEultUrl(file.oeil_procedure_ref) : null;

  return (
    <div className="tracked-file-card">
      <div className="tracked-file-card__header">
        <div
          className="tracked-file-card__status"
          style={{ backgroundColor: getStatusColor(file.current_status) }}
        >
          {file.current_status.replace(/_/g, ' ')}
        </div>
        {file.is_blocked && (
          <div className="tracked-file-card__blocked">
            <Icon path={mdiAlertCircleOutline} size={0.7} />
            Blocked
          </div>
        )}
        {amendmentCount !== undefined && amendmentCount > 0 && (
          <div className="tracked-file-card__amendment-badge">
            <Icon path={mdiPencilOutline} size={0.6} />
            {amendmentCount} amendment{amendmentCount !== 1 ? 's' : ''}
          </div>
        )}
      </div>

      <h4 className="tracked-file-card__title" onClick={onViewDetail}>
        {file.title}
      </h4>

      <div className="tracked-file-card__meta">
        {file.oeil_procedure_ref && (
          <span className="tracked-file-card__ref">
            {file.oeil_procedure_ref}
          </span>
        )}
        {file.lead_committee && (
          <span className="tracked-file-card__committee">
            <Icon path={mdiAccountGroupOutline} size={0.6} />
            {file.lead_committee}
          </span>
        )}
        {file.days_in_current_status && (
          <span className="tracked-file-card__days">
            <Icon path={mdiClockOutline} size={0.6} />
            {file.days_in_current_status} days
          </span>
        )}
      </div>

      <div className="tracked-file-card__actions">
        <button
          className="tracked-file-card__action-btn tracked-file-card__action-btn--primary"
          onClick={onViewDetail}
        >
          <Icon path={mdiFileDocumentOutline} size={0.7} />
          View Details
        </button>
        <button
          className="tracked-file-card__action-btn tracked-file-card__action-btn--amendator"
          onClick={onDraftAmendment}
          title="Open in Amendator"
        >
          <Icon path={mdiPencilOutline} size={0.7} />
          Draft Amendment
        </button>
        {oeilUrl && (
          <a
            href={oeilUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="tracked-file-card__action-btn"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            OEIL
          </a>
        )}
        {eultUrl && (
          <a
            href={eultUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="tracked-file-card__action-btn"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            EU Law Tracker
          </a>
        )}
        <button
          className="tracked-file-card__action-btn tracked-file-card__action-btn--danger"
          onClick={onUntrack}
        >
          <Icon path={mdiTrashCanOutline} size={0.7} />
          Untrack
        </button>
      </div>

      <div className="tracked-file-card__footer">
        <span className="tracked-file-card__tracked-since">
          Tracking since {new Date(file.tracked_since).toLocaleDateString()}
        </span>
      </div>
    </div>
  );
};

// Committee Work Card Component
interface CommitteeWorkCardProps {
  item: CommitteeWorkItem;
}

const CommitteeWorkCard = ({ item }: CommitteeWorkCardProps) => {
  const procedureInfo = PROCEDURE_TYPE_INFO[item.procedure_type] || { name: item.procedure_type, color: '#6b7280', score: 0 };
  const statusInfo = STATUS_INFO[item.status] || { name: item.status, color: '#9ca3af' };

  const oeilUrl = item.oeil_url || (item.procedure_ref
    ? `https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${encodeURIComponent(item.procedure_ref)}`
    : null
  );
  const eultUrl = item.procedure_ref ? getEultUrl(item.procedure_ref) : null;

  return (
    <div className="committee-work-card">
      <div className="committee-work-card__header">
        <span
          className="committee-work-card__committee"
          title={`${item.committee_code} - ${item.committee_role}`}
        >
          {item.committee_code}
        </span>
        <span
          className="committee-work-card__procedure-type"
          style={{ backgroundColor: procedureInfo.color }}
          title={procedureInfo.name}
        >
          {item.procedure_type}
        </span>
        <span
          className="committee-work-card__status"
          style={{ backgroundColor: statusInfo.color }}
        >
          {statusInfo.name}
        </span>
      </div>

      <h4 className="committee-work-card__title">
        {item.title}
      </h4>

      <div className="committee-work-card__meta">
        <span className="committee-work-card__ref">
          {item.procedure_ref}
        </span>
        {item.rapporteur_name && (
          <span className="committee-work-card__rapporteur">
            <Icon path={mdiAccountTieOutline} size={0.6} />
            {item.rapporteur_name}
          </span>
        )}
        <span className="committee-work-card__relevance" title="Relevance score">
          Score: {item.relevance_score}
        </span>
      </div>

      <div className="committee-work-card__actions">
        {oeilUrl && (
          <a
            href={oeilUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="committee-work-card__action-btn"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            OEIL
          </a>
        )}
        {eultUrl && (
          <a
            href={eultUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="committee-work-card__action-btn"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            EU Law Tracker
          </a>
        )}
        {item.ep_page_url && (
          <a
            href={item.ep_page_url}
            target="_blank"
            rel="noopener noreferrer"
            className="committee-work-card__action-btn"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            EP Page
          </a>
        )}
      </div>
    </div>
  );
};
