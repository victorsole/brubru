// frontend/src/components/admin/documents_management.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface DocumentRow {
  id: string;
  user_email: string | null;
  title: string | null;
  document_type: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export const DocumentsManagement = () => {
  const { token } = useAuth();
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    fetchDocuments();
  }, [page]);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/admin/documents`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { page, page_size: 50 }
      });
      setDocuments(response.data.items || []);
      setTotal(response.data.total || 0);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch documents:', err);
      setError(err.response?.data?.detail || 'Failed to load documents');
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  };

  if (loading && documents.length === 0) {
    return <div className="admin-section__loading">Loading documents...</div>;
  }

  if (error && documents.length === 0) {
    return (
      <div className="admin-section__error">
        <p>{error}</p>
        <button className="btn btn--primary btn--small" onClick={fetchDocuments}>Retry</button>
      </div>
    );
  }

  return (
    <div className="admin-section">
      <div className="admin-section__header">
        <h2>Documents (all users)</h2>
        <button className="btn btn--primary btn--small" onClick={fetchDocuments}>
          <span className="mdi mdi-refresh"></span>
          Refresh
        </button>
      </div>

      <div className="admin-section__stats">
        <span>Total Documents: <strong>{total}</strong></span>
        <span>Showing: <strong>{documents.length}</strong></span>
      </div>

      <div className="admin-section__table-container">
        <table className="admin-section__table">
          <thead>
            <tr>
              <th>User</th>
              <th>Title</th>
              <th>Type</th>
              <th>Created</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {documents.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ textAlign: 'center', padding: '2rem' }}>
                  No documents found
                </td>
              </tr>
            ) : (
              documents.map((d) => (
                <tr key={d.id}>
                  <td><small className="admin-section__text-muted">{d.user_email || '-'}</small></td>
                  <td>{(d.title || '-').substring(0, 60)}</td>
                  <td>
                    <span className="admin-section__badge">{d.document_type || '-'}</span>
                  </td>
                  <td>{d.created_at ? new Date(d.created_at).toLocaleDateString() : '-'}</td>
                  <td>{d.updated_at ? new Date(d.updated_at).toLocaleString() : '-'}</td>
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
