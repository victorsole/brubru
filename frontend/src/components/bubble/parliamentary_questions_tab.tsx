/**
 * Parliamentary Questions tab (MEUB Section 3 - Institutional Monitoring).
 *
 * Written + oral questions tabled by MEPs, pre-filtered to the user's Policy
 * Interests. Kills the manual EP-portal flow: no SPA, no typing a topic, no
 * Googling the author - each card carries the author MEP's profile link, the
 * institution it targets, awaiting/answered status, and an AI "why this matters".
 */
import { useEffect, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiCommentQuestionOutline, mdiMagnify, mdiClose, mdiAccountVoice, mdiOpenInNew,
  mdiLoading, mdiBellRingOutline, mdiCreation, mdiBankOutline, mdiCheckCircle,
  mdiClockOutline, mdiFileDocumentOutline,
} from '@mdi/js';
import { parliamentaryQuestionsService } from '../../services/parliamentary_questions_service';
import type { QuestionSummary, QuestionDetail } from '../../services/parliamentary_questions_service';
import './parliamentary_questions_tab.css';
import { LensToggle, TrackedBadge, type LensMode } from './lens_toggle';

const TYPE_LABEL: Record<string, string> = {
  written: 'Written', oral: 'Oral', priority: 'Priority', question_time: 'Question Time',
};
const eurlex = (celex: string) =>
  `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:${encodeURIComponent(celex)}`;

