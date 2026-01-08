// frontend/src/components/amendator/two_column_layout.tsx
import React, { useState, useEffect } from 'react';
import Icon from '@mdi/react';
import { mdiDeleteOutline, mdiPlusBoxOutline, mdiAlphaM } from '@mdi/js';
import type { LoadedDocument } from './document_viewer';
import { EURLexURLInput } from './eurlex_url_input';
import type { FetchedDocument } from './eurlex_url_input';
import { AmendatorDocumentUpload } from './amendator_document_upload';
import type { UploadedDocument } from './amendator_document_upload';
import './two_column_layout.css';

export interface LegislativeElement {
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
}

export interface CellAmendment {
  elementIndex: number;
  elementType: string;
  elementNumber: string;
  amendmentType: 'suppression' | 'addition' | 'modification';
  originalText: string;
  proposedText: string;
  position: string;
  insertAfter?: number;
}

interface TwoColumnLayoutProps {
  loadedDocument: LoadedDocument | null;
  onDocumentLoaded: (document: LoadedDocument) => void;
  onElementSelected?: (element: LegislativeElement, index: number) => void;
  onAmendmentsChange?: (amendments: Map<number, CellAmendment>) => void;
}

export const TwoColumnLayout = ({
  loadedDocument,
  onDocumentLoaded,
  onElementSelected,
  onAmendmentsChange,
}: TwoColumnLayoutProps) => {
  const [showDocumentLoader, setShowDocumentLoader] = useState(!loadedDocument);
  const [elements, setElements] = useState<LegislativeElement[]>([]);
  const [amendments, setAmendments] = useState<Map<number, CellAmendment>>(new Map());
  const [editingCell, setEditingCell] = useState<number | null>(null);
  const [hoveredCell, setHoveredCell] = useState<number | null>(null);

  // Extract legislative elements from loaded document
  useEffect(() => {
    if (loadedDocument?.structure?.legislative_structure?.elements) {
      setElements(loadedDocument.structure.legislative_structure.elements);
    } else {
      setElements([]);
    }
  }, [loadedDocument]);

  // Notify parent when amendments change
  useEffect(() => {
    if (onAmendmentsChange) {
      onAmendmentsChange(amendments);
    }
  }, [amendments, onAmendmentsChange]);

  const handleDocumentFetched = (document: FetchedDocument) => {
    const loadedDoc: LoadedDocument = {
      document_id: document.document_id,
      filename: document.filename,
      text: document.text,
      metadata: document.metadata,
      structure: document.structure,
    };
    onDocumentLoaded(loadedDoc);
    setShowDocumentLoader(false);
  };

  const handleDocumentUploaded = (document: UploadedDocument) => {
    const loadedDoc: LoadedDocument = {
      document_id: document.document_id,
      filename: document.filename,
      text: document.text,
      metadata: document.metadata,
      structure: document.structure,
    };
    onDocumentLoaded(loadedDoc);
    setShowDocumentLoader(false);
  };

  const getElementPrefix = (element: LegislativeElement): string => {
    switch (element.type) {
      case 'recital':
        return `(${element.number})`;
      case 'article':
        return `Article ${element.number}`;
      case 'point':
        return `${element.number}.`;
      case 'paragraph':
        return `(${element.letter})`;
      case 'subparagraph':
        return `(${element.roman})`;
      case 'chapter':
        return '';
      default:
        return '';
    }
  };

  const getElementPosition = (element: LegislativeElement): string => {
    if (element.type === 'recital') {
      return `Recital ${element.number}`;
    } else if (element.type === 'article') {
      return `Article ${element.number}`;
    } else if (element.type === 'article_title') {
      return `Article ${element.article_number}, title`;
    } else if (element.type === 'point') {
      return `Article ${element.article_number}, point ${element.number}`;
    } else if (element.type === 'paragraph') {
      if (element.point_number) {
        return `Article ${element.article_number}, point ${element.point_number}, paragraph (${element.letter})`;
      } else {
        return `Article ${element.article_number}, paragraph (${element.letter})`;
      }
    } else if (element.type === 'subparagraph') {
      return `Subparagraph (${element.roman})`;
    } else if (element.type === 'chapter') {
      return `Chapter ${element.number}`;
    }
    return 'Unknown position';
  };

  const handleSuppression = (index: number) => {
    const element = elements[index];
    const newAmendments = new Map(amendments);

    const amendment: CellAmendment = {
      elementIndex: index,
      elementType: element.type,
      elementNumber: element.number || element.letter || element.roman || '',
      amendmentType: 'suppression',
      originalText: element.text,
      proposedText: '',
      position: getElementPosition(element),
    };

    newAmendments.set(index, amendment);
    setAmendments(newAmendments);
  };

  const handleAddition = (index: number) => {
    const element = elements[index];
    const newAmendments = new Map(amendments);

    const amendment: CellAmendment = {
      elementIndex: index,
      elementType: element.type,
      elementNumber: element.number || element.letter || element.roman || '',
      amendmentType: 'addition',
      originalText: '',
      proposedText: '',
      position: `After ${getElementPosition(element)}`,
      insertAfter: index,
    };

    newAmendments.set(index + 0.5, amendment); // Use fractional index for insertions
    setAmendments(newAmendments);
    setEditingCell(index + 0.5);
  };

  const handleModification = (index: number) => {
    setEditingCell(index);

    if (onElementSelected && elements[index]) {
      onElementSelected(elements[index], index);
    }
  };

  const handleCellBlur = (index: number, value: string) => {
    const element = elements[Math.floor(index)];
    const newAmendments = new Map(amendments);

    // Check if this is a fractional index (addition)
    const isAddition = index % 1 !== 0;

    // Only store if different from original
    if (isAddition || value !== element?.text) {
      const amendment: CellAmendment = {
        elementIndex: Math.floor(index),
        elementType: element?.type || 'unknown',
        elementNumber: element?.number || element?.letter || element?.roman || '',
        amendmentType: isAddition ? 'addition' : 'modification',
        originalText: element?.text || '',
        proposedText: value,
        position: isAddition ? `After ${getElementPosition(element)}` : getElementPosition(element),
        insertAfter: isAddition ? Math.floor(index) : undefined,
      };

      newAmendments.set(index, amendment);
    } else {
      newAmendments.delete(index);
    }

    setAmendments(newAmendments);
    setEditingCell(null);
  };

  const handleCellChange = (index: number, value: string) => {
    const element = elements[Math.floor(index)];
    const isAddition = index % 1 !== 0;
    const newAmendments = new Map(amendments);

    const amendment: CellAmendment = {
      elementIndex: Math.floor(index),
      elementType: element?.type || 'unknown',
      elementNumber: element?.number || element?.letter || element?.roman || '',
      amendmentType: isAddition ? 'addition' : 'modification',
      originalText: element?.text || '',
      proposedText: value,
      position: isAddition ? `After ${getElementPosition(element)}` : getElementPosition(element),
      insertAfter: isAddition ? Math.floor(index) : undefined,
    };

    newAmendments.set(index, amendment);
    setAmendments(newAmendments);
  };

  return (
    <div className="two-column-layout">
      {/* Document Loader */}
      {showDocumentLoader && (
        <div className="two-column-layout__document-loader">
          <div className="two-column-layout__loader-container">
            <h2 className="two-column-layout__loader-title">Load Legislative Document</h2>
            <EURLexURLInput onDocumentFetched={handleDocumentFetched} />
            <div className="two-column-layout__divider">
              <span className="two-column-layout__divider-text">OR</span>
            </div>
            <AmendatorDocumentUpload onDocumentUploaded={handleDocumentUploaded} />
          </div>
        </div>
      )}

      {/* Two-Column Amendment Table */}
      {loadedDocument && (
        <div className="two-column-layout__table-container">
          {/* Header */}
          <div className="two-column-layout__table-header">
            <div className="two-column-layout__header-info">
              <h2 className="two-column-layout__document-title">
                {loadedDocument.metadata?.title || loadedDocument.filename}
              </h2>
              <button
                className="button button-sm button-secondary"
                onClick={() => setShowDocumentLoader(true)}
              >
                Load New Document
              </button>
            </div>
          </div>

          {/* Table */}
          {elements.length === 0 ? (
            <div className="two-column-layout__empty">
              <p>No legislative elements found in the document.</p>
              <p className="two-column-layout__empty-hint">
                The document might not contain recognizable legislative structure (recitals, articles, points).
              </p>
            </div>
          ) : (
            <div className="two-column-layout__table">
              {/* Column Headers */}
              <div className="two-column-layout__table-header-row">
                <div className="two-column-layout__header-cell two-column-layout__header-cell--original">
                  Original Document
                </div>
                <div className="two-column-layout__header-cell two-column-layout__header-cell--amendment">
                  Amendment Editor
                </div>
              </div>

              {/* Table Body */}
              <div className="two-column-layout__table-body">
                {elements.map((element, index) => {
                  const amendment = amendments.get(index);
                  const isSuppressed = amendment?.amendmentType === 'suppression';
                  const isModified = amendment?.amendmentType === 'modification';

                  return (
                    <React.Fragment key={index}>
                      <div
                        className={`two-column-layout__row two-column-layout__row--level-${element.level} two-column-layout__row--${element.type}`}
                      >
                        {/* Original Column (Read-Only) */}
                        <div className="two-column-layout__cell two-column-layout__cell--original">
                          <span className="two-column-layout__prefix">
                            {getElementPrefix(element)}
                          </span>
                          <span className="two-column-layout__text">
                            {element.text}
                          </span>
                        </div>

                        {/* Amendment Column (Editable) */}
                        <div
                          className={`two-column-layout__cell two-column-layout__cell--amendment ${
                            editingCell === index ? 'two-column-layout__cell--editing' : ''
                          } ${
                            amendments.has(index)
                              ? `two-column-layout__cell--${amendment?.amendmentType}`
                              : ''
                          }`}
                          onMouseEnter={() => setHoveredCell(index)}
                          onMouseLeave={() => setHoveredCell(null)}
                        >
                          {/* Amendment Icons Overlay */}
                          {hoveredCell === index && editingCell !== index && (
                            <div className="two-column-layout__amendment-icons">
                              <button
                                className="two-column-layout__amendment-icon"
                                onClick={() => handleSuppression(index)}
                                title="Suppression"
                                aria-label="Delete text"
                              >
                                <Icon path={mdiDeleteOutline} size={0.8} />
                              </button>
                              <button
                                className="two-column-layout__amendment-icon"
                                onClick={() => handleAddition(index)}
                                title="Addition"
                                aria-label="Add new text"
                              >
                                <Icon path={mdiPlusBoxOutline} size={0.8} />
                              </button>
                              <button
                                className="two-column-layout__amendment-icon"
                                onClick={() => handleModification(index)}
                                title="Modification"
                                aria-label="Modify text"
                              >
                                <Icon path={mdiAlphaM} size={0.8} />
                              </button>
                            </div>
                          )}

                          {editingCell === index ? (
                            <div className="two-column-layout__cell-edit-wrapper">
                              <span className="two-column-layout__prefix">
                                {getElementPrefix(element)}
                              </span>
                              <textarea
                                className="two-column-layout__textarea"
                                value={amendment?.proposedText || element.text}
                                onChange={(e) => handleCellChange(index, e.target.value)}
                                onBlur={(e) => handleCellBlur(index, e.target.value)}
                                autoFocus
                                onFocus={(e) => {
                                  e.target.selectionStart = e.target.value.length;
                                  e.target.selectionEnd = e.target.value.length;
                                }}
                              />
                            </div>
                          ) : (
                            <>
                              <span className="two-column-layout__prefix">
                                {getElementPrefix(element)}
                              </span>
                              <span
                                className={`two-column-layout__text ${
                                  isSuppressed ? 'two-column-layout__text--suppressed' : ''
                                }`}
                              >
                                {isSuppressed
                                  ? element.text
                                  : isModified
                                  ? amendment?.proposedText
                                  : element.text}
                              </span>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Addition Row (if amendment type is addition) */}
                      {amendments.has(index + 0.5) && (
                        <div className="two-column-layout__row two-column-layout__row--addition">
                          <div className="two-column-layout__cell two-column-layout__cell--empty"></div>
                          <div
                            className={`two-column-layout__cell two-column-layout__cell--amendment two-column-layout__cell--addition ${
                              editingCell === index + 0.5 ? 'two-column-layout__cell--editing' : ''
                            }`}
                          >
                            <span className="two-column-layout__addition-badge">NEW</span>
                            {editingCell === index + 0.5 ? (
                              <textarea
                                className="two-column-layout__textarea"
                                value={amendments.get(index + 0.5)?.proposedText || ''}
                                onChange={(e) => handleCellChange(index + 0.5, e.target.value)}
                                onBlur={(e) => handleCellBlur(index + 0.5, e.target.value)}
                                placeholder="Enter new text to add..."
                                autoFocus
                              />
                            ) : (
                              <span
                                className="two-column-layout__text"
                                onClick={() => setEditingCell(index + 0.5)}
                              >
                                {amendments.get(index + 0.5)?.proposedText || 'Click to add text...'}
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                    </React.Fragment>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
