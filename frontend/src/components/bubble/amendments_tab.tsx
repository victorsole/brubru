/**
 * Amendments Tab Component
 *
 * Displays and manages user amendments with status tracking.
 * Part of My EU Bubble - Phase 3: Frontend
 */

import { useEffect, useState } from 'react';
import { useAuth } from '../../hooks/use_auth';
import './amendments_tab.css';

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
}

export const AmendmentsTab = () => {
  const { token } = useAuth();
  const [amendments, setAmendments] = useState<Amendment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [documentFilter, setDocumentFilter] = useState<string>('all');

  useEffect(() => {
    fetchAmendments();
  }, []);

  const fetchAmendments = async () => {
    setIsLoading(true);
    try {
      console.log('🔍 Fetching amendments from API...');
      const response = await fetch('/api/amendments', {
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
      const response = await fetch(`/api/amendments/${id}`, {
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

  return (
    <div className="amendments-tab">
      {/* Header */}
      <div className="amendments-tab__header">
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
        ) : (
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
