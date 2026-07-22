// frontend/src/components/shared/impersonation_banner.tsx
// Fixed banner shown while an admin is impersonating another user.
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/use_auth';

export const ImpersonationBanner = () => {
  const { user, adminBackup, exitImpersonation } = useAuth();
  const navigate = useNavigate();

  if (!adminBackup) return null;

  const handleExit = () => {
    exitImpersonation();
    navigate('/admin');
  };

  return (
    <div
      role="status"
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 10000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '1rem',
        padding: '0.6rem 1rem',
        background: '#7c2d12',
        color: '#fff7ed',
        fontSize: '0.9rem',
        boxShadow: '0 -2px 8px rgba(0,0,0,0.25)',
      }}
    >
      <span className="mdi mdi-account-switch" aria-hidden="true"></span>
      <span>
        Viewing Brubru as <strong>{user?.email || user?.full_name || 'unknown user'}</strong>
        {' '}(impersonation, expires after 2h)
      </span>
      <button
        onClick={handleExit}
        style={{
          background: '#fff7ed',
          color: '#7c2d12',
          border: 'none',
          borderRadius: '4px',
          padding: '0.35rem 0.9rem',
          fontWeight: 600,
          cursor: 'pointer',
        }}
      >
        Exit impersonation
      </button>
    </div>
  );
};
