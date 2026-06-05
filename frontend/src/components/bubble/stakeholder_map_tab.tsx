/**
 * Stakeholder Mapping tab (MEUB Section 4 - Strategy).
 *
 * A PI-aware actor graph: PI-overview (default) or file-centric. Two renderers,
 * lazy-loaded and switchable: "Web" (react-force-graph) and "Map" (React Flow).
 * Click any node for a detail drawer. Colours: EP red, Commission blue, Council
 * purple, file navy, stakeholders amber (or green/red by Outcome-Alignment stance).
 * No Anthropic. 1040px cap, 6 languages, no em-dashes.
 */
import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiGraphOutline, mdiVectorTriangle, mdiSitemapOutline, mdiOpenInNew, mdiClose,
  mdiInformationOutline, mdiViewGridOutline, mdiEmailOutline, mdiChevronDown, mdiMagnify,
} from '@mdi/js';
import { stakeholdersService } from '../../services/stakeholders_service';
import type { SMGraph, SMNode, SMFile, SMContactsResult, SMDgContacts } from '../../services/stakeholders_service';
import { GraphBoundary } from './graph_boundary';
import './stakeholder_map_tab.css';

const ForceView = lazy(() => import('./stakeholder_force_view'));
const FlowView = lazy(() => import('./stakeholder_flow_view'));

const INST: Record<string, string> = {
  file: '#1e3a8a', ep: '#be123c', ec: '#0693e3', council: '#9b51e0', stakeholder: '#d97706',
};
const STANCE: Record<string, string> = { support: '#059669', oppose: '#dc2626', amend: '#d97706' };

function colorOf(n: SMNode): string {
  if (n.type === 'org' && n.stance && STANCE[n.stance]) return STANCE[n.stance];
  return INST[n.institution] || '#64748b';
}

