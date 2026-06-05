// frontend/src/components/amendator/document_viewer.tsx
import { useTranslation } from 'react-i18next';
import './document_viewer.css';
import { LegalText } from '../shared/legal_text';

interface DocumentViewerProps {
  selectedText?: string;
  loadedDocument?: LoadedDocument | null;
}

export interface LoadedDocument {
  document_id: string;
  filename: string;
  text: string;
  metadata: {
    title?: string;
    celex?: string;
    [key: string]: any;
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
}

export const DocumentViewer = ({ selectedText, loadedDocument }: DocumentViewerProps) => {
  const { t } = useTranslation();
  // If no document loaded, show empty state
  if (!loadedDocument) {
    return (
      <div className="document-viewer">
        <div className="document-viewer__content">
          <div className="document-viewer__empty">
            <span className="document-viewer__empty-icon mdi mdi-file-document-outline"></span>
            <p className="document-viewer__empty-text">{t('amendatorExtras.noDocLoaded')}</p>
            <p className="document-viewer__empty-hint">
              {t('amendator.eurlex.hint')}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // If selected text, show it
  if (selectedText) {
    return (
      <div className="document-viewer">
        <div className="document-viewer__content">
          <div className="document-viewer__selected">
            <h3 className="document-viewer__selected-title">{t('amendatorExtras.selectedText')}</h3>
            <div className="document-viewer__selected-content">{selectedText}</div>
          </div>
        </div>
      </div>
    );
  }

  // Display loaded document
  const articles = loadedDocument.structure?.legislative_structure?.articles || [];
  const recitals = loadedDocument.structure?.legislative_structure?.recitals || [];
  const title = loadedDocument.metadata.title || loadedDocument.filename;

  return (
    <div className="document-viewer">
      <div className="document-viewer__content">
        <h1 className="document-viewer__doc-title">{title}</h1>

        {loadedDocument.metadata.celex && (
          <div className="document-viewer__metadata">
            <span className="document-viewer__metadata-label">{t('amendatorExtras.celexLabel')}</span>
            <span className="document-viewer__metadata-value">{loadedDocument.metadata.celex}</span>
          </div>
        )}

        {/* Display Recitals if available */}
        {recitals.length > 0 && (
          <div className="document-viewer__recitals">
            <h2 className="document-viewer__section-title">{t('amendatorExtras.recitalsLabel')}</h2>
            {recitals.map((recital) => (
              <div key={recital.number} className="document-viewer__recital">
                <span className="document-viewer__recital-number">({recital.number})</span>
                <LegalText
                  text={recital.text}
                  celex={loadedDocument.metadata.celex}
                  className="document-viewer__recital-text"
                />
              </div>
            ))}
          </div>
        )}

        {/* Display Articles if available */}
        {articles.length > 0 ? (
          articles.map((article) => (
            <div key={article.number} className="document-viewer__article">
              <h3 className="document-viewer__article-title">
                Article {article.number}
              </h3>
              <LegalText
                text={article.full_text || article.text}
                celex={loadedDocument.metadata.celex}
                className="document-viewer__paragraph"
              />
            </div>
          ))
        ) : (
          /* Display plain text if no structure detected */
          <div className="document-viewer__plain-text">
            {loadedDocument.text.split('\n\n').map((paragraph, idx) => (
              <LegalText
                key={idx}
                text={paragraph}
                celex={loadedDocument.metadata.celex}
                className="document-viewer__paragraph"
              />
            ))}
          </div>
        )}

        <div className="document-viewer__footer">
          <p className="document-viewer__footer-text">
            Document loaded: {loadedDocument.filename}
          </p>
        </div>
      </div>
    </div>
  );
};
