/**
 * News Tab — EU institutional news, PI-filtered, image-rich (MEUB Section 3).
 *
 * A featured hero (big image + 2 secondaries) over a card feed of every
 * Commission/DG/agency news item, sorted newest-first. Cards are image-led with
 * a per-DG colour accent. PI lens ("My interests | All") + Institution/DG/type
 * filters, shared with the rest of MEUB.
 *
 * Data: /api/eu-news/{items,my-keywords}
 */

import { useEffect, useMemo, useState } from 'react';
import { ListSkeleton } from '../shared/skeleton';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import { MeubHeader } from './meub_header';
import {
  mdiNewspaperVariantMultipleOutline, mdiStar, mdiStarOutline, mdiOpenInNew,
  mdiBookmarkCheck, mdiBookmarkCheckOutline,
  mdiMagnify, mdiImageOutline,
  mdiBankOutline, mdiAccountTieVoiceOutline, mdiTranslate, mdiAlertCircleOutline,
} from '@mdi/js';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import './news_tab.css';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api`;

// Per-DG accent colours (close to each DG's domain). Fallback for the rest.
const DG_COLORS: Record<string, string> = {
  AGRI: '#6a8c2f', MARE: '#0d6e8c', SANTE: '#c0392b', ENV: '#2e8b57', CLIMA: '#16a34a',
  ENER: '#d97706', MOVE: '#2563c9', CNECT: '#7c3aed', COMP: '#1a5fb4', TRADE: '#9333ea',
  FISMA: '#b45309', ECFIN: '#0369a1', TAXUD: '#6366f1', GROW: '#0891b2', EMPL: '#db2777',
  JUST: '#4f46e5', HOME: '#ea580c', REGIO: '#e11d48', RTD: '#0d9488', JRC: '#475569',
  INTPA: '#ca8a04', ENEST: '#c2710c', DEFIS: '#3f4756', OLAF: '#b91c1c', ECHO: '#ef6c00',
  HERA: '#be123c', DGT: '#6366f1', ESTAT: '#7c3aed', FPI: '#516170', MENA: '#a16207',
};
const dgColor = (dg: string | null) => (dg && DG_COLORS[dg]) || '#2a3fd6';

interface NewsItem {
  id: string;
  title: string;
  summary: string | null;
  news_date: string | null;
  institution: string | null;
  commission_dg: string | null;
  dg_name: string | null;
  item_type: string | null;
  source_key: string | null;
  image_url: string | null;
  source_url: string | null;
  matches_interests: boolean;
  interest_reason?: string | null;
  matches_tracked?: boolean;
  tracked_reason?: string | null;
  policy_areas?: string[];
  org_type_label?: string | null;
  org_code?: string | null;
  translated_from?: string | null;
  detected_lang?: string | null;
}
interface Facets { institution: Record<string, number>; commission_dg: Record<string, number>; item_type: Record<string, number>; }

// Friendly labels for the institution filter; agencies keep their acronym.
const INST_LABELS: Record<string, string> = {
  COMMISSION: 'European Commission', EP: 'European Parliament', OUTLET: 'EU bubble outlets',
  ECB: 'European Central Bank (ECB)', EEA: 'Environment Agency (EEA)',
  EFSA: 'Food Safety (EFSA)', ESMA: 'Securities & Markets (ESMA)',
  EBA: 'Banking Authority (EBA)', EIOPA: 'Insurance & Pensions (EIOPA)',
  EUROPOL: 'Europol', FRONTEX: 'Frontex', EASA: 'Aviation Safety (EASA)',
  EUDA: 'Drugs Agency (EUDA)', EULISA: 'eu-LISA', EUSPA: 'Space Programme (EUSPA)',
  SRB: 'Single Resolution Board', CEDEFOP: 'Cedefop', ETF: 'Training Foundation (ETF)',
  ELA: 'Labour Authority (ELA)', EFCA: 'Fisheries Control (EFCA)', ERA: 'Railways (ERA)',
  EIGE: 'Gender Equality (EIGE)', BEREC: 'BEREC',
  EESC: 'Economic & Social Committee (EESC)', EPPO: 'Public Prosecutor (EPPO)',
  EMA: 'Medicines Agency (EMA)', EMSA: 'Maritime Safety (EMSA)',
  // bespoke-parser bodies
  COUNCIL: 'Council of the EU', ECA: 'Court of Auditors (ECA)',
  EIB: 'European Investment Bank (EIB)', COR: 'Committee of the Regions (CoR)',
  OMBUDSMAN: 'European Ombudsman', ECHA: 'Chemicals Agency (ECHA)',
  ENISA: 'Cybersecurity (ENISA)', EUIPO: 'Intellectual Property (EUIPO)',
  EUAA: 'Asylum Agency (EUAA)', EUROJUST: 'Eurojust', FRA: 'Fundamental Rights (FRA)',
  'EU-OSHA': 'Safety at Work (EU-OSHA)', OSHA: 'Safety at Work (EU-OSHA)',
  ACER: 'Energy Regulators (ACER)', ECDC: 'Disease Control (ECDC)',
  CEPOL: 'Law Enforcement Training (CEPOL)', EIT: 'Innovation & Technology (EIT)',
  CPVO: 'Plant Variety (CPVO)', CDT: 'Translation Centre (CdT)',
  CJEU: 'Court of Justice (CJEU)', EDPS: 'Data Protection Supervisor (EDPS)',
  EEAS: 'External Action Service (EEAS)',
  FUNDING: 'Funding & Tenders Portal',
};
const instLabel = (code: string) => INST_LABELS[code] || code;
interface NewsResponse { items: NewsItem[]; featured: NewsItem[]; total: number; pi_active: boolean; files_active?: boolean; has_tracked_files?: boolean; facets: Facets; org_type_labels?: Record<string, string>; }

type NewsSource = 'institutions' | 'stakeholders';

const authCfg = () => {
  const token = useAuth.getState().token;
  return token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;
};

const fmtDate = (iso: string | null) => {
  if (!iso) return '';
  try { return new Date(iso + 'T00:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }); }
  catch { return iso; }
};

const DgChip = ({ item }: { item: NewsItem }) => {
  const { t } = useTranslation();
  // Stakeholder items have no DG: show the localised org-type, never the register code.
  const label = item.commission_dg
    || (item.org_type_label ? t(`news.orgType.${item.institution}`, item.org_type_label) : null)
    || item.source_key || item.institution || 'EU';
  return <span className="news-dgchip" style={{ background: dgColor(item.commission_dg) }}>{label}</span>;
};

const Thumb = ({ item, className }: { item: NewsItem; className?: string }) => (
  item.image_url ? (
    <img className={`news-img ${className || ''}`} src={item.image_url} alt="" loading="lazy"
      onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }} />
  ) : (
    <div className={`news-img news-img--placeholder ${className || ''}`}
      style={{ background: `linear-gradient(135deg, ${dgColor(item.commission_dg)}, #1a1a2e)` }}>
      <Icon path={mdiImageOutline} size={1.4} />
    </div>
  )
);

