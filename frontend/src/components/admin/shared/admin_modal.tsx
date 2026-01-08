// frontend/src/components/admin/shared/admin_modal.tsx
import { useEffect } from 'react';
import './admin_modal.css';

interface AdminModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  size?: 'small' | 'medium' | 'large';
  footer?: React.ReactNode;
}

export const AdminModal = ({
  isOpen,
  onClose,
  title,
  children,
  size = 'medium',
  footer
}: AdminModalProps) => {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }

    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="admin-modal-overlay" onClick={onClose}>
      <div
        className={`admin-modal admin-modal--${size}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="admin-modal__header">
          <h3 className="admin-modal__title">{title}</h3>
          <button
            className="admin-modal__close"
            onClick={onClose}
            aria-label="Close modal"
          >
            <span className="mdi mdi-close"></span>
          </button>
        </div>

        <div className="admin-modal__body">
          {children}
        </div>

        {footer && (
          <div className="admin-modal__footer">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};
