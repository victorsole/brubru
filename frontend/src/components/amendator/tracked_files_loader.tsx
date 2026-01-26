// Tracked Files Loader for Amendator
// Allows users to load documents from their tracked legislative files
import { useState, useEffect } from 'react';
import { useLegislativeTrains } from '../../hooks/use_legislative_trains';
import type { FetchedDocument } from './eurlex_url_input';
import './tracked_files_loader.css';

const API_BASE = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api`;

interface TrackedFilesLoaderProps {
  onDocumentFetched: (document: FetchedDocument) => void;
}

export const TrackedFilesLoader = ({ onDocumentFetched }: TrackedFilesLoaderProps) => {
  const { trackedFiles, fetchTrackedFiles, isLoadingTrackedFiles } = useLegislativeTrains();
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetchTrackedFiles();
  }, [fetchTrackedFiles]);

  // Filter tracked files by search query
  const filteredFiles = trackedFiles.filter(file =>
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
        setError('Looking up document in EUR-Lex...');
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
            throw new Error('No CELEX number found for this legislation. It may be too new or not yet published in EUR-Lex.');
          }
        } else {
          const errorData = await enrichResponse.json().catch(() => ({}));
          throw new Error(errorData.detail || 'Failed to fetch CELEX number from OEIL');
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
        throw new Error(errorData.detail || 'Failed to fetch document from EUR-Lex');
      }

      const document: FetchedDocument = await response.json();
      onDocumentFetched(document);

    } catch (err) {
      console.error('Error loading tracked file:', err);
      setError(err instanceof Error ? err.message : 'Failed to load document');
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
        <h3 className="tracked-files-loader__title">Load from Tracked Files</h3>
        <p className="tracked-files-loader__hint">
          Select a file from your tracked legislation to start drafting amendments
        </p>
      </div>

      <div className="tracked-files-loader__search">
        <input
          type="text"
          className="tracked-files-loader__search-input"
          placeholder="Search tracked files..."
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
          <div className="tracked-files-loader__loading">Loading tracked files...</div>
        ) : filteredFiles.length === 0 ? (
          <div className="tracked-files-loader__empty">
            {searchQuery ? (
              <p>No tracked files match your search.</p>
            ) : (
              <>
                <p>You haven't tracked any legislative files yet.</p>
                <p className="tracked-files-loader__empty-hint">
                  Track files in My EU Bubble → My Tracked Files to see them here.
                </p>
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
                {isLoading && selectedFileId === file.carriage_id ? 'Loading...' : 'Load'}
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
