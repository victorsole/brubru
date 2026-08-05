import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import { GoogleLogin } from '@react-oauth/google';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../hooks/use_auth';
import './auth_pages.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

type ClaimInfo = {
  valid: boolean;
  first_name?: string | null;
  full_name?: string | null;
  organization?: string | null;
  role_title?: string | null;
  pre_provisioned_at?: string | null;
  subscription_tier?: string | null;
  private_guide_status?: string | null;
  reason?: string | null;
};

// Maps API reason codes to i18n keys + English defaults; translated at render time.
const REASON_COPY: Record<string, { key: string; defaultText: string }> = {
  not_found: {
    key: 'claim.reason.notFound',
    defaultText:
      'This claim link does not match a pre-provisioned Brubru profile.',
  },
  expired: {
    key: 'claim.reason.expired',
    defaultText:
      'This claim link has expired. Reach out to hello@beresol.eu and we will issue a fresh one.',
  },
  already_claimed: {
    key: 'claim.reason.alreadyClaimed',
    defaultText: 'This profile has already been claimed. Sign in normally instead.',
  },
};

export const ClaimPage = () => {
  const { t } = useTranslation();
  const { token = '' } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { loginWithGoogle, loginWithLinkedIn } = useAuth();

  const [info, setInfo] = useState<ClaimInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');

  // Password fallback fields
  const [showPassword, setShowPassword] = useState(false);
  const [pwEmail, setPwEmail] = useState('');
  const [pwPassword, setPwPassword] = useState('');
  const [pwBusy, setPwBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const fetchInfo = async () => {
      try {
        const r = await axios.get(`${API_URL}/api/auth/claim/${token}`);
        if (!cancelled) setInfo(r.data as ClaimInfo);
      } catch (e: any) {
        if (!cancelled) {
          setError(
            e.response?.data?.detail ||
              t('claim.loadError', 'Unable to load the claim link. Please try again later.'),
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchInfo();
    return () => {
      cancelled = true;
    };
  }, [token]);

  // Receive LinkedIn OAuth result from popup (mirrors login_page.tsx).
  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return;
      if (event.data?.type === 'LINKEDIN_AUTH_SUCCESS') {
        sessionStorage.setItem(
          'brubru_previous_login',
          event.data.previous_last_login || '',
        );
        // The hook's persistence layer will be populated by the popup write.
        navigate('/my-eu-bubble');
      }
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [navigate]);

  const handleGoogleSuccess = async (credentialResponse: any) => {
    try {
      await loginWithGoogle(credentialResponse, token);
      navigate('/my-eu-bubble');
    } catch (e: any) {
      setError(
        e.response?.data?.detail ||
          t('claim.googleFailed', 'Google sign-in failed. Try LinkedIn or the password fallback.'),
      );
    }
  };

  const handleLinkedIn = async () => {
    await loginWithLinkedIn(token);
  };

  const handlePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwBusy(true);
    setError('');
    try {
      const r = await axios.post(
        `${API_URL}/api/auth/claim/${token}/password`,
        { email: pwEmail, password: pwPassword },
      );
      // Hand the token to the auth store the same way useAuth.login does.
      sessionStorage.setItem(
        'brubru_previous_login',
        r.data.previous_last_login || '',
      );
      // Persist auth via the same key zustand uses.
      try {
        const persisted = JSON.parse(
          localStorage.getItem('brubru-auth') || '{}',
        );
        persisted.state = {
          ...(persisted.state || {}),
          token: r.data.access_token,
          user: r.data.user,
          isAuthenticated: true,
        };
        localStorage.setItem('brubru-auth', JSON.stringify(persisted));
      } catch {
        /* ignore */
      }
      window.location.href = '/my-eu-bubble';
    } catch (e: any) {
      setError(
        e.response?.data?.detail ||
          t('claim.passwordError', 'Could not set the password. Double-check the email and try again.'),
      );
    } finally {
      setPwBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="auth-page">
        <div className="auth-page__card">
          <h2 className="auth-page__title">{t('claim.loading', 'Loading your Brubru profile...')}</h2>
        </div>
      </div>
    );
  }

  if (!info || !info.valid) {
    const reasonCopy = info?.reason ? REASON_COPY[info.reason] : undefined;
    const reason = reasonCopy ? t(reasonCopy.key, reasonCopy.defaultText) : error;
    return (
      <div className="auth-page">
        <div className="auth-page__card">
          <h2 className="auth-page__title">{t('claim.notActive', 'Claim link not active')}</h2>
          <p className="auth-page__subtitle">{reason}</p>
          <p className="auth-page__subtitle">
            <a href="/login">{t('claim.signIn', 'Sign in')}</a> · <a href="/signup">{t('claim.createAccount', 'Create an account')}</a>
          </p>
        </div>
      </div>
    );
  }

  const greeting = info.first_name
    ? t('claim.hello', 'Hello {{name}}', { name: info.first_name })
    : t('claim.welcome', 'Welcome to Brubru');

  const configuredFor = info.organization
    ? t('claim.configuredForAt', '{{name}} at {{org}}', {
        name: info.full_name || t('claim.you', 'you'),
        org: info.organization,
      })
    : info.full_name || t('claim.you', 'you');

  return (
    <div className="auth-page">
      <div className="auth-page__card">
        <h2 className="auth-page__title">{greeting}</h2>
        <p className="auth-page__subtitle">
          {t(
            'claim.subtitle',
            'Brubru is already configured for {{who}}. Sign in below to claim it - your policy interests, EU file tracks, news feeds and private knowledge guides are pre-loaded.',
            { who: configuredFor },
          )}
        </p>

        {error && <div className="auth-page__error">{error}</div>}

        <div className="auth-page__oauth" style={{ marginTop: '1.5rem' }}>
          <div className="google-login-wrapper">
            <GoogleLogin
              onSuccess={handleGoogleSuccess}
              onError={() => setError(t('claim.googleCancelled', 'Google sign-in was cancelled.'))}
              size="large"
              text="continue_with"
            />
          </div>
          <button
            type="button"
            onClick={handleLinkedIn}
            className="btn btn--oauth btn--oauth-linkedin"
          >
            {t('claim.continueLinkedIn', 'Continue with LinkedIn')}
          </button>
        </div>

        <div className="auth-page__divider"><span>{t('claim.or', 'or')}</span></div>

        {!showPassword ? (
          <button
            type="button"
            className="btn btn--link"
            onClick={() => setShowPassword(true)}
          >
            {t('claim.passwordFallback', 'Set an email and password instead')}
          </button>
        ) : (
          <form onSubmit={handlePassword} className="auth-page__form">
            <label>
              {t('auth.email', 'Email')}
              <input
                type="email"
                required
                value={pwEmail}
                onChange={(e) => setPwEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </label>
            <label>
              {t('auth.password', 'Password')}
              <input
                type="password"
                required
                minLength={8}
                value={pwPassword}
                onChange={(e) => setPwPassword(e.target.value)}
                placeholder={t('claim.passwordPlaceholder', 'Min 8 chars, 1 digit, 1 uppercase')}
              />
            </label>
            <button type="submit" className="btn btn--primary" disabled={pwBusy}>
              {pwBusy ? t('claim.claiming', 'Claiming...') : t('claim.claimButton', 'Claim my profile')}
            </button>
          </form>
        )}

        <p className="auth-page__legal" style={{ marginTop: '2rem' }}>
          {t(
            'claim.legal',
            'Pre-provisioned profile created via private invitation. Tier: {{tier}}. Questions? hello@beresol.eu.',
            { tier: info.subscription_tier || 'white' },
          )}
        </p>
      </div>
    </div>
  );
};