export function StakeholderMapTab() {
  const { t } = useTranslation();
  const [files, setFiles] = useState<SMFile[]>([]);
  const [mine, setMine] = useState(true);      // My interests | All
  const [sel, setSel] = useState('');          // '' = overview
  const [view, setView] = useState<'cards' | 'web' | 'map'>('cards');
  const [graph, setGraph] = useState<SMGraph | null>(null);
  const [contacts, setContacts] = useState<SMContactsResult | null>(null);
  const [pick, setPick] = useState<SMNode | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { stakeholdersService.files(mine).then((r) => setFiles(r.files)).catch(() => {}); }, [mine]);
  useEffect(() => {
    setLoading(true); setPick(null); setContacts(null);
    stakeholdersService.graph(sel || undefined, mine)
      .then(setGraph).catch(() => setGraph(null)).finally(() => setLoading(false));
    stakeholdersService.contacts(sel || undefined, mine).then(setContacts).catch(() => setContacts(null));
  }, [sel, mine]);

  const setScope = (m: boolean) => { setMine(m); setSel(''); };

  const legend = useMemo(() => ([
    ['ep', t('sm.ep', 'European Parliament')],
    ['ec', t('sm.ec', 'Commission')],
    ['council', t('sm.council', 'Council')],
    ['stakeholder', t('sm.stakeholders', 'Stakeholders')],
  ] as [string, string][]), [t]);

  return (
    <div className="sm-tab">
      <header className="db-tab__header">
        <div className="db-tab__title">
          <Icon path={mdiGraphOutline} size={1.1} />
          <div>
            <h2>{t('bubble.stakeholder_mapping', 'Stakeholder Mapping')}</h2>
            <p>{t('sm.subtitle', 'Who matters on your files and across your interests: the Parliament, Commission and Council actors and the organisations active around them.')}</p>
          </div>
        </div>
      </header>

      <div className="sm-controls">
        <div className="sm-toggle sm-scope">
          <button className={mine ? 'is-active' : ''} onClick={() => setScope(true)}>{t('sm.mine', 'My interests')}</button>
          <button className={!mine ? 'is-active' : ''} onClick={() => setScope(false)}>{t('sm.all', 'All')}</button>
        </div>
        <label className="sm-select">
          <span>{t('sm.focus', 'Focus')}</span>
          <select value={sel} onChange={(e) => setSel(e.target.value)}>
            <option value="">{t('sm.overviewShort', 'Overview')}</option>
            {files.map((f) => (
              <option key={f.ref} value={f.ref}>{(f.title || f.ref).slice(0, 70)}</option>
            ))}
          </select>
        </label>
        <div className="sm-toggle" role="tablist">
          <button role="tab" aria-selected={view === 'cards'} className={view === 'cards' ? 'is-active' : ''} onClick={() => setView('cards')}>
            <Icon path={mdiViewGridOutline} size={0.7} /> {t('sm.cards', 'Cards')}
          </button>
          <button role="tab" aria-selected={view === 'web'} className={view === 'web' ? 'is-active' : ''} onClick={() => setView('web')}>
            <Icon path={mdiVectorTriangle} size={0.7} /> {t('sm.web', 'Web')}
          </button>
          <button role="tab" aria-selected={view === 'map'} className={view === 'map' ? 'is-active' : ''} onClick={() => setView('map')}>
            <Icon path={mdiSitemapOutline} size={0.7} /> {t('sm.map', 'Map')}
          </button>
        </div>
      </div>

      <div className="sm-stage">
        <div className="sm-main">
          {/* All scope, Cards: the full browsable directory (independent of the graph) */}
          {view === 'cards' && !mine && <DirectoryView onPick={setPick} t={t} />}

          {!(view === 'cards' && !mine) && loading && <div className="db-loading">{t('sm.loading', 'Building the map...')}</div>}
          {!(view === 'cards' && !mine) && !loading && graph && graph.nodes.length <= 1 && (
            <div className="db-note"><Icon path={mdiInformationOutline} size={0.7} />
              <span>{t('sm.empty', 'No actors yet. Track a file (or set your policy interests) and the map fills in.')}</span></div>
          )}

          {!loading && graph && graph.nodes.length > 1 && view === 'cards' && mine && (
            <CardsView graph={graph} contacts={contacts} onPick={setPick} t={t} />
          )}

          {!loading && graph && graph.nodes.length > 1 && view !== 'cards' && (
            <div className="sm-graphwrap">
              <GraphBoundary
                key={`${view}:${graph.focus?.id || ''}`}
                fallback={
                  <div className="sm-fallback">
                    <Icon path={mdiInformationOutline} size={1} />
                    <p>{t('sm.viewError', 'This view could not be drawn here. Try another view.')}</p>
                    <button onClick={() => setView('cards')}>{t('sm.switchView', 'Switch view')}</button>
                  </div>
                }
              >
                <Suspense fallback={<div className="db-loading">{t('sm.loading', 'Building the map...')}</div>}>
                  {view === 'web'
                    ? <ForceView graph={graph} colorOf={colorOf} onPick={setPick} />
                    : <FlowView graph={graph} colorOf={colorOf} onPick={setPick} />}
                </Suspense>
              </GraphBoundary>

              <div className="sm-help" tabIndex={0}>
                <Icon path={mdiInformationOutline} size={0.8} />
                <div className="sm-help__pop">
                  {view === 'web'
                    ? t('sm.helpWeb', 'Drag the background to pan and scroll to zoom. Hover a dot to see its name, click it for full details. Bigger, more connected dots are more central to the file. Colours: red Parliament, blue Commission, purple Council, navy file, amber stakeholders (green supports, red opposes).')
                    : t('sm.helpMap', 'Each column is an institution: Parliament, Council, the file, the Commission, then stakeholders. Click any card for full details. Lines show who connects to what; faint lines are inferred, solid lines are evidence.')}
                </div>
              </div>

              <div className="sm-legend">
                {legend.map(([k, label]) => (
                  <span key={k} className="sm-legend__item"><i style={{ background: INST[k] }} /> {label}</span>
                ))}
                <span className="sm-legend__sep" />
                <span className="sm-legend__item"><i style={{ background: STANCE.support }} /> {t('sm.support', 'supports')}</span>
                <span className="sm-legend__item"><i style={{ background: STANCE.oppose }} /> {t('sm.oppose', 'opposes')}</span>
                <span className="sm-legend__hint">{t('sm.provenance', 'Faint links are inferred (PI crosswalk); solid links are evidence.')}</span>
              </div>
            </div>
          )}
        </div>

        {pick && <NodeDrawer node={pick} onClose={() => setPick(null)} t={t} />}
      </div>
    </div>
  );
}

const GROUP_ORDER: SMNode['institution'][] = ['file', 'ep', 'ec', 'council', 'stakeholder'];

function NodeCard({ n, onPick, t }: { n: SMNode; onPick: (n: SMNode) => void; t: any }) {
  return (
    <button type="button" className="sm-card" style={{ borderLeftColor: colorOf(n) }} onClick={() => onPick(n)}>
      <span className="sm-card__label">{n.label}</span>
      {n.sublabel && <span className="sm-card__sub">{n.sublabel}</span>}
      <div className="sm-card__badges">
        {n.pi_match && <i className="sm-badge sm-badge--pi">{t('sm.yourInterest', 'Your interest')}</i>}
        {n.stance && <i className="sm-badge" style={{ color: STANCE[n.stance], background: STANCE[n.stance] + '1f' }}>{t('sm.stance_' + n.stance, n.stance)}</i>}
        {n.meta?.is_brussels && <i className="sm-badge sm-badge--bx">{t('sm.brussels', 'Brussels')}</i>}
        {typeof n.meta?.meetings === 'number' && n.meta.meetings > 0 && <i className="sm-badge sm-badge--m">{n.meta.meetings} {t('sm.meet', 'meetings')}</i>}
      </div>
    </button>
  );
}

