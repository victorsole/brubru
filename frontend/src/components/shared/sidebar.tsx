// frontend/src/components/shared/sidebar.tsx
import { useEffect } from 'react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import './sidebar.css';

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  children: ReactNode;
  width?: number;
}

export const Sidebar = ({ isOpen, onToggle, children, width }: SidebarProps) => {
  const { t } = useTranslation();
  // Auto-collapse on mobile by default
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 768 && isOpen) {
        onToggle();
      }
    };

    // Check on mount
    handleResize();

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <>
      {/* Sidebar Toggle Button */}
      <button
        className="sidebar__toggle"
        onClick={onToggle}
        aria-label={isOpen ? t('common.closeSidebar') : t('common.openSidebar')}
        aria-expanded={isOpen}
      >
        <span className={`sidebar__toggle-icon ${isOpen ? 'sidebar__toggle-icon--open' : ''}`}>
          {isOpen ? '←' : '→'}
        </span>
      </button>

      {/* Sidebar */}
      <aside
        className={`sidebar ${isOpen ? 'sidebar--open' : 'sidebar--closed'}`}
        style={width ? { '--sidebar-width': `${width}px` } as React.CSSProperties : undefined}
      >
        <div className="sidebar__content">
          {children}
        </div>
      </aside>

      {/* Overlay for mobile */}
      {isOpen && (
        <div
          className="sidebar__overlay"
          onClick={onToggle}
          aria-hidden="true"
        />
      )}
    </>
  );
};
