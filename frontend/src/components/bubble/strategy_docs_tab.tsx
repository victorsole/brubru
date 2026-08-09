/**
 * Strategy Docs tab (MEUB Section 4 - Strategy).
 *
 * A strategy-scoped, file-anchored view over My Documents (document_type='strategy').
 * Bidirectional with My Documents (one store, two views) and reuses the same
 * full-screen DocumentEditor. Adds an autonomous "frame": objective, the file a
 * strategy is anchored to (procedure_reference), status and a starter-template
 * picker. No Anthropic; the editor's AI co-writer stays Mistral-first.
 */
import { useEffect, useMemo, useState } from 'react';
import { ListSkeleton } from '../shared/skeleton';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiBullseyeArrow, mdiPlus, mdiMagnify, mdiFileDocumentEditOutline, mdiDelete,
  mdiLinkVariant, mdiClose, mdiChessKnight, mdiAccountGroupOutline, mdiBullhornOutline,
  mdiAutoFix,
} from '@mdi/js';
import { useBubble, type UserDocument } from '../../hooks/use_bubble';
import { resolveKind, ADVOCACY_KINDS, KIND_ORDER, kindLabel } from '../../utils/document_kinds';
import { useAuth } from '../../hooks/use_auth';
import { stakeholdersService, type SMFile } from '../../services/stakeholders_service';
import { DocumentEditor } from './document_editor';
import { DocumentGeneratorWizard } from './document_generator_wizard';
import { MeubHeader } from './meub_header';
import './strategy_docs_tab.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const STATUSES = ['draft', 'active', 'archived'] as const;
const STATUS_COLOR: Record<string, string> = { draft: '#94a3b8', active: '#059669', archived: '#cbd5e1' };

interface Template { id: string; icon: string; titleKey: string; scaffoldKey: string }
const TEMPLATES: Template[] = [
  { id: 'advocacy', icon: mdiBullhornOutline, titleKey: 'sd.tplAdvocacy', scaffoldKey: 'sd.scaffold.advocacy' },
  { id: 'engagement', icon: mdiAccountGroupOutline, titleKey: 'sd.tplEngagement', scaffoldKey: 'sd.scaffold.engagement' },
  { id: 'positioning', icon: mdiChessKnight, titleKey: 'sd.tplPositioning', scaffoldKey: 'sd.scaffold.positioning' },
];

