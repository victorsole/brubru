/**
 * Documents Tab Component
 *
 * Displays and manages user documents (amendments, analyses, strategies, notes).
 * Part of My EU Bubble - Phase 3: Frontend
 */

import { useEffect, useState } from 'react';
import { useBubble } from '../../hooks/use_bubble';
import './documents_tab.css';

export const DocumentsTab = () => {
  const {
    documents,
    isLoadingDocuments,
    fetchDocuments,
    createDocument,
    deleteDocument,
    selectDocument,
  } = useBubble();

  const [filterType, setFilterType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    fetchDocuments({
      document_type: filterType !== 'all' ? filterType : undefined,
      search: searchQuery || undefined,
    });
  }, [filterType, searchQuery]);

  const handleCreateDocument = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);

    const document = {
      document_type: formData.get('type') as 'amendment' | 'analysis' | 'strategy' | 'note',
      title: formData.get('title') as string,
      content: formData.get('content') as string,
      policy_areas: (formData.get('policy_areas') as string)?.split(',').map(s => s.trim()).filter(Boolean) || [],
      tags: (formData.get('tags') as string)?.split(',').map(s => s.trim()).filter(Boolean) || [],
    };

    try {
      await createDocument(document);
      setShowCreateModal(false);
      e.currentTarget.reset();
    } catch (error) {
      console.error('Failed to create document:', error);
    }
  };

  const handleDelete = async (id: string, title: string) => {
    if (confirm(`Are you sure you want to delete "${title}"?`)) {
      await deleteDocument(id);
    }
  };

  const filteredDocuments = documents.filter(doc => {
    if (filterType !== 'all' && doc.document_type !== filterType) return false;
    if (searchQuery && !doc.title.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="documents-tab">
      {/* Header */}
      <div className="documents-tab__header">
        <h2>My Documents</h2>
        <button
          className="documents-tab__create-btn"
          onClick={() => setShowCreateModal(true)}
        >
          + Create Document
        </button>
      </div>

      {/* Filters */}
      <div className="documents-tab__filters">
        <div className="documents-tab__filter-group">
          <label>Type:</label>
          <select value={filterType} onChange={(e) => setFilterType(e.target.value)}>
            <option value="all">All</option>
            <option value="amendment">Amendments</option>
            <option value="analysis">Analyses</option>
            <option value="strategy">Strategies</option>
            <option value="note">Notes</option>
          </select>
        </div>

        <div className="documents-tab__filter-group documents-tab__filter-group--search">
          <input
            type="text"
            placeholder="Search documents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Document Grid */}
      <div className="documents-tab__content">
        {isLoadingDocuments ? (
          <div className="documents-tab__loading">Loading documents...</div>
        ) : filteredDocuments.length === 0 ? (
          <div className="documents-tab__empty">
            <p>No documents found</p>
            <button onClick={() => setShowCreateModal(true)}>
              Create your first document
            </button>
          </div>
        ) : (
          <div className="documents-tab__grid">
            {filteredDocuments.map(doc => (
              <div key={doc.id} className="documents-tab__card" data-type={doc.document_type}>
                {/* Type Badge */}
                <div className="documents-tab__card-badge">{doc.document_type}</div>

                {/* Content */}
                <div className="documents-tab__card-content">
                  <h3 className="documents-tab__card-title">{doc.title}</h3>

                  {doc.content && (
                    <p className="documents-tab__card-excerpt">
                      {doc.content.slice(0, 150)}...
                    </p>
                  )}

                  {/* Meta */}
                  <div className="documents-tab__card-meta">
                    <span>{new Date(doc.updated_at).toLocaleDateString()}</span>
                    <span>•</span>
                    <span>{doc.word_count || 0} words</span>
                  </div>

                  {/* Policy Areas */}
                  {doc.policy_areas && doc.policy_areas.length > 0 && (
                    <div className="documents-tab__card-tags">
                      {doc.policy_areas.slice(0, 3).map((area, idx) => (
                        <span key={idx} className="documents-tab__tag">{area}</span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="documents-tab__card-actions">
                  <button
                    className="documents-tab__action-btn"
                    onClick={() => selectDocument(doc)}
                  >
                    View
                  </button>
                  <button
                    className="documents-tab__action-btn documents-tab__action-btn--danger"
                    onClick={() => handleDelete(doc.id, doc.title)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="documents-tab__modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="documents-tab__modal" onClick={(e) => e.stopPropagation()}>
            <div className="documents-tab__modal-header">
              <h3>Create Document</h3>
              <button onClick={() => setShowCreateModal(false)}>×</button>
            </div>

            <form onSubmit={handleCreateDocument}>
              <div className="documents-tab__form-group">
                <label>Document Type *</label>
                <select name="type" required>
                  <option value="note">Note</option>
                  <option value="amendment">Amendment</option>
                  <option value="analysis">Analysis</option>
                  <option value="strategy">Strategy</option>
                </select>
              </div>

              <div className="documents-tab__form-group">
                <label>Title *</label>
                <input
                  type="text"
                  name="title"
                  required
                  placeholder="Enter document title"
                />
              </div>

              <div className="documents-tab__form-group">
                <label>Content</label>
                <textarea
                  name="content"
                  rows={6}
                  placeholder="Enter document content"
                />
              </div>

              <div className="documents-tab__form-group">
                <label>Policy Areas</label>
                <input
                  type="text"
                  name="policy_areas"
                  placeholder="e.g., Climate Action, Energy (comma-separated)"
                />
              </div>

              <div className="documents-tab__form-group">
                <label>Tags</label>
                <input
                  type="text"
                  name="tags"
                  placeholder="e.g., urgent, review (comma-separated)"
                />
              </div>

              <div className="documents-tab__modal-actions">
                <button
                  type="button"
                  className="documents-tab__modal-btn documents-tab__modal-btn--secondary"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="documents-tab__modal-btn documents-tab__modal-btn--primary"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
