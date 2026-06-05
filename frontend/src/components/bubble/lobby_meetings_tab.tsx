/**
 * Lobby Meetings tab (MEUB Section 3 - Institutional Monitoring).
 *
 * Four views through the PI lens:
 *   - Commission: the Transparency Register meetings (who lobbied the Commission).
 *   - Parliament: MEP rapporteur/shadow meetings (OEIL Transparency + MEP profiles).
 *   - Comparison: who lobbied BOTH branches vs one only (the cross-branch footprint).
 *   - Footprint (Tier 0): factual engagement signals - access depth, competitive
 *     balance, declared spend. NO success/causation verdicts (those belong in
 *     Section 4 Analysis & Strategy, on a positions layer).
 *
 * Organisations are hyperlinked to their own website + Transparency Register profile.
 * Data: /api/lobby-meetings.
 */
import { useEffect, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiHandshakeOutline, mdiMagnify, mdiClose, mdiLoading, mdiOfficeBuildingOutline,
  mdiDomain, mdiCalendarClock, mdiOpenInNew, mdiAccountTieOutline, mdiChartTimelineVariant,
  mdiAccountVoice, mdiCompareHorizontal, mdiFileDocumentOutline, mdiEarth, mdiCardAccountDetailsOutline,
  mdiChartBoxOutline, mdiCashMultiple, mdiScaleBalance, mdiTrophyOutline, mdiAccountTie, mdiMapMarkerOutline,
} from '@mdi/js';
import { lobbyMeetingsService } from '../../services/lobby_meetings_service';
import type {
  LobbyMeeting, LobbyStats, MepMeeting, ParliamentResult, ComparisonResult,
  FootprintResult, OrgFootprint,
} from '../../services/lobby_meetings_service';
import './lobby_meetings_tab.css';

type View = 'commission' | 'parliament' | 'comparison' | 'footprint';

