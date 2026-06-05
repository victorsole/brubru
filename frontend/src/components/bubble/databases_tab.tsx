/**
 * Brubru Databases tab (MEUB Section 4.2 - Analysis & Strategy).
 *
 * Six sub-tabs (seven in the Catalan UI):
 *   - EU Canon: synthetic, animated mirror of /eucanon/ (binding-law explainers).
 *   - Deep Dives: animated summary of the thematic deep-dive reports.
 *   - Knowledge Guides: synthetic mirror of /guides/index.html (categories + counts).
 *   - Dret europeu en catala: Catalan-only; mirror of /legislacio-ue-catala/.
 *   - Policy Areas: "who does what" across the EU institutions, PI-aware, charts.
 *   - Beresol Monitors: live Beresol policy-intelligence digests (Beresol Monitor API).
 *
 * (Research & Evidence is now its own top-level Section-4 tab: research_evidence_tab.tsx,
 *  since it surfaces EXTERNAL EU sources, not Brubru-proprietary databases.)
 *
 * Brubru aesthetic (#1e3a8a / #0693e3 + rainbow accent), framer-motion animation,
 * Recharts viz, 1040px content cap, 6 languages. Every URL is verified-real. No
 * Anthropic. No em-dashes. Libraries auto-update from their canonical sources
 * (canon manifest, deep_dive_map, the regenerated guides index, the Catalan dirs).
 */
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, AnimatePresence } from 'framer-motion';
import Icon from '@mdi/react';
import {
  mdiBookshelf, mdiBookOpenPageVariantOutline, mdiFileDocumentMultipleOutline, mdiTranslate,
  mdiSitemapOutline, mdiRadar, mdiOpenInNew, mdiAccountGroupOutline,
  mdiDomain, mdiBankOutline, mdiArrowRight, mdiInformationOutline,
  mdiFormatListNumbered, mdiCalendarOutline, mdiDna, mdiFactory, mdiClockAlertOutline,
  mdiPill, mdiAccessPointNetwork, mdiShieldAlertOutline, mdiTerrain,
  mdiShieldOutline, mdiSwapHorizontal, mdiRobotOutline, mdiAtomVariant, mdiRocketLaunchOutline,
  mdiGold, mdiChartLine, mdiChevronDown, mdiChevronUp,
} from '@mdi/js';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell, PieChart, Pie,
} from 'recharts';
import { databasesService } from '../../services/databases_service';
import type {
  CanonResult, GuidesResult, CatalanResult, PolicyAreasResult, PolicyArea,
  BeresolMonitorsResult, BeresolMonitorDetail,
} from '../../services/databases_service';
import { DEEP_DIVES, getDeepDiveUrl, LANG_LABELS } from '../../utils/deep_dive_map';
import './databases_tab.css';

type Sub = 'canon' | 'deep' | 'guides' | 'catalan' | 'policy' | 'partners';

const C = { primary: '#1e3a8a', accent: '#0693e3', pi: '#d97706', ep: '#be123c', ec: '#0693e3', council: '#9b51e0', muted: '#cbd5e1' };

// Map the deep-dive map's mdi-class strings to @mdi/js icon paths.
const DD_ICON: Record<string, string> = {
  'mdi-domain': mdiDomain, 'mdi-dna': mdiDna, 'mdi-factory': mdiFactory,
  'mdi-clock-alert-outline': mdiClockAlertOutline, 'mdi-pill': mdiPill,
  'mdi-access-point-network': mdiAccessPointNetwork, 'mdi-shield-alert-outline': mdiShieldAlertOutline,
  'mdi-mountain': mdiTerrain,
};

const slugify = (s: string) => s.toLowerCase().replace(/&/g, 'and').replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');

// Per-monitor icon (Beresol Monitors). Falls back to the radar glyph.
const MON_ICON: Record<string, string> = {
  defence: mdiShieldOutline, cmu: mdiBankOutline, tariff: mdiSwapHorizontal,
  ai: mdiRobotOutline, quantum: mdiAtomVariant, startup: mdiRocketLaunchOutline,
  gold: mdiGold, markets: mdiChartLine,
};

const fmtDate = (iso?: string) => {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
};


// Count-up animation for the library KPIs.
function CountUp({ to }: { to: number }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    let raf = 0; const start = performance.now(); const dur = 700;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      setN(Math.round(to * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to]);
  return <>{n.toLocaleString()}</>;
}

