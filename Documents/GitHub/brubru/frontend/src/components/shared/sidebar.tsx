// frontend/src/components/shared/sidebar.tsx
import { useEffect } from 'react';
import type { ReactNode } from 'react';
import './sidebar.css';

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  children: ReactNode;
}

export const Sidebar = ({ isOpen, onToggle, children }: SidebarProps) => {
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
        aria-label={isOpen ? 'Close sidebar' : 'Open sidebar'}
        aria-expanded={isOpen}
      >
        <span className={`sidebar__toggle-icon ${isOpen ? 'sidebar__toggle-icon--open' : ''}`}>
          {isOpen ? '←' : '→'}
        </span>
      </button>

      {/* Sidebar */}
      <aside className={`sidebar ${isOpen ? 'sidebar--open' : 'sidebar--closed'}`}>
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
