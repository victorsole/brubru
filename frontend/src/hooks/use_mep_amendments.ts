/**
 * MEP Amendments Hook (Zustand)
 *
 * State management for EP committee amendment data.
 * Used by the MEP Amendments sub-tab in My EU Bubble > Amendments.
 *
 * Created: February 2026
 */

import { create } from 'zustand';
import {
  listAmendments,
  getStats,
  fetchAmendments as fetchAmendmentsApi,
  scoreAlignment,
  getComparison,
  type MEPAmendment,
  type AmendmentStats,
  type AmendmentFilters,
  type MEPAmendmentListResponse,
  type AlignmentScoreItem,
  type ComparisonData,
} from '../services/mep_amendment_service';

// ============================================================================
// EP Group Colours (brand colours from amendmenttraining.md Section 7.2)
// ============================================================================

export const EP_GROUP_COLOURS: Record<string, string> = {
  EPP: '#003D8F',
  'S&D': '#E30613',
  Renew: '#FFD700',
  'Greens/EFA': '#00A651',
  ECR: '#0054A6',
  'The Left': '#8B0000',
  PfE: '#002855',
  ESN: '#1B365D',
  NI: '#808080',
  Rapporteur: '#059669',
  Unknown: '#9ca3af',
};

/** Groups where white text is not readable (light backgrounds) */
export const DARK_TEXT_GROUPS = new Set(['Renew']);

// ============================================================================
// Types
// ============================================================================

export type LoadingStatus = 'idle' | 'loading' | 'success' | 'error';

interface MEPAmendmentsState {
  // Selected procedure
  selectedProcedure: string | null;

  // Data
  amendments: MEPAmendment[];
  stats: AmendmentStats | null;
  total: number;

  // Filters
  filters: AmendmentFilters;
  activeGroups: Set<string>;

  // Pagination
  page: number;
  pageSize: number;

  // Loading
  loadingStatus: LoadingStatus;
  statsLoadingStatus: LoadingStatus;
  error: string | null;

  // Alignment scoring (Phase 4)
  policyPosition: string;
  alignmentScores: AlignmentScoreItem[] | null;
  alignmentHash: string | null;
  scoreDistribution: Record<string, number> | null;
  comparison: ComparisonData | null;
  scoringStatus: LoadingStatus;
  scoringError: string | null;

  // Actions
  selectProcedure: (ref: string, token: string) => Promise<void>;
  setFilter: (key: keyof AmendmentFilters, value: string | undefined) => void;
  toggleGroup: (group: string) => void;
  setPage: (page: number) => void;
  loadAmendments: (token: string) => Promise<void>;
  loadStats: (token: string) => Promise<void>;
  triggerFetch: (procedureRef: string, token: string) => Promise<void>;
  setPolicyPosition: (text: string) => void;
  runAlignment: (token: string) => Promise<void>;
  reset: () => void;
}

// ============================================================================
// Store
// ============================================================================

export const useMEPAmendments = create<MEPAmendmentsState>((set, get) => ({
  selectedProcedure: null,
  amendments: [],
  stats: null,
  total: 0,
  filters: {},
  activeGroups: new Set(Object.keys(EP_GROUP_COLOURS)),
  page: 1,
  pageSize: 20,
  loadingStatus: 'idle',
  statsLoadingStatus: 'idle',
  error: null,

  // Alignment scoring defaults
  policyPosition: '',
  alignmentScores: null,
  alignmentHash: null,
  scoreDistribution: null,
  comparison: null,
  scoringStatus: 'idle',
  scoringError: null,

  selectProcedure: async (ref: string, token: string) => {
    set({
      selectedProcedure: ref,
      page: 1,
      filters: {},
      activeGroups: new Set(Object.keys(EP_GROUP_COLOURS)),
    });
    // Load stats and amendments in parallel
    const state = get();
    await Promise.all([
      state.loadStats(token),
      state.loadAmendments(token),
    ]);
  },

  setFilter: (key, value) => {
    set((state) => ({
      filters: { ...state.filters, [key]: value || undefined },
      page: 1,
    }));
  },

  toggleGroup: (group: string) => {
    set((state) => {
      const next = new Set(state.activeGroups);
      if (next.has(group)) {
        next.delete(group);
      } else {
        next.add(group);
      }
      return { activeGroups: next };
    });
  },

  setPage: (page: number) => {
    set({ page });
  },

  loadAmendments: async (token: string) => {
    const { selectedProcedure, filters, page, pageSize } = get();
    if (!selectedProcedure) return;

    set({ loadingStatus: 'loading', error: null });
    try {
      const offset = (page - 1) * pageSize;
      const data: MEPAmendmentListResponse = await listAmendments(
        selectedProcedure,
        token,
        filters,
        pageSize,
        offset
      );
      set({
        amendments: data.items,
        total: data.total,
        loadingStatus: 'success',
      });
    } catch (err) {
      set({
        loadingStatus: 'error',
        error: err instanceof Error ? err.message : 'Failed to load amendments',
      });
    }
  },

  loadStats: async (token: string) => {
    const { selectedProcedure } = get();
    if (!selectedProcedure) return;

    set({ statsLoadingStatus: 'loading' });
    try {
      const data = await getStats(selectedProcedure, token);
      set({ stats: data, statsLoadingStatus: 'success' });
    } catch {
      set({ statsLoadingStatus: 'error' });
    }
  },

  triggerFetch: async (procedureRef: string, token: string) => {
    set({ loadingStatus: 'loading' });
    try {
      await fetchAmendmentsApi(procedureRef, token);
      // Reload data after fetch
      const state = get();
      await Promise.all([
        state.loadStats(token),
        state.loadAmendments(token),
      ]);
    } catch (err) {
      set({
        loadingStatus: 'error',
        error: err instanceof Error ? err.message : 'Failed to fetch amendments',
      });
    }
  },

  setPolicyPosition: (text: string) => {
    set({ policyPosition: text });
  },

  runAlignment: async (token: string) => {
    const { selectedProcedure, policyPosition } = get();
    if (!selectedProcedure || !policyPosition || policyPosition.length < 10) return;

    set({ scoringStatus: 'loading', scoringError: null });
    try {
      // Step 1: Score amendments
      const alignmentResult = await scoreAlignment(selectedProcedure, token, policyPosition);
      set({
        alignmentScores: alignmentResult.scores,
        alignmentHash: alignmentResult.policy_position_hash,
        scoreDistribution: alignmentResult.score_distribution,
      });

      // Step 2: Get comparative analysis
      const comparisonResult = await getComparison(
        selectedProcedure,
        token,
        alignmentResult.policy_position_hash,
      );
      set({
        comparison: comparisonResult,
        scoringStatus: 'success',
      });
    } catch (err) {
      set({
        scoringStatus: 'error',
        scoringError: err instanceof Error ? err.message : 'Alignment scoring failed',
      });
    }
  },

  reset: () => {
    set({
      selectedProcedure: null,
      amendments: [],
      stats: null,
      total: 0,
      filters: {},
      activeGroups: new Set(Object.keys(EP_GROUP_COLOURS)),
      page: 1,
      loadingStatus: 'idle',
      statsLoadingStatus: 'idle',
      error: null,
      policyPosition: '',
      alignmentScores: null,
      alignmentHash: null,
      scoreDistribution: null,
      comparison: null,
      scoringStatus: 'idle',
      scoringError: null,
    });
  },
}));
