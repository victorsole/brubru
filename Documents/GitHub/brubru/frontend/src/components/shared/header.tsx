// frontend/src/components/shared/header.tsx
import { Link, useLocation } from 'react-router-dom';
import './header.css';

export const Header = () => {
  const location = useLocation();

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  return (
    <header className="header">
      <div className="header__container">
        <div className="header__brand">
          <Link to="/" className="header__logo">
            Brubru
          </Link>
        </div>

        <nav className="header__nav">
          <Link
            to="/"
            className={`header__nav-link ${isActive('/') ? 'header__nav-link--active' : ''}`}
          >
            Main
          </Link>
          <Link
            to="/amendator"
            className={`header__nav-link ${isActive('/amendator') ? 'header__nav-link--active' : ''}`}
          >
            Amendator
          </Link>
        </nav>

        <div className="header__language">
          <select
            className="header__language-selector"
            defaultValue="en"
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
      </div>
    </header>
  );
};
