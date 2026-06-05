/**
 * Research & Evidence tab (MEUB Section 4 - Analysis & Strategy).
 *
 * An independent, top-level filter (NOT part of Brubru Databases): a curated,
 * PI-aware launchpad over EXTERNAL EU research/evidence publishers. Foresight
 * anchors (STOA / JRC / Council) plus EU research & evidence sources (CORDIS,
 * JRC Knowledge Centres, the Publications Office catalogue, flagship DGs). Each
 * source can read-through its publications RSS feed, and any document can be
 * summarised in full by AI with a personalised "how this is useful to you".
 *
 * No Anthropic (the summariser uses Mistral -> GPT-4 -> Gemini). 1040px cap,
 * 6 languages, no em-dashes. Shares the Brubru Databases stylesheet.
 */
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, AnimatePresence } from 'framer-motion';
import Icon from '@mdi/react';
import {
  mdiFlaskOutline, mdiMicroscope, mdiBankOutline, mdiRocketLaunchOutline, mdiLightbulbOnOutline,
  mdiLibraryShelves, mdiChartLine, mdiChip, mdiFactory, mdiAnchor, mdiSprout, mdiMapOutline,
  mdiOpenInNew, mdiMagnify, mdiChevronDown, mdiChevronUp, mdiInformationOutline, mdiAutoFix,
  mdiTextBoxOutline,
  mdiLeaf, mdiAccountGroupOutline, mdiShieldOutline, mdiHospitalBoxOutline, mdiMedicalBag,
  mdiFlash, mdiEarth, mdiScaleBalance, mdiTrainCar, mdiPercentOutline, mdiHandshakeOutline,
  mdiLifebuoy, mdiAtomVariant, mdiSchoolOutline, mdiSwapHorizontal,
} from '@mdi/js';
import { databasesService } from '../../services/databases_service';
import type {
  ResearchCatalogue, ResearchSource, ResearchFeedItem, ResearchSummary,
} from '../../services/databases_service';
import './databases_tab.css';

const cardVariants = {
  hidden: { opacity: 0, y: 14 },
  show: (i: number) => ({ opacity: 1, y: 0, transition: { delay: Math.min(i, 12) * 0.05 } }),
};

const fmtDate = (iso?: string) => {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
};

// Source icons (backend returns a short name).
const RES_ICON: Record<string, string> = {
  flask: mdiFlaskOutline, microscope: mdiMicroscope, bank: mdiBankOutline,
  rocket: mdiRocketLaunchOutline, lightbulb: mdiLightbulbOnOutline, library: mdiLibraryShelves,
  chart: mdiChartLine, chip: mdiChip, factory: mdiFactory, anchor: mdiAnchor,
  sprout: mdiSprout, map: mdiMapOutline,
  leaf: mdiLeaf, 'account-group': mdiAccountGroupOutline, shield: mdiShieldOutline,
  hospital: mdiHospitalBoxOutline, medical: mdiMedicalBag, flash: mdiFlash, earth: mdiEarth,
  scale: mdiScaleBalance, train: mdiTrainCar, percent: mdiPercentOutline,
  handshake: mdiHandshakeOutline, lifebuoy: mdiLifebuoy, atom: mdiAtomVariant,
  school: mdiSchoolOutline, trade: mdiSwapHorizontal,
};

// Minimal renderer for the AI summary (## headers + "- " bullets, plain paragraphs).
function renderSummary(text: string) {
  const blocks: ReactNode[] = [];
  let bullets: string[] = [];
  const flush = (key: string) => {
    if (bullets.length) {
      blocks.push(<ul key={key}>{bullets.map((b, i) => <li key={i}>{b}</li>)}</ul>);
      bullets = [];
    }
  };
  (text || '').split('\n').forEach((raw, i) => {
    const line = raw.trim();
    if (!line) { flush(`u${i}`); return; }
    if (line.startsWith('## ')) { flush(`u${i}`); blocks.push(<h5 key={`h${i}`}>{line.slice(3)}</h5>); return; }
    if (/^[-*•]\s+/.test(line)) { bullets.push(line.replace(/^[-*•]\s+/, '')); return; }
    flush(`u${i}`); blocks.push(<p key={`p${i}`}>{line}</p>);
  });
  flush('uend');
  return blocks;
}

