// EUR-Lex URL Input Component
import { useState } from 'react';
import './eurlex_url_input.css';

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
        type: 'recital' | 'article' | 'article_title' | 'point' | 'paragraph' | 'subparagraph' | 'chapter';
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

export const EURLexURLInput = ({ onDocumentFetched }: EURLexURLInputProps) => {
  const [url, setUrl] = useState('');
  const [isFetching, setIsFetching] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

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
      const response = await fetch('http://localhost:8000/api/documents/fetch-eurlex', {
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
          {isFetching ? 'Fetching...' : success ? '✓ Loaded!' : 'Load Document'}
        </button>
      </div>

      {error && (
        <div className="eurlex-url-input__error">
          <span className="eurlex-url-input__error-icon">⚠️</span>
          {error}
        </div>
      )}

      {success && (
        <div className="eurlex-url-input__success">
          <span className="eurlex-url-input__success-icon">✓</span>
          Document loaded successfully!
        </div>
      )}

      <div className="eurlex-url-input__examples">
        <p className="eurlex-url-input__examples-title">Example URLs:</p>
        <ul className="eurlex-url-input__examples-list">
          <li>
            <button
              className="eurlex-url-input__example-link"
              onClick={() => setUrl('https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689')}
            >
              AI Act (Artificial Intelligence Act)
            </button>
          </li>
          <li>
            <button
              className="eurlex-url-input__example-link"
              onClick={() => setUrl('https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679')}
            >
              GDPR (General Data Protection Regulation)
            </button>
          </li>
        </ul>
      </div>
    </div>
  );
};
