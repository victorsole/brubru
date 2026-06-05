// frontend/src/pages/api_billing_page.tsx
//
// /api/billing — Anthropic-style euro balance dashboard.
//
// Layout:
//   - Balance card (big number + Top up button + auto-top-up toggle)
//   - Recent usage table (last 50 paid calls)
//   - Recent top-ups list (last 10 Stripe checkouts)
//
// Top-up flow:
//   User picks amount → POST /api/billing/topup → window.location.href to
//   Stripe Checkout → on return, ?topup=success in the URL triggers a refresh
//   of the balance card.

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../hooks/use_auth';
import type {
  AutoTopupConfig,
  BalanceResponse,
  BillingError,
} from '../services/billing';
import { BillingService } from '../services/billing';
import '../components/api/api_keys.css';
import './policy_pages.css';
import './api_billing_page.css';

const PRESET_AMOUNTS = [1, 10, 50, 200] as const;

function formatEur(eur: number): string {
  return new Intl.NumberFormat(undefined, {
    style: 'currency', currency: 'EUR', minimumFractionDigits: 2, maximumFractionDigits: 4,
  }).format(eur);
}

function formatEurSmall(eur: number): string {
  // For per-call costs that may be < 0.01 (we want full precision)
  if (eur < 0.01) {
    return `€${eur.toFixed(4)}`;
  }
  return formatEur(eur);
}

function formatDateTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

// ============================================================================
// Sub-components
// ============================================================================

function BalanceCard({
  balance,
  onTopUp,
}: {
  balance: BalanceResponse;
  onTopUp: () => void;
}) {
  const { t } = useTranslation();
  const isLow = balance.balance_eur < 1;

  return (
    <section className="billing-card">
      <div className="billing-card__row billing-card__row--main">
        <div>
          <div className="billing-card__eyebrow">{t('api.billing.balance.title')}</div>
          <div className={`billing-card__balance${isLow ? ' billing-card__balance--low' : ''}`}>
            {formatEur(balance.balance_eur)}
          </div>
          <div className="billing-card__sub">
            {balance.balance_eur < 0.001
              ? t('api.billing.balance.empty')
              : t('api.billing.balance.calls', { count: Math.floor(balance.balance_eur * 1000) })}
          </div>
        </div>
        <button
          type="button"
          className="api-keys-btn api-keys-btn--primary"
          onClick={onTopUp}
        >
          <span className="mdi mdi-plus" aria-hidden="true" /> {t('api.billing.topup.cta')}
        </button>
      </div>
    </section>
  );
}

function TopupSection({
  onCheckout,
  submitting,
  error,
}: {
  onCheckout: (amount: number) => void;
  submitting: boolean;
  error: string | null;
}) {
  const { t } = useTranslation();
  const [custom, setCustom] = useState('');

  const handlePreset = (amount: number) => {
    if (!submitting) onCheckout(amount);
  };

  const handleCustom = (e: React.FormEvent) => {
    e.preventDefault();
    const amount = Number(custom);
    if (!Number.isFinite(amount) || amount < 1) return;
    onCheckout(amount);
  };

  return (
    <section className="billing-card" id="topup">
      <h3 className="billing-card__heading">{t('api.billing.topup.title')}</h3>
      <p className="billing-card__lede">{t('api.billing.topup.lede')}</p>

      {error && (
        <div className="api-keys-error-banner">
          <span className="mdi mdi-alert-circle-outline" aria-hidden="true" />
          {error}
        </div>
      )}

      <div className="billing-topup__presets">
        {PRESET_AMOUNTS.map((amt) => (
          <button
            key={amt}
            type="button"
            className="billing-topup__preset"
            onClick={() => handlePreset(amt)}
            disabled={submitting}
          >
            <span className="billing-topup__preset-amount">€{amt}</span>
            <span className="billing-topup__preset-calls">
              {t('api.billing.topup.callsApprox', { count: amt * 1000 })}
            </span>
          </button>
        ))}
      </div>

      <form className="billing-topup__custom" onSubmit={handleCustom}>
        <label className="api-keys-field__label" htmlFor="custom-amt">
          {t('api.billing.topup.customLabel')}
        </label>
        <div className="billing-topup__custom-row">
          <input
            id="custom-amt"
            type="number"
            min={1}
            max={5000}
            step={1}
            inputMode="numeric"
            className="api-keys-input"
            placeholder={t('api.billing.topup.customPlaceholder') as string}
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            disabled={submitting}
          />
          <button
            type="submit"
            className="api-keys-btn api-keys-btn--primary"
            disabled={submitting || !custom || Number(custom) < 1}
          >
            {submitting ? t('api.billing.topup.submitting') : t('api.billing.topup.checkout')}
          </button>
        </div>
        <span className="api-keys-field__hint">{t('api.billing.topup.minHint')}</span>
      </form>
    </section>
  );
}

