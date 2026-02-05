// frontend/src/components/shared/feedback_invitation.tsx
import { useState } from 'react';
import Icon from '@mdi/react';
import { mdiMessageTextOutline, mdiEmailOutline, mdiFormTextbox } from '@mdi/js';
import { FeedbackForm } from '../feedback/feedback_form';
import './feedback_invitation.css';

interface FeedbackInvitationProps {
  featureName: string;
  featureDescription?: string;
  variant?: 'card' | 'sidebar';
  className?: string;
}

export const FeedbackInvitation = ({
  featureName,
  featureDescription,
  variant = 'card',
  className = '',
}: FeedbackInvitationProps) => {
  const [showInternalForm, setShowInternalForm] = useState(false);

  // Build mailto link with pre-filled subject and body
  const mailtoSubject = encodeURIComponent(`Feedback on ${featureName}`);
  const mailtoBody = encodeURIComponent(
    `Hi Beresol team,\n\nI would like to share my feedback on ${featureName}:\n\n[Please write your feedback here]\n\nThank you!`
  );
  const mailtoLink = `mailto:hello@beresol.eu?subject=${mailtoSubject}&body=${mailtoBody}`;

  // Default description if not provided
  const description = featureDescription ||
    `Help us improve ${featureName} by sharing your thoughts, suggestions, or reporting any issues. Your feedback helps us create better tools for the EU policy community.`;

  return (
    <section className={`feedback-invitation feedback-invitation--${variant} ${className}`}>
      <div className="feedback-invitation__icon-wrapper">
        <Icon
          path={mdiMessageTextOutline}
          size={variant === 'card' ? 1.5 : 1.2}
          className="feedback-invitation__icon"
        />
      </div>

      <h3 className="feedback-invitation__title">We Value Your Feedback</h3>

      <p className="feedback-invitation__description">{description}</p>

      <div className="feedback-invitation__actions">
        <a
          href={mailtoLink}
          className="feedback-invitation__button feedback-invitation__button--primary"
        >
          <Icon path={mdiEmailOutline} size={0.9} />
          <span>Give Feedback</span>
        </a>

        <button
          type="button"
          className="feedback-invitation__button feedback-invitation__button--secondary"
          onClick={() => setShowInternalForm(!showInternalForm)}
        >
          <Icon path={mdiFormTextbox} size={0.9} />
          <span>{showInternalForm ? 'Close Form' : 'Submit via Form'}</span>
        </button>
      </div>

      {showInternalForm && (
        <div className="feedback-invitation__form-container">
          <FeedbackForm onSuccess={() => setShowInternalForm(false)} />
        </div>
      )}

      <p className="feedback-invitation__footer">
        Your email will be sent to our team at hello@beresol.eu
      </p>
    </section>
  );
};
