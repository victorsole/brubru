/**
 * My OJ Tab — the day's Official Journal entries, filterable by interests.
 *
 * A date selector + "day at a glance" facets, then act cards grouped by
 * category (Regulations / Decisions / Directives / Information & notices). PI
 * lens (My interests | All, title-keyword match) shared with the rest of MEUB.
 * Acts that are the adopted form of a tracked dossier carry a "Tracked" badge
 * deep-linking to My Tracked Files.
 *
 * Data: /api/oj/{dates,entries,my-keywords}
 */

import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import { MeubHeader } from './meub_header';
import {
  mdiNewspaperVariantOutline, mdiStar, mdiOpenInNew,
  mdiMagnify, mdiBookmarkCheck, mdiCalendarBlankOutline, mdiScaleBalance, mdiBullhornOutline,
  mdiInformationOutline, mdiCreation, mdiTagOutline, mdiClose, mdiTranslate,
} from '@mdi/js';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import './oj_tab.css';
import { LensToggle, type LensMode } from './lens_toggle';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api`;

interface OjEntry {
  id: string;
  oj_date: string;
  series: 'L' | 'C';
  oj_number: string;
  oj_id: string | null;
  celex: string | null;
  title: string;
  act_type: string | null;
  category: string | null;
  institution: string | null;
  eurlex_url: string | null;
  plain_explanation: string | null;
  translated_from?: string | null;
  catalan_url?: string | null;
  change_kind: string | null;
  theme: string | null;
  carriage_id: string | null;
  matched_procedure_ref: string | null;
  is_tracked: boolean;
  matches_interests: boolean;
  matches_tracked?: boolean;
}
interface Facets { series: Record<string, number>; act_type: Record<string, number>; institution: Record<string, number>; theme: Record<string, number>; total: number; }
interface EntriesResponse {
  date: string | null; items: OjEntry[]; total: number; pi_active: boolean;
  tracked_count: number; interest_count: number; facets: Facets;
  has_tracked_files?: boolean; files_active?: boolean;
}

const authCfg = () => {
  const token = useAuth.getState().token;
  return token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;
};

const fmtDate = (iso: string, locale?: string) => {
  try {
    return new Date(iso + 'T00:00:00').toLocaleDateString(locale || undefined,
      { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
  } catch { return iso; }
};

// Category display order.
const CAT_ORDER = ['Regulations', 'Directives', 'Decisions', 'Other acts', 'Information and notices'];

// "What it changes" tag colours.
const CHANGE_COLORS: Record<string, string> = {
  new: '#1f7a4d', amends: '#2563c9', renews: '#7a5b1f',
  repeals: '#c0392b', extends: '#6c3a86', suspends: '#a8730a', corrects: '#5b6472',
};

export const OJTab = () => {
  const { t, i18n } = useTranslation();
  const uiLang = (i18n.language || 'en').split('-')[0];
  const [dates, setDates] = useState<{ date: string; count: number }[]>([]);
  const [activeDate, setActiveDate] = useState<string>('');
  const [series, setSeries] = useState<'' | 'L' | 'C'>('');
  const [mode, setMode] = useState<LensMode>('all');
  const [institution, setInstitution] = useState('');
  const [theme, setTheme] = useState('');
  const [search, setSearch] = useState('');
  const [legendOpen, setLegendOpen] = useState(false);
  // On-demand "Explain with AI" state, per entry id. `failed` keeps the button
  // visible so the user can retry — a single transient miss should not look
  // permanent.
  const [explained, setExplained] = useState<Record<string, { loading?: boolean; text?: string; failed?: boolean }>>({});

  const explain = async (id: string) => {
    setExplained((s) => ({ ...s, [id]: { loading: true } }));
    try {
      const r = await axios.post<{ explanation: string | null; available: boolean }>(
        `${API_BASE}/oj/explain/${id}`, {}, authCfg());
      setExplained((s) => ({ ...s, [id]: r.data.available && r.data.explanation
        ? { text: r.data.explanation } : { failed: true } }));
    } catch {
      setExplained((s) => ({ ...s, [id]: { failed: true } }));
    }
  };
  const [data, setData] = useState<EntriesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [hasPi, setHasPi] = useState(false);

  useEffect(() => {
    axios.get<{ dates: { date: string; count: number }[] }>(`${API_BASE}/oj/dates`)
      .then((r) => {
        setDates(r.data.dates || []);
        if (r.data.dates?.length) setActiveDate(r.data.dates[0].date);
      }).catch(() => { });
    axios.get<{ keywords: string[] }>(`${API_BASE}/oj/my-keywords`, authCfg())
      .then((r) => setHasPi((r.data.keywords || []).length > 0)).catch(() => { });
  }, []);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (activeDate) params.set('date', activeDate);
    if (series) params.set('series', series);
    if (mode === 'pi') params.set('my_interests', 'true');
    if (mode === 'files') params.set('my_files', 'true');
    if (institution) params.set('institution', institution);
    if (theme) params.set('theme', theme);
    if (search.trim()) params.set('search', search.trim());
    if (uiLang !== 'en') params.set('lang', uiLang);
    axios.get<EntriesResponse>(`${API_BASE}/oj/entries?${params.toString()}`, authCfg())
      .then((r) => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [activeDate, series, mode, institution, theme, search, uiLang]);

  const grouped = useMemo(() => {
    const items = data?.items || [];
    const m: Record<string, OjEntry[]> = {};
    for (const e of items) {
      const c = e.category || 'Other acts';
      (m[c] ||= []).push(e);
    }
    return Object.entries(m).sort(
      (a, b) => (CAT_ORDER.indexOf(a[0]) + 99 * (CAT_ORDER.indexOf(a[0]) < 0 ? 1 : 0))
              - (CAT_ORDER.indexOf(b[0]) + 99 * (CAT_ORDER.indexOf(b[0]) < 0 ? 1 : 0)));
  }, [data]);

  const facets = data?.facets;

  return (
    <div className="oj-tab">
      <MeubHeader
        icon={mdiNewspaperVariantOutline}
        title={(
          <>
            {t('oj.title', 'My OJ')}
            <button className="oj-legendbtn" onClick={() => setLegendOpen((v) => !v)}
              aria-label={t('oj.whatIsThis', 'What do these codes mean?') as string}>
              <Icon path={mdiInformationOutline} size={0.85} />
            </button>
          </>
        )}
        subtitle={t('oj.intro', 'The day’s Official Journal of the EU, filtered to your interests and linked to the files you track.')}
        aside={dates.length > 0 && (
          <label className="oj-datepick">
            <Icon path={mdiCalendarBlankOutline} size={0.8} />
            <select value={activeDate} onChange={(e) => setActiveDate(e.target.value)}>
              {dates.map((d) => (
                <option key={d.date} value={d.date}>{fmtDate(d.date, uiLang)} ({d.count})</option>
              ))}
            </select>
          </label>
        )}
      />

      {legendOpen && (
        <div className="oj-legend">
          <button className="oj-legend__close" onClick={() => setLegendOpen(false)} aria-label={t('common.close', 'Close')}>
            <Icon path={mdiClose} size={0.8} />
          </button>
          <h3>{t('oj.legend.title', 'How to read the Official Journal')}</h3>
          <p><b>{t('oj.legend.lTitle', 'OJ L (Legislation)')}</b>: {t('oj.legend.lBody', 'binding law (regulations, directives, decisions).')}</p>
          <p><b>{t('oj.legend.cTitle', 'OJ C (Information and notices)')}</b>: {t('oj.legend.cBody', 'non-binding material (communications, calls, State-aid and court notices).')}</p>
          <p><b>{t('oj.legend.bothTitle', 'L + C')}</b>: {t('oj.legend.bothBody', 'both series together: everything published that day.')}</p>
          <p className="oj-legend__celex">
            <b>{t('oj.legend.celexTitle', 'Codes like 32026R1146')}</b>: {t('oj.legend.celexBody', 'this is the CELEX number, the act’s unique ID. Read it as:')}
          </p>
          <ul className="oj-legend__celexparts">
            <li><span>3</span> {t('oj.legend.celex3', 'sector: legislation')}</li>
            <li><span>2026</span> {t('oj.legend.celexYear', 'year')}</li>
            <li><span>R</span> {t('oj.legend.celexType', 'type: R = Regulation, L = Directive, D = Decision')}</li>
            <li><span>1146</span> {t('oj.legend.celexNum', 'sequential number')}</li>
          </ul>
        </div>
      )}

      {facets && (
        <div className="oj-glance">
          <div className="oj-stat"><b>{facets.total}</b><span>{t('oj.acts', 'acts')}</span></div>
          <div className="oj-stat is-l"><b>{facets.series.L || 0}</b><span>{t('oj.lSeries', 'L (law)')}</span></div>
          <div className="oj-stat is-c"><b>{facets.series.C || 0}</b><span>{t('oj.cSeries', 'C (notices)')}</span></div>
          {data && data.tracked_count > 0 && (
            <div className="oj-stat is-tracked"><b>{data.tracked_count}</b><span>{t('oj.tracked', 'tracked')}</span></div>
          )}
          {hasPi && data && (
            <div className="oj-stat is-pi"><b>{data.interest_count}</b><span>{t('oj.yours', 'in your interests')}</span></div>
          )}
        </div>
      )}

      <div className="oj-controls">
        <LensToggle mode={mode} onChange={setMode} hasPi={hasPi} hasFiles={!!data?.has_tracked_files} />
        <div className="oj-segmented">
          <button className={series === '' ? 'is-active' : ''} onClick={() => setSeries('')}>{t('oj.bothSeries', 'L + C')}</button>
          <button className={series === 'L' ? 'is-active' : ''} onClick={() => setSeries('L')}>L</button>
          <button className={series === 'C' ? 'is-active' : ''} onClick={() => setSeries('C')}>C</button>
        </div>
        {facets && (
          <select className="oj-sort" value={institution} onChange={(e) => setInstitution(e.target.value)}>
            <option value="">{t('oj.allInstitutions', 'All institutions')}</option>
            {Object.keys(facets.institution).map((i) => <option key={i} value={i}>{t(`oj.institutionName.${i}`, i)}</option>)}
          </select>
        )}
        <div className="oj-search">
          <Icon path={mdiMagnify} size={0.8} />
          <input value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder={t('oj.searchPlaceholder', 'Search the day’s acts') as string} />
        </div>
      </div>

      {facets && Object.keys(facets.theme).filter((k) => k !== 'Other').length > 0 && (
        <div className="oj-themes">
          <span className="oj-themes__label"><Icon path={mdiTagOutline} size={0.7} /> {t('oj.themes', 'Themes')}:</span>
          {Object.entries(facets.theme).filter(([k]) => k !== 'Other').map(([th, n]) => (
            <button key={th} className={`oj-themechip ${theme === th ? 'is-active' : ''}`}
              onClick={() => setTheme(theme === th ? '' : th)}>
              {t(`oj.themeName.${th}`, th)} <span>{n}</span>
            </button>
          ))}
          {theme && (
            <button className="oj-themechip is-clear" onClick={() => setTheme('')}>
              <Icon path={mdiClose} size={0.55} /> {t('oj.clear', 'Clear')}
            </button>
          )}
        </div>
      )}

      {loading ? (
        <p className="oj-muted oj-empty">{t('common.loading', 'Loading…')}</p>
      ) : !data || data.items.length === 0 ? (
        <div className="oj-empty">
          <Icon path={mdiNewspaperVariantOutline} size={2} />
          <p>{mode === 'pi'
            ? t('oj.emptyPi', 'No acts in your interests were published on this day.')
            : mode === 'files'
            ? t('oj.emptyFiles', 'No acts touching the files you track on this day.')
            : t('oj.empty', 'No Official Journal acts for this day.')}</p>
        </div>
      ) : (
        grouped.map(([cat, entries]) => (
          <section key={cat} className="oj-group">
            <h2 className="oj-group__title">
              {t(`oj.categoryName.${cat}`, cat)} <span className="oj-muted">({entries.length})</span>
            </h2>
            <div className="oj-list">
              {entries.map((e) => (
                <article key={e.id} className={`oj-card ${e.matches_interests ? 'is-pi' : ''} ${e.series === 'L' ? 'is-l' : 'is-c'}`}>
                  <div className="oj-card__num">
                    <span className={`oj-seriestag is-${e.series.toLowerCase()}`}>{e.series}</span>
                    {e.oj_number}
                    {e.change_kind && (
                      <span className="oj-changetag" style={{ color: CHANGE_COLORS[e.change_kind] || '#5b6472' }}>
                        {t(`oj.change.${e.change_kind}`, e.change_kind)}
                      </span>
                    )}
                  </div>
                  <div className="oj-card__main">
                    {/* Lead with the plain-language gloss when available (cached or
                        just generated) — the jargon-busting view. Otherwise show the
                        official title + an "Explain with AI" button. */}
                    {(e.plain_explanation || explained[e.id]?.text) ? (
                      <>
                        <p className="oj-card__plain">
                          <Icon path={mdiCreation} size={0.6} className="oj-card__plainicon" />
                          {e.plain_explanation || explained[e.id]?.text}
                        </p>
                        <a className="oj-card__official" href={e.eurlex_url || '#'} target="_blank" rel="noopener noreferrer">
                          {e.title} <Icon path={mdiOpenInNew} size={0.5} />
                        </a>
                      </>
                    ) : (
                      <>
                        <a className="oj-card__title" href={e.eurlex_url || '#'} target="_blank" rel="noopener noreferrer">
                          {e.title} <Icon path={mdiOpenInNew} size={0.55} />
                        </a>
                        <div className="oj-card__ai">
                          {explained[e.id]?.loading ? (
                            <span className="oj-ai-loading"><Icon path={mdiCreation} size={0.6} /> {t('oj.explaining', 'Explaining…')}</span>
                          ) : explained[e.id]?.failed ? (
                            <button className="oj-ai-btn is-retry" onClick={() => explain(e.id)}>
                              <Icon path={mdiCreation} size={0.6} /> {t('oj.explainRetry', 'Explanation failed, try again')}
                            </button>
                          ) : (
                            <button className="oj-ai-btn" onClick={() => explain(e.id)}>
                              <Icon path={mdiCreation} size={0.6} /> {t('oj.explainAi', 'Explain with AI')}
                            </button>
                          )}
                        </div>
                      </>
                    )}
                    <div className="oj-card__meta">
                      {e.theme && e.theme !== 'Other' && (
                        <span className="oj-chip is-theme"><Icon path={mdiTagOutline} size={0.5} /> {t(`oj.themeName.${e.theme}`, e.theme)}</span>
                      )}
                      {e.act_type && (
                        <span className="oj-chip"><Icon path={mdiScaleBalance} size={0.5} /> {t(`oj.actTypeName.${e.act_type}`, e.act_type)}</span>
                      )}
                      {e.institution && <span className="oj-chip is-muted">{t(`oj.institutionName.${e.institution}`, e.institution)}</span>}
                      {e.celex && (
                        <span className="oj-chip is-muted" title={t('oj.celexTip', 'CELEX number: the act’s unique EUR-Lex ID') as string}>
                          {e.celex}
                        </span>
                      )}
                      {uiLang === 'ca' && e.catalan_url && (
                        <a className="oj-chip is-catalan" href={e.catalan_url} target="_blank" rel="noopener noreferrer">
                          <Icon path={mdiTranslate} size={0.5} /> {t('oj.readInCatalan', 'Llegeix l’acte en català')}
                        </a>
                      )}
                      {e.matches_interests && (
                        <span className="oj-chip is-pi"><Icon path={mdiStar} size={0.5} /> {t('oj.mine', 'My interests')}</span>
                      )}
                      {e.is_tracked && (
                        <a className="oj-chip is-tracked" href={`/my-eu-bubble?tab=my_files&file=${e.carriage_id}`}>
                          <Icon path={mdiBookmarkCheck} size={0.5} /> {t('oj.trackedFile', 'Tracked file')}
                        </a>
                      )}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))
      )}

      {data?.date && (
        <p className="oj-foot oj-muted">
          <Icon path={mdiBullhornOutline} size={0.6} /> {t('oj.sourceNote', 'Source: EUR-Lex Official Journal daily view')} {' · '} {fmtDate(data.date, uiLang)}
        </p>
      )}
    </div>
  );
};
