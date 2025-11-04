// frontend/src/components/shared/header.tsx
// Shared header component with navigation

import { Link, useLocation } from 'react-router-dom';
import './header.css'; // Component-specific styles

export const Header = () => {
  const location = useLocation();

  return (
    <header className="header">
      <div className="header-container">
        {/* Brubru Logo */}
        <div className="logo">
          <Link to="/">
            <img src="/brubru-logo.svg" alt="Brubru" />
            <span className="logo-text">Brubru</span>
          </Link>
        </div>

        {/* Main Navigation */}
        <nav className="main-nav">
          <Link
            to="/"
            className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}
          >
            Chat
          </Link>

          <Link
            to="/amendator"
            className={`nav-link ${location.pathname === '/amendator' ? 'active' : ''}`}
          >
            Amendator
          </Link>
        </nav>

        {/* User Menu (optional) */}
        <div className="user-menu">
          <button className="user-avatar">
            <img src="/default-avatar.png" alt="User" />
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;
