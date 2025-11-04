// frontend/src/components/chat/document_upload.tsx
import { useState, useRef } from 'react';
import './document_upload.css';

export interface UploadedFile {
  id: string;
  file: File;
  name: string;
  size: number;
  type: string;
}

export const DocumentUpload = () => {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const acceptedFormats = '.pdf,.docx,.txt,.md,.pptx,.xlsx,.png,.jpg,.jpeg';
  const maxFileSize = 10 * 1024 * 1024; // 10MB

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const handleFiles = (files: FileList | null) => {
    if (!files) return;

    const validFiles: UploadedFile[] = [];

    Array.from(files).forEach((file) => {
      if (file.size > maxFileSize) {
        alert(`File ${file.name} is too large. Maximum size is 10MB.`);
        return;
      }

      validFiles.push({
        id: `${file.name}-${Date.now()}`,
        file,
        name: file.name,
        size: file.size,
        type: file.type,
      });
    });

    setUploadedFiles((prev) => [...prev, ...validFiles]);
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
      <h3 className="document-upload__title">Documents</h3>

      {/* Drag and Drop Area */}
      <div
        className={`document-upload__dropzone ${
          isDragging ? 'document-upload__dropzone--dragging' : ''
        }`}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={triggerFileInput}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="document-upload__input"
          onChange={handleFileInput}
          accept={acceptedFormats}
          multiple
        />
        <div className="document-upload__dropzone-content">
          <p className="document-upload__dropzone-text">
            Drag & drop files here or click to browse
          </p>
          <p className="document-upload__dropzone-formats">
            Supported: PDF, Word, Text, Markdown, PowerPoint, Excel, PNG, JPEG
          </p>
          <p className="document-upload__dropzone-size">Max 10MB per file</p>
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
