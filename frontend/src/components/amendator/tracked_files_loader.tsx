// Tracked Files Loader for Amendator
// Allows users to load documents from their tracked legislative files
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useLegislativeTrains } from '../../hooks/use_legislative_trains';
import type { FetchedDocument } from './eurlex_url_input';
import './tracked_files_loader.css';

const API_BASE = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api`;

interface TrackedFilesLoaderProps {
  onDocumentFetched: (document: FetchedDocument) => void;
}

export const TrackedFilesLoader = ({ onDocumentFetched }: TrackedFilesLoaderProps) => {
  const { t } = useTranslation();
  const { trackedFiles, fetchTrackedFiles, isLoadingTrackedFiles } = useLegislativeTrains();
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetchTrackedFiles();
  }, [fetchTrackedFiles]);

  // The Amendator drafts amendments to files that are still open in the
  // legislative process. Two exclusions:
  //  1. Type: only COD/APP/CNS procedures (or anything with a CELEX) are
  //     amendable. Resolutions (RSP/RSO), own-initiative reports (INI),
  //     delegated/implementing acts (DEA/RPS) and Commission communications
  //     (COM ...) have no amendable text or fetchable CELEX.
  //  2. Stage: already adopted/completed acts are final, so they are not
  //     offered for amendment drafting.
  const AMENDABLE_PROC = /\((?:COD|APP|CNS)\)\s*$/i;
  const FINAL_STATUSES = new Set(['completed', 'adopted', 'withdrawn', 'rejected', 'closed']);
  const amendableFiles = trackedFiles.filter(file =>
    !FINAL_STATUSES.has((file.current_status || '').toLowerCase()) &&
    ((file.celex_numbers && file.celex_numbers.length > 0) ||
      AMENDABLE_PROC.test(file.oeil_procedure_ref || ''))
  );
  const hiddenCount = trackedFiles.length - amendableFiles.length;

  // Filter amendable files by search query
  const filteredFiles = amendableFiles.filter(file =>
    file.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (file.oeil_procedure_ref && file.oeil_procedure_ref.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const handleLoadFile = async (carriageId: string, celexNumbers?: string[]) => {
    setIsLoading(true);
    setSelectedFileId(carriageId);
    setError('');

    try {
      let celex = celexNumbers && celexNumbers.length > 0 ? celexNumbers[0] : null;

      // If no CELEX, try to fetch via backend (OEIL + EUR-Lex SPARQL)
      if (!celex) {
        setError(t('amendator.tracked.lookingUp'));
        const enrichResponse = await fetch(`${API_BASE}/legislative-train/carriages/${carriageId}/enrich-celex`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
        });

        if (enrichResponse.ok) {
          const enrichData = await enrichResponse.json();
          if (enrichData.celex_numbers && enrichData.celex_numbers.length > 0) {
            celex = enrichData.celex_numbers[0];
            setError(''); // Clear the "fetching" message
          } else {
            throw new Error(t('amendator.tracked.errorNoCelex'));
          }
        } else {
          const errorData = await enrichResponse.json().catch(() => ({}));
          throw new Error(errorData.detail || t('amendator.tracked.errorFetchCelex'));
        }
      }

      // Now fetch the document from EUR-Lex
      const url = `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:${celex}`;

      const response = await fetch(`${API_BASE}/documents/fetch-eurlex`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: url,
          format: 'html',
          language: 'EN'
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || t('amendator.eurlex.errorFetch'));
      }

      const document: FetchedDocument = await response.json();
      onDocumentFetched(document);

    } catch (err) {
      console.error('Error loading tracked file:', err);
      setError(err instanceof Error ? err.message : t('amendator.eurlex.errorFetch'));
    } finally {
      setIsLoading(false);
      setSelectedFileId(null);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'adopted':
      case 'completed':
        return 'status--adopted';
      case 'tabled':
      case 'close_to_adoption':
        return 'status--tabled';
      case 'blocked':
        return 'status--blocked';
      case 'withdrawn':
        return 'status--withdrawn';
      default:
        return 'status--announced';
    }
  };

  const formatStatus = (status: string) => {
    return status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  };

  return (
    <div className="tracked-files-loader">
      <div className="tracked-files-loader__header">
        <h3 className="tracked-files-loader__title">{t('amendator.tracked.title')}</h3>
        <p className="tracked-files-loader__hint">{t('amendator.tracked.hint')}</p>
        {hiddenCount > 0 && (
          <p className="tracked-files-loader__hint" style={{ fontSize: '0.8rem', opacity: 0.8, marginTop: '0.35rem' }}>
            {hiddenCount} tracked {hiddenCount === 1 ? 'file is' : 'files are'} not shown: only legislative files still open for amendment appear here. Already-adopted or completed acts, resolutions, delegated acts and communications are excluded.
          </p>
        )}
      </div>

      <div className="tracked-files-loader__search">
        <input
          type="text"
          className="tracked-files-loader__search-input"
          placeholder={t('amendator.tracked.searchPlaceholder')}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      {error && (
        <div className="tracked-files-loader__error">
          <span className="tracked-files-loader__error-icon mdi mdi-alert"></span>
          {error}
        </div>
      )}

      <div className="tracked-files-loader__list">
        {isLoadingTrackedFiles ? (
          <div className="tracked-files-loader__loading">{t('amendator.tracked.loadingTracked')}</div>
        ) : filteredFiles.length === 0 ? (
          <div className="tracked-files-loader__empty">
            {searchQuery ? (
              <p>{t('amendator.tracked.noMatch')}</p>
            ) : (
              <>
                <p>{t('amendator.tracked.noneYet')}</p>
                <p className="tracked-files-loader__empty-hint">{t('amendator.tracked.noneYetHint')}</p>
              </>
            )}
          </div>
        ) : (
          filteredFiles.map((file) => (
            <div
              key={file.id}
              className={`tracked-files-loader__item ${selectedFileId === file.carriage_id ? 'tracked-files-loader__item--selected' : ''}`}
            >
              <div className="tracked-files-loader__item-content">
                <div className="tracked-files-loader__item-header">
                  <span className={`tracked-files-loader__status ${getStatusColor(file.current_status)}`}>
                    {formatStatus(file.current_status)}
                  </span>
                  {file.lead_committee && (
                    <span className="tracked-files-loader__committee">{file.lead_committee}</span>
                  )}
                </div>
                <h4 className="tracked-files-loader__item-title">{file.title}</h4>
                {file.oeil_procedure_ref && (
                  <p className="tracked-files-loader__item-ref">{file.oeil_procedure_ref}</p>
                )}
              </div>
              <button
                className="tracked-files-loader__load-button button button-primary"
                onClick={() => handleLoadFile(file.carriage_id, file.celex_numbers)}
                disabled={isLoading && selectedFileId === file.carriage_id}
              >
                {isLoading && selectedFileId === file.carriage_id ? t('amendator.tracked.loading') : t('amendator.tracked.load')}
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
