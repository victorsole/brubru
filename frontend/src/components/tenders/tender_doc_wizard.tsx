/**
 * Tender Doc Wizard "Start a Tender Doc" modal.
 *
 * Three-step flow:
 * 1) Programme + sub-instrument picker (or a preselected template)
 * 2) Funding mode + topic id (conditional on the chosen template)
 * 3) Title + create
 *
 * On submit, POSTs /api/tender-files and navigates the parent into the editor.
 */
import { useEffect, useState, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useAuth } from '../../hooks/use_auth';
import './tender_doc_wizard.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface TemplateDetail {
 id: string;
 name: string;
 programme: string;
 sub_instrument?: string;
 stage?: string;
 scaffold_version?: string;
 topic_id_default?: string;
 funding_mode_default?: string;
 cut_offs_2026_cet?: string[];
 deadline_2026_cet?: string;
 deadline_2027_cet?: string;
 deadline_2027_indicative_cet?: string;
 note?: string;
 documents?: Array<{ kind: string; title: string }>;
}

interface TemplateSummary {
 id: string;
 name: string;
 programme: string;
 sub_instrument?: string;
 stage?: string;
 scaffold_version?: string;
 topic_id_default?: string;
 deadline?: string;
 note?: string;
}

const PROGRAMME_LABELS: Record<string, string> = {
 EIC: 'European Innovation Council',
 HE: 'Horizon Europe',
 CEF: 'Connecting Europe Facility',
 LIFE: 'LIFE',
 EDF: 'European Defence Fund',
};

const SUB_INSTRUMENT_LABELS: Record<string, string> = {
 accelerator: 'Accelerator',
 'pathfinder-open': 'Pathfinder Open',
 'pathfinder-challenges': 'Pathfinder Challenges',
 transition: 'Transition',
 step: 'STEP Scale Up',
 aic: 'Advanced Innovation Challenges',
 'pre-accelerator': 'Pre-Accelerator',
};

const FUNDING_MODE_LABELS: Record<string, string> = {
 'grant-only': 'Grant only',
 'equity-only': 'Equity only',
 blended: 'Blended (grant + equity)',
};

// Sub-instruments that involve the EIC Fund's equity component
const FUNDING_MODE_SUB_INSTRUMENTS = new Set(['accelerator', 'step']);

export interface TenderDocWizardProps {
 initialTemplateId?: string;
 onClose: () => void;
 onCreated: (tenderFileId: string) => void;
}

