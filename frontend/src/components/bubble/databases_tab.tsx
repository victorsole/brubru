/**
 * Brubru Databases tab (MEUB Section 4.2 - Analysis & Strategy).
 *
 * Seven sub-tabs (eight in the Catalan UI):
 *   - EU Canon: synthetic, animated mirror of /eucanon/ (binding-law explainers).
 *   - Deep Dives: animated summary of the thematic deep-dive reports.
 *   - Knowledge Guides: synthetic mirror of /guides/index.html (categories + counts).
 *   - Dret europeu en catala: Catalan-only; mirror of /legislacio-ue-catala/.
 *   - Open datasets: the DCAT catalogue (brubru_dataset_catalog), which described
 *     every Brubru dataset to the outside world while no surface in the product
 *     read it. Each card is a dataset, each chip a callable distribution.
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
import { useEffect, useMemo, useRef, useState } from 'react';
import { ListSkeleton } from '../shared/skeleton';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { MeubHeader } from './meub_header';
import Icon from '@mdi/react';
import {
  mdiDatabaseOutline, mdiKeyOutline, mdiCheck,
  mdiBookshelf, mdiBookOpenPageVariantOutline, mdiFileDocumentMultipleOutline, mdiTranslate,
  mdiSitemapOutline, mdiRadar, mdiOpenInNew, mdiAccountGroupOutline,
  mdiDomain, mdiBankOutline, mdiArrowRight, mdiInformationOutline,
  mdiFormatListNumbered, mdiCalendarOutline, mdiDna, mdiFactory, mdiClockAlertOutline,
  mdiPill, mdiAccessPointNetwork, mdiShieldAlertOutline, mdiTerrain,
  mdiShieldOutline, mdiSwapHorizontal, mdiRobotOutline, mdiAtomVariant, mdiRocketLaunchOutline,
  mdiGold, mdiChartLine, mdiChevronDown, mdiChevronUp,
  mdiHistory, mdiPlusCircleOutline, mdiPencilOutline, mdiBookPlusOutline,
  mdiMagnify, mdiClose, mdiChevronRight, mdiCloseCircle, mdiDumbbell,
} from '@mdi/js';
import { createPortal } from 'react-dom';
import { marked } from 'marked';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell, PieChart, Pie,
} from 'recharts';
import { databasesService } from '../../services/databases_service';
import type {
  DatasetsResult,
  CanonResult, GuidesResult, CatalanResult, PolicyAreasResult, PolicyArea,
  BeresolMonitorsResult, BeresolMonitorDetail, KbChangelogResult, KbChangelogEntry,
  GuideListResult, GuideSummary, GuideDetail,
} from '../../services/databases_service';
import { DEEP_DIVES, getDeepDiveUrl, LANG_LABELS } from '../../utils/deep_dive_map';
import './databases_tab.css';

type Sub = 'canon' | 'deep' | 'guides' | 'catalan' | 'datasets' | 'policy' | 'partners';

const C = { primary: '#1e3a8a', accent: '#0693e3', pi: '#d97706', ep: '#be123c', ec: '#0693e3', council: '#9b51e0', muted: '#cbd5e1' };

// Map the deep-dive map's mdi-class strings to @mdi/js icon paths.
const DD_ICON: Record<string, string> = {
  'mdi-domain': mdiDomain, 'mdi-dna': mdiDna, 'mdi-factory': mdiFactory,
  'mdi-clock-alert-outline': mdiClockAlertOutline, 'mdi-pill': mdiPill,
  'mdi-access-point-network': mdiAccessPointNetwork, 'mdi-shield-alert-outline': mdiShieldAlertOutline,
  'mdi-mountain': mdiTerrain,
};

// (slugify removed: category tiles used it to build an anchor into the static
// guides/index.html. They now filter the in-page guide list instead.)

// Per-monitor icon (Beresol Monitors). Falls back to the radar glyph.
const MON_ICON: Record<string, string> = {
  defence: mdiShieldOutline, cmu: mdiBankOutline, tariff: mdiSwapHorizontal,
  ai: mdiRobotOutline, quantum: mdiAtomVariant, startup: mdiRocketLaunchOutline,
  gold: mdiGold, markets: mdiChartLine,
};

// A ninth card in the Beresol Monitors grid: Massimino's Fitness Intelligence.
// A sibling product, not a Beresol monitor, so it lives here rather than in the
// /beresol-monitors payload, which must keep mirroring the Beresol API exactly.
const EXTRA_MONITOR = {
  slug: 'massimino-fitness-intelligence',
  title: 'Fitness Intelligence',
  description:
    'European fitness industry data: gym penetration rates, market sizes and '
    + 'growth trends across Europe.',
  url: 'https://massimino.fitness/fitness-intelligence',
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

const SUBS: Sub[] = ['canon', 'deep', 'guides', 'catalan', 'datasets', 'policy', 'partners'];

export function DatabasesTab() {
  const { t, i18n } = useTranslation();
  const isCa = i18n.language?.startsWith('ca');
  const [searchParams, setSearchParams] = useSearchParams();

  // The library you are looking at belongs in the URL. Without this, the five
  // libraries were unreachable except by clicking, so none of them could be
  // linked to, bookmarked or shared: every link to "Brubru Databases" landed
  // on EU Canon. `?db=guides` now opens the Knowledge Guides library directly.
  const [sub, setSub] = useState<Sub>(() => {
    const raw = searchParams.get('db');
    return (raw && (SUBS as string[]).includes(raw)) ? raw as Sub : 'canon';
  });

  const selectSub = (next: Sub) => {
    setSub(next);
    const params = new URLSearchParams(searchParams);
    if (next === 'canon') params.delete('db'); else params.set('db', next);
    setSearchParams(params, { replace: true });
  };

  // Follow the URL when it changes underneath us (back button, a deep link
  // arriving while the tab is already open).
  useEffect(() => {
    const raw = searchParams.get('db');
    const next: Sub = (raw && (SUBS as string[]).includes(raw)) ? raw as Sub : 'canon';
    setSub((cur) => (cur === next ? cur : next));
  }, [searchParams]);
  const [canon, setCanon] = useState<CanonResult | null>(null);
  const [guides, setGuides] = useState<GuidesResult | null>(null);
  const [guideList, setGuideList] = useState<GuideListResult | null>(null);
  const [changelog, setChangelog] = useState<KbChangelogResult | null>(null);
  const [catalan, setCatalan] = useState<CatalanResult | null>(null);
  const [datasets, setDatasets] = useState<DatasetsResult | null>(null);
  const [pa, setPa] = useState<PolicyAreasResult | null>(null);
  const [paMine, setPaMine] = useState(true);
  const [selArea, setSelArea] = useState<string | null>(null);

  // If the user leaves Catalan while on the Catalan tab, fall back to EU Canon.
  useEffect(() => { if (!isCa && sub === 'catalan') selectSub('canon'); }, [isCa, sub]);

  // Lazy-load each library when its tab is first opened.
  useEffect(() => { if (sub === 'canon' && !canon) databasesService.canon().then(setCanon).catch(() => {}); }, [sub, canon]);
  useEffect(() => { if (sub === 'guides' && !guides) databasesService.guides().then(setGuides).catch(() => {}); }, [sub, guides]);
  useEffect(() => { if (sub === 'guides' && !changelog) databasesService.kbChangelog().then(setChangelog).catch(() => {}); }, [sub, changelog]);
  useEffect(() => { if (sub === 'guides' && !guideList) databasesService.guidesList().then(setGuideList).catch(() => {}); }, [sub, guideList]);
  useEffect(() => { if (sub === 'catalan' && !catalan) databasesService.catalan().then(setCatalan).catch(() => {}); }, [sub, catalan]);
  useEffect(() => { if (sub === 'datasets' && !datasets) databasesService.datasets().then(setDatasets).catch(() => {}); }, [sub, datasets]);
  useEffect(() => {
    if (sub !== 'policy') return;
    databasesService.policyAreas(paMine).then((r) => { setPa(r); setSelArea(r.areas[0]?.name || null); }).catch(() => {});
  }, [sub, paMine]);

  const tabs: [Sub, string, string][] = [
    ['canon', mdiBookOpenPageVariantOutline, t('db.tabCanon', 'EU Canon')],
    ['deep', mdiFileDocumentMultipleOutline, t('db.tabDeep', 'Deep Dives')],
    ['guides', mdiBookshelf, t('db.tabGuides', 'Knowledge Guides')],
    ...(isCa ? [['catalan', mdiTranslate, t('db.tabCatalan', 'Dret europeu en català')]] as [Sub, string, string][] : []),
    ['datasets', mdiDatabaseOutline, t('db.tabDatasets', 'Open datasets')],
    ['policy', mdiSitemapOutline, t('db.tabPolicy', 'Policy Areas')],
    ['partners', mdiRadar, t('db.tabPartners', 'Beresol Monitors')],
  ];

  return (
    <div className="db-tab">
      <MeubHeader
        icon={mdiBookshelf}
        title={t('bubble.databases', 'Brubru Databases')}
        subtitle={t('db.subtitle', 'Brubru’s knowledge libraries and a map of who does what across the EU, tailored to your interests.')}
      />

      <div className="db-subtabs" role="tablist">
        {tabs.map(([id, icon, label]) => (
          <button key={id} role="tab" aria-selected={sub === id} className={sub === id ? 'is-active' : ''} onClick={() => selectSub(id)}>
            <Icon path={icon} size={0.7} /> {label}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div key={sub} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
          {sub === 'canon' && <CanonLibrary data={canon} t={t} lang={i18n.language} />}
          {sub === 'deep' && <DeepDives t={t} lang={i18n.language} />}
          {sub === 'guides' && <KnowledgeGuides data={guides} list={guideList} changelog={changelog} t={t} />}
          {sub === 'catalan' && <CatalanLibrary data={catalan} t={t} />}
          {sub === 'datasets' && <OpenDatasets data={datasets} t={t} />}
          {sub === 'policy' && <PolicyAreas pa={pa} mine={paMine} setMine={setPaMine} sel={selArea} setSel={setSelArea} t={t} />}
          {sub === 'partners' && <BeresolMonitors t={t} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}


// ISO 8601 durations, as they appear in brubru_dataset_catalog today.
const PERIODICITY: Record<string, [string, string]> = {
  P1D: ['db.periodDaily', 'updated daily'],
  P1W: ['db.periodWeekly', 'updated weekly'],
  P1M: ['db.periodMonthly', 'updated monthly'],
};

// ------------------------------------------------------------- Open datasets
// brubru_dataset_catalog held DCAT metadata for the outside world while nothing
// in the product read it, so a user could not see what Brubru publishes. Each
// card is a dataset; each chip under it is a distribution you can actually open.
function OpenDatasets({ data, t }: { data: DatasetsResult | null; t: any }) {
  const [copied, setCopied] = useState<string | null>(null);
  const copyEndpoint = (url: string) => {
    navigator.clipboard?.writeText(url).then(
      () => { setCopied(url); window.setTimeout(() => setCopied(null), 1800); },
      () => {},
    );
  };
  if (!data) return <ListSkeleton count={5} lines={3} />;
  return (
    <div className="db-section">
      <LibHero
        icon={mdiDatabaseOutline}
        title={t('db.datasetsTitle', 'Open datasets')}
        subtitle={t('db.datasetsDesc', 'Everything Brubru publishes as open data: the corpora behind the product, each with the endpoints you can call.')}
        kpis={[
          { value: data.count, label: t('db.datasetsKpi', 'datasets') },
          { value: data.datasets.reduce((n, d) => n + d.distributions.length, 0),
            label: t('db.datasetsKpiDist', 'distributions') },
        ]}
      />
      {data.datasets.some((d) => d.distributions.some((x) => x.requires_api_key)) && (
        <p className="db-dataset-keynote">
          {t('db.datasetsKeyNote',
             'Endpoints marked with a key need a Brubru API key. Click one to copy it, then call it from your own client.')}
          {' '}
          <a href="/api" target="_blank" rel="noopener noreferrer">
            {t('db.datasetsGetKey', 'Get an API key')}
          </a>
        </p>
      )}
      <div className="db-canon-grid">
        {data.datasets.map((d, i) => (
          <motion.div key={d.uri} className="db-canon-card"
            custom={i} variants={cardVariants} initial="hidden" animate="show"
            whileHover={{ y: -4, boxShadow: '0 12px 28px rgba(15,23,42,0.12)' }}>
            <h4>{d.title}</h4>
            <p className="db-dataset-card__desc">{d.description}</p>
            <div className="db-dataset-card__dists">
              {d.distributions.length === 0 && (
                <span className="db-dataset-card__nodist">
                  {t('db.datasetsNoDist', 'No public download yet')}
                </span>
              )}
              {/* A key-gated endpoint is not a link. Clicking one used to show a
                  raw 401 JSON blob, and putting the caller's key in the href
                  would leak it into history and logs, so these copy the URL for
                  use in an API client instead. */}
              {d.distributions.map((dist) => (dist.requires_api_key ? (
                <button key={dist.url} type="button" className="db-dataset-card__dist is-key"
                        title={`${dist.title} \u2014 ${dist.url}`}
                        onClick={() => copyEndpoint(dist.url)}>
                  <Icon path={copied === dist.url ? mdiCheck : mdiKeyOutline} size={0.5} />
                  {copied === dist.url ? t('db.datasetsCopied', 'copied') : dist.format}
                </button>
              ) : (
                <a key={dist.url} href={dist.url} target="_blank" rel="noopener noreferrer"
                   className="db-dataset-card__dist" title={dist.title}>
                  <Icon path={mdiOpenInNew} size={0.5} /> {dist.format}
                </a>
              )))}
            </div>
            <span className="db-canon-card__celex">
              {d.themes.length} {t('db.datasetsThemes', 'EuroVoc themes')}
              {/* accrual_periodicity is an ISO 8601 duration: correct in DCAT,
                  unreadable on a card. P1D is "daily", not a serial number. */}
              {PERIODICITY[d.updated] ? ` · ${t(PERIODICITY[d.updated][0], PERIODICITY[d.updated][1])}` : ''}
            </span>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

