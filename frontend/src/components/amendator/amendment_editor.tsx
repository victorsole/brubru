// frontend/src/components/amendator/amendment_editor.tsx
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import type { Amendment, AmendmentType, AmendmentStatus, StructureLevel } from '../../pages/amendator_page';
import { detectChanges } from '../../utils/amendment_formatter';
import './amendment_editor.css';

interface AmendmentEditorProps {
  amendment: Amendment | null;
  onSave: (amendment: Amendment) => void;
  onCancel: () => void;
}

export const AmendmentEditor = ({ amendment, onSave, onCancel }: AmendmentEditorProps) => {
  const { t } = useTranslation();

  // Amendment Type System
  const [type, setType] = useState<AmendmentType>('modification');
  const [structureLevel, setStructureLevel] = useState<StructureLevel>('article');

  // Position and text
  const [position, setPosition] = useState('');
  const [originalText, setOriginalText] = useState('');
  const [proposedText, setProposedText] = useState('');
  const [status, setStatus] = useState<AmendmentStatus>('candidate');

  // Amendment specific flags
  const [isCompleteSupression, setIsCompleteSupression] = useState(false);

  // Optional metadata
  const [justification, setJustification] = useState('');
  const [group, setGroup] = useState('');

  useEffect(() => {
    if (amendment) {
      setType(amendment.type);
      setStructureLevel(amendment.structureLevel);
      setPosition(amendment.position);
      setOriginalText(amendment.originalText);
      setProposedText(amendment.proposedText);
      setStatus(amendment.status);
      setIsCompleteSupression(amendment.isCompleteSupression || false);
      setJustification(amendment.justification || '');
      setGroup(amendment.group || '');
    }
  }, [amendment]);

  const handleSave = () => {
    // Detect text changes for bold italic formatting
    const changes = type === 'modification' ? detectChanges(originalText, proposedText) : undefined;

    const newAmendment: Amendment = {
      id: amendment?.id || Date.now().toString(),

      // Amendment Type System
      type,
      structureLevel,

      // Position and text
      position,
      originalText,
      proposedText,

      // Formatting
      changedWords: changes,
      isCompleteSupression: type === 'suppression' ? isCompleteSupression : undefined,
      isNewAddition: type === 'addition' ? true : undefined,

      // Metadata
      status,
      createdAt: amendment?.createdAt || new Date(),
      updatedAt: new Date(),

      // Optional fields
      justification: justification || undefined,
      group: group || undefined,
    };

    onSave(newAmendment);
    handleClear();
  };

  const handleClear = () => {
    setType('modification');
    setStructureLevel('article');
    setPosition('');
    setOriginalText('');
    setProposedText('');
    setStatus('candidate');
    setIsCompleteSupression(false);
    setJustification('');
    setGroup('');
  };

  const handleAIDraft = () => {
    // Placeholder for AI drafting functionality
    alert(t('amendator.editor.aiDraftComingSoon', 'AI drafting assistance coming soon! This will use Anthropic Claude to help draft amendments.'));
  };

  return (
    <div className="amendment-editor">
      <div className="amendment-editor__content">
        {!amendment && !position ? (
          <div className="amendment-editor__empty">
            <p>{t('amendatorExtras.selectTextPrompt', 'Select text from the original document to start drafting an amendment.')}</p>
            <p className="amendment-editor__empty-hint">
              {t('amendator.editor.emptyHint', 'Or manually configure the amendment details below.')}
            </p>
          </div>
        ) : null}

        {/* Amendment Type Selector */}
        <div className="amendment-editor__field">
          <label htmlFor="type" className="amendment-editor__label">
            {t('amendator.editor.typeLabel', 'Amendment Type')} <span className="amendment-editor__required">*</span>
          </label>
          <select
            id="type"
            className="amendment-editor__select"
            value={type}
            onChange={(e) => setType(e.target.value as AmendmentType)}
          >
            <option value="modification">{t('amendatorExtras.modificationDesc', 'Modification - Change specific words or phrases')}</option>
            <option value="suppression">{t('amendatorExtras.suppressionDesc', 'Suppression - Delete text partially or completely')}</option>
            <option value="addition">{t('amendatorExtras.additionDesc', 'Addition - Insert entirely new text')}</option>
          </select>
          <p className="amendment-editor__hint">
            {type === 'modification' && t('amendator.editor.typeHintModification', 'Original: old words in bold italic. Amendment: new words in bold italic.')}
            {type === 'suppression' && t('amendator.editor.typeHintSuppression', 'Original: deleted text in bold italic. Amendment: remaining text or "Suppressed text".')}
            {type === 'addition' && t('amendator.editor.typeHintAddition', 'Original: "No original text". Amendment: new text in bold italic.')}
          </p>
        </div>

        {/* Structure Level */}
        <div className="amendment-editor__field">
          <label htmlFor="structure-level" className="amendment-editor__label">
            {t('amendator.editor.structureLabel', 'Structure Level')} <span className="amendment-editor__required">*</span>
          </label>
          <select
            id="structure-level"
            className="amendment-editor__select"
            value={structureLevel}
            onChange={(e) => setStructureLevel(e.target.value as StructureLevel)}
          >
            <option value="recital">{t('amendatorExtras.recitalDesc', 'Recital - (1), (2), (3)...')}</option>
            <option value="article">{t('amendatorExtras.articleDesc', 'Article - Article number')}</option>
            <option value="article-title">{t('amendatorExtras.articleTitleDesc', 'Article Title')}</option>
            <option value="point">{t('amendatorExtras.pointDesc', 'Point - 1, 2, 3...')}</option>
            <option value="paragraph">{t('amendatorExtras.paragraphDesc', 'Paragraph - (a), (b), (c)...')}</option>
            <option value="subparagraph">{t('amendatorExtras.subparagraphDesc', 'Subparagraph - (i), (ii), (iii)...')}</option>
          </select>
        </div>

        {/* Position Reference */}
        <div className="amendment-editor__field">
          <label htmlFor="position" className="amendment-editor__label">
            {t('amendator.editor.positionLabel', 'Position Reference')} <span className="amendment-editor__required">*</span>
          </label>
          <input
            id="position"
            type="text"
            className="amendment-editor__input"
            placeholder={
              structureLevel === 'recital' ? t('amendator.editor.positionPhRecital', 'Recital 15') :
              structureLevel === 'article' ? t('amendator.editor.positionPhArticle', 'Article 3') :
              structureLevel === 'point' ? t('amendator.editor.positionPhPoint', 'Article 3, point 2') :
              structureLevel === 'paragraph' ? t('amendator.editor.positionPhParagraph', 'Article 3, point 2, paragraph (a)') :
              t('amendator.editor.positionPhSubparagraph', 'Article 3, point 2, paragraph (a), subparagraph (i)')
            }
            value={position}
            onChange={(e) => setPosition(e.target.value)}
          />
        </div>

        {/* Complete Suppression Toggle (only for suppression type) */}
        {type === 'suppression' && (
          <div className="amendment-editor__field">
            <label className="amendment-editor__checkbox-label">
              <input
                type="checkbox"
                checked={isCompleteSupression}
                onChange={(e) => setIsCompleteSupression(e.target.checked)}
              />
              <span>{t('amendatorExtras.completeSuppression', 'Complete Suppression (entire element)')}</span>
            </label>
            <p className="amendment-editor__hint">
              {isCompleteSupression
                ? t('amendator.editor.completeSuppressionOnHint', 'Will show "Suppressed text" in the amendment column')
                : t('amendator.editor.completeSuppressionOffHint', 'Will show the remaining text after deletion')}
            </p>
          </div>
        )}

        {/* Original Text (disabled for Addition type) */}
        <div className="amendment-editor__field">
          <label htmlFor="original-text" className="amendment-editor__label">
            {t('amendator.editor.originalLabel', 'Original Text')} {type !== 'addition' && <span className="amendment-editor__required">*</span>}
          </label>
          {type === 'addition' ? (
            <div className="amendment-editor__system-message">
              <em>{t('amendatorExtras.noOriginalText', 'No original text')}</em>
              <p className="amendment-editor__hint">
                {t('amendator.editor.additionNoOriginalHint', 'Addition amendments introduce entirely new text with no original reference.')}
              </p>
            </div>
          ) : (
            <textarea
              id="original-text"
              className="amendment-editor__textarea"
              placeholder={t('amendatorExtras.enterOriginalText', 'Enter the original text from the document...')}
              rows={5}
              value={originalText}
              onChange={(e) => setOriginalText(e.target.value)}
            />
          )}
        </div>

        {/* Proposed Text with Track Changes */}
        <div className="amendment-editor__field">
          <label htmlFor="proposed-text" className="amendment-editor__label">
            {t('amendator.editor.proposedLabel', 'Proposed Amendment')} <span className="amendment-editor__required">*</span>
          </label>
          <div className="amendment-editor__toolbar">
            <button
              className="amendment-editor__ai-button button button-accent button-sm"
              onClick={handleAIDraft}
            >
              {t('amendator.editor.aiDraftBtn', 'AI Draft Assistance')}
            </button>
          </div>
          {type === 'suppression' && isCompleteSupression ? (
            <div className="amendment-editor__system-message">
              <em>{t('amendatorExtras.suppressedText', 'Suppressed text')}</em>
              <p className="amendment-editor__hint">
                {t('amendator.editor.completeSuppressionNote', 'Complete suppression removes the entire element. The amendment column will show "Suppressed text".')}
              </p>
            </div>
          ) : (
            <textarea
              id="proposed-text"
              className="amendment-editor__textarea"
              placeholder={
                type === 'addition' ? t('amendator.editor.proposedPhAddition', 'Enter your new text (will be shown in bold italic)...') :
                type === 'suppression' ? t('amendator.editor.proposedPhSuppression', 'Enter the remaining text after deletion...') :
                t('amendator.editor.proposedPhModification', 'Enter your proposed amendment text...')
              }
              rows={8}
              value={proposedText}
              onChange={(e) => setProposedText(e.target.value)}
              disabled={type === 'suppression' && isCompleteSupression}
            />
          )}
          <p className="amendment-editor__hint">
            {type === 'modification' && t('amendator.editor.proposedHintModification', 'Changed words will be automatically highlighted in bold italic.')}
            {type === 'addition' && t('amendator.editor.proposedHintAddition', 'New text will be shown in bold italic in the amendment column.')}
            {type === 'suppression' && !isCompleteSupression && t('amendator.editor.proposedHintSuppression', 'Deleted portions will be marked in bold italic in the original column.')}
          </p>
        </div>

        {/* Optional: Group/Committee Label */}
        <div className="amendment-editor__field">
          <label htmlFor="group" className="amendment-editor__label">
            {t('amendator.editor.groupLabel', 'Group / Committee (Optional)')}
          </label>
          <input
            id="group"
            type="text"
            className="amendment-editor__input"
            placeholder={t('amendatorExtras.groupPlaceholder', 'e.g., LIBE, ECON, EPP, S&D...')}
            value={group}
            onChange={(e) => setGroup(e.target.value)}
          />
          <p className="amendment-editor__hint">
            {t('amendator.editor.groupHint', 'Will appear as a green badge in the amendment grid.')}
          </p>
        </div>

        {/* Optional: Justification */}
        <div className="amendment-editor__field">
          <label htmlFor="justification" className="amendment-editor__label">
            {t('amendator.editor.justificationLabel', 'Justification (Optional)')}
          </label>
          <textarea
            id="justification"
            className="amendment-editor__textarea"
            placeholder={t('amendator.editor.justificationPlaceholder', 'Explain why this amendment is needed...')}
            rows={3}
            value={justification}
            onChange={(e) => setJustification(e.target.value)}
          />
        </div>

        {/* Status Selector */}
        <div className="amendment-editor__field">
          <label htmlFor="status" className="amendment-editor__label">
            {t('amendator.editor.statusLabel', 'Status')}
          </label>
          <select
            id="status"
            className="amendment-editor__select"
            value={status}
            onChange={(e) => setStatus(e.target.value as 'candidate' | 'tabled' | 'withdrawn')}
          >
            <option value="candidate">{t('amendments.candidate', 'Candidate')}</option>
            <option value="tabled">{t('amendments.tabled', 'Tabled')}</option>
            <option value="withdrawn">{t('amendments.withdrawn', 'Withdrawn')}</option>
          </select>
        </div>

        {/* Action Buttons */}
        <div className="amendment-editor__actions">
          <button
            className="amendment-editor__button button button-primary"
            onClick={handleSave}
            disabled={
              !position ||
              (type !== 'addition' && !originalText) ||
              (type !== 'suppression' || !isCompleteSupression) && !proposedText
            }
          >
            {t('amendator.editor.saveAmendmentBtn', 'Save Amendment')}
          </button>
          <button
            className="amendment-editor__button button button-secondary"
            onClick={onCancel}
          >
            {t('common.cancel', 'Cancel')}
          </button>
        </div>
      </div>
    </div>
  );
};
