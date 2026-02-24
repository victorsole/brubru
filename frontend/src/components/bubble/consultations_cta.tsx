/**
 * Consultations CTA Component
 *
 * Call-to-action component for White (free) tier users.
 * Displays feature highlights and upgrade button.
 *
 * Created: January 2026
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import Icon from '@mdi/react';
import {
  mdiCalendarCollapseHorizontal,
  mdiArrowRight,
  mdiBellRingOutline,
  mdiFileDocumentEditOutline,
  mdiChartTimelineVariant,
} from '@mdi/js';

// ============================================================================
// Styles
// ============================================================================

const styles = {
  container: {
    maxWidth: '600px',
    margin: '3rem auto',
    padding: '2rem',
    textAlign: 'center' as const,
  },
  iconWrapper: {
    width: '80px',
    height: '80px',
    borderRadius: '50%',
    background: 'linear-gradient(135deg, #fed7aa 0%, #ffedd5 100%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    margin: '0 auto 1.5rem auto',
  },
  icon: {
    color: '#f97316',
  },
  title: {
    fontSize: '1.5rem',
    fontWeight: 600,
    color: '#111827',
    margin: '0 0 0.75rem 0',
  },
  description: {
    fontSize: '1rem',
    color: '#6b7280',
    margin: '0 0 2rem 0',
    lineHeight: 1.6,
  },
  features: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '1rem',
    marginBottom: '2rem',
    textAlign: 'left' as const,
  },
  feature: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '0.75rem',
    padding: '1rem',
    background: '#fff7ed',
    borderRadius: '12px',
    border: '1px solid #fed7aa',
  },
  featureIcon: {
    color: '#f97316',
    flexShrink: 0,
    marginTop: '0.125rem',
  },
  featureContent: {
    flex: 1,
  },
  featureTitle: {
    fontSize: '0.9375rem',
    fontWeight: 600,
    color: '#111827',
    margin: '0 0 0.25rem 0',
  },
  featureDescription: {
    fontSize: '0.8125rem',
    color: '#6b7280',
    margin: 0,
    lineHeight: 1.5,
  },
  upgradeBtn: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.5rem',
    padding: '0.875rem 2rem',
    borderRadius: '8px',
    border: 'none',
    background: 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)',
    color: 'white',
    fontSize: '1rem',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'transform 0.2s, box-shadow 0.2s',
    boxShadow: '0 4px 14px rgba(249, 115, 22, 0.4)',
  },
  note: {
    fontSize: '0.8125rem',
    color: '#9ca3af',
    marginTop: '1rem',
  },
};

// ============================================================================
// Component
// ============================================================================

export const ConsultationsCTA: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const features = [
    {
      icon: mdiCalendarCollapseHorizontal,
      title: t('bubble.consultations.cta.feature1Title', 'Track Open Consultations'),
      description: t(
        'bubble.consultations.cta.feature1Desc',
        'Monitor all EC public consultations in your policy areas. Get notified about deadlines and new opportunities to participate.'
      ),
    },
    {
      icon: mdiBellRingOutline,
      title: t('bubble.consultations.cta.feature2Title', 'Deadline Reminders'),
      description: t(
        'bubble.consultations.cta.feature2Desc',
        'Receive reminders 7 days, 3 days, and 1 day before consultation deadlines. Never miss an opportunity to have your say.'
      ),
    },
    {
      icon: mdiFileDocumentEditOutline,
      title: t('bubble.consultations.cta.feature3Title', 'AI-Powered Proposals'),
      description: t(
        'bubble.consultations.cta.feature3Desc',
        'Generate personalised response proposals based on your documents and position papers. (Professional plan)'
      ),
    },
    {
      icon: mdiChartTimelineVariant,
      title: t('bubble.consultations.cta.feature4Title', 'Outcome Analysis'),
      description: t(
        'bubble.consultations.cta.feature4Desc',
        'Track consultation outcomes and see how well they align with your submitted positions. (Professional plan)'
      ),
    },
  ];

  const handleUpgrade = () => {
    navigate('/subscription');
  };

  return (
    <div style={styles.container}>
      <div style={styles.iconWrapper}>
        <Icon path={mdiCalendarCollapseHorizontal} size={2} style={styles.icon} />
      </div>

      <h2 style={styles.title}>
        {t('bubble.consultations.cta.title', 'EC Public Consultations')}
      </h2>

      <p style={styles.description}>
        {t(
          'bubble.consultations.cta.description',
          'Participate in EU policy-making with AI-powered assistance. Track consultations, receive deadline reminders, and generate personalised response proposals.'
        )}
      </p>

      <div style={styles.features}>
        {features.map((feature, index) => (
          <div key={index} style={styles.feature}>
            <Icon path={feature.icon} size={1} style={styles.featureIcon} />
            <div style={styles.featureContent}>
              <h3 style={styles.featureTitle}>{feature.title}</h3>
              <p style={styles.featureDescription}>{feature.description}</p>
            </div>
          </div>
        ))}
      </div>

      <button
        style={styles.upgradeBtn}
        onClick={handleUpgrade}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = 'translateY(-2px)';
          e.currentTarget.style.boxShadow = '0 6px 20px rgba(249, 115, 22, 0.5)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'translateY(0)';
          e.currentTarget.style.boxShadow = '0 4px 14px rgba(249, 115, 22, 0.4)';
        }}
      >
        {t('bubble.consultations.cta.upgrade', 'Subscribe')}
        <Icon path={mdiArrowRight} size={0.9} />
      </button>

      <p style={styles.note}>
        {t(
          'bubble.consultations.cta.note',
          'Subscribe to unlock tracking and notifications. Professional plan adds AI proposals and alignment analysis.'
        )}
      </p>
    </div>
  );
};

export default ConsultationsCTA;
