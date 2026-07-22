/**
 * Predictions Hook (Zustand)
 *
 * State management for legislative predictions.
 * Follows the mockup design in docs/mockups/predictions-tab.html
 *
 * Created: February 2026
 */

import { create } from 'zustand';
import i18n from '../i18n/config';
import {
  getFullPrediction,
  getTimelinePrediction,
  getOutcomePrediction,
  getEPVotePrediction,
  getStagnationAlerts,
  getModelInfo,
  type PredictionSummary,
  type PredictionQuota,
  type StagnationAlert,
  type ModelInfo,
} from '../services/prediction_service';

// ============================================================================
// Types
// ============================================================================

export type LoadingStatus = 'idle' | 'loading' | 'success' | 'error';

export interface LoadingState {
  status: LoadingStatus;
  message?: string;
}

// Loading status messages (cycle through these)
export const LOADING_MESSAGES = [
  'Checking EP voting records...',
  'Analysing Council positions...',
  'Calculating timeline projections...',
  'Assessing amendment patterns...',
  'Evaluating resolution signals...',
];

interface PredictionsState {
  // Data
  predictions: PredictionSummary[];
  stagnationAlerts: StagnationAlert[];
  modelInfo: ModelInfo | null;

  // Quota (Yellow tier only)
  quota: PredictionQuota | null;

  // Loading states
  loadingState: LoadingState;
  isGeneratingPrediction: boolean;
  loadingMessageIndex: number;

  // Selected prediction for detail view
  selectedPredictionId: string | null;

  // Error state
  error: string | null;

  // Actions
  generatePrediction: (
    procedureRef: string,
    title: string,
    leadCommittee?: string,
    rapporteurGroup?: string
  ) => Promise<PredictionSummary | null>;
  refreshPrediction: (predictionId: string) => Promise<void>;
  deletePrediction: (predictionId: string) => void;
  toggleExpanded: (predictionId: string) => void;
  setSelectedPrediction: (predictionId: string | null) => void;
  fetchStagnationAlerts: () => Promise<void>;
  fetchModelInfo: () => Promise<void>;
  updateQuota: (used: number, total: number, resetDate: string) => void;
  clearError: () => void;
  setLoadingMessage: (index: number) => void;
}

// ============================================================================
// Store
// ============================================================================

export const usePredictions = create<PredictionsState>((set, get) => ({
  // Initial state
  predictions: [],
  stagnationAlerts: [],
  modelInfo: null,
  quota: null,
  loadingState: { status: 'idle' },
  isGeneratingPrediction: false,
  loadingMessageIndex: 0,
  selectedPredictionId: null,
  error: null,

  // Generate a new prediction for a procedure
  generatePrediction: async (
    procedureRef: string,
    title: string,
    leadCommittee?: string,
    rapporteurGroup?: string
  ): Promise<PredictionSummary | null> => {
    const { predictions, quota } = get();

    // Check quota (Yellow tier)
    if (quota && quota.used >= quota.total) {
      set({ error: 'Monthly prediction quota reached. Upgrade to Professional for unlimited predictions.' });
      return null;
    }

    // Check if prediction already exists
    const existing = predictions.find((p) => p.procedure_ref === procedureRef);
    if (existing) {
      // Return existing prediction
      set({ selectedPredictionId: existing.id });
      return existing;
    }

    // Start loading
    set({
      isGeneratingPrediction: true,
      loadingState: { status: 'loading', message: LOADING_MESSAGES[0] },
      loadingMessageIndex: 0,
      error: null,
    });

    // Start cycling through loading messages
    const messageInterval = setInterval(() => {
      const { loadingMessageIndex } = get();
      const nextIndex = (loadingMessageIndex + 1) % LOADING_MESSAGES.length;
      set({
        loadingMessageIndex: nextIndex,
        loadingState: { status: 'loading', message: LOADING_MESSAGES[nextIndex] },
      });
    }, 2000);

    try {
      const prediction = await getFullPrediction(
        procedureRef,
        title,
        leadCommittee,
        rapporteurGroup
      );

      clearInterval(messageInterval);

      // Add to predictions list
      set((state) => ({
        predictions: [prediction, ...state.predictions],
        isGeneratingPrediction: false,
        loadingState: { status: 'success' },
        selectedPredictionId: prediction.id,
        // Update quota if applicable
        quota: state.quota
          ? { ...state.quota, used: state.quota.used + 1 }
          : null,
      }));

      return prediction;
    } catch (err) {
      clearInterval(messageInterval);

      const errorMessage =
        err instanceof Error
          ? err.message
          : i18n.t('predictions.errGenerate', { defaultValue: 'Failed to generate prediction' });

      set({
        isGeneratingPrediction: false,
        loadingState: { status: 'error', message: errorMessage },
        error: errorMessage,
      });

      return null;
    }
  },

  // Refresh an existing prediction
  refreshPrediction: async (predictionId: string): Promise<void> => {
    const { predictions } = get();
    const prediction = predictions.find((p) => p.id === predictionId);

    if (!prediction) return;

    set({ loadingState: { status: 'loading', message: 'Refreshing prediction...' } });

    try {
      // Fetch fresh data
      const [timeline, outcome, epVote] = await Promise.all([
        getTimelinePrediction(prediction.procedure_ref).catch(() => undefined),
        getOutcomePrediction(prediction.procedure_ref).catch(() => undefined),
        getEPVotePrediction(prediction.procedure_ref).catch(() => undefined),
      ]);

      // Calculate new overall confidence
      const confidences: number[] = [];
      if (timeline) confidences.push(timeline.confidence);
      if (outcome) confidences.push(outcome.confidence);
      if (epVote) confidences.push(epVote.confidence);

      const overallConfidence =
        confidences.length > 0
          ? confidences.reduce((a, b) => a + b, 0) / confidences.length
          : 0.5;

      // Update prediction
      set((state) => ({
        predictions: state.predictions.map((p) =>
          p.id === predictionId
            ? {
                ...p,
                timeline,
                outcome,
                ep_vote: epVote,
                overall_confidence: overallConfidence,
                predicted_at: new Date().toISOString(),
              }
            : p
        ),
        loadingState: { status: 'success' },
      }));
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : i18n.t('predictions.errRefresh', { defaultValue: 'Failed to refresh prediction' });

      set({
        loadingState: { status: 'error', message: errorMessage },
        error: errorMessage,
      });
    }
  },

  // Delete a prediction from the list
  deletePrediction: (predictionId: string): void => {
    set((state) => ({
      predictions: state.predictions.filter((p) => p.id !== predictionId),
      selectedPredictionId:
        state.selectedPredictionId === predictionId
          ? null
          : state.selectedPredictionId,
    }));
  },

  // Toggle expanded state for a prediction card
  toggleExpanded: (predictionId: string): void => {
    set((state) => ({
      predictions: state.predictions.map((p) =>
        p.id === predictionId ? { ...p, is_expanded: !p.is_expanded } : p
      ),
    }));
  },

  // Set selected prediction for detail view
  setSelectedPrediction: (predictionId: string | null): void => {
    set({ selectedPredictionId: predictionId });
  },

  // Fetch stagnation alerts
  fetchStagnationAlerts: async (): Promise<void> => {
    try {
      const alerts = await getStagnationAlerts('warning', 50);
      set({ stagnationAlerts: alerts });
    } catch (err) {
      console.error('Failed to fetch stagnation alerts:', err);
    }
  },

  // Fetch model info (Blue tier)
  fetchModelInfo: async (): Promise<void> => {
    try {
      const info = await getModelInfo();
      set({ modelInfo: info });
    } catch (err) {
      console.error('Failed to fetch model info:', err);
    }
  },

  // Update quota (called from parent component based on user tier)
  updateQuota: (used: number, total: number, resetDate: string): void => {
    set({ quota: { used, total, reset_date: resetDate } });
  },

  // Clear error
  clearError: (): void => {
    set({ error: null });
  },

  // Set loading message index (for animation)
  setLoadingMessage: (index: number): void => {
    set({
      loadingMessageIndex: index,
      loadingState: { status: 'loading', message: LOADING_MESSAGES[index] },
    });
  },
}));