export function StrategyDocsTab() {
  const { t } = useTranslation();
  const { token } = useAuth();
  const { documents, fetchDocuments, createDocument, updateDocument, deleteDocument } = useBubble();
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [kindFilter, setKindFilter] = useState('all');
  const [editDoc, setEditDoc] = useState<UserDocument | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [showWizard, setShowWizard] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchDocuments({}).finally(() => setLoading(false));
  }, []);

  // The advocacy-outputs hub: strategy + position papers + talking points + briefings +
  // one-pagers + emails + petitions + questions + resolutions + consultation responses +
  // stakeholder maps + amendments. Same store as My Documents (bidirectional).
  const advocacyDocs = useMemo(() => documents.filter((d) => ADVOCACY_KINDS.has(resolveKind(d))), [documents]);
  const presentKinds = useMemo(
    () => KIND_ORDER.filter((k) => advocacyDocs.some((d) => resolveKind(d) === k)), [advocacyDocs]);
  const statusOf = (d: UserDocument) => (d.doc_metadata?.status as string) || 'draft';
  const filtered = useMemo(() => advocacyDocs.filter((d) => {
    if (kindFilter !== 'all' && resolveKind(d) !== kindFilter) return false;
    if (statusFilter !== 'all' && statusOf(d) !== statusFilter) return false;
    if (q) {
      const hay = `${d.title || ''} ${d.objectives || ''}`.toLowerCase();
      if (!hay.includes(q.toLowerCase())) return false;
    }
    return true;
  }), [advocacyDocs, kindFilter, statusFilter, q]);

  const saveFromEditor = async (title: string, markdown: string, asNewVersion: boolean) => {
    if (!editDoc) return;
    if (asNewVersion) {
      const res = await fetch(`${API_BASE_URL}/api/documents/${editDoc.id}/version`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const newDoc = await res.json();
      await updateDocument(newDoc.id, { title, content: markdown });
    } else {
      await updateDocument(editDoc.id, { title, content: markdown } as Partial<UserDocument>);
    }
    fetchDocuments({});
  };

  const setStatus = async (d: UserDocument, status: string) => {
    await updateDocument(d.id, { doc_metadata: { ...(d.doc_metadata || {}), status } } as Partial<UserDocument>);
  };

  const onDelete = async (d: UserDocument) => {
    if (window.confirm(t('sd.confirmDelete', 'Delete this strategy document?'))) {
      await deleteDocument(d.id);
    }
  };

  const onCreate = async (payload: Partial<UserDocument>) => {
    await createDocument({ document_type: 'strategy', doc_metadata: { status: 'draft' }, ...payload });
    setShowNew(false);
    const created = useBubble.getState().documents[0];
    if (created && created.document_type === 'strategy') setEditDoc(created);
  };

  return (
    <div className="sd-tab">
      <MeubHeader
        icon={mdiBullseyeArrow}
        title={t('bubble.strategy_docs', 'Strategy Docs')}
        subtitle={t('sd.subtitle2', 'Everything you produce to influence your files: strategies, position papers, briefings, emails, petitions, questions, amendments and more. In sync with My Documents.')}
        aside={
          <div className="sd-actions">
            <button className="sd-ai" onClick={() => setShowWizard(true)}><Icon path={mdiAutoFix} size={0.8} /> {t('sd.generateAI', 'Generate with AI')}</button>
            <button className="sd-new" onClick={() => setShowNew(true)}><Icon path={mdiPlus} size={0.8} /> {t('sd.new', 'New strategy')}</button>
          </div>
        }
      />

      {presentKinds.length > 1 && (
        <div className="sd-kinds">
          <button className={kindFilter === 'all' ? 'is-active' : ''} onClick={() => setKindFilter('all')}>{t('sd.allKinds', 'All')}</button>
          {presentKinds.map((k) => (
            <button key={k} className={kindFilter === k ? 'is-active' : ''} onClick={() => setKindFilter(k)}>
              {kindLabel(t, k)} <span>{advocacyDocs.filter((d) => resolveKind(d) === k).length}</span>
            </button>
          ))}
        </div>
      )}

      <div className="sd-controls">
        <div className="sm-toggle">
          {['all', ...STATUSES].map((s) => (
            <button key={s} className={statusFilter === s ? 'is-active' : ''} onClick={() => setStatusFilter(s)}>
              {s === 'all' ? t('sd.allStatuses', 'All') : t('sd.status_' + s, s)}
            </button>
          ))}
        </div>
        <div className="sm-search sd-search">
          <Icon path={mdiMagnify} size={0.7} />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('sd.searchPlaceholder', 'Search strategies...')} />
        </div>
      </div>

      {loading ? <ListSkeleton count={4} /> : (
        filtered.length === 0 ? (
          <div className="sd-empty">
            <Icon path={mdiBullseyeArrow} size={1.6} />
            <p>{t('sd.empty', 'No strategy documents yet. Start one from a template.')}</p>
            <button className="sd-new" onClick={() => setShowNew(true)}><Icon path={mdiPlus} size={0.8} /> {t('sd.new', 'New strategy')}</button>
          </div>
        ) : (
          <div className="sd-grid">
            {filtered.map((d) => (
              <div key={d.id} className="sd-card" style={{ borderTopColor: STATUS_COLOR[statusOf(d)] }}>
                <div className="sd-card__top">
                  <span className="sd-kind">{kindLabel(t, resolveKind(d))}</span>
                  <span className="sd-status" style={{ background: STATUS_COLOR[statusOf(d)] + '22', color: STATUS_COLOR[statusOf(d)] }}>{t('sd.status_' + statusOf(d), statusOf(d))}</span>
                  <button className="sd-card__del" onClick={() => onDelete(d)} title={t('common.delete', 'Delete')}><Icon path={mdiDelete} size={0.65} /></button>
                </div>
                <h3>{d.title}</h3>
                {d.objectives && <p className="sd-card__obj">{d.objectives}</p>}
                {d.procedure_reference && (
                  <a className="sd-card__file" href={`https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=${encodeURIComponent(d.procedure_reference)}`} target="_blank" rel="noopener noreferrer">
                    <Icon path={mdiLinkVariant} size={0.55} /> {d.procedure_reference}
                  </a>
                )}
                {d.timeline && <span className="sd-card__deadline">{t('sd.deadline', 'Deadline')}: {d.timeline}</span>}
                <div className="sd-card__actions">
                  <button className="sd-open" onClick={() => setEditDoc(d)}><Icon path={mdiFileDocumentEditOutline} size={0.65} /> {t('sd.open', 'Open')}</button>
                  <select value={statusOf(d)} onChange={(e) => setStatus(d, e.target.value)} aria-label={t('sd.statusLabel', 'Status')}>
                    {STATUSES.map((s) => <option key={s} value={s}>{t('sd.status_' + s, s)}</option>)}
                  </select>
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {showNew && <NewStrategyModal t={t} onClose={() => setShowNew(false)} onCreate={onCreate} />}

      <DocumentGeneratorWizard
        isOpen={showWizard}
        onClose={() => setShowWizard(false)}
        onDocumentGenerated={() => fetchDocuments({})}
      />

      {editDoc && (
        <DocumentEditor
          key={editDoc.id}
          doc={editDoc}
          onClose={() => { setEditDoc(null); fetchDocuments({}); }}
          onSave={saveFromEditor}
        />
      )}
    </div>
  );
}

function NewStrategyModal({ t, onClose, onCreate }: { t: any; onClose: () => void; onCreate: (p: Partial<UserDocument>) => void }) {
  const [tpl, setTpl] = useState<Template>(TEMPLATES[0]);
  const [title, setTitle] = useState('');
  const [objective, setObjective] = useState('');
  const [fileRef, setFileRef] = useState('');
  const [files, setFiles] = useState<SMFile[]>([]);
  const [autoBuild, setAutoBuild] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => { stakeholdersService.files(false).then((r) => setFiles(r.files)).catch(() => {}); }, []);

  const submit = async () => {
    setBusy(true);
    try {
      if (autoBuild && fileRef) {
        const draft = await stakeholdersService.strategyDraft(fileRef);
        await onCreate({
          title: title.trim() || draft.title,
          content: draft.content,
          objectives: objective.trim() || draft.objectives || undefined,
          procedure_reference: fileRef,
          stakeholders: draft.stakeholders,
        });
      } else {
        await onCreate({
          title: title.trim() || t(tpl.titleKey),
          content: t(tpl.scaffoldKey),
          objectives: objective.trim() || undefined,
          procedure_reference: fileRef || undefined,
        });
      }
    } catch {
      setBusy(false);
    }
  };

  return createPortal(
    <div className="sd-modal__scrim" onClick={onClose}>
      <div className="sd-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <button className="sd-modal__close" onClick={onClose}><Icon path={mdiClose} size={0.8} /></button>
        <h3>{t('sd.new', 'New strategy')}</h3>

        <label className="sd-field"><span>{t('sd.template', 'Template')}</span></label>
        <div className="sd-tpls">
          {TEMPLATES.map((x) => (
            <button key={x.id} className={`sd-tpl${tpl.id === x.id ? ' is-active' : ''}`} onClick={() => setTpl(x)}>
              <Icon path={x.icon} size={0.9} /> {t(x.titleKey, x.id)}
            </button>
          ))}
        </div>

        <label className="sd-field"><span>{t('sd.title', 'Title')}</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t(tpl.titleKey)} />
        </label>
        <label className="sd-field"><span>{t('sd.objective', 'Objective')}</span>
          <textarea value={objective} onChange={(e) => setObjective(e.target.value)} rows={2} placeholder={t('sd.objectivePh', 'What outcome do you want, and by when?')} />
        </label>
        <label className="sd-field"><span>{t('sd.anchorFile', 'Anchor to a file (optional)')}</span>
          <select value={fileRef} onChange={(e) => { setFileRef(e.target.value); if (!e.target.value) setAutoBuild(false); }}>
            <option value="">{t('sd.noFile', 'No file')}</option>
            {files.map((f) => <option key={f.ref} value={f.ref}>{(f.title || f.ref).slice(0, 70)}</option>)}
          </select>
        </label>
        {fileRef && (
          <label className="sd-check">
            <input type="checkbox" checked={autoBuild} onChange={(e) => setAutoBuild(e.target.checked)} />
            <span>{t('sd.autoBuild', 'Auto-assemble from this file: decision-makers, who to contact, and who is for and against.')}</span>
          </label>
        )}

        <div className="sd-modal__actions">
          <button className="sd-btn-ghost" onClick={onClose}>{t('common.cancel', 'Cancel')}</button>
          <button className="sd-btn" onClick={submit} disabled={busy}>{busy ? t('sd.creating', 'Creating...') : (autoBuild && fileRef ? t('sd.build', 'Build & edit') : t('sd.create', 'Create & edit'))}</button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

export default StrategyDocsTab;