function CardsView({ graph, contacts, onPick, t }: { graph: SMGraph; contacts: SMContactsResult | null; onPick: (n: SMNode) => void; t: any }) {
  const byInst: Record<string, SMNode[]> = {};
  // Skip the synthetic "Your interests" hub (anchors the Web/Map graphs, not a real actor).
  graph.nodes.filter((n) => n.id !== 'pi:hub').forEach((n) => { (byInst[n.institution] ||= []).push(n); });
  Object.values(byInst).forEach((l) => l.sort((a, b) => (b.relevance || 0) - (a.relevance || 0)));
  const LABELS: Record<string, string> = {
    file: t('sm.gFile', 'Files'), ep: t('sm.ep', 'European Parliament'),
    ec: t('sm.ec', 'European Commission'), council: t('sm.council', 'Council'),
    stakeholder: t('sm.stakeholders', 'Stakeholders'),
  };
  const hasContacts = !!(contacts && contacts.dgs.length > 0);
  const tabs = GROUP_ORDER.filter((inst) => (byInst[inst]?.length) || (inst === 'ec' && hasContacts));
  const [tab, setTab] = useState('');
  const [ecSub, setEcSub] = useState<'departments' | 'contacts'>('departments');
  const active = (tabs as string[]).includes(tab) ? tab : (tabs[0] || '');

  const note = (txt: string) => (
    <div className="db-note"><Icon path={mdiInformationOutline} size={0.7} /><span>{txt}</span></div>
  );

  return (
    <div className="sm-cards">
      <div className="sm-ctabs" role="tablist">
        {tabs.map((inst) => (
          <button key={inst} role="tab" aria-selected={active === inst}
            style={active === inst ? { color: INST[inst], borderBottomColor: INST[inst] } : undefined}
            onClick={() => setTab(inst)}>
            {LABELS[inst]} <span>{byInst[inst]?.length || 0}</span>
          </button>
        ))}
      </div>

      {active && active !== 'ec' && (
        <div className="sm-cards__grid">{(byInst[active] || []).map((n) => <NodeCard key={n.id} n={n} onPick={onPick} t={t} />)}</div>
      )}

      {active === 'ec' && (
        <>
          <div className="sm-subtabs" role="tablist">
            <button role="tab" aria-selected={ecSub === 'departments'} onClick={() => setEcSub('departments')}>{t('sm.departments', 'Departments')}</button>
            <button role="tab" aria-selected={ecSub === 'contacts'} onClick={() => setEcSub('contacts')}>{t('sm.contactsTitle', 'Who to contact in the Commission')}</button>
          </div>
          {ecSub === 'departments' && (
            byInst.ec?.length
              ? <div className="sm-cards__grid">{byInst.ec.map((n) => <NodeCard key={n.id} n={n} onPick={onPick} t={t} />)}</div>
              : note(t('sm.noDepartments', 'No Commission departments in this view. Focus a file to see its lead DGs.'))
          )}
          {ecSub === 'contacts' && (
            hasContacts
              ? <div className="sm-contacts">
                  <p className="sm-contacts__hint">{t('sm.contactsHint', 'Heads of unit and their email, units relevant to this file first. Names and emails are from the EU Who-is-Who directory.')}</p>
                  {contacts!.dgs.map((dg) => <DgContacts key={dg.dg} dg={dg} t={t} />)}
                </div>
              : note(t('sm.noContacts', 'Focus a file to see who to contact in its lead departments.'))
          )}
        </>
      )}
    </div>
  );
}

// -------------------------------------------------------------- All-mode directory
const DIR_TABS: SMNode['institution'][] = ['stakeholder', 'ec', 'ep', 'council', 'file'];
const PAGED = new Set(['stakeholder', 'ep', 'file']);

