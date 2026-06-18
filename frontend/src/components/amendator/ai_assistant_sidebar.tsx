// frontend/src/components/amendator/ai_assistant_sidebar.tsx
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { LegislativeElement } from './two_column_layout';
import type { LoadedDocument } from './document_viewer';
import { FeedbackInvitation } from '../shared/feedback_invitation';
import { useAuth } from '../../hooks/use_auth';
import './ai_assistant_sidebar.css';

const API_BASE = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api`;

interface AIAssistantPanelProps {
  selectedElement: LegislativeElement | null;
  selectedElementIndex?: number | null;
  loadedDocument: LoadedDocument | null;
  onSuggestionAccepted: (suggestion: AISuggestion) => void;
  onBatchSuggestionsAccepted?: (suggestions: AISuggestion[]) => void;
}

export interface SuggestionValidation {
  original_verified: boolean;
  scope_ratio: number;
  phantom_references: string[];
  flags: string[];
}

export interface AISuggestion {
  amendment_type: 'modification' | 'suppression' | 'addition';
  original_text: string;
  proposed_text: string;
  justification: string;
  element_position?: string;
  element_index?: number | null;
  validation?: SuggestionValidation;
}

interface UploadedDoc {
  file: File;
  extractedText: string | null;
  isUploading: boolean;
  error: string | null;
}

export const AIAssistantPanel = ({
  selectedElement,
  selectedElementIndex,
  loadedDocument,
  onSuggestionAccepted,
  onBatchSuggestionsAccepted,
}: AIAssistantPanelProps) => {
  const { t } = useTranslation();
  const [policyText, setPolicyText] = useState('');
  const [uploadedDocuments, setUploadedDocuments] = useState<UploadedDoc[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState<AISuggestion | null>(null);
  const [batchSuggestions, setBatchSuggestions] = useState<AISuggestion[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editedText, setEditedText] = useState('');

  // Get supporting context from uploaded documents
  const getSupportingContext = (): string | null => {
    const texts = uploadedDocuments
      .filter(d => d.extractedText)
      .map(d => d.extractedText!);
    return texts.length > 0 ? texts.join('\n\n---\n\n') : null;
  };

  // CELEX of the loaded law (drives backend drafting-context injection)
  const getCelex = (): string | undefined => loadedDocument?.metadata?.celex || undefined;

  // Every article number in the loaded document, lowercased, for the backend's
  // phantom-reference detection (an "Article 99" in proposed text that does not
  // exist in this law gets flagged).
  const getKnownArticleNumbers = (): string[] => {
    const elements = loadedDocument?.structure?.legislative_structure?.elements || [];
    const nums = new Set<string>();
    for (const elem of elements) {
      if (elem.type === 'article' && elem.number) {
        nums.add(String(elem.number).toLowerCase());
      }
    }
    return Array.from(nums);
  };

  // Extract key elements from loaded document for batch mode. element_index is
  // the position in the FULL element list, so the editor can place each
  // accepted suggestion by index instead of fuzzy-matching a position string.
  const getDocumentElements = (): Array<{ position: string; element_type: string; text: string; element_index: number }> => {
    if (!loadedDocument?.structure?.legislative_structure?.elements) return [];

    const elements = loadedDocument.structure.legislative_structure.elements;
    const keyElements: Array<{ position: string; element_type: string; text: string; element_index: number }> = [];
    let currentArticleNumber = '';

    elements.forEach((elem, idx) => {
      // Track current article number for sub-element context
      if (elem.type === 'article') {
        currentArticleNumber = elem.number || '';
      }

      // Only include articles, recitals, points, and paragraphs
      if (!['article', 'recital', 'point', 'paragraph'].includes(elem.type)) return;

      let position = '';
      if (elem.type === 'recital') {
        position = `Recital ${elem.number || ''}`;
      } else if (elem.type === 'article') {
        position = `Article ${elem.number || ''}`;
      } else if (elem.type === 'point') {
        // Include parent article context - match getElementPosition() format
        const artNum = (elem as any).article_number || currentArticleNumber;
        position = artNum ? `Article ${artNum}, point ${elem.number || ''}` : `Point ${elem.number || ''}`;
      } else if (elem.type === 'paragraph') {
        // Match getElementPosition() format: uses element.number, not elem.letter
        const artNum = (elem as any).article_number || currentArticleNumber;
        const paraId = elem.number || elem.letter || '';
        position = artNum ? `Article ${artNum}, paragraph ${paraId}` : `Paragraph ${paraId}`;
      }

      // Skip articles with no body text (just the heading "Article X")
      const elemText = elem.text || '';
      if (elem.type === 'article' && elemText.length < 20) return;

      keyElements.push({
        position: position.trim(),
        element_type: elem.type,
        text: elemText.substring(0, 300),
        element_index: idx,
      });
    });

    return keyElements;
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files) return;

    for (const file of Array.from(files)) {
      const newDoc: UploadedDoc = {
        file,
        extractedText: null,
        isUploading: true,
        error: null,
      };
      setUploadedDocuments(prev => [...prev, newDoc]);

      try {
        // Upload to backend for text extraction
        const formData = new FormData();
        formData.append('file', file);

        const token = useAuth.getState().token;
        const uploadResponse = await fetch(`${API_BASE}/documents/upload`, {
          method: 'POST',
          headers: {
            ...(token && { 'Authorization': `Bearer ${token}` }),
          },
          body: formData,
        });

        if (!uploadResponse.ok) {
          throw new Error('Upload failed');
        }

        const uploadResult = await uploadResponse.json();

        // Fetch extracted text
        const contentResponse = await fetch(`${API_BASE}/documents/storage/${uploadResult.document_id}/content`, {
          headers: {
            ...(token && { 'Authorization': `Bearer ${token}` }),
          },
        });

        if (!contentResponse.ok) {
          throw new Error('Could not extract text');
        }

        const contentResult = await contentResponse.json();
        const extractedText = contentResult.text || '';

        setUploadedDocuments(prev =>
          prev.map(d =>
            d.file === file
              ? { ...d, extractedText, isUploading: false }
              : d
          )
        );
      } catch (error) {
        setUploadedDocuments(prev =>
          prev.map(d =>
            d.file === file
              ? { ...d, isUploading: false, error: 'Failed to process' }
              : d
          )
        );
      }
    }

    // Reset input
    event.target.value = '';
  };

  const handleRemoveDocument = (index: number) => {
    setUploadedDocuments(prev => prev.filter((_, i) => i !== index));
  };

  const handleAISuggest = async () => {
    setErrorMessage(null);

    // Determine mode: targeted (element selected) vs document-wide (no element)
    const isTargetedMode = !!selectedElement;
    const hasDocument = !!loadedDocument;

    // Validate: need at least a document loaded OR an element selected
    if (!isTargetedMode && !hasDocument) {
      setErrorMessage('Please load a legislative document first.');
      return;
    }

    setIsLoading(true);
    setAiSuggestion(null);
    setBatchSuggestions([]);

    const token = useAuth.getState().token;
    const supportingContext = getSupportingContext();

    try {
      if (isTargetedMode) {
        // --- TARGETED MODE: Suggest for specific element ---
        let elementPosition = '';
        if (selectedElement!.type === 'recital') {
          elementPosition = `Recital ${selectedElement!.number}`;
        } else if (selectedElement!.type === 'article') {
          elementPosition = `Article ${selectedElement!.number}`;
        } else if (selectedElement!.type === 'article_title') {
          elementPosition = `Article ${selectedElement!.number} Title`;
        } else if (selectedElement!.type === 'point') {
          elementPosition = `Point ${selectedElement!.number}`;
        } else if (selectedElement!.type === 'paragraph') {
          elementPosition = `Paragraph (${selectedElement!.letter})`;
        } else if (selectedElement!.type === 'subparagraph') {
          elementPosition = `Subparagraph (${selectedElement!.roman})`;
        } else if (selectedElement!.type === 'chapter') {
          elementPosition = `Chapter ${selectedElement!.number}`;
        }

        const celex = getCelex();
        const params = new URLSearchParams({
          policy_position: policyText.trim() || 'Analyse this element and suggest improvements',
          original_text: selectedElement!.text,
          element_type: selectedElement!.type,
          element_position: elementPosition,
          ...(supportingContext && { supporting_context: supportingContext }),
          ...(celex && { celex }),
          ...(selectedElementIndex != null && { element_index: String(selectedElementIndex) }),
          ...((selectedElement as any).article_number && { article_number: String((selectedElement as any).article_number) }),
        });
        // Repeatable query param: one entry per known article number
        for (const num of getKnownArticleNumbers()) {
          params.append('known_article_numbers', num);
        }

        const response = await fetch(`${API_BASE}/amendments/suggest?${params.toString()}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token && { 'Authorization': `Bearer ${token}` }),
          },
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || 'Failed to generate AI suggestion');
        }

        const suggestion = await response.json();
        setAiSuggestion({
          amendment_type: suggestion.amendment_type,
          original_text: selectedElement!.text,
          proposed_text: suggestion.proposed_text,
          justification: suggestion.justification,
          element_position: elementPosition,
          element_index: suggestion.element_index ?? selectedElementIndex ?? null,
          validation: suggestion.validation,
        });
      } else {
        // --- DOCUMENT-WIDE MODE: Analyse key elements ---
        const elements = getDocumentElements();
        if (elements.length === 0) {
          setErrorMessage('No legislative elements found in the document.');
          return;
        }

        const response = await fetch(`${API_BASE}/amendments/suggest-batch`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token && { 'Authorization': `Bearer ${token}` }),
          },
          body: JSON.stringify({
            policy_position: policyText.trim() || 'Analyse this legislation and suggest the most impactful amendments',
            supporting_context: supportingContext,
            elements,
            celex: getCelex(),
            known_article_numbers: getKnownArticleNumbers(),
          }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || 'Failed to generate suggestions');
        }

        const result = await response.json();
        const suggestions: AISuggestion[] = (result.suggestions || []).map((s: any) => ({
          amendment_type: s.amendment_type,
          original_text: s.original_text,
          proposed_text: s.proposed_text,
          justification: s.justification,
          element_position: s.element_position,
          element_index: s.element_index ?? null,
          validation: s.validation,
        }));

        setBatchSuggestions(suggestions);
      }
    } catch (error) {
      console.error('AI suggestion error:', error);
      setErrorMessage(error instanceof Error ? error.message : 'Failed to generate AI suggestion');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAccept = () => {
    if (aiSuggestion) {
      if (isEditing) {
        // Accept the edited version
        onSuggestionAccepted({ ...aiSuggestion, proposed_text: editedText });
      } else {
        onSuggestionAccepted(aiSuggestion);
      }
      setAiSuggestion(null);
      setIsEditing(false);
      setEditedText('');
    }
  };

  const handleModify = () => {
    if (aiSuggestion) {
      setIsEditing(true);
      setEditedText(aiSuggestion.proposed_text);
    }
  };

  const handleReject = () => {
    setAiSuggestion(null);
    setIsEditing(false);
    setEditedText('');
  };

  const handleAcceptBatchItem = (index: number) => {
    const suggestion = batchSuggestions[index];
    if (suggestion) {
      onSuggestionAccepted(suggestion);
      setBatchSuggestions(prev => prev.filter((_, i) => i !== index));
    }
  };

  const handleRejectBatchItem = (index: number) => {
    setBatchSuggestions(prev => prev.filter((_, i) => i !== index));
  };

  const handleAcceptAll = () => {
    if (onBatchSuggestionsAccepted && batchSuggestions.length > 0) {
      onBatchSuggestionsAccepted(batchSuggestions);
      setBatchSuggestions([]);
    }
  };

  const isDocumentLoaded = !!loadedDocument;
  const canSuggest = isDocumentLoaded || !!selectedElement;

  // Deterministic fidelity badges from the backend check. Warnings prompt the
  // user to look closer; they never block accepting a suggestion.
  const renderValidationBadges = (v?: SuggestionValidation) => {
    if (!v) return null;
    const badges: Array<{ key: string; label: string; warn: boolean; icon: string }> = [];
    if (v.flags?.includes('original_mismatch')) {
      badges.push({ key: 'orig', label: t('amendator.badgeOriginalMismatch', 'Quoted original may not match the source text'), warn: true, icon: 'mdi-alert-outline' });
    }
    if (v.flags?.includes('scope_creep')) {
      badges.push({
        key: 'scope',
        label: t('amendator.badgeScopeCreep', { pct: Math.round((v.scope_ratio || 0) * 100), defaultValue: 'Large rewrite ({{pct}}% changed)' }),
        warn: true,
        icon: 'mdi-format-letter-matches',
      });
    }
    if (v.flags?.includes('phantom_reference') && v.phantom_references?.length) {
      const refs = v.phantom_references.map((n) => `Article ${n}`).join(', ');
      badges.push({ key: 'phantom', label: t('amendator.badgePhantom', { refs, defaultValue: 'Unrecognised reference: {{refs}}' }), warn: true, icon: 'mdi-link-variant-off' });
    }
    if (badges.length === 0 && v.original_verified) {
      badges.push({ key: 'ok', label: t('amendator.badgeVerified', 'Original verified against the source'), warn: false, icon: 'mdi-check-decagram' });
    }
    if (badges.length === 0) return null;
    return (
      <div className="ai-panel__badges">
        {badges.map((b) => (
          <span key={b.key} className={`ai-panel__badge ${b.warn ? 'ai-panel__badge--warn' : 'ai-panel__badge--ok'}`}>
            <span className={`mdi ${b.icon}`}></span> {b.label}
          </span>
        ))}
      </div>
    );
  };

  return (
    <div className="ai-panel">
      {/* Policy Input */}
      <div className="ai-panel__section">
        <h3 className="ai-panel__section-title">{t('ai.policyPosition')}</h3>
        <textarea
          className="ai-panel__textarea"
          placeholder={t('ai.policyPlaceholder')}
          value={policyText}
          onChange={(e) => setPolicyText(e.target.value)}
          rows={5}
        />
      </div>

      {/* Document Upload */}
      <div className="ai-panel__section">
        <h3 className="ai-panel__section-title">{t('ai.uploadDocs')}</h3>
        <label className="ai-panel__upload-button button button-sm button-secondary">
          <span className="mdi mdi-paperclip"></span> {t('ai.uploadButton')}
          <input
            type="file"
            multiple
            accept=".pdf,.doc,.docx,.txt"
            onChange={handleFileUpload}
            style={{ display: 'none' }}
          />
        </label>

        {uploadedDocuments.length > 0 && (
          <div className="ai-panel__documents">
            {uploadedDocuments.map((doc, index) => (
              <div key={index} className={`ai-panel__document ${doc.error ? 'ai-panel__document--error' : ''}`}>
                <span className="ai-panel__document-icon mdi mdi-file-document"></span>
                <span className="ai-panel__document-name">{doc.file.name}</span>
                {doc.isUploading && <span className="ai-panel__document-status">Processing...</span>}
                {doc.extractedText && <span className="ai-panel__document-status ai-panel__document-status--ok">Ready</span>}
                {doc.error && <span className="ai-panel__document-status ai-panel__document-status--error">{doc.error}</span>}
                <button
                  className="ai-panel__document-remove"
                  onClick={() => handleRemoveDocument(index)}
                  aria-label="Remove document"
                >
                  <span className="mdi mdi-close"></span>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Selected Element */}
      <div className="ai-panel__section">
        <h3 className="ai-panel__section-title">{t('ai.currentlySelected')}</h3>
        {selectedElement ? (
          <div className="ai-panel__selected">
            <div className="ai-panel__selected-type">
              {selectedElement.type === 'recital' && `Recital ${selectedElement.number}`}
              {selectedElement.type === 'article' && `Article ${selectedElement.number}`}
              {selectedElement.type === 'point' && `Point ${selectedElement.number}`}
              {selectedElement.type === 'paragraph' && `Paragraph (${selectedElement.letter})`}
              {selectedElement.type === 'subparagraph' && `Subparagraph (${selectedElement.roman})`}
            </div>
            <div className="ai-panel__selected-text">
              {selectedElement.text.substring(0, 100)}...
            </div>
          </div>
        ) : (
          <p className="ai-panel__no-selection">
            {isDocumentLoaded
              ? 'No element selected - AI will analyse the full document'
              : t('ai.clickRow')}
          </p>
        )}
      </div>

      {/* Error Message */}
      {errorMessage && (
        <div className="ai-panel__error">
          <span className="mdi mdi-alert-circle"></span>
          <span>{errorMessage}</span>
        </div>
      )}

      {/* AI Suggest Button */}
      <button
        className="button button-primary ai-panel__suggest-button"
        onClick={handleAISuggest}
        disabled={isLoading || !canSuggest}
      >
        <span className="mdi mdi-robot"></span>
        {isLoading
          ? t('ai.thinking')
          : selectedElement
            ? t('ai.suggest')
            : "Let's Amend"}
      </button>
      {!canSuggest && (
        <p className="ai-panel__hint">Load a legislative document to enable AI analysis</p>
      )}
      {canSuggest && !selectedElement && !isLoading && (
        <p className="ai-panel__hint">Tip: select a specific element for targeted suggestions, or let the AI analyse the full document</p>
      )}

      {/* Single Suggestion (Targeted Mode) */}
      {aiSuggestion && (
        <div className="ai-panel__suggestion">
          <h3 className="ai-panel__suggestion-title"><span className="mdi mdi-lightbulb"></span> {t('ai.suggestion')}</h3>
          {aiSuggestion.element_position && (
            <div className="ai-panel__suggestion-position">{aiSuggestion.element_position}</div>
          )}
          {renderValidationBadges(aiSuggestion.validation)}

          <div className="ai-panel__suggestion-content">
            <div className="ai-panel__suggestion-field">
              <strong>{t('ai.type')}</strong> {aiSuggestion.amendment_type}
            </div>

            <div className="ai-panel__suggestion-field">
              <strong>{t('ai.proposedText')}</strong>
              {isEditing ? (
                <textarea
                  className="ai-panel__textarea ai-panel__suggestion-edit"
                  value={editedText}
                  onChange={(e) => setEditedText(e.target.value)}
                  rows={6}
                  autoFocus
                />
              ) : (
                <div className="ai-panel__suggestion-text">
                  {aiSuggestion.proposed_text}
                </div>
              )}
            </div>

            <div className="ai-panel__suggestion-field">
              <strong>{t('ai.justification')}</strong>
              <div className="ai-panel__suggestion-justification">
                {aiSuggestion.justification}
              </div>
            </div>
          </div>

          <div className="ai-panel__suggestion-actions">
            <button className="button button-sm button-success" onClick={handleAccept}>
              <span className="mdi mdi-check"></span> {isEditing ? 'Apply' : t('ai.accept')}
            </button>
            {!isEditing && (
              <button className="button button-sm button-secondary" onClick={handleModify}>
                <span className="mdi mdi-pencil"></span> {t('ai.modify')}
              </button>
            )}
            <button className="button button-sm button-danger" onClick={handleReject}>
              <span className="mdi mdi-close"></span> {isEditing ? 'Cancel' : t('ai.reject')}
            </button>
          </div>
        </div>
      )}

      {/* Batch Suggestions (Document-Wide Mode) */}
      {batchSuggestions.length > 0 && (
        <div className="ai-panel__batch">
          <div className="ai-panel__batch-header">
            <h3 className="ai-panel__suggestion-title">
              <span className="mdi mdi-lightbulb"></span> {batchSuggestions.length} Suggestions
            </h3>
            {onBatchSuggestionsAccepted && (
              <button className="button button-sm button-success" onClick={handleAcceptAll}>
                Accept All
              </button>
            )}
          </div>

          <div className="ai-panel__batch-list">
            {batchSuggestions.map((suggestion, index) => (
              <div key={index} className="ai-panel__batch-item">
                <div className="ai-panel__batch-item-header">
                  <span className="ai-panel__batch-item-position">{suggestion.element_position}</span>
                  <span className={`ai-panel__batch-item-type ai-panel__batch-item-type--${suggestion.amendment_type}`}>
                    {suggestion.amendment_type}
                  </span>
                </div>

                {renderValidationBadges(suggestion.validation)}

                <div className="ai-panel__batch-item-text">
                  {suggestion.proposed_text.substring(0, 150)}
                  {suggestion.proposed_text.length > 150 ? '...' : ''}
                </div>

                <div className="ai-panel__batch-item-justification">
                  {suggestion.justification}
                </div>

                <div className="ai-panel__batch-item-actions">
                  <button
                    className="button button-sm button-success"
                    onClick={() => handleAcceptBatchItem(index)}
                  >
                    <span className="mdi mdi-check"></span> Accept
                  </button>
                  <button
                    className="button button-sm button-danger"
                    onClick={() => handleRejectBatchItem(index)}
                  >
                    <span className="mdi mdi-close"></span> Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Feedback Section */}
      <FeedbackInvitation
        featureName="Amendator"
        featureDescription="Help us improve Amendator. Your feedback on the AI assistant and amendment tools is valuable."
        variant="sidebar"
      />
    </div>
  );
};
