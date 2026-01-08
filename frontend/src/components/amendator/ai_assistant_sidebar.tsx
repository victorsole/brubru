// frontend/src/components/amendator/ai_assistant_sidebar.tsx
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { LegislativeElement } from './two_column_layout';
import { FeedbackInvitation } from '../shared/feedback_invitation';
import './ai_assistant_sidebar.css';

interface AIAssistantSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  selectedElement: LegislativeElement | null;
  onSuggestionAccepted: (suggestion: AISuggestion) => void;
}

export interface AISuggestion {
  amendment_type: 'modification' | 'suppression' | 'addition';
  original_text: string;
  proposed_text: string;
  justification: string;
}

export const AIAssistantSidebar = ({
  isOpen,
  onToggle,
  selectedElement,
  onSuggestionAccepted,
}: AIAssistantSidebarProps) => {
  const { t } = useTranslation();
  const [policyText, setPolicyText] = useState('');
  const [uploadedDocuments, setUploadedDocuments] = useState<File[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState<AISuggestion | null>(null);

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files) {
      setUploadedDocuments(prev => [...prev, ...Array.from(files)]);
    }
  };

  const handleRemoveDocument = (index: number) => {
    setUploadedDocuments(prev => prev.filter((_, i) => i !== index));
  };

  const handleAISuggest = async () => {
    if (!selectedElement) {
      alert('Please select a row in the amendment table first');
      return;
    }

    setIsLoading(true);
    setAiSuggestion(null);

    try {
      // TODO: Replace with actual API call
      // Simulating API call for now
      await new Promise(resolve => setTimeout(resolve, 2000));

      // Mock AI suggestion
      const mockSuggestion: AISuggestion = {
        amendment_type: 'modification',
        original_text: selectedElement.text,
        proposed_text: selectedElement.text.replace(
          /children/gi,
          'minors under 18 years of age'
        ),
        justification: 'This amendment strengthens child protection by providing a more precise legal definition, aligning with your policy position on enhanced data privacy for minors.',
      };

      setAiSuggestion(mockSuggestion);
    } catch (error) {
      console.error('AI suggestion error:', error);
      alert('Failed to generate AI suggestion');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAccept = () => {
    if (aiSuggestion) {
      onSuggestionAccepted(aiSuggestion);
      setAiSuggestion(null);
    }
  };

  const handleModify = () => {
    if (aiSuggestion) {
      onSuggestionAccepted(aiSuggestion);
      setAiSuggestion(null);
    }
  };

  const handleReject = () => {
    setAiSuggestion(null);
  };

  const getMascotImage = () => {
    if (isLoading) {
      return {
        src: '/assets/brubru_myeububble.png',
        alt: 'Brubru is analyzing your policy position...',
        className: 'pulse',
      };
    }

    if (aiSuggestion) {
      return {
        src: '/assets/brubru_amendator.png',
        alt: 'Brubru has an amendment suggestion for you!',
        className: 'bounce wiggle',
      };
    }

    return {
      src: '/assets/brubru_amendator_nochips.png',
      alt: 'Upload your policy documents to get started',
      className: 'breathe',
    };
  };

  const mascot = getMascotImage();

  if (!isOpen) {
    return (
      <button
        className="ai-sidebar__toggle ai-sidebar__toggle--collapsed"
        onClick={onToggle}
        aria-label={t('ai.openAssistant')}
      >
        <span className="ai-sidebar__toggle-icon">▶</span>
        <span className="ai-sidebar__toggle-text">{t('ai.assistant')}</span>
      </button>
    );
  }

  return (
    <div className={`ai-sidebar ${isOpen ? 'ai-sidebar--open' : ''}`}>
      {/* Mobile Close Button */}
      <button
        className="ai-sidebar__close-mobile"
        onClick={onToggle}
        aria-label={t('ai.closeAssistant')}
      >
        ✕
      </button>
      {/* Content */}
      <div className="ai-sidebar__content">
          {/* Brubru Mascot */}
          <div className="ai-sidebar__mascot-container">
            <img
              src={mascot.src}
              alt={mascot.alt}
              className={`ai-sidebar__mascot ${mascot.className}`}
            />
            <p className="ai-sidebar__mascot-message">
              {isLoading
                ? t('ai.analyzing')
                : aiSuggestion
                ? t('ai.foundAmendment')
                : t('ai.selectRow')}
            </p>
          </div>

          {/* Policy Input */}
          <div className="ai-sidebar__section">
            <h3 className="ai-sidebar__section-title">{t('ai.policyPosition')}</h3>
            <textarea
              className="ai-sidebar__textarea"
              placeholder={t('ai.policyPlaceholder')}
              value={policyText}
              onChange={(e) => setPolicyText(e.target.value)}
              rows={6}
            />
          </div>

          {/* Document Upload */}
          <div className="ai-sidebar__section">
            <h3 className="ai-sidebar__section-title">{t('ai.uploadDocs')}</h3>
            <label className="ai-sidebar__upload-button button button-sm button-secondary">
              📎 {t('ai.uploadButton')}
              <input
                type="file"
                multiple
                accept=".pdf,.doc,.docx,.txt"
                onChange={handleFileUpload}
                style={{ display: 'none' }}
              />
            </label>

            {uploadedDocuments.length > 0 && (
              <div className="ai-sidebar__documents">
                {uploadedDocuments.map((doc, index) => (
                  <div key={index} className="ai-sidebar__document">
                    <span className="ai-sidebar__document-icon">📄</span>
                    <span className="ai-sidebar__document-name">{doc.name}</span>
                    <button
                      className="ai-sidebar__document-remove"
                      onClick={() => handleRemoveDocument(index)}
                      aria-label="Remove document"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Selected Element */}
          <div className="ai-sidebar__section">
            <h3 className="ai-sidebar__section-title">{t('ai.currentlySelected')}</h3>
            {selectedElement ? (
              <div className="ai-sidebar__selected">
                <div className="ai-sidebar__selected-type">
                  {selectedElement.type === 'recital' && `Recital ${selectedElement.number}`}
                  {selectedElement.type === 'article' && `Article ${selectedElement.number}`}
                  {selectedElement.type === 'point' && `Point ${selectedElement.number}`}
                  {selectedElement.type === 'paragraph' && `Paragraph (${selectedElement.letter})`}
                  {selectedElement.type === 'subparagraph' && `Subparagraph (${selectedElement.roman})`}
                </div>
                <div className="ai-sidebar__selected-text">
                  {selectedElement.text.substring(0, 100)}...
                </div>
              </div>
            ) : (
              <p className="ai-sidebar__no-selection">
                {t('ai.clickRow')}
              </p>
            )}
          </div>

          {/* AI Suggest Button */}
          <button
            className="button button-primary ai-sidebar__suggest-button"
            onClick={handleAISuggest}
            disabled={!selectedElement || isLoading}
          >
            {isLoading ? `🤖 ${t('ai.thinking')}` : `🤖 ${t('ai.suggest')}`}
          </button>

          {/* AI Suggestion */}
          {aiSuggestion && (
            <div className="ai-sidebar__suggestion">
              <h3 className="ai-sidebar__suggestion-title">💡 {t('ai.suggestion')}</h3>

              <div className="ai-sidebar__suggestion-content">
                <div className="ai-sidebar__suggestion-field">
                  <strong>{t('ai.type')}</strong> {aiSuggestion.amendment_type}
                </div>

                <div className="ai-sidebar__suggestion-field">
                  <strong>{t('ai.proposedText')}</strong>
                  <div className="ai-sidebar__suggestion-text">
                    {aiSuggestion.proposed_text}
                  </div>
                </div>

                <div className="ai-sidebar__suggestion-field">
                  <strong>{t('ai.justification')}</strong>
                  <div className="ai-sidebar__suggestion-justification">
                    {aiSuggestion.justification}
                  </div>
                </div>
              </div>

              <div className="ai-sidebar__suggestion-actions">
                <button
                  className="button button-sm button-success"
                  onClick={handleAccept}
                >
                  ✓ {t('ai.accept')}
                </button>
                <button
                  className="button button-sm button-secondary"
                  onClick={handleModify}
                >
                  ✎ {t('ai.modify')}
                </button>
                <button
                  className="button button-sm button-danger"
                  onClick={handleReject}
                >
                  ✕ {t('ai.reject')}
                </button>
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
    </div>
  );
};
