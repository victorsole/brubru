/**
 * Amendments Tab Component
 *
 * Displays and manages user amendments with status tracking.
 * Groups amendments by tracked legislative file for better context.
 * Part of My EU Bubble - Phase 3: Frontend + Priority #4 Integration
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '@mdi/react';
import { mdiFileDocumentOutline, mdiViewList, mdiViewModule, mdiPencilOutline, mdiOpenInNew } from '@mdi/js';
import { useAuth } from '../../hooks/use_auth';
import { useLegislativeTrains } from '../../hooks/use_legislative_trains';
import type { TrackedFile } from '../../hooks/use_legislative_trains';
import './amendments_tab.css';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api`;

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

export const AmendmentsTab = () => {
  const navigate = useNavigate();
  const { token } = useAuth();
  const { trackedFiles, fetchTrackedFiles, fetchFileDetail } = useLegislativeTrains();
  const [amendments, setAmendments] = useState<Amendment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [documentFilter, setDocumentFilter] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'list' | 'grouped'>('grouped');

  useEffect(() => {
    fetchAmendments();
    fetchTrackedFiles();
  }, []);

  const fetchAmendments = async () => {
    setIsLoading(true);
    try {
      console.log('🔍 Fetching amendments from API...');
      const response = await fetch(`${API_BASE}/amendments`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      console.log('📡 Response status:', response.status);
      if (response.ok) {
        const data = await response.json();
        console.log('✅ Amendments data:', data);
        console.log('📊 Number of amendments:', data.amendments?.length || 0);
        setAmendments(data.amendments || []);
      } else {
        console.error('❌ Failed to fetch amendments, status:', response.status);
      }
    } catch (error) {
      console.error('❌ Error fetching amendments:', error);
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
        return a.trackedFile.title.localeCompare(b.trackedFile.title);
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
      {/* Header */}
      <div className="amendments-tab__header">
        <div className="amendments-tab__header-left">
          <h2>My Amendments</h2>
          <div className="amendments-tab__summary">
            <span className="amendments-tab__summary-item">
              Total: <strong>{amendments.length}</strong>
            </span>
            <span className="amendments-tab__summary-item">
              Documents: <strong>{uniqueDocuments.length}</strong>
            </span>
          </div>
        </div>
        <div className="amendments-tab__view-toggle">
          <button
            className={`amendments-tab__view-btn ${viewMode === 'grouped' ? 'amendments-tab__view-btn--active' : ''}`}
            onClick={() => setViewMode('grouped')}
            title="Group by Legislative File"
          >
            <Icon path={mdiViewModule} size={0.8} />
            Grouped
          </button>
          <button
            className={`amendments-tab__view-btn ${viewMode === 'list' ? 'amendments-tab__view-btn--active' : ''}`}
            onClick={() => setViewMode('list')}
            title="List View"
          >
            <Icon path={mdiViewList} size={0.8} />
            List
          </button>
        </div>
      </div>

      {/* Document Filter */}
      {uniqueDocuments.length > 1 && (
        <div className="amendments-tab__document-filter">
          <label>Filter by Document:</label>
          <select
            value={documentFilter}
            onChange={(e) => setDocumentFilter(e.target.value)}
            className="amendments-tab__filter-select"
          >
            <option value="all">All Documents</option>
            {uniqueDocuments.map(docId => (
              <option key={docId} value={docId}>{docId}</option>
            ))}
          </select>
        </div>
      )}

      {/* Status Filters */}
      <div className="amendments-tab__status-filters">
        {[
          { value: 'all', label: 'All', color: '#666' },
          { value: 'draft', label: 'Draft', color: '#999' },
          { value: 'candidate', label: 'Candidate', color: '#f57c00' },
          { value: 'tabled', label: 'Tabled', color: '#059669' },
          { value: 'adopted', label: 'Adopted', color: '#2e7d32' },
          { value: 'rejected', label: 'Rejected', color: '#dc3545' },
          { value: 'withdrawn', label: 'Withdrawn', color: '#6b7280' },
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
          <div className="amendments-tab__loading">Loading amendments...</div>
        ) : filteredAmendments.length === 0 ? (
          <div className="amendments-tab__empty">
            <p>No amendments found</p>
            <small>Create amendments in the Amendator to see them here</small>
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
                          {group.trackedFile.oeil_procedure_ref && (
                            <span className="amendments-tab__group-ref">
                              {group.trackedFile.oeil_procedure_ref}
                            </span>
                          )}
                          <span className="amendments-tab__group-count">
                            {group.amendments.length} amendment{group.amendments.length !== 1 ? 's' : ''}
                          </span>
                        </div>
                        <h3
                          className="amendments-tab__group-title"
                          onClick={() => fetchFileDetail(group.trackedFile!.file_id)}
                        >
                          <Icon path={mdiFileDocumentOutline} size={0.9} />
                          {group.trackedFile.title}
                        </h3>
                      </div>
                      <div className="amendments-tab__group-actions">
                        <button
                          className="amendments-tab__group-action-btn"
                          onClick={() => navigate('/amendator')}
                          title="Draft More Amendments"
                        >
                          <Icon path={mdiPencilOutline} size={0.7} />
                        </button>
                        {group.trackedFile.oeil_procedure_ref && (
                          <a
                            href={`https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${group.trackedFile.oeil_procedure_ref}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="amendments-tab__group-action-btn"
                            title="View in OEIL"
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
                            <strong>Original:</strong>
                            <p>{amendment.original_text.slice(0, 100)}{amendment.original_text.length > 100 ? '...' : ''}</p>
                          </div>
                        )}
                        {amendment.proposed_text && amendment.amendment_type !== 'suppression' && (
                          <div className="amendments-tab__text-block">
                            <strong>Proposed:</strong>
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
                          <option value="draft">Draft</option>
                          <option value="candidate">Candidate</option>
                          <option value="tabled">Tabled</option>
                          <option value="adopted">Adopted</option>
                          <option value="rejected">Rejected</option>
                          <option value="withdrawn">Withdrawn</option>
                        </select>
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
                        <strong>Original:</strong>
                        <p>{amendment.original_text.slice(0, 150)}{amendment.original_text.length > 150 ? '...' : ''}</p>
                      </div>
                    )}
                    {amendment.proposed_text && amendment.amendment_type !== 'suppression' && (
                      <div className="amendments-tab__text-block">
                        <strong>Proposed:</strong>
                        <p><em><strong>{amendment.proposed_text.slice(0, 150)}{amendment.proposed_text.length > 150 ? '...' : ''}</strong></em></p>
                      </div>
                    )}
                  </div>

                  {/* Justification */}
                  {amendment.justification && (
                    <div className="amendments-tab__justification">
                      <strong>Justification:</strong>
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
                      <option value="draft">Draft</option>
                      <option value="candidate">Candidate</option>
                      <option value="tabled">Tabled</option>
                      <option value="adopted">Adopted</option>
                      <option value="rejected">Rejected</option>
                      <option value="withdrawn">Withdrawn</option>
                    </select>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
