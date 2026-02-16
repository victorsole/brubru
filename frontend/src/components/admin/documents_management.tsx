// frontend/src/components/admin/documents_management.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import { AdminModal } from './shared/admin_modal';
import { AdminExportButton } from './shared/admin_export_button';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface Document {
  id: string;
  user_id: string;
  title: string;
  file_name?: string;
  file_type?: string;
  file_size?: number;
  source?: 'upload' | 'eurlex';
  celex_number?: string;
  uploaded_at: string;
  versions?: number;
  user_email?: string;
}

interface DocumentStats {
  total_documents: number;
  total_storage_bytes: number;
  by_type: Record<string, number>;
  by_source?: { upload: number; eurlex: number };
  this_week: number;
}

export const DocumentsManagement = () => {
  const { token } = useAuth();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [stats, setStats] = useState<DocumentStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const calculateStats = (documentsList: Document[]) => {
    const now = new Date();
    const oneWeekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);

    const byType: Record<string, number> = {};
    const bySource = { upload: 0, eurlex: 0 };
    let totalStorage = 0;
    let thisWeek = 0;

    documentsList.forEach(doc => {
      // Count by type
      const type = doc.file_type || 'unknown';
      byType[type] = (byType[type] || 0) + 1;

      // Count by source
      if (doc.source === 'upload') bySource.upload++;
      else if (doc.source === 'eurlex') bySource.eurlex++;

      // Sum storage
      if (doc.file_size) totalStorage += doc.file_size;

      // Count recent documents
      const uploadedAt = new Date(doc.uploaded_at);
      if (uploadedAt >= oneWeekAgo) thisWeek++;
    });

    setStats({
      total_documents: documentsList.length,
      total_storage_bytes: totalStorage,
      by_type: byType,
      by_source: bySource,
      this_week: thisWeek
    });
  };

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      // Try user documents endpoint first
      const response = await axios.get(`${API_BASE_URL}/api/documents`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      // Handle response format - backend returns {documents: [...], total, limit, offset, has_more}
      const documentsArray = Array.isArray(response.data)
        ? response.data
        : (response.data.documents || []);

      setDocuments(documentsArray);
      calculateStats(documentsArray);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch documents:', err);
      setError(err.response?.data?.detail || 'Failed to load documents');
      setDocuments([]);
      setStats(null);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
      await axios.delete(`${API_BASE_URL}/api/documents/storage/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const updatedDocuments = documents.filter(d => d.id !== id);
      setDocuments(updatedDocuments);
      calculateStats(updatedDocuments);
    } catch (err: any) {
      console.error('Failed to delete document:', err);
      alert(err.response?.data?.detail || 'Failed to delete document');
    }
  };

  const handleDownload = async (doc: Document) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/documents/storage/${doc.id}`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', doc.file_name || doc.title || 'document');
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err: any) {
      console.error('Download failed:', err);
      alert('Failed to download document');
    }
  };

  const handleExport = async (format: 'csv' | 'json' | 'xlsx') => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/export/documents/${format}`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `documents.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err: any) {
      console.error('Export failed:', err);
      alert('Export functionality coming soon');
    }
  };

  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return 'Unknown';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  const formatStorageSize = (bytes: number): string => {
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
  };

  // Defensive check to ensure documents is an array
  const filteredDocuments = Array.isArray(documents) ? documents.filter(doc => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      if (
        !doc.title?.toLowerCase().includes(query) &&
        !doc.file_name?.toLowerCase().includes(query) &&
        !doc.user_email?.toLowerCase().includes(query) &&
        !doc.celex_number?.toLowerCase().includes(query)
      ) {
        return false;
      }
    }
    if (sourceFilter !== 'all' && doc.source !== sourceFilter) return false;
    return true;
  }) : [];

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
        <h2>Documents Management</h2>
        <div className="admin-section__actions">
          <input
            type="text"
            placeholder="Search documents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="admin-section__search"
          />
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="admin-section__filter"
          >
            <option value="all">All Sources</option>
            <option value="upload">Upload</option>
            <option value="eurlex">EUR-Lex</option>
          </select>
          <button className="btn btn--primary btn--small" onClick={fetchDocuments}>
            <span className="mdi mdi-refresh"></span>
            Refresh
          </button>
          <AdminExportButton onExport={handleExport} />
        </div>
      </div>

      {stats && (
        <div className="admin-section__stats">
          <span>Total: <strong>{stats.total_documents}</strong></span>
          <span>Storage: <strong>{formatStorageSize(stats.total_storage_bytes)}</strong></span>
          <span>This Week: <strong>{stats.this_week}</strong></span>
          {stats.by_source && (
            <>
              <span>Uploads: <strong>{stats.by_source.upload}</strong></span>
              <span>EUR-Lex: <strong>{stats.by_source.eurlex}</strong></span>
            </>
          )}
        </div>
      )}

      <div className="admin-section__table-container">
        <table className="admin-section__table">
          <thead>
            <tr>
              <th>Title</th>
              <th>User</th>
              <th>Source</th>
              <th>Type</th>
              <th>Size</th>
              <th>Uploaded</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredDocuments.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }}>
                  No documents found
                </td>
              </tr>
            ) : (
              filteredDocuments.map((doc) => (
                <tr key={doc.id}>
                  <td>
                    <strong>{doc.title || doc.file_name || 'Untitled'}</strong>
                    {doc.celex_number && (
                      <>
                        <br />
                        <small className="admin-section__text-muted">{doc.celex_number}</small>
                      </>
                    )}
                  </td>
                  <td>
                    <small className="admin-section__text-muted">
                      {doc.user_email || doc.user_id}
                    </small>
                  </td>
                  <td>
                    <span className={`admin-section__badge ${doc.source === 'eurlex' ? 'admin-section__badge--blue' : ''}`}>
                      {doc.source || 'upload'}
                    </span>
                  </td>
                  <td>
                    <span className="admin-section__badge">
                      {doc.file_type || 'unknown'}
                    </span>
                  </td>
                  <td>{formatFileSize(doc.file_size)}</td>
                  <td>{new Date(doc.uploaded_at).toLocaleDateString()}</td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button
                        className="btn btn--secondary btn--small"
                        onClick={() => {
                          setSelectedDocument(doc);
                          setShowDetailModal(true);
                        }}
                        title="View details"
                      >
                        <span className="mdi mdi-eye"></span>
                      </button>
                      <button
                        className="btn btn--secondary btn--small"
                        onClick={() => handleDownload(doc)}
                        title="Download"
                      >
                        <span className="mdi mdi-download"></span>
                      </button>
                      <button
                        className="btn btn--secondary btn--small"
                        onClick={() => handleDelete(doc.id)}
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

      {/* Document Detail Modal */}
      <AdminModal
        isOpen={showDetailModal}
        onClose={() => setShowDetailModal(false)}
        title="Document Details"
        size="large"
      >
        {selectedDocument && (
          <div style={{ display: 'grid', gap: '1.5rem' }}>
            <div>
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>Title</h4>
              <p style={{ margin: 0, fontWeight: 600 }}>{selectedDocument.title || selectedDocument.file_name}</p>
            </div>
            <div>
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>User</h4>
              <p style={{ margin: 0 }}>{selectedDocument.user_email || selectedDocument.user_id}</p>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>Source</h4>
                <span className="admin-section__badge">{selectedDocument.source || 'upload'}</span>
              </div>
              <div>
                <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>File Type</h4>
                <span className="admin-section__badge">{selectedDocument.file_type || 'unknown'}</span>
              </div>
            </div>
            {selectedDocument.celex_number && (
              <div>
                <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>CELEX Number</h4>
                <p style={{ margin: 0 }}>{selectedDocument.celex_number}</p>
              </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>File Size</h4>
                <p style={{ margin: 0 }}>{formatFileSize(selectedDocument.file_size)}</p>
              </div>
              <div>
                <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>Uploaded</h4>
                <p style={{ margin: 0 }}>{new Date(selectedDocument.uploaded_at).toLocaleString()}</p>
              </div>
            </div>
            {selectedDocument.versions && selectedDocument.versions > 1 && (
              <div>
                <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>Versions</h4>
                <p style={{ margin: 0 }}>{selectedDocument.versions} versions available</p>
              </div>
            )}
          </div>
        )}
      </AdminModal>
    </div>
  );
};
