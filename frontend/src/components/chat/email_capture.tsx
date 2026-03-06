// frontend/src/components/chat/email_capture.tsx
import { useState } from 'react';
import './email_capture.css';

const API_BASE_URL = import.meta.env?.VITE_API_URL || (window as any).REACT_APP_API_URL || 'http://localhost:8000';
const CAPTURE_STORAGE_KEY = 'brubru_email_capture_dismissed';

interface EmailCaptureProps {
  preUserId: string;
}

export const EmailCapture = ({ preUserId }: EmailCaptureProps) => {
  const [dismissed, setDismissed] = useState(
    () => localStorage.getItem(CAPTURE_STORAGE_KEY) === 'true'
  );
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleDismiss = () => {
    setDismissed(true);
    localStorage.setItem(CAPTURE_STORAGE_KEY, 'true');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || submitting) return;

    setSubmitting(true);
    try {
      await fetch(`${API_BASE_URL}/api/analytics/preuser-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pre_user_id: preUserId, email: email.trim() }),
      });
      setSubmitted(true);
      localStorage.setItem(CAPTURE_STORAGE_KEY, 'true');
    } catch {
      // Silently fail — never block UX
      setSubmitted(true);
    } finally {
      setSubmitting(false);
    }
  };

  if (dismissed) return null;

  if (submitted) {
    return (
      <div className="email-capture email-capture--success">
        <span className="mdi mdi-check-circle email-capture__icon email-capture__icon--success" />
        <span className="email-capture__text">You are in. We will send you the daily EU brief.</span>
      </div>
    );
  }

  return (
    <div className="email-capture">
      <button
        type="button"
        className="email-capture__close"
        onClick={handleDismiss}
        aria-label="Dismiss"
      >
        <span className="mdi mdi-close" />
      </button>
      <div className="email-capture__content">
        <span className="mdi mdi-email-newsletter email-capture__icon" />
        <div className="email-capture__body">
          <p className="email-capture__title">Get the daily EU brief in your inbox</p>
          <p className="email-capture__subtitle">Top Brussels headlines + AI analysis, every morning. Free.</p>
        </div>
      </div>
      <form className="email-capture__form" onSubmit={handleSubmit}>
        <input
          type="email"
          className="email-capture__input"
          placeholder="your@email.eu"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          aria-label="Email address"
        />
        <button
          type="submit"
          className="email-capture__submit"
          disabled={submitting || !email.trim()}
        >
          {submitting ? 'Subscribing...' : 'Subscribe'}
        </button>
      </form>
    </div>
  );
};
