/**
 * Transcripts tab (MEUB Section 3 - Institutional Monitoring).
 *
 * Catalog of completed EP committee transcripts + PI-suggested recordings the
 * user can transcribe on-demand (Blue tier) + open/read + save to My Files.
 * Surfaces the existing committee transcription pipeline; no ASR in the client.
 */
import { useEffect, useState, useCallback, useRef } from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import Hls from 'hls.js';
import Icon from '@mdi/react';
import {
  mdiMicrophoneMessage, mdiMagnify, mdiClose, mdiFileDownloadOutline,
  mdiPlayCircleOutline, mdiLoading, mdiCheckCircle, mdiAlertCircleOutline,
  mdiViewListOutline, mdiClockOutline, mdiAccountVoice, mdiOpenInNew, mdiPlaylistPlus,
  mdiTextBoxOutline, mdiFormatListBulleted, mdiCreation, mdiFilePdfBox,
} from '@mdi/js';
import { transcriptsService } from '../../services/transcripts_service';
import type { TranscriptSummary, TranscriptDetail, AgendaItem } from '../../services/transcripts_service';
import './transcripts_tab.css';
import { FreshnessChip } from './freshness_chip';

const POLL_MS = 6000;

// Summary languages (Brubru's six). Native labels for the selector.
const SUMMARY_LANGS: { code: string; label: string }[] = [
  { code: 'en', label: 'English' }, { code: 'es', label: 'Español' },
  { code: 'fr', label: 'Français' }, { code: 'it', label: 'Italiano' },
  { code: 'nl', label: 'Nederlands' }, { code: 'ca', label: 'Català' },
];
const SUMMARY_LANG_CODES = SUMMARY_LANGS.map((l) => l.code);

