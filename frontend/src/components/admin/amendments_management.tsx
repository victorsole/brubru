// frontend/src/components/admin/amendments_management.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface AmendmentRow {
  id: string;
  user_email: string | null;
  procedure_reference: string | null;
  document_filename: string | null;
  amendment_type: string | null;
  amendment_number: number | null;
  status: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export const AmendmentsManagement = () => {
  const { token } = useAuth();
  const [amendments, setAmendments] = useState<AmendmentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    fetchAmendments();
  }, [page]);

  const fetchAmendments = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/admin/amendments`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { page, page_size: 50 }
      });
      setAmendments(response.data.items || []);
      setTotal(response.data.total || 0);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch amendments:', err);
      setError(err.response?.data?.detail || 'Failed to load amendments');
      setAmendments([]);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this amendment? This cannot be undone.')) return;
    try {
      await axios.delete(`${API_BASE_URL}/api/admin/amendments/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      fetchAmendments();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete amendment');
    }
  };

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
        <h2>Amendments (all users)</h2>
        <button className="btn btn--primary btn--small" onClick={fetchAmendments}>
          <span className="mdi mdi-refresh"></span>
          Refresh
        </button>
      </div>

      <div className="admin-section__stats">
        <span>Total Amendments: <strong>{total}</strong></span>
        <span>Showing: <strong>{amendments.length}</strong></span>
      </div>

      <div className="admin-section__table-container">
        <table className="admin-section__table">
          <thead>
            <tr>
              <th>User</th>
              <th>Procedure</th>
              <th>Document</th>
              <th>Type</th>
              <th>Status</th>
              <th>Updated</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {amendments.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }}>
                  No amendments found
                </td>
              </tr>
            ) : (
              amendments.map((a) => (
                <tr key={a.id}>
                  <td><small className="admin-section__text-muted">{a.user_email || '-'}</small></td>
                  <td>{a.procedure_reference || '-'}</td>
                  <td><small>{(a.document_filename || '-').substring(0, 40)}</small></td>
                  <td>
                    <span className="admin-section__badge">
                      {a.amendment_type || '-'}
                    </span>
                  </td>
                  <td>{a.status || '-'}</td>
                  <td>{a.updated_at ? new Date(a.updated_at).toLocaleString() : '-'}</td>
                  <td>
                    <button
                      className="btn btn--secondary btn--small"
                      onClick={() => handleDelete(a.id)}
                      style={{ color: '#dc2626' }}
                      title="Delete amendment"
                    >
                      <span className="mdi mdi-delete"></span>
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {total > 50 && (
        <div className="admin-section__pagination">
          <button
            className="btn btn--secondary btn--small"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </button>
          <span>Page {page} of {Math.ceil(total / 50)}</span>
          <button
            className="btn btn--secondary btn--small"
            onClick={() => setPage(p => p + 1)}
            disabled={page >= Math.ceil(total / 50)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};
