// frontend/src/components/shared/feedback_invitation.tsx
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();
  const [showInternalForm, setShowInternalForm] = useState(false);

  // Build mailto link with pre-filled subject and body
  const mailtoSubject = encodeURIComponent(t('feedback.subject', { name: featureName }));
  const mailtoBody = encodeURIComponent(t('feedback.bodyTemplate', { name: featureName }));
  const mailtoLink = `mailto:hello@beresol.eu?subject=${mailtoSubject}&body=${mailtoBody}`;

  // Default description if not provided
  const description = featureDescription || t('feedback.defaultDescription', { name: featureName });

  return (
    <section className={`feedback-invitation feedback-invitation--${variant} ${className}`}>
      <div className="feedback-invitation__icon-wrapper">
        <Icon
          path={mdiMessageTextOutline}
          size={variant === 'card' ? 1.5 : 1.2}
          className="feedback-invitation__icon"
        />
      </div>

      <h3 className="feedback-invitation__title">{t('feedback.title')}</h3>

      <p className="feedback-invitation__description">{description}</p>

      <div className="feedback-invitation__actions">
        <a
          href={mailtoLink}
          className="feedback-invitation__button feedback-invitation__button--primary"
        >
          <Icon path={mdiEmailOutline} size={0.9} />
          <span>{t('feedback.giveFeedback')}</span>
        </a>

        <button
          type="button"
          className="feedback-invitation__button feedback-invitation__button--secondary"
          onClick={() => setShowInternalForm(!showInternalForm)}
        >
          <Icon path={mdiFormTextbox} size={0.9} />
          <span>{showInternalForm ? t('feedback.closeForm') : t('feedback.submitViaForm')}</span>
        </button>
      </div>

      {showInternalForm && (
        <div className="feedback-invitation__form-container">
          <FeedbackForm onSuccess={() => setShowInternalForm(false)} />
        </div>
      )}

      <p className="feedback-invitation__footer">{t('feedback.emailFooter')}</p>
    </section>
  );
};
