// frontend/src/components/amendator/amendment_editor.tsx
import { useState, useEffect } from 'react';
import type { Amendment } from '../../pages/amendator_page';
import './amendment_editor.css';

interface AmendmentEditorProps {
  amendment: Amendment | null;
  onSave: (amendment: Amendment) => void;
  onCancel: () => void;
}

export const AmendmentEditor = ({ amendment, onSave, onCancel }: AmendmentEditorProps) => {
  const [position, setPosition] = useState('');
  const [originalText, setOriginalText] = useState('');
  const [proposedText, setProposedText] = useState('');
  const [status, setStatus] = useState<'candidate' | 'tabled' | 'withdrawn'>('candidate');

  useEffect(() => {
    if (amendment) {
      setPosition(amendment.position);
      setOriginalText(amendment.originalText);
      setProposedText(amendment.proposedText);
      setStatus(amendment.status);
    }
  }, [amendment]);

  const handleSave = () => {
    const newAmendment: Amendment = {
      id: amendment?.id || Date.now().toString(),
      position,
      originalText,
      proposedText,
      status,
      createdAt: amendment?.createdAt || new Date(),
    };
    onSave(newAmendment);
    handleClear();
  };

  const handleClear = () => {
    setPosition('');
    setOriginalText('');
    setProposedText('');
    setStatus('candidate');
  };

  const handleAIDraft = () => {
    // Placeholder for AI drafting functionality
    alert('AI drafting assistance coming soon! This will use Anthropic Claude to help draft amendments.');
  };

  return (
    <div className="amendment-editor">
      <div className="amendment-editor__content">
        {!amendment && !position ? (
          <div className="amendment-editor__empty">
            <p>Select text from the original document to start drafting an amendment.</p>
            <p className="amendment-editor__empty-hint">
              Or manually enter the position reference below.
            </p>
          </div>
        ) : null}

        {/* Position Reference */}
        <div className="amendment-editor__field">
          <label htmlFor="position" className="amendment-editor__label">
            Position Reference
          </label>
          <input
            id="position"
            type="text"
            className="amendment-editor__input"
            placeholder="Article X, paragraph Y, point (a)"
            value={position}
            onChange={(e) => setPosition(e.target.value)}
          />
        </div>

        {/* Original Text */}
        <div className="amendment-editor__field">
          <label htmlFor="original-text" className="amendment-editor__label">
            Original Text
          </label>
          <textarea
            id="original-text"
            className="amendment-editor__textarea"
            placeholder="Enter the original text from the document..."
            rows={5}
            value={originalText}
            onChange={(e) => setOriginalText(e.target.value)}
          />
        </div>

        {/* Proposed Text with Track Changes */}
        <div className="amendment-editor__field">
          <label htmlFor="proposed-text" className="amendment-editor__label">
            Proposed Amendment
          </label>
          <div className="amendment-editor__toolbar">
            <button
              className="amendment-editor__ai-button button button-accent button-sm"
              onClick={handleAIDraft}
            >
              AI Draft Assistance
            </button>
          </div>
          <textarea
            id="proposed-text"
            className="amendment-editor__textarea"
            placeholder="Enter your proposed amendment text..."
            rows={8}
            value={proposedText}
            onChange={(e) => setProposedText(e.target.value)}
          />
          <p className="amendment-editor__hint">
            Use <strong>bold</strong> for additions and <del>strikethrough</del> for deletions
          </p>
        </div>

        {/* Status Selector */}
        <div className="amendment-editor__field">
          <label htmlFor="status" className="amendment-editor__label">
            Status
          </label>
          <select
            id="status"
            className="amendment-editor__select"
            value={status}
            onChange={(e) => setStatus(e.target.value as 'candidate' | 'tabled' | 'withdrawn')}
          >
            <option value="candidate">Candidate</option>
            <option value="tabled">Tabled</option>
            <option value="withdrawn">Withdrawn</option>
          </select>
        </div>

        {/* Action Buttons */}
        <div className="amendment-editor__actions">
          <button
            className="amendment-editor__button button button-primary"
            onClick={handleSave}
            disabled={!position || !originalText || !proposedText}
          >
            Save Amendment
          </button>
          <button
            className="amendment-editor__button button button-secondary"
            onClick={onCancel}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};
