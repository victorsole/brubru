// EUR-Lex URL Input Component
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/use_auth';
import './eurlex_url_input.css';

const API_BASE = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api`;

interface EURLexURLInputProps {
  onDocumentFetched: (document: FetchedDocument) => void;
}

export interface FetchedDocument {
  document_id: string;
  filename: string;
  text: string;
  metadata: {
    celex: string;
    title: string;
    date: string;
    type: string;
    language: string;
    source: string;
  };
  structure?: {
    legislative_structure?: {
      elements?: Array<{
        type: 'recital' | 'article' | 'article_title' | 'article_intro' | 'point' | 'paragraph' | 'subparagraph' | 'chapter';
        number?: string;
        letter?: string;
        roman?: string;
        text: string;
        level: number;
        article_number?: string;
        point_number?: string;
        paragraph_letter?: string;
        title?: string;
      }>;
      articles?: Array<{
        number: string;
        text: string;
        full_text: string;
      }>;
      recitals?: Array<{
        number: string;
        text: string;
      }>;
      chapters?: Array<{
        number: string;
        text: string;
      }>;
    };
  };
  quality: string;
}

interface FeaturedExample {
  celex: string | null;
  eurlex_url: string;
  title: string;
  description: string | null;
  source: string | null;
  position: number;
}

interface MyAmendableFile {
  carriage_id: string;
  title: string;
  celex: string | null;
  procedure_ref: string | null;
  eurlex_url: string | null;
  text_type: string | null;
}

export const EURLexURLInput = ({ onDocumentFetched }: EURLexURLInputProps) => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [url, setUrl] = useState('');
  const [isFetching, setIsFetching] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [examples, setExamples] = useState<FeaturedExample[]>([]);
  const [examplesLoading, setExamplesLoading] = useState(true);
  const [examplesError, setExamplesError] = useState('');
  const [myFiles, setMyFiles] = useState<MyAmendableFile[]>([]);

  // "Amend a file you track" — the user's amendable tracked dossiers (Phase 3 bridge).
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/amendator/my-amendable-files?limit=12`,
          { headers: { Authorization: `Bearer ${token}` } });
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) setMyFiles((data || []).filter((f: MyAmendableFile) => f.eurlex_url));
      } catch { /* silent: this section just won't render */ }
    })();
    return () => { cancelled = true; };
  }, [token]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/amendator/featured-examples?limit=10`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) setExamples(data.items || []);
      } catch (e) {
        if (!cancelled) setExamplesError(e instanceof Error ? e.message : 'Failed to load examples');
      } finally {
        if (!cancelled) setExamplesLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const handleFetch = async () => {
    if (!url.trim()) {
      setError(t('amendator.eurlex.errorEnterUrl'));
      return;
    }

    setIsFetching(true);
    setError('');
    setSuccess(false);

    try {
      // Fetch document from EUR-Lex
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

      // Notify parent component
      onDocumentFetched(document);

      setSuccess(true);
      setUrl('');

      // Reset success message after 3 seconds
      setTimeout(() => {
        setSuccess(false);
      }, 3000);

    } catch (err) {
      console.error('Error fetching EUR-Lex document:', err);
      setError(err instanceof Error ? err.message : t('amendator.eurlex.errorFetch'));
    } finally {
      setIsFetching(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleFetch();
    }
  };

  return (
    <div className="eurlex-url-input">
      <div className="eurlex-url-input__header">
        <h3 className="eurlex-url-input__title">{t('amendator.eurlex.title')}</h3>
        <p className="eurlex-url-input__hint">{t('amendator.eurlex.hint')}</p>
      </div>

      <div className="eurlex-url-input__field">
        <input
          type="text"
          className="eurlex-url-input__input"
          placeholder="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={isFetching}
        />
        <button
          className={`eurlex-url-input__button button ${success ? 'button-success' : 'button-primary'}`}
          onClick={handleFetch}
          disabled={isFetching || !url.trim()}
        >
          {isFetching ? t('amendator.eurlex.fetching') : success ? <><span className="mdi mdi-check"></span> {t('amendator.eurlex.loaded')}</> : t('amendator.eurlex.loadDocument')}
        </button>
      </div>

      {error && (
        <div className="eurlex-url-input__error">
          <span className="eurlex-url-input__error-icon mdi mdi-alert"></span>
          {error}
        </div>
      )}

      {success && (
        <div className="eurlex-url-input__success">
          <span className="eurlex-url-input__success-icon mdi mdi-check-circle"></span>
          {t('amendator.eurlex.loadedSuccess')}
        </div>
      )}

      {myFiles.length > 0 && (
        <div className="eurlex-url-input__examples eurlex-url-input__myfiles">
          <p className="eurlex-url-input__examples-title">
            <span className="mdi mdi-bookmark-check"></span> {t('amendator.eurlex.myFiles', 'Amend a file you track')}
          </p>
          <ul className="eurlex-url-input__examples-list">
            {myFiles.map((f) => (
              <li key={f.carriage_id}>
                <button
                  className="eurlex-url-input__example-link"
                  onClick={() => f.eurlex_url && setUrl(f.eurlex_url)}
                  title={f.procedure_ref || f.celex || ''}
                >
                  {f.title}
                </button>
                {(f.celex || f.procedure_ref) && (
                  <span className="eurlex-url-input__example-desc">{f.celex || f.procedure_ref}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="eurlex-url-input__examples">
        <p className="eurlex-url-input__examples-title">{t('amendator.eurlex.hotFiles')}</p>
        {examplesLoading && (
          <p className="eurlex-url-input__examples-loading">{t('amendator.eurlex.examplesLoading')}</p>
        )}
        {examplesError && !examplesLoading && (
          <p className="eurlex-url-input__examples-error">
            <span className="mdi mdi-alert"></span> {t('amendator.eurlex.examplesError', { error: examplesError })}
          </p>
        )}
        {!examplesLoading && !examplesError && examples.length === 0 && (
          <p className="eurlex-url-input__examples-empty">{t('amendator.eurlex.examplesEmpty')}</p>
        )}
        {!examplesLoading && examples.length > 0 && (
          <ul className="eurlex-url-input__examples-list">
            {examples.map((ex) => (
              <li key={ex.eurlex_url}>
                <button
                  className="eurlex-url-input__example-link"
                  onClick={() => setUrl(ex.eurlex_url)}
                  title={ex.description || ex.eurlex_url}
                >
                  {ex.title}
                </button>
                {ex.description && (
                  <span className="eurlex-url-input__example-desc">{ex.description}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
