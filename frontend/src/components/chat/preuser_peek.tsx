/**
 * Pre-user peek strip - a light glimpse of Brubru's breadth shown only in the
 * logged-out Chat empty-state. Six plain-language chips of what lives inside
 * the product (the moat a chat box alone cannot fake) plus a single trial CTA
 * that opens the cockpit (My EU Bubble). No new data, no density - one strip.
 */

import { useTranslation } from 'react-i18next';
import './preuser_peek.css';

interface PreUserPeekProps {
  /** Fired when the visitor clicks "Start free trial". */
  onStartTrial: () => void;
}

export const PreUserPeek = ({ onStartTrial }: PreUserPeekProps) => {
  const { t } = useTranslation();

  const chips = [
    t('chat.preuser.peek.tracker'),
    t('chat.preuser.peek.lobby'),
    t('chat.preuser.peek.calendar'),
    t('chat.preuser.peek.amendments'),
    t('chat.preuser.peek.compliance'),
    t('chat.preuser.peek.tenders'),
  ];

  return (
    <div className="preuser-peek">
      <div className="preuser-peek__chips" role="list">
        {chips.map((label, i) => (
          <span key={i} className="preuser-peek__chip" role="listitem">
            <i aria-hidden="true" />
            {label}
          </span>
        ))}
      </div>
      <button type="button" className="preuser-peek__cta" onClick={onStartTrial}>
        {t('chat.preuser.cta')} <span aria-hidden="true">&rarr;</span>
      </button>
      <p className="preuser-peek__note">{t('chat.preuser.note')}</p>
    </div>
  );
};