const cardVariants = {
  hidden: { opacity: 0, y: 14 },
  show: (i: number) => ({ opacity: 1, y: 0, transition: { delay: Math.min(i, 12) * 0.05 } }),
};

// Reusable animated hero strip with the EU Canon rainbow accent + KPI count-ups.
function LibHero({ icon, title, subtitle, kpis, cta }: {
  icon: string; title: string; subtitle: string;
  kpis: { value: number; label: string }[];
  cta?: { label: string; url: string };
}) {
  return (
    <motion.header className="db-hero" initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
      <div className="db-hero__accent" />
      <div className="db-hero__body">
        <div className="db-hero__lead">
          <span className="db-hero__icon"><Icon path={icon} size={1.1} /></span>
          <div>
            <h3>{title}</h3>
            <p>{subtitle}</p>
          </div>
        </div>
        <div className="db-hero__kpis">
          {kpis.map((k) => (
            <div key={k.label} className="db-kpi">
              <span className="db-kpi__value"><CountUp to={k.value} /></span>
              <span className="db-kpi__label">{k.label}</span>
            </div>
          ))}
        </div>
      </div>
      {cta && (
        <a className="db-hero__cta" href={cta.url} target="_blank" rel="noopener noreferrer">
          {cta.label} <Icon path={mdiArrowRight} size={0.7} />
        </a>
      )}
    </motion.header>
  );
}

