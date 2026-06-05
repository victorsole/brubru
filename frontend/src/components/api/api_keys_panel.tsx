// frontend/src/components/api/api_keys_panel.tsx
//
// Panel rendered on /api for logged-in users. Shows an empty state, a list of
// the caller's keys, and a "Create key" button that opens the mint flow.
//
// State machine:
//
//     mounted -> loading -> (empty | list)
//                                  |
//                                  +-> "Create" -> CreateKeyModal
//                                  |                |
//                                  |                +-> on success ->
//                                  |                    KeyRevealModal -> "Done" -> back to list (refreshed)
//                                  |
//                                  +-> "Revoke" -> RevokeConfirmModal -> on success -> back to list (refreshed)

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type {
  ApiKeySummary,
  CreateKeyResponse,
  ScopeCatalogue,
} from '../../services/api_keys';
import { ApiKeysService } from '../../services/api_keys';
import { ApiKeysList } from './api_keys_list';
import { CreateKeyModal } from './create_key_modal';
import { KeyRevealModal } from './key_reveal_modal';
import { RevokeConfirmModal } from './revoke_confirm_modal';
import './api_keys.css';

export const ApiKeysPanel = () => {
  const { t } = useTranslation();

  const [keys, setKeys] = useState<ApiKeySummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [catalogue, setCatalogue] = useState<ScopeCatalogue | null>(null);

  // Modal state
  const [creating, setCreating] = useState(false);
  const [revealing, setRevealing] = useState<CreateKeyResponse | null>(null);
  const [revoking, setRevoking] = useState<ApiKeySummary | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await ApiKeysService.listMyKeys();
      setKeys(data);
      setError(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to load keys';
      setError(msg);
    }
  }, []);

  useEffect(() => {
    refresh();
    // Preload the catalogue so we can show "X of N keys" in the header.
    ApiKeysService.getScopeCatalogue().then(setCatalogue).catch(() => undefined);
  }, [refresh]);

  const activeCount = (keys ?? []).filter(
    (k) => !k.revoked_at && !k.is_expired,
  ).length;
  const maxKeys = catalogue?.max_active_keys ?? 3;
  const atCap = activeCount >= maxKeys;

  const handleCreated = (result: CreateKeyResponse) => {
    setCreating(false);
    setRevealing(result);
    refresh(); // refresh list in the background
  };

  const handleRevoked = () => {
    setRevoking(null);
    refresh();
  };

  return (
    <section className="api-keys-panel" id="your-keys">
      <header className="api-keys-panel__header">
        <div>
          <h2 className="api-keys-panel__title">{t('api.keys.title')}</h2>
          <p className="api-keys-panel__lede">
            {t('api.keys.lede')}{' '}
            <span style={{ color: '#888' }}>
              ({t('api.keys.activeCount', { active: activeCount, max: maxKeys })})
            </span>
          </p>
        </div>
        <div className="api-keys-panel__cta-row">
          <Link to="/billing" className="api-keys-btn api-keys-btn--secondary">
            <span className="mdi mdi-wallet-outline" aria-hidden="true" />
            {t('api.keys.manageCredits')}
          </Link>
          <button
            type="button"
            className="api-keys-btn api-keys-btn--primary"
            onClick={() => setCreating(true)}
            disabled={atCap}
            title={atCap ? (t('api.keys.cap.reached') as string) : undefined}
          >
            <span className="mdi mdi-plus" aria-hidden="true" />
            {t('api.keys.createCta')}
          </button>
        </div>
      </header>

      {error && (
        <div className="api-keys-error-banner">
          <span className="mdi mdi-alert-circle-outline" aria-hidden="true" />
          {error}
        </div>
      )}

      {atCap && !error && (
        <div className="api-keys-error-banner" style={{ background: '#fff8e1', borderColor: '#ffe082', color: '#6a4d00' }}>
          <span className="mdi mdi-information-outline" aria-hidden="true" />
          {t('api.keys.cap.reached')}
        </div>
      )}

      {keys === null ? (
        <div className="api-keys-loading">{t('api.keys.loading')}</div>
      ) : keys.length === 0 ? (
        <div className="api-keys-empty">
          <span className="mdi mdi-key-outline api-keys-empty__icon" aria-hidden="true" />
          <h3 className="api-keys-empty__title">{t('api.keys.empty.title')}</h3>
          <p className="api-keys-empty__body">{t('api.keys.empty.body')}</p>
          <button
            type="button"
            className="api-keys-btn api-keys-btn--primary"
            onClick={() => setCreating(true)}
          >
            <span className="mdi mdi-plus" aria-hidden="true" />
            {t('api.keys.empty.cta')}
          </button>
        </div>
      ) : (
        <ApiKeysList keys={keys} onRevoke={setRevoking} />
      )}

      {creating && (
        <CreateKeyModal
          onClose={() => setCreating(false)}
          onCreated={handleCreated}
        />
      )}

      {revealing && (
        <KeyRevealModal
          result={revealing}
          onDone={() => setRevealing(null)}
        />
      )}

      {revoking && (
        <RevokeConfirmModal
          keyToRevoke={revoking}
          onClose={() => setRevoking(null)}
          onRevoked={handleRevoked}
        />
      )}
    </section>
  );
};
