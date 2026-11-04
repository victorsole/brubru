// frontend/src/components/api_console/how_it_works.tsx
// The console explained once, for someone who has never called an API. Opens only when asked for.
import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { ConsolePricing } from '../../services/api_console';

const STEPS = ['1', '2', '3'];
const WORDS = ['api', 'route', 'filter', 'result', 'freeCall', 'key', 'fullText'];

interface Props {
  pricing: ConsolePricing | null;
  onClose: () => void;
}

export const HowItWorks = ({ pricing, onClose }: Props) => {
  const { t } = useTranslation();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = overflow;
      before?.focus?.();
    };
  }, [onClose]);

  const calls = pricing?.sandbox.calls_per_visitor_per_day ?? 10;
  const rows = pricing?.sandbox.max_limit ?? 25;

  return createPortal(
    <div className="api-console-modal" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="api-console-modal__box" role="dialog" aria-modal="true" aria-labelledby="api-console-how-title">
        <div className="api-console-modal__head">
          <h2 id="api-console-how-title">{t('api.console.how.title')}</h2>
          <button ref={closeRef} type="button" className="api-console-modal__close" aria-label={t('api.console.how.close')} onClick={onClose}>
            <span className="mdi mdi-close" aria-hidden="true" />
          </button>
        </div>
        <p>{t('api.console.how.intro')}</p>
        <ol className="api-console-modal__steps">
          {STEPS.map((n) => (
            <li key={n}>
              <strong>{t(`api.console.how.step${n}Title`)}</strong>
              <span>{t(`api.console.how.step${n}Text`)}</span>
            </li>
          ))}
        </ol>
        <h3>{t('api.console.how.wordsTitle')}</h3>
        <dl className="api-console-modal__words">
          {WORDS.map((word) => (
            <div key={word}>
              <dt>{t(`api.console.how.words.${word}Term`)}</dt>
              <dd>{t(`api.console.how.words.${word}Text`, { calls, rows })}</dd>
            </div>
          ))}
        </dl>
        <h3>{t('api.console.how.nextTitle')}</h3>
        <p>{t('api.console.how.nextText')}</p>
        <div className="api-console-modal__actions">
          <button type="button" className="api-console__send-button" onClick={onClose}>{t('api.console.how.start')}</button>
          <Link to="/api#your-keys" onClick={onClose}>{t('api.console.getKey')}</Link>
        </div>
      </div>
    </div>,
    document.body,
  );
};
