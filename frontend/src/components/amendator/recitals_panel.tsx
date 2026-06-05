// frontend/src/components/amendator/recitals_panel.tsx
//
// Third sidebar tab in the Amendator. Surfaces the TF-IDF-linked recitals for
// the article the user is currently amending so that a drafter can cite them
// in the amendment's Justification without leaving the page.
//
// Inputs:
//   - selectedElement: the article / paragraph / point currently selected in
//                      the document viewer (comes from amendator_page.tsx)
//   - celex: CELEX of the loaded law
//
// Behaviour:
//   - If no article is selected, shows an empty state.
//   - Otherwise fetches (cached) the recital-article map for the CELEX and
//     displays the top-3 recitals linked to the selected article, with score
//     bars and a "Copy for justification" button per recital.
//
// The panel never mutates application state -- copies go to the clipboard;
// the drafter pastes them wherever they want.

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiCompassOutline,
  mdiContentCopy,
  mdiCheck,
  mdiOpenInNew,
  mdiLinkVariantOff,
} from '@mdi/js';
import type { LegislativeElement } from './two_column_layout';
import type { RecitalLink } from '../../hooks/use_legal_intelligence';
import { useRecitalArticleMap } from '../../hooks/use_legal_intelligence';
import './recitals_panel.css';

interface RecitalsPanelProps {
  selectedElement: LegislativeElement | null;
  celex?: string;
}

/** Given a selected element, pick the best key to look up in the map. */
function _articleKey(el: LegislativeElement | null): string | null {
  if (!el) return null;
  const num = el.article_number || el.number;
  if (!num) return null;
  return `Article ${num}`;
}

export const RecitalsPanel = ({ selectedElement, celex }: RecitalsPanelProps) => {
  const { t } = useTranslation();
  const { data: map, loading } = useRecitalArticleMap(celex);
  const articleKey = _articleKey(selectedElement);
  const links: RecitalLink[] = (articleKey && map?.[articleKey]) || [];

  if (!celex) {
    return (
      <div className="recitals-panel__empty">
        <Icon path={mdiLinkVariantOff} size={2.5} />
        <p className="recitals-panel__empty-title">{t('amendator.panel.loadLawFirst')}</p>
        <p className="recitals-panel__empty-hint">{t('amendator.panel.loadLawHint')}</p>
      </div>
    );
  }

  if (loading && !map) {
    return (
      <div className="recitals-panel__empty">
        <p className="recitals-panel__empty-hint">{t('amendator.panel.computing')}</p>
      </div>
    );
  }

  if (!articleKey) {
    return (
      <div className="recitals-panel__empty">
        <Icon path={mdiCompassOutline} size={2.5} />
        <p className="recitals-panel__empty-title">{t('amendator.panel.selectArticle')}</p>
        <p className="recitals-panel__empty-hint">{t('amendator.panel.selectArticleHint')}</p>
      </div>
    );
  }

  if (!links.length) {
    return (
      <div className="recitals-panel__empty">
        <p className="recitals-panel__empty-title">{t('amendator.panel.noLinkedRecitals', { article: articleKey })}</p>
        <p className="recitals-panel__empty-hint">{t('amendator.panel.noLinkedHint')}</p>
      </div>
    );
  }

  return (
    <div className="recitals-panel">
      <header className="recitals-panel__header">
        <h3 className="recitals-panel__title">{t('amendator.panel.title', { article: articleKey })}</h3>
        <p className="recitals-panel__subtitle">{t('amendator.panel.subtitle', { count: links.length })}</p>
      </header>

      <ul className="recitals-panel__list">
        {links.map((link) => (
          <RecitalCard
            key={link.recital_number}
            link={link}
            celex={celex}
            articleKey={articleKey}
          />
        ))}
      </ul>

      <footer className="recitals-panel__footer">
        <a
          href={`https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:${celex}`}
          target="_blank"
          rel="noopener noreferrer"
          className="recitals-panel__eurlex-link"
        >
          <Icon path={mdiOpenInNew} size={0.7} />
          {t('amendator.panel.openFullEurlex')}
        </a>
      </footer>
    </div>
  );
};

interface RecitalCardProps {
  link: RecitalLink;
  celex: string;
  articleKey: string;
}

function RecitalCard({ link, celex, articleKey }: RecitalCardProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  const scorePct = Math.min(100, Math.round(link.score * 100));

  const handleCopy = () => {
    const justification = `Recital (${link.recital_number}) of ${celex} supports the amendment to ${articleKey}: ${link.snippet}`;
    navigator.clipboard
      .writeText(justification)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => {
        /* clipboard refused -- let the user copy manually */
      });
  };

  useEffect(() => {
    setCopied(false);
  }, [link.recital_number]);

  return (
    <li className="recital-card">
      <div className="recital-card__header">
        <span className="recital-card__number">{t('amendator.panel.recitalNumber', { number: link.recital_number })}</span>
        <span className="recital-card__score" title={`Cosine similarity: ${link.score.toFixed(3)}`}>
          <span className="recital-card__score-bar" style={{ width: `${scorePct}%` }} />
          <span className="recital-card__score-label">{scorePct}%</span>
        </span>
      </div>

      <p className="recital-card__snippet">{link.snippet}</p>

      <div className="recital-card__actions">
        <button
          type="button"
          className="recital-card__copy-btn"
          onClick={handleCopy}
          title={t('amendator.panel.copyTooltip')}
        >
          <Icon path={copied ? mdiCheck : mdiContentCopy} size={0.7} />
          {copied ? t('amendator.panel.copied') : t('amendator.panel.copyForJustification')}
        </button>
      </div>
    </li>
  );
}