// -------------------------------------------------------------- EU Canon
function CanonLibrary({ data, t, lang }: { data: CanonResult | null; t: any; lang: string }) {
  if (!data) return <ListSkeleton count={6} lines={3} />;
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
const CHANGELOG_ACTION_META: Record<string, { icon: string; color: string; label: string }> = {
  added:     { icon: mdiBookPlusOutline,    color: '#16a34a', label: 'New guide' },
  updated:   { icon: mdiPencilOutline,      color: '#0693e3', label: 'Updated' },
  canon:     { icon: mdiPlusCircleOutline,  color: '#7c3aed', label: 'Canon' },
  deep_dive: { icon: mdiPlusCircleOutline,  color: '#db2777', label: 'Deep dive' },
};

/**
 * `knownSlugs` is what makes an entry openable. Every entry names a guide in
 * `entry.guide`, but the feed also carries `canon` and `deep_dive` items whose
 * slug is not a guide file. Only entries whose slug resolves to a real guide
 * become buttons; the rest stay plain text rather than pretending to lead
 * somewhere.
 */
function WhatsNew({ entries, knownSlugs, onOpen, t }: {
  entries: KbChangelogEntry[];
  knownSlugs: Set<string>;
  onOpen: (slug: string) => void;
  t: any;
}) {
  if (!entries || entries.length === 0) return null;
  return (
    <div className="db-whatsnew">
      <div className="db-whatsnew__head">
        <span className="mdi" aria-hidden="true">
          <Icon path={mdiHistory} size={0.8} />
        </span>
        <h4>{t('db.whatsNew', "What's new in the knowledge base")}</h4>
      </div>
      <ol className="db-whatsnew__list">
        {entries.map((e, i) => {
          const meta = CHANGELOG_ACTION_META[e.action] || CHANGELOG_ACTION_META.updated;
          const openable = knownSlugs.has(e.guide);
          const body = (
            <>
              <span className="db-whatsnew__badge" style={{ background: meta.color }}>
                <Icon path={meta.icon} size={0.62} />
              </span>
              <div className="db-whatsnew__body">
                <div className="db-whatsnew__line1">
                  <strong>{e.title}</strong>
                  <span className="db-whatsnew__tag" style={{ color: meta.color, borderColor: meta.color }}>
                    {t(`db.action.${e.action}`, meta.label)}
                  </span>
                  <time className="db-whatsnew__date">{e.date}</time>
                </div>
                <p className="db-whatsnew__summary">{e.summary}</p>
              </div>
              {openable && (
                <Icon path={mdiChevronRight} size={0.8} className="db-whatsnew__go" />
              )}
            </>
          );
          return (
            <motion.li key={`${e.date}-${e.guide}-${i}`}
              className={`db-whatsnew__item${openable ? ' db-whatsnew__item--clickable' : ''}`}
              custom={i} variants={cardVariants} initial="hidden" animate="show">
              {openable ? (
                <button type="button" className="db-whatsnew__hit" onClick={() => onOpen(e.guide)}>
                  {body}
                </button>
              ) : body}
            </motion.li>
          );
        })}
      </ol>
    </div>
  );
}

/**
 * Reader for one guide.
 *
 * Guides are authored as markdown. Handing a reader a .md file, or bouncing
 * them to a static index, is not reading — so the markdown is rendered to HTML
 * here and shown in place. `marked` runs with `gfm` for tables and with raw
 * HTML passthrough left off: the guides are first-party markdown and have no
 * reason to inject markup.
 *
 * Portalled to document.body: the MEUB shell is an AnimatedPage whose
 * transform would otherwise become the containing block for a fixed overlay.
 */
/**
 * Guides cross-reference each other in a "Related Brubru guides" section, as
 * bullets naming a file: "`ecodesign_digital_product_passport.md`: the ESPR
 * and the Digital Product Passport". Rendered literally that is a dead end —
 * a file name the reader cannot open and would not recognise.
 *
 * Each reference is rewritten to a link carrying the slug, labelled with the
 * guide's real title where we know it. References to guides that do not exist
 * (the corpus has a couple) are left as plain text: no link that goes nowhere.
 */
const RELATED_SECTION = /(##+\s*Related Brubru guides\s*\n)([\s\S]*?)(?=\n##|\s*$)/i;
const RELATED_LINE = /^(\s*[-*]\s*)`?([a-z0-9_]+?)(?:\.md)?`?\s*:\s*(.*)$/;

function linkRelatedGuides(markdown: string, titles: Map<string, string>): string {
  return markdown.replace(RELATED_SECTION, (_all, heading: string, body: string) => {
    const rewritten = body.split('\n').map((line) => {
      const m = line.match(RELATED_LINE);
      if (!m) return line;
      const [, bullet, slug, rest] = m;
      const title = titles.get(slug);
      if (!title) return `${bullet}${rest}`;   // no such guide: keep the prose, drop the file name
      return `${bullet}[${title}](#guide:${slug}): ${rest}`;
    }).join('\n');
    return heading + rewritten;
  });
}

function GuideReader({ guide, loading, titles, onOpenGuide, onClose, t }: {
  guide: GuideDetail | null;
  loading: boolean;
  titles: Map<string, string>;
  onOpenGuide: (slug: string) => void;
  onClose: () => void;
  t: any;
}) {
  const bodyRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onEsc);
    return () => document.removeEventListener('keydown', onEsc);
  }, [onClose]);

  // Opening a related guide swaps the content in place, so send the reader
  // back to the top rather than leaving them mid-way down the previous one.
  useEffect(() => { bodyRef.current?.scrollTo({ top: 0 }); }, [guide?.slug]);

  const html = useMemo(() => {
    if (!guide?.markdown) return '';
    try {
      const md = linkRelatedGuides(guide.markdown, titles);
      return marked.parse(md, { gfm: true, breaks: false, async: false }) as string;
    } catch {
      return '';
    }
  }, [guide?.markdown, titles]);

  // Delegated: the markdown is injected as HTML, so the cross-reference links
  // have no React handlers of their own.
  const onBodyClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const anchor = (e.target as HTMLElement).closest('a');
    const href = anchor?.getAttribute('href') || '';
    if (!href.startsWith('#guide:')) return;
    e.preventDefault();
    onOpenGuide(href.slice('#guide:'.length));
  };

  return createPortal(
    <div className="db-reader" role="dialog" aria-modal="true" aria-label={guide?.title || 'Guide'}>
      <div className="db-reader__overlay" onClick={onClose} />
      <div className="db-reader__panel">
        <header className="db-reader__head">
          <div className="db-reader__headtext">
            <h3>{guide?.title || t('db.loading', 'Loading...')}</h3>
            {guide && (
              <p className="db-reader__meta">
                <span>{guide.category}</span>
                {guide.updated && <span>{t('db.updatedOn', 'updated')} {guide.updated}</span>}
                {guide.procedure_ref && <span>{guide.procedure_ref}</span>}
              </p>
            )}
          </div>
          <button type="button" className="db-reader__close" onClick={onClose}
            aria-label={t('common.close', 'Close')}>
            <Icon path={mdiClose} size={1} />
          </button>
        </header>
        <div className="db-reader__body" ref={bodyRef} onClick={onBodyClick}>
          {loading || !guide
            ? <div className="db-loading">{t('db.loading', 'Loading...')}</div>
            /* First-party markdown rendered by marked; no user input reaches this. */
            : <article className="db-reader__md" dangerouslySetInnerHTML={{ __html: html }} />}
        </div>
      </div>
    </div>,
    document.body,
  );
}

