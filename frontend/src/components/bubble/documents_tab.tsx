/**
 * Documents Tab Component
 *
 * Displays and manages user documents (amendments, analyses, strategies, notes, uploaded files).
 * Part of My EU Bubble - Phase 3: Frontend
 */

import { useEffect, useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import Icon from '@mdi/react';
import {
  mdiRobotOutline,
  mdiFileUploadOutline,
  mdiFilePdfBox,
  mdiFileWordBox,
  mdiFileDocumentOutline,
  mdiBrain,
} from '@mdi/js';
import { marked } from 'marked';
import { useBubble } from '../../hooks/use_bubble';
import type { UserDocument } from '../../hooks/use_bubble';
import { useAuth } from '../../hooks/use_auth';
import { DocumentGeneratorWizard } from './document_generator_wizard';
import './documents_tab.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/** Strip markdown syntax for plain-text card excerpts */
function stripMarkdown(text: string): string {
  return text
    .replace(/```[\w]*\n?/g, '')        // ```markdown / ``` code fences
    .replace(/\*\*(.*?)\*\*/g, '$1')   // **bold**
    .replace(/\*(.*?)\*/g, '$1')        // *italic*
    .replace(/^--\s*/gm, '\u2014 ')     // -- dashes
    .replace(/^#+\s*/gm, '')            // # headings
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // [links](url)
    .replace(/`([^`]+)`/g, '$1')        // `code`
    .replace(/^\d+\.\s+/gm, '')         // 1. numbered lists
    .replace(/^[-*]\s+/gm, '')          // - bullet lists
    .trim();
}

/** Format file size for display */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Get file type icon path */
function getFileTypeIcon(contentType?: string): string {
  if (contentType === 'application/pdf') return mdiFilePdfBox;
  if (contentType?.includes('word') || contentType?.includes('docx')) return mdiFileWordBox;
  return mdiFileDocumentOutline;
}

export const DocumentsTab = () => {
  const {
    documents,
    isLoadingDocuments,
    fetchDocuments,
    createDocument,
    updateDocument,
    deleteDocument,
    selectDocument,
  } = useBubble();

  const { user } = useAuth();
  const userTier = user?.subscription_tier || 'white';
  const canUseResolution = userTier === 'yellow' || userTier === 'blue';

  const [filterType, setFilterType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showGeneratorWizard, setShowGeneratorWizard] = useState(false);
  const [viewingDocument, setViewingDocument] = useState<UserDocument | null>(null);

  // Upload state
  const [isUploading, setIsUploading] = useState(false);
  const [uploadDragging, setUploadDragging] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchDocuments({
      document_type: filterType !== 'all' ? filterType : undefined,
      search: searchQuery || undefined,
    });
  }, [filterType, searchQuery]);

  const [createType, setCreateType] = useState('note');

  const RESOLUTION_TEMPLATE = `**European Parliament resolution on [topic]**

**The European Parliament,**

-- having regard to Articles 2 and 3 of the Treaty on European Union,

-- having regard to Rule 132(2) of its Rules of Procedure,

A.  whereas [first contextual statement];

B.  whereas [second contextual statement];

C.  whereas [third contextual statement];

1.  Calls on [the Commission/Council/Member States] to [specific action];

2.  Urges [institution] to [specific action];

3.  Stresses that [important principle];

4.  Instructs its President to forward this resolution to the Council, the Commission, the Vice-President of the Commission / High Representative of the Union for Foreign Affairs and Security Policy, and the governments and parliaments of the Member States.
`;

  const handleCreateDocument = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);

    const selectedType = formData.get('type') as string;
    const isResolution = selectedType === 'resolution';

    const userTags = (formData.get('tags') as string)?.split(',').map(s => s.trim()).filter(Boolean) || [];

    const document = {
      document_type: (isResolution ? 'note' : selectedType) as 'amendment' | 'analysis' | 'strategy' | 'note',
      title: formData.get('title') as string,
      content: formData.get('content') as string,
      policy_areas: (formData.get('policy_areas') as string)?.split(',').map(s => s.trim()).filter(Boolean) || [],
      tags: isResolution ? ['resolution', ...userTags] : userTags,
    };

    try {
      const form = e.currentTarget;
      await createDocument(document);
      form.reset();
      setCreateType('note');
      setShowCreateModal(false);
    } catch (error) {
      console.error('Failed to create document:', error);
    }
  };

  const handleDelete = async (id: string, title: string) => {
    if (confirm(`Are you sure you want to delete "${title}"?`)) {
      await deleteDocument(id);
    }
  };

  const handleToggleAIContext = async (doc: UserDocument) => {
    try {
      await updateDocument(doc.id, {
        include_in_ai_context: !doc.include_in_ai_context,
      });
    } catch (error) {
      console.error('Failed to toggle AI context:', error);
    }
  };

  const handleUploadFile = async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    if (fileArray.length === 0) return;

    setIsUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      for (const file of fileArray) {
        if (file.size > 10 * 1024 * 1024) {
          setUploadError(`${file.name} exceeds 10MB limit`);
          continue;
        }

        const formData = new FormData();
        formData.append('file', file);

        const token = useAuth.getState().token;
        const response = await fetch(`${API_BASE_URL}/api/documents/upload`, {
          method: 'POST',
          headers: {
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
          },
          body: formData,
        });

        if (!response.ok) {
          const err = await response.json().catch(() => ({ detail: 'Upload failed' }));
          setUploadError(err.detail || `Failed to upload ${file.name}`);
          continue;
        }

        setUploadSuccess(`"${file.name}" uploaded successfully`);
      }

      // Refresh document list
      fetchDocuments({
        document_type: filterType !== 'all' ? filterType : undefined,
        search: searchQuery || undefined,
      });

      // Auto-close after success
      setTimeout(() => {
        setShowUploadModal(false);
        setUploadSuccess(null);
      }, 1500);
    } catch (error) {
      console.error('Upload failed:', error);
      setUploadError('Failed to upload file');
    } finally {
      setIsUploading(false);
    }
  };

  const handleUploadDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setUploadDragging(false);
    if (e.dataTransfer.files.length > 0) {
      handleUploadFile(e.dataTransfer.files);
    }
  };

  const filteredDocuments = documents.filter(doc => {
    if (filterType === 'ep_question') {
      if (!doc.tags?.includes('ep_question')) return false;
    } else if (filterType !== 'all' && doc.document_type !== filterType) {
      return false;
    }
    if (searchQuery && !doc.title.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="documents-tab">
      {/* Header */}
      <div className="documents-tab__header">
        <h2>My Documents</h2>
        <div className="documents-tab__header-actions">
          <button
            className="documents-tab__upload-btn"
            onClick={() => setShowUploadModal(true)}
          >
            <Icon path={mdiFileUploadOutline} size={0.9} />
            Upload
          </button>
          <button
            className="documents-tab__generate-btn"
            onClick={() => setShowGeneratorWizard(true)}
          >
            <Icon path={mdiRobotOutline} size={0.9} />
            Generate with AI
          </button>
          <button
            className="documents-tab__create-btn"
            onClick={() => setShowCreateModal(true)}
          >
            + Create Document
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="documents-tab__filters">
        <div className="documents-tab__filter-group">
          <label>Type:</label>
          <select value={filterType} onChange={(e) => setFilterType(e.target.value)}>
            <option value="all">All</option>
            <option value="uploaded">Uploaded Documents</option>
            <option value="amendment">Amendments</option>
            <option value="analysis">Analyses</option>
            <option value="strategy">Strategies</option>
            <option value="note">Notes</option>
            <option value="ep_question">EP Questions</option>
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
            {filteredDocuments.map(doc => {
              const isEpQuestion = doc.tags?.includes('ep_question');
              const displayType = isEpQuestion ? 'ep_question' : doc.document_type;
              return (
              <div key={doc.id} className="documents-tab__card" data-type={displayType}>
                {/* Type Badge */}
                <div className="documents-tab__card-badge">
                  {doc.document_type === 'uploaded' ? (
                    <span className="documents-tab__card-badge--uploaded">
                      <Icon path={getFileTypeIcon(doc.file_content_type)} size={0.6} />
                      uploaded
                    </span>
                  ) : isEpQuestion ? (
                    'EP Question'
                  ) : (
                    doc.document_type
                  )}
                </div>

                {/* Content */}
                <div className="documents-tab__card-content">
                  <h3 className="documents-tab__card-title">{doc.title}</h3>

                  {/* Uploaded file info */}
                  {doc.document_type === 'uploaded' && doc.original_filename && (
                    <div className="documents-tab__file-meta">
                      <span className="documents-tab__file-name">{doc.original_filename}</span>
                      {doc.file_size_bytes && (
                        <span className="documents-tab__file-size">{formatFileSize(doc.file_size_bytes)}</span>
                      )}
                    </div>
                  )}

                  {doc.content && (
                    <p className="documents-tab__card-excerpt">
                      {stripMarkdown(doc.content).slice(0, 150)}...
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
                  {doc.document_type === 'uploaded' && (
                    <button
                      className={`documents-tab__action-btn documents-tab__ai-toggle ${
                        doc.include_in_ai_context ? 'documents-tab__ai-toggle--active' : ''
                      }`}
                      onClick={() => handleToggleAIContext(doc)}
                      title={doc.include_in_ai_context ? 'Included in AI context (click to exclude)' : 'Excluded from AI context (click to include)'}
                    >
                      <Icon path={mdiBrain} size={0.7} />
                    </button>
                  )}
                  <button
                    className="documents-tab__action-btn"
                    onClick={() => { selectDocument(doc); setViewingDocument(doc); }}
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
              );
            })}
          </div>
        )}
      </div>

      {/* Upload Modal - rendered via portal to escape stacking context */}
      {showUploadModal && createPortal(
        <div className="documents-tab__modal-overlay" onClick={() => { setShowUploadModal(false); setUploadError(null); setUploadSuccess(null); }}>
          <div className="documents-tab__modal documents-tab__upload-modal" onClick={(e) => e.stopPropagation()}>
            <div className="documents-tab__modal-header">
              <h3>Upload Document</h3>
              <button onClick={() => { setShowUploadModal(false); setUploadError(null); setUploadSuccess(null); }}>x</button>
            </div>

            <div
              className={`documents-tab__dropzone ${uploadDragging ? 'documents-tab__dropzone--dragging' : ''} ${isUploading ? 'documents-tab__dropzone--uploading' : ''}`}
              onDragEnter={(e) => { e.preventDefault(); setUploadDragging(true); }}
              onDragOver={(e) => { e.preventDefault(); setUploadDragging(true); }}
              onDragLeave={() => setUploadDragging(false)}
              onDrop={handleUploadDrop}
              onClick={() => !isUploading && fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.doc"
                style={{ display: 'none' }}
                onChange={(e) => e.target.files && handleUploadFile(e.target.files)}
              />
              {isUploading ? (
                <div className="documents-tab__dropzone-content">
                  <div className="documents-tab__upload-spinner" />
                  <p>Uploading...</p>
                </div>
              ) : (
                <div className="documents-tab__dropzone-content">
                  <Icon path={mdiFileUploadOutline} size={2} />
                  <p>Drop files here or click to browse</p>
                  <span className="documents-tab__dropzone-formats">PDF, DOCX, DOC - Max 10MB</span>
                </div>
              )}
            </div>

            {uploadSuccess && (
              <div className="documents-tab__upload-feedback documents-tab__upload-feedback--success">
                {uploadSuccess}
              </div>
            )}
            {uploadError && (
              <div className="documents-tab__upload-feedback documents-tab__upload-feedback--error">
                {uploadError}
              </div>
            )}

            <p className="documents-tab__upload-note">
              Uploaded documents will be available in your AI context to personalise Brubru's responses.
            </p>
          </div>
        </div>,
        document.body
      )}

      {/* Create Modal - rendered via portal to escape stacking context */}
      {showCreateModal && createPortal(
        <div className="documents-tab__modal-overlay" onClick={() => { setShowCreateModal(false); setCreateType('note'); }}>
          <div className="documents-tab__modal" onClick={(e) => e.stopPropagation()}>
            <div className="documents-tab__modal-header">
              <h3>Create Document</h3>
              <button onClick={() => { setShowCreateModal(false); setCreateType('note'); }}>x</button>
            </div>

            <form onSubmit={handleCreateDocument}>
              <div className="documents-tab__form-group">
                <label>Document Type *</label>
                <select
                  name="type"
                  required
                  value={createType}
                  onChange={(e) => setCreateType(e.target.value)}
                >
                  <option value="note">Note</option>
                  <option value="amendment">Amendment</option>
                  <option value="analysis">Analysis</option>
                  <option value="strategy">Strategy</option>
                  {canUseResolution && (
                    <option value="resolution">EP Resolution</option>
                  )}
                </select>
              </div>

              <div className="documents-tab__form-group">
                <label>Title *</label>
                <input
                  type="text"
                  name="title"
                  required
                  placeholder={createType === 'resolution' ? 'e.g., EP Resolution on the situation in Sudan' : 'Enter document title'}
                />
              </div>

              <div className="documents-tab__form-group">
                <label>{createType === 'resolution' ? 'Resolution Text' : 'Content'}</label>
                <textarea
                  name="content"
                  rows={createType === 'resolution' ? 12 : 6}
                  placeholder={createType === 'resolution' ? 'Write or paste your resolution text following the EP format...' : 'Enter document content'}
                  defaultValue={createType === 'resolution' ? RESOLUTION_TEMPLATE : ''}
                  key={createType}
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
                  onClick={() => { setShowCreateModal(false); setCreateType('note'); }}
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
        </div>,
        document.body
      )}

      {/* View Document Modal - rendered via portal to escape stacking context */}
      {viewingDocument && createPortal(
        <div className="documents-tab__modal-overlay" onClick={() => setViewingDocument(null)}>
          <div className="documents-tab__view-modal" onClick={(e) => e.stopPropagation()}>
            <div className="documents-tab__modal-header">
              <div>
                <span className="documents-tab__view-badge" data-type={viewingDocument.document_type}>
                  {viewingDocument.document_type}
                </span>
                <h3>{viewingDocument.title}</h3>
              </div>
              <button onClick={() => setViewingDocument(null)}>x</button>
            </div>

            <div className="documents-tab__view-meta">
              <span>{new Date(viewingDocument.updated_at).toLocaleDateString()}</span>
              <span>•</span>
              <span>{viewingDocument.word_count || 0} words</span>
              {viewingDocument.document_type === 'uploaded' && viewingDocument.original_filename && (
                <>
                  <span>•</span>
                  <span>{viewingDocument.original_filename}</span>
                  {viewingDocument.file_size_bytes && (
                    <span>({formatFileSize(viewingDocument.file_size_bytes)})</span>
                  )}
                </>
              )}
              {viewingDocument.policy_areas && viewingDocument.policy_areas.length > 0 && (
                <>
                  <span>•</span>
                  {viewingDocument.policy_areas.map((area, idx) => (
                    <span key={idx} className="documents-tab__tag">{area}</span>
                  ))}
                </>
              )}
            </div>

            <div className="documents-tab__view-content">
              {viewingDocument.content ? (
                <div
                  className="markdown-content"
                  dangerouslySetInnerHTML={{
                    __html: marked.parse(
                      viewingDocument.content.replace(/^```[\w]*\n?/, '').replace(/\n?```\s*$/, '')
                    ) as string,
                  }}
                />
              ) : (
                <p className="documents-tab__view-empty">No content</p>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* Document Generator Wizard */}
      <DocumentGeneratorWizard
        isOpen={showGeneratorWizard}
        onClose={() => setShowGeneratorWizard(false)}
        onDocumentGenerated={() => {
          fetchDocuments({
            document_type: filterType !== 'all' ? filterType : undefined,
            search: searchQuery || undefined,
          });
        }}
      />
    </div>
  );
};
