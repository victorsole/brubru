// frontend/src/components/amendator/amendment_sidebar.tsx
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { Amendment } from '../../pages/amendator_page';
import { getAmendmentTypeLabel, getStructureLevelLabel } from '../../utils/amendment_formatter';
import Icon from '@mdi/react';
import { mdiCloseCircleOutline } from '@mdi/js';
import { useAuth } from '../../hooks/use_auth';
import './amendment_sidebar.css';
import { uiDateLocale } from '../../i18n/config';

const API_BASE = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api`;

interface AmendmentSidebarProps {
  amendments: Amendment[];
  onSelectAmendment: (amendment: Amendment) => void;
  onDeleteAmendment?: (amendment: Amendment) => void;
  selectedAmendmentId?: string;
  documentId?: string;
}

export const AmendmentSidebar = ({
  amendments,
  onSelectAmendment,
  onDeleteAmendment,
  selectedAmendmentId,
  documentId,
}: AmendmentSidebarProps) => {
  const { t } = useTranslation();
  const [isExporting, setIsExporting] = useState(false);
  const [exportSuccess, setExportSuccess] = useState(false);
  const getStatusClass = (status: Amendment['status']) => {
    switch (status) {
      case 'tabled':
        return 'amendment-grid__status--tabled';
      case 'candidate':
        return 'amendment-grid__status--candidate';
      case 'withdrawn':
        return 'amendment-grid__status--withdrawn';
      default:
        return '';
    }
  };

  const getStatusLabel = (status: Amendment['status']) => {
    switch (status) {
      case 'tabled':
        return t('amendments.tabled');
      case 'candidate':
        return t('amendments.candidate');
      case 'withdrawn':
        return t('amendments.withdrawn');
      default:
        return status;
    }
  };

  const truncateText = (text: string, maxLength: number = 60) => {
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };

  const handleExport = async () => {
    if (!documentId) {
      console.error('No document ID available for export');
      return;
    }

    setIsExporting(true);
    try {
      // Get auth token
      const token = useAuth.getState().token;

      // Call backend export API
      const response = await fetch(`${API_BASE}/amendments/export/${documentId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` }),
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to export amendments');
      }

      // Get the blob from response
      const blob = await response.blob();

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;

      // Extract filename from Content-Disposition header or use default
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = `amendments_${documentId}.docx`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }

      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      // Show success state
      setIsExporting(false);
      setExportSuccess(true);
      setTimeout(() => {
        setExportSuccess(false);
      }, 2000);
    } catch (error) {
      console.error('Error exporting amendments:', error);
      setIsExporting(false);
      // Could add error state here if needed
    }
  };

  return (
    <div className="amendment-grid">
      <div className="amendment-grid__header">
        <h3 className="amendment-grid__title">{t('amendments.title')}</h3>
        <span className="amendment-grid__count">{amendments.length}</span>
      </div>

      {amendments.length === 0 ? (
        <div className="amendment-grid__empty">
          <p>{t('amendments.noAmendments')}</p>
          <p className="amendment-grid__empty-hint">
            {t('amendments.createFirst')}
          </p>
        </div>
      ) : (
        <div className="amendment-grid__list">
          {amendments.map((amendment) => (
            <div
              key={amendment.id}
              className={`amendment-grid__item ${
                amendment.id === selectedAmendmentId ? 'amendment-grid__item--selected' : ''
              }`}
              onClick={() => onSelectAmendment(amendment)}
            >
              <div className="amendment-grid__item-header">
                {/* Group Badge (green background) */}
                {amendment.group && (
                  <span className="amendment-grid__group">{amendment.group}</span>
                )}
                <span className="amendment-grid__position">{amendment.position}</span>
                <span className={`amendment-grid__status ${getStatusClass(amendment.status)}`}>
                  {getStatusLabel(amendment.status)}
                </span>
                {onDeleteAmendment && (
                  <button
                    className="amendment-grid__delete"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteAmendment(amendment);
                    }}
                    title={t('amendatorExtras.deleteAmendment')}
                    aria-label={t('amendatorExtras.deleteAmendment')}
                  >
                    <Icon path={mdiCloseCircleOutline} size={0.65} />
                  </button>
                )}
              </div>

              {/* Amendment Type and Structure Level */}
              <div className="amendment-grid__meta">
                <span className="amendment-grid__type">{getAmendmentTypeLabel(amendment.type)}</span>
                <span className="amendment-grid__separator">•</span>
                <span className="amendment-grid__level">{getStructureLevelLabel(amendment.structureLevel)}</span>
              </div>

              {/* Preview Text */}
              <p className="amendment-grid__preview">
                {truncateText(amendment.proposedText)}
              </p>

              {/* Date */}
              <span className="amendment-grid__date">
                {new Date(amendment.createdAt).toLocaleDateString(uiDateLocale(), {
                  day: '2-digit',
                  month: 'short',
                  year: 'numeric',
                })}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="amendment-grid__actions">
        <button
          className={`amendment-grid__export-button button button-sm ${
            exportSuccess ? 'button-success' : 'button-secondary'
          }`}
          onClick={handleExport}
          disabled={isExporting || amendments.length === 0}
        >
          {isExporting ? t('amendments.exporting') : exportSuccess ? <><span className="mdi mdi-check"></span> {t('amendments.exported')}</> : t('amendments.exportAll')}
        </button>
      </div>
    </div>
  );
};
