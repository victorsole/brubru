// frontend/src/components/chat/document_upload.tsx
import { useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import './document_upload.css';

export interface UploadedFile {
  id: string;
  file: File;
  name: string;
  size: number;
  type: string;
}

interface DocumentUploadProps {
  onUpload?: (documentId: string, file: File) => void;
}

export const DocumentUpload = ({ onUpload }: DocumentUploadProps = {}) => {
  const { t } = useTranslation();
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const API_BASE_URL = import.meta.env?.VITE_API_URL || (window as any).REACT_APP_API_URL || 'http://localhost:8000';
  const acceptedFormats = '.pdf,.docx,.doc';
  const maxFileSize = 10 * 1024 * 1024; // 10MB

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const handleFiles = async (files: FileList | null) => {
    if (!files) return;

    setIsUploading(true);

    try {
      for (const file of Array.from(files)) {
        // Validate file size
        if (file.size > maxFileSize) {
          alert(`${file.name} ${t('docs.tooLarge')}`);
          continue;
        }

        // Upload to backend
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE_URL}/api/uploads/upload`, {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          alert(`${t('docs.uploadFailed') || 'Upload failed'}: ${file.name}`);
          continue;
        }

        const data = await response.json();

        // Add to local state
        const uploadedFile: UploadedFile = {
          id: data.document_id,
          file,
          name: file.name,
          size: file.size,
          type: file.type,
        };

        setUploadedFiles((prev) => [...prev, uploadedFile]);

        // Notify parent component
        if (onUpload) {
          onUpload(data.document_id, file);
        }
      }
    } catch (error) {
      console.error('Failed to upload files:', error);
      alert(t('docs.uploadFailed') || 'Failed to upload files');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files);
  };

  const handleRemoveFile = (fileId: string) => {
    setUploadedFiles((prev) => prev.filter((f) => f.id !== fileId));
  };

  const triggerFileInput = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="document-upload">
      <h3 className="document-upload__title">{t('docs.title')}</h3>

      {/* Brubru Mascot - Shows empty bag when no documents, full bag when documents uploaded */}
      <div className="document-upload__mascot">
        <img
          src={uploadedFiles.length === 0 ? '/assets/brubru_nochips.png' : '/assets/brubru_mainlogo.png'}
          alt={uploadedFiles.length === 0 ? t('docs.noDocuments') : t('docs.documentsUploaded')}
          className="document-upload__mascot-image"
        />
      </div>

      {/* Drag and Drop Area */}
      <div
        className={`document-upload__dropzone ${
          isDragging ? 'document-upload__dropzone--dragging' : ''
        } ${isUploading ? 'document-upload__dropzone--disabled' : ''}`}
        onDragEnter={isUploading ? undefined : handleDragEnter}
        onDragOver={isUploading ? undefined : handleDragOver}
        onDragLeave={isUploading ? undefined : handleDragLeave}
        onDrop={isUploading ? undefined : handleDrop}
        onClick={isUploading ? undefined : triggerFileInput}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="document-upload__input"
          onChange={handleFileInput}
          accept={acceptedFormats}
          multiple
          disabled={isUploading}
        />
        <div className="document-upload__dropzone-content">
          {isUploading ? (
            <p className="document-upload__dropzone-text">
              {t('docs.uploading') || 'Uploading...'}
            </p>
          ) : (
            <>
              <p className="document-upload__dropzone-text">
                {t('docs.dragDrop')}
              </p>
              <p className="document-upload__dropzone-formats">
                {t('docs.supported')} PDF, DOCX, DOC
              </p>
              <p className="document-upload__dropzone-size">{t('docs.maxSize')} 10MB</p>
            </>
          )}
        </div>
      </div>

      {/* Uploaded Files List */}
      {uploadedFiles.length > 0 && (
        <div className="document-upload__list">
          {uploadedFiles.map((file) => (
            <div key={file.id} className="document-upload__file">
              <div className="document-upload__file-info">
                <span className="document-upload__file-name">{file.name}</span>
                <span className="document-upload__file-size">
                  {formatFileSize(file.size)}
                </span>
              </div>
              <button
                className="document-upload__file-remove"
                onClick={() => handleRemoveFile(file.id)}
                aria-label={`Remove ${file.name}`}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
