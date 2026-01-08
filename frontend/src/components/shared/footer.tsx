import { Link, useLocation } from 'react-router-dom';
import './footer.css';

interface FooterProps {
  isSidebarOpen: boolean;
}

export const Footer = ({ isSidebarOpen }: FooterProps) => {
  const currentYear = new Date().getFullYear();
  const location = useLocation();

  // Only apply sidebar margin on pages that actually have a sidebar
  const pagesWithSidebar = ['/main', '/amendator', '/my-eu-bubble'];
  const hasSidebar = pagesWithSidebar.includes(location.pathname);

  return (
    <footer className={`footer ${isSidebarOpen && hasSidebar ? 'footer--sidebar-open' : ''}`}>
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
                  Brubru's trademark belongs to{' '}
                  <a
                    href="https://beresol.eu"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="footer__beresol-link"
                  >
                    Beresol
                  </a>
                  {' '}BV and is registered at EUIPO
                </p>
              </div>
            </div>
          </div>

          <div className="footer__section footer__section--nav">
            <h4 className="footer__nav-title">Links</h4>
            <nav className="footer__nav">
              <Link to="/about" className="footer__link">
                About
              </Link>
              <a
                href="mailto:helloberesol@gmail.com"
                className="footer__link"
              >
                Contact
              </a>
              <Link to="/privacy" className="footer__link">
                Privacy Policy
              </Link>
              <Link to="/terms" className="footer__link">
                Terms of Service
              </Link>
              <Link to="/cookies" className="footer__link">
                Cookies
              </Link>
              <Link to="/subprocessors" className="footer__link">
                Subprocessors
              </Link>
            </nav>
          </div>
        </div>
      </div>
    </footer>
  );
};