const fmtDate = (iso: string | null) => {
  if (!iso) return '';
  try { return new Date(iso.slice(0, 10) + 'T00:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }); }
  catch { return iso; }
};

// Declared lobbying spend is a band (costs_min..costs_max). Render as "EUR 6.0M-6.5M".
const fmtSpend = (min: number | null, max: number | null) => {
  if (min == null && max == null) return null;
  const m = (n: number | null) => {
    if (n == null) return '';
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${Math.round(n / 1_000)}k`;
    return String(n);
  };
  return min != null && max != null ? `EUR ${m(min)}-${m(max)}` : `EUR ${m(min ?? max)}`;
};

// A safe org name: hyperlinked to the org's website when we have a valid one.
function OrgName({ name, website }: { name: string; website?: string | null }) {
  if (website) {
    return (
      <a className="lobby-orglink" href={website} target="_blank" rel="noopener noreferrer">
        {name} <Icon path={mdiOpenInNew} size={0.5} />
      </a>
    );
  }
  return <span>{name}</span>;
}

export function LobbyMeetingsTab() {
  const { t } = useTranslation();
  const [view, setView] = useState<View>('commission');
  const [myInterests, setMyInterests] = useState(true);
  const [search, setSearch] = useState('');

  // Commission state
  const [dg, setDg] = useState('');
  const [items, setItems] = useState<LobbyMeeting[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<LobbyStats | null>(null);
  const [detail, setDetail] = useState<LobbyMeeting | null>(null);

  // Parliament state
  const [pres, setPres] = useState<ParliamentResult | null>(null);
  const [mdetail, setMdetail] = useState<MepMeeting | null>(null);

  // Comparison + Footprint state
  const [cmp, setCmp] = useState<ComparisonResult | null>(null);
  const [foot, setFoot] = useState<FootprintResult | null>(null);

  // Per-organisation footprint drill-down (opened from any org)
  const [org, setOrg] = useState<OrgFootprint | null>(null);
  const [orgLoading, setOrgLoading] = useState(false);

  const [loading, setLoading] = useState(true);
  const params = { myInterests, dg: dg || undefined, search: search || undefined };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (view === 'commission') {
        const [list, st] = await Promise.all([
          lobbyMeetingsService.list(params),
          lobbyMeetingsService.stats(params),
        ]);
        setItems(list.items); setTotal(list.total); setStats(st);
      } else if (view === 'parliament') {
        setPres(await lobbyMeetingsService.parliament({ myInterests, search: search || undefined }));
      } else if (view === 'comparison') {
        setCmp(await lobbyMeetingsService.comparison(myInterests));
      } else {
        setFoot(await lobbyMeetingsService.footprint(myInterests));
      }
    } catch { /* tier / network */ }
    setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, myInterests, dg, search]);

  useEffect(() => { load(); }, [load]);

  // Open one organisation's cross-branch footprint.
  const openOrg = async (name: string, trId?: string | null) => {
    setOrg(null); setOrgLoading(true);
    try { setOrg(await lobbyMeetingsService.orgFootprint(name, trId)); }
    catch { setOrgLoading(false); return; }
    setOrgLoading(false);
  };

  // Deep-link from Position Analysis: ?org=<name>&org_tr=<id> auto-opens the footprint.
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    const orgParam = searchParams.get('org');
    if (orgParam) {
      openOrg(orgParam, searchParams.get('org_tr'));
      setSearchParams((prev) => {
        const n = new URLSearchParams(prev); n.delete('org'); n.delete('org_tr'); return n;
      }, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const dgOptions = stats?.top_dgs || [];
  const maxOrg = Math.max(1, ...(stats?.top_organisations || []).map((o) => o.count));
  const maxDg = Math.max(1, ...(stats?.top_dgs || []).map((d) => d.count));
  const maxMonth = Math.max(1, ...(stats?.monthly || []).map((m) => m.count));
  const maxPOrg = Math.max(1, ...(pres?.top_organisations || []).map((o) => o.count));
  const catMixKnown = (foot?.category_mix || []).filter((c) => c.type !== 'Unknown');
  const maxCat = Math.max(1, ...catMixKnown.map((c) => c.count));
  const unknownCat = (foot?.category_mix || []).find((c) => c.type === 'Unknown');
  const maxAccess = Math.max(1, ...(foot?.access_depth || []).map((a) => a.direct + a.staff));

  return (
    <div className="lobby-tab">
      <header className="lobby-tab__header">
        <div className="lobby-tab__title">
          <Icon path={mdiHandshakeOutline} size={1.1} />
          <div>
            <h2>{t('bubble.lobby.title', 'Lobby Meetings')}</h2>
            <p>{t('bubble.lobby.subtitle', 'Who is lobbying the EU institutions on your policy interests, and whom they met.')}</p>
          </div>
        </div>
      </header>

      {/* Sub-tabs */}
      <div className="lobby-subtabs" role="tablist">
        <button role="tab" aria-selected={view === 'commission'} className={view === 'commission' ? 'is-active' : ''} onClick={() => setView('commission')}>
          <Icon path={mdiDomain} size={0.7} /> {t('bubble.lobby.tabCommission', 'Commission')}
        </button>
        <button role="tab" aria-selected={view === 'parliament'} className={view === 'parliament' ? 'is-active' : ''} onClick={() => setView('parliament')}>
          <Icon path={mdiAccountVoice} size={0.7} /> {t('bubble.lobby.tabParliament', 'Parliament')}
        </button>
        <button role="tab" aria-selected={view === 'comparison'} className={view === 'comparison' ? 'is-active' : ''} onClick={() => setView('comparison')}>
          <Icon path={mdiCompareHorizontal} size={0.7} /> {t('bubble.lobby.tabComparison', 'Comparison')}
        </button>
        <button role="tab" aria-selected={view === 'footprint'} className={view === 'footprint' ? 'is-active' : ''} onClick={() => setView('footprint')}>
          <Icon path={mdiChartBoxOutline} size={0.7} /> {t('bubble.lobby.tabFootprint', 'Footprint')}
        </button>
      </div>

      {/* Shared controls */}
      <div className="lobby-tab__controls">
        <div className="lobby-tab__toggle">
          <button className={myInterests ? 'is-active' : ''} onClick={() => setMyInterests(true)}>{t('bubble.lobby.mine', 'My interests')}</button>
          <button className={!myInterests ? 'is-active' : ''} onClick={() => setMyInterests(false)}>{t('bubble.lobby.all', 'All')}</button>
        </div>
        {view === 'commission' && (
          <select className="lobby-tab__select" value={dg} onChange={(e) => setDg(e.target.value)}>
            <option value="">{t('bubble.lobby.allDgs', 'All departments')}</option>
            {dgOptions.map((d) => (
              <option key={d.dg} value={d.dg}>{d.dg}{d.dg_name ? ` - ${d.dg_name}` : ''}</option>
            ))}
          </select>
        )}
        {view !== 'comparison' && (
          <div className="lobby-tab__search">
            <Icon path={mdiMagnify} size={0.8} />
            <input value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder={t('bubble.lobby.search', 'Search organisation or subject') as string} />
          </div>
        )}
      </div>

      {/* ===== COMMISSION ===== */}
      {view === 'commission' && (<>
        {stats && (
          <>
            <div className="lobby-kpis">
              <div className="lobby-kpi"><Icon path={mdiHandshakeOutline} size={0.9} /><div><b>{stats.total.toLocaleString()}</b><span>{t('bubble.lobby.kpiMeetings', 'meetings')}</span></div></div>
              <div className="lobby-kpi"><Icon path={mdiOfficeBuildingOutline} size={0.9} /><div><b>{stats.distinct_organisations.toLocaleString()}</b><span>{t('bubble.lobby.kpiOrgs', 'organisations')}</span></div></div>
              <div className="lobby-kpi"><Icon path={mdiDomain} size={0.9} /><div><b>{stats.distinct_dgs}</b><span>{t('bubble.lobby.kpiDgs', 'departments')}</span></div></div>
              <div className="lobby-kpi"><Icon path={mdiCalendarClock} size={0.9} /><div><b>{stats.recent_90d.toLocaleString()}</b><span>{t('bubble.lobby.kpiRecent', 'last 90 days')}</span></div></div>
            </div>

            <div className="lobby-modules">
              <section className="lobby-module">
                <h4><Icon path={mdiOfficeBuildingOutline} size={0.7} /> {t('bubble.lobby.topOrgs', 'Top organisations')}</h4>
                <ul className="lobby-bars">
                  {stats.top_organisations.map((o) => (
                    <li key={o.organisation} title={o.organisation}>
                      <span className="lobby-bars__label">{o.organisation}</span>
                      <span className="lobby-bars__track"><span className="lobby-bars__fill" style={{ width: `${(o.count / maxOrg) * 100}%` }} /></span>
                      <span className="lobby-bars__val">{o.count}</span>
                    </li>
                  ))}
                  {stats.top_organisations.length === 0 && <li className="lobby-bars__empty">{t('bubble.lobby.noData', 'No data')}</li>}
                </ul>
              </section>

              <section className="lobby-module">
                <h4><Icon path={mdiDomain} size={0.7} /> {t('bubble.lobby.topDgs', 'Most-lobbied departments')}</h4>
                <ul className="lobby-bars">
                  {stats.top_dgs.map((d) => (
                    <li key={d.dg} title={d.dg_name || d.dg}>
                      <span className="lobby-bars__label">{d.dg}{d.dg_name ? ` · ${d.dg_name}` : ''}</span>
                      <span className="lobby-bars__track"><span className="lobby-bars__fill is-dg" style={{ width: `${(d.count / maxDg) * 100}%` }} /></span>
                      <span className="lobby-bars__val">{d.count}</span>
                    </li>
                  ))}
                </ul>
              </section>

              <section className="lobby-module lobby-module--wide">
                <h4><Icon path={mdiChartTimelineVariant} size={0.7} /> {t('bubble.lobby.activity', 'Activity over time')}</h4>
                <div className="lobby-spark">
                  {stats.monthly.map((m) => (
                    <div className="lobby-spark__col" key={m.month} title={`${m.month}: ${m.count}`}>
                      <span className="lobby-spark__bar" style={{ height: `${Math.max(6, (m.count / maxMonth) * 100)}%` }} />
                      <span className="lobby-spark__lbl">{m.month.slice(2)}</span>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          </>
        )}

        {loading ? (
          <div className="lobby-tab__empty"><Icon path={mdiLoading} size={1} spin /></div>
        ) : items.length === 0 ? (
          <div className="lobby-tab__empty">{t('bubble.lobby.none', 'No lobby meetings match your interests yet.')}</div>
        ) : (
          <>
            <p className="lobby-tab__count">{total.toLocaleString()} {t('bubble.lobby.results', 'meetings')}</p>
            <div className="lobby-grid">
              {items.map((m) => (
                <div key={m.id} className="lobby-card lobby-card--click" onClick={() => setDetail(m)}>
                  <div className="lobby-card__top">
                    {m.host_dg && <span className="lobby-chip">{m.host_dg}</span>}
                    <span className="lobby-card__date">{fmtDate(m.meeting_date)}</span>
                  </div>
                  <div className="lobby-card__org" onClick={(e) => e.stopPropagation()}>
                    <Icon path={mdiOfficeBuildingOutline} size={0.65} /> <OrgName name={m.organisation_met} website={m.org_website} />
                  </div>
                  <div className="lobby-card__subject">{m.subject}</div>
                  <div className="lobby-card__host">
                    <Icon path={mdiAccountTieOutline} size={0.6} />
                    {m.host_name || m.host_dg_name}{m.host_role ? ` · ${m.host_role}` : ''}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </>)}

      {/* ===== PARLIAMENT ===== */}
      {view === 'parliament' && (<>
        {pres && (
          <div className="lobby-kpis">
            <div className="lobby-kpi"><Icon path={mdiAccountVoice} size={0.9} /><div><b>{pres.total.toLocaleString()}</b><span>{t('bubble.lobby.kpiMepMeetings', 'MEP meetings')}</span></div></div>
            <div className="lobby-kpi"><Icon path={mdiCardAccountDetailsOutline} size={0.9} /><div><b>{pres.distinct_meps}</b><span>{t('bubble.lobby.kpiMeps', 'MEPs')}</span></div></div>
            <div className="lobby-kpi"><Icon path={mdiOfficeBuildingOutline} size={0.9} /><div><b>{pres.distinct_organisations.toLocaleString()}</b><span>{t('bubble.lobby.kpiOrgs', 'organisations')}</span></div></div>
          </div>
        )}
        {pres && pres.top_organisations.length > 0 && (
          <div className="lobby-modules">
            <section className="lobby-module lobby-module--wide">
              <h4><Icon path={mdiOfficeBuildingOutline} size={0.7} /> {t('bubble.lobby.topOrgsEp', 'Organisations meeting MEPs most')}</h4>
              <ul className="lobby-bars">
                {pres.top_organisations.map((o) => (
                  <li key={o.organisation} title={o.organisation}>
                    <span className="lobby-bars__label">{o.organisation}</span>
                    <span className="lobby-bars__track"><span className="lobby-bars__fill is-ep" style={{ width: `${(o.count / maxPOrg) * 100}%` }} /></span>
                    <span className="lobby-bars__val">{o.count}</span>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        )}

        {loading ? (
          <div className="lobby-tab__empty"><Icon path={mdiLoading} size={1} spin /></div>
        ) : !pres || pres.items.length === 0 ? (
          <div className="lobby-tab__empty">{t('bubble.lobby.noneEp', 'No MEP meetings match your interests yet.')}</div>
        ) : (
          <>
            <p className="lobby-tab__count">{pres.total.toLocaleString()} {t('bubble.lobby.results', 'meetings')}</p>
            <div className="lobby-grid">
              {pres.items.map((m) => (
                <div key={m.id} className="lobby-card lobby-card--click" onClick={() => setMdetail(m)}>
                  <div className="lobby-card__top">
                    {m.committee && <span className="lobby-chip is-ep">{m.committee}</span>}
                    {m.role && <span className="lobby-chip is-muted">{m.role}</span>}
                    <span className="lobby-card__date">{fmtDate(m.meeting_date)}</span>
                  </div>
                  <div className="lobby-card__org" onClick={(e) => e.stopPropagation()}>
                    <Icon path={mdiOfficeBuildingOutline} size={0.65} /> <OrgName name={m.organisation} website={m.org_website} />
                  </div>
                  <div className="lobby-card__host">
                    <Icon path={mdiAccountVoice} size={0.6} /> {m.mep_name || '-'}
                  </div>
                  {m.procedure_ref && (
                    <div className="lobby-card__proc" onClick={(e) => e.stopPropagation()}>
                      <a href={m.procedure_url || undefined} target="_blank" rel="noopener noreferrer">
                        <Icon path={mdiFileDocumentOutline} size={0.55} /> {m.procedure_ref}
                      </a>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </>)}

      {/* ===== COMPARISON ===== */}
      {view === 'comparison' && (<>
        {loading ? (
          <div className="lobby-tab__empty"><Icon path={mdiLoading} size={1} spin /></div>
        ) : !cmp ? (
          <div className="lobby-tab__empty">{t('bubble.lobby.noCmp', 'Not enough data to compare yet.')}</div>
        ) : (
          <>
            <div className="lobby-venn">
              <div className="lobby-venn__cell is-comm">
                <span className="lobby-venn__n">{cmp.counts.commission_only}</span>
                <span className="lobby-venn__l"><Icon path={mdiDomain} size={0.6} /> {t('bubble.lobby.commissionOnly', 'Commission only')}</span>
              </div>
              <div className="lobby-venn__cell is-both">
                <span className="lobby-venn__n">{cmp.counts.both}</span>
                <span className="lobby-venn__l"><Icon path={mdiCompareHorizontal} size={0.6} /> {t('bubble.lobby.bothBranches', 'Both branches')}</span>
              </div>
              <div className="lobby-venn__cell is-ep">
                <span className="lobby-venn__n">{cmp.counts.parliament_only}</span>
                <span className="lobby-venn__l"><Icon path={mdiAccountVoice} size={0.6} /> {t('bubble.lobby.parliamentOnly', 'Parliament only')}</span>
              </div>
            </div>
            <p className="lobby-cmp__note">{t('bubble.lobby.cmpNote', 'Engagement footprint only - matched on organisation name. No success or causation is implied.')}</p>

            <div className="lobby-modules">
              <section className="lobby-module lobby-module--wide">
                <h4><Icon path={mdiCompareHorizontal} size={0.7} /> {t('bubble.lobby.bothTable', 'Organisations that lobbied both branches')}</h4>
                {cmp.both.length === 0 ? (
                  <p className="lobby-bars__empty">{t('bubble.lobby.noData', 'No data')}</p>
                ) : (
                  <table className="lobby-cmp-table">
                    <thead><tr><th>{t('bubble.lobby.organisation', 'Organisation')}</th><th>{t('bubble.lobby.tabCommission', 'Commission')}</th><th>{t('bubble.lobby.tabParliament', 'Parliament')}</th><th>{t('bubble.lobby.totalCol', 'Total')}</th></tr></thead>
                    <tbody>
                      {cmp.both.map((r) => (
                        <tr key={r.organisation}>
                          <td>{r.organisation}</td>
                          <td className="lobby-cmp-table__num">{r.commission}</td>
                          <td className="lobby-cmp-table__num">{r.parliament}</td>
                          <td className="lobby-cmp-table__num lobby-cmp-table__tot">{r.total}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </section>
            </div>
          </>
        )}
      </>)}

      {/* ===== FOOTPRINT (Tier 0: factual signals, no verdicts) ===== */}
      {view === 'footprint' && (<>
        {loading ? (
          <div className="lobby-tab__empty"><Icon path={mdiLoading} size={1} spin /></div>
        ) : !foot ? (
          <div className="lobby-tab__empty">{t('bubble.lobby.noFoot', 'Not enough data for a footprint yet.')}</div>
        ) : (
          <>
            <p className="lobby-cmp__note">{t('bubble.lobby.footNote', 'Factual engagement signals only - access reached, who is active, declared spend. Whether lobbying succeeded is not assessed here.')}</p>
            <div className="lobby-modules">
              {/* Competitive balance */}
              <section className="lobby-module">
                <h4><Icon path={mdiScaleBalance} size={0.7} /> {t('bubble.lobby.balance', 'Competitive balance')}</h4>
                <ul className="lobby-bars">
                  {catMixKnown.map((c) => (
                    <li key={c.type} title={c.type}>
                      <span className="lobby-bars__label">{c.type}</span>
                      <span className="lobby-bars__track"><span className="lobby-bars__fill" style={{ width: `${(c.count / maxCat) * 100}%` }} /></span>
                      <span className="lobby-bars__val">{c.count}</span>
                    </li>
                  ))}
                  {catMixKnown.length === 0 && <li className="lobby-bars__empty">{t('bubble.lobby.noData', 'No data')}</li>}
                </ul>
                {unknownCat && <p className="lobby-foot__hint">{unknownCat.count} {t('bubble.lobby.notMatched', 'organisations not matched to the register')}</p>}
              </section>

              {/* EP access depth */}
              <section className="lobby-module">
                <h4><Icon path={mdiAccountTie} size={0.7} /> {t('bubble.lobby.accessDepth', 'Parliament access depth')}</h4>
                <ul className="lobby-access">
                  {foot.access_depth.map((a) => (
                    <li key={a.level}>
                      <span className="lobby-access__label">{a.label}</span>
                      <span className="lobby-access__bar">
                        <span className="lobby-access__direct" style={{ width: `${(a.direct / maxAccess) * 100}%` }} title={`${a.direct} ${t('bubble.lobby.directMeetings', 'direct')}`} />
                        <span className="lobby-access__staff" style={{ width: `${(a.staff / maxAccess) * 100}%` }} title={`${a.staff} ${t('bubble.lobby.staffMeetings', 'staff-level')}`} />
                      </span>
                      <span className="lobby-bars__val">{a.direct + a.staff}</span>
                    </li>
                  ))}
                </ul>
                <p className="lobby-foot__legend">
                  <span className="lobby-dot is-direct" /> {t('bubble.lobby.directMeetings', 'direct')}
                  <span className="lobby-dot is-staff" /> {t('bubble.lobby.staffMeetings', 'staff-level')}
                </p>
              </section>

              {/* Declared spend leaders */}
              <section className="lobby-module lobby-module--wide">
                <h4><Icon path={mdiCashMultiple} size={0.7} /> {t('bubble.lobby.spendLeaders', 'Declared lobbying spend (largest on your topics)')}</h4>
                {foot.spend_leaders.length === 0 ? (
                  <p className="lobby-bars__empty">{t('bubble.lobby.noSpend', 'No declared spend on this set.')}</p>
                ) : (
                  <table className="lobby-cmp-table">
                    <thead><tr><th>{t('bubble.lobby.organisation', 'Organisation')}</th><th>{t('bubble.lobby.spend', 'Declared spend')}</th><th>FTE</th><th>{t('bubble.lobby.tabCommission', 'Commission')}</th><th>{t('bubble.lobby.tabParliament', 'Parliament')}</th></tr></thead>
                    <tbody>
                      {foot.spend_leaders.map((s) => (
                        <tr key={s.organisation} className="lobby-row--click" onClick={() => openOrg(s.organisation, s.tr_id)}>
                          <td>{s.organisation}</td>
                          <td className="lobby-cmp-table__num">{fmtSpend(s.costs_min, s.costs_max) || '-'}</td>
                          <td className="lobby-cmp-table__num">{s.fte != null ? Math.round(s.fte) : '-'}</td>
                          <td className="lobby-cmp-table__num">{s.commission}</td>
                          <td className="lobby-cmp-table__num">{s.parliament}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </section>

              {/* Deepest access: reached a rapporteur directly */}
              <section className="lobby-module lobby-module--wide">
                <h4><Icon path={mdiTrophyOutline} size={0.7} /> {t('bubble.lobby.deepest', 'Reached a rapporteur directly')}</h4>
                {foot.deepest_access.length === 0 ? (
                  <p className="lobby-bars__empty">{t('bubble.lobby.noData', 'No data')}</p>
                ) : (
                  <div className="lobby-chips">
                    {foot.deepest_access.map((d) => (
                      <button key={d.organisation} className="lobby-orgchip" onClick={() => openOrg(d.organisation, d.tr_id)}>
                        {d.organisation} <span className="lobby-orgchip__n">{d.parliament + d.commission}</span>
                      </button>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </>
        )}
      </>)}

      {/* Commission detail modal */}
      {detail && createPortal(
        <div className="lobby-modal" role="dialog" aria-modal="true" onClick={() => setDetail(null)}>
          <div className="lobby-modal__panel" onClick={(e) => e.stopPropagation()}>
            <header className="lobby-modal__head">
              <div>
                <div className="lobby-modal__tags">
                  {detail.host_dg && <span className="lobby-chip">{detail.host_dg}{detail.host_dg_name ? ` · ${detail.host_dg_name}` : ''}</span>}
                  <span className="lobby-chip is-muted">{fmtDate(detail.meeting_date)}</span>
                </div>
                <h3><Icon path={mdiOfficeBuildingOutline} size={0.85} /> <OrgName name={detail.organisation_met} website={detail.org_website} /></h3>
              </div>
              <button className="lobby-modal__close" onClick={() => setDetail(null)}><Icon path={mdiClose} size={0.9} /></button>
            </header>
            <div className="lobby-modal__body">
              <h5>{t('bubble.lobby.subjectLabel', 'Subject')}</h5>
              <p>{detail.subject}</p>
              <div className="lobby-modal__grid">
                <div><span>{t('bubble.lobby.host', 'Commission host')}</span><b>{detail.host_name || '-'}{detail.host_role ? ` (${detail.host_role})` : ''}</b></div>
                {detail.host_cabinet && <div><span>{t('bubble.lobby.cabinet', 'Cabinet / source')}</span><b>{detail.host_cabinet}</b></div>}
                {detail.representatives && <div><span>{t('bubble.lobby.reps', 'Representatives')}</span><b>{detail.representatives}</b></div>}
                {detail.location && <div><span>{t('bubble.lobby.location', 'Location')}</span><b>{detail.location}</b></div>}
                {detail.org_category && <div><span>{t('bubble.lobby.category', 'Register category')}</span><b>{detail.org_category}</b></div>}
                {detail.org_country && <div><span>{t('bubble.lobby.country', 'Head office')}</span><b>{detail.org_country}</b></div>}
                {detail.org_ep_passes != null && <div><span>{t('bubble.lobby.epPasses', 'EP access passes')}</span><b>{detail.org_ep_passes}</b></div>}
              </div>
              <div className="lobby-modal__links">
                <button className="lobby-link" onClick={() => { openOrg(detail.organisation_met, detail.transparency_register_id); setDetail(null); }}>
                  <Icon path={mdiChartBoxOutline} size={0.6} /> {t('bubble.lobby.viewFootprint', 'View organisation footprint')}
                </button>
                {detail.org_website && (
                  <a className="lobby-link is-muted" href={detail.org_website} target="_blank" rel="noopener noreferrer">
                    <Icon path={mdiEarth} size={0.6} /> {t('bubble.lobby.orgWebsite', 'Organisation website')}
                  </a>
                )}
                {(detail.org_register_url || detail.transparency_register_url) && (
                  <a className="lobby-link is-muted" href={(detail.org_register_url || detail.transparency_register_url) as string} target="_blank" rel="noopener noreferrer">
                    <Icon path={mdiCardAccountDetailsOutline} size={0.6} /> {t('bubble.lobby.registerProfile', 'Transparency Register profile')}
                  </a>
                )}
                {detail.source_url && (
                  <a className="lobby-link is-muted" href={detail.source_url} target="_blank" rel="noopener noreferrer">
                    <Icon path={mdiOpenInNew} size={0.6} /> {t('bubble.lobby.source', 'Official source')}
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>,
        document.body,
      )}

      {/* MEP meeting detail modal */}
      {mdetail && createPortal(
        <div className="lobby-modal" role="dialog" aria-modal="true" onClick={() => setMdetail(null)}>
          <div className="lobby-modal__panel" onClick={(e) => e.stopPropagation()}>
            <header className="lobby-modal__head">
              <div>
                <div className="lobby-modal__tags">
                  {mdetail.committee && <span className="lobby-chip is-ep">{mdetail.committee}</span>}
                  {mdetail.role && <span className="lobby-chip is-muted">{mdetail.role}</span>}
                  <span className="lobby-chip is-muted">{fmtDate(mdetail.meeting_date)}</span>
                </div>
                <h3><Icon path={mdiOfficeBuildingOutline} size={0.85} /> <OrgName name={mdetail.organisation} website={mdetail.org_website} /></h3>
              </div>
              <button className="lobby-modal__close" onClick={() => setMdetail(null)}><Icon path={mdiClose} size={0.9} /></button>
            </header>
            <div className="lobby-modal__body">
              <div className="lobby-modal__grid">
                <div><span>{t('bubble.lobby.mep', 'MEP')}</span><b>{mdetail.mep_name || '-'}</b></div>
                {mdetail.role && <div><span>{t('bubble.lobby.capacity', 'Capacity')}</span><b>{mdetail.role}</b></div>}
                {mdetail.committee && <div><span>{t('bubble.lobby.committee', 'Committee')}</span><b>{mdetail.committee}</b></div>}
                {mdetail.procedure_ref && <div><span>{t('bubble.lobby.dossier', 'Dossier')}</span><b>{mdetail.procedure_ref}</b></div>}
                <div><span>{t('bubble.lobby.sourceLabel', 'Source')}</span><b>{mdetail.source === 'both' ? 'OEIL + profile' : mdetail.source}</b></div>
              </div>
              <div className="lobby-modal__links">
                <button className="lobby-link" onClick={() => { openOrg(mdetail.organisation, mdetail.transparency_register_id); setMdetail(null); }}>
                  <Icon path={mdiChartBoxOutline} size={0.6} /> {t('bubble.lobby.viewFootprint', 'View organisation footprint')}
                </button>
                {mdetail.org_website && (
                  <a className="lobby-link is-muted" href={mdetail.org_website} target="_blank" rel="noopener noreferrer">
                    <Icon path={mdiEarth} size={0.6} /> {t('bubble.lobby.orgWebsite', 'Organisation website')}
                  </a>
                )}
                {mdetail.org_register_url && (
                  <a className="lobby-link is-muted" href={mdetail.org_register_url} target="_blank" rel="noopener noreferrer">
                    <Icon path={mdiCardAccountDetailsOutline} size={0.6} /> {t('bubble.lobby.registerProfile', 'Transparency Register profile')}
                  </a>
                )}
                {mdetail.procedure_url && (
                  <a className="lobby-link is-muted" href={mdetail.procedure_url} target="_blank" rel="noopener noreferrer">
                    <Icon path={mdiFileDocumentOutline} size={0.6} /> {t('bubble.lobby.procedureFile', 'Procedure file (OEIL)')}
                  </a>
                )}
                {mdetail.source_url && (
                  <a className="lobby-link is-muted" href={mdetail.source_url} target="_blank" rel="noopener noreferrer">
                    <Icon path={mdiOpenInNew} size={0.6} /> {t('bubble.lobby.source', 'Official source')}
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>,
        document.body,
      )}

      {/* Per-organisation footprint (cross-branch drill-down) */}
      {(org || orgLoading) && createPortal(
        <div className="lobby-modal" role="dialog" aria-modal="true" onClick={() => { setOrg(null); setOrgLoading(false); }}>
          <div className="lobby-modal__panel lobby-modal__panel--wide" onClick={(e) => e.stopPropagation()}>
            {orgLoading || !org ? (
              <div className="lobby-tab__empty"><Icon path={mdiLoading} size={1} spin /></div>
            ) : (() => {
              const maxOM = Math.max(1, ...org.timeline.map((m) => m.count));
              return (<>
                <header className="lobby-modal__head">
                  <div>
                    <div className="lobby-modal__tags">
                      {org.identity.balance_type && org.identity.balance_type !== 'Unknown' && <span className="lobby-chip">{org.identity.balance_type}</span>}
                      {org.identity.country && <span className="lobby-chip is-muted"><Icon path={mdiMapMarkerOutline} size={0.5} /> {org.identity.country}</span>}
                      {org.reached_rapporteur && <span className="lobby-chip is-ep">{t('bubble.lobby.reachedRapporteur', 'Reached rapporteur')}</span>}
                    </div>
                    <h3><Icon path={mdiOfficeBuildingOutline} size={0.85} /> <OrgName name={org.organisation} website={org.identity.website} /></h3>
                  </div>
                  <button className="lobby-modal__close" onClick={() => { setOrg(null); setOrgLoading(false); }}><Icon path={mdiClose} size={0.9} /></button>
                </header>
                <div className="lobby-modal__body">
                  <div className="lobby-kpis lobby-kpis--org">
                    <div className="lobby-kpi"><Icon path={mdiDomain} size={0.9} /><div><b>{org.commission_count}</b><span>{t('bubble.lobby.commissionMeetings', 'Commission meetings')}</span></div></div>
                    <div className="lobby-kpi"><Icon path={mdiAccountVoice} size={0.9} /><div><b>{org.parliament_count}</b><span>{t('bubble.lobby.epMeetings', 'Parliament meetings')}</span></div></div>
                    {org.best_access_label && <div className="lobby-kpi"><Icon path={mdiAccountTie} size={0.9} /><div><b style={{ fontSize: '0.95rem' }}>{org.best_access_label}</b><span>{t('bubble.lobby.deepestAccess', 'deepest access')}</span></div></div>}
                  </div>

                  <div className="lobby-modal__grid">
                    {org.identity.category && <div><span>{t('bubble.lobby.category', 'Register category')}</span><b>{org.identity.category}</b></div>}
                    {org.identity.fte != null && <div><span>FTE</span><b>{Math.round(org.identity.fte)}</b></div>}
                    {fmtSpend(org.identity.costs_min, org.identity.costs_max) && <div><span>{t('bubble.lobby.spend', 'Declared spend')}</span><b>{fmtSpend(org.identity.costs_min, org.identity.costs_max)}</b></div>}
                  </div>

                  {org.timeline.length > 0 && (
                    <>
                      <h5><Icon path={mdiChartTimelineVariant} size={0.6} /> {t('bubble.lobby.activity', 'Activity over time')}</h5>
                      <div className="lobby-spark">
                        {org.timeline.map((m) => (
                          <div className="lobby-spark__col" key={m.month} title={`${m.month}: ${m.count}`}>
                            <span className="lobby-spark__bar" style={{ height: `${Math.max(6, (m.count / maxOM) * 100)}%` }} />
                            <span className="lobby-spark__lbl">{m.month.slice(2)}</span>
                          </div>
                        ))}
                      </div>
                    </>
                  )}

                  {org.dgs_met.length > 0 && (<>
                    <h5>{t('bubble.lobby.dgsMet', 'Commission departments met')}</h5>
                    <div className="lobby-chips">{org.dgs_met.map((d) => <span key={d.code} className="lobby-chip" title={d.name || d.code}>{d.code}</span>)}</div>
                  </>)}

                  {org.meps_met.length > 0 && (<>
                    <h5>{t('bubble.lobby.mepsMet', 'MEPs met')}</h5>
                    <div className="lobby-chips">{org.meps_met.map((m) => <span key={m.name} className="lobby-chip is-muted">{m.name}{m.role ? ` · ${m.role}` : ''}</span>)}</div>
                  </>)}

                  {org.dossiers.length > 0 && (<>
                    <h5>{t('bubble.lobby.dossiersEngaged', 'Dossiers engaged')}</h5>
                    <div className="lobby-chips">{org.dossiers.map((d) => (
                      <a key={d} className="lobby-orgchip" href={`https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${d}`} target="_blank" rel="noopener noreferrer">{d}</a>
                    ))}</div>
                  </>)}
                </div>
              </>);
            })()}
          </div>
        </div>,
        document.body,
      )}
    </div>
  );
}

export default LobbyMeetingsTab;
