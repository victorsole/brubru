// frontend/src/components/api/api_keys_list.tsx
//
// Renders the caller's API keys both as a desktop table (≥768px) and a stack
// of cards (<768px). CSS handles the switch via display: none / flex.

import { useTranslation } from 'react-i18next';
import type { ApiKeySummary } from '../../services/api_keys';
import './api_keys.css';

interface Props {
  keys: ApiKeySummary[];
  onRevoke: (k: ApiKeySummary) => void;
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

function statusFor(k: ApiKeySummary): 'active' | 'revoked' | 'expired' {
  if (k.revoked_at) return 'revoked';
  if (k.is_expired) return 'expired';
  return 'active';
}

function ScopeChips({ scopes }: { scopes: string[] }) {
  return (
    <div className="api-keys-table__scopes">
      {scopes.map((s) => (
        <span
          key={s}
          className={`api-keys-scope-chip${s === '*' ? ' api-keys-scope-chip--wildcard' : ''}`}
        >
          {s}
        </span>
      ))}
    </div>
  );
}

export const ApiKeysList = ({ keys, onRevoke }: Props) => {
  const { t } = useTranslation();
  const never = t('api.keys.list.never') as string;

  return (
    <div className="api-keys-list">
      {/* ---- Desktop / tablet table ---- */}
      <table className="api-keys-table" role="table">
        <thead>
          <tr>
            <th>{t('api.keys.list.name')}</th>
            <th>{t('api.keys.list.prefix')}</th>
            <th className="api-keys-table__col-scopes">{t('api.keys.list.scopes')}</th>
            <th>{t('api.keys.list.lastUsed')}</th>
            <th>{t('api.keys.list.expires')}</th>
            <th>{t('api.keys.list.status')}</th>
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {keys.map((k) => {
            const status = statusFor(k);
            return (
              <tr key={k.id}>
                <td className="api-keys-table__name">{k.name}</td>
                <td>
                  <span className="api-keys-table__prefix">brubru_live_…{k.key_prefix}</span>
                </td>
                <td className="api-keys-table__col-scopes">
                  <ScopeChips scopes={k.scopes} />
                </td>
                <td>
                  <span className={`api-keys-table__${k.last_used_at ? 'date' : 'never'}`}>
                    {formatDate(k.last_used_at, never)}
                  </span>
                </td>
                <td>
                  <span className={`api-keys-table__${k.expires_at ? 'date' : 'never'}`}>
                    {formatDate(k.expires_at, never)}
                  </span>
                </td>
                <td>
                  <span className={`api-keys-table__status api-keys-table__status--${status}`}>
                    {t(`api.keys.list.statusLabels.${status}`)}
                  </span>
                </td>
                <td>
                  {status === 'active' && (
                    <button
                      type="button"
                      className="api-keys-btn api-keys-btn--danger"
                      onClick={() => onRevoke(k)}
                    >
                      {t('api.keys.list.revoke')}
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* ---- Mobile cards ---- */}
      <div className="api-keys-cards">
        {keys.map((k) => {
          const status = statusFor(k);
          return (
            <div key={k.id} className="api-keys-card">
              <div className="api-keys-card__header">
                <h3 className="api-keys-card__name">{k.name}</h3>
                <span className={`api-keys-table__status api-keys-table__status--${status}`}>
                  {t(`api.keys.list.statusLabels.${status}`)}
                </span>
              </div>

              <div className="api-keys-card__row">
                <span className="api-keys-card__label">{t('api.keys.list.prefix')}</span>
                <span className="api-keys-card__value">
                  <span className="api-keys-table__prefix">brubru_live_…{k.key_prefix}</span>
                </span>
              </div>

              <div className="api-keys-card__row">
                <span className="api-keys-card__label">{t('api.keys.list.scopes')}</span>
                <div className="api-keys-card__scopes">
                  {k.scopes.map((s) => (
                    <span
                      key={s}
                      className={`api-keys-scope-chip${s === '*' ? ' api-keys-scope-chip--wildcard' : ''}`}
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>

              <div className="api-keys-card__row">
                <span className="api-keys-card__label">{t('api.keys.list.lastUsed')}</span>
                <span className="api-keys-card__value">{formatDate(k.last_used_at, never)}</span>
              </div>

              <div className="api-keys-card__row">
                <span className="api-keys-card__label">{t('api.keys.list.expires')}</span>
                <span className="api-keys-card__value">{formatDate(k.expires_at, never)}</span>
              </div>

              {status === 'active' && (
                <div className="api-keys-card__actions">
                  <button
                    type="button"
                    className="api-keys-btn api-keys-btn--danger"
                    onClick={() => onRevoke(k)}
                  >
                    {t('api.keys.list.revoke')}
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
