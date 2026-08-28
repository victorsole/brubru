// The Tenderator glossary: the words the EU uses for money, and what they mean.
//
// Opened from the Glossary button in the dashboard header, beside Calendar and
// Profile. Rendered through createPortal into document.body -- the Tenderator
// sits inside an AnimatedPage, framer-motion puts a transform on it, and a
// transformed ancestor becomes the containing block for position: fixed. Left
// in place the overlay would size itself to the page box instead of the
// viewport, dimming only part of the screen. See feedback_modal_portal_required.

import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import { mdiClose, mdiMagnify, mdiBookOpenPageVariantOutline } from '@mdi/js';
import {
  GLOSSARY_CATEGORIES,
  GLOSSARY_ENTRIES,
  type GlossaryCategory,
} from '../../utils/tender_glossary';
import './glossary_modal.css';

interface GlossaryModalProps {
  open: boolean;
  onClose: () => void;
}

/** Accent-insensitive, case-insensitive haystack for the search box. */
const fold = (value: string): string =>
  value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

export const GlossaryModal = ({ open, onClose }: GlossaryModalProps) => {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const searchRef = useRef<HTMLInputElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  // Escape closes, and the search box takes focus on open so a keyboard user
  // can start typing immediately.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    const focusTimer = window.setTimeout(() => searchRef.current?.focus(), 40);
    // Stop the page behind scrolling under the dialog.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      window.clearTimeout(focusTimer);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  useEffect(() => {
    if (!open) setQuery('');
  }, [open]);

  // Search matches the term, the definition AND the machine codes the entry
  // explains, so someone who pasted "neg-w-call" out of a spreadsheet lands on
  // the negotiated-procedure entry.
  const grouped = useMemo(() => {
    const needle = fold(query.trim());
    const out = new Map<GlossaryCategory, { key: string; term: string; definition: string }[]>();
    GLOSSARY_CATEGORIES.forEach((c) => out.set(c, []));

    GLOSSARY_ENTRIES.forEach((entry) => {
      const term = t(`tenderator.glossary.terms.${entry.key}.term`);
      const definition = t(`tenderator.glossary.terms.${entry.key}.definition`);
      if (needle) {
        const haystack = fold([term, definition, ...(entry.codes || [])].join(' '));
        if (!haystack.includes(needle)) return;
      }
      out.get(entry.category)!.push({ key: entry.key, term, definition });
    });
    return out;
  }, [query, t]);

  const total = useMemo(
    () => Array.from(grouped.values()).reduce((n, list) => n + list.length, 0),
    [grouped],
  );

  if (!open) return null;

  return createPortal(
    <div
      className="tender-glossary__overlay"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="tender-glossary"
        role="dialog"
        aria-modal="true"
        aria-labelledby="tender-glossary-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="tender-glossary__header">
          <div className="tender-glossary__heading">
            <Icon path={mdiBookOpenPageVariantOutline} size={0.95} aria-hidden="true" />
            <div>
              <h2 id="tender-glossary-title">{t('tenderator.glossary.title')}</h2>
              <p>{t('tenderator.glossary.subtitle')}</p>
            </div>
          </div>
          <button
            ref={closeRef}
            type="button"
            className="tender-glossary__close"
            onClick={onClose}
            aria-label={t('tenderator.glossary.close')}
          >
            <Icon path={mdiClose} size={0.9} />
          </button>
        </header>

        <div className="tender-glossary__search">
          <Icon path={mdiMagnify} size={0.8} aria-hidden="true" />
          <input
            ref={searchRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('tenderator.glossary.search')}
            aria-label={t('tenderator.glossary.search')}
          />
          <span className="tender-glossary__count">
            {t('tenderator.glossary.count', { count: total })}
          </span>
        </div>

        <div className="tender-glossary__body">
          {total === 0 && (
            <p className="tender-glossary__empty">{t('tenderator.glossary.noResults')}</p>
          )}
          {GLOSSARY_CATEGORIES.map((category) => {
            const entries = grouped.get(category) || [];
            if (entries.length === 0) return null;
            return (
              <section key={category} className="tender-glossary__group">
                <h3>{t(`tenderator.glossary.categories.${category}`)}</h3>
                <dl>
                  {entries.map((entry) => (
                    <div key={entry.key} className="tender-glossary__entry">
                      <dt>{entry.term}</dt>
                      <dd>{entry.definition}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            );
          })}
        </div>
      </div>
    </div>,
    document.body,
  );
};
