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
import { useTranslation } from 'react-i18next';
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

// Labels are i18n keys resolved with t() at render time; labelDefault is the
// English fallback shown when a locale is missing the key.
const SUBTYPE_META: Record<string, { labelKey: string; labelDefault: string; icon: string; color: string }> = {
  one_pager:         { labelKey: 'chat.draftedDoc.onePager',         labelDefault: 'One-pager',           icon: mdiFileDocumentEditOutline, color: '#16a34a' },
  position_paper:    { labelKey: 'chat.draftedDoc.positionPaper',    labelDefault: 'Position paper',      icon: mdiFileDocumentOutline,     color: '#2e7d32' },
  mep_briefing:      { labelKey: 'chat.draftedDoc.mepBriefing',      labelDefault: 'MEP briefing',        icon: mdiFileDocumentOutline,     color: '#1565c0' },
  talking_points:    { labelKey: 'chat.draftedDoc.talkingPoints',    labelDefault: 'Talking points',      icon: mdiMessageText,             color: '#7b1fa2' },
  resolution:        { labelKey: 'chat.draftedDoc.resolution',       labelDefault: 'EP resolution',       icon: mdiScriptTextOutline,       color: '#b91c1c' },
  ep_question:       { labelKey: 'chat.draftedDoc.epQuestion',       labelDefault: 'EP written question', icon: mdiCommentQuestionOutline,  color: '#0693e3' },
  eu_email:          { labelKey: 'chat.draftedDoc.euEmail',          labelDefault: 'EU email',            icon: mdiEmailOutline,            color: '#0d9488' },
  press_release:     { labelKey: 'chat.draftedDoc.pressRelease',     labelDefault: 'EU press release',    icon: mdiBullhornOutline,         color: '#ea580c' },
  stakeholder_map:   { labelKey: 'chat.draftedDoc.stakeholderMap',   labelDefault: 'Stakeholder map',     icon: mdiAccountGroupOutline,     color: '#4f46e5' },
  impact_assessment: { labelKey: 'chat.draftedDoc.impactAssessment', labelDefault: 'Impact assessment',   icon: mdiClipboardListOutline,    color: '#0891b2' },
  presentation:      { labelKey: 'chat.draftedDoc.presentation',     labelDefault: 'Presentation',        icon: mdiPresentation,            color: '#a21caf' },
};

interface DraftedDocumentCardProps {
  drafted: DraftedDocument;
}

export const DraftedDocumentCard = ({ drafted }: DraftedDocumentCardProps) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const meta = SUBTYPE_META[drafted.document_subtype] || {
    labelKey: 'chat.draftedDoc.document',
    labelDefault: 'Document',
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
          <span className="drafted-doc-card__kind">{t(meta.labelKey, meta.labelDefault)}</span>
          <h4 className="drafted-doc-card__title">{drafted.title}</h4>
        </div>
        <span className="drafted-doc-card__words">{drafted.word_count} words</span>
      </div>

      <p className="drafted-doc-card__preview">{drafted.preview}</p>

      <div className="drafted-doc-card__actions">
        <button type="button" className="drafted-doc-card__primary" onClick={handleOpen}>
          <Icon path={mdiPencilOutline} size={0.75} />
          {t('chat.draftedDoc.openEdit', 'Open and edit in Documents')}
        </button>
        <a
          className="drafted-doc-card__secondary"
          href={drafted.edit_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Icon path={mdiOpenInNew} size={0.7} />
          {t('chat.draftedDoc.openNewTab', 'Open in new tab')}
        </a>
      </div>
    </div>
  );
};