// ============================================================================
// Selectors
// ============================================================================

/**
 * Get the currently selected prediction
 */
export const useSelectedPrediction = () => {
  const predictions = usePredictions((state) => state.predictions);
  const selectedId = usePredictions((state) => state.selectedPredictionId);
  return predictions.find((p) => p.id === selectedId) || null;
};

/**
 * Get expanded predictions
 */
export const useExpandedPredictions = () => {
  const predictions = usePredictions((state) => state.predictions);
  return predictions.filter((p) => p.is_expanded);
};

/**
 * Check if quota is exhausted
 */
export const useIsQuotaExhausted = () => {
  const quota = usePredictions((state) => state.quota);
  return quota ? quota.used >= quota.total : false;
};

/**
 * Get quota percentage used
 */
export const useQuotaPercentage = () => {
  const quota = usePredictions((state) => state.quota);
  if (!quota || quota.total === 0) return 0;
  return (quota.used / quota.total) * 100;
};

// ============================================================================
// Utility Constants
// ============================================================================

/**
 * EP Group information for display
 */
export const EP_GROUPS = [
  { code: 'EPP', name: 'EPP', fullName: 'European People\'s Party', seats: 188, color: '#0066cc' },
  { code: 'S&D', name: 'S&D', fullName: 'Socialists & Democrats', seats: 136, color: '#c62828' },
  { code: 'Renew', name: 'Renew', fullName: 'Renew Europe', seats: 77, color: '#ffc107' },
  { code: 'Greens/EFA', name: 'Greens/EFA', fullName: 'Greens/European Free Alliance', seats: 53, color: '#2e7d32' },
  { code: 'ECR', name: 'ECR', fullName: 'European Conservatives and Reformists', seats: 78, color: '#1565c0' },
  { code: 'PfE', name: 'PfE', fullName: 'Patriots for Europe', seats: 84, color: '#00695c' },
  { code: 'The Left', name: 'The Left', fullName: 'The Left in the EP', seats: 46, color: '#6a1b9a' },
  { code: 'ESN', name: 'ESN', fullName: 'Europe of Sovereign Nations', seats: 25, color: '#37474f' },
  { code: 'NI', name: 'NI', fullName: 'Non-Inscrits', seats: 33, color: '#9e9e9e' },
];

/**
 * Timeline stages for display. `label` is a lazy getter so it follows the
 * active UI language (keys reused from predictionsTab, same values).
 */
const stage = (id: string, key: string, fallback: string, icon: string) => ({
  id,
  get label(): string { return i18n.t(key, { defaultValue: fallback }); },
  icon,
});
export const TIMELINE_STAGES = [
  stage('committee', 'predictionsTab.committee', 'Committee', 'mdi-account-group'),
  stage('plenary', 'predictionsTab.plenary', 'Plenary', 'mdi-account-voice'),
  stage('trilogue', 'predictionsTab.trilogue', 'Trilogue', 'mdi-handshake'),
  stage('council', 'predictionsTab.council', 'Council', 'mdi-gavel'),
  stage('oj', 'predictionsTab.oj', 'OJ', 'mdi-book-open-page-variant'),
];