function KnowledgeGuides({ data, list, changelog, t }: {
  data: GuidesResult | null;
  list: GuideListResult | null;
  changelog: KbChangelogResult | null;
  t: any;
}) {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState<string | null>(null);
  const [openSlug, setOpenSlug] = useState<string | null>(null);
  const [detail, setDetail] = useState<GuideDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    if (!openSlug) { setDetail(null); return; }
    setDetailLoading(true);
    databasesService.guideDetail(openSlug)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  }, [openSlug]);

  // Filtering happens client-side: the whole list is one small payload, so a
  // keystroke should not cost a round trip.
  const guides: GuideSummary[] = list?.guides || [];
  const knownSlugs = useMemo(() => new Set(guides.map((g) => g.slug)), [guides]);
  // slug -> real title, so a cross-reference reads as the guide's name rather
  // than its file name.
  const titlesBySlug = useMemo(
    () => new Map(guides.map((g) => [g.slug, g.title])),
    [guides],
  );
  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return guides.filter((g) => {
      if (category && g.category !== category) return false;
      if (!needle) return true;
      return g.title.toLowerCase().includes(needle)
        || g.summary.toLowerCase().includes(needle)
        || (g.procedure_ref || '').toLowerCase().includes(needle);
    });
  }, [guides, query, category]);

  if (!data) return <ListSkeleton count={6} lines={3} />;

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
      {changelog && (
        <WhatsNew
          entries={changelog.entries}
          knownSlugs={knownSlugs}
          onOpen={setOpenSlug}
          t={t}
        />
      )}

      {/* Category tiles now filter the list below instead of sending the
          reader off to a static page they have to come back from. */}
      <div className="db-guide-grid">
        {data.categories.map((cat, i) => {
          const active = category === cat.title;
          return (
            <motion.button key={cat.title} type="button"
              className={`db-guide-card${active ? ' db-guide-card--active' : ''}`}
              onClick={() => setCategory(active ? null : cat.title)}
              aria-pressed={active}
              custom={i} variants={cardVariants} initial="hidden" animate="show"
              whileHover={{ y: -4, boxShadow: '0 10px 24px rgba(15,23,42,0.10)' }}>
              <span className="db-guide-card__icon" style={{ background: cat.color }}>
                <span className={`mdi ${cat.icon}`} aria-hidden="true" />
              </span>
              <div className="db-guide-card__body">
                <h4>{cat.title}</h4>
                <span className="db-guide-card__count" style={{ color: cat.color }}>
                  <CountUp to={cat.count} /> {cat.count === 1 ? t('db.guideOne', 'guide') : t('db.guidesKpi', 'guides')}
                </span>
              </div>
            </motion.button>
          );
        })}
      </div>

      {/* The library itself: every guide, searchable and openable. */}
      <div className="db-guidelist">
        <div className="db-guidelist__bar">
          <div className="db-guidelist__search">
            <Icon path={mdiMagnify} size={0.8} />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('db.searchGuides', 'Search guides by title, topic or procedure...') as string}
              aria-label={t('db.searchGuides', 'Search guides by title, topic or procedure...') as string}
            />
          </div>
          {(category || query) && (
            <button type="button" className="db-guidelist__clear"
              onClick={() => { setCategory(null); setQuery(''); }}>
              <Icon path={mdiCloseCircle} size={0.7} />
              {t('db.clearFilters', 'Clear')}
            </button>
          )}
          <span className="db-guidelist__count">
            {shown.length} {shown.length === 1 ? t('db.guideOne', 'guide') : t('db.guidesKpi', 'guides')}
            {category ? ` · ${category}` : ''}
          </span>
        </div>

        {!list ? (
          <div className="db-loading">{t('db.loading', 'Loading...')}</div>
        ) : shown.length === 0 ? (
          /* Search and category combine, so picking a category with 93 guides
             while a stale search is active shows nothing. Say which filters are
             responsible and offer to drop them, rather than an unexplained
             empty list. */
          <div className="db-guidelist__empty">
            <p>
              {query && category
                ? t('db.noGuidesBoth', {
                    query, category,
                    defaultValue: 'No guide in {{category}} matches "{{query}}".',
                  })
                : query
                  ? t('db.noGuidesQuery', { query, defaultValue: 'No guide matches "{{query}}".' })
                  : t('db.noGuidesCategory', { category, defaultValue: 'No guide in {{category}} yet.' })}
            </p>
            <button type="button" className="db-guidelist__clear" onClick={() => { setCategory(null); setQuery(''); }}>
              <Icon path={mdiCloseCircle} size={0.7} />
              {t('db.showAllGuides', 'Show all guides')}
            </button>
          </div>
        ) : (
          <ul className="db-guidelist__items">
            {shown.map((g) => (
              <li key={g.slug}>
                <button type="button" className="db-guideitem" onClick={() => setOpenSlug(g.slug)}>
                  <span className="db-guideitem__body">
                    <span className="db-guideitem__title">{g.title}</span>
                    {g.summary && <span className="db-guideitem__summary">{g.summary}</span>}
                    <span className="db-guideitem__meta">
                      <span className="db-guideitem__pill">{g.category}</span>
                      {g.procedure_ref && <span className="db-guideitem__pill">{g.procedure_ref}</span>}
                      {g.updated && <span className="db-guideitem__when">{g.updated}</span>}
                    </span>
                  </span>
                  <Icon path={mdiChevronRight} size={0.8} className="db-guideitem__go" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {openSlug && (
        <GuideReader
          guide={detail}
          loading={detailLoading}
          titles={titlesBySlug}
          onOpenGuide={setOpenSlug}
          onClose={() => setOpenSlug(null)}
          t={t}
        />
      )}
    </div>
  );
}

// -------------------------------------------------------------- Dret europeu en català
function CatalanLibrary({ data, t }: { data: CatalanResult | null; t: any }) {
  if (!data) return <ListSkeleton count={6} lines={3} />;
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
        /* +1: the grid shows the Beresol monitors plus the Fitness Intelligence card. */
        kpis={[{ value: (res.count || res.monitors.length) + 1, label: t('db.beresolKpi', 'live monitors') }]}
        cta={{ label: t('db.openBeresol', 'Open Beresol'), url: res.source_url || 'https://beresol.eu' }}
      />
      <div className="db-monitor-grid">
        {/* Massimino's Fitness Intelligence sits alongside the Beresol monitors
            as a ninth card. It is a sibling product rather than a Beresol
            monitor, so it is added here and not to /beresol-monitors, which
            mirrors the Beresol API and should keep reporting exactly what that
            API returns. It has no in-app digest, so the card opens the
            dashboard directly and says so. */}
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

        <motion.a
          key={EXTRA_MONITOR.slug}
          className="db-monitor-card"
          href={EXTRA_MONITOR.url}
          target="_blank"
          rel="noopener noreferrer"
          custom={res.monitors.length}
          variants={cardVariants}
          initial="hidden"
          animate="show"
          whileHover={{ y: -4, boxShadow: '0 12px 28px rgba(15,23,42,0.12)' }}
        >
          <span className="db-monitor-card__icon"><Icon path={mdiDumbbell} size={0.95} /></span>
          <h4>{t('db.monitorFitnessTitle', EXTRA_MONITOR.title)}</h4>
          <p>{t('db.monitorFitnessDesc', EXTRA_MONITOR.description)}</p>
          <span className="db-monitor-card__more">
            {t('db.openDashboard', 'Open dashboard')}
            <Icon path={mdiOpenInNew} size={0.6} />
          </span>
        </motion.a>
      </div>

      <AnimatePresence mode="wait">
        {sel && (
          <motion.div key={sel} className="db-monitor-detail" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
            {loadingDetail && <ListSkeleton count={4} />}
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
