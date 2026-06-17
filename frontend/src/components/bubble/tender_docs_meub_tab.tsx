/**
 * Tender Docs tab (MEUB Section 4  Strategy).
 *
 * MEUB wrapper around the Tenderator's TenderDocsTab + TenderDocEditor +
 * TenderDocWizard. The three surfaces (Tenderator Tender Docs, MEUB Tender
 * Docs, MEUB Documents) share the same backend store:
 *   - tender_files (container per funding application)
 *   - user_documents (individual docs, linked via tender_file_id)
 *
 * Edits made here surface immediately in the Tenderator's Tender Docs page
 * AND in MEUB Documents (the "Funding & Tenders" filter), because all three
 * read /api/tender-files/ and /api/documents/.
 *
 * Mirrors strategy_docs_tab.tsx in role: a MEUB tab that exposes a peer
 * authoring surface for one specific doc family (here: tender docs) without
 * forking the data store.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { TenderDocsTab } from '../tenders/tender_docs_tab';
import { TenderDocEditor } from '../tenders/tender_doc_editor';
import { TenderDocWizard } from '../tenders/tender_doc_wizard';
import './tender_docs_meub_tab.css';

type View = 'list' | 'editor';

export function TenderDocsMeubTab() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [view, setView] = useState<View>('list');
  const [activeFileId, setActiveFileId] = useState<string | null>(null);
  const [showWizard, setShowWizard] = useState(false);
  const [wizardPreselectId, setWizardPreselectId] = useState<string | undefined>(undefined);

  const meubSubtitle = t(
    'tenderDocs.meubSubtitle',
    'Everything you write to apply for EU funding. Same store as the Tenderator Tender Docs surface and the My Documents "Funding & Tenders" filter  edit here, see the change everywhere.',
  );

  return (
    <>
      {view === 'list' && (
        <TenderDocsTab
          subtitle={meubSubtitle}
          onOpenFile={(file) => {
            setActiveFileId(file.id);
            setView('editor');
          }}
          onOpenStartWizard={(templateId) => {
            setWizardPreselectId(templateId);
            setShowWizard(true);
          }}
        />
      )}

      {view === 'editor' && activeFileId && (
        <TenderDocEditor
          fileId={activeFileId}
          onBack={() => {
            setActiveFileId(null);
            setView('list');
          }}
        />
      )}

      {showWizard && (
        <TenderDocWizard
          initialTemplateId={wizardPreselectId}
          onClose={() => {
            setShowWizard(false);
            setWizardPreselectId(undefined);
          }}
          onCreated={(fileId) => {
            setShowWizard(false);
            setWizardPreselectId(undefined);
            setActiveFileId(fileId);
            setView('editor');
          }}
        />
      )}

      {view === 'list' && (
        <div className="tender-docs-meub__cross-links" role="note">
          <button
            type="button"
            onClick={() => navigate('/my-eu-bubble?tab=documents&type=funding')}
            className="tender-docs-meub__link-btn"
          >
            {t('tenderDocs.alsoInDocuments', 'Also visible in My Documents  Funding & Tenders')}
          </button>
          <button
            type="button"
            onClick={() => navigate('/tenderator?view=tender-docs')}
            className="tender-docs-meub__link-btn"
          >
            {t('tenderDocs.alsoInTenderator', 'Open in the Tenderator')}
          </button>
        </div>
      )}
    </>
  );
}

export default TenderDocsMeubTab;
