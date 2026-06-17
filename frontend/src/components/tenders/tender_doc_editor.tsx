/**
 * Tender Doc Editor 3-column canvas for one tender_file.
 *
 * Left rail: doc checklist (template's documents[])
 * Center: active doc markdown textarea with section outline overlay
 * + per-section "Draft with AI" button
 * Right rail: tabbed context Topic / Org Profile / AI co-writer / Comply / Past winners
 *
 * The AI co-writer uses POST /api/generate/tender-section which runs through
 * the SAME multi-provider chain as MEUB Documents + Strategy Docs (Cerebras
 * → Gemini → ... → OpenAI). No new AI plumbing.
 *
 * Green disclaimer at the top conveys the current scaffold version.
 */
import { useEffect, useState, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/use_auth';
import { marked } from 'marked';
import './tender_doc_editor.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface TenderFileDoc {
 id: string;
 title: string;
 document_type: string;
 tags: string[];
 doc_metadata: Record<string, unknown>;
 word_count: number;
 updated_at?: string;
 created_at?: string;
}

interface TemplateSection {
 id: string;
 label: string;
 page_budget?: number;
 criterion?: string | null;
 prompts?: string[];
 sub?: TemplateSection[];
 conditional?: Record<string, unknown>;
}

interface TemplateDoc {
 kind: string;
 title: string;
 page_limit?: number | null;
 formatting?: { font?: string; page_size?: string; margins_mm?: number };
 render?: string;
 ai_disclosure_required?: boolean;
 sections?: TemplateSection[];
 scaffold_slides?: string[];
 constraints?: Record<string, unknown>;
 conditional?: Record<string, unknown>;
 note?: string;
}

interface ReferenceDoc {
 label: string;
 url: string;
 category?: string;
}

interface Template {
 id: string;
 name: string;
 programme: string;
 sub_instrument?: string;
 stage?: string;
 scaffold_version: string;
 official_template_url?: string;
 kb_guide?: string;
 documents: TemplateDoc[];
 comply_targets?: string[];
 hand_offs?: { next_stage?: string; chat_cta?: string; comply_cta?: string };
 // Enrichment from EuropeanAcademy index (17 Jun 2026): the official EU
 // post-award reference set per programme. Surfaced in the Topic tab.
 model_grant_agreement_url?: string | null;
 annotated_grant_agreement_url?: string | null;
 reference_docs?: ReferenceDoc[];
}

interface TenderFileResponse {
 id: string;
 title: string;
 programme: string;
 sub_instrument?: string;
 stage?: string;
 topic_id?: string;
 topic_variant?: string;
 funding_mode?: string;
 deadline_iso?: string;
 status: string;
 template_id: string;
 scaffold_version: string;
 extra: Record<string, unknown>;
 documents: TenderFileDoc[];
 template: Template;
}

interface ComplyCluster {
 id: number;
 name: string;
 description: string;
 policy_area: string;
 law_count: number;
 requirement_count: number;
 match_reason: string[];
}

interface TenderProfile {
 company_name?: string;
 company_size?: string;
 sectors_description?: string;
 countries_of_interest?: string[];
 keywords?: string[];
 certifications?: string[];
}

interface TenderDocEditorProps {
 fileId: string;
 onBack: () => void;
}

