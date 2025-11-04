// frontend/src/components/amendator/document_viewer.tsx
import './document_viewer.css';

interface DocumentViewerProps {
  selectedText?: string;
}

export const DocumentViewer = ({ selectedText }: DocumentViewerProps) => {
  // Placeholder legislative text (will be replaced with actual XML parsing later)
  const placeholderDocument = {
    title: 'Regulation (EU) 2024/XXX',
    articles: [
      {
        number: '1',
        title: 'Subject matter',
        paragraphs: [
          'This Regulation establishes rules concerning...',
          'It applies to all Member States and their respective authorities.',
        ],
      },
      {
        number: '2',
        title: 'Definitions',
        paragraphs: [
          'For the purposes of this Regulation, the following definitions apply:',
        ],
        points: [
          '(a) "competent authority" means...',
          '(b) "data subject" means...',
          '(c) "processing" means...',
        ],
      },
      {
        number: '3',
        title: 'General obligations',
        paragraphs: [
          'Member States shall ensure that...',
          'The Commission shall adopt delegated acts in accordance with Article 15.',
        ],
      },
    ],
  };

  return (
    <div className="document-viewer">
      <div className="document-viewer__content">
        {!selectedText ? (
          <>
            <h1 className="document-viewer__doc-title">{placeholderDocument.title}</h1>
            {placeholderDocument.articles.map((article) => (
              <div key={article.number} className="document-viewer__article">
                <h3 className="document-viewer__article-title">
                  Article {article.number} - {article.title}
                </h3>
                {article.paragraphs.map((paragraph, idx) => (
                  <p key={idx} className="document-viewer__paragraph">
                    {paragraph}
                  </p>
                ))}
                {article.points && (
                  <ul className="document-viewer__points">
                    {article.points.map((point, idx) => (
                      <li key={idx} className="document-viewer__point">
                        {point}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
            <div className="document-viewer__placeholder">
              <p>Click on any amendable element to start editing.</p>
              <p className="document-viewer__placeholder-hint">
                XML parsing and click-to-amend functionality coming soon!
              </p>
            </div>
          </>
        ) : (
          <div className="document-viewer__selected">
            <h3 className="document-viewer__selected-title">Selected Text</h3>
            <div className="document-viewer__selected-content">{selectedText}</div>
          </div>
        )}
      </div>
    </div>
  );
};
