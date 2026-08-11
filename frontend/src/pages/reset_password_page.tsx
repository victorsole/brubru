import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { useAuth } from '../hooks/use_auth';
import './auth_pages.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

type TokenState = 'checking' | 'valid' | 'invalid';

/**
 * "I forgot my password" step two: redeem the emailed token.
 *
 * The token is checked before the form is shown, so an expired link says so
 * up front rather than after the user has chosen and typed a new password.
 */
export const ResetPasswordPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { resetPassword } = useAuth();

  const token = searchParams.get('token') || '';

  const [tokenState, setTokenState] = useState<TokenState>('checking');
  const [invalidReason, setInvalidReason] = useState<string>('not_found');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) {
      setTokenState('invalid');
      setInvalidReason('not_found');
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const response = await axios.get(
          `${API_URL}/api/auth/reset-password/${encodeURIComponent(token)}`
        );
        if (cancelled) return;
        if (response.data?.valid) {
          setTokenState('valid');
        } else {
          setTokenState('invalid');
          setInvalidReason(response.data?.reason || 'not_found');
        }
      } catch {
        if (!cancelled) {
          setTokenState('invalid');
          setInvalidReason('not_found');
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token]);

  // Mirrors the backend rule in schemas/auth_schemas.py so the user is told
  // before the round trip, not after it.
  const validatePassword = (value: string): string | null => {
    if (value.length < 8) return t('auth.errors.passwordTooShort');
    if (!/\d/.test(value)) return t('auth.errors.passwordNeedsDigit');
    if (!/[A-Z]/.test(value)) return t('auth.errors.passwordNeedsUppercase');
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const passwordError = validatePassword(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }
    if (password !== confirmPassword) {
      setError(t('auth.errors.passwordsDoNotMatch'));
      return;
    }

    setLoading(true);
    try {
      await resetPassword(token, password);
      navigate('/my-eu-bubble');
    } catch (err: any) {
      setError(err.response?.data?.detail || t('auth.errors.resetFailed'));
    } finally {
      setLoading(false);
    }
  };

  const invalidMessage =
    invalidReason === 'expired'
      ? t('auth.resetExpired')
      : invalidReason === 'already_used'
        ? t('auth.resetAlreadyUsed')
        : t('auth.resetNotFound');

  return (
    <div className="auth-page">
      <video className="auth-page__video" autoPlay loop muted playsInline>
        <source src="/assets/eu_flag.mp4" type="video/mp4" />
      </video>
      <div className="auth-page__overlay"></div>
      <div className="auth-page__container">
        <div className="auth-page__header">
          <img src="/assets/brubru_mainlogo.png" alt="Brubru" className="auth-page__logo" />
          <h1>{t('auth.resetTitle')}</h1>
          {tokenState === 'valid' && <p>{t('auth.resetSubtitle')}</p>}
        </div>

        {error && <div className="auth-page__error">{error}</div>}

        {tokenState === 'checking' && (
          <p className="auth-page__intro">{t('auth.resetChecking')}</p>
        )}

        {tokenState === 'invalid' && (
          <>
            <div className="auth-page__error">{invalidMessage}</div>
            <Link to="/forgot-password" className="btn btn--primary btn--full">
              {t('auth.resetRequestNew')}
            </Link>
          </>
        )}

        {tokenState === 'valid' && (
          <form onSubmit={handleSubmit} className="auth-page__form">
            <div className="auth-page__field">
              <label htmlFor="password">{t('auth.newPassword')}</label>
              <div className="auth-page__password-wrap">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                  autoFocus
                  disabled={loading}
                />
                <button
                  type="button"
                  className="auth-page__password-toggle"
                  onClick={() => setShowPassword((v) => !v)}
                  disabled={loading}
                  aria-label={showPassword ? t('auth.hidePassword') : t('auth.showPassword')}
                  aria-pressed={showPassword}
                  title={showPassword ? t('auth.hidePassword') : t('auth.showPassword')}
                >
                  <span
                    className={`mdi ${showPassword ? 'mdi-eye-off-outline' : 'mdi-eye-outline'}`}
                    aria-hidden="true"
                  ></span>
                </button>
              </div>
              <small>{t('auth.passwordHint')}</small>
            </div>

            <div className="auth-page__field">
              <label htmlFor="confirmPassword">{t('auth.confirmNewPassword')}</label>
              <input
                id="confirmPassword"
                type={showPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                autoComplete="new-password"
                disabled={loading}
              />
            </div>

            <button type="submit" className="btn btn--primary btn--full" disabled={loading}>
              {loading ? t('auth.resetSaving') : t('auth.resetSubmit')}
            </button>
          </form>
        )}

        <div className="auth-page__footer">
          <p>
            <Link to="/login">{t('auth.backToLogin')}</Link>
          </p>
        </div>
      </div>
    </div>
  );
};
