// EUR-Lex URL Input Component
import { useEffect, useState } from 'react';
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

export const EURLexURLInput = ({ onDocumentFetched }: EURLexURLInputProps) => {
  const [url, setUrl] = useState('');
  const [isFetching, setIsFetching] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [examples, setExamples] = useState<FeaturedExample[]>([]);
  const [examplesLoading, setExamplesLoading] = useState(true);
  const [examplesError, setExamplesError] = useState('');

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
      setError('Please enter a EUR-Lex URL');
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
        throw new Error(errorData.detail || 'Failed to fetch document');
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
      setError(err instanceof Error ? err.message : 'Failed to fetch document');
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
        <h3 className="eurlex-url-input__title">Load from EUR-Lex</h3>
        <p className="eurlex-url-input__hint">
          Paste a EUR-Lex URL to load legislative text
        </p>
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
          {isFetching ? 'Fetching...' : success ? <><span className="mdi mdi-check"></span> Loaded!</> : 'Load Document'}
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
          Document loaded successfully!
        </div>
      )}

      <div className="eurlex-url-input__examples">
        <p className="eurlex-url-input__examples-title">Hot files this week:</p>
        {examplesLoading && (
          <p className="eurlex-url-input__examples-loading">Loading…</p>
        )}
        {examplesError && !examplesLoading && (
          <p className="eurlex-url-input__examples-error">
            <span className="mdi mdi-alert"></span> Could not load featured examples ({examplesError}).
          </p>
        )}
        {!examplesLoading && !examplesError && examples.length === 0 && (
          <p className="eurlex-url-input__examples-empty">No featured examples yet — paste any EUR-Lex URL above.</p>
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
