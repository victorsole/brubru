// frontend/src/components/shared/cookie_consent.tsx
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import Icon from '@mdi/react';
import { mdiCookie, mdiCheck, mdiClose } from '@mdi/js';
import './cookie_consent.css';

const COOKIE_CONSENT_KEY = 'brubru_cookie_consent';

type ConsentStatus = 'accepted' | 'declined' | null;

export const CookieConsent = () => {
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
  };

  const handleDecline = () => {
    localStorage.setItem(COOKIE_CONSENT_KEY, 'declined');
    setConsentStatus('declined');
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
              We use cookies to ensure you get the best experience on Brubru.
              Essential cookies are required for the site to function.
              By clicking "Accept", you consent to our use of cookies.{' '}
              <Link to="/cookies" className="cookie-consent__link">
                Learn more
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
              <span>Decline</span>
            </button>
            <button
              type="button"
              className="cookie-consent__button cookie-consent__button--primary"
              onClick={handleAccept}
            >
              <Icon path={mdiCheck} size={0.8} />
              <span>Accept</span>
            </button>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
};
