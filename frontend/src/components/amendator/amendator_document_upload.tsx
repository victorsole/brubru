// Amendator Document Upload Component
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/use_auth';
import './amendator_document_upload.css';

interface AmendatorDocumentUploadProps {
  onDocumentUploaded: (document: UploadedDocument) => void;
}

export interface UploadedDocument {
  document_id: string;
  filename: string;
  text: string;
  metadata: any;
  structure?: any;
  quality: string;
}

export const AmendatorDocumentUpload = ({ onDocumentUploaded }: AmendatorDocumentUploadProps) => {
  const { t } = useTranslation();
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState('');
  const [uploadProgress, setUploadProgress] = useState<{ [key: string]: number }>({});

  // API base URL - configure this in your environment
  const API_BASE_URL = import.meta.env?.VITE_API_URL || (window as any).REACT_APP_API_URL || 'http://localhost:8000';

  const acceptedFileTypes = {
    'application/pdf': ['.pdf'],
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    'application/msword': ['.doc'],
  };

  const maxFileSize = 10 * 1024 * 1024; // 10MB

  const handleFileSelect = (files: FileList | null) => {
    if (!files) return;

    const validFiles: File[] = [];
    const errors: string[] = [];

    Array.from(files).forEach((file) => {
      // Validate file type
      if (!Object.keys(acceptedFileTypes).includes(file.type)) {
        errors.push(t('amendator.upload.errorUnsupported', { name: file.name }));
        return;
      }

      // Validate file size
      if (file.size > maxFileSize) {
        errors.push(t('amendator.upload.errorTooLarge', { name: file.name }));
        return;
      }

      validFiles.push(file);
    });

    if (errors.length > 0) {
      setError(errors.join('\n'));
    } else {
      setError('');
    }

    setSelectedFiles((prev) => [...prev, ...validFiles]);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFileSelect(e.dataTransfer.files);
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) {
      setError(t('amendator.upload.errorSelectFile'));
      return;
    }

    setIsUploading(true);
    setError('');

    try {
      for (const file of selectedFiles) {
        const formData = new FormData();
        formData.append('file', file);

        // Upload file
        const token = useAuth.getState().token;
        const uploadResponse = await fetch(`${API_BASE_URL}/api/documents/upload`, {
          method: 'POST',
          headers: {
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
          },
          body: formData,
        });

        if (!uploadResponse.ok) {
          const errorData = await uploadResponse.json();
          throw new Error(errorData.detail || t('amendator.upload.errorFailed'));
        }

        const uploadedDoc = await uploadResponse.json();

        // Fetch processed content
        const contentResponse = await fetch(
          `${API_BASE_URL}/api/documents/storage/${uploadedDoc.document_id}/content`
        );

        if (!contentResponse.ok) {
          throw new Error(t('amendator.upload.errorFetchContent', 'Failed to fetch document content'));
        }

        const content: UploadedDocument = await contentResponse.json();

        // Notify parent component
        onDocumentUploaded(content);

        // Update progress
        setUploadProgress((prev) => ({
          ...prev,
          [file.name]: 100
        }));
      }

      // Clear selected files after successful upload
      setSelectedFiles([]);
      setUploadProgress({});

    } catch (err) {
      console.error('Error uploading documents:', err);
      setError(err instanceof Error ? err.message : t('amendator.upload.errorFailed'));
    } finally {
      setIsUploading(false);
    }
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="amendator-document-upload">
      <div className="amendator-document-upload__header">
        <h3 className="amendator-document-upload__title">{t('amendator.upload.title')}</h3>
        <p className="amendator-document-upload__hint">{t('amendator.upload.hint')}</p>
      </div>

      {/* Drag & Drop Zone */}
      <div
        className={`amendator-document-upload__dropzone ${isDragging ? 'amendator-document-upload__dropzone--dragging' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="amendator-document-upload__dropzone-content">
          <span className="amendator-document-upload__icon mdi mdi-file-document-outline"></span>
          <p className="amendator-document-upload__dropzone-text">{t('amendator.upload.dragDrop')}</p>
          <p className="amendator-document-upload__dropzone-or">{t('amendator.upload.or')}</p>
          <label className="amendator-document-upload__file-label button button-secondary button-sm">
            {t('amendator.upload.browse')}
            <input
              type="file"
              className="amendator-document-upload__file-input"
              multiple
              accept=".pdf,.doc,.docx"
              onChange={(e) => handleFileSelect(e.target.files)}
              disabled={isUploading}
            />
          </label>
        </div>
      </div>

      {/* Selected Files */}
      {selectedFiles.length > 0 && (
        <div className="amendator-document-upload__files">
          <h4 className="amendator-document-upload__files-title">
            {t('amendator.upload.selectedFiles', { count: selectedFiles.length })}
          </h4>
          <ul className="amendator-document-upload__files-list">
            {selectedFiles.map((file, index) => (
              <li key={index} className="amendator-document-upload__file-item">
                <div className="amendator-document-upload__file-info">
                  <span className="amendator-document-upload__file-name">{file.name}</span>
                  <span className="amendator-document-upload__file-size">
                    {(file.size / 1024).toFixed(1)} KB
                  </span>
                </div>
                {!isUploading && (
                  <button
                    className="amendator-document-upload__remove-button"
                    onClick={() => handleRemoveFile(index)}
                  >
                    <span className="mdi mdi-close"></span>
                  </button>
                )}
                {uploadProgress[file.name] && (
                  <div className="amendator-document-upload__progress">
                    <div
                      className="amendator-document-upload__progress-bar"
                      style={{ width: `${uploadProgress[file.name]}%` }}
                    />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="amendator-document-upload__error">
          <span className="amendator-document-upload__error-icon mdi mdi-alert"></span>
          {error}
        </div>
      )}

      {/* Upload Button */}
      {selectedFiles.length > 0 && (
        <button
          className="amendator-document-upload__upload-button button button-primary"
          onClick={handleUpload}
          disabled={isUploading}
        >
          {isUploading ? t('amendator.upload.uploading') : t('amendator.upload.uploadFiles', { count: selectedFiles.length })}
        </button>
      )}
    </div>
  );
};
