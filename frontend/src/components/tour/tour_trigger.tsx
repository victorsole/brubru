// frontend/src/components/tour/tour_trigger.tsx
import Icon from '@mdi/react';
import { mdiHelpCircleOutline } from '@mdi/js';
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
  label = 'Take a tour',
  variant = 'button',
  className = '',
}: TourTriggerProps) => {
  const { triggerTour } = useTour();

  const handleClick = () => {
    triggerTour(tourKey, true); // force=true to always show
  };

  if (variant === 'icon') {
    return (
      <button
        type="button"
        className={`tour-trigger tour-trigger--icon ${className}`}
        onClick={handleClick}
        aria-label={label}
        title={label}
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
        <span>{label}</span>
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
      <span>{label}</span>
    </button>
  );
};