const HeroCard = ({ item, big }: { item: NewsItem; big?: boolean }) => {
  const { t } = useTranslation();
  return (
    <a className={`news-hero ${big ? 'news-hero--big' : ''}`} href={item.source_url || '#'}
      target="_blank" rel="noopener noreferrer">
      <Thumb item={item} className="news-hero__img" />
      <div className="news-hero__overlay" />
      <div className="news-hero__body">
        <div className="news-hero__meta">
          <DgChip item={item} />
          {item.matches_interests && (
            <span className="news-chip news-chip--pi"><Icon path={mdiStar} size={0.5} /> {t('news.mine', 'Your interest')}</span>
          )}
          <span className="news-hero__date">{fmtDate(item.news_date)}</span>
        </div>
        <h3 className="news-hero__title">{item.title}</h3>
        {big && item.summary && <p className="news-hero__summary">{item.summary}</p>}
      </div>
    </a>
  );
};

const NewsCard = ({ item }: { item: NewsItem }) => {
  const { t } = useTranslation();
  return (
    <a className={`news-card ${item.matches_interests ? 'is-pi' : ''}`} href={item.source_url || '#'}
      target="_blank" rel="noopener noreferrer" style={{ ['--dg' as never]: dgColor(item.commission_dg) }}>
      <div className="news-card__imgwrap"><Thumb item={item} /></div>
      <div className="news-card__body">
        <div className="news-card__meta">
          <DgChip item={item} />
          {item.translated_from && (
            <span className="news-chip is-muted" title={t('news.translatedFrom', { lang: item.translated_from }) as string}>
              <Icon path={mdiTranslate} size={0.45} /> {t('news.translated', 'Translated')}
            </span>
          )}
          {item.item_type && item.item_type !== 'news' && (
            <span className="news-chip is-muted">{t(`news.type.${item.item_type}`, item.item_type)}</span>
          )}
          {item.matches_tracked && (
            <span className="news-chip news-chip--tracked" title={item.tracked_reason || ''}>
              <Icon path={mdiBookmarkCheck} size={0.45} /> {t('news.tracked', 'Files you track')}
            </span>
          )}
          {item.matches_interests && (
            <span className="news-chip news-chip--pi" title={item.interest_reason || ''}><Icon path={mdiStar} size={0.45} /> {t('news.mine', 'Your interest')}</span>
          )}
        </div>
        <h3 className="news-card__title">{item.title}</h3>
        {item.summary && <p className="news-card__summary">{item.summary}</p>}
        <div className="news-card__foot">
          <span className="news-card__date">{fmtDate(item.news_date)}</span>
          <span className="news-card__src">{item.dg_name || item.source_key} <Icon path={mdiOpenInNew} size={0.5} /></span>
        </div>
      </div>
    </a>
  );
};