export function DatabasesTab() {
  const { t, i18n } = useTranslation();
  const isCa = i18n.language?.startsWith('ca');
  const [sub, setSub] = useState<Sub>('canon');
  const [canon, setCanon] = useState<CanonResult | null>(null);
  const [guides, setGuides] = useState<GuidesResult | null>(null);
  const [catalan, setCatalan] = useState<CatalanResult | null>(null);
  const [pa, setPa] = useState<PolicyAreasResult | null>(null);
  const [paMine, setPaMine] = useState(true);
  const [selArea, setSelArea] = useState<string | null>(null);

  // If the user leaves Catalan while on the Catalan tab, fall back to EU Canon.
  useEffect(() => { if (!isCa && sub === 'catalan') setSub('canon'); }, [isCa, sub]);

  // Lazy-load each library when its tab is first opened.
  useEffect(() => { if (sub === 'canon' && !canon) databasesService.canon().then(setCanon).catch(() => {}); }, [sub, canon]);
  useEffect(() => { if (sub === 'guides' && !guides) databasesService.guides().then(setGuides).catch(() => {}); }, [sub, guides]);
  useEffect(() => { if (sub === 'catalan' && !catalan) databasesService.catalan().then(setCatalan).catch(() => {}); }, [sub, catalan]);
  useEffect(() => {
    if (sub !== 'policy') return;
    databasesService.policyAreas(paMine).then((r) => { setPa(r); setSelArea(r.areas[0]?.name || null); }).catch(() => {});
  }, [sub, paMine]);

  const tabs: [Sub, string, string][] = [
    ['canon', mdiBookOpenPageVariantOutline, t('db.tabCanon', 'EU Canon')],
    ['deep', mdiFileDocumentMultipleOutline, t('db.tabDeep', 'Deep Dives')],
    ['guides', mdiBookshelf, t('db.tabGuides', 'Knowledge Guides')],
    ...(isCa ? [['catalan', mdiTranslate, t('db.tabCatalan', 'Dret europeu en català')]] as [Sub, string, string][] : []),
    ['policy', mdiSitemapOutline, t('db.tabPolicy', 'Policy Areas')],
    ['partners', mdiRadar, t('db.tabPartners', 'Beresol Monitors')],
  ];

  return (
    <div className="db-tab">
      <header className="db-tab__header">
        <div className="db-tab__title">
          <Icon path={mdiBookshelf} size={1.1} />
          <div>
            <h2>{t('bubble.databases', 'Brubru Databases')}</h2>
            <p>{t('db.subtitle', 'Brubru’s knowledge libraries and a map of who does what across the EU, tailored to your interests.')}</p>
          </div>
        </div>
      </header>

      <div className="db-subtabs" role="tablist">
        {tabs.map(([id, icon, label]) => (
          <button key={id} role="tab" aria-selected={sub === id} className={sub === id ? 'is-active' : ''} onClick={() => setSub(id)}>
            <Icon path={icon} size={0.7} /> {label}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div key={sub} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
          {sub === 'canon' && <CanonLibrary data={canon} t={t} lang={i18n.language} />}
          {sub === 'deep' && <DeepDives t={t} lang={i18n.language} />}
          {sub === 'guides' && <KnowledgeGuides data={guides} t={t} />}
          {sub === 'catalan' && <CatalanLibrary data={catalan} t={t} />}
          {sub === 'policy' && <PolicyAreas pa={pa} mine={paMine} setMine={setPaMine} sel={selArea} setSel={setSelArea} t={t} />}
          {sub === 'partners' && <BeresolMonitors t={t} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

// -------------------------------------------------------------- EU Canon
function CanonLibrary({ data, t, lang }: { data: CanonResult | null; t: any; lang: string }) {
  if (!data) return <div className="db-loading">{t('db.loading', 'Loading...')}</div>;
  const langKey = (lang || 'en').slice(0, 2);
  return (
    <div className="db-section">
      <LibHero
        icon={mdiBookOpenPageVariantOutline}
        title={t('db.canonTitle', 'EU Canon')}
        subtitle={t('db.canonDesc', 'Plain-language, article-by-article explainers of binding EU laws.')}
        kpis={[
          { value: data.count, label: t('db.canonKpiLaws', 'laws explained') },
          { value: data.languages, label: t('db.kpiLanguages', 'languages') },
        ]}
        cta={{ label: t('db.openCanon', 'Open the full EU Canon'), url: data.site_url }}
      />
      <div className="db-canon-grid">
        {data.items.map((it, i) => {
          const href = (it.lang_urls && it.lang_urls[langKey]) || it.url || data.site_url;
          const stats = [
            it.articles ? { icon: mdiFormatListNumbered, value: it.articles, label: t('db.articles', 'Articles') } : null,
            it.titles ? { icon: mdiBookOpenPageVariantOutline, value: it.titles, label: t('db.titles', 'Titles') } : null,
            { icon: mdiTranslate, value: it.languages.length, label: t('db.kpiLanguages', 'languages') },
            it.year ? { icon: mdiCalendarOutline, value: it.year, label: t('db.enacted', 'Enacted') } : null,
          ].filter(Boolean) as { icon: string; value: number | string; label: string }[];
          return (
            <motion.a key={it.slug || i} className="db-canon-card" href={href} target="_blank" rel="noopener noreferrer"
              custom={i} variants={cardVariants} initial="hidden" animate="show" whileHover={{ y: -4, boxShadow: '0 12px 28px rgba(15,23,42,0.12)' }}>
              {it.celex && <span className="db-canon-card__celex">CELEX {it.celex}</span>}
              <h4>{it.title}</h4>
              {it.doc_type && <p className="db-canon-card__sub">{it.doc_type}</p>}
              {(it.chips.length > 0 || it.family_label) && (
                <div className="db-chips">
                  {(it.chips.length ? it.chips : [it.family_label!]).slice(0, 3).map((c) => <span key={c} className="db-chip">{c}</span>)}
                </div>
              )}
              <div className="db-canon-card__stats">
                {stats.map((s) => (
                  <div key={s.label} className="db-stat-mini">
                    <span className="db-stat-mini__value"><Icon path={s.icon} size={0.55} /> {s.value}</span>
                    <span className="db-stat-mini__label">{s.label}</span>
                  </div>
                ))}
              </div>
              <span className="db-canon-card__cta">{t('db.readExplainer', 'Read the explainer')} <Icon path={mdiArrowRight} size={0.6} /></span>
            </motion.a>
          );
        })}
      </div>
    </div>
  );
}

// -------------------------------------------------------------- Deep Dives
function DeepDives({ t, lang }: { t: any; lang: string }) {
  const langKey = (lang || 'en').slice(0, 2);
  const langs = useMemo(() => new Set(DEEP_DIVES.flatMap((d) => d.languages)), []);
  return (
    <div className="db-section">
      <LibHero
        icon={mdiFileDocumentMultipleOutline}
        title={t('db.deepTitle', 'Deep Dives')}
        subtitle={t('db.deepDesc', 'Thematic, end-to-end analyses of the EU files that matter most.')}
        kpis={[
          { value: DEEP_DIVES.length, label: t('db.deepKpi', 'deep dives') },
          { value: langs.size, label: t('db.kpiLanguages', 'languages') },
        ]}
      />
      <div className="db-deep-grid">
        {DEEP_DIVES.map((dd, i) => {
          const href = dd.languages.includes(langKey) ? getDeepDiveUrl(dd, langKey) : getDeepDiveUrl(dd, 'en');
          return (
            <motion.a key={dd.procedureRef} className="db-deep-card" href={href} target="_blank" rel="noopener noreferrer"
              style={{ ['--dd' as any]: dd.color }} custom={i} variants={cardVariants} initial="hidden" animate="show"
              whileHover={{ y: -4, boxShadow: '0 12px 28px rgba(15,23,42,0.12)' }}>
              <div className="db-deep-card__bar" />
              <div className="db-deep-card__head">
                <span className="db-deep-card__icon"><Icon path={DD_ICON[dd.icon] || mdiFileDocumentMultipleOutline} size={0.9} /></span>
                <div className="db-deep-card__refs">
                  <span className="db-ref">{dd.comReference}</span>
                  <span className="db-ref db-ref--muted">{dd.procedureRef}</span>
                </div>
              </div>
              <h4>{dd.title}</h4>
              <div className="db-langpills">
                {dd.languages.map((l) => <span key={l} className="db-langpill">{LANG_LABELS[l] || l.toUpperCase()}</span>)}
              </div>
              <span className="db-canon-card__cta">{t('db.readDeep', 'Read deep dive')} <Icon path={mdiArrowRight} size={0.6} /></span>
            </motion.a>
          );
        })}
      </div>
    </div>
  );
}

// -------------------------------------------------------------- Knowledge Guides
function KnowledgeGuides({ data, t }: { data: GuidesResult | null; t: any }) {
  if (!data) return <div className="db-loading">{t('db.loading', 'Loading...')}</div>;
  return (
    <div className="db-section">
      <LibHero
        icon={mdiBookshelf}
        title={t('db.guidesTitle', 'Knowledge Guides')}
        subtitle={t('db.guidesDesc', 'The curated guides that ground every Brubru answer.')}
        kpis={[
          { value: data.count, label: t('db.guidesKpi', 'guides') },
          { value: data.categories.length, label: t('db.categories', 'categories') },
        ]}
        cta={{ label: t('db.openGuides', 'Browse all guides'), url: data.url }}
      />
      <div className="db-guide-grid">
        {data.categories.map((cat, i) => (
          <motion.a key={cat.title} className="db-guide-card" href={`${data.url}#${slugify(cat.title)}`} target="_blank" rel="noopener noreferrer"
            custom={i} variants={cardVariants} initial="hidden" animate="show" whileHover={{ y: -4, boxShadow: '0 10px 24px rgba(15,23,42,0.10)' }}>
            <span className="db-guide-card__icon" style={{ background: cat.color }}>
              <span className={`mdi ${cat.icon}`} aria-hidden="true" />
            </span>
            <div className="db-guide-card__body">
              <h4>{cat.title}</h4>
              <span className="db-guide-card__count" style={{ color: cat.color }}>
                <CountUp to={cat.count} /> {cat.count === 1 ? t('db.guideOne', 'guide') : t('db.guidesKpi', 'guides')}
              </span>
            </div>
          </motion.a>
        ))}
      </div>
    </div>
  );
}

// -------------------------------------------------------------- Dret europeu en català
function CatalanLibrary({ data, t }: { data: CatalanResult | null; t: any }) {
  if (!data) return <div className="db-loading">{t('db.loading', 'Loading...')}</div>;
  return (
    <div className="db-section">
      <LibHero
        icon={mdiTranslate}
        title={t('db.catalanTitle', 'Dret europeu en català')}
        subtitle={t('db.catalanDesc', 'Legislació de la UE traduïda al català.')}
        kpis={[{ value: data.count, label: t('db.catalanKpi', 'textos traduïts') }]}
        cta={{ label: t('db.openCatalan', 'Obre Dret europeu en català'), url: data.url }}
      />
      {data.items.length === 0 ? (
        <div className="db-note"><Icon path={mdiInformationOutline} size={0.7} /><span>{t('db.catalanEmpty', 'Encara no hi ha traduccions publicades.')}</span></div>
      ) : (
        <div className="db-canon-grid">
          {data.items.map((it, i) => (
            <motion.a key={it.name} className="db-canon-card" href={it.url} target="_blank" rel="noopener noreferrer"
              custom={i} variants={cardVariants} initial="hidden" animate="show" whileHover={{ y: -4, boxShadow: '0 12px 28px rgba(15,23,42,0.12)' }}>
              <span className="db-canon-card__celex">{it.name}</span>
              <h4>{it.title}</h4>
              <span className="db-canon-card__cta">{t('db.readCatalan', 'Llegeix la traducció')} <Icon path={mdiOpenInNew} size={0.55} /></span>
            </motion.a>
          ))}
        </div>
      )}
    </div>
  );
}

// -------------------------------------------------------------- Policy Areas
function PolicyAreas({ pa, mine, setMine, sel, setSel, t }: {
  pa: PolicyAreasResult | null; mine: boolean; setMine: (v: boolean) => void;
  sel: string | null; setSel: (s: string) => void; t: any;
}) {
  const area: PolicyArea | undefined = useMemo(() => pa?.areas.find((a) => a.name === sel), [pa, sel]);
  const chartData = useMemo(() => (pa?.areas || []).slice(0, 14).map((a) => ({
    name: a.name.length > 22 ? a.name.slice(0, 21) + '…' : a.name, full: a.name, value: a.body_count, pi: a.is_pi_match,
  })), [pa]);
  const donut = area ? [
    { name: t('db.committees', 'EP committees'), value: area.committees.length, fill: C.ep },
    { name: t('db.dgs', 'Commission DGs'), value: area.dgs.length, fill: C.ec },
    { name: t('db.councilConfigs', 'Council configs'), value: area.council_configs.length, fill: C.council },
  ].filter((d) => d.value > 0) : [];

  if (!pa) return <div className="db-loading">{t('db.loading', 'Loading...')}</div>;
  return (
    <div className="db-policy">
      <div className="db-policy__controls">
        <div className="db-toggle">
          <button className={mine ? 'is-active' : ''} onClick={() => setMine(true)}>{t('db.mine', 'My interests')}</button>
          <button className={!mine ? 'is-active' : ''} onClick={() => setMine(false)}>{t('db.all', 'All areas')}</button>
        </div>
        <p className="db-policy__hint">{t('db.policyHint', 'Which EU institutions are responsible for each policy domain. Select a bar to explore.')}</p>
      </div>

      <div className="db-chart">
        <ResponsiveContainer width="100%" height={Math.max(280, chartData.length * 30)}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="name" width={170} tick={{ fontSize: 12, fill: '#475569' }} axisLine={false} tickLine={false} />
            <Tooltip cursor={{ fill: 'rgba(6,147,227,0.06)' }}
              formatter={(v: any) => [`${v} ${t('db.bodies', 'responsible bodies')}`, '']}
              labelFormatter={(l: any, p: any) => (p && p[0] ? p[0].payload.full : l)} />
            <Bar dataKey="value" radius={[0, 6, 6, 0]} onClick={(d: any) => d && setSel(d.full)} cursor="pointer" animationDuration={650}>
              {chartData.map((d, i) => <Cell key={i} fill={d.pi ? C.pi : C.accent} fillOpacity={d.full === sel ? 1 : 0.78} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <AnimatePresence mode="wait">
        {area && (
          <motion.div key={area.name} className="db-area" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
            <div className="db-area__head">
              <h3>{area.name}{area.is_pi_match && <span className="db-pi-badge">{t('db.yourInterest', 'Your interest')}</span>}</h3>
              {donut.length > 0 && (
                <div className="db-area__donut">
                  <ResponsiveContainer width={120} height={120}>
                    <PieChart>
                      <Pie data={donut} dataKey="value" innerRadius={32} outerRadius={52} paddingAngle={2} animationDuration={600}>
                        {donut.map((d, i) => <Cell key={i} fill={d.fill} />)}
                      </Pie>
                      <Tooltip formatter={(v: any, n: any) => [v, n]} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
            <div className="db-area__cols">
              <InstCol icon={mdiAccountGroupOutline} color={C.ep} title={t('db.committees', 'EP committees')} bodies={area.committees} />
              <InstCol icon={mdiDomain} color={C.ec} title={t('db.dgs', 'Commission DGs')} bodies={area.dgs} />
              <InstCol icon={mdiBankOutline} color={C.council} title={t('db.councilConfigs', 'Council configurations')} bodies={area.council_configs} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function InstCol({ icon, color, title, bodies }: { icon: string; color: string; title: string; bodies: { code: string; name: string }[] }) {
  const { t } = useTranslation();
  return (
    <div className="db-instcol" style={{ ['--inst' as any]: color }}>
      <h4><Icon path={icon} size={0.7} /> {title}</h4>
      {bodies.length === 0 ? <span className="db-instcol__none">{t('db.noBody', 'None mapped')}</span> : (
        <ul>{bodies.map((b) => <li key={b.code} title={b.name}><span className="db-code">{b.code}</span> {b.name}</li>)}</ul>
      )}
    </div>
  );
}

// -------------------------------------------------------------- Beresol Monitors
function BeresolMonitors({ t }: { t: any }) {
  const [res, setRes] = useState<BeresolMonitorsResult | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [detail, setDetail] = useState<BeresolMonitorDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    databasesService.beresolMonitors().then(setRes).catch(() => setRes({ available: false, reason: 'unreachable', monitors: [] }));
  }, []);
  useEffect(() => {
    if (!sel) { setDetail(null); return; }
    setLoadingDetail(true); setDetail(null);
    databasesService.beresolMonitor(sel)
      .then(setDetail).catch(() => setDetail({ available: false, reason: 'unreachable' }))
      .finally(() => setLoadingDetail(false));
  }, [sel]);

  if (!res) return <div className="db-loading">{t('db.loading', 'Loading...')}</div>;
  if (!res.available) {
    return (
      <div className="db-note">
        <Icon path={mdiInformationOutline} size={0.7} />
        <span>{t('db.beresolUnavailable', 'The Beresol Monitors feed is not reachable right now. Please try again shortly.')}</span>
      </div>
    );
  }
  return (
    <div className="db-section">
      <LibHero
        icon={mdiRadar}
        title={t('db.beresolTitle', 'Beresol Monitors')}
        subtitle={res.description || t('db.beresolDesc2', 'Beresol’s policy-intelligence monitors, live from the Beresol Monitor API.')}
        kpis={[{ value: res.count || res.monitors.length, label: t('db.beresolKpi', 'live monitors') }]}
        cta={{ label: t('db.openBeresol', 'Open Beresol'), url: res.source_url || 'https://beresol.eu' }}
      />
      <div className="db-monitor-grid">
        {res.monitors.map((m, i) => (
          <motion.button key={m.monitor} type="button" className={`db-monitor-card${sel === m.monitor ? ' is-active' : ''}`}
            custom={i} variants={cardVariants} initial="hidden" animate="show" whileHover={{ y: -4, boxShadow: '0 12px 28px rgba(15,23,42,0.12)' }}
            onClick={() => setSel(sel === m.monitor ? null : m.monitor)} aria-expanded={sel === m.monitor}>
            <span className="db-monitor-card__icon"><Icon path={MON_ICON[m.monitor] || mdiRadar} size={0.95} /></span>
            <h4>{m.title}</h4>
            <p>{m.description}</p>
            <span className="db-monitor-card__more">
              {sel === m.monitor ? t('db.hideDigest', 'Hide digest') : t('db.viewDigest', 'View digest')}
              <Icon path={sel === m.monitor ? mdiChevronUp : mdiChevronDown} size={0.6} />
            </span>
          </motion.button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {sel && (
          <motion.div key={sel} className="db-monitor-detail" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
            {loadingDetail && <div className="db-loading">{t('db.loading', 'Loading...')}</div>}
            {detail && detail.available && (
              <>
                <div className="db-monitor-detail__head">
                  <h3>{detail.title}</h3>
                  <div className="db-monitor-detail__meta">
                    {detail.created_date && <span className="db-monitor-detail__date">{t('db.updated', 'Updated')} {fmtDate(detail.created_date)}</span>}
                    {detail.public_url && (
                      <a href={detail.public_url} target="_blank" rel="noopener noreferrer">
                        {t('db.openDashboard', 'Open dashboard')} <Icon path={mdiOpenInNew} size={0.55} />
                      </a>
                    )}
                  </div>
                </div>
                <div className="db-monitor-digest" dangerouslySetInnerHTML={{ __html: detail.body_html || '' }} />
              </>
            )}
            {detail && !detail.available && !loadingDetail && (
              <div className="db-note"><Icon path={mdiInformationOutline} size={0.7} /><span>{t('db.digestUnavailable', 'This digest is not available right now.')}</span></div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default DatabasesTab;
