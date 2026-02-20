// frontend/src/components/shared/header.tsx
import { useState, useRef, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiChatProcessingOutline,
  mdiGlassMugVariant,
  mdiFileEditOutline,
  mdiScaleBalance,
  mdiPiggyBankOutline
} from '@mdi/js';
import { useAuth } from '../../hooks/use_auth';
import { SUPPORTED_LANGUAGES, LANGUAGE_NAMES } from '../../i18n/config';
import type { SupportedLanguage } from '../../i18n/config';
import { useTour } from '../tour';
import { NotificationDropdown } from './notification_dropdown';
import './header.css';

export const Header = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { t, i18n } = useTranslation();
  const [showDropdown, setShowDropdown] = useState(false);
  const [isLoadingLanguage, setIsLoadingLanguage] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { triggerTour } = useTour();

  // Check if user has Blue tier access (blue or admin)
  const hasBlueAccess = user?.subscription_tier === 'blue' || user?.subscription_tier === 'admin';

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    };

    if (showDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showDropdown]);

  const handleLogout = () => {
    logout();
    setShowDropdown(false);
    navigate('/');
  };

  const handleStartTour = () => {
    setShowDropdown(false);
    // Determine which tour to show based on current page
    const path = location.pathname;
    if (path === '/main') {
      triggerTour('welcome', true);
    } else if (path === '/amendator') {
      triggerTour('amendator', true);
    } else if (path === '/my-eu-bubble') {
      triggerTour('eu_bubble', true);
    } else if (path === '/eulawcomply') {
      triggerTour('eu_comply', true);
    } else if (path === '/tenderator') {
      triggerTour('tenderator', true);
    } else {
      triggerTour('welcome', true);
    }
  };

  const handleLanguageChange = async (event: React.ChangeEvent<HTMLSelectElement>) => {
    const newLanguage = event.target.value as SupportedLanguage;
    setIsLoadingLanguage(true);

    try {
      await i18n.changeLanguage(newLanguage);
    } catch (error) {
      console.error('[ERROR] Failed to change language:', error);
    } finally {
      setIsLoadingLanguage(false);
    }
  };

  return (
    <header className="header">
      <div className="header__container">
        <div className="header__brand">
          <Link to="/subscription" className="header__logo">
            <img
              src="/assets/brubru_mainlogo.png"
              alt="Brubru Logo"
              className="header__logo-image"
            />
            <span className="header__logo-text">Brubru</span>
          </Link>
        </div>

        <nav className="header__nav">
          {[
            { path: '/main', icon: mdiChatProcessingOutline, labelKey: 'header.main', color: 'blue' },
            { path: '/my-eu-bubble', icon: mdiGlassMugVariant, labelKey: 'header.myEuBubble', color: 'purple' },
            { path: '/amendator', icon: mdiFileEditOutline, labelKey: 'header.amendator', color: 'green' },
            { path: '/eulawcomply', icon: mdiScaleBalance, labelKey: 'header.euLawComply', color: 'silver' },
            { path: '/tenderator', icon: mdiPiggyBankOutline, labelKey: 'header.tenderator', color: 'gold', requiresBlue: true },
          ].map((item) => {
            if (item.requiresBlue && !hasBlueAccess) return null;
            const active = isActive(item.path);

            // Pre-user: disable all nav buttons except Main (chat)
            if (!user && item.path !== '/main') {
              return (
                <span
                  key={item.path}
                  className={`header__nav-icon-btn header__nav-icon-btn--${item.color} header__nav-icon-btn--disabled`}
                  data-tooltip={t('header.onlyForUsers', { feature: t(item.labelKey) })}
                >
                  <Icon path={item.icon} size={1} />
                  <span className="header__nav-icon-label">{t(item.labelKey)}</span>
                </span>
              );
            }

            return (
              <Link
                key={item.path}
                to={item.path}
                className={`header__nav-icon-btn header__nav-icon-btn--${item.color}${active ? ' header__nav-icon-btn--active' : ''}`}
                aria-label={t(item.labelKey)}
              >
                <Icon path={item.icon} size={1} />
                <span className="header__nav-icon-label">{t(item.labelKey)}</span>
              </Link>
            );
          })}
        </nav>

        <div className="header__actions">
          <div className="header__language">
            <select
              className="header__language-selector"
              value={i18n.language || 'en'}
              onChange={handleLanguageChange}
              disabled={isLoadingLanguage}
              aria-label="Select language"
            >
              {SUPPORTED_LANGUAGES.map((lang) => (
                <option key={lang} value={lang}>
                  {LANGUAGE_NAMES[lang]}
                </option>
              ))}
            </select>
          </div>

          {!user && (
            <div className="header__auth-buttons">
              <Link to="/signup" className="header__signup-btn">{t('header.signUpFree')}</Link>
              <Link to="/login" className="header__login-btn">{t('header.logIn')}</Link>
            </div>
          )}

          {user && (
            <>
              <NotificationDropdown />
              <div className="header__user" ref={dropdownRef}>
                <button
                  className="header__user-button"
                  onClick={() => setShowDropdown(!showDropdown)}
                  aria-label="User menu"
                >
                  <img
                    src="/assets/brubru_icon.png"
                    alt="User"
                    className="header__user-icon"
                  />
                </button>

              {showDropdown && (
                <div className="header__user-dropdown">
                  <div className="header__user-info">
                    <div className="header__user-name">{user.full_name || user.email}</div>
                    <div className="header__user-email">{user.email}</div>
                  </div>
                  <div className="header__user-divider"></div>
                  <Link
                    to="/profile"
                    className="header__user-menu-item"
                    onClick={() => setShowDropdown(false)}
                  >
                    <svg className="header__user-menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                    {t('header.viewProfile')}
                  </Link>
                  <Link
                    to="/subscription"
                    className="header__user-menu-item"
                    onClick={() => setShowDropdown(false)}
                  >
                    <svg className="header__user-menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                    </svg>
                    {t('header.subscription')}
                  </Link>
                  <button
                    className="header__user-menu-item"
                    onClick={handleStartTour}
                  >
                    <svg className="header__user-menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {t('header.takeTour', 'Take a tour')}
                  </button>
                  <button
                    className="header__user-menu-item header__user-menu-item--logout"
                    onClick={handleLogout}
                  >
                    <svg className="header__user-menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                    </svg>
                    {t('header.logOut')}
                  </button>
                </div>
              )}
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
};