function DirectoryView({ onPick, t }: { onPick: (n: SMNode) => void; t: any }) {
  const LABELS: Record<string, string> = {
    file: t('sm.gFile', 'Files'), ep: t('sm.ep', 'European Parliament'),
    ec: t('sm.ec', 'European Commission'), council: t('sm.council', 'Council'),
    stakeholder: t('sm.stakeholders', 'Stakeholders'),
  };
  const [tab, setTab] = useState<SMNode['institution']>('stakeholder');
  const [ecSub, setEcSub] = useState<'departments' | 'contacts'>('departments');
  const [qInput, setQInput] = useState('');
  const [q, setQ] = useState('');
  const [items, setItems] = useState<SMNode[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  // EC -> Who to contact
  const [dgs, setDgs] = useState<SMNode[]>([]);
  const [selDg, setSelDg] = useState('');
  const [dgTree, setDgTree] = useState<SMDgContacts | null>(null);

  useEffect(() => { const id = setTimeout(() => setQ(qInput), 350); return () => clearTimeout(id); }, [qInput]);
  useEffect(() => { setQInput(''); setQ(''); }, [tab]);

  const browsing = !(tab === 'ec' && ecSub === 'contacts');
  useEffect(() => {
    if (!browsing) return;
    setLoading(true); setPage(1);
    stakeholdersService.directory(tab, q, 1)
      .then((r) => { setTotal(r.total); setItems(r.items); })
      .catch(() => { setTotal(0); setItems([]); }).finally(() => setLoading(false));
  }, [tab, q, browsing]);

  const more = () => {
    const next = page + 1;
    setLoading(true);
    stakeholdersService.directory(tab, q, next)
      .then((r) => { setPage(next); setItems((prev) => [...prev, ...r.items]); })
      .catch(() => {}).finally(() => setLoading(false));
  };

  // DG picker for Who-to-contact
  useEffect(() => { stakeholdersService.directory('ec', '', 1, 100).then((r) => setDgs(r.items)).catch(() => {}); }, []);
  useEffect(() => {
    if (!selDg) { setDgTree(null); return; }
    stakeholdersService.contactsByDg(selDg).then((r) => setDgTree(r.dgs[0] || null)).catch(() => setDgTree(null));
  }, [selDg]);

  return (
    <div className="sm-cards">
      <div className="sm-ctabs" role="tablist">
        {DIR_TABS.map((inst) => (
          <button key={inst} role="tab" aria-selected={tab === inst}
            style={tab === inst ? { color: INST[inst], borderBottomColor: INST[inst] } : undefined}
            onClick={() => setTab(inst)}>{LABELS[inst]}</button>
        ))}
      </div>

      {tab === 'ec' && (
        <div className="sm-subtabs" role="tablist">
          <button role="tab" aria-selected={ecSub === 'departments'} onClick={() => setEcSub('departments')}>{t('sm.departments', 'Departments')}</button>
          <button role="tab" aria-selected={ecSub === 'contacts'} onClick={() => setEcSub('contacts')}>{t('sm.contactsTitle', 'Who to contact in the Commission')}</button>
        </div>
      )}

      {tab === 'ec' && ecSub === 'contacts' ? (
        <div className="sm-contacts">
          <label className="sm-select sm-dg-pick">
            <span>{t('sm.department', 'Department')}</span>
            <select value={selDg} onChange={(e) => setSelDg(e.target.value)}>
              <option value="">{t('sm.pickDepartment', 'Pick a department...')}</option>
              {dgs.map((d) => <option key={d.id} value={d.label}>{d.label} — {d.sublabel}</option>)}
            </select>
          </label>
          {dgTree && <DgContacts dg={dgTree} t={t} />}
        </div>
      ) : (
        <>
          {(PAGED.has(tab) || tab === 'ec') && (
            <div className="sm-search">
              <Icon path={mdiMagnify} size={0.7} />
              <input value={qInput} onChange={(e) => setQInput(e.target.value)}
                placeholder={t('sm.searchPlaceholder', 'Search by name...')} />
              {!loading && <span className="sm-search__count">{total.toLocaleString()}</span>}
            </div>
          )}
          {items.length > 0 && (
            <div className="sm-cards__grid">{items.map((n) => <NodeCard key={n.id} n={n} onPick={onPick} t={t} />)}</div>
          )}
          {loading && <div className="db-loading">{t('sm.loading', 'Building the map...')}</div>}
          {!loading && items.length === 0 && (
            <div className="db-note"><Icon path={mdiInformationOutline} size={0.7} /><span>{t('sm.noResults', 'No results.')}</span></div>
          )}
          {!loading && items.length < total && (
            <button type="button" className="sm-dg__more" onClick={more}>
              {t('sm.loadMore', 'Load more')} ({items.length}/{total.toLocaleString()})
            </button>
          )}
        </>
      )}
    </div>
  );
}

function DgContacts({ dg, t }: { dg: SMDgContacts; t: any }) {
  const [all, setAll] = useState(false);
  const units = dg.directorates.flatMap((d) =>
    d.units.filter((u) => u.head && u.head.email).map((u) => ({ ...u, dir: `${d.code} · ${d.name}` })));
  const relevant = units.filter((u) => u.relevant);
  const base = relevant.length ? relevant : units;
  const shown = all ? units : base.slice(0, 9);
  const dgp = dg.director_general;
  return (
    <div className="sm-dg">
      <div className="sm-dg__head">
        <a href={dg.url} target="_blank" rel="noopener noreferrer">{dg.dg} — {dg.dg_name} <Icon path={mdiOpenInNew} size={0.5} /></a>
        {dgp && (
          <span className="sm-dg__chief">{dgp.name} · {dgp.function || 'Director-General'}
            {dgp.email && <a href={`mailto:${dgp.email}`} title={dgp.email}><Icon path={mdiEmailOutline} size={0.6} /></a>}
          </span>
        )}
      </div>
      <div className="sm-contact-grid">
        {shown.map((u) => (
          <div key={u.code} className={`sm-contact${u.relevant ? ' is-relevant' : ''}`}>
            <span className="sm-contact__unit">{u.code} {u.name}</span>
            <span className="sm-contact__dir">{u.dir}</span>
            <span className="sm-contact__head">{u.head!.name}<small>{u.head!.function}</small></span>
            <a className="sm-contact__mail" href={`mailto:${u.head!.email}`}>
              <Icon path={mdiEmailOutline} size={0.6} /> {u.head!.email}
            </a>
          </div>
        ))}
      </div>
      {units.length > shown.length && (
        <button type="button" className="sm-dg__more" onClick={() => setAll(true)}>
          {t('sm.showAllUnits', 'Show all units')} ({units.length}) <Icon path={mdiChevronDown} size={0.6} />
        </button>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value?: any }) {
  if (value === undefined || value === null || value === '') return null;
  return <div className="sm-drawer__row"><span>{label}</span><strong>{String(value)}</strong></div>;
}

function NodeDrawer({ node, onClose, t }: { node: SMNode; onClose: () => void; t: any }) {
  const m = node.meta || {};
  const typeLabel: Record<string, string> = {
    file: t('sm.tFile', 'Legislative file'), committee: t('sm.tCommittee', 'EP committee'),
    mep: t('sm.tMep', 'Member of Parliament'), dg: t('sm.tDg', 'Commission DG'),
    official: t('sm.tOfficial', 'EU Who-is-Who'), council_config: t('sm.tCouncil', 'Council configuration'),
    org: t('sm.tOrg', 'Organisation'),
  };
  return (
    <aside className="sm-drawer">
      <button className="sm-drawer__close" onClick={onClose} aria-label={t('common.close', 'Close')}><Icon path={mdiClose} size={0.8} /></button>
      <span className="sm-drawer__kind" style={{ background: colorOf(node) }}>{typeLabel[node.type] || node.type}</span>
      <h3>{m.full_name || node.label}</h3>
      {node.sublabel && <p className="sm-drawer__sub">{node.sublabel}</p>}

      {node.type === 'org' && (
        <>
          <Row label={t('sm.category', 'Category')} value={node.sublabel} />
          <Row label={t('sm.hq', 'Head office')} value={[m.hq_city, m.hq_country].filter(Boolean).join(', ')} />
          {m.is_brussels && <div className="sm-tag">{t('sm.brussels', 'Brussels-based')}</div>}
          {typeof m.meetings === 'number' && m.meetings > 0 && <Row label={t('sm.meetings', 'Lobby meetings on this file')} value={m.meetings} />}
          {node.stance && <Row label={t('sm.stance', 'Stated position')} value={t('sm.stance_' + node.stance, node.stance)} />}
          {m.stance_summary && <p className="sm-drawer__quote">{m.stance_summary}</p>}
          {m.kind === 'ecosystem' && <p className="sm-drawer__note">{t('sm.ecosystemNote', 'Brussels-based organisation active in this policy area (shown for context).')}</p>}
        </>
      )}
      {node.type === 'mep' && <Row label={t('sm.role', 'Role')} value={m.role} />}
      {node.type === 'official' && <p className="sm-drawer__note">{t('sm.wiwNote', 'Opens the live EU Who-is-Who organisation chart for this department.')}</p>}

      {node.url && (
        <a className="sm-drawer__cta" href={node.url} target="_blank" rel="noopener noreferrer">
          {t('sm.open', 'Open profile')} <Icon path={mdiOpenInNew} size={0.6} />
        </a>
      )}
    </aside>
  );
}

export default StakeholderMapTab;
