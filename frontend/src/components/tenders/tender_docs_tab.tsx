/**
 * Tender Docs tab list view of the user's tender_files.
 *
 * Each card represents ONE EU funding application (e.g. an EIC Accelerator
 * submission), grouping the Part B narrative + pitch deck + video + annexes.
 *
 * Cross-feature hand-offs: each card hand-offs to Comply / Chat / the
 * Tenderator drawer / MEUB Documents. See `docs/api/api_funds.md` (Tender
 * Docs design, 16 Jun 2026).
 *
 * AI system: same multi-provider chain as MEUB Documents + Strategy Docs
 * (Cerebras → Gemini → ... → OpenAI), via the existing
 * `services/ai/multi_provider_service.py` singleton.
 */
import { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/use_auth';
import './tender_docs_tab.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface TenderFile {
 id: string;
 title: string;
 programme: string;
 sub_instrument?: string | null;
 stage?: string | null;
 topic_id?: string | null;
 funding_mode?: string | null;
 deadline_iso?: string | null;
 status: string;
 template_id: string;
 scaffold_version: string;
 extra?: Record<string, unknown>;
 created_at?: string;
 updated_at?: string;
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
 official_template_url?: string;
 note?: string;
}

const PROGRAMME_LABELS: Record<string, string> = {
 EIC: 'tenderator.docsTab.programmes.eic',
 HE: 'tenderator.docsTab.programmes.he',
 'ERASMUS+': 'tenderator.docsTab.programmes.erasmusPlus',
 DIGITAL: 'tenderator.docsTab.programmes.digital',
 CERV: 'tenderator.docsTab.programmes.cerv',
 LIFE: 'tenderator.docsTab.programmes.life',
 CREA: 'tenderator.docsTab.programmes.crea',
 CEF: 'tenderator.docsTab.programmes.cef',
 'ESF+': 'tenderator.docsTab.programmes.esfPlus',
 EDF: 'tenderator.docsTab.programmes.edf',
 TED: 'tenderator.docsTab.programmes.ted',
};

const STATUS_LABELS: Record<string, string> = {
 drafting: 'tenderator.docsTab.status.drafting',
 'ready-to-submit': 'tenderator.docsTab.status.readyToSubmit',
 submitted: 'tenderator.docsTab.status.submitted',
 won: 'tenderator.docsTab.status.won',
 lost: 'tenderator.docsTab.status.lost',
 'seal-of-excellence': 'tenderator.docsTab.status.sealOfExcellence',
};

const STATUS_COLORS: Record<string, string> = {
 drafting: '#94a3b8',
 'ready-to-submit': '#0ea5e9',
 submitted: '#6366f1',
 won: '#16a34a',
 lost: '#ef4444',
 'seal-of-excellence': '#f59e0b',
};

const SUB_INSTRUMENT_LABELS: Record<string, string> = {
 // EIC
 accelerator: 'tenderator.docsTab.subInstruments.accelerator',
 'pathfinder-open': 'tenderator.docsTab.subInstruments.pathfinderOpen',
 'pathfinder-challenges': 'tenderator.docsTab.subInstruments.pathfinderChallenges',
 transition: 'tenderator.docsTab.subInstruments.transition',
 step: 'tenderator.docsTab.subInstruments.step',
 aic: 'tenderator.docsTab.subInstruments.aic',
 'pre-accelerator': 'tenderator.docsTab.subInstruments.preAccelerator',
 prize: 'tenderator.docsTab.subInstruments.prize',
 // Erasmus+ / DIGITAL / CERV
 lsi: 'tenderator.docsTab.subInstruments.lsi',
 dep: 'tenderator.docsTab.subInstruments.dep',
 general: 'tenderator.docsTab.subInstruments.general',
 // CREA strands
 culture: 'tenderator.docsTab.subInstruments.culture',
 media: 'tenderator.docsTab.subInstruments.media',
 // LIFE strands
 sap: 'tenderator.docsTab.subInstruments.sap',
 // CEF strands
 transport: 'tenderator.docsTab.subInstruments.transport',
 energy: 'tenderator.docsTab.subInstruments.energy',
 digital: 'tenderator.docsTab.subInstruments.digital',
 // ESF+ delivery route
 'agency-procurement': 'tenderator.docsTab.subInstruments.agencyProcurement',
};

