// frontend/src/components/admin/amendments_management.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import { AdminModal } from './shared/admin_modal';
import { AdminExportButton } from './shared/admin_export_button';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface Amendment {
  id: string;
  user_id: string;
  user_email?: string;
  document_id: string;
  document_title?: string;
  amendment_type: 'addition' | 'modification' | 'suppression';
  original_text: string;
  proposed_text: string;
  justification?: string;
  element_type?: string;
  element_number?: string;
  position?: number;
  status?: string;
  created_at: string;
  updated_at: string;
}

interface AmendmentStats {
  total_amendments: number;
  by_type: Record<string, number>;
  this_month: number;
  this_week: number;
}

export const AmendmentsManagement = () => {
  const { token } = useAuth();
  const [amendments, setAmendments] = useState<Amendment[]>([]);
  const [stats, setStats] = useState<AmendmentStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [selectedAmendment, setSelectedAmendment] = useState<Amendment | null>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);

  useEffect(() => {
    fetchAmendments();
  }, []);

  const calculateStats = (amendmentsList: Amendment[]) => {
    const now = new Date();
    const oneWeekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    const oneMonthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);

    const byType: Record<string, number> = {};
    let thisWeek = 0;
    let thisMonth = 0;

    amendmentsList.forEach(amendment => {
      // Count by type
      const type = amendment.amendment_type || 'unknown';
      byType[type] = (byType[type] || 0) + 1;

      // Count recent amendments
      const createdAt = new Date(amendment.created_at);
      if (createdAt >= oneWeekAgo) thisWeek++;
      if (createdAt >= oneMonthAgo) thisMonth++;
    });

    setStats({
      total_amendments: amendmentsList.length,
      by_type: byType,
      this_week: thisWeek,
      this_month: thisMonth
    });
  };

  const fetchAmendments = async () => {
    try {
      setLoading(true);
      const params: any = {};
      if (typeFilter !== 'all') params.amendment_type = typeFilter;

      const response = await axios.get(`${API_BASE_URL}/api/amendments`, {
        headers: { Authorization: `Bearer ${token}` },
        params
      });

      // Handle response format - backend returns {amendments: [...], total, page, page_size}
      const amendmentsArray = Array.isArray(response.data)
        ? response.data
        : (response.data.amendments || []);

      setAmendments(amendmentsArray);
      calculateStats(amendmentsArray);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch amendments:', err);
      setError(err.response?.data?.detail || 'Failed to load amendments');
      setAmendments([]);
      setStats(null);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this amendment?')) return;

    try {
      await axios.delete(`${API_BASE_URL}/api/amendments/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const updatedAmendments = amendments.filter(a => a.id !== id);
      setAmendments(updatedAmendments);
      calculateStats(updatedAmendments);
    } catch (err: any) {
      console.error('Failed to delete amendment:', err);
      alert(err.response?.data?.detail || 'Failed to delete amendment');
    }
  };

  const handleExport = async (format: 'csv' | 'json' | 'xlsx') => {
    try {
      // Implementation would depend on backend export endpoint
      const response = await axios.get(`${API_BASE_URL}/api/amendments/export`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { format },
        responseType: 'blob'
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `amendments.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err: any) {
      console.error('Export failed:', err);
      alert('Export functionality coming soon');
    }
  };

  // Defensive check to ensure amendments is an array
  const filteredAmendments = Array.isArray(amendments) ? amendments.filter(amendment => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return (
        amendment.original_text?.toLowerCase().includes(query) ||
        amendment.proposed_text?.toLowerCase().includes(query) ||
        amendment.user_email?.toLowerCase().includes(query) ||
        amendment.document_title?.toLowerCase().includes(query)
      );
    }
    return true;
  }) : [];

  if (loading && amendments.length === 0) {
    return <div className="admin-section__loading">Loading amendments...</div>;
  }

  if (error && amendments.length === 0) {
    return (
      <div className="admin-section__error">
        <p>{error}</p>
        <button className="btn btn--primary btn--small" onClick={fetchAmendments}>Retry</button>
      </div>
    );
  }

  return (
    <div className="admin-section">
      <div className="admin-section__header">
        <h2>Amendments Management</h2>
        <div className="admin-section__actions">
          <input
            type="text"
            placeholder="Search amendments..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="admin-section__search"
          />
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="admin-section__filter"
          >
            <option value="all">All Types</option>
            <option value="addition">Addition</option>
            <option value="modification">Modification</option>
            <option value="suppression">Suppression</option>
          </select>
          <button className="btn btn--primary btn--small" onClick={fetchAmendments}>
            <span className="mdi mdi-refresh"></span>
            Refresh
          </button>
          <AdminExportButton onExport={handleExport} />
        </div>
      </div>

      {stats && (
        <div className="admin-section__stats">
          <span>Total: <strong>{stats.total_amendments}</strong></span>
          <span>This Month: <strong>{stats.this_month}</strong></span>
          <span>This Week: <strong>{stats.this_week}</strong></span>
          <span>Additions: <strong>{stats.by_type.addition || 0}</strong></span>
          <span>Modifications: <strong>{stats.by_type.modification || 0}</strong></span>
          <span>Suppressions: <strong>{stats.by_type.suppression || 0}</strong></span>
        </div>
      )}

      <div className="admin-section__table-container">
        <table className="admin-section__table">
          <thead>
            <tr>
              <th>User</th>
              <th>Document</th>
              <th>Type</th>
              <th>Element</th>
              <th>Original Text</th>
              <th>Proposed Text</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredAmendments.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '2rem' }}>
                  No amendments found
                </td>
              </tr>
            ) : (
              filteredAmendments.map((amendment) => (
                <tr key={amendment.id}>
                  <td>
                    <small className="admin-section__text-muted">
                      {amendment.user_email || amendment.user_id}
                    </small>
                  </td>
                  <td>
                    <small className="admin-section__text-muted">
                      {amendment.document_title || amendment.document_id}
                    </small>
                  </td>
                  <td>
                    <span className={`admin-section__badge admin-section__badge--type`}>
                      {amendment.amendment_type}
                    </span>
                  </td>
                  <td>
                    <small className="admin-section__text-muted">
                      {amendment.element_type} {amendment.element_number}
                    </small>
                  </td>
                  <td>
                    <div style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {amendment.original_text?.substring(0, 50)}
                      {amendment.original_text?.length > 50 ? '...' : ''}
                    </div>
                  </td>
                  <td>
                    <div style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {amendment.proposed_text?.substring(0, 50)}
                      {amendment.proposed_text?.length > 50 ? '...' : ''}
                    </div>
                  </td>
                  <td>{new Date(amendment.created_at).toLocaleDateString()}</td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button
                        className="btn btn--secondary btn--small"
                        onClick={() => {
                          setSelectedAmendment(amendment);
                          setShowDetailModal(true);
                        }}
                        title="View details"
                      >
                        <span className="mdi mdi-eye"></span>
                      </button>
                      <button
                        className="btn btn--secondary btn--small"
                        onClick={() => handleDelete(amendment.id)}
                        title="Delete"
                        style={{ color: '#dc2626' }}
                      >
                        <span className="mdi mdi-delete"></span>
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Amendment Detail Modal */}
      <AdminModal
        isOpen={showDetailModal}
        onClose={() => setShowDetailModal(false)}
        title="Amendment Details"
        size="large"
      >
        {selectedAmendment && (
          <div style={{ display: 'grid', gap: '1.5rem' }}>
            <div>
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>User</h4>
              <p style={{ margin: 0 }}>{selectedAmendment.user_email || selectedAmendment.user_id}</p>
            </div>
            <div>
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>Document</h4>
              <p style={{ margin: 0 }}>{selectedAmendment.document_title || selectedAmendment.document_id}</p>
            </div>
            <div>
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>Amendment Type</h4>
              <span className="admin-section__badge admin-section__badge--type">
                {selectedAmendment.amendment_type}
              </span>
            </div>
            <div>
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>Element</h4>
              <p style={{ margin: 0 }}>
                {selectedAmendment.element_type} {selectedAmendment.element_number}
              </p>
            </div>
            <div>
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>Original Text</h4>
              <p style={{ margin: 0, whiteSpace: 'pre-wrap', background: '#f9fafb', padding: '1rem', borderRadius: '6px' }}>
                {selectedAmendment.original_text}
              </p>
            </div>
            <div>
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>Proposed Text</h4>
              <p style={{ margin: 0, whiteSpace: 'pre-wrap', background: '#f0fdf4', padding: '1rem', borderRadius: '6px' }}>
                {selectedAmendment.proposed_text}
              </p>
            </div>
            {selectedAmendment.justification && (
              <div>
                <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>Justification</h4>
                <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{selectedAmendment.justification}</p>
              </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', fontSize: '0.875rem', color: '#6b7280' }}>
              <div>
                <strong>Created:</strong> {new Date(selectedAmendment.created_at).toLocaleString()}
              </div>
              <div>
                <strong>Updated:</strong> {new Date(selectedAmendment.updated_at).toLocaleString()}
              </div>
            </div>
          </div>
        )}
      </AdminModal>
    </div>
  );
};