const fmtClock = (sec?: number | null) => {
  if (typeof sec !== 'number' || sec < 0) return null;
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
  const h = Math.floor(m / 60);
  return h > 0 ? `${h}:${String(m % 60).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    : `${m}:${String(s).padStart(2, '0')}`;
};

// Minimal markdown renderer for summaries (## headings, - bullets, **bold**).
function renderSummaryMarkdown(md: string): ReactNode[] {
  const inline = (s: string): ReactNode[] =>
    s.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
      part.startsWith('**') && part.endsWith('**')
        ? <strong key={i}>{part.slice(2, -2)}</strong>
        : <span key={i}>{part}</span>);
  const blocks: ReactNode[] = [];
  let bullets: ReactNode[] = [];
  const flush = () => {
    if (bullets.length) { blocks.push(<ul key={`u${blocks.length}`}>{bullets}</ul>); bullets = []; }
  };
  (md || '').split('\n').forEach((raw, i) => {
    const line = raw.trimEnd();
    if (!line.trim()) { flush(); return; }
    const h = line.match(/^(#{2,4})\s+(.*)$/);
    if (h) { flush(); blocks.push(<h5 key={`h${i}`}>{inline(h[2])}</h5>); return; }
    const b = line.match(/^[-•]\s+(.*)$/);
    if (b) { bullets.push(<li key={`l${i}`}>{inline(b[1])}</li>); return; }
    flush(); blocks.push(<p key={`p${i}`}>{inline(line)}</p>);
  });
  flush();
  return blocks;
}

export function TranscriptsTab() {
  const { t } = useTranslation();
  const [myInterests, setMyInterests] = useState(true);
  const [search, setSearch] = useState('');
  const [items, setItems] = useState<TranscriptSummary[]>([]);
  const [suggestions, setSuggestions] = useState<TranscriptSummary[]>([]);
  const [canTranscribe, setCanTranscribe] = useState(false);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<TranscriptDetail | null>(null);
  const [busy, setBusy] = useState<Record<string, string>>({}); // id -> status
  const [prog, setProg] = useState<Record<string, { stage: string | null; pct: number | null }>>({});
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const [institution, setInstitution] = useState('');
  const [body, setBody] = useState('');
  const [facets, setFacets] = useState<{ institutions: string[]; bodies: Record<string, string[]> }>({ institutions: [], bodies: {} });

  useEffect(() => {
    transcriptsService.facets().then(setFacets).catch(() => {});
  }, []);

  const loadCatalog = useCallback(async () => {
    setLoading(true);
    try {
      const [cat, sug] = await Promise.all([
        transcriptsService.list(myInterests, search || undefined, institution || undefined, body || undefined),
        transcriptsService.suggestions(myInterests, institution || undefined, body || undefined),
      ]);
      setItems(cat.items);
      setSuggestions(sug.items);
      setCanTranscribe(sug.can_transcribe);
    } catch { /* tier or network */ }
    setLoading(false);
  }, [myInterests, search, institution, body]);

  useEffect(() => { loadCatalog(); }, [loadCatalog]);

  const bodyOptions = institution ? (facets.bodies[institution] || []) : [];
  // A single body that equals the institution code (EC/COUNCIL) is not worth a dropdown.
  const showBodyDropdown = bodyOptions.length > 1 || (bodyOptions.length === 1 && bodyOptions[0] !== institution);

  // Poll an in-progress transcription until it settles.
  const poll = useCallback((id: string) => {
    const tick = async () => {
      try {
        const s = await transcriptsService.status(id);
        setBusy((b) => ({ ...b, [id]: s.status }));
        setProg((p) => ({ ...p, [id]: { stage: s.stage, pct: s.progress } }));
        if (s.status === 'completed' || s.status === 'failed') {
          setBusy((b) => { const n = { ...b }; delete n[id]; return n; });
          setProg((p) => { const n = { ...p }; delete n[id]; return n; });
          loadCatalog();
          return;
        }
      } catch { /* keep polling */ }
      setTimeout(tick, POLL_MS);
    };
    setTimeout(tick, POLL_MS);
  }, [loadCatalog]);

  const onTranscribe = async (id: string) => {
    setBusy((b) => ({ ...b, [id]: 'transcribing' }));
    try {
      const r = await transcriptsService.transcribe(id);
      if (r.status === 'completed') { setBusy((b) => { const n = { ...b }; delete n[id]; return n; }); loadCatalog(); }
      else poll(id);
    } catch {
      setBusy((b) => { const n = { ...b }; delete n[id]; return n; });
    }
  };

  const openDetail = async (id: string) => {
    setDetail(null);
    try { setDetail(await transcriptsService.get(id)); } catch { /* */ }
  };

  const onSave = async (id: string) => {
    try {
      const r = await transcriptsService.saveToFiles(id);
      setSavedMsg(r.title);
      setTimeout(() => setSavedMsg(null), 4000);
    } catch { /* tier */ }
  };

  // Badge text: EP shows the committee code (informative); EC/Council show the
  // institution name. Colour by institution.
  const bodyBadge = (institution: string, committee: string) =>
    institution === 'EP' ? committee : t(`bubble.transcripts.inst.${institution}`, institution);
  const instClass = (institution: string) => `transcript-card__cm inst-${institution.toLowerCase()}`;

  const fmtDate = (iso: string | null) => {
    if (!iso) return '';
    try { return new Date(iso + 'T00:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }); }
    catch { return iso; }
  };

  return (
    <div className="transcripts-tab">
      <header className="transcripts-tab__header">
        <div className="transcripts-tab__title">
          <Icon path={mdiMicrophoneMessage} size={1.1} />
          <div>
            <h2>{t('bubble.transcripts.title', 'Transcripts')}</h2>
            <p>{t('bubble.transcripts.subtitle', 'AI transcripts of European Parliament committee debates. Open one, or transcribe a recording on demand.')}</p>
            <FreshnessChip sourceKey="transcripts" />
          </div>
        </div>
      </header>

      {/* Filters - apply to both Suggested and the catalog below */}
      <div className="transcripts-tab__controls">
        <div className="transcripts-tab__toggle">
          <button className={myInterests ? 'is-active' : ''} onClick={() => setMyInterests(true)}>{t('bubble.transcripts.mine', 'My interests')}</button>
          <button className={!myInterests ? 'is-active' : ''} onClick={() => setMyInterests(false)}>{t('bubble.transcripts.all', 'All')}</button>
        </div>
        <select
          className="transcripts-tab__select"
          value={institution}
          onChange={(e) => { setInstitution(e.target.value); setBody(''); }}
        >
          <option value="">{t('bubble.transcripts.allInstitutions', 'All institutions')}</option>
          {facets.institutions.map((i) => (
            <option key={i} value={i}>{t(`bubble.transcripts.inst.${i}`, i)}</option>
          ))}
        </select>
        {institution && showBodyDropdown && (
          <select className="transcripts-tab__select" value={body} onChange={(e) => setBody(e.target.value)}>
            <option value="">{t('bubble.transcripts.allBodies', 'All bodies')}</option>
            {bodyOptions.map((b) => (
              <option key={b} value={b}>{b}</option>
            ))}
          </select>
        )}
        <div className="transcripts-tab__search">
          <Icon path={mdiMagnify} size={0.8} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('bubble.transcripts.searchPlaceholder', 'Search transcripts') as string}
          />
        </div>
      </div>

      {/* Suggested recordings to transcribe (PI-relevant) */}
      {suggestions.length > 0 && (
        <section className="transcripts-tab__suggested">
          <h3>{t('bubble.transcripts.suggested', 'Suggested for you')}</h3>
          {!canTranscribe && (
            <p className="transcripts-tab__hint">{t('bubble.transcripts.blueHint', 'On-demand transcription is a Professional feature.')}</p>
          )}
          <div className="transcripts-grid">
            {suggestions.map((s) => {
              const state = busy[s.id];
              return (
                <div key={s.id} className="transcript-card transcript-card--suggested">
                  <span className={instClass(s.institution)}>{bodyBadge(s.institution, s.committee_code)}</span>
                  <div className="transcript-card__date">{fmtDate(s.meeting_date)}</div>
                  <div className="transcript-card__title">{s.title}</div>
                  {state ? (
                    <div className="transcript-progress">
                      <div className="transcript-progress__label">
                        <Icon path={mdiLoading} size={0.65} spin />
                        <span>
                          {prog[s.id]?.stage === 'preparing'
                            ? t('bubble.transcripts.preparing', 'Preparing audio…')
                            : t('bubble.transcripts.transcribing', 'Transcribing…')}
                          {typeof prog[s.id]?.pct === 'number' ? ` ${Math.round(prog[s.id]!.pct as number)}%` : ''}
                        </span>
                      </div>
                      <div className="transcript-progress__track">
                        <div
                          className={`transcript-progress__fill${typeof prog[s.id]?.pct === 'number' ? '' : ' is-indeterminate'}`}
                          style={typeof prog[s.id]?.pct === 'number' ? { width: `${prog[s.id]!.pct}%` } : undefined}
                        />
                      </div>
                    </div>
                  ) : (
                    <button
                      className="transcript-card__btn"
                      disabled={!canTranscribe}
                      onClick={() => onTranscribe(s.id)}
                    >
                      <Icon path={mdiPlayCircleOutline} size={0.7} /> {t('bubble.transcripts.transcribe', 'Transcribe')}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Catalog */}
      {loading ? (
        <div className="transcripts-tab__empty"><Icon path={mdiLoading} size={1} spin /></div>
      ) : items.length === 0 ? (
        <div className="transcripts-tab__empty">{t('bubble.transcripts.empty', 'No transcripts yet. Transcribe a suggested recording above.')}</div>
      ) : (
        <div className="transcripts-grid">
          {items.map((it) => (
            <button key={it.id} className="transcript-card" onClick={() => openDetail(it.id)}>
              <span className={instClass(it.institution)}>{bodyBadge(it.institution, it.committee_code)}</span>
              <div className="transcript-card__date">{fmtDate(it.meeting_date)}</div>
              <div className="transcript-card__title">{it.title}</div>
              <div className="transcript-card__meta">
                {it.word_count.toLocaleString()} {t('bubble.transcripts.words', 'words')} · {it.duration_minutes} {t('bubble.transcripts.min', 'min')}
                {it.procedure_refs.length > 0 && <> · {it.procedure_refs.length} {t('bubble.transcripts.refs', 'refs')}</>}
                {it.official_minutes && it.official_minutes.length > 0 && (
                  <span className="transcript-card__minutes-flag" title={t('bubble.transcripts.officialMinutesTip', 'Official adopted minutes available') as string}>
                    {' '}· <Icon path={mdiFilePdfBox} size={0.55} /> {t('bubble.transcripts.minutes', 'minutes')}
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>
      )}

      {savedMsg && (
        <div className="transcripts-tab__saved"><Icon path={mdiCheckCircle} size={0.8} /> {t('bubble.transcripts.saved', 'Saved to My Files')}: {savedMsg}</div>
      )}

      {/* Detail modal (portal to escape the AnimatedPage transform) */}
      {detail && createPortal(
        <TranscriptDetailModal
          detail={detail}
          onClose={() => setDetail(null)}
          onSave={() => onSave(detail.id)}
          instClass={instClass}
          bodyBadge={bodyBadge}
          fmtDate={fmtDate}
        />,
        document.body,
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail modal: HLS video + agenda chapter rail + time-synced transcript
// ---------------------------------------------------------------------------

interface DetailModalProps {
  detail: TranscriptDetail;
  onClose: () => void;
  onSave: () => void;
  instClass: (i: string) => string;
  bodyBadge: (i: string, c: string) => string;
  fmtDate: (iso: string | null) => string;
}

function TranscriptDetailModal({ detail, onClose, onSave, instClass, bodyBadge, fmtDate }: DetailModalProps) {
  const { t, i18n } = useTranslation();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const segRefs = useRef<Record<number, HTMLParagraphElement | null>>({});
  const [agenda, setAgenda] = useState<AgendaItem[]>(detail.agenda_items || []);
  const [attaching, setAttaching] = useState(false);
  const [agendaMsg, setAgendaMsg] = useState<string | null>(null);
  const [activeIdx, setActiveIdx] = useState<number>(-1);
  const [activeItem, setActiveItem] = useState<number | null>(null);

  const segments = detail.segments || [];
  const isHls = !!detail.video_url && detail.video_url.endsWith('.m3u8');
  const hasVideo = !!detail.video_url;
  const isEpCommittee = detail.institution === 'EP' && detail.committee_code !== 'PLENARY';

  // ---- summaries -----------------------------------------------------------
  const prefLang = SUMMARY_LANG_CODES.includes((i18n.language || 'en').slice(0, 2))
    ? (i18n.language || 'en').slice(0, 2) : 'en';
  const [view, setView] = useState<'summary' | 'transcript'>(
    (detail.summary_langs && detail.summary_langs.length) ? 'summary' : 'transcript');
  const [sumLang, setSumLang] = useState<string>(
    detail.summary_langs?.includes(prefLang) ? prefLang
      : (detail.summary_langs?.[0] || prefLang));
  const [availLangs, setAvailLangs] = useState<string[]>(detail.summary_langs || []);
  const [sumByLang, setSumByLang] = useState<Record<string, string | null>>({});
  const [sumLoading, setSumLoading] = useState(false);
  const [sumGenerating, setSumGenerating] = useState(false);
  const [sumErr, setSumErr] = useState<string | null>(null);
  const [canGenerate, setCanGenerate] = useState(false);

  const loadSummary = useCallback(async (lang: string) => {
    if (sumByLang[lang] !== undefined) return;
    setSumLoading(true); setSumErr(null);
    try {
      const r = await transcriptsService.getSummary(detail.id, lang);
      setSumByLang((m) => ({ ...m, [lang]: r.summary }));
      setAvailLangs(r.available_langs);
      setCanGenerate(r.can_generate);
    } catch { setSumErr(t('bubble.transcripts.summaryError', 'Could not load the summary.') as string); }
    setSumLoading(false);
  }, [detail.id, sumByLang, t]);

  useEffect(() => { if (view === 'summary') loadSummary(sumLang); }, [view, sumLang, loadSummary]);

  const onGenerateSummary = async () => {
    setSumGenerating(true); setSumErr(null);
    try {
      const r = await transcriptsService.generateSummary(detail.id, sumLang);
      setSumByLang((m) => ({ ...m, [sumLang]: r.summary }));
      setAvailLangs(r.available_langs);
    } catch {
      setSumErr(t('bubble.transcripts.summaryGenError', 'Summary generation failed. Please try again.') as string);
    }
    setSumGenerating(false);
  };

  const summaryText = sumByLang[sumLang];

  // Attach the HLS stream to the <video> element.
  useEffect(() => {
    const v = videoRef.current;
    if (!v || !detail.video_url) return;
    if (isHls && Hls.isSupported()) {
      const hls = new Hls({ enableWorker: true });
      hls.loadSource(detail.video_url);
      hls.attachMedia(v);
      return () => hls.destroy();
    }
    // Safari plays HLS natively; non-HLS (mp4) just sets src.
    v.src = detail.video_url;
  }, [detail.video_url, isHls]);

  // Track the active transcript line as the video plays.
  const onTimeUpdate = useCallback(() => {
    const v = videoRef.current;
    if (!v || segments.length === 0) return;
    const tt = v.currentTime;
    // last segment whose start <= currentTime (binary-ish linear is fine here)
    let lo = 0;
    for (let i = 0; i < segments.length; i++) {
      if (segments[i].s <= tt) lo = i; else break;
    }
    setActiveIdx((prev) => (prev === lo ? prev : lo));
  }, [segments]);

  const seekTo = useCallback((sec?: number | null, itemNo?: number) => {
    if (typeof sec !== 'number') return;
    const v = videoRef.current;
    if (v) { v.currentTime = sec; v.play().catch(() => {}); }
    if (typeof itemNo === 'number') setActiveItem(itemNo);
    // scroll the transcript to the nearest segment
    if (segments.length) {
      let idx = 0;
      for (let i = 0; i < segments.length; i++) { if (segments[i].s <= sec) idx = i; else break; }
      segRefs.current[idx]?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
  }, [segments]);

  const onAttachAgenda = async () => {
    setAttaching(true);
    setAgendaMsg(null);
    try {
      const r = await transcriptsService.attachAgenda(detail.id);
      setAgenda(r.agenda_items || []);
      if (!r.agenda_items?.length) setAgendaMsg(t('bubble.transcripts.agendaNone', 'No matching agenda found.'));
    } catch {
      setAgendaMsg(t('bubble.transcripts.agendaNone', 'No matching agenda found.'));
    }
    setAttaching(false);
  };

  const timedCount = agenda.filter((a) => typeof a.start_time === 'number').length;

  return (
    <div className="transcript-modal" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="transcript-modal__panel" onClick={(e) => e.stopPropagation()}>
        <header className="transcript-modal__head">
          <div>
            <span className={instClass(detail.institution)}>{bodyBadge(detail.institution, detail.committee_code)}</span>
            <h3>{detail.title}</h3>
            <div className="transcript-card__meta">
              {fmtDate(detail.meeting_date)} · {detail.word_count.toLocaleString()} {t('bubble.transcripts.words', 'words')} · {detail.duration_minutes} {t('bubble.transcripts.min', 'min')} · {detail.engine}
            </div>
          </div>
          <button className="transcript-modal__close" onClick={onClose}><Icon path={mdiClose} size={0.9} /></button>
        </header>

        {detail.procedure_refs.length > 0 && (
          <div className="transcript-modal__refs">
            {detail.procedure_refs.map((r) => <span key={r} className="transcript-ref">{r}</span>)}
          </div>
        )}

        <div className="transcript-modal__actions">
          <button className="transcript-card__btn" onClick={onSave}>
            <Icon path={mdiFileDownloadOutline} size={0.7} /> {t('bubble.transcripts.saveToFiles', 'Save to My Files')}
          </button>
          {isEpCommittee && agenda.length === 0 && (
            <button className="transcript-card__btn is-ghost" onClick={onAttachAgenda} disabled={attaching}>
              <Icon path={attaching ? mdiLoading : mdiPlaylistPlus} size={0.7} spin={attaching} />
              {t('bubble.transcripts.linkAgenda', 'Link agenda')}
            </button>
          )}
          {detail.multimedia_url && (
            <a className="transcript-card__btn is-ghost" href={detail.multimedia_url} target="_blank" rel="noopener noreferrer">
              <Icon path={mdiOpenInNew} size={0.7} /> {t('bubble.transcripts.watchOnEp', 'Watch on EP')}
            </a>
          )}
          {(detail.official_minutes || []).map((m, i) => (
            <a key={i} className="transcript-card__btn is-ghost" href={m.pdf_url || m.source_url || undefined}
              target="_blank" rel="noopener noreferrer"
              title={t('bubble.transcripts.officialMinutesTip', 'Official adopted minutes available') as string}>
              <Icon path={mdiFilePdfBox} size={0.7} /> {t('bubble.transcripts.officialMinutes', 'Official minutes (PDF)')}
            </a>
          ))}
        </div>
        {agendaMsg && <p className="transcripts-tab__hint">{agendaMsg}</p>}

        {hasVideo && (
          <div className="transcript-modal__player">
            <video ref={videoRef} controls playsInline onTimeUpdate={onTimeUpdate} />
          </div>
        )}

        {/* View toggle: multilingual summary | full transcript */}
        <div className="transcript-viewtabs" role="tablist">
          <button role="tab" aria-selected={view === 'summary'}
            className={view === 'summary' ? 'is-active' : ''} onClick={() => setView('summary')}>
            <Icon path={mdiTextBoxOutline} size={0.7} /> {t('bubble.transcripts.summary', 'Summary')}
          </button>
          <button role="tab" aria-selected={view === 'transcript'}
            className={view === 'transcript' ? 'is-active' : ''} onClick={() => setView('transcript')}>
            <Icon path={mdiFormatListBulleted} size={0.7} /> {t('bubble.transcripts.transcript', 'Transcript')}
          </button>
        </div>

        {view === 'summary' && (
          <div className="transcript-summary">
            <div className="transcript-summary__bar">
              <div className="transcript-summary__langs">
                {SUMMARY_LANGS.map((l) => (
                  <button key={l.code}
                    className={`transcript-summary__lang${sumLang === l.code ? ' is-active' : ''}${availLangs.includes(l.code) ? ' has-summary' : ''}`}
                    onClick={() => setSumLang(l.code)}>
                    {l.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="transcript-summary__body">
              {sumLoading ? (
                <div className="transcripts-tab__empty"><Icon path={mdiLoading} size={1} spin /></div>
              ) : sumErr ? (
                <p className="transcripts-tab__hint"><Icon path={mdiAlertCircleOutline} size={0.7} /> {sumErr}</p>
              ) : summaryText ? (
                <article className="transcript-summary__doc">{renderSummaryMarkdown(summaryText)}</article>
              ) : (
                <div className="transcript-summary__empty">
                  <Icon path={mdiTextBoxOutline} size={1.6} />
                  <p>{t('bubble.transcripts.summaryAbsent', 'No summary in this language yet.')}</p>
                  {canGenerate ? (
                    <button className="transcript-card__btn" onClick={onGenerateSummary} disabled={sumGenerating}>
                      <Icon path={sumGenerating ? mdiLoading : mdiCreation} size={0.7} spin={sumGenerating} />
                      {sumGenerating
                        ? t('bubble.transcripts.summaryGenerating', 'Generating…')
                        : t('bubble.transcripts.generateSummary', 'Generate summary')}
                    </button>
                  ) : (
                    <p className="transcripts-tab__hint">{t('bubble.transcripts.summaryBlueHint', 'AI summaries are a Professional feature.')}</p>
                  )}
                </div>
              )}
              {summaryText && (
                <p className="transcript-summary__provenance">
                  {t('bubble.transcripts.summaryProvenance', 'AI-generated institutional summary. Verify against the transcript and the source recording.')}
                </p>
              )}
            </div>
          </div>
        )}

        {view === 'transcript' && (
        <div className="transcript-modal__split">
          {/* Agenda chapter rail */}
          {agenda.length > 0 && (
            <aside className="transcript-agenda">
              <h4>
                <Icon path={mdiViewListOutline} size={0.75} /> {t('bubble.transcripts.agenda', 'Agenda')}
                {timedCount > 0 && hasVideo && (
                  <span className="transcript-agenda__hint">{t('bubble.transcripts.agendaHint', 'Click an item to jump')}</span>
                )}
              </h4>
              <ol className="transcript-agenda__list">
                {agenda.map((it) => {
                  const ts = fmtClock(it.start_time);
                  const clickable = typeof it.start_time === 'number' && hasVideo;
                  return (
                    <li
                      key={it.number}
                      className={`transcript-agenda__item${clickable ? ' is-clickable' : ''}${activeItem === it.number ? ' is-active' : ''}`}
                      onClick={clickable ? () => seekTo(it.start_time, it.number) : undefined}
                    >
                      <div className="transcript-agenda__top">
                        <span className="transcript-agenda__num">{it.number}</span>
                        {ts && <span className="transcript-agenda__ts"><Icon path={mdiClockOutline} size={0.55} /> {ts}</span>}
                      </div>
                      <div className="transcript-agenda__title">{it.title}</div>
                      <div className="transcript-agenda__meta">
                        {it.procedure_ref && <span className="transcript-ref is-sm">{it.procedure_ref}</span>}
                        {it.rapporteur && <span className="transcript-agenda__rapp"><Icon path={mdiAccountVoice} size={0.55} /> {it.rapporteur}</span>}
                      </div>
                    </li>
                  );
                })}
              </ol>
            </aside>
          )}

          {/* Transcript */}
          <div className={`transcript-modal__body${agenda.length > 0 ? ' has-agenda' : ''}`}>
            {detail.error_message ? (
              <p className="transcripts-tab__hint"><Icon path={mdiAlertCircleOutline} size={0.7} /> {detail.error_message}</p>
            ) : segments.length > 0 ? (
              segments.map((seg, i) => (
                <p
                  key={i}
                  ref={(el) => { segRefs.current[i] = el; }}
                  className={`transcript-line${activeIdx === i ? ' is-active' : ''}`}
                  onClick={() => seekTo(seg.s)}
                  title={hasVideo ? (fmtClock(seg.s) || '') : undefined}
                >
                  {seg.t}
                </p>
              ))
            ) : (
              (detail.transcript_text || '').split('\n').filter(Boolean).map((p, i) => <p key={i}>{p}</p>)
            )}
          </div>
        </div>
        )}
      </div>
    </div>
  );
}