function formatDeadlineCountdown(iso?: string | null): string {
 if (!iso) return '';
 try {
 const d = new Date(iso);
 const now = new Date();
 const ms = d.getTime() - now.getTime();
 if (ms < 0) return 'past';
 const days = Math.ceil(ms / (1000 * 60 * 60 * 24));
 if (days > 60) return `${Math.floor(days / 30)} months`;
 return `${days}d`;
 } catch {
 return '';
 }
}

export interface TenderDocsTabProps {
 onOpenFile: (file: TenderFile) => void;
 onOpenStartWizard: (templateId?: string) => void;
 /**
  * Optional back-arrow handler. When omitted, no back button renders the MEUB
  * embedding uses its own sidebar instead of an in-tab back arrow.
  */
 onBack?: () => void;
 /** Optional subtitle override (default targets the Tenderator embedding). */
 subtitle?: string;
}

export const TenderDocsTab = ({ onOpenFile, onOpenStartWizard, onBack, subtitle }: TenderDocsTabProps) => {
 const { token } = useAuth();
 const navigate = useNavigate();
 const { t } = useTranslation();

 const [files, setFiles] = useState<TenderFile[]>([]);
 const [templates, setTemplates] = useState<TemplateSummary[]>([]);
 const [loading, setLoading] = useState(true);

 const [programmeFilter, setProgrammeFilter] = useState<string>('all');
 const [subFilter, setSubFilter] = useState<string>('all');
 const [statusFilter, setStatusFilter] = useState<string>('all');
 const [searchQ, setSearchQ] = useState('');

 useEffect(() => {
 let cancelled = false;
 (async () => {
 if (!token) return;
 setLoading(true);
 try {
 const [filesRes, tplRes] = await Promise.all([
 fetch(`${API_URL}/api/tender-files/`, { headers: { Authorization: `Bearer ${token}` } }),
 fetch(`${API_URL}/api/tender-templates/`, { headers: { Authorization: `Bearer ${token}` } }),
 ]);
 const filesData = filesRes.ok ? await filesRes.json() : [];
 const tplData = tplRes.ok ? await tplRes.json() : { templates: [] };
 if (cancelled) return;
 setFiles(Array.isArray(filesData) ? filesData : []);
 setTemplates(tplData.templates || []);
 } catch (err) {
 console.error('TenderDocsTab: failed to load:', err);
 } finally {
 if (!cancelled) setLoading(false);
 }
 })();
 return () => { cancelled = true; };
 }, [token]);

 const filteredFiles = useMemo(() => {
 return files.filter((f) => {
 if (programmeFilter !== 'all' && f.programme !== programmeFilter) return false;
 if (subFilter !== 'all' && f.sub_instrument !== subFilter) return false;
 if (statusFilter !== 'all' && f.status !== statusFilter) return false;
 if (searchQ) {
 const q = searchQ.toLowerCase();
 const hay = `${f.title} ${f.topic_id || ''} ${f.template_id}`.toLowerCase();
 if (!hay.includes(q)) return false;
 }
 return true;
 });
 }, [files, programmeFilter, subFilter, statusFilter, searchQ]);

 const programmesPresent = useMemo(() => {
 const s = new Set(templates.map((t) => t.programme));
 return Array.from(s).sort();
 }, [templates]);

 const subsForProgramme = useMemo(() => {
 if (programmeFilter === 'all') return [];
 return templates
 .filter((t) => t.programme === programmeFilter && t.sub_instrument)
 .map((t) => t.sub_instrument as string)
 .filter((s, i, arr) => arr.indexOf(s) === i)
 .sort();
 }, [templates, programmeFilter]);

 return (
 <div className="tender-docs-tab">
 {/* Header */}
 <header className="tender-docs-tab__header">
 <div className="tender-docs-tab__header-left">
 {onBack && (
 <button className="tender-docs-tab__back" onClick={onBack} aria-label={t('tenderator.docsTab.backAriaLabel')}>
 <span className="mdi mdi-arrow-left" />
 </button>
 )}
 <div>
 <h1 className="tender-docs-tab__title">
 <span className="mdi mdi-file-document-edit-outline" aria-hidden="true" />
 {t('tenderator.docsTab.title')}
 </h1>
 <p className="tender-docs-tab__subtitle">
 {subtitle || t('tenderator.docsTab.subtitle')}
 </p>
 </div>
 </div>
 <div className="tender-docs-tab__header-actions">
 <button
 type="button"
 className="tender-docs-tab__cta"
 onClick={() => onOpenStartWizard()}
 >
 <span className="mdi mdi-plus" aria-hidden="true" />
 {t('tenderator.docsTab.startCtaButton')}
 </button>
 </div>
 </header>

 {/* Filters */}
 <section className="tender-docs-tab__filters" aria-label={t('tenderator.docsTab.filtersAriaLabel')}>
 <div className="tender-docs-tab__filter-group">
 <label>{t('tenderator.docsTab.programmeLabel')}</label>
 <select value={programmeFilter} onChange={(e) => { setProgrammeFilter(e.target.value); setSubFilter('all'); }}>
 <option value="all">{t('tenderator.docsTab.filterAllOption')}</option>
 {programmesPresent.map((p) => (
 <option key={p} value={p}>{t(PROGRAMME_LABELS[p] || p)}</option>
 ))}
 </select>
 </div>
 {programmeFilter !== 'all' && subsForProgramme.length > 0 && (
 <div className="tender-docs-tab__filter-group">
 <label>{t('tenderator.docsTab.subInstrumentLabel')}</label>
 <select value={subFilter} onChange={(e) => setSubFilter(e.target.value)}>
 <option value="all">{t('tenderator.docsTab.filterAllOption')}</option>
 {subsForProgramme.map((s) => (
 <option key={s} value={s}>{t(SUB_INSTRUMENT_LABELS[s] || s)}</option>
 ))}
 </select>
 </div>
 )}
 <div className="tender-docs-tab__filter-group">
 <label>{t('tenderator.docsTab.statusLabel')}</label>
 <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
 <option value="all">{t('tenderator.docsTab.filterAllOption')}</option>
 {Object.entries(STATUS_LABELS).map(([k]) => (
 <option key={k} value={k}>{t(STATUS_LABELS[k])}</option>
 ))}
 </select>
 </div>
 <div className="tender-docs-tab__filter-group tender-docs-tab__filter-group--search">
 <label htmlFor="td-search">{t('tenderator.docsTab.searchLabel')}</label>
 <input
 id="td-search"
 type="text"
 placeholder={t('tenderator.docsTab.searchPlaceholder')}
 value={searchQ}
 onChange={(e) => setSearchQ(e.target.value)}
 />
 </div>
 </section>

 {/* Body */}
 <section className="tender-docs-tab__body">
 {loading ? (
 <div className="tender-docs-tab__loading">
 <span className="mdi mdi-loading mdi-spin" />
 {' '}{t('tenderator.docsTab.loadingText')}
 </div>
 ) : files.length === 0 ? (
 // Empty state programme picker
 <div className="tender-docs-tab__empty">
 <h2>{t('tenderator.docsTab.empty.heading')}</h2>
 <p>
 {t('tenderator.docsTab.empty.description')}
 </p>
 <div className="tender-docs-tab__empty-grid">
 {templates.map((tpl) => (
 <button
 key={tpl.id}
 type="button"
 className="tender-docs-tab__empty-card"
 onClick={() => onOpenStartWizard(tpl.id)}
 >
 <div className="tender-docs-tab__empty-card-badge">{tpl.programme}</div>
 <div className="tender-docs-tab__empty-card-title">{tpl.name}</div>
 {tpl.deadline && (
 <div className="tender-docs-tab__empty-card-meta">
 <span className="mdi mdi-calendar-clock" /> {' '}
 {t('tenderator.docsTab.empty.nextDeadlinePrefix')}: {new Date(tpl.deadline).toLocaleDateString()}
 </div>
 )}
 {tpl.note && (
 <div className="tender-docs-tab__empty-card-note">{tpl.note}</div>
 )}
 </button>
 ))}
 </div>
 </div>
 ) : filteredFiles.length === 0 ? (
 <div className="tender-docs-tab__empty">
 <p>{t('tenderator.docsTab.empty.noMatches')}</p>
 <button onClick={() => { setProgrammeFilter('all'); setSubFilter('all'); setStatusFilter('all'); setSearchQ(''); }}>
 {t('tenderator.docsTab.empty.clearFiltersButton')}
 </button>
 </div>
 ) : (
 <div className="tender-docs-tab__grid">
 {filteredFiles.map((f) => {
 const docCount = (f.extra as { doc_count?: number } | undefined)?.doc_count ?? 0;
 return (
 <article key={f.id} className="tender-docs-tab__card" data-status={f.status}>
 <div className="tender-docs-tab__card-top">
 <span className="tender-docs-tab__card-prog">{t(PROGRAMME_LABELS[f.programme] || f.programme)}</span>
 {f.sub_instrument && (
 <span className="tender-docs-tab__card-sub">{t(SUB_INSTRUMENT_LABELS[f.sub_instrument] || f.sub_instrument)}</span>
 )}
 <span
 className="tender-docs-tab__card-status"
 style={{ background: `${STATUS_COLORS[f.status]}22`, color: STATUS_COLORS[f.status] }}
 >
 {t(STATUS_LABELS[f.status] || f.status)}
 </span>
 </div>
 <h3 className="tender-docs-tab__card-title">{f.title}</h3>
 {f.topic_id && (
 <div className="tender-docs-tab__card-topic" title={f.topic_id}>
 <span className="mdi mdi-link-variant" /> {f.topic_id}
 </div>
 )}
 <div className="tender-docs-tab__card-meta">
 {f.funding_mode && (
 <span className="tender-docs-tab__card-pill">{f.funding_mode}</span>
 )}
 {f.deadline_iso && (
 <span className="tender-docs-tab__card-pill tender-docs-tab__card-pill--deadline">
 <span className="mdi mdi-calendar-clock" /> {formatDeadlineCountdown(f.deadline_iso)} ·{' '}
 {new Date(f.deadline_iso).toLocaleDateString()}
 </span>
 )}
 <span className="tender-docs-tab__card-pill">{docCount} {t('tenderator.docsTab.card.docLabel', { count: docCount })}</span>
 </div>
 <div className="tender-docs-tab__card-actions">
 <button type="button" className="tender-docs-tab__card-open" onClick={() => onOpenFile(f)}>
 {t('tenderator.docsTab.card.openButton')}
 </button>
 <button
 type="button"
 className="tender-docs-tab__card-icon"
 title={t('tenderator.docsTab.card.complyButtonTitle')}
 onClick={() => {
 const params = new URLSearchParams();
 params.set('template_id', f.template_id);
 if (f.funding_mode) params.set('funding_mode', f.funding_mode);
 navigate(`/eulawcomply?${params.toString()}`);
 }}
 >
 <span className="mdi mdi-clipboard-check-outline" />
 </button>
 <button
 type="button"
 className="tender-docs-tab__card-icon"
 title={t('tenderator.docsTab.card.chatButtonTitle')}
 onClick={() => {
 navigate('/chat', {
 state: {
 initialQuestion: t('tenderator.docsTab.card.chatInitialQuestion', { title: f.title, programme: t(PROGRAMME_LABELS[f.programme] || f.programme), subInstrument: f.sub_instrument ? t(SUB_INSTRUMENT_LABELS[f.sub_instrument] || f.sub_instrument) : '' }),
 source: 'tender_docs_tab',
 },
 });
 }}
 >
 <span className="mdi mdi-chat-outline" />
 </button>
 </div>
 </article>
 );
 })}
 </div>
 )}
 </section>
 </div>
 );
};

export default TenderDocsTab;
