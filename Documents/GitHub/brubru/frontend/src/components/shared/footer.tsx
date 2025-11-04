import { Link } from 'react-router-dom';
import './footer.css';

export const Footer = () => {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="footer">
      <div className="footer__container">
        <div className="footer__content">
          <div className="footer__section">
            <p className="footer__copyright">
              © {currentYear} Beresol BV
            </p>
            <p className="footer__trademark">
              Brubru's trademark belongs to Beresol BV and is registered at EUIPO
            </p>
          </div>

          <div className="footer__section">
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
