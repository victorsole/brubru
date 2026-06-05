/**
 * Drafted Document Card
 *
 * Shown inline in chat when Brubru auto-drafts a document in response to a
 * user request (e.g. "draft a position paper on the AI Act"). Lets the user
 * (a) read a short preview, (b) jump straight to the document in My EU Bubble
 * → Documents to edit / export / version it.
 *
 * Companion experience: instead of telling the user "I'll open the wizard",
 * we hand them the finished draft and the edit link.
 */

import { useNavigate } from 'react-router-dom';
import Icon from '@mdi/react';
import {
  mdiFileDocumentEditOutline,
  mdiPencilOutline,
  mdiOpenInNew,
  mdiFileDocumentOutline,
  mdiPresentation,
  mdiBullhornOutline,
  mdiAccountGroupOutline,
  mdiClipboardListOutline,
  mdiCommentQuestionOutline,
  mdiScriptTextOutline,
  mdiMessageText,
  mdiEmailOutline,
} from '@mdi/js';
import type { DraftedDocument } from './chat_interface';
import './drafted_document_card.css';

const SUBTYPE_META: Record<string, { label: string; icon: string; color: string }> = {
  one_pager:         { label: 'One-pager',          icon: mdiFileDocumentEditOutline, color: '#16a34a' },
  position_paper:    { label: 'Position paper',     icon: mdiFileDocumentOutline,     color: '#2e7d32' },
  mep_briefing:      { label: 'MEP briefing',       icon: mdiFileDocumentOutline,     color: '#1565c0' },
  talking_points:    { label: 'Talking points',     icon: mdiMessageText,             color: '#7b1fa2' },
  resolution:        { label: 'EP resolution',      icon: mdiScriptTextOutline,       color: '#b91c1c' },
  ep_question:       { label: 'EP written question', icon: mdiCommentQuestionOutline, color: '#0693e3' },
  eu_email:          { label: 'EU email',           icon: mdiEmailOutline,            color: '#0d9488' },
  press_release:     { label: 'EU press release',   icon: mdiBullhornOutline,         color: '#ea580c' },
  stakeholder_map:   { label: 'Stakeholder map',    icon: mdiAccountGroupOutline,     color: '#4f46e5' },
  impact_assessment: { label: 'Impact assessment',  icon: mdiClipboardListOutline,    color: '#0891b2' },
  presentation:      { label: 'Presentation',       icon: mdiPresentation,            color: '#a21caf' },
};

interface DraftedDocumentCardProps {
  drafted: DraftedDocument;
}

export const DraftedDocumentCard = ({ drafted }: DraftedDocumentCardProps) => {
  const navigate = useNavigate();
  const meta = SUBTYPE_META[drafted.document_subtype] || {
    label: 'Document',
    icon: mdiFileDocumentOutline,
    color: '#0066cc',
  };

  const handleOpen = () => {
    // Route via react-router so the SPA picks up ?docId.
    navigate(drafted.edit_url);
  };

  return (
    <div
      className="drafted-doc-card"
      style={{ ['--drafted-accent' as string]: meta.color } as React.CSSProperties}
    >
      <div className="drafted-doc-card__header">
        <span className="drafted-doc-card__icon" aria-hidden="true">
          <Icon path={meta.icon} size={0.85} color={meta.color} />
        </span>
        <div className="drafted-doc-card__head-text">
          <span className="drafted-doc-card__kind">{meta.label}</span>
          <h4 className="drafted-doc-card__title">{drafted.title}</h4>
        </div>
        <span className="drafted-doc-card__words">{drafted.word_count} words</span>
      </div>

      <p className="drafted-doc-card__preview">{drafted.preview}</p>

      <div className="drafted-doc-card__actions">
        <button type="button" className="drafted-doc-card__primary" onClick={handleOpen}>
          <Icon path={mdiPencilOutline} size={0.75} />
          Open and edit in Documents
        </button>
        <a
          className="drafted-doc-card__secondary"
          href={drafted.edit_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Icon path={mdiOpenInNew} size={0.7} />
          Open in new tab
        </a>
      </div>
    </div>
  );
};
