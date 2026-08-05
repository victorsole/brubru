// frontend/src/components/tour/tour_trigger.tsx
import Icon from '@mdi/react';
import { mdiHelpCircleOutline } from '@mdi/js';
import { useTranslation } from 'react-i18next';
import { useTour } from './tour_provider';
import type { TourKey } from '../../stores/tour_store';
import './tour_trigger.css';

interface TourTriggerProps {
  tourKey: TourKey;
  label?: string;
  variant?: 'button' | 'icon' | 'link';
  className?: string;
}

export const TourTrigger = ({
  tourKey,
  label,
  variant = 'button',
  className = '',
}: TourTriggerProps) => {
  const { t } = useTranslation();
  const { triggerTour } = useTour();
  const resolvedLabel = label ?? t('header.takeTour', 'Take a tour');

  const handleClick = () => {
    triggerTour(tourKey, true); // force=true to always show
  };

  if (variant === 'icon') {
    return (
      <button
        type="button"
        className={`tour-trigger tour-trigger--icon ${className}`}
        onClick={handleClick}
        aria-label={resolvedLabel}
        title={resolvedLabel}
      >
        <Icon path={mdiHelpCircleOutline} size={1} />
      </button>
    );
  }

  if (variant === 'link') {
    return (
      <button
        type="button"
        className={`tour-trigger tour-trigger--link ${className}`}
        onClick={handleClick}
      >
        <Icon path={mdiHelpCircleOutline} size={0.8} />
        <span>{resolvedLabel}</span>
      </button>
    );
  }

  return (
    <button
      type="button"
      className={`tour-trigger tour-trigger--button ${className}`}
      onClick={handleClick}
    >
      <Icon path={mdiHelpCircleOutline} size={0.9} />
      <span>{resolvedLabel}</span>
    </button>
  );
};
