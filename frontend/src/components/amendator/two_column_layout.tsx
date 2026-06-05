// frontend/src/components/amendator/two_column_layout.tsx
import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import { mdiDeleteOutline, mdiPlusBoxOutline, mdiAlphaM, mdiAutoFix, mdiContentSave, mdiCheck } from '@mdi/js';
import { useAuth } from '../../hooks/use_auth';
import type { LoadedDocument } from './document_viewer';
import { EURLexURLInput } from './eurlex_url_input';
import type { FetchedDocument } from './eurlex_url_input';
import { AmendatorDocumentUpload } from './amendator_document_upload';
import type { UploadedDocument } from './amendator_document_upload';
import { TrackedFilesLoader } from './tracked_files_loader';
import './two_column_layout.css';

const API_BASE = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api`;

export interface LegislativeElement {
  type: 'recital' | 'article' | 'article_title' | 'article_intro' | 'point' | 'paragraph' | 'subparagraph' | 'chapter';
  number?: string;
  letter?: string;
  roman?: string;
  text: string;
  level: number;
  article_number?: string;
  point_number?: string;
  paragraph_number?: string;
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

export interface PendingAIAmendment {
  elementIndex?: number;
  elementPosition?: string;
  amendmentType: 'modification' | 'suppression' | 'addition';
  proposedText: string;
  justification?: string;
}

interface TwoColumnLayoutProps {
  loadedDocument: LoadedDocument | null;
  onDocumentLoaded: (document: LoadedDocument) => void;
  onElementSelected?: (element: LegislativeElement, index: number) => void;
  amendments: Map<number, CellAmendment>;
  setAmendments: React.Dispatch<React.SetStateAction<Map<number, CellAmendment>>>;
  pendingAmendments?: PendingAIAmendment[];
  onPendingAmendmentsProcessed?: () => void;
}

export const TwoColumnLayout = ({
  loadedDocument,
  onDocumentLoaded,
  onElementSelected,
  amendments,
  setAmendments,
  pendingAmendments,
  onPendingAmendmentsProcessed,
}: TwoColumnLayoutProps) => {
  const { t } = useTranslation();
  const [showDocumentLoader, setShowDocumentLoader] = useState(!loadedDocument);

  // Keep the document-loader pane in sync with deep-link navigation. Without
  // this, arriving via /amendator?celex=... renders the editor AND the loader
  // side-by-side because the initial useState ran while loadedDocument was
  // still null.
  useEffect(() => {
    setShowDocumentLoader(!loadedDocument);
  }, [loadedDocument]);
  const [elements, setElements] = useState<LegislativeElement[]>([]);
  const [editingCell, setEditingCell] = useState<number | null>(null);
  const [hoveredCell, setHoveredCell] = useState<number | null>(null);
  const [additionCounter, setAdditionCounter] = useState(0);
  const [improvingCell, setImprovingCell] = useState<number | null>(null);
  const [preImproveText, setPreImproveText] = useState<string | null>(null);
  const [improveError, setImproveError] = useState<string | null>(null);
  const [savingCell, setSavingCell] = useState<number | null>(null);
  const [savedCells, setSavedCells] = useState<Set<number>>(new Set());

  // Extract legislative elements from loaded document
  useEffect(() => {
    if (loadedDocument?.structure?.legislative_structure?.elements) {
      setElements(loadedDocument.structure.legislative_structure.elements);
    } else {
      setElements([]);
    }
  }, [loadedDocument]);

  // Normalize a position string for fuzzy matching: lowercase, strip parentheses, collapse spaces
  const normalizePosition = (pos: string): string => {
    return pos
      .toLowerCase()
      .replace(/[()]/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  };

  // Process pending AI amendments from parent
  useEffect(() => {
    if (!pendingAmendments || pendingAmendments.length === 0 || elements.length === 0) return;

    const newAmendments = new Map(amendments);
    let applied = false;

    for (const pending of pendingAmendments) {
      let targetIndex: number | null = null;

      // Find the target element by index or position string
      if (pending.elementIndex !== undefined && pending.elementIndex !== null) {
        targetIndex = pending.elementIndex;
      } else if (pending.elementPosition) {
        const normPos = normalizePosition(pending.elementPosition);

        // Pass 1: exact normalized match or startsWith in either direction
        for (let i = 0; i < elements.length; i++) {
          const normElemPos = normalizePosition(getElementPosition(elements[i]));
          if (normElemPos === normPos || normElemPos.startsWith(normPos) || normPos.startsWith(normElemPos)) {
            targetIndex = i;
            break;
          }
        }

        // Pass 2: one contains the other (handles format variations)
        if (targetIndex === null) {
          for (let i = 0; i < elements.length; i++) {
            const normElemPos = normalizePosition(getElementPosition(elements[i]));
            if (normElemPos.includes(normPos) || normPos.includes(normElemPos)) {
              targetIndex = i;
              break;
            }
          }
        }

        // Pass 3: match by article number + element type as last resort
        if (targetIndex === null) {
          const artMatch = normPos.match(/article\s+(\d+)/);
          const recMatch = normPos.match(/recital\s+(\d+)/);
          if (artMatch) {
            const artNum = artMatch[1];
            // Try to find a paragraph/point within this article
            const paraMatch = normPos.match(/paragraph\s+(\w+)/);
            const pointMatch = normPos.match(/point\s+(\w+)/);
            for (let i = 0; i < elements.length; i++) {
              const el = elements[i];
              const elArtNum = el.article_number || el.number;
              if (paraMatch && el.type === 'paragraph' && elArtNum === artNum) {
                const paraId = paraMatch[1];
                if (el.number === paraId || el.letter === paraId || el.number === `(${paraId})`) {
                  targetIndex = i;
                  break;
                }
              } else if (pointMatch && el.type === 'point' && elArtNum === artNum) {
                const pointId = pointMatch[1];
                if (el.number === pointId) {
                  targetIndex = i;
                  break;
                }
              } else if (!paraMatch && !pointMatch && el.type === 'article' && el.number === artNum) {
                targetIndex = i;
                break;
              }
            }
          } else if (recMatch) {
            const recNum = recMatch[1];
            for (let i = 0; i < elements.length; i++) {
              if (elements[i].type === 'recital' && elements[i].number === recNum) {
                targetIndex = i;
                break;
              }
            }
          }
        }
      }

      if (targetIndex !== null && targetIndex >= 0 && targetIndex < elements.length) {
        const element = elements[targetIndex];
        const amendment: CellAmendment = {
          elementIndex: targetIndex,
          elementType: element.type,
          elementNumber: element.number || element.letter || element.roman || '',
          amendmentType: pending.amendmentType,
          originalText: element.text,
          proposedText: pending.proposedText,
          position: getElementPosition(element),
        };
        newAmendments.set(targetIndex, amendment);
        applied = true;
      }
    }

    if (applied) {
      setAmendments(newAmendments);
    }

    if (onPendingAmendmentsProcessed) {
      onPendingAmendmentsProcessed();
    }
  }, [pendingAmendments, elements]);

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
      case 'article_title':
        return `Article ${element.number}`;
      case 'article_intro':
        return ''; // No prefix for intro text
      case 'point':
        return `${element.number}.`;
      case 'paragraph':
        // Paragraph number can be "(1)", "(a)", or just "1"
        return element.number || '';
      case 'subparagraph':
        // Subparagraph number is Roman numeral like "i", "ii"
        return element.number ? `${element.number}.` : '';
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
      return `Article ${element.article_number || element.number}, title`;
    } else if (element.type === 'article_intro') {
      return `Article ${element.article_number || element.number}, introductory part`;
    } else if (element.type === 'point') {
      return `Article ${element.article_number}, point ${element.number}`;
    } else if (element.type === 'paragraph') {
      // Paragraph number can be "(1)", "(a)", or "1"
      return `Article ${element.article_number}, paragraph ${element.number}`;
    } else if (element.type === 'subparagraph') {
      // Subparagraph has article_number and paragraph_number
      return `Article ${element.article_number}, paragraph ${element.paragraph_number}, point ${element.number}`;
    } else if (element.type === 'chapter') {
      return `Chapter ${element.number}`;
    }
    return 'Unknown position';
  };

  const handleSuppression = (index: number) => {
    const element = elements[index];
    const newAmendments = new Map(amendments);

    // Toggle: if already suppressed, revert to original
    const existing = newAmendments.get(index);
    if (existing && existing.amendmentType === 'suppression') {
      newAmendments.delete(index);
      setAmendments(newAmendments);
      return;
    }

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

    // Select element for AI panel context
    if (onElementSelected) {
      onElementSelected(element, index);
    }
  };

  const handleAddition = (index: number) => {
    const element = elements[index];
    const newAmendments = new Map(amendments);

    // Count existing additions after this element to generate a unique fractional key
    const nextCounter = additionCounter + 1;
    setAdditionCounter(nextCounter);

    // Use a unique fractional index: index + 0.001 * counter to avoid collisions
    const additionKey = index + nextCounter * 0.001;

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

    newAmendments.set(additionKey, amendment);
    setAmendments(newAmendments);
    setEditingCell(additionKey);
  };

  const handleModification = (index: number) => {
    // Toggle: if already modified and not currently editing, revert to original
    const existing = amendments.get(index);
    if (existing && existing.amendmentType === 'modification' && editingCell !== index) {
      const newAmendments = new Map(amendments);
      newAmendments.delete(index);
      setAmendments(newAmendments);
      setEditingCell(null);
      return;
    }

    // If currently editing this cell, exit edit mode
    if (editingCell === index) {
      setEditingCell(null);
      return;
    }

    setEditingCell(index);

    if (onElementSelected && elements[index]) {
      onElementSelected(elements[index], index);
    }
  };

  const handleCellBlur = (index: number, value: string, event?: React.FocusEvent<HTMLTextAreaElement>) => {
    // Don't exit edit mode if focus moved to the improve actions area
    if (event?.relatedTarget) {
      const related = event.relatedTarget as HTMLElement;
      if (related.closest('.two-column-layout__cell-edit-actions')) {
        return;
      }
    }

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

  const handleImproveText = async (index: number) => {
    const element = elements[Math.floor(index)];
    const amendment = amendments.get(index);
    const isAddition = index % 1 !== 0;
    const currentText = amendment?.proposedText || (isAddition ? '' : element?.text || '');

    if (!currentText.trim()) return;

    setImprovingCell(index);
    setPreImproveText(currentText);
    setImproveError(null);

    try {
      const token = useAuth.getState().token;
      const response = await fetch(`${API_BASE}/amendments/improve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` }),
        },
        body: JSON.stringify({
          drafted_text: currentText,
          original_text: isAddition ? '' : (element?.text || ''),
          element_type: element?.type || 'unknown',
          element_position: getElementPosition(element),
          amendment_type: isAddition ? 'addition' : 'modification',
          document_title: loadedDocument?.metadata?.title || loadedDocument?.filename || null,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to improve text');
      }

      const result = await response.json();
      handleCellChange(index, result.improved_text);
    } catch (error) {
      setImproveError(error instanceof Error ? error.message : 'Could not improve text');
      setTimeout(() => setImproveError(null), 5000);
    } finally {
      setImprovingCell(null);
    }
  };

  const handleSaveCell = async (index: number) => {
    const amendment = amendments.get(index);
    if (!amendment || !loadedDocument) return;

    setSavingCell(index);

    try {
      const token = useAuth.getState().token;
      const response = await fetch(`${API_BASE}/amendments`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` }),
        },
        body: JSON.stringify({
          document_id: loadedDocument.document_id,
          document_filename: loadedDocument.filename,
          element_index: amendment.elementIndex,
          element_type: amendment.elementType,
          element_number: amendment.elementNumber,
          position_text: amendment.position,
          amendment_type: amendment.amendmentType,
          original_text: amendment.originalText,
          proposed_text: amendment.proposedText,
          insert_after: amendment.insertAfter,
          justification: '',
          group_label: '',
          author: '',
          amendment_number: '',
          status: 'draft',
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to save amendment');
      }

      setSavedCells(prev => new Set(prev).add(index));
    } catch (error) {
      console.error('Error saving amendment:', error);
    } finally {
      setSavingCell(null);
    }
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

    // Clear saved status if text changed after saving
    if (savedCells.has(index)) {
      const newSaved = new Set(savedCells);
      newSaved.delete(index);
      setSavedCells(newSaved);
    }
  };

  return (
    <div className="two-column-layout">
      {/* Document Loader */}
      {showDocumentLoader && (
        <div className="two-column-layout__document-loader">
          <div className="two-column-layout__loader-container">
            <h2 className="two-column-layout__loader-title">{t('amendator.loadTitle')}</h2>
            <TrackedFilesLoader onDocumentFetched={handleDocumentFetched} />
            <div className="two-column-layout__divider">
              <span className="two-column-layout__divider-text">{t('amendator.or')}</span>
            </div>
            <EURLexURLInput onDocumentFetched={handleDocumentFetched} />
            <div className="two-column-layout__divider">
              <span className="two-column-layout__divider-text">{t('amendator.or')}</span>
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
                {t('amendator.loadNewDocument')}
              </button>
            </div>
          </div>

          {/* Table */}
          {elements.length === 0 ? (
            <div className="two-column-layout__empty">
              <p>{t('amendator.noElements')}</p>
              <p className="two-column-layout__empty-hint">{t('amendator.noElementsHint')}</p>
            </div>
          ) : (
            <div className="two-column-layout__table">
              {/* Column Headers */}
              <div className="two-column-layout__table-header-row">
                <div className="two-column-layout__header-cell two-column-layout__header-cell--original">
                  {t('amendator.originalDocument')}
                </div>
                <div className="two-column-layout__header-cell two-column-layout__header-cell--amendment">
                  {t('amendator.amendmentEditor')}
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
                        data-element-index={index}
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
                                title={t('amendator.suppression')}
                                aria-label={t('amendator.deleteText')}
                              >
                                <Icon path={mdiDeleteOutline} size={0.8} />
                              </button>
                              <button
                                className="two-column-layout__amendment-icon"
                                onClick={() => handleAddition(index)}
                                title={t('amendator.addition')}
                                aria-label={t('amendator.addNewText')}
                              >
                                <Icon path={mdiPlusBoxOutline} size={0.8} />
                              </button>
                              <button
                                className="two-column-layout__amendment-icon"
                                onClick={() => handleModification(index)}
                                title={t('amendator.modification')}
                                aria-label={t('amendator.modifyText')}
                              >
                                <Icon path={mdiAlphaM} size={0.8} />
                              </button>
                            </div>
                          )}

                          {editingCell === index ? (
                            <div className="two-column-layout__cell-edit-wrapper">
                              <div className="two-column-layout__cell-edit-top">
                                <span className="two-column-layout__prefix">
                                  {getElementPrefix(element)}
                                </span>
                                <textarea
                                  className="two-column-layout__textarea"
                                  value={amendment?.proposedText || element.text}
                                  onChange={(e) => handleCellChange(index, e.target.value)}
                                  onBlur={(e) => handleCellBlur(index, e.target.value, e)}
                                  autoFocus
                                  onFocus={(e) => {
                                    e.target.selectionStart = e.target.value.length;
                                    e.target.selectionEnd = e.target.value.length;
                                  }}
                                />
                              </div>
                              <div className="two-column-layout__cell-edit-actions">
                                {['yellow', 'blue', 'admin'].includes(useAuth.getState().user?.subscription_tier || '') && (
                                  <button
                                    className={`two-column-layout__improve-button ${improvingCell === index ? 'two-column-layout__improve-button--loading' : ''}`}
                                    onClick={(e) => { e.stopPropagation(); handleImproveText(index); }}
                                    disabled={improvingCell === index || !(amendment?.proposedText || element.text).trim()}
                                    title={t('amendator.improveWithAi')}
                                    aria-label={t('amendator.improveTextWithAi')}
                                  >
                                    <Icon path={mdiAutoFix} size={0.65} className={improvingCell === index ? 'two-column-layout__spin' : ''} />
                                    <span>{improvingCell === index ? t('amendator.improving') : t('amendator.improve')}</span>
                                  </button>
                                )}
                                <button
                                  className={`two-column-layout__save-button ${savedCells.has(index) ? 'two-column-layout__save-button--saved' : ''}`}
                                  onClick={(e) => { e.stopPropagation(); handleSaveCell(index); }}
                                  disabled={savingCell === index || savedCells.has(index) || !(amendment?.proposedText || '').trim()}
                                  title={savedCells.has(index) ? t('amendator.saved') : t('amendator.saveAmendment')}
                                  aria-label={t('amendator.saveAmendment')}
                                >
                                  <Icon path={savedCells.has(index) ? mdiCheck : mdiContentSave} size={0.65} />
                                  <span>{savingCell === index ? t('amendator.saving') : savedCells.has(index) ? t('amendator.saved') : t('amendator.save')}</span>
                                </button>
                                {preImproveText && improvingCell !== index && editingCell === index && (
                                  <button
                                    className="two-column-layout__undo-improve"
                                    onClick={(e) => { e.stopPropagation(); handleCellChange(index, preImproveText); setPreImproveText(null); }}
                                  >
                                    {t('amendator.undo')}
                                  </button>
                                )}
                                {improveError && editingCell === index && (
                                  <span className="two-column-layout__improve-error">{improveError}</span>
                                )}
                              </div>
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

                      {/* Addition Rows (all additions after this element) */}
                      {Array.from(amendments.entries())
                        .filter(([, a]) => a.amendmentType === 'addition' && a.insertAfter === index)
                        .sort(([keyA], [keyB]) => keyA - keyB)
                        .map(([additionKey, additionAmendment]) => (
                          <div key={additionKey} className="two-column-layout__row two-column-layout__row--addition">
                            <div className="two-column-layout__cell two-column-layout__cell--empty"></div>
                            <div
                              className={`two-column-layout__cell two-column-layout__cell--amendment two-column-layout__cell--addition ${
                                editingCell === additionKey ? 'two-column-layout__cell--editing' : ''
                              }`}
                            >
                              <span className="two-column-layout__addition-badge">{t('amendator.newBadge')}</span>
                              <button
                                className="two-column-layout__addition-remove"
                                onClick={() => {
                                  const newAmendments = new Map(amendments);
                                  newAmendments.delete(additionKey);
                                  setAmendments(newAmendments);
                                  if (editingCell === additionKey) setEditingCell(null);
                                }}
                                title={t('amendator.removeAddition')}
                                aria-label={t('amendator.removeAddition')}
                              >
                                <Icon path={mdiDeleteOutline} size={0.7} />
                              </button>
                              {editingCell === additionKey ? (
                                <div className="two-column-layout__cell-edit-wrapper">
                                  <textarea
                                    className="two-column-layout__textarea"
                                    value={additionAmendment.proposedText || ''}
                                    onChange={(e) => handleCellChange(additionKey, e.target.value)}
                                    onBlur={(e) => handleCellBlur(additionKey, e.target.value, e)}
                                    placeholder={t('amendator.enterNewText')}
                                    autoFocus
                                  />
                                  <div className="two-column-layout__cell-edit-actions">
                                    {['yellow', 'blue', 'admin'].includes(useAuth.getState().user?.subscription_tier || '') && (
                                      <button
                                        className={`two-column-layout__improve-button ${improvingCell === additionKey ? 'two-column-layout__improve-button--loading' : ''}`}
                                        onClick={(e) => { e.stopPropagation(); handleImproveText(additionKey); }}
                                        disabled={improvingCell === additionKey || !(additionAmendment.proposedText || '').trim()}
                                        title="Improve with AI"
                                        aria-label="Improve text with AI"
                                      >
                                        <Icon path={mdiAutoFix} size={0.65} className={improvingCell === additionKey ? 'two-column-layout__spin' : ''} />
                                        <span>{improvingCell === additionKey ? t('amendator.improving') : t('amendator.improve')}</span>
                                      </button>
                                    )}
                                    <button
                                      className={`two-column-layout__save-button ${savedCells.has(additionKey) ? 'two-column-layout__save-button--saved' : ''}`}
                                      onClick={(e) => { e.stopPropagation(); handleSaveCell(additionKey); }}
                                      disabled={savingCell === additionKey || savedCells.has(additionKey) || !(additionAmendment.proposedText || '').trim()}
                                      title={savedCells.has(additionKey) ? t('amendator.saved') : t('amendator.saveAmendment')}
                                      aria-label={t('amendator.saveAmendment')}
                                    >
                                      <Icon path={savedCells.has(additionKey) ? mdiCheck : mdiContentSave} size={0.65} />
                                      <span>{savingCell === additionKey ? t('amendator.saving') : savedCells.has(additionKey) ? t('amendator.saved') : t('amendator.save')}</span>
                                    </button>
                                    {preImproveText && improvingCell !== additionKey && editingCell === additionKey && (
                                      <button
                                        className="two-column-layout__undo-improve"
                                        onClick={(e) => { e.stopPropagation(); handleCellChange(additionKey, preImproveText); setPreImproveText(null); }}
                                      >
                                        Undo
                                      </button>
                                    )}
                                    {improveError && editingCell === additionKey && (
                                      <span className="two-column-layout__improve-error">{improveError}</span>
                                    )}
                                  </div>
                                </div>
                              ) : (
                                <span
                                  className="two-column-layout__text"
                                  onClick={() => setEditingCell(additionKey)}
                                >
                                  {additionAmendment.proposedText || t('amendator.clickToAdd')}
                                </span>
                              )}
                            </div>
                          </div>
                        ))}
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