export const NewsTab = () => {
  const { t, i18n } = useTranslation();
  const uiLang = (i18n.language || 'en').split('-')[0];
  const [source, setSource] = useState<NewsSource>('institutions');
  const [mode, setMode] = useState<'all' | 'pi' | 'files'>('all');
  const [institution, setInstitution] = useState('');
  const [dg, setDg] = useState('');
  const [itemType, setItemType] = useState('');
  const [search, setSearch] = useState('');
  const [data, setData] = useState<NewsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryNonce, setRetryNonce] = useState(0);
  const [hasPi, setHasPi] = useState(false);

  const stakeholders = source === 'stakeholders';

  useEffect(() => {
    axios.get<{ keywords: string[] }>(`${API_BASE}/eu-news/my-keywords`, authCfg())
      .then((r) => setHasPi((r.data.keywords || []).length > 0)).catch(() => { });
  }, []);

  // Switching source swaps the facet vocabulary; reset facet filters (keep search).
  const switchSource = (next: NewsSource) => {
    if (next === source) return;
    setSource(next);
    setInstitution(''); setDg(''); setItemType('');
    if (next === 'stakeholders' && mode === 'files') setMode('all');
  };

  useEffect(() => {
    setLoading(true);
    setError(false);
    const p = new URLSearchParams();
    if (mode === 'pi') p.set('my_interests', 'true');
    if (mode === 'files' && !stakeholders) p.set('my_files', 'true');
    if (institution) p.set('institution', institution);
    if (dg && !stakeholders) p.set('commission_dg', dg);
    if (itemType && !stakeholders) p.set('item_type', itemType);
    if (search.trim()) p.set('search', search.trim());
    if (stakeholders) p.set('lang', uiLang);
    p.set('limit', '80');
    const endpoint = stakeholders ? 'stakeholders' : 'items';
    axios.get<NewsResponse>(`${API_BASE}/eu-news/${endpoint}?${p.toString()}`, authCfg())
      .then((r) => setData(r.data))
      .catch(() => { setData(null); setError(true); })
      .finally(() => setLoading(false));
  }, [source, mode, institution, dg, itemType, search, uiLang, retryNonce]);

  const facets = data?.facets;
  // The hero shows the featured set; the grid shows the rest (de-duplicated).
  const heroIds = useMemo(() => new Set((data?.featured || []).map((f) => f.id)), [data]);
  const gridItems = useMemo(
    () => (data?.items || []).filter((i) => !heroIds.has(i.id)),
    [data, heroIds]);
  const showHero = !institution && !dg && !itemType && !search.trim() && (data?.featured?.length || 0) >= 3;

  return (
    <div className="news-tab">
      <MeubHeader
        icon={mdiNewspaperVariantMultipleOutline}
        title={t('news.title', 'News')}
        subtitle={stakeholders
          ? t('news.introStakeholders', 'What the Brussels advocacy ecosystem is publishing, in one feed.')
          : t('news.intro', 'Every EU institution’s news in one feed, tuned to your interests.')}
        aside={data && (
          <div className="news-head__count"><b>{data.total}</b> {stakeholders ? t('news.updates', 'updates') : t('news.stories', 'stories')}</div>
        )}
      />

      {/* Source axis: institutions (what the EU does) vs stakeholders (what the bubble says). */}
      <div className="news-segmented news-segmented--source">
        <button className={!stakeholders ? 'is-active' : ''} onClick={() => switchSource('institutions')}>
          <Icon path={mdiBankOutline} size={0.7} /> {t('news.srcInstitutions', 'EU institutions')}
        </button>
        <button className={stakeholders ? 'is-active' : ''} onClick={() => switchSource('stakeholders')}>
          <Icon path={mdiAccountTieVoiceOutline} size={0.7} /> {t('news.srcStakeholders', 'Brussels stakeholders')}
        </button>
      </div>

      <div className="news-controls">
        {(hasPi || data?.has_tracked_files) && (
          <div className="news-segmented">
            <button className={mode === 'all' ? 'is-active' : ''} onClick={() => setMode('all')}>{t('news.all', 'All')}</button>
            {hasPi && (
              <button className={mode === 'pi' ? 'is-active' : ''} onClick={() => setMode('pi')}>
                <Icon path={mode === 'pi' ? mdiStar : mdiStarOutline} size={0.7} /> {t('news.myInterests', 'My interests')}
              </button>
            )}
            {data?.has_tracked_files && (
              <button className={mode === 'files' ? 'is-active' : ''} onClick={() => setMode('files')}>
                <Icon path={mode === 'files' ? mdiBookmarkCheck : mdiBookmarkCheckOutline} size={0.7} /> {t('news.myFiles', 'My files')}
              </button>
            )}
          </div>
        )}
        {facets && (
          <select className="news-select" value={institution} onChange={(e) => { setInstitution(e.target.value); setDg(''); }}>
            <option value="">{stakeholders ? t('news.allTypesStk', 'All types') : t('news.allInstitutions', 'All institutions')}</option>
            {Object.entries(facets.institution).map(([code, n]) => (
              <option key={code} value={code}>
                {stakeholders ? t(`news.orgType.${code}`, data?.org_type_labels?.[code] || code) : instLabel(code)} ({n})
              </option>
            ))}
          </select>
        )}
        {!stakeholders && facets && (!institution || institution === 'COMMISSION') && (
          <select className="news-select" value={dg} onChange={(e) => setDg(e.target.value)}>
            <option value="">{t('news.allDgs', 'All departments')}</option>
            {Object.entries(facets.commission_dg).map(([code, n]) => (
              <option key={code} value={code}>{code} ({n})</option>
            ))}
          </select>
        )}
        {!stakeholders && facets && (
          <select className="news-select" value={itemType} onChange={(e) => setItemType(e.target.value)}>
            <option value="">{t('news.allTypes', 'All types')}</option>
            {Object.keys(facets.item_type).map((ty) => (
              <option key={ty} value={ty}>{t(`news.type.${ty}`, ty)}</option>
            ))}
          </select>
        )}
        <div className="news-search">
          <Icon path={mdiMagnify} size={0.8} />
          <input value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder={(stakeholders ? t('news.searchPlaceholderStk', 'Search stakeholder updates') : t('news.searchPlaceholder', 'Search EU news')) as string} />
        </div>
      </div>

      {loading ? (
        <ListSkeleton count={6} lines={3} />
      ) : error ? (
        <div className="news-empty news-error">
          <Icon path={mdiAlertCircleOutline} size={2} />
          <p>{t('news.error', 'We could not load the news right now. Please try again in a moment.')}</p>
          <button type="button" className="news-retry" onClick={() => setRetryNonce((n) => n + 1)}>
            {t('common.retry', 'Retry')}
          </button>
        </div>
      ) : !data || data.items.length === 0 ? (
        <div className="news-empty">
          <Icon path={mdiNewspaperVariantMultipleOutline} size={2} />
          <p>{mode === 'pi' ? t('news.emptyPi', 'No news in your interests right now.')
              : mode === 'files' ? t('news.emptyFiles', 'No news related to the files you track right now.')
              : stakeholders ? t('news.emptyStk', 'No stakeholder updates found.')
              : t('news.empty', 'No news found.')}</p>
        </div>
      ) : (
        <>
          {showHero && data.featured.length >= 3 && (
            <section className="news-herogrid">
              <HeroCard item={data.featured[0]} big />
              <div className="news-herogrid__side">
                <HeroCard item={data.featured[1]} />
                <HeroCard item={data.featured[2]} />
              </div>
            </section>
          )}
          <section className="news-section">
            <h2 className="news-section__title">
              {mode === 'pi' ? t('news.inYourInterests', 'In your interests')
                : mode === 'files' ? t('news.relatedToFiles', 'Related to files you track')
                : t('news.latest', 'Latest')}
              <span className="news-muted"> ({gridItems.length})</span>
            </h2>
            <div className="news-grid">
              {gridItems.map((item) => <NewsCard key={item.id} item={item} />)}
            </div>
          </section>
        </>
      )}
    </div>
  );
};
