/**
 * EP Plenary - Order of Business tab (MEUB Section 3). Upcoming sittings + the
 * dossiers plenary recently adopted on the user's interests, PI-filtered.
 */
import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiGavel, mdiMagnify, mdiLoading, mdiCalendarStar, mdiFileDocumentCheckOutline, mdiOpenInNew,
  mdiSitemapOutline,
} from '@mdi/js';
import { plenaryAgendaService } from '../../services/plenary_agenda_service';
import type { PlenaryOoB } from '../../services/plenary_agenda_service';
import { MeubHeader } from './meub_header';
import './plenary_agenda_tab.css';

export function PlenaryAgendaTab() {
  const { t } = useTranslation();
  const [myInterests, setMyInterests] = useState(true);
  const [search, setSearch] = useState('');
  const [data, setData] = useState<PlenaryOoB | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try { setData(await plenaryAgendaService.get(myInterests, search || undefined)); }
    catch { /* */ }
    setLoading(false);
  }, [myInterests, search]);
  useEffect(() => { load(); }, [load]);

  const fmtDate = (iso: string | null) => { if (!iso) return ''; try { return new Date(iso.slice(0, 10) + 'T00:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }); } catch { return iso; } };

  return (
    <div className="plen-tab">
      <MeubHeader
        icon={mdiGavel}
        title={t('bubble.plen.title', 'Plenary - Order of Business')}
        subtitle={t('bubble.plen.subtitle', 'Upcoming plenary sittings and the dossiers recently adopted on your interests.')}
      />

      <div className="plen-tab__controls">
        <div className="plen-tab__toggle">
          <button className={myInterests ? 'is-active' : ''} onClick={() => setMyInterests(true)}>{t('bubble.plen.mine', 'My interests')}</button>
          <button className={!myInterests ? 'is-active' : ''} onClick={() => setMyInterests(false)}>{t('bubble.plen.all', 'All')}</button>
        </div>
        <div className="plen-tab__search">
          <Icon path={mdiMagnify} size={0.8} />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t('bubble.plen.search', 'Search a dossier') as string} />
        </div>
      </div>

      {loading ? (
        <div className="plen-tab__empty"><Icon path={mdiLoading} size={1} spin /></div>
      ) : !data ? (
        <div className="plen-tab__empty">{t('bubble.plen.none', 'No plenary data yet.')}</div>
      ) : (
        <>
          {/* Upcoming sittings */}
          <section className="plen-section">
            <h4><Icon path={mdiCalendarStar} size={0.75} /> {t('bubble.plen.upcoming', 'Upcoming sittings')}</h4>
            {data.sessions.length === 0 ? (
              <p className="plen-muted">{t('bubble.plen.noSessions', 'No upcoming sittings scheduled.')}</p>
            ) : (
              <div className="plen-sessions">
                {data.sessions.map((s, i) => (
                  <div className="plen-session" key={i}>
                    <Icon path={mdiCalendarStar} size={0.7} />
                    <div>
                      <b>{fmtDate(s.date)}{s.end_date && s.end_date !== s.date ? ` – ${fmtDate(s.end_date)}` : ''}</b>
                      <span>{s.title}</span>
                    </div>
                    {s.agenda_url && <a href={s.agenda_url} target="_blank" rel="noopener noreferrer"><Icon path={mdiOpenInNew} size={0.55} /></a>}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Recently adopted business */}
          <section className="plen-section">
            <h4><Icon path={mdiFileDocumentCheckOutline} size={0.75} /> {t('bubble.plen.recent', 'Recently adopted on your interests')}</h4>
            {data.business.length === 0 ? (
              <p className="plen-muted">{t('bubble.plen.noBusiness', 'No recent plenary business matches your interests.')}</p>
            ) : (
              <ul className="plen-biz">
                {data.business.map((b, i) => (
                  <li key={i} className="plen-bizitem">
                    <div className="plen-bizitem__top">
                      {b.procedure_ref && <span className="plen-chip">{b.procedure_ref}</span>}
                      {b.committees.slice(0, 3).map((c) => <span key={c} className="plen-chip is-cmte">{c}</span>)}
                      <span className="plen-bizitem__date">{fmtDate(b.adoption_date)}</span>
                    </div>
                    <div className="plen-bizitem__title">
                      {b.document_url ? <a href={b.document_url} target="_blank" rel="noopener noreferrer">{b.title}</a> : b.title}
                    </div>
                    <div className="plen-bizitem__links">
                      {b.document_url && (
                        <a href={b.document_url} target="_blank" rel="noopener noreferrer"><Icon path={mdiOpenInNew} size={0.55} /> {t('bubble.plen.adoptedText', 'Adopted text')}</a>
                      )}
                      {b.oeil_url && (
                        <a href={b.oeil_url} target="_blank" rel="noopener noreferrer"><Icon path={mdiSitemapOutline} size={0.55} /> {t('bubble.plen.procedureFile', 'Procedure file')}</a>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <p className="plen-note">{t('bubble.plen.note', 'Note: the forthcoming item-level order of business (live agenda) is being wired in. Plenary roll-call votes are in the Votes tab.')} ({data.plenary_votes} {t('bubble.plen.votes', 'plenary votes recorded')})</p>
        </>
      )}
    </div>
  );
}

export default PlenaryAgendaTab;
