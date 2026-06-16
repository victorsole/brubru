import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import { mdiInstagram } from '@mdi/js';
import './footer.css';

interface FooterProps {
  isSidebarOpen: boolean;
}

export const Footer = ({ isSidebarOpen }: FooterProps) => {
  const { t } = useTranslation();
  const currentYear = new Date().getFullYear();
  const location = useLocation();

  // Only apply sidebar margin on pages that have a LEFT-side collapsible
  // sidebar (Main + Amendator). My EU Bubble's NewsSidebar is on the right,
  // so the footer must not shift — otherwise the footer renders 300px off-axis
  // versus the rest of the page chrome.
  const pagesWithSidebar = ['/chat', '/amendator'];
  const hasSidebar = pagesWithSidebar.includes(location.pathname);
  const isChatApp = location.pathname === '/chat';

  return (
    <footer className={`footer ${isSidebarOpen && hasSidebar ? 'footer--sidebar-open' : ''} ${isChatApp ? 'footer--chat-app' : ''}`}>
      <div className="footer__container">
        <div className="footer__content">
          <div className="footer__section footer__section--brand">
            <div className="footer__brand">
              <img
                src="/assets/beresol-logo.png"
                alt="Beresol BV"
                className="footer__logo"
              />
              <div className="footer__brand-info">
                <p className="footer__copyright">
                  © {currentYear}{' '}
                  <a
                    href="https://beresol.eu"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="footer__beresol-link"
                  >
                    Beresol
                  </a>
                  {' '}BV
                </p>
                <p className="footer__trademark">
                  {t('footer.trademarkLine')}{' '}
                  <a
                    href="https://beresol.eu"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="footer__beresol-link"
                  >
                    Beresol
                  </a>
                  {' '}{t('footer.trademarkRegistered')}
                </p>
              </div>
            </div>
          </div>

          <div className="footer__section footer__section--nav">
            <h4 className="footer__nav-title">{t('footer.links')}</h4>
            <nav className="footer__nav">
              <Link to="/about" className="footer__link">
                {t('footer.about')}
              </Link>
              <a
                href="mailto:hello@beresol.eu"
                className="footer__link"
              >
                {t('footer.contact')}
              </a>
              <Link to="/privacy" className="footer__link">
                {t('footer.privacyPolicy')}
              </Link>
              <Link to="/terms" className="footer__link">
                {t('footer.termsOfService')}
              </Link>
              <Link to="/cookies" className="footer__link">
                {t('footer.cookies')}
              </Link>
              <Link to="/subprocessors" className="footer__link">
                {t('footer.subprocessors')}
              </Link>
              <a
                href="https://www.instagram.com/beresolbv/"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Beresol on Instagram"
                className="footer__link footer__link--social"
              >
                <Icon path={mdiInstagram} size={0.85} />
                <span className="footer__link-label">Instagram</span>
              </a>
            </nav>
          </div>
        </div>
      </div>
    </footer>
  );
};
