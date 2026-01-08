// frontend/src/components/tour/tour_provider.tsx
import { useCallback } from 'react';
import Joyride, { STATUS, EVENTS, ACTIONS } from 'react-joyride';
import type { Step, CallBackProps } from 'react-joyride';
import { useTourStore } from '../../stores/tour_store';
import type { TourKey } from '../../stores/tour_store';
import { TourTooltip } from './tour_tooltip';
import { tourSteps } from './tour_steps';

interface TourProviderProps {
  children: React.ReactNode;
}

export const TourProvider = ({ children }: TourProviderProps) => {
  const {
    currentTour,
    currentStep,
    isRunning,
    setStep,
    completeTour,
    skipTour,
    stopTour,
  } = useTourStore();

  // Get steps for current tour
  const steps: Step[] = currentTour ? tourSteps[currentTour] || [] : [];

  // Handle Joyride callbacks
  const handleCallback = useCallback(
    (data: CallBackProps) => {
      const { action, index, status, type } = data;

      // Handle tour completion
      if (status === STATUS.FINISHED) {
        if (currentTour) {
          completeTour(currentTour);
        }
        return;
      }

      // Handle skip
      if (status === STATUS.SKIPPED) {
        if (currentTour) {
          skipTour(currentTour);
        }
        return;
      }

      // Handle close button
      if (action === ACTIONS.CLOSE) {
        stopTour();
        return;
      }

      // Handle step changes
      if (type === EVENTS.STEP_AFTER) {
        if (action === ACTIONS.NEXT) {
          setStep(index + 1);
        } else if (action === ACTIONS.PREV) {
          setStep(index - 1);
        }
      }

      // Handle target not found - skip to next step
      if (type === EVENTS.TARGET_NOT_FOUND) {
        setStep(index + 1);
      }
    },
    [currentTour, completeTour, skipTour, stopTour, setStep]
  );

  return (
    <>
      {children}
      <Joyride
        steps={steps}
        stepIndex={currentStep}
        run={isRunning}
        continuous
        showSkipButton
        showProgress
        disableOverlayClose
        disableCloseOnEsc={false}
        spotlightClicks
        callback={handleCallback}
        tooltipComponent={TourTooltip}
        floaterProps={{
          disableAnimation: false,
        }}
        styles={{
          options: {
            zIndex: 10000,
            arrowColor: 'white',
          },
          overlay: {
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
          },
          spotlight: {
            borderRadius: 8,
          },
        }}
        locale={{
          back: 'Back',
          close: 'Close',
          last: 'Finish',
          next: 'Next',
          skip: 'Skip tour',
        }}
      />
    </>
  );
};

// Export hook for triggering tours
export const useTour = () => {
  const { startTour, shouldShowTour, resetTour, resetAllTours } = useTourStore();

  const triggerTour = useCallback(
    (tourKey: TourKey, force = false) => {
      if (force || shouldShowTour(tourKey)) {
        startTour(tourKey);
      }
    },
    [startTour, shouldShowTour]
  );

  return {
    triggerTour,
    shouldShowTour,
    resetTour,
    resetAllTours,
  };
};