export const TenderDocEditor = ({ fileId, onBack }: TenderDocEditorProps) => {
 const { t } = useTranslation();
 const { token } = useAuth();

 const [data, setData] = useState<TenderFileResponse | null>(null);
 const [loading, setLoading] = useState(true);
 const [error, setError] = useState<string | null>(null);

 const [activeDocId, setActiveDocId] = useState<string | null>(null);
 const [docContent, setDocContent] = useState<string>('');
 const [docDirty, setDocDirty] = useState(false);
 const [saving, setSaving] = useState(false);
 // View / Edit mode (mirrors MEUB Documents view modal + edit modal pattern).
 // Default is 'view' so the user sees rendered HTML instead of raw markdown.
 const [editMode, setEditMode] = useState<'view' | 'edit'>('view');

 const [activeSectionId, setActiveSectionId] = useState<string | null>(null);
 const [aiBusy, setAiBusy] = useState(false);

 const [rightTab, setRightTab] = useState<'topic' | 'org' | 'ai' | 'comply' | 'winners'>('topic');
 const [comply, setComply] = useState<ComplyCluster[] | null>(null);
 const [complyLoading, setComplyLoading] = useState(false);
 const [orgProfile, setOrgProfile] = useState<TenderProfile | null>(null);

 // Load tender_file
 const reload = useCallback(async () => {
 if (!token) return;
 setLoading(true);
 setError(null);
 try {
 const r = await fetch(`${API_URL}/api/tender-files/${fileId}`, { headers: { Authorization: `Bearer ${token}` } });
 if (!r.ok) throw new Error(`HTTP ${r.status}`);
 const d = await r.json();
 setData(d);
 if (d.documents?.length && !activeDocId) {
 setActiveDocId(d.documents[0].id);
 }
 } catch (e) {
 setError((e as Error).message);
 } finally {
 setLoading(false);
 }
 }, [token, fileId, activeDocId]);

 useEffect(() => { reload(); /* eslint-disable-next-line */ }, [fileId]);

 // Load org profile from Tenderator
 useEffect(() => {
 let cancelled = false;
 (async () => {
 if (!token) return;
 try {
 const r = await fetch(`${API_URL}/api/tenders/profile/me`, { headers: { Authorization: `Bearer ${token}` } });
 if (r.ok) {
 const d = await r.json();
 if (!cancelled) setOrgProfile(d);
 }
 } catch (e) { /* swallow profile is optional context */ }
 })();
 return () => { cancelled = true; };
 }, [token]);

 // Fetch the active doc's content (the embedded `documents` array only carries metadata).
 useEffect(() => {
 let cancelled = false;
 (async () => {
 if (!activeDocId || !token) return;
 try {
 const r = await fetch(`${API_URL}/api/documents/${activeDocId}`, { headers: { Authorization: `Bearer ${token}` } });
 if (!r.ok) return;
 const d = await r.json();
 if (!cancelled) {
 setDocContent(d.content || '');
 setDocDirty(false);
 }
 } catch (e) { console.warn('Could not load doc:', e); }
 })();
 return () => { cancelled = true; };
 }, [activeDocId, token]);

 // Load Comply when right tab is "comply"
 useEffect(() => {
 let cancelled = false;
 (async () => {
 if (rightTab !== 'comply' || !data || !token) return;
 setComplyLoading(true);
 try {
 const params = new URLSearchParams({ template_id: data.template_id });
 if (data.funding_mode) params.set('funding_mode', data.funding_mode);
 const r = await fetch(`${API_URL}/api/eu-law-comply/by-topic-clusters?${params}`, {
 headers: { Authorization: `Bearer ${token}` },
 });
 if (!r.ok) {
 if (r.status === 403) {
 if (!cancelled) setComply([]);
 return;
 }
 throw new Error(`HTTP ${r.status}`);
 }
 const d = await r.json();
 if (!cancelled) setComply(d.clusters || []);
 } catch (e) {
 console.warn('Could not load comply:', e);
 if (!cancelled) setComply([]);
 } finally {
 if (!cancelled) setComplyLoading(false);
 }
 })();
 return () => { cancelled = true; };
 }, [rightTab, data, token]);

 const activeDoc = useMemo(() => {
 if (!data || !activeDocId) return null;
 return data.documents.find((d) => d.id === activeDocId) || null;
 }, [data, activeDocId]);

 const activeDocSpec = useMemo<TemplateDoc | null>(() => {
 if (!data || !activeDoc) return null;
 const kind = (activeDoc.doc_metadata as { doc_kind?: string }).doc_kind || activeDoc.tags?.[0];
 return data.template.documents.find((d) => d.kind === kind) || null;
 }, [data, activeDoc]);

 const saveDoc = async () => {
 if (!activeDocId || !token) return;
 setSaving(true);
 try {
 await fetch(`${API_URL}/api/documents/${activeDocId}`, {
 method: 'PATCH',
 headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
 body: JSON.stringify({ content: docContent }),
 });
 setDocDirty(false);
 } catch (e) {
 console.error('save failed', e);
 } finally {
 setSaving(false);
 }
 };

 const draftSectionWithAI = async (sectionId: string) => {
 if (!data || !activeDocSpec) return;
 setAiBusy(true);
 setActiveSectionId(sectionId);
 try {
 const body: Record<string, unknown> = {
 template_id: data.template_id,
 section_id: sectionId,
 };
 if (data.funding_mode) body.funding_mode = data.funding_mode;
 if (data.topic_id) body.topic_id = data.topic_id;
 if (data.topic_variant) body.topic_variant = data.topic_variant;
 if (orgProfile) {
 body.org_context = {
 company_name: orgProfile.company_name,
 company_size: orgProfile.company_size,
 sectors_description: orgProfile.sectors_description,
 keywords: (orgProfile.keywords || []).slice(0, 12).join(', '),
 };
 }
 const r = await fetch(`${API_URL}/api/generate/tender-section`, {
 method: 'POST',
 headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
 body: JSON.stringify(body),
 });
 if (!r.ok) {
 const err = await r.json().catch(() => ({ detail: 'AI generation failed' }));
 throw new Error(typeof err.detail === 'string' ? err.detail : 'AI generation failed');
 }
 const out = await r.json();

 // Insert the AI markdown INTO the matching section heading in the doc
 // (the seeded skeleton already has the heading lines). Strategy:
 // (a) find the section's label as a heading line (## or ### prefix);
 // (b) if found, insert the AI block right after it, BEFORE the next heading;
 // (c) if not found (user deleted the heading), append at the end with a header.
 const sectionLabel: string = out.section?.label || sectionId;
 const aiBlock = `${out.markdown.trim()}\n`;
 setDocContent((prev) => {
 const content = prev || '';
 // Match the heading line containing the section's label (## or ###).
 const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
 const headingRe = new RegExp(`^(#{1,6})\\s+.*${escape(sectionLabel)}.*$`, 'm');
 const headingMatch = content.match(headingRe);
 if (headingMatch && headingMatch.index !== undefined) {
 const idxAfterHeading = headingMatch.index + headingMatch[0].length;
 // Find the next heading line after this one (the boundary of this section).
 const tail = content.slice(idxAfterHeading);
 const nextHeadingRe = /\n(#{1,6})\s+/m;
 const nextMatch = tail.match(nextHeadingRe);
 const boundary = nextMatch && nextMatch.index !== undefined
 ? idxAfterHeading + nextMatch.index
 : content.length;
 const before = content.slice(0, idxAfterHeading);
 const inside = content.slice(idxAfterHeading, boundary).replace(/^\s+/, '');
 const after = content.slice(boundary);
 // If the section is empty (just heading + blank space), drop in; otherwise
 // append the AI block beneath any existing prose, before the next heading.
 const merged = inside.trim().length === 0
 ? `\n\n${aiBlock}\n${after}`
 : `\n\n${inside.trim()}\n\n${aiBlock}\n${after.startsWith('\n') ? after : '\n' + after}`;
 return before + merged;
 }
 // Fallback: heading not found, append at end with the heading reinstated.
 return `${content}\n\n### ${sectionLabel}\n\n${aiBlock}`;
 });
 setDocDirty(true);
 // After insertion, keep the user in Edit mode briefly so they can see the
 // change land; switch back to View mode is a manual choice.
 setEditMode('edit');
 } catch (e) {
 alert(`AI draft failed: ${(e as Error).message}`);
 } finally {
 setAiBusy(false);
 }
 };

 const addAnotherDoc = async (kind: string) => {
 if (!data || !token) return;
 try {
 const r = await fetch(`${API_URL}/api/tender-files/${data.id}/documents`, {
 method: 'POST',
 headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
 body: JSON.stringify({ kind }),
 });
 if (!r.ok) throw new Error(`HTTP ${r.status}`);
 const d = await r.json();
 await reload();
 setActiveDocId(d.id);
 } catch (e) {
 alert(`Add doc failed: ${(e as Error).message}`);
 }
 };

 const updateStatus = async (newStatus: string) => {
 if (!data || !token) return;
 await fetch(`${API_URL}/api/tender-files/${data.id}`, {
 method: 'PATCH',
 headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
 body: JSON.stringify({ status: newStatus }),
 });
 reload();
 };

 // Cross-feature hand-offs. EU Law Comply + Chat open in NEW tabs so the
 // browser back button preserves the user's Tender Doc editor state.
 const openComply = () => {
 if (!data) return;
 const params = new URLSearchParams();
 params.set('template_id', data.template_id);
 if (data.funding_mode) params.set('funding_mode', data.funding_mode);
 if (data.topic_id) params.set('topic', data.topic_id);
 window.open(`/eulawcomply?${params.toString()}`, '_blank', 'noopener,noreferrer');
 };
 const useInChat = () => {
 if (!data || !activeDoc) return;
 const q = data.template.hand_offs?.chat_cta || `Help me improve my ${data.template.name} draft.`;
 const params = new URLSearchParams({ q });
 window.open(`/chat?${params.toString()}`, '_blank', 'noopener,noreferrer');
 };
 const openSourceTender = () => {
 if (!data || !data.topic_id) return;
 window.open(`https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/${data.topic_id}`, '_blank');
 };

 if (loading) {
 return (
 <div className="td-edit__loading">
 <span className="mdi mdi-loading mdi-spin" /> {t('tenderator.docEditor.loading')}
 </div>
 );
 }
 if (error || !data) {
 return (
 <div className="td-edit__error">
 <span className="mdi mdi-alert-circle" /> {error || t('tenderator.docEditor.couldNotLoadTenderFile')}
 <button onClick={onBack}>{t('tenderator.docEditor.back')}</button>
 </div>
 );
 }

 // Build the unseeded doc-kinds list the user can add them à-la-carte
 const seededKinds = new Set(data.documents.map((d) => (d.doc_metadata as { doc_kind?: string }).doc_kind || d.tags?.[0]));
 const availableKinds = data.template.documents.filter((d) => !seededKinds.has(d.kind));

 return (
 <div className="td-edit">
 {/* Top bar */}
 <div className="td-edit__topbar">
 <button className="td-edit__back" onClick={onBack} aria-label={t('tenderator.docEditor.backToTenderDocs')}>
 <span className="mdi mdi-arrow-left" />
 </button>
 <div className="td-edit__topbar-info">
 <div className="td-edit__topbar-title">{data.title}</div>
 <div className="td-edit__topbar-meta">
 <span>{data.template.name}</span>
 {data.funding_mode && <><span>·</span><span>{data.funding_mode}</span></>}
 {data.topic_id && <><span>·</span><code>{data.topic_id}</code></>}
 </div>
 </div>
 <div className="td-edit__topbar-actions">
 <select value={data.status} onChange={(e) => updateStatus(e.target.value)}>
 <option value="drafting">{t('tenderator.docEditor.statusDrafting')}</option>
 <option value="ready-to-submit">{t('tenderator.docEditor.statusReadyToSubmit')}</option>
 <option value="submitted">{t('tenderator.docEditor.statusSubmitted')}</option>
 <option value="won">{t('tenderator.docEditor.statusWon')}</option>
 <option value="lost">{t('tenderator.docEditor.statusLost')}</option>
 <option value="seal-of-excellence">{t('tenderator.docEditor.statusSealOfExcellence')}</option>
 </select>
 </div>
 </div>

 {/* Green disclaimer */}
 <div className="td-edit__disclaimer" title={t('tenderator.docEditor.disclaimerTooltip')}>
 <span className="mdi mdi-check-decagram" />
 {t('tenderator.docEditor.disclaimerText', { version: data.scaffold_version, name: data.template.name })}
 {data.template.official_template_url && (
 <a href={data.template.official_template_url} target="_blank" rel="noreferrer">
 {t('tenderator.docEditor.viewSource')} <span className="mdi mdi-open-in-new" />
 </a>
 )}
 </div>

 {/* 3-column body */}
 <div className="td-edit__cols">
 {/* LEFT RAIL: doc checklist */}
 <aside className="td-edit__left">
 <h4>{t('tenderator.docEditor.documentsInThisFile')}</h4>
 <ul className="td-edit__doc-list">
 {data.documents.map((d) => {
 const kind = (d.doc_metadata as { doc_kind?: string }).doc_kind || d.tags?.[0];
 const spec = data.template.documents.find((x) => x.kind === kind);
 const pageLimit = spec?.page_limit;
 const wordsApprox = d.word_count;
 const onTrack = !pageLimit || wordsApprox <= pageLimit * 300;
 return (
 <li
 key={d.id}
 className={`td-edit__doc-item ${d.id === activeDocId ? 'is-active' : ''}`}
 onClick={() => { setActiveDocId(d.id); setActiveSectionId(null); }}
 >
 <div className="td-edit__doc-item-title">{spec?.title || d.title}</div>
 <div className="td-edit__doc-item-meta">
 {t('tenderator.docEditor.wordCount', { count: wordsApprox })}
 {pageLimit && <> · {t('tenderator.docEditor.maxPages', { limit: pageLimit })}</>}
 {!onTrack && <span className="td-edit__warning"> · {t('tenderator.docEditor.overBudget')}</span>}
 </div>
 </li>
 );
 })}
 </ul>
 {availableKinds.length > 0 && (
 <>
 <h4 style={{ marginTop: '1rem' }}>+ {t('tenderator.docEditor.addAnotherDoc')}</h4>
 <ul className="td-edit__add-list">
 {availableKinds.map((spec) => (
 <li key={spec.kind}>
 <button onClick={() => addAnotherDoc(spec.kind)}>
 <span className="mdi mdi-plus" /> {spec.title}
 </button>
 </li>
 ))}
 </ul>
 </>
 )}
 </aside>

 {/* CENTER: editor */}
 <main className="td-edit__center">
 {activeDoc && activeDocSpec && (
 <>
 <div className="td-edit__center-head">
 <h3>{activeDocSpec.title}</h3>
 <div className="td-edit__center-meta">
 {activeDocSpec.page_limit && <span>{t('tenderator.docEditor.pageLimit', { limit: activeDocSpec.page_limit })}</span>}
 {activeDocSpec.formatting?.font && <span> · {activeDocSpec.formatting.font}</span>}
 {activeDocSpec.formatting?.page_size && <span> · {activeDocSpec.formatting.page_size}</span>}
 </div>
 </div>

 {/* Section outline overlay */}
 {(activeDocSpec.sections || []).length > 0 && (
 <details className="td-edit__outline" open>
 <summary>
 {t('tenderator.docEditor.sectionOutline', { count: (activeDocSpec.sections || []).length })}
 </summary>
 <div className="td-edit__outline-list">
 {(activeDocSpec.sections || []).map((section) => (
 <div key={section.id} className="td-edit__outline-section">
 <div className="td-edit__outline-section-head">
 <strong>{section.label}</strong>
 {section.criterion && <span className="td-edit__crit">{section.criterion}</span>}
 {section.page_budget && <span className="td-edit__pb">{section.page_budget} pp</span>}
 <button
 className="td-edit__draft-btn"
 disabled={aiBusy && activeSectionId === section.id}
 onClick={() => draftSectionWithAI(section.id)}
 >
 {aiBusy && activeSectionId === section.id ? t('tenderator.docEditor.drafting') : t('tenderator.docEditor.draftWithAI')}
 </button>
 </div>
 {(section.sub || []).map((sub) => (
 <div key={sub.id} className="td-edit__outline-sub">
 <strong>{sub.label}</strong>
 <button
 className="td-edit__draft-btn td-edit__draft-btn--sm"
 disabled={aiBusy && activeSectionId === sub.id}
 onClick={() => draftSectionWithAI(sub.id)}
 >
 {aiBusy && activeSectionId === sub.id ? t('tenderator.docEditor.drafting') : t('tenderator.docEditor.draftSubsection')}
 </button>
 </div>
 ))}
 </div>
 ))}
 </div>
 </details>
 )}

 {/* Pitch deck scaffold preview */}
 {activeDocSpec.scaffold_slides && (
 <div className="td-edit__slides">
 <h4>{t('tenderator.docEditor.suggestedSlidePattern')}</h4>
 <ol>
 {activeDocSpec.scaffold_slides.map((s, i) => <li key={i}>{s}</li>)}
 </ol>
 </div>
 )}

 {/* View / Edit toggle — mirrors MEUB Documents' view + edit pattern */}
 <div className="td-edit__mode-toggle" role="tablist" aria-label={t('tenderator.docEditor.documentMode')}>
 <button
 type="button"
 role="tab"
 aria-selected={editMode === 'view'}
 className={editMode === 'view' ? 'is-active' : ''}
 onClick={() => setEditMode('view')}
 >
 <span className="mdi mdi-eye-outline" /> {t('tenderator.docEditor.preview')}
 </button>
 <button
 type="button"
 role="tab"
 aria-selected={editMode === 'edit'}
 className={editMode === 'edit' ? 'is-active' : ''}
 onClick={() => setEditMode('edit')}
 >
 <span className="mdi mdi-pencil-outline" /> {t('tenderator.docEditor.edit')}
 </button>
 </div>

 {/* Body: rendered HTML in view mode, textarea in edit mode (same pattern as MEUB Documents) */}
 {editMode === 'view' ? (
 <div className="td-edit__preview">
 {docContent.trim().length === 0 ? (
 <p className="td-edit__preview-empty">
 {t('tenderator.docEditor.emptyPreviewText')}
 </p>
 ) : (
 <div
 className="td-edit__preview-body markdown-content"
 dangerouslySetInnerHTML={{
 __html: marked.parse(
 docContent.replace(/^```[\w]*\n?/, '').replace(/\n?```\s*$/, ''),
 ) as string,
 }}
 />
 )}
 </div>
 ) : (
 <textarea
 className="td-edit__textarea"
 value={docContent}
 onChange={(e) => { setDocContent(e.target.value); setDocDirty(true); }}
 rows={28}
 placeholder={t('tenderator.docEditor.textareaPlaceholder')}
 />
 )}

 <div className="td-edit__center-foot">
 <span className="td-edit__center-status">
 {docDirty ? t('tenderator.docEditor.unsavedChanges') : t('tenderator.docEditor.saved')} · {t('tenderator.docEditor.wordCount', { count: docContent.split(/\s+/).filter(Boolean).length })}
 </span>
 <button className="td-edit__save" onClick={saveDoc} disabled={!docDirty || saving}>
 {saving ? t('tenderator.docEditor.saving') : t('tenderator.docEditor.save')}
 </button>
 </div>
 </>
 )}
 </main>

 {/* RIGHT RAIL: tabbed context */}
 <aside className="td-edit__right">
 <div className="td-edit__right-tabs">
 <button className={rightTab === 'topic' ? 'is-active' : ''} onClick={() => setRightTab('topic')}>{t('tenderator.docEditor.tabTopic')}</button>
 <button className={rightTab === 'org' ? 'is-active' : ''} onClick={() => setRightTab('org')}>{t('tenderator.docEditor.tabOrg')}</button>
 <button className={rightTab === 'ai' ? 'is-active' : ''} onClick={() => setRightTab('ai')}>{t('tenderator.docEditor.tabAI')}</button>
 <button className={rightTab === 'comply' ? 'is-active' : ''} onClick={() => setRightTab('comply')}>{t('tenderator.docEditor.tabComply')}</button>
 <button className={rightTab === 'winners' ? 'is-active' : ''} onClick={() => setRightTab('winners')}>{t('tenderator.docEditor.tabPastWinners')}</button>
 </div>
 <div className="td-edit__right-body">
 {rightTab === 'topic' && (
 <div>
 <h4>{data.template.name}</h4>
 <p>{t('tenderator.docEditor.programme')}: {data.programme} {data.sub_instrument && `· ${data.sub_instrument}`}</p>
 {data.stage && <p>{t('tenderator.docEditor.stage')}: {data.stage}</p>}
 {data.funding_mode && <p>{t('tenderator.docEditor.fundingMode')}: {data.funding_mode}</p>}
 {data.topic_id && <p>{t('tenderator.docEditor.topicID')}: <code>{data.topic_id}</code></p>}
 {data.deadline_iso && <p>{t('tenderator.docEditor.deadline')}: {new Date(data.deadline_iso).toLocaleString()}</p>}
 <p>{t('tenderator.docEditor.scaffold')}: {data.scaffold_version}</p>
 <div className="td-edit__cta-row">
 {data.topic_id && (
 <button onClick={openSourceTender}><span className="mdi mdi-open-in-new" /> {t('tenderator.docEditor.ftPortal')}</button>
 )}
 {data.template.official_template_url && (
 <a href={data.template.official_template_url} target="_blank" rel="noreferrer">
 <button type="button"><span className="mdi mdi-file-pdf-box" /> {t('tenderator.docEditor.officialTemplate')}</button>
 </a>
 )}
 </div>

 {/* Reference docs — official EU post-award reference set per programme.
     Enrichment via EuropeanAcademy index, 17 Jun 2026. */}
 {(data.template.model_grant_agreement_url || data.template.annotated_grant_agreement_url ||
   (data.template.reference_docs && data.template.reference_docs.length > 0)) && (
 <section className="td-edit__refs">
 <h5>{t('tenderator.docEditor.referenceDocuments')}</h5>
 {data.template.model_grant_agreement_url && (
 <a className="td-edit__refs-primary" href={data.template.model_grant_agreement_url} target="_blank" rel="noreferrer">
 <span className="mdi mdi-file-sign" /> {t('tenderator.docEditor.modelGrantAgreement')}
 <span className="mdi mdi-open-in-new td-edit__refs-ext" />
 </a>
 )}
 {data.template.annotated_grant_agreement_url && (
 <a className="td-edit__refs-primary" href={data.template.annotated_grant_agreement_url} target="_blank" rel="noreferrer">
 <span className="mdi mdi-book-open-variant" /> {t('tenderator.docEditor.annotatedGrantAgreement')}
 <span className="mdi mdi-open-in-new td-edit__refs-ext" />
 </a>
 )}
 {data.template.reference_docs && data.template.reference_docs.length > 0 && (() => {
 // Group reference_docs by category so the list stays scannable.
 const byCat: Record<string, ReferenceDoc[]> = {};
 (data.template.reference_docs || []).forEach((r) => {
 const c = r.category || t('tenderator.docEditor.refCategoryOther');
 if (!byCat[c]) byCat[c] = [];
 byCat[c].push(r);
 });
 const orderedCats = [
 t('tenderator.docEditor.refCategoryGrantAgreement'),
 t('tenderator.docEditor.refCategoryPostAward'),
 t('tenderator.docEditor.refCategoryCostRules'),
 t('tenderator.docEditor.refCategoryEligibility'),
 t('tenderator.docEditor.refCategoryOrgProfile'),
 t('tenderator.docEditor.refCategorySubmission'),
 t('tenderator.docEditor.refCategoryProgramme'),
 t('tenderator.docEditor.refCategoryOther')
 ]
 .filter((c) => byCat[c]);
 return (
 <div className="td-edit__refs-grouped">
 {orderedCats.map((cat) => (
 <div key={cat} className="td-edit__refs-cat">
 <div className="td-edit__refs-cat-label">{cat}</div>
 <ul className="td-edit__refs-list">
 {byCat[cat].map((r, i) => (
 <li key={i}>
 <a href={r.url} target="_blank" rel="noreferrer" title={r.url}>
 <span className="mdi mdi-file-pdf-box" /> {r.label}
 <span className="mdi mdi-open-in-new td-edit__refs-ext" />
 </a>
 </li>
 ))}
 </ul>
 </div>
 ))}
 </div>
 );
 })()}
 <p className="td-edit__refs-source">{t('tenderator.docEditor.refsSource')}</p>
 </section>
 )}
 </div>
 )}
 {rightTab === 'org' && (
 <div>
 <h4>{t('tenderator.docEditor.orgProfile')}</h4>
 {orgProfile ? (
 <ul className="td-edit__org-list">
 <li><strong>{t('tenderator.docEditor.company')}:</strong> {orgProfile.company_name || ''}</li>
 <li><strong>{t('tenderator.docEditor.size')}:</strong> {orgProfile.company_size || ''}</li>
 <li><strong>{t('tenderator.docEditor.sectors')}:</strong> {orgProfile.sectors_description || ''}</li>
 {orgProfile.keywords && orgProfile.keywords.length > 0 && (
 <li><strong>{t('tenderator.docEditor.keywords')}:</strong> {orgProfile.keywords.slice(0, 10).join(', ')}</li>
 )}
 {orgProfile.certifications && orgProfile.certifications.length > 0 && (
 <li><strong>{t('tenderator.docEditor.certifications')}:</strong> {orgProfile.certifications.join(', ')}</li>
 )}
 </ul>
 ) : (
 <p>{t('tenderator.docEditor.noTenderProfile')}</p>
 )}
 </div>
 )}
 {rightTab === 'ai' && (
 <div>
 <h4>{t('tenderator.docEditor.aiCoWriter')}</h4>
 <p>
 {t('tenderator.docEditor.aiInstructions')}
 </p>
 <p className="td-edit__hint">
 {t('tenderator.docEditor.aiNoFabrication')}
 </p>
 <p className="td-edit__hint">
 {t('tenderator.docEditor.aiDisclosure')}
 </p>
 </div>
 )}
 {rightTab === 'comply' && (
 <div>
 <h4>{t('tenderator.docEditor.applicableObligations')}</h4>
 {complyLoading ? (
 <p>{t('tenderator.docEditor.loadingClusters')}</p>
 ) : !comply || comply.length === 0 ? (
 <p>{t('tenderator.docEditor.noApplicableClusters')}</p>
 ) : (
 <ul className="td-edit__comply-list">
 {comply.slice(0, 12).map((c) => (
 <li key={c.id}>
 <strong>{c.name}</strong>
 <div className="td-edit__comply-meta">{t('tenderator.docEditor.complyMeta', { policyArea: c.policy_area, lawCount: c.law_count, reqCount: c.requirement_count })}</div>
 </li>
 ))}
 </ul>
 )}
 <button className="td-edit__cta" onClick={openComply}>{t('tenderator.docEditor.openComply')}</button>
 </div>
 )}
 {rightTab === 'winners' && (
 <div>
 <h4>{t('tenderator.docEditor.pastWinners')}</h4>
 {data.programme === 'EIC' && (data.sub_instrument === 'accelerator' || data.sub_instrument === 'step') ? (
 <PastWinners subInstrument={data.sub_instrument} token={token} />
 ) : (
 <p>{t('tenderator.docEditor.pastWinnersNote')}</p>
 )}
 </div>
 )}
 </div>

 {/* Cross-feature hand-offs (always visible) */}
 <div className="td-edit__handoffs">
 <button onClick={useInChat}><span className="mdi mdi-chat-outline" /> {t('tenderator.docEditor.useInChat')}</button>
 <button onClick={openComply}><span className="mdi mdi-clipboard-check-outline" /> {t('tenderator.docEditor.comply')}</button>
 </div>
 </aside>
 </div>
 </div>
 );
};

const PastWinners = ({ subInstrument, token }: { subInstrument?: string; token: string | null }) => {
 const { t } = useTranslation();
 const [grantees, setGrantees] = useState<Array<{ name: string; country?: string; theme_name?: string; description?: string }>>([]);
 const [loading, setLoading] = useState(true);

 useEffect(() => {
 let cancelled = false;
 (async () => {
 if (!token) return;
 try {
 const bucket = subInstrument === 'step' ? 'step-scale' : 'accelerator';
 const r = await fetch(`${API_URL}/api/tenders/eic-fund-grantees?bucket=${bucket}&limit=8`, {
 headers: { Authorization: `Bearer ${token}` },
 });
 // Endpoint returns { bucket, theme_codes_filter, items: [...] }
 const d = r.ok ? await r.json() : { items: [] };
 if (!cancelled) setGrantees(d.items || []);
 } catch (e) {
 console.warn(e);
 } finally {
 if (!cancelled) setLoading(false);
 }
 })();
 return () => { cancelled = true; };
 }, [subInstrument, token]);

 if (loading) return <p>{t('tenderator.docEditor.loading')}</p>;
 if (grantees.length === 0) return <p>{t('tenderator.docEditor.noGranteesData')}</p>;
 return (
 <ul className="td-edit__winners-list">
 {grantees.map((g, i) => (
 <li key={i}>
 <strong>{g.name}</strong>
 {g.country && <> · {g.country}</>}
 {g.theme_name && <div className="td-edit__winners-theme">{g.theme_name}</div>}
 </li>
 ))}
 </ul>
 );
};

export default TenderDocEditor;