export function ResearchEvidenceTab() {
  const { t } = useTranslation();
  const [cat, setCat] = useState<ResearchCatalogue | null>(null);
  const [mine, setMine] = useState(true);
  useEffect(() => { databasesService.researchSources(mine).then(setCat).catch(() => {}); }, [mine]);

  const visible = cat ? (mine ? cat.sources.filter((s) => s.is_pi_match) : cat.sources) : [];
  const groups: [string, string][] = [
    ['foresight', t('db.resForesight', 'Foresight anchors')],
    ['research', t('db.resPublishers', 'EU research & evidence')],
    ['department', t('db.resDepartments', 'Commission departments')],
  ];

  return (
    <div className="db-tab">
      <header className="db-tab__header">
        <div className="db-tab__title">
          <Icon path={mdiFlaskOutline} size={1.1} />
          <div>
            <h2>{t('bubble.research_evidence', 'Research & Evidence')}</h2>
            <p>{t('db.researchHint2', 'EU research and evidence, tailored to your interests. Open recent documents and get an AI summary of any of them.')}</p>
          </div>
        </div>
      </header>

      {!cat ? <div className="db-loading">{t('db.loading', 'Loading...')}</div> : (
        <div className="db-section">
          <div className="db-policy__controls">
            <div className="db-toggle">
              <button className={mine ? 'is-active' : ''} onClick={() => setMine(true)}>{t('db.mine', 'My interests')}</button>
              <button className={!mine ? 'is-active' : ''} onClick={() => setMine(false)}>{t('db.all', 'All sources')}</button>
            </div>
          </div>

          {groups.map(([gid, label]) => {
            const list = visible.filter((s) => s.group === gid);
            if (!list.length) return null;
            return (
              <div key={gid}>
                <h4 className="db-res-grouphead">{label}</h4>
                <div className="db-research-grid">
                  {list.map((s, i) => <ResearchCard key={s.id} src={s} i={i} t={t} />)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ResearchCard({ src, i, t }: { src: ResearchSource; i: number; t: any }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<ResearchFeedItem[] | null>(null);
  const [loadingFeed, setLoadingFeed] = useState(false);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && src.has_feed && items === null) {
      setLoadingFeed(true);
      databasesService.researchFeed(src.id)
        .then(setItems).catch(() => setItems([])).finally(() => setLoadingFeed(false));
    }
  };

  return (
    <motion.div className="db-research-card" custom={i} variants={cardVariants} initial="hidden" animate="show" whileHover={{ y: -3 }}>
      <div className="db-research-card__bar" style={{ background: src.color }} />
      <div className="db-research-card__head">
        <span className="db-research-card__icon" style={{ color: src.color }}><Icon path={RES_ICON[src.icon] || mdiFlaskOutline} size={0.95} /></span>
        <h3>{src.name}{src.is_pi_match && <span className="db-pi-badge">{t('db.yourInterest', 'Your interest')}</span>}</h3>
      </div>
      <p>{src.full}</p>
      <div className="db-research-card__actions">
        <a className="db-canon-card__cta" href={src.landing} target="_blank" rel="noopener noreferrer">{t('db.openPortal', 'Open portal')} <Icon path={mdiOpenInNew} size={0.55} /></a>
        <a className="db-seed" href={src.search} target="_blank" rel="noopener noreferrer"><Icon path={mdiMagnify} size={0.55} /> {t('db.searchMine', 'Search your interests')}</a>
      </div>
      {src.has_feed && (
        <button type="button" className="db-research-card__more" onClick={toggle} aria-expanded={open}>
          {open ? t('db.hideDocs', 'Hide recent documents') : t('db.showDocs', 'Recent documents')}
          <Icon path={open ? mdiChevronUp : mdiChevronDown} size={0.6} />
        </button>
      )}
      <AnimatePresence initial={false}>
        {open && src.has_feed && (
          <motion.div className="db-res-feed" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.2 }}>
            {loadingFeed && <div className="db-loading">{t('db.loading', 'Loading...')}</div>}
            {items && items.length === 0 && !loadingFeed && (
              <div className="db-note"><Icon path={mdiInformationOutline} size={0.7} /><span>{t('db.noDocs', 'No recent documents to show. Use the portal link above.')}</span></div>
            )}
            {items && items.map((it, j) => <ResearchDoc key={j} item={it} t={t} />)}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function ResearchDoc({ item, t }: { item: ResearchFeedItem; t: any }) {
  const [sum, setSum] = useState<ResearchSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const summarise = () => {
    if (loading || sum) return;
    setLoading(true);
    databasesService.researchSummary(item.url)
      .then(setSum).catch(() => setSum({ available: false, reason: 'failed' })).finally(() => setLoading(false));
  };
  return (
    <div className="db-res-doc">
      <div className="db-res-doc__row">
        <Icon path={mdiTextBoxOutline} size={0.6} className="db-res-doc__ic" />
        <a className="db-res-doc__title" href={item.url} target="_blank" rel="noopener noreferrer">{item.title}</a>
      </div>
      {item.date && <span className="db-res-doc__date">{fmtDate(item.date)}</span>}
      <button type="button" className="db-res-doc__ai" onClick={summarise} disabled={loading || !!sum}>
        <Icon path={mdiAutoFix} size={0.6} /> {loading ? t('db.summarising', 'Summarising...') : sum ? t('db.summarised', 'AI summary') : t('db.summariseAI', 'Summarise with AI')}
      </button>
      {sum && sum.available && (
        <div className="db-res-summary">
          {renderSummary(sum.summary || '')}
          <span className="db-res-summary__by">{t('db.generatedBy', 'Generated by')} {sum.model}{sum.cached ? ` · ${t('db.cached', 'cached')}` : ''}</span>
        </div>
      )}
      {sum && !sum.available && (
        <div className="db-note db-note--sm"><Icon path={mdiInformationOutline} size={0.6} /><span>{t('db.summaryFailed', 'Could not summarise this document right now.')}</span></div>
      )}
    </div>
  );
}

export default ResearchEvidenceTab;
