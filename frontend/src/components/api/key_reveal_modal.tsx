// frontend/src/components/api/key_reveal_modal.tsx
//
// One-time plaintext reveal after a successful mint. Closes for good once the
// user clicks "I've saved it" — the plaintext is never reachable again from
// the application; the only place it exists is wherever the user pasted it.
//
// Rendered via createPortal so it escapes any framer-motion `transform`
// parent (see memory/feedback_modal_portal_required.md).

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import type { CreateKeyResponse } from '../../services/api_keys';
import './api_keys.css';

interface Props {
  result: CreateKeyResponse;
  onDone: () => void;
}

function formatDate(iso: string | null, neverLabel: string): string {
  if (!iso) return neverLabel;
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
    });
  } catch {
    return iso;
  }
}

export const KeyRevealModal = ({ result, onDone }: Props) => {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  // ESC to close — but we keep this conservative: the warning is meant to be read.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onDone();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onDone]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(result.key);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2200);
    } catch {
      // Older browsers / insecure contexts: fall back to a textarea select.
      const ta = document.createElement('textarea');
      ta.value = result.key;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch { /* ignore */ }
      document.body.removeChild(ta);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2200);
    }
  };

  const modal = (
    <div
      className="api-keys-modal__backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="reveal-title"
      onClick={(e) => { if (e.target === e.currentTarget) onDone(); }}
    >
      <div className="api-keys-modal">
        <div className="api-keys-modal__header">
          <div>
            <h2 id="reveal-title" className="api-keys-modal__title">
              {t('api.keys.reveal.title')}
            </h2>
            <p className="api-keys-modal__subtitle">{result.name}</p>
          </div>
        </div>

        <div className="api-keys-modal__body">
          <div className="api-keys-reveal__warning">
            <span className="mdi mdi-alert-circle-outline" aria-hidden="true" />
            <span>{t('api.keys.reveal.warning')}</span>
          </div>

          <div className="api-keys-reveal__keybox" aria-label={t('api.keys.reveal.title') as string}>
            {result.key}
          </div>

          <div className="api-keys-reveal__copy-row">
            <button
              type="button"
              className="api-keys-btn api-keys-btn--secondary"
              onClick={handleCopy}
            >
              <span className="mdi mdi-content-copy" aria-hidden="true" />
              {t('api.keys.reveal.copy')}
            </button>
            {copied && (
              <span className="api-keys-reveal__copied" role="status">
                <span className="mdi mdi-check" aria-hidden="true" /> {t('api.keys.reveal.copied')}
              </span>
            )}
          </div>

          <div className="api-keys-reveal__metadata">
            <div className="api-keys-reveal__metadata-row">
              <span className="api-keys-reveal__metadata-label">
                {t('api.keys.list.prefix')}:
              </span>
              <span>brubru_live_…{result.key_prefix}</span>
            </div>
            <div className="api-keys-reveal__metadata-row">
              <span className="api-keys-reveal__metadata-label">
                {t('api.keys.list.scopes')}:
              </span>
              <span>{result.scopes.join(', ')}</span>
            </div>
            <div className="api-keys-reveal__metadata-row">
              <span className="api-keys-reveal__metadata-label">
                {t('api.keys.list.expires')}:
              </span>
              <span>
                {formatDate(result.expires_at, t('api.keys.list.never') as string)}
              </span>
            </div>
          </div>
        </div>

        <div className="api-keys-modal__footer">
          <button
            type="button"
            className="api-keys-btn api-keys-btn--primary"
            onClick={onDone}
          >
            {t('api.keys.reveal.done')}
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
};
