// frontend/src/components/api/revoke_confirm_modal.tsx
//
// Confirmation dialog for revoking an API key. Portal'd to body.

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import type { ApiKeySummary } from '../../services/api_keys';
import { ApiKeysService } from '../../services/api_keys';
import './api_keys.css';

interface Props {
  keyToRevoke: ApiKeySummary;
  onClose: () => void;
  onRevoked: () => void;
}

export const RevokeConfirmModal = ({ keyToRevoke, onClose, onRevoked }: Props) => {
  const { t } = useTranslation();
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !working) onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, working]);

  const handleRevoke = async () => {
    setWorking(true);
    setError(null);
    try {
      await ApiKeysService.revokeKey(keyToRevoke.id);
      onRevoked();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Revoke failed';
      setError(msg);
      setWorking(false);
    }
  };

  const modal = (
    <div
      className="api-keys-modal__backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="revoke-title"
      onClick={(e) => { if (e.target === e.currentTarget && !working) onClose(); }}
    >
      <div className="api-keys-modal" style={{ maxWidth: 480 }}>
        <div className="api-keys-modal__header">
          <h2 id="revoke-title" className="api-keys-modal__title">
            {t('api.keys.revoke.title')}
          </h2>
          <button
            type="button"
            className="api-keys-modal__close"
            onClick={onClose}
            disabled={working}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="api-keys-modal__body">
          {error && (
            <div className="api-keys-error-banner">
              <span className="mdi mdi-alert-circle-outline" aria-hidden="true" />
              {error}
            </div>
          )}

          <p style={{ margin: '0 0 0.75rem 0', color: '#1a1a1a' }}>
            {t('api.keys.revoke.body', { name: keyToRevoke.name })}
          </p>
          <p style={{ margin: 0, color: '#555', fontSize: '0.875rem' }}>
            <span className="mdi mdi-information-outline" style={{ color: '#888', marginRight: '0.3rem' }} aria-hidden="true" />
            brubru_live_…{keyToRevoke.key_prefix}
          </p>
        </div>

        <div className="api-keys-modal__footer">
          <button
            type="button"
            className="api-keys-btn api-keys-btn--secondary"
            onClick={onClose}
            disabled={working}
          >
            {t('api.keys.revoke.cancel')}
          </button>
          <button
            type="button"
            className="api-keys-btn api-keys-btn--danger-solid"
            onClick={handleRevoke}
            disabled={working}
          >
            {working ? t('api.keys.revoke.working') : t('api.keys.revoke.confirm')}
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
};
