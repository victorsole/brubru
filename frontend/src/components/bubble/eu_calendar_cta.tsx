/**
 * EU Calendar CTA Component
 *
 * Call-to-action for White (free) tier users.
 * Displays feature highlights and upgrade button.
 * Follows consultations_cta.tsx pattern.
 *
 * Created: February 2026
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import Icon from '@mdi/react';
import {
  mdiCalendarMonth,
  mdiArrowRight,
  mdiFilterVariant,
  mdiBellOutline,
  mdiLinkVariant,
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
    background: 'linear-gradient(135deg, #bfdbfe 0%, #dbeafe 100%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    margin: '0 auto 1.5rem auto',
  },
  icon: {
    color: '#0693e3',
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
    background: '#eff6ff',
    borderRadius: '12px',
    border: '1px solid #bfdbfe',
  },
  featureIcon: {
    color: '#0693e3',
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
    background: 'linear-gradient(135deg, #0693e3 0%, #0284c7 100%)',
    color: 'white',
    fontSize: '1rem',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'transform 0.2s, box-shadow 0.2s',
    boxShadow: '0 4px 14px rgba(6, 147, 227, 0.4)',
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

export const EUCalendarCTA: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const features = [
    {
      icon: mdiCalendarMonth,
      title: t('bubble.euCalendar.cta.feature1Title', 'Month, Week & Day Views'),
      description: t(
        'bubble.euCalendar.cta.feature1Desc',
        'Navigate EU institutional calendars in your preferred view. See plenary sessions, Council meetings, Commission college meetings, and more at a glance.'
      ),
    },
    {
      icon: mdiFilterVariant,
      title: t('bubble.euCalendar.cta.feature2Title', 'Filter by Institution & Policy Area'),
      description: t(
        'bubble.euCalendar.cta.feature2Desc',
        'Focus on the institutions and policy areas that matter to you. Filter by EP, Council, Commission, and 8 policy areas.'
      ),
    },
    {
      icon: mdiBellOutline,
      title: t('bubble.euCalendar.cta.feature3Title', 'My EU Today Digest'),
      description: t(
        'bubble.euCalendar.cta.feature3Desc',
        'Start your day with a summary of today\'s EU events. Blue tier includes AI-generated briefings.'
      ),
    },
    {
      icon: mdiLinkVariant,
      title: t('bubble.euCalendar.cta.feature4Title', 'Legislative Deep-Linking'),
      description: t(
        'bubble.euCalendar.cta.feature4Desc',
        'Calendar events link directly to Predictions, Tracked Files, and Amendator for related legislative procedures.'
      ),
    },
  ];

  const handleUpgrade = () => {
    navigate('/subscription');
  };

  return (
    <div style={styles.container}>
      <div style={styles.iconWrapper}>
        <Icon path={mdiCalendarMonth} size={2} style={styles.icon} />
      </div>

      <h2 style={styles.title}>
        {t('bubble.euCalendar.cta.title', 'EU Calendar')}
      </h2>

      <p style={styles.description}>
        {t(
          'bubble.euCalendar.cta.description',
          'Track every EU institutional event in one unified calendar. From EP plenary sessions to Council meetings and Commission decisions.'
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
          e.currentTarget.style.boxShadow = '0 6px 20px rgba(6, 147, 227, 0.5)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'translateY(0)';
          e.currentTarget.style.boxShadow = '0 4px 14px rgba(6, 147, 227, 0.4)';
        }}
      >
        {t('bubble.euCalendar.cta.upgrade', 'Upgrade to Yellow')}
        <Icon path={mdiArrowRight} size={0.9} />
      </button>

      <p style={styles.note}>
        {t(
          'bubble.euCalendar.cta.note',
          'Yellow tier unlocks full calendar access. Blue tier adds AI daily digest and advanced features.'
        )}
      </p>
    </div>
  );
};

export default EUCalendarCTA;
