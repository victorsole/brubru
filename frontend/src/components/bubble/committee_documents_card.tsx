// frontend/src/components/bubble/committee_documents_card.tsx
//
// The substantive EP committee-meeting documents tied to a tracked file's OEIL
// procedure - the draft report, amendments, compromise amendments, the opinions
// from associated committees, reasoned opinions, and any agreed text / letter of
// agreement / draft resolution / working document. Grouped by document type,
// newest first, each with a direct PDF link. Surface-not-ingest: the documents
// live only in ep_emeeting_documents; this just reads them by procedure.
//
// Shared by Position Analysis (per-file detail) and the tracked-file detail view.
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiFileDocumentMultipleOutline, mdiFilePdfBox, mdiOpenInNew, mdiAccountVoice,
} from '@mdi/js';
import { positionService } from '../../services/position_service';
import type { EmeetingDocGroup, EmeetingDoc } from '../../services/position_service';
import './committee_documents_card.css';

// Per-kind i18n labels (fallback to the backend-provided plain-language label).
const KIND_I18N: Record<string, string> = {
  draft_report: 'committeeDocs.draftReport',
  amendment: 'committeeDocs.amendments',
  compromise_amendments: 'committeeDocs.compromiseAmendments',
  opinion: 'committeeDocs.opinion',
  draft_opinion: 'committeeDocs.draftOpinion',
  reasoned_opinion: 'committeeDocs.reasonedOpinion',
  agreed_text: 'committeeDocs.agreedText',
  letter_of_agreement: 'committeeDocs.letterOfAgreement',
  draft_resolution: 'committeeDocs.draftResolution',
  working_document: 'committeeDocs.workingDocument',
};

function fmtDate(d: string | null): string {
  if (!d) return '';
  try { return new Date(d).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }); }
  catch { return d; }
}

function DocRow({ doc }: { doc: EmeetingDoc }) {
  const href = doc.pdf_url || doc.source_url || undefined;
  const label = doc.item_title || doc.title || doc.reference || doc.committee_name || doc.committee_code || '';
  const rapps = (doc.rapporteurs || []).filter(Boolean);
  return (
    <li className="cmtdocs-row">
      <a className="cmtdocs-row__link" href={href} target="_blank" rel="noopener noreferrer"
        title={href ? 'Open PDF' : undefined}>
        <Icon path={mdiFilePdfBox} size={0.8} />
        <span className="cmtdocs-row__title">{label}</span>
        {href && <Icon path={mdiOpenInNew} size={0.55} />}
      </a>
      <div className="cmtdocs-row__meta">
        {doc.committee_code && <span className="cmtdocs-row__committee">{doc.committee_code}</span>}
        {doc.meeting_date && <span className="cmtdocs-row__date">{fmtDate(doc.meeting_date)}</span>}
        {rapps.length > 0 && (
          <span className="cmtdocs-row__rapp"><Icon path={mdiAccountVoice} size={0.6} /> {rapps.join(', ')}</span>
        )}
      </div>
    </li>
  );
}

/**
 * Committee documents for one tracked file. Renders nothing (returns null) when
 * the file has no substantive committee documents, so it can be dropped into any
 * detail view without leaving an empty shell.
 */
export default function CommitteeDocumentsCard({ carriageId, compact = false }: {
  carriageId: string;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  const [groups, setGroups] = useState<EmeetingDocGroup[] | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true); setError(false);
    positionService.emeetingDocuments(carriageId)
      .then((r) => { if (alive) { setGroups(r.groups); setTotal(r.total); } })
      .catch(() => { if (alive) setError(true); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [carriageId]);

  // Stay invisible until we know there is something to show.
  if (loading || error || !groups || groups.length === 0) return null;

  return (
    <div className={`cmtdocs ${compact ? 'cmtdocs--compact' : 'pos-card'}`}>
      <div className={compact ? 'cmtdocs__head' : 'pos-card__header'}>
        <Icon path={mdiFileDocumentMultipleOutline} size={compact ? 0.9 : 1} />
        <h3>{t('committeeDocs.title', 'Committee documents')}</h3>
        <span className="cmtdocs__count">{total}</span>
      </div>
      <p className="cmtdocs__note pos-foot-note">
        {t('committeeDocs.note', 'Documents tabled in the committee that owns this file, straight from the European Parliament. Each links to the original PDF.')}
      </p>
      {groups.map((g) => (
        <section key={g.kind} className="cmtdocs__group">
          <h4 className="cmtdocs__group-label">
            {t(KIND_I18N[g.kind] || '', g.label)}
            <span className="cmtdocs__group-count">{g.documents.length}</span>
          </h4>
          <ul className="cmtdocs__list">
            {g.documents.map((d, i) => <DocRow key={`${g.kind}-${i}`} doc={d} />)}
          </ul>
        </section>
      ))}
    </div>
  );
}
