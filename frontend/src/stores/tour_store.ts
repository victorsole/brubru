// frontend/src/stores/tour_store.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type TourKey =
  | 'welcome'
  | 'chat'
  | 'amendator'
  | 'eu_bubble'
  | 'eu_comply'
  | 'tenderator';

interface TourState {
  // State
  completedTours: TourKey[];
  skippedTours: TourKey[];
  currentTour: TourKey | null;
  currentStep: number;
  isRunning: boolean;

  // Actions
  startTour: (tourKey: TourKey) => void;
  stopTour: () => void;
  completeTour: (tourKey: TourKey) => void;
  skipTour: (tourKey: TourKey) => void;
  setStep: (step: number) => void;
  nextStep: () => void;
  prevStep: () => void;
  resetTour: (tourKey: TourKey) => void;
  resetAllTours: () => void;

  // Helpers
  isTourCompleted: (tourKey: TourKey) => boolean;
  isTourSkipped: (tourKey: TourKey) => boolean;
  shouldShowTour: (tourKey: TourKey) => boolean;
}

export const useTourStore = create<TourState>()(
  persist(
    (set, get) => ({
      // Initial state
      completedTours: [],
      skippedTours: [],
      currentTour: null,
      currentStep: 0,
      isRunning: false,

      // Actions
      startTour: (tourKey: TourKey) => {
        set({
          currentTour: tourKey,
          currentStep: 0,
          isRunning: true,
        });
      },

      stopTour: () => {
        set({
          currentTour: null,
          currentStep: 0,
          isRunning: false,
        });
      },

      completeTour: (tourKey: TourKey) => {
        const { completedTours } = get();
        if (!completedTours.includes(tourKey)) {
          set({
            completedTours: [...completedTours, tourKey],
            currentTour: null,
            currentStep: 0,
            isRunning: false,
          });
        } else {
          set({
            currentTour: null,
            currentStep: 0,
            isRunning: false,
          });
        }
      },

      skipTour: (tourKey: TourKey) => {
        const { skippedTours } = get();
        if (!skippedTours.includes(tourKey)) {
          set({
            skippedTours: [...skippedTours, tourKey],
            currentTour: null,
            currentStep: 0,
            isRunning: false,
          });
        } else {
          set({
            currentTour: null,
            currentStep: 0,
            isRunning: false,
          });
        }
      },

      setStep: (step: number) => {
        set({ currentStep: step });
      },

      nextStep: () => {
        set((state) => ({ currentStep: state.currentStep + 1 }));
      },

      prevStep: () => {
        set((state) => ({ currentStep: Math.max(0, state.currentStep - 1) }));
      },

      resetTour: (tourKey: TourKey) => {
        const { completedTours, skippedTours } = get();
        set({
          completedTours: completedTours.filter((t) => t !== tourKey),
          skippedTours: skippedTours.filter((t) => t !== tourKey),
        });
      },

      resetAllTours: () => {
        set({
          completedTours: [],
          skippedTours: [],
          currentTour: null,
          currentStep: 0,
          isRunning: false,
        });
      },

      // Helpers
      isTourCompleted: (tourKey: TourKey) => {
        return get().completedTours.includes(tourKey);
      },

      isTourSkipped: (tourKey: TourKey) => {
        return get().skippedTours.includes(tourKey);
      },

      shouldShowTour: (tourKey: TourKey) => {
        const { completedTours, skippedTours } = get();
        return !completedTours.includes(tourKey) && !skippedTours.includes(tourKey);
      },
    }),
    {
      name: 'brubru-tour-storage',
      partialize: (state) => ({
        completedTours: state.completedTours,
        skippedTours: state.skippedTours,
      }),
    }
  )
);
