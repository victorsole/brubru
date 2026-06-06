/**
 * MEP Watch tab (MEUB Section 3) - the MEPs most active on the user's files.
 * Ranked by questions tabled on the user's interests; click an MEP to see their
 * questions and open their EP profile.
 */
import { useEffect, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiAccountTieOutline, mdiMagnify, mdiLoading, mdiClose, mdiOpenInNew,
  mdiCommentQuestionOutline, mdiCheckCircle, mdiClockOutline,
} from '@mdi/js';
import { mepWatchService } from '../../services/mep_watch_service';
import type { MepRow, MepQuestion } from '../../services/mep_watch_service';
import { MeubHeader } from './meub_header';
import './mep_watch_tab.css';

export function MepWatchTab() {
  const { t } = useTranslation();
  const [myInterests, setMyInterests] = useState(true);
  const [search, setSearch] = useState('');
  const [items, setItems] = useState<MepRow[]>([]);
  const [totalMeps, setTotalMeps] = useState(0);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState<MepRow | null>(null);
  const [questions, setQuestions] = useState<MepQuestion[] | null>(null);
  const [profileUrl, setProfileUrl] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { const r = await mepWatchService.list(myInterests, search || undefined); setItems(r.items); setTotalMeps(r.total_meps); }
    catch { /* */ }
    setLoading(false);
  }, [myInterests, search]);
  useEffect(() => { load(); }, [load]);

  const openMep = async (m: MepRow) => {
    setOpen(m); setQuestions(null); setProfileUrl(m.profile_url);
    try { const r = await mepWatchService.questions(m.name, myInterests); setQuestions(r.questions); setProfileUrl(r.profile_url || m.profile_url); }
    catch { setQuestions([]); }
  };
  const fmtDate = (iso: string | null) => { if (!iso) return ''; try { return new Date(iso.slice(0, 10) + 'T00:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }); } catch { return iso; } };
  const maxCount = Math.max(1, ...items.map((m) => m.question_count));

  return (
    <div className="mepw-tab">
      <MeubHeader
        icon={mdiAccountTieOutline}
        title={t('bubble.mepw.title', 'MEP Watch')}
        subtitle={t('bubble.mepw.subtitle', 'The MEPs most active on your policy interests, and what they are asking.')}
      />

      <div className="mepw-tab__controls">
        <div className="mepw-tab__toggle">
          <button className={myInterests ? 'is-active' : ''} onClick={() => setMyInterests(true)}>{t('bubble.mepw.mine', 'My interests')}</button>
          <button className={!myInterests ? 'is-active' : ''} onClick={() => setMyInterests(false)}>{t('bubble.mepw.all', 'All')}</button>
        </div>
        <div className="mepw-tab__search">
          <Icon path={mdiMagnify} size={0.8} />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t('bubble.mepw.search', 'Search a topic') as string} />
        </div>
        {!loading && <span className="mepw-tab__count">{totalMeps.toLocaleString()} {t('bubble.mepw.activeMeps', 'MEPs active')}</span>}
      </div>

      {loading ? (
        <div className="mepw-tab__empty"><Icon path={mdiLoading} size={1} spin /></div>
      ) : items.length === 0 ? (
        <div className="mepw-tab__empty">{t('bubble.mepw.none', 'No MEP activity matches your interests yet.')}</div>
      ) : (
        <div className="mepw-grid">
          {items.map((m, i) => (
            <button key={m.name} className="mepw-card" onClick={() => openMep(m)}>
              <div className="mepw-card__rank">{i + 1}</div>
              <div className="mepw-card__main">
                <div className="mepw-card__name">{m.name}</div>
                <div className="mepw-card__bar"><span style={{ width: `${(m.question_count / maxCount) * 100}%` }} /></div>
                <div className="mepw-card__meta">
                  <b>{m.question_count}</b> {t('bubble.mepw.questions', 'questions')}
                  {m.latest_date && <> · {t('bubble.mepw.latest', 'latest')} {fmtDate(m.latest_date)}</>}
                </div>
                {m.sample_subjects[0] && <div className="mepw-card__subj">{m.sample_subjects[0]}</div>}
              </div>
            </button>
          ))}
        </div>
      )}

      {open && createPortal(
        <div className="mepw-modal" role="dialog" aria-modal="true" onClick={() => setOpen(null)}>
          <div className="mepw-modal__panel" onClick={(e) => e.stopPropagation()}>
            <header className="mepw-modal__head">
              <div>
                <h3><Icon path={mdiAccountTieOutline} size={0.85} /> {open.name}</h3>
                {profileUrl && <a className="mepw-profile" href={profileUrl} target="_blank" rel="noopener noreferrer">{t('bubble.mepw.profile', 'EP profile')} <Icon path={mdiOpenInNew} size={0.55} /></a>}
              </div>
              <button className="mepw-modal__close" onClick={() => setOpen(null)}><Icon path={mdiClose} size={0.9} /></button>
            </header>
            <div className="mepw-modal__body">
              <h5><Icon path={mdiCommentQuestionOutline} size={0.7} /> {myInterests ? t('bubble.mepw.questionsOnYours', 'Questions on your interests') : t('bubble.mepw.allQuestions', 'Recent questions')}</h5>
              {questions === null ? (
                <div className="mepw-tab__empty"><Icon path={mdiLoading} size={0.9} spin /></div>
              ) : questions.length === 0 ? (
                <p className="mepw-muted">{t('bubble.mepw.noQ', 'No questions found.')}</p>
              ) : (
                <ul className="mepw-qlist">
                  {questions.map((q) => (
                    <li key={q.reference}>
                      <span className={`mepw-status ${q.answered ? 'is-answered' : 'is-awaiting'}`} title={q.answered ? 'Answered' : 'Awaiting answer'}>
                        <Icon path={q.answered ? mdiCheckCircle : mdiClockOutline} size={0.55} />
                      </span>
                      <a href={q.source_url} target="_blank" rel="noopener noreferrer">{q.subject}</a>
                      <span className="mepw-qdate">{fmtDate(q.submitted_date)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>,
        document.body,
      )}
    </div>
  );
}

export default MepWatchTab;
