/**
 * Council Watch tab (MEUB Section 3) - what the Council of the EU is doing on the
 * user's topics: configuration meetings + outcomes/press, PI-filtered.
 */
import { useEffect, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiAccountGroup, mdiMagnify, mdiLoading, mdiCalendarClock, mdiBullhornOutline,
  mdiGavel, mdiOpenInNew, mdiDomain, mdiClose, mdiCreation, mdiAccountMultipleOutline,
  mdiMapMarkerOutline,
} from '@mdi/js';
import { councilWatchService } from '../../services/council_watch_service';
import type { CouncilItem, CouncilStats, PermRep } from '../../services/council_watch_service';
import './council_watch_tab.css';

export function CouncilWatchTab() {
  const { t, i18n } = useTranslation();
  const [myInterests, setMyInterests] = useState(true);
  const [kind, setKind] = useState('all');
  const [search, setSearch] = useState('');
  const [items, setItems] = useState<CouncilItem[]>([]);
  const [stats, setStats] = useState<CouncilStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<CouncilItem | null>(null);
  const [summary, setSummary] = useState<string | null>(null);
  const [summarising, setSummarising] = useState(false);
  const [permreps, setPermreps] = useState<PermRep[]>([]);
  const [prSearch, setPrSearch] = useState('');
  const [view, setView] = useState<'activity' | 'permreps'>('activity');

  useEffect(() => { councilWatchService.permreps().then((r) => setPermreps(r.items)).catch(() => {}); }, []);

  const openDetail = (it: CouncilItem) => { setDetail(it); setSummary(null); setSummarising(false); };
  const onSummarise = async () => {
    if (!detail) return;
    setSummarising(true);
    try { const r = await councilWatchService.summarise(detail, (i18n.language || 'en').slice(0, 2)); setSummary(r.summary); }
    catch { setSummary(t('bubble.cwatch.summaryError', 'Could not generate the summary.') as string); }
    setSummarising(false);
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [l, s] = await Promise.all([
        councilWatchService.list(myInterests, kind, search || undefined),
        councilWatchService.stats(myInterests),
      ]);
      setItems(l.items); setStats(s);
    } catch { /* */ }
    setLoading(false);
  }, [myInterests, kind, search]);
  useEffect(() => { load(); }, [load]);

  const fmtDate = (iso: string | null) => {
    if (!iso) return '';
    try { return new Date(iso.slice(0, 10) + 'T00:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }); }
    catch { return iso; }
  };
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className="cwatch-tab">
      <header className="cwatch-tab__header">
        <div className="cwatch-tab__title">
          <Icon path={mdiAccountGroup} size={1.1} />
          <div>
            <h2>{t('bubble.cwatch.title', 'Council Watch')}</h2>
            <p>{t('bubble.cwatch.subtitle', 'What the Council of the EU is doing on your policy interests: meetings and outcomes.')}</p>
          </div>
        </div>
      </header>

      <div className="cwatch-subtabs" role="tablist">
        <button role="tab" aria-selected={view === 'activity'} className={view === 'activity' ? 'is-active' : ''} onClick={() => setView('activity')}>
          <Icon path={mdiAccountGroup} size={0.7} /> {t('bubble.cwatch.tabActivity', 'Council activity')}
        </button>
        <button role="tab" aria-selected={view === 'permreps'} className={view === 'permreps' ? 'is-active' : ''} onClick={() => setView('permreps')}>
          <Icon path={mdiMapMarkerOutline} size={0.7} /> {t('bubble.cwatch.permrepsTitle', 'Permanent Representations')}
        </button>
      </div>

      {view === 'activity' && (<>
      <div className="cwatch-tab__controls">
        <div className="cwatch-tab__toggle">
          <button className={myInterests ? 'is-active' : ''} onClick={() => setMyInterests(true)}>{t('bubble.cwatch.mine', 'My interests')}</button>
          <button className={!myInterests ? 'is-active' : ''} onClick={() => setMyInterests(false)}>{t('bubble.cwatch.all', 'All')}</button>
        </div>
        <select className="cwatch-tab__select" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="all">{t('bubble.cwatch.allKinds', 'Meetings & outcomes')}</option>
          <option value="meeting">{t('bubble.cwatch.meetings', 'Meetings')}</option>
          <option value="outcome">{t('bubble.cwatch.outcomes', 'Outcomes')}</option>
        </select>
        <div className="cwatch-tab__search">
          <Icon path={mdiMagnify} size={0.8} />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t('bubble.cwatch.search', 'Search Council activity') as string} />
        </div>
      </div>

      {stats && (
        <div className="cwatch-kpis">
          <div className="cwatch-kpi"><Icon path={mdiCalendarClock} size={0.9} /><div><b>{stats.upcoming_meetings}</b><span>{t('bubble.cwatch.kpiUpcoming', 'upcoming meetings')}</span></div></div>
          <div className="cwatch-kpi"><Icon path={mdiBullhornOutline} size={0.9} /><div><b>{stats.recent_outcomes}</b><span>{t('bubble.cwatch.kpiOutcomes', 'recent outcomes')}</span></div></div>
          <div className="cwatch-kpi"><Icon path={mdiGavel} size={0.9} /><div><b>{stats.council_votes}</b><span>{t('bubble.cwatch.kpiVotes', 'Council votes')}</span></div></div>
          <div className="cwatch-kpi cwatch-kpi--configs">
            <Icon path={mdiDomain} size={0.9} />
            <div><span>{t('bubble.cwatch.yourConfigs', 'Your configurations')}</span>
              <div className="cwatch-configs">{stats.your_configurations.map((c) => <span key={c} className="cwatch-chip">{c}</span>)}
                {stats.your_configurations.length === 0 && <span className="cwatch-muted">-</span>}</div>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="cwatch-tab__empty"><Icon path={mdiLoading} size={1} spin /></div>
      ) : items.length === 0 ? (
        <div className="cwatch-tab__empty">{t('bubble.cwatch.none', 'No Council activity matches your interests yet.')}</div>
      ) : (
        <ul className="cwatch-feed">
          {items.map((it, i) => (
            <li key={i} className={`cwatch-item is-${it.kind} is-clickable`} onClick={() => openDetail(it)}>
              <div className="cwatch-item__rail">
                <Icon path={it.kind === 'meeting' ? mdiCalendarClock : mdiBullhornOutline} size={0.7} />
              </div>
              <div className="cwatch-item__body">
                <div className="cwatch-item__top">
                  <span className={`cwatch-kindchip is-${it.kind}`}>{it.kind === 'meeting' ? t('bubble.cwatch.meeting', 'Meeting') : t('bubble.cwatch.outcome', 'Outcome')}</span>
                  {it.configuration && <span className="cwatch-chip">{it.configuration}</span>}
                  {it.date && (it.kind === 'meeting' && it.date >= today) && <span className="cwatch-soon">{t('bubble.cwatch.upcoming', 'Upcoming')}</span>}
                  <span className="cwatch-item__date">{fmtDate(it.date)}</span>
                </div>
                <div className="cwatch-item__title">{it.title}</div>
                {it.summary && <p className="cwatch-item__summary">{it.summary.slice(0, 220)}</p>}
              </div>
            </li>
          ))}
        </ul>
      )}
      </>)}

      {/* Permanent Representations directory - the member states' working level */}
      {view === 'permreps' && (
        <section className="cwatch-permreps">
          <div className="cwatch-permreps__head">
            <h3><Icon path={mdiMapMarkerOutline} size={0.8} /> {t('bubble.cwatch.permrepsTitle', 'Permanent Representations')}</h3>
            <p>{t('bubble.cwatch.permrepsSub', 'The 27 member states in Brussels - the Council’s working level.')}</p>
            <div className="cwatch-tab__search cwatch-permreps__search">
              <Icon path={mdiMagnify} size={0.8} />
              <input value={prSearch} onChange={(e) => setPrSearch(e.target.value)} placeholder={t('bubble.cwatch.permrepsSearch', 'Find a member state') as string} />
            </div>
          </div>
          <div className="cwatch-pr-grid">
            {permreps
              // Sub-national delegations (e.g. Catalonia) only show in the Catalan UI.
              .filter((p) => !p.region || (i18n.language || '').slice(0, 2) === 'ca')
              .filter((p) => !prSearch || p.name.toLowerCase().includes(prSearch.toLowerCase()) || p.code.toLowerCase().includes(prSearch.toLowerCase()))
              .map((p) => (
                <div key={p.code} className={`cwatch-pr ${p.region ? 'is-region' : ''}`}>
                  <div className="cwatch-pr__top">
                    <span className="cwatch-pr__code">{p.code}</span>
                    <a className="cwatch-pr__name" href={p.home} target="_blank" rel="noopener noreferrer">{p.name} <Icon path={mdiOpenInNew} size={0.5} /></a>
                  </div>
                  <div className="cwatch-pr__links">
                    {p.who && <a href={p.who} target="_blank" rel="noopener noreferrer"><Icon path={mdiAccountMultipleOutline} size={0.55} /> {t('bubble.cwatch.whoIsWho', 'Who’s who')}</a>}
                    {p.news && <a href={p.news} target="_blank" rel="noopener noreferrer"><Icon path={mdiBullhornOutline} size={0.55} /> {t('bubble.cwatch.news', 'News')}</a>}
                  </div>
                </div>
              ))}
          </div>
        </section>
      )}

      {detail && createPortal(
        <div className="cwatch-modal" role="dialog" aria-modal="true" onClick={() => setDetail(null)}>
          <div className="cwatch-modal__panel" onClick={(e) => e.stopPropagation()}>
            <header className="cwatch-modal__head">
              <div>
                <div className="cwatch-modal__tags">
                  <span className={`cwatch-kindchip is-${detail.kind}`}>{detail.kind === 'meeting' ? t('bubble.cwatch.meeting', 'Meeting') : t('bubble.cwatch.outcome', 'Outcome')}</span>
                  {detail.configuration && <span className="cwatch-chip">{detail.configuration}</span>}
                  <span className="cwatch-modal__date">{fmtDate(detail.date)}</span>
                </div>
                <h3>{detail.title}</h3>
              </div>
              <button className="cwatch-modal__close" onClick={() => setDetail(null)}><Icon path={mdiClose} size={0.9} /></button>
            </header>
            <div className="cwatch-modal__body">
              {detail.summary && <p className="cwatch-modal__text">{detail.summary}</p>}

              {summary ? (
                <div className="cwatch-ai"><Icon path={mdiCreation} size={0.7} /> <span>{summary}</span></div>
              ) : (
                <button className="cwatch-ai-btn" onClick={onSummarise} disabled={summarising}>
                  <Icon path={summarising ? mdiLoading : mdiCreation} size={0.7} spin={summarising} />
                  {summarising ? t('bubble.cwatch.summarising', 'Analysing…') : t('bubble.cwatch.whatThisMeans', 'What this means')}
                </button>
              )}

              {detail.url && (
                <a className="cwatch-source" href={detail.url} target="_blank" rel="noopener noreferrer">
                  <Icon path={mdiOpenInNew} size={0.6} /> {t('bubble.cwatch.viewSource', 'Open on consilium.europa.eu')}
                </a>
              )}
            </div>
          </div>
        </div>,
        document.body,
      )}
    </div>
  );
}

export default CouncilWatchTab;
