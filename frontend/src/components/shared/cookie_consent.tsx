// frontend/src/components/shared/cookie_consent.tsx
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import { mdiCookie, mdiCheck, mdiClose } from '@mdi/js';
import './cookie_consent.css';

const COOKIE_CONSENT_KEY = 'brubru_cookie_consent';

type ConsentStatus = 'accepted' | 'declined' | null;

export const CookieConsent = () => {
  const { t } = useTranslation();
  const [consentStatus, setConsentStatus] = useState<ConsentStatus | 'pending'>('pending');

  useEffect(() => {
    const stored = localStorage.getItem(COOKIE_CONSENT_KEY);
    if (stored === 'accepted' || stored === 'declined') {
      setConsentStatus(stored);
    } else {
      setConsentStatus(null);
    }
  }, []);

  const handleAccept = () => {
    localStorage.setItem(COOKIE_CONSENT_KEY, 'accepted');
    setConsentStatus('accepted');
    // Tell analytics.js it may load now. Without this the banner was decorative:
    // it wrote localStorage and nothing read it, while the tracker had already
    // fired on first paint.
    window.dispatchEvent(new Event('brubru-consent-accepted'));
  };

  const handleDecline = () => {
    localStorage.setItem(COOKIE_CONSENT_KEY, 'declined');
    setConsentStatus('declined');
    window.dispatchEvent(new Event('brubru-consent-declined'));
  };

  // Don't render anything while checking localStorage or if consent already given
  if (consentStatus === 'pending' || consentStatus === 'accepted' || consentStatus === 'declined') {
    return null;
  }

  return (
    <AnimatePresence>
      <motion.div
        className="cookie-consent"
        initial={{ y: 100, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 100, opacity: 0 }}
        transition={{ duration: 0.3, ease: [0.25, 0.1, 0.25, 1] }}
      >
        <div className="cookie-consent__container">
          <div className="cookie-consent__icon-wrapper">
            <Icon path={mdiCookie} size={1.2} className="cookie-consent__icon" />
          </div>

          <div className="cookie-consent__content">
            <p className="cookie-consent__text">
              {t('cookies.message')}{' '}
              <Link to="/cookies" className="cookie-consent__link">
                {t('common.learnMore')}
              </Link>
            </p>
          </div>

          <div className="cookie-consent__actions">
            <button
              type="button"
              className="cookie-consent__button cookie-consent__button--secondary"
              onClick={handleDecline}
            >
              <Icon path={mdiClose} size={0.8} />
              <span>{t('common.decline')}</span>
            </button>
            <button
              type="button"
              className="cookie-consent__button cookie-consent__button--primary"
              onClick={handleAccept}
            >
              <Icon path={mdiCheck} size={0.8} />
              <span>{t('common.accept')}</span>
            </button>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
};
