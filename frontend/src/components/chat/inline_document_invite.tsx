// frontend/src/components/chat/inline_document_invite.tsx
//
// Compact "drop a document" invitation rendered in the chat empty state.
// Companion move: Brubru offers to read a draft, position paper, or
// briefing without waiting for the user to find the sidebar uploader.
//
// Pre-user variant: sign-up CTA (real upload requires auth).
// Authenticated variant: real file picker + drag-and-drop + POST to
//   /api/documents/upload, then bubble the document_id up to main_page.

import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/use_auth';
import { trackPreUserEvent } from '../../services/preuser_tracker';
import './inline_document_invite.css';

const API_BASE_URL =
  import.meta.env?.VITE_API_URL ||
  (window as any).REACT_APP_API_URL ||
  'http://localhost:8000';

const ACCEPTED_FORMATS = '.pdf,.docx,.doc';
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB
const PRE_USER_ID_KEY = 'brubru_preuser_id';

interface InlineDocumentInviteProps {
  /** Called with the new document_id when a real upload succeeds. */
  onUpload?: (documentId: string, file: File) => void;
}

const getPreUserId = (): string => {
  let id = localStorage.getItem(PRE_USER_ID_KEY);
  if (!id) {
    id = (window.crypto?.randomUUID?.() as string) || `${Date.now()}-${Math.random()}`;
    localStorage.setItem(PRE_USER_ID_KEY, id);
  }
  return id;
};

const formatBytes = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export const InlineDocumentInvite = ({ onUpload }: InlineDocumentInviteProps) => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [justUploaded, setJustUploaded] = useState<{ name: string; size: number } | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const goSignup = () => {
    trackPreUserEvent(getPreUserId(), 'doc_invite_clicked');
    navigate('/signup');
  };

  const triggerPicker = () => {
    fileInputRef.current?.click();
  };

  const uploadOne = async (file: File) => {
    if (file.size > MAX_FILE_SIZE) {
      setErrorMessage(`${file.name} is too large (max 10 MB).`);
      return;
    }
    setErrorMessage(null);
    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const token = useAuth.getState().token;
      const response = await fetch(`${API_BASE_URL}/api/documents/upload`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        body: formData,
      });
      if (!response.ok) {
        setErrorMessage(`Upload failed for ${file.name}.`);
        return;
      }
      const data = await response.json();
      setJustUploaded({ name: file.name, size: file.size });
      if (onUpload && data.document_id) {
        onUpload(data.document_id, file);
      }
    } catch (e) {
      console.error('Inline upload failed:', e);
      setErrorMessage('Upload failed. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    // Upload one file at a time; users typically drop a single doc here.
    void uploadOne(files[0]);
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isAuthenticated || isUploading) return;
    setIsDragging(true);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (!isAuthenticated) {
      goSignup();
      return;
    }
    if (isUploading) return;
    handleFiles(e.dataTransfer.files);
  };

  // Pre-user state: sign-up CTA
  if (!isAuthenticated) {
    return (
      <button
        type="button"
        className="inline-doc-invite inline-doc-invite--preuser"
        onClick={goSignup}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        title="Sign up to upload a document"
      >
        <span className="mdi mdi-file-upload-outline inline-doc-invite__icon" aria-hidden="true" />
        <span className="inline-doc-invite__body">
          <span className="inline-doc-invite__title">
            Got a draft, position paper, or briefing?
          </span>
          <span className="inline-doc-invite__subtitle">
            Sign up free and I will read your PDF and find the EU-law touchpoints.
          </span>
        </span>
        <span className="mdi mdi-arrow-right inline-doc-invite__arrow" aria-hidden="true" />
      </button>
    );
  }

  // Authenticated, post-upload success state
  if (justUploaded) {
    return (
      <div className="inline-doc-invite inline-doc-invite--success" role="status">
        <span className="mdi mdi-check-circle inline-doc-invite__icon" aria-hidden="true" />
        <span className="inline-doc-invite__body">
          <span className="inline-doc-invite__title">
            Got it. {justUploaded.name} is loaded.
          </span>
          <span className="inline-doc-invite__subtitle">
            {formatBytes(justUploaded.size)}. Ask me anything about it and I will reference it in my answer.
          </span>
        </span>
      </div>
    );
  }

  // Authenticated default: drop zone
  return (
    <div
      className={`inline-doc-invite inline-doc-invite--authed ${isDragging ? 'inline-doc-invite--dragging' : ''} ${isUploading ? 'inline-doc-invite--uploading' : ''}`}
      onClick={triggerPicker}
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          triggerPicker();
        }
      }}
      aria-label="Drop a document for Brubru to read"
    >
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_FORMATS}
        className="inline-doc-invite__hidden-input"
        onChange={(e) => handleFiles(e.target.files)}
        disabled={isUploading}
      />
      <span className="mdi mdi-file-upload-outline inline-doc-invite__icon" aria-hidden="true" />
      <span className="inline-doc-invite__body">
        <span className="inline-doc-invite__title">
          {isUploading
            ? 'Reading your document...'
            : 'Got a draft, position paper, or briefing?'}
        </span>
        <span className="inline-doc-invite__subtitle">
          {isUploading
            ? 'One moment.'
            : 'Drop a PDF or DOCX here and I will reference it in my next answer.'}
        </span>
        {errorMessage && (
          <span className="inline-doc-invite__error">{errorMessage}</span>
        )}
      </span>
      {!isUploading && (
        <span className="inline-doc-invite__cta">Browse files</span>
      )}
    </div>
  );
};
