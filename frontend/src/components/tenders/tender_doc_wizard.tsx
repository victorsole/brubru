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
import { useTranslation } from 'react-i18next';
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
 'ERASMUS+': 'Erasmus+',
 DIGITAL: 'Digital Europe Programme',
 CERV: 'Citizens, Equality, Rights and Values',
 LIFE: 'LIFE (Environment + Climate Action)',
 CREA: 'Creative Europe',
 CEF: 'Connecting Europe Facility',
 'ESF+': 'European Social Fund Plus',
 EDF: 'European Defence Fund',
};

const SUB_INSTRUMENT_LABELS: Record<string, string> = {
 // EIC
 accelerator: 'Accelerator',
 'pathfinder-open': 'Pathfinder Open',
 'pathfinder-challenges': 'Pathfinder Challenges',
 transition: 'Transition',
 step: 'STEP Scale Up',
 aic: 'Advanced Innovation Challenges',
 'pre-accelerator': 'Pre-Accelerator',
 // Erasmus+ + DIGITAL + CERV (generic strands)
 lsi: 'Lump-Sum Standard Implementation',
 dep: 'Digital Europe (generic action)',
 general: 'General action',
 // CREA strands
 culture: 'Culture',
 media: 'MEDIA',
 // LIFE strands
 sap: 'Standard Action Project (SAP)',
 // CEF strands
 transport: 'Transport (CEF-T)',
 energy: 'Energy (CEF-E)',
 digital: 'Digital (CEF-DIG)',
 // ESF+ delivery route
 'agency-procurement': 'Agency procurement (national MA)',
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
 const { t } = useTranslation();

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
 setError(t('tenderator.docWizard.errorMissingTemplateAndTitle'));
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
 <button className="td-wiz__close" onClick={onClose} aria-label={t('tenderator.docWizard.closeWizard')}>
 <span className="mdi mdi-close" />
 </button>

 {/* Step indicator */}
 <div className="td-wiz__steps">
 <div className={`td-wiz__step ${step >= 1 ? 'is-active' : ''}`}>{t('tenderator.docWizard.step1Programme')}</div>
 <div className={`td-wiz__step ${step >= 2 ? 'is-active' : ''}`}>{t('tenderator.docWizard.step2TopicFunding')}</div>
 <div className={`td-wiz__step ${step >= 3 ? 'is-active' : ''}`}>{t('tenderator.docWizard.step3NameStart')}</div>
 </div>

 {/* Step 1: Programme picker */}
 {step === 1 && (
 <div className="td-wiz__body">
 <h2>{t('tenderator.docWizard.whichProgramme')}</h2>
 <p className="td-wiz__hint">
 {t('tenderator.docWizard.step1Hint')}
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
 {t('tenderator.docWizard.nextCutOff')}: {new Date(tpl.deadline).toLocaleDateString()}
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
 <button className="td-wiz__btn td-wiz__btn--ghost" onClick={onClose}>{t('tenderator.docWizard.cancel')}</button>
 <button
 className="td-wiz__btn td-wiz__btn--primary"
 disabled={!selectedTemplateId}
 onClick={() => setStep(2)}
 >
 {t('tenderator.docWizard.next')}
 </button>
 </div>
 </div>
 )}

 {/* Step 2: Topic + funding mode */}
 {step === 2 && templateDetail && (
 <div className="td-wiz__body">
 <div className="td-wiz__green-disclaimer">
 <span className="mdi mdi-check-decagram" /> {t('tenderator.docWizard.usingTemplateVersion', { version: templateDetail.scaffold_version || 'current', template: templateDetail.name })}
 </div>
 <h2>{templateDetail.name}</h2>
 <p className="td-wiz__hint">{loadingDetail ? t('tenderator.docWizard.loadingTemplateDetail') : t('tenderator.docWizard.step2Hint')}</p>

 <label className="td-wiz__field">
 <span>{t('tenderator.docWizard.topicIdLabel')}</span>
 <input
 type="text"
 value={topicId}
 onChange={(e) => setTopicId(e.target.value)}
 placeholder={templateDetail.topic_id_default || t('tenderator.docWizard.topicIdPlaceholder')}
 />
 </label>

 {templateDetail.sub_instrument === 'accelerator' && (
 <label className="td-wiz__field">
 <span>{t('tenderator.docWizard.challengeVariantLabel')}</span>
 <select value={topicVariant} onChange={(e) => setTopicVariant(e.target.value)}>
 <option value="">{t('tenderator.docWizard.challengeOpenCall')}</option>
 <option value="challenge-2.1">{t('tenderator.docWizard.challenge21')}</option>
 <option value="challenge-2.2">{t('tenderator.docWizard.challenge22')}</option>
 <option value="challenge-2.3">{t('tenderator.docWizard.challenge23')}</option>
 <option value="challenge-2.4">{t('tenderator.docWizard.challenge24')}</option>
 <option value="challenge-2.5">{t('tenderator.docWizard.challenge25')}</option>
 </select>
 </label>
 )}

 {showFundingMode && (
 <label className="td-wiz__field">
 <span>{t('tenderator.docWizard.fundingModeLabel')}</span>
 <select value={fundingMode} onChange={(e) => setFundingMode(e.target.value)}>
 <option value="">{t('tenderator.docWizard.fundingModePickOne')}</option>
 {Object.keys(FUNDING_MODE_LABELS).map((k) => (
 <option key={k} value={k}>{t(`tenderator.docWizard.fundingMode${k.charAt(0).toUpperCase() + k.slice(1).replace(/-/g, '')}`)}</option>
 ))}
 </select>
 </label>
 )}

 <label className="td-wiz__field">
 <span>{t('tenderator.docWizard.deadlineLabel')}</span>
 <input
 type="datetime-local"
 value={deadlineIso ? deadlineIso.slice(0, 16) : ''}
 onChange={(e) => setDeadlineIso(e.target.value ? `${e.target.value}:00+02:00` : '')}
 />
 </label>

 <div className="td-wiz__actions">
 <button className="td-wiz__btn td-wiz__btn--ghost" onClick={() => setStep(1)}>{t('tenderator.docWizard.back')}</button>
 <button
 className="td-wiz__btn td-wiz__btn--primary"
 onClick={() => setStep(3)}
 >
 {t('tenderator.docWizard.next')}
 </button>
 </div>
 </div>
 )}

 {/* Step 3: Title + create */}
 {step === 3 && templateDetail && (
 <div className="td-wiz__body">
 <h2>{t('tenderator.docWizard.nameTenderFile')}</h2>
 <p className="td-wiz__hint">
 {t('tenderator.docWizard.step3Hint')}
 </p>
 <label className="td-wiz__field">
 <span>{t('tenderator.docWizard.fileTitleLabel')}</span>
 <input
 type="text"
 value={title}
 onChange={(e) => setTitle(e.target.value)}
 placeholder={t('tenderator.docWizard.fileTitlePlaceholder')}
 autoFocus
 />
 </label>
 <div className="td-wiz__summary">
 <div><strong>{t('tenderator.docWizard.summaryTemplate')}:</strong> {templateDetail.name}</div>
 <div><strong>{t('tenderator.docWizard.summaryScaffoldVersion')}:</strong> {templateDetail.scaffold_version}</div>
 {fundingMode && <div><strong>{t('tenderator.docWizard.summaryFundingMode')}:</strong> {t(`tenderator.docWizard.fundingMode${fundingMode.charAt(0).toUpperCase() + fundingMode.slice(1).replace(/-/g, '')}`) || fundingMode}</div>}
 {topicId && <div><strong>{t('tenderator.docWizard.summaryTopicId')}:</strong> <code>{topicId}</code></div>}
 {topicVariant && <div><strong>{t('tenderator.docWizard.summaryChallenge')}:</strong> {topicVariant}</div>}
 {deadlineIso && <div><strong>{t('tenderator.docWizard.summaryDeadline')}:</strong> {new Date(deadlineIso).toLocaleString()}</div>}
 {(templateDetail.documents || []).length > 0 && (
 <div>
 <strong>{t('tenderator.docWizard.summaryWeSeed')}:</strong> {t('tenderator.docWizard.summaryFirstDocument')}
 {' '}({(templateDetail.documents || [])[0]?.title}). {t('tenderator.docWizard.summaryAddMore')}
 </div>
 )}
 </div>
 {error && <div className="td-wiz__error">{error}</div>}
 <div className="td-wiz__actions">
 <button className="td-wiz__btn td-wiz__btn--ghost" onClick={() => setStep(2)} disabled={submitting}>{t('tenderator.docWizard.back')}</button>
 <button
 className="td-wiz__btn td-wiz__btn--primary"
 onClick={submit}
 disabled={submitting || !title.trim()}
 >
 {submitting ? t('tenderator.docWizard.creating') : t('tenderator.docWizard.createAndOpenEditor')}
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
