// frontend/src/components/admin/shared/admin_export_button.tsx
import { useState } from 'react';
import './admin_export_button.css';

interface AdminExportButtonProps {
  onExport: (format: 'csv' | 'json' | 'xlsx') => Promise<void>;
  disabled?: boolean;
  formats?: ('csv' | 'json' | 'xlsx')[];
}

export const AdminExportButton = ({
  onExport,
  disabled = false,
  formats = ['csv', 'json']
}: AdminExportButtonProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleExport = async (format: 'csv' | 'json' | 'xlsx') => {
    setIsLoading(true);
    try {
      await onExport(format);
      setIsOpen(false);
    } catch (error) {
      console.error('Export failed:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="admin-export-button">
      <button
        className="btn btn--secondary btn--small"
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled || isLoading}
      >
        <span className="mdi mdi-download"></span>
        Export
      </button>

      {isOpen && (
        <div className="admin-export-button__dropdown">
          {formats.map((format) => (
            <button
              key={format}
              className="admin-export-button__option"
              onClick={() => handleExport(format)}
              disabled={isLoading}
            >
              <span className="mdi mdi-file-delimited"></span>
              Export as {format.toUpperCase()}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