function AutoTopupSection({
  initial,
  onSave,
}: {
  initial: AutoTopupConfig;
  onSave: (config: AutoTopupConfig) => Promise<void>;
}) {
  const { t } = useTranslation();
  const [enabled, setEnabled] = useState(initial.enabled);
  const [threshold, setThreshold] = useState<string>(initial.threshold_eur?.toString() ?? '1');
  const [amount, setAmount] = useState<string>(initial.amount_eur?.toString() ?? '10');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await onSave({
        enabled,
        threshold_eur: enabled ? Number(threshold) : null,
        amount_eur: enabled ? Number(amount) : null,
      });
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2500);
    } catch (e) {
      const err = e as BillingError;
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="billing-card">
      <h3 className="billing-card__heading">{t('api.billing.autoTopup.title')}</h3>
      <p className="billing-card__lede">{t('api.billing.autoTopup.lede')}</p>

      {error && (
        <div className="api-keys-error-banner">
          <span className="mdi mdi-alert-circle-outline" aria-hidden="true" />
          {error}
        </div>
      )}

      <label className="billing-auto-toggle">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
        />
        <span>{t('api.billing.autoTopup.enableLabel')}</span>
      </label>

      {enabled && (
        <div className="billing-auto-fields">
          <div className="api-keys-field">
            <label className="api-keys-field__label" htmlFor="auto-thr">
              {t('api.billing.autoTopup.thresholdLabel')}
            </label>
            <input
              id="auto-thr"
              type="number" min={0} step={1} inputMode="numeric"
              className="api-keys-input"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              disabled={saving}
            />
            <span className="api-keys-field__hint">{t('api.billing.autoTopup.thresholdHint')}</span>
          </div>
          <div className="api-keys-field">
            <label className="api-keys-field__label" htmlFor="auto-amt">
              {t('api.billing.autoTopup.amountLabel')}
            </label>
            <input
              id="auto-amt"
              type="number" min={1} step={1} inputMode="numeric"
              className="api-keys-input"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              disabled={saving}
            />
            <span className="api-keys-field__hint">{t('api.billing.autoTopup.amountHint')}</span>
          </div>
        </div>
      )}

      <div className="billing-auto-save">
        <button
          type="button"
          className="api-keys-btn api-keys-btn--primary"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? t('api.billing.autoTopup.saving') : t('api.billing.autoTopup.save')}
        </button>
        {saved && (
          <span className="billing-auto-saved" role="status">
            <span className="mdi mdi-check" aria-hidden="true" /> {t('api.billing.autoTopup.saved')}
          </span>
        )}
      </div>
    </section>
  );
}