export const TenderDocWizard = ({ initialTemplateId, onClose, onCreated }: TenderDocWizardProps) => {
 const { token } = useAuth();

 const [step, setStep] = useState<number>(initialTemplateId ? 2 : 1);
 const [templates, setTemplates] = useState<TemplateSummary[]>([]);
 const [selectedTemplateId, setSelectedTemplateId] = useState<string>(initialTemplateId || '');
 const [templateDetail, setTemplateDetail] = useState<TemplateDetail | null>(null);
 const [loadingDetail, setLoadingDetail] = useState(false);

 const [fundingMode, setFundingMode] = useState<string>('');
 const [topicId, setTopicId] = useState<string>('');
 const [topicVariant, setTopicVariant] = useState<string>('');
 const [deadlineIso, setDeadlineIso] = useState<string>('');
 const [title, setTitle] = useState<string>('');
 const [submitting, setSubmitting] = useState(false);
 const [error, setError] = useState<string | null>(null);

 // Load templates list
 useEffect(() => {
 let cancelled = false;
 (async () => {
 if (!token) return;
 try {
 const r = await fetch(`${API_URL}/api/tender-templates/`, { headers: { Authorization: `Bearer ${token}` } });
 const d = r.ok ? await r.json() : { templates: [] };
 if (!cancelled) setTemplates(d.templates || []);
 } catch (e) {
 console.error('Wizard: failed to load templates', e);
 }
 })();
 return () => { cancelled = true; };
 }, [token]);

 // Load detail when a template is chosen
 useEffect(() => {
 let cancelled = false;
 (async () => {
 if (!selectedTemplateId || !token) { setTemplateDetail(null); return; }
 setLoadingDetail(true);
 try {
 const r = await fetch(`${API_URL}/api/tender-templates/${selectedTemplateId}`, { headers: { Authorization: `Bearer ${token}` } });
 const d = r.ok ? await r.json() : null;
 if (!cancelled && d) {
 setTemplateDetail(d);
 // Pre-fill defaults
 setTopicId(d.topic_id_default || '');
 setFundingMode(d.funding_mode_default || '');
 const dl = d.deadline_2026_cet || d.cut_offs_2026_cet?.[0] || d.deadline_2027_cet || d.deadline_2027_indicative_cet || '';
 setDeadlineIso(dl || '');
 // Seed a sensible default title
 setTitle((prev) => prev || `My application ${d.name}`);
 }
 } catch (e) {
 console.error('Wizard: failed to load template detail', e);
 } finally {
 if (!cancelled) setLoadingDetail(false);
 }
 })();
 return () => { cancelled = true; };
 }, [selectedTemplateId, token]);

 const programmes = useMemo(() => {
 const map: Record<string, TemplateSummary[]> = {};
 templates.forEach((t) => {
 const p = t.programme || 'Other';
 if (!map[p]) map[p] = [];
 map[p].push(t);
 });
 return map;
 }, [templates]);

 const submit = async () => {
 if (!selectedTemplateId || !title.trim()) {
 setError('Please choose a template and give your tender doc a title.');
 return;
 }
 setSubmitting(true);
 setError(null);
 try {
 const body: Record<string, unknown> = {
 title: title.trim(),
 template_id: selectedTemplateId,
 seed_first_doc: true,
 };
 if (fundingMode) body.funding_mode = fundingMode;
 if (topicId) body.topic_id = topicId;
 if (topicVariant) body.topic_variant = topicVariant;
 if (deadlineIso) body.deadline_iso = deadlineIso;

 const r = await fetch(`${API_URL}/api/tender-files/`, {
 method: 'POST',
 headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
 body: JSON.stringify(body),
 });
 if (!r.ok) {
 const err = await r.json().catch(() => ({ detail: 'Create failed' }));
 throw new Error(typeof err.detail === 'string' ? err.detail : 'Create failed');
 }
 const data = await r.json();
 onCreated(data.id);
 } catch (e) {
 setError((e as Error).message);
 } finally {
 setSubmitting(false);
 }
 };

 const showFundingMode = templateDetail && FUNDING_MODE_SUB_INSTRUMENTS.has(templateDetail.sub_instrument || '');

 return createPortal(
 <div className="td-wiz__scrim" onClick={onClose}>
 <div className="td-wiz" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
 <button className="td-wiz__close" onClick={onClose} aria-label="Close wizard">
 <span className="mdi mdi-close" />
 </button>

 {/* Step indicator */}
 <div className="td-wiz__steps">
 <div className={`td-wiz__step ${step >= 1 ? 'is-active' : ''}`}>1. Programme</div>
 <div className={`td-wiz__step ${step >= 2 ? 'is-active' : ''}`}>2. Topic + funding</div>
 <div className={`td-wiz__step ${step >= 3 ? 'is-active' : ''}`}>3. Name + start</div>
 </div>

 {/* Step 1: Programme picker */}
 {step === 1 && (
 <div className="td-wiz__body">
 <h2>Which programme?</h2>
 <p className="td-wiz__hint">
 Brubru ships a template per (programme × sub-instrument × stage). We start
 you with the official EU section structure for your chosen track.
 </p>
 <div className="td-wiz__programmes">
 {Object.entries(programmes).map(([p, tpls]) => (
 <div key={p} className="td-wiz__programme">
 <h3>{PROGRAMME_LABELS[p] || p}</h3>
 <div className="td-wiz__templates">
 {tpls.map((tpl) => (
 <button
 key={tpl.id}
 type="button"
 className={`td-wiz__tpl ${selectedTemplateId === tpl.id ? 'is-active' : ''}`}
 onClick={() => setSelectedTemplateId(tpl.id)}
 >
 <div className="td-wiz__tpl-name">{tpl.name}</div>
 {tpl.sub_instrument && (
 <div className="td-wiz__tpl-sub">{SUB_INSTRUMENT_LABELS[tpl.sub_instrument] || tpl.sub_instrument}</div>
 )}
 {tpl.deadline && (
 <div className="td-wiz__tpl-deadline">
 <span className="mdi mdi-calendar-clock" />{' '}
 Next cut-off: {new Date(tpl.deadline).toLocaleDateString()}
 </div>
 )}
 {tpl.note && <div className="td-wiz__tpl-note">{tpl.note}</div>}
 </button>
 ))}
 </div>
 </div>
 ))}
 </div>
 <div className="td-wiz__actions">
 <button className="td-wiz__btn td-wiz__btn--ghost" onClick={onClose}>Cancel</button>
 <button
 className="td-wiz__btn td-wiz__btn--primary"
 disabled={!selectedTemplateId}
 onClick={() => setStep(2)}
 >
 Next
 </button>
 </div>
 </div>
 )}

 {/* Step 2: Topic + funding mode */}
 {step === 2 && templateDetail && (
 <div className="td-wiz__body">
 <div className="td-wiz__green-disclaimer">
 <span className="mdi mdi-check-decagram" /> You are using the{' '}
 <strong>{templateDetail.scaffold_version || 'current'}</strong> version of the official EU template
 ({templateDetail.name}).
 </div>
 <h2>{templateDetail.name}</h2>
 <p className="td-wiz__hint">{loadingDetail ? 'Loading template detail...' : 'Adjust topic + funding mode if relevant. You can change these later.'}</p>

 <label className="td-wiz__field">
 <span>Topic ID (F&T Portal)</span>
 <input
 type="text"
 value={topicId}
 onChange={(e) => setTopicId(e.target.value)}
 placeholder={templateDetail.topic_id_default || 'HORIZON-EIC-2026-...'}
 />
 </label>

 {templateDetail.sub_instrument === 'accelerator' && (
 <label className="td-wiz__field">
 <span>Challenge variant (Stage 2 only leave blank for Open)</span>
 <select value={topicVariant} onChange={(e) => setTopicVariant(e.target.value)}>
 <option value=""> Open call</option>
 <option value="challenge-2.1">2.1 Advanced Materials for Renewable Energy</option>
 <option value="challenge-2.2">2.2 Fusion Power Plants</option>
 <option value="challenge-2.3">2.3 Biotech for Regenerating Agricultural Soils</option>
 <option value="challenge-2.4">2.4 Critical Raw Materials value chain</option>
 <option value="challenge-2.5">2.5 Deep Tech for Climate Adaptation</option>
 </select>
 </label>
 )}

 {showFundingMode && (
 <label className="td-wiz__field">
 <span>Funding mode</span>
 <select value={fundingMode} onChange={(e) => setFundingMode(e.target.value)}>
 <option value=""> Pick one</option>
 {Object.entries(FUNDING_MODE_LABELS).map(([k, v]) => (
 <option key={k} value={k}>{v}</option>
 ))}
 </select>
 </label>
 )}

 <label className="td-wiz__field">
 <span>Deadline (cut-off) pre-filled with next applicable cut-off</span>
 <input
 type="datetime-local"
 value={deadlineIso ? deadlineIso.slice(0, 16) : ''}
 onChange={(e) => setDeadlineIso(e.target.value ? `${e.target.value}:00+02:00` : '')}
 />
 </label>

 <div className="td-wiz__actions">
 <button className="td-wiz__btn td-wiz__btn--ghost" onClick={() => setStep(1)}>Back</button>
 <button
 className="td-wiz__btn td-wiz__btn--primary"
 onClick={() => setStep(3)}
 >
 Next
 </button>
 </div>
 </div>
 )}

 {/* Step 3: Title + create */}
 {step === 3 && templateDetail && (
 <div className="td-wiz__body">
 <h2>Name your Tender File</h2>
 <p className="td-wiz__hint">
 A Tender File groups all the documents you write for ONE application 
 the Part B narrative, pitch deck, video script, annexes. We'll seed the first
 doc from the official template's section structure so you don't start from a blank page.
 </p>
 <label className="td-wiz__field">
 <span>File title</span>
 <input
 type="text"
 value={title}
 onChange={(e) => setTitle(e.target.value)}
 placeholder="e.g. ACME EIC Accelerator 2026 Cut-off 4"
 autoFocus
 />
 </label>
 <div className="td-wiz__summary">
 <div><strong>Template:</strong> {templateDetail.name}</div>
 <div><strong>Scaffold version:</strong> {templateDetail.scaffold_version}</div>
 {fundingMode && <div><strong>Funding mode:</strong> {FUNDING_MODE_LABELS[fundingMode] || fundingMode}</div>}
 {topicId && <div><strong>Topic ID:</strong> <code>{topicId}</code></div>}
 {topicVariant && <div><strong>Challenge:</strong> {topicVariant}</div>}
 {deadlineIso && <div><strong>Deadline:</strong> {new Date(deadlineIso).toLocaleString()}</div>}
 {(templateDetail.documents || []).length > 0 && (
 <div>
 <strong>We'll seed:</strong> the first document
 {' '}({(templateDetail.documents || [])[0]?.title}). You can add more from the editor.
 </div>
 )}
 </div>
 {error && <div className="td-wiz__error">{error}</div>}
 <div className="td-wiz__actions">
 <button className="td-wiz__btn td-wiz__btn--ghost" onClick={() => setStep(2)} disabled={submitting}>Back</button>
 <button
 className="td-wiz__btn td-wiz__btn--primary"
 onClick={submit}
 disabled={submitting || !title.trim()}
 >
 {submitting ? 'Creating…' : 'Create & open editor'}
 </button>
 </div>
 </div>
 )}
 </div>
 </div>,
 document.body,
 );
};

export default TenderDocWizard;