export function ParliamentaryQuestionsTab() {
  const { t } = useTranslation();
  const [mode, setMode] = useState<LensMode>('pi');
  const [hasTracked, setHasTracked] = useState(false);
  const [questionType, setQuestionType] = useState('');
  const [answered, setAnswered] = useState<'' | 'true' | 'false'>('');
  const [search, setSearch] = useState('');
  const [items, setItems] = useState<QuestionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<QuestionDetail | null>(null);
  const [newCount, setNewCount] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await parliamentaryQuestionsService.list({
        myInterests: mode === 'pi',
        myFiles: mode === 'files',
        questionType: questionType || undefined,
        answered: answered === '' ? undefined : answered === 'true',
        search: search || undefined,
      });
      setItems(r.items); setTotal(r.total);
      if (typeof r.has_tracked_files === 'boolean') setHasTracked(r.has_tracked_files);
    } catch { /* tier / network */ }
    setLoading(false);
  }, [mode, questionType, answered, search]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    parliamentaryQuestionsService.newCount(14).then((r) => setNewCount(r.count)).catch(() => {});
  }, []);

  const openDetail = async (ref: string) => {
    setDetail(null);
    try { setDetail(await parliamentaryQuestionsService.get(ref)); } catch { /* */ }
  };

  const fmtDate = (iso: string | null) => {
    if (!iso) return '';
    try { return new Date(iso + 'T00:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }); }
    catch { return iso; }
  };

  return (
    <div className="parlq-tab">
      <header className="parlq-tab__header">
        <div className="parlq-tab__title">
          <Icon path={mdiCommentQuestionOutline} size={1.1} />
          <div>
            <h2>{t('bubble.parlq.title', 'Parliamentary Questions')}</h2>
            <p>{t('bubble.parlq.subtitle', 'Written and oral questions tabled by MEPs on your policy interests.')}</p>
          </div>
        </div>
        {newCount > 0 && mode === 'pi' && (
          <div className="parlq-tab__badge" title={t('bubble.parlq.newHint', 'New questions tabled on your interests recently') as string}>
            <Icon path={mdiBellRingOutline} size={0.8} />
            {t('bubble.parlq.newCount', '{{count}} new on your interests', { count: newCount })}
          </div>
        )}
      </header>

      {/* Controls */}
      <div className="parlq-tab__controls">
        <LensToggle mode={mode} onChange={setMode} hasPi hasFiles={hasTracked} />
        <select className="parlq-tab__select" value={questionType} onChange={(e) => setQuestionType(e.target.value)}>
          <option value="">{t('bubble.parlq.allTypes', 'All types')}</option>
          <option value="written">{t('bubble.parlq.written', 'Written')}</option>
          <option value="oral">{t('bubble.parlq.oral', 'Oral')}</option>
          <option value="priority">{t('bubble.parlq.priority', 'Priority')}</option>
          <option value="question_time">{t('bubble.parlq.questionTime', 'Question Time')}</option>
        </select>
        <select className="parlq-tab__select" value={answered} onChange={(e) => setAnswered(e.target.value as '' | 'true' | 'false')}>
          <option value="">{t('bubble.parlq.anyStatus', 'Any status')}</option>
          <option value="false">{t('bubble.parlq.awaiting', 'Awaiting answer')}</option>
          <option value="true">{t('bubble.parlq.answered', 'Answered')}</option>
        </select>
        <div className="parlq-tab__search">
          <Icon path={mdiMagnify} size={0.8} />
          <input value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder={t('bubble.parlq.search', 'Search questions') as string} />
        </div>
      </div>

      {loading ? (
        <div className="parlq-tab__empty"><Icon path={mdiLoading} size={1} spin /></div>
      ) : items.length === 0 ? (
        <div className="parlq-tab__empty">{t('bubble.parlq.none', 'No questions match your interests yet.')}</div>
      ) : (
        <>
          <p className="parlq-tab__count">{total.toLocaleString()} {t('bubble.parlq.results', 'questions')}</p>
          <div className="parlq-grid">
            {items.map((q) => (
              <button key={q.reference} className="parlq-card" onClick={() => openDetail(q.reference)}>
                <div className="parlq-card__top">
                  <span className={`parlq-chip is-${q.type}`}>{t(`bubble.parlq.${q.type === 'question_time' ? 'questionTime' : q.type}`, TYPE_LABEL[q.type] || q.type)}</span>
                  <span className={`parlq-status ${q.answered ? 'is-answered' : 'is-awaiting'}`}>
                    <Icon path={q.answered ? mdiCheckCircle : mdiClockOutline} size={0.55} />
                    {q.answered ? t('bubble.parlq.answered', 'Answered') : t('bubble.parlq.awaiting', 'Awaiting answer')}
                  </span>
                  <span className="parlq-card__date">{fmtDate(q.submitted_date)}</span>
                  {q.matches_tracked && <TrackedBadge />}
                </div>
                <div className="parlq-card__subject">{q.subject}</div>
                <div className="parlq-card__meta">
                  {q.meps.length > 0 && (
                    <span className="parlq-card__meps">
                      <Icon path={mdiAccountVoice} size={0.6} />
                      {q.meps.map((m) => m.name).filter(Boolean).slice(0, 3).join(', ')}
                      {q.meps.length > 3 && ` +${q.meps.length - 3}`}
                    </span>
                  )}
                  {q.answering_institution && (
                    <span className="parlq-card__addressee">
                      <Icon path={mdiBankOutline} size={0.6} /> {q.answering_institution}
                    </span>
                  )}
                  {q.related_celex.length > 0 && (
                    <span className="parlq-card__celex"><Icon path={mdiFileDocumentOutline} size={0.55} /> {q.related_celex.length} {t('bubble.parlq.refs', 'refs')}</span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </>
      )}

      {detail && createPortal(
        <QuestionDetailModal detail={detail} onClose={() => setDetail(null)} fmtDate={fmtDate} />,
        document.body,
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail modal
// ---------------------------------------------------------------------------

function QuestionDetailModal({ detail, onClose, fmtDate }: {
  detail: QuestionDetail; onClose: () => void; fmtDate: (iso: string | null) => string;
}) {
  const { t } = useTranslation();
  const [explainer, setExplainer] = useState<string | null>(detail.ai_explainer);
  const [explaining, setExplaining] = useState(false);

  const onExplain = async () => {
    setExplaining(true);
    try { const r = await parliamentaryQuestionsService.explain(detail.reference); setExplainer(r.explainer); }
    catch { /* */ }
    setExplaining(false);
  };

  return (
    <div className="parlq-modal" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="parlq-modal__panel" onClick={(e) => e.stopPropagation()}>
        <header className="parlq-modal__head">
          <div>
            <div className="parlq-modal__tags">
              <span className={`parlq-chip is-${detail.type}`}>{t(`bubble.parlq.${detail.type === 'question_time' ? 'questionTime' : detail.type}`, TYPE_LABEL[detail.type] || detail.type)}</span>
              <span className="parlq-chip is-muted">{detail.reference}</span>
              <span className={`parlq-status ${detail.answered ? 'is-answered' : 'is-awaiting'}`}>
                <Icon path={detail.answered ? mdiCheckCircle : mdiClockOutline} size={0.55} />
                {detail.answered ? t('bubble.parlq.answered', 'Answered') : t('bubble.parlq.awaiting', 'Awaiting answer')}
              </span>
            </div>
            <h3>{detail.subject}</h3>
            <p className="parlq-modal__sub">{fmtDate(detail.submitted_date)}{detail.answering_institution ? ` · ${t('bubble.parlq.to', 'to')} ${detail.answering_institution}` : ''}{detail.answering_commissioner ? ` · ${detail.answering_commissioner}` : ''}</p>
          </div>
          <button className="parlq-modal__close" onClick={onClose}><Icon path={mdiClose} size={0.9} /></button>
        </header>

        <div className="parlq-modal__body">
          {/* Author MEPs with the profile links the doceo page hides */}
          {detail.meps.length > 0 && (
            <div className="parlq-meps">
              {detail.meps.map((m, i) => (
                m.profile_url ? (
                  <a key={i} className="parlq-mep" href={m.profile_url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>
                    <Icon path={mdiAccountVoice} size={0.6} /> {m.name || m.id} <Icon path={mdiOpenInNew} size={0.5} />
                  </a>
                ) : (
                  <span key={i} className="parlq-mep is-plain"><Icon path={mdiAccountVoice} size={0.6} /> {m.name}</span>
                )
              ))}
            </div>
          )}

          {/* AI "why this matters" */}
          {explainer ? (
            <div className="parlq-explainer"><Icon path={mdiCreation} size={0.7} /> <span>{explainer}</span></div>
          ) : (
            <button className="parlq-explain-btn" onClick={onExplain} disabled={explaining}>
              <Icon path={explaining ? mdiLoading : mdiCreation} size={0.7} spin={explaining} />
              {explaining ? t('bubble.parlq.explaining', 'Analysing…') : t('bubble.parlq.explain', 'Why this matters')}
            </button>
          )}

          {/* CELEX deep-links */}
          {detail.related_celex.length > 0 && (
            <div className="parlq-celex-row">
              <span className="parlq-celex-row__lbl">{t('bubble.parlq.relatedLaws', 'Related laws')}:</span>
              {detail.related_celex.map((c) => (
                <a key={c} className="parlq-ref" href={eurlex(c)} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>{c}</a>
              ))}
            </div>
          )}

          <h4 className="parlq-section">{t('bubble.parlq.question', 'Question')}</h4>
          <div className="parlq-text">{(detail.text_question || detail.subject || '').split('\n').filter(Boolean).map((p, i) => <p key={i}>{p}</p>)}</div>

          {detail.answered && detail.text_answer && (
            <>
              <h4 className="parlq-section">{t('bubble.parlq.answer', 'Answer')}{detail.answering_commissioner ? ` - ${detail.answering_commissioner}` : ''}</h4>
              <div className="parlq-text is-answer">{detail.text_answer.split('\n').filter(Boolean).map((p, i) => <p key={i}>{p}</p>)}</div>
            </>
          )}

          {detail.source_url && (
            <a className="parlq-source" href={detail.source_url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>
              <Icon path={mdiOpenInNew} size={0.6} /> {t('bubble.parlq.officialDoc', 'Official document on EP doceo')}
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

export default ParliamentaryQuestionsTab;