function UsageHistory({ rows }: { rows: BalanceResponse['recent_usage'] }) {
  const { t } = useTranslation();

  if (rows.length === 0) {
    return (
      <section className="billing-card">
        <h3 className="billing-card__heading">{t('api.billing.usage.title')}</h3>
        <p className="billing-card__lede">{t('api.billing.usage.empty')}</p>
      </section>
    );
  }

  return (
    <section className="billing-card">
      <h3 className="billing-card__heading">{t('api.billing.usage.title')}</h3>

      {/* Desktop / tablet */}
      <table className="api-keys-table billing-usage__table">
        <thead>
          <tr>
            <th>{t('api.billing.usage.when')}</th>
            <th>{t('api.billing.usage.endpoint')}</th>
            <th>{t('api.billing.usage.method')}</th>
            <th style={{ textAlign: 'right' }}>{t('api.billing.usage.cost')}</th>
            <th>{t('api.billing.usage.status')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} style={r.refunded ? { opacity: 0.6 } : undefined}>
              <td className="api-keys-table__date">{formatDateTime(r.created_at)}</td>
              <td>
                <span className="api-keys-table__prefix">{r.endpoint}</span>
              </td>
              <td>{r.method}</td>
              <td style={{ textAlign: 'right', fontFamily: 'ui-monospace, monospace' }}>
                {r.refunded ? <s>{formatEurSmall(r.cost_eur)}</s> : formatEurSmall(r.cost_eur)}
              </td>
              <td>
                {r.refunded ? (
                  <span className="api-keys-table__status api-keys-table__status--revoked">
                    {t('api.billing.usage.refunded')}
                  </span>
                ) : r.status_code && r.status_code >= 400 ? (
                  <span className="api-keys-table__status api-keys-table__status--expired">
                    {r.status_code}
                  </span>
                ) : (
                  <span className="api-keys-table__status api-keys-table__status--active">
                    {r.status_code ?? 200}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Mobile */}
      <div className="api-keys-cards billing-usage__cards">
        {rows.map((r) => (
          <div key={r.id} className="api-keys-card" style={r.refunded ? { opacity: 0.6 } : undefined}>
            <div className="api-keys-card__header">
              <h3 className="api-keys-card__name" style={{ fontSize: '0.9rem' }}>{r.endpoint}</h3>
              <span style={{ fontFamily: 'ui-monospace, monospace', fontSize: '0.85rem' }}>
                {r.refunded ? <s>{formatEurSmall(r.cost_eur)}</s> : formatEurSmall(r.cost_eur)}
              </span>
            </div>
            <div className="api-keys-card__row">
              <span className="api-keys-card__label">{t('api.billing.usage.when')}</span>
              <span className="api-keys-card__value">{formatDateTime(r.created_at)}</span>
            </div>
            <div className="api-keys-card__row">
              <span className="api-keys-card__label">{t('api.billing.usage.method')}</span>
              <span className="api-keys-card__value">{r.method}</span>
            </div>
            <div className="api-keys-card__row">
              <span className="api-keys-card__label">{t('api.billing.usage.status')}</span>
              <span className="api-keys-card__value">
                {r.refunded ? t('api.billing.usage.refunded') : r.status_code ?? 200}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function TopupHistory({ rows }: { rows: BalanceResponse['recent_topups'] }) {
  const { t } = useTranslation();
  if (rows.length === 0) {
    return null;
  }
  return (
    <section className="billing-card">
      <h3 className="billing-card__heading">{t('api.billing.history.title')}</h3>
      <ul className="billing-topup__history">
        {rows.map((r) => (
          <li key={r.id} className="billing-topup__history-item">
            <span className="billing-topup__history-amount">{formatEur(r.amount_eur)}</span>
            <span className={`api-keys-table__status api-keys-table__status--${r.status === 'succeeded' ? 'active' : r.status === 'pending' ? 'expired' : 'revoked'}`}>
              {t(`api.billing.history.status.${r.status}`)}
            </span>
            <span className="billing-topup__history-date">{formatDateTime(r.created_at)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ============================================================================
// Page
// ============================================================================

export const ApiBillingPage = () => {
  const { t } = useTranslation();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const [params, setParams] = useSearchParams();

  const [balance, setBalance] = useState<BalanceResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [topupError, setTopupError] = useState<string | null>(null);
  const [topupSubmitting, setTopupSubmitting] = useState(false);
  const [postCheckoutBanner, setPostCheckoutBanner] = useState<'success' | 'cancelled' | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await BillingService.getBalance();
      setBalance(data);
      setLoadError(null);
    } catch (e) {
      const err = e as { message?: string };
      setLoadError(err.message ?? 'Failed to load balance');
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated) return;
    refresh();
  }, [refresh, isAuthenticated]);

  // Handle return from Stripe Checkout
  useEffect(() => {
    const topup = params.get('topup');
    if (!topup) return;
    if (topup === 'success') {
      setPostCheckoutBanner('success');
      // Stripe webhook should have credited the balance; poll for a few seconds.
      const start = Date.now();
      const poll = window.setInterval(async () => {
        await refresh();
        if (Date.now() - start > 8000) window.clearInterval(poll);
      }, 1500);
      return () => window.clearInterval(poll);
    } else if (topup === 'cancelled') {
      setPostCheckoutBanner('cancelled');
    }
    // Clear the query param so a refresh doesn't re-trigger
    const next = new URLSearchParams(params);
    next.delete('topup'); next.delete('session_id');
    setParams(next, { replace: true });
  }, [params, setParams, refresh]);

  const handleTopUp = async (amount: number) => {
    setTopupSubmitting(true);
    setTopupError(null);
    try {
      const res = await BillingService.createTopup(amount);
      window.location.href = res.checkout_url;
    } catch (e) {
      const err = e as BillingError;
      setTopupError(
        t(`api.billing.topup.errors.${err.reason_code}`, { defaultValue: err.message }) as string,
      );
      setTopupSubmitting(false);
    }
  };

  const handleSaveAutoTopup = async (config: AutoTopupConfig) => {
    await BillingService.setAutoTopup(config);
    await refresh();
  };

  const autoTopupInitial = useMemo<AutoTopupConfig>(
    () =>
      balance?.auto_topup ?? { enabled: false, threshold_eur: null, amount_eur: null },
    [balance],
  );

  // ---- Logged-out view ----
  if (!isAuthenticated) {
    return (
      <div className="policy-page api-page">
        <div className="api-page__layout">
          <div className="api-page__main">
            <div className="api-keys-signin-cta" style={{ marginTop: '4rem' }}>
              <span className="mdi mdi-wallet-outline api-keys-signin-cta__icon" aria-hidden="true" />
              <h1 className="api-keys-signin-cta__title">{t('api.billing.signedOut.title')}</h1>
              <p className="api-keys-signin-cta__body">{t('api.billing.signedOut.body')}</p>
              <Link to="/login" className="api-keys-btn api-keys-btn--primary">
                <span className="mdi mdi-login" aria-hidden="true" /> {t('api.keys.signedOut.cta')}
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ---- Logged-in view ----
  return (
    <div className="policy-page api-page api-billing-page">
      <div className="api-page__layout">
        <div className="api-page__main api-billing-page__main">
          <div className="api-page__eyebrow">{t('api.eyebrow')}</div>
          <h1 className="policy-page__title">
            {t('api.billing.titlePre')}{' '}
            <span className="api-page__accent">{t('api.billing.titleAccent')}</span>
          </h1>
          <p className="api-page__lede">{t('api.billing.lede')}</p>

          {postCheckoutBanner === 'success' && (
            <div className="api-keys-error-banner" style={{ background: '#e7f6ee', borderColor: '#a5d6a7', color: '#1c7a3e' }}>
              <span className="mdi mdi-check-circle-outline" aria-hidden="true" />
              {t('api.billing.banner.success')}
            </div>
          )}
          {postCheckoutBanner === 'cancelled' && (
            <div className="api-keys-error-banner" style={{ background: '#fff4e5', borderColor: '#ffe0b2', color: '#b56a00' }}>
              <span className="mdi mdi-information-outline" aria-hidden="true" />
              {t('api.billing.banner.cancelled')}
            </div>
          )}

          {loadError && (
            <div className="api-keys-error-banner">
              <span className="mdi mdi-alert-circle-outline" aria-hidden="true" />
              {loadError}
            </div>
          )}

          {!balance ? (
            <div className="api-keys-loading">{t('api.billing.loading')}</div>
          ) : (
            <>
              <BalanceCard balance={balance} onTopUp={() => {
                const el = document.getElementById('topup');
                if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }} />
              <TopupSection
                onCheckout={handleTopUp}
                submitting={topupSubmitting}
                error={topupError}
              />
              <AutoTopupSection initial={autoTopupInitial} onSave={handleSaveAutoTopup} />
              <UsageHistory rows={balance.recent_usage} />
              <TopupHistory rows={balance.recent_topups} />
            </>
          )}

          <div className="api-page__cta-row" style={{ marginTop: '2rem' }}>
            <Link to="/api" className="api-keys-btn api-keys-btn--secondary">
              <span className="mdi mdi-arrow-left" aria-hidden="true" /> {t('api.billing.backToApi')}
            </Link>
            <Link to="/api/docs" className="api-keys-btn api-keys-btn--secondary">
              <span className="mdi mdi-book-open-variant" aria-hidden="true" /> {t('api.cta.reference')}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ApiBillingPage;
