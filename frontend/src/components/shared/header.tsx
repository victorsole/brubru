// frontend/src/components/shared/header.tsx
import { useState, useRef, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/use_auth';
import { translationService } from '../../services/translation_service';
import { useTour } from '../tour';
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
    const newLanguage = event.target.value;
    console.log('🔄 Header: Language change requested to:', newLanguage);
    console.log('📍 Current language:', i18n.language);
    setIsLoadingLanguage(true);

    try {
      await translationService.changeLanguage(newLanguage);
      console.log('✅ Header: Language change complete');
    } catch (error) {
      console.error('❌ Header: Failed to change language:', error);
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
          <Link
            to="/main"
            className={`header__nav-link ${isActive('/main') ? 'header__nav-link--active' : ''}`}
          >
            {t('header.main')}
          </Link>
          <Link
            to="/my-eu-bubble"
            className={`header__nav-link ${isActive('/my-eu-bubble') ? 'header__nav-link--active' : ''}`}
          >
            {t('header.myEuBubble')}
          </Link>
          <Link
            to="/amendator"
            className={`header__nav-link ${isActive('/amendator') ? 'header__nav-link--active' : ''}`}
          >
            {t('header.amendator')}
          </Link>
          <Link
            to="/eulawcomply"
            className={`header__nav-link ${isActive('/eulawcomply') ? 'header__nav-link--active' : ''}`}
          >
            {t('header.euLawComply')}
          </Link>
          {hasBlueAccess && (
            <Link
              to="/tenderator"
              className={`header__nav-link ${isActive('/tenderator') ? 'header__nav-link--active' : ''}`}
            >
              {t('header.tenderator')}
            </Link>
          )}
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
              <option value="bg">Български (Bulgarian)</option>
              <option value="hr">Hrvatski (Croatian)</option>
              <option value="cs">Čeština (Czech)</option>
              <option value="da">Dansk (Danish)</option>
              <option value="nl">Nederlands (Dutch)</option>
              <option value="en">English</option>
              <option value="et">Eesti (Estonian)</option>
              <option value="fi">Suomi (Finnish)</option>
              <option value="fr">Français (French)</option>
              <option value="de">Deutsch (German)</option>
              <option value="el">Ελληνικά (Greek)</option>
              <option value="hu">Magyar (Hungarian)</option>
              <option value="ga">Gaeilge (Irish)</option>
              <option value="it">Italiano (Italian)</option>
              <option value="lv">Latviešu (Latvian)</option>
              <option value="lt">Lietuvių (Lithuanian)</option>
              <option value="mt">Malti (Maltese)</option>
              <option value="pl">Polski (Polish)</option>
              <option value="pt">Português (Portuguese)</option>
              <option value="ro">Română (Romanian)</option>
              <option value="sk">Slovenčina (Slovak)</option>
              <option value="sl">Slovenščina (Slovenian)</option>
              <option value="es">Español (Spanish)</option>
              <option value="sv">Svenska (Swedish)</option>
              <option value="ca">Català (Catalan)</option>
            </select>
          </div>

          {user && (
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
          )}
        </div>
      </div>
    </header>
  );
};
