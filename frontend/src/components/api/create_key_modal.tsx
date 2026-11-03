// frontend/src/components/api/create_key_modal.tsx
//
// Mint a new API key. Lets the user open every route or only the API bundles
// they pick, and choose an expiry; validates locally, POSTs to /api/me/api-keys,
// and hands the plaintext response back to the parent (which opens the reveal
// modal).

import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import type {
  BundleSummary,
  CreateKeyRequest,
  CreateKeyResponse,
  ScopeCatalogue,
} from '../../services/api_keys';
import { ApiKeysService } from '../../services/api_keys';
import './api_keys.css';

interface Props {
  onClose: () => void;
  onCreated: (result: CreateKeyResponse) => void;
}

export const CreateKeyModal = ({ onClose, onCreated }: Props) => {
  const { t } = useTranslation();

  const [catalogue, setCatalogue] = useState<ScopeCatalogue | null>(null);
  const [loadingCatalogue, setLoadingCatalogue] = useState(true);
  const [catalogueError, setCatalogueError] = useState<string | null>(null);

  const [name, setName] = useState('');
  const [limited, setLimited] = useState(false);
  const [bundles, setBundles] = useState<BundleSummary[]>([]);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [expiresInDays, setExpiresInDays] = useState<number>(180);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nameError, setNameError] = useState<string | null>(null);
  const [scopesError, setScopesError] = useState<string | null>(null);

  // Lock body scroll while modal open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  // ESC to close (but not while submitting)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !submitting) onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, submitting]);

  // Load scope catalogue + pre-check defaults
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const cat = await ApiKeysService.getScopeCatalogue();
        if (cancelled) return;
        setCatalogue(cat);
        ApiKeysService.getBundles()
          .then((list) => { if (!cancelled) setBundles(list); })
          .catch(() => { if (!cancelled) setBundles([]); });
        // Pick 180 if available else the first option
        if (cat.expiry_options_days.includes(180)) setExpiresInDays(180);
        else if (cat.expiry_options_days.length > 0) setExpiresInDays(cat.expiry_options_days[0]);
      } catch (e) {
        if (!cancelled) setCatalogueError(e instanceof Error ? e.message : 'Failed to load');
      } finally {
        if (!cancelled) setLoadingCatalogue(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const toggleBundle = (id: string) => {
    setChosen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setScopesError(null);
  };

  const canSubmit = useMemo(() => {
    return (
      name.trim().length >= 3 &&
      name.trim().length <= 100 &&
      catalogue !== null &&
      (!limited || chosen.size > 0) &&
      !submitting
    );
  }, [name, catalogue, limited, chosen, submitting]);

  const validate = (): boolean => {
    let ok = true;
    const n = name.trim();
    if (n.length < 3 || n.length > 100) {
      setNameError(t('api.keys.create.errors.nameLength') as string);
      ok = false;
    } else {
      setNameError(null);
    }
    if (limited && chosen.size === 0) {
      setScopesError(t('api.keys.create.errors.bundlesRequired') as string);
      ok = false;
    } else {
      setScopesError(null);
    }
    return ok;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setSubmitting(true);
    setError(null);

    const payload: CreateKeyRequest = {
      name: name.trim(),
      scopes: catalogue?.defaults ?? [],
      ...(limited ? { bundles: Array.from(chosen) } : {}),
      expires_in_days: expiresInDays,
    };

    try {
      const result = await ApiKeysService.createKey(payload);
      onCreated(result);  // parent will close us and open reveal modal
    } catch (e) {
      const err = e as { reason_code?: string; message?: string };
      const reason = err.reason_code || 'unknown';
      // Localise some known reason codes; fall back to the server message.
      const localised = t(`api.keys.create.errors.${reason}`, {
        defaultValue: err.message || (t('api.keys.create.errors.unknown') as string),
      });
      setError(localised as string);
      setSubmitting(false);
    }
  };

  const modal = (
    <div
      className="api-keys-modal__backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-title"
      onClick={(e) => { if (e.target === e.currentTarget && !submitting) onClose(); }}
    >
      <form className="api-keys-modal" onSubmit={handleSubmit}>
        <div className="api-keys-modal__header">
          <div>
            <h2 id="create-title" className="api-keys-modal__title">
              {t('api.keys.create.title')}
            </h2>
            <p className="api-keys-modal__subtitle">
              {t('api.keys.create.subtitle')}
            </p>
          </div>
          <button
            type="button"
            className="api-keys-modal__close"
            onClick={onClose}
            disabled={submitting}
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

          {/* --- Name ----------------------------------------------------- */}
          <div className="api-keys-field">
            <label htmlFor="ak-name" className="api-keys-field__label">
              {t('api.keys.create.nameLabel')}
            </label>
            <input
              id="ak-name"
              type="text"
              className={`api-keys-input${nameError ? ' api-keys-input--error' : ''}`}
              placeholder={t('api.keys.create.namePlaceholder') as string}
              value={name}
              onChange={(e) => { setName(e.target.value); setNameError(null); }}
              minLength={3}
              maxLength={100}
              required
              disabled={submitting}
              autoFocus
            />
            {nameError && <span className="api-keys-field__error">{nameError}</span>}
            <span className="api-keys-field__hint">{t('api.keys.create.nameHint')}</span>
          </div>

          {/* --- What it opens ---------------------------------------------- */}
          <div className="api-keys-field">
            <span className="api-keys-field__label">
              {t('api.keys.create.accessLabel')}
            </span>
            {loadingCatalogue && (
              <div className="api-keys-loading">{t('api.keys.create.loadingScopes')}</div>
            )}
            {catalogueError && (
              <div className="api-keys-error-banner">{catalogueError}</div>
            )}
            {catalogue && (
              <div className="api-keys-scopes-grid">
                <label className="api-keys-scope-row">
                  <input type="radio" name="ak-access" checked={!limited} onChange={() => { setLimited(false); setScopesError(null); }} disabled={submitting} />
                  <div>
                    <div><span className="api-keys-scope-row__label">{t('api.keys.create.accessAll')}</span></div>
                    <div className="api-keys-scope-row__desc">{t('api.keys.create.accessAllDesc')}</div>
                  </div>
                </label>
                <label className="api-keys-scope-row">
                  <input type="radio" name="ak-access" checked={limited} onChange={() => setLimited(true)} disabled={submitting || bundles.length === 0} />
                  <div>
                    <div><span className="api-keys-scope-row__label">{t('api.keys.create.accessBundles')}</span></div>
                    <div className="api-keys-scope-row__desc">{t('api.keys.create.accessBundlesDesc')}</div>
                  </div>
                </label>
                {limited && bundles.map((b) => (
                  <label key={b.id} className="api-keys-scope-row api-keys-scope-row--indented">
                    <input type="checkbox" checked={chosen.has(b.id)} onChange={() => toggleBundle(b.id)} disabled={submitting} />
                    <div>
                      <div>
                        <span className="api-keys-scope-row__label">{t(`api.bundles.${b.id}.name`, { defaultValue: b.label })}</span>
                        <span className="api-keys-scope-row__count"> ({t('api.console.resultCount', { count: b.routes })})</span>
                      </div>
                      <div className="api-keys-scope-row__desc">{t(`api.bundles.${b.id}.desc`, { defaultValue: b.description })}</div>
                    </div>
                  </label>
                ))}
              </div>
            )}
            {scopesError && <span className="api-keys-field__error">{scopesError}</span>}
          </div>

          {/* --- Expiry --------------------------------------------------- */}
          <div className="api-keys-field">
            <label htmlFor="ak-expiry" className="api-keys-field__label">
              {t('api.keys.create.expiryLabel')}
            </label>
            <select
              id="ak-expiry"
              className="api-keys-select"
              value={expiresInDays}
              onChange={(e) => setExpiresInDays(Number(e.target.value))}
              disabled={submitting || !catalogue}
            >
              {(catalogue?.expiry_options_days ?? [30, 90, 180, 365]).map((d) => (
                <option key={d} value={d}>
                  {t(`api.keys.create.expiryOptions.${d}`, { defaultValue: `${d} days` })}
                </option>
              ))}
            </select>
            <span className="api-keys-field__hint">{t('api.keys.create.expiryHint')}</span>
          </div>
        </div>

        <div className="api-keys-modal__footer">
          <button
            type="button"
            className="api-keys-btn api-keys-btn--secondary"
            onClick={onClose}
            disabled={submitting}
          >
            {t('api.keys.create.cancel')}
          </button>
          <button
            type="submit"
            className="api-keys-btn api-keys-btn--primary"
            disabled={!canSubmit}
          >
            {submitting ? t('api.keys.create.submitting') : t('api.keys.create.submit')}
          </button>
        </div>
      </form>
    </div>
  );

  return createPortal(modal, document.body);
};
