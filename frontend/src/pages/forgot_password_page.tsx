import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import './auth_pages.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * "I forgot my password" step one: ask for the address.
 *
 * The backend answers identically whether or not the address has an account,
 * so this page must not imply otherwise. On success it always shows the same
 * neutral confirmation.
 */
export const ForgotPasswordPage = () => {
  const { t } = useTranslation();

  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await axios.post(`${API_URL}/api/auth/forgot-password`, { email });
      setSent(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('auth.errors.resetRequestFailed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <video className="auth-page__video" autoPlay loop muted playsInline>
        <source src="/assets/eu_flag.mp4" type="video/mp4" />
      </video>
      <div className="auth-page__overlay"></div>
      <div className="auth-page__container">
        <div className="auth-page__header">
          <img src="/assets/brubru_mainlogo.png" alt="Brubru" className="auth-page__logo" />
          <h1>{t('auth.forgotTitle')}</h1>
          <p>{t('auth.forgotSubtitle')}</p>
        </div>

        {error && <div className="auth-page__error">{error}</div>}

        {sent ? (
          <>
            <div className="auth-page__success">{t('auth.forgotSent')}</div>
            <p className="auth-page__intro">{t('auth.forgotSentHint')}</p>
          </>
        ) : (
          <form onSubmit={handleSubmit} className="auth-page__form">
            <div className="auth-page__field">
              <label htmlFor="email">{t('auth.email')}</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                autoFocus
                disabled={loading}
              />
            </div>

            <button type="submit" className="btn btn--primary btn--full" disabled={loading}>
              {loading ? t('auth.forgotSending') : t('auth.forgotSubmit')}
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
