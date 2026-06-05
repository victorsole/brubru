/**
 * Consultations State Management
 *
 * Zustand store for managing EC Public Consultations data.
 * Handles fetching consultations, tracking, and filters.
 *
 * Created: January 2026
 */

import { create } from 'zustand';
import {
  consultationService,
} from '../services/consultation_service';
import type {
  ConsultationListItem,
  ConsultationDetail,
  TrackedConsultation,
  ConsultationFilters,
  TrackingOptions,
  UpdateTrackingOptions,
  DGInfo,
  PolicyAreaInfo,
  ConsultationType,
  ConsultationStatus,
} from '../services/consultation_service';

// ============================================================================
// State Interface
// ============================================================================

interface ConsultationsState {
  // Data
  consultations: ConsultationListItem[];
  selectedConsultation: ConsultationDetail | null;
  trackedConsultations: TrackedConsultation[];
  dgs: DGInfo[];
  policyAreas: PolicyAreaInfo[];
  totalItems: number;

  // Filters
  filters: ConsultationFilters;
  sortBy: string;
  sortDesc: boolean;
  limit: number;
  offset: number;

  // Loading states
  isLoadingConsultations: boolean;
  isLoadingDetail: boolean;
  isLoadingTracked: boolean;
  isLoadingReferenceData: boolean;
  isTracking: boolean;

  // Error state
  error: string | null;

  // Actions
  fetchConsultations: () => Promise<void>;
  fetchConsultationDetail: (id: string) => Promise<void>;
  fetchTrackedConsultations: () => Promise<void>;
  fetchReferenceData: () => Promise<void>;
  trackConsultation: (id: string, options?: TrackingOptions) => Promise<void>;
  untrackConsultation: (id: string) => Promise<void>;
  updateTracking: (id: string, options: UpdateTrackingOptions) => Promise<void>;
  setFilters: (filters: ConsultationFilters) => void;
  setSort: (sortBy: string, sortDesc: boolean) => void;
  setPage: (offset: number) => void;
  closeDetail: () => void;
  clearFilters: () => void;
  clearError: () => void;
}

// ============================================================================
// Store
// ============================================================================

export const useConsultations = create<ConsultationsState>((set, get) => ({
  // Initial state
  consultations: [],
  selectedConsultation: null,
  trackedConsultations: [],
  dgs: [],
  policyAreas: [],
  totalItems: 0,
  filters: { status: 'open' as ConsultationStatus, my_interests: true },
  sortBy: 'end_date',
  sortDesc: false,
  limit: 50,
  offset: 0,
  isLoadingConsultations: false,
  isLoadingDetail: false,
  isLoadingTracked: false,
  isLoadingReferenceData: false,
  isTracking: false,
  error: null,

  // Fetch consultations with current filters
  fetchConsultations: async () => {
    set({ isLoadingConsultations: true, error: null });

    try {
      const { filters, sortBy, sortDesc, limit, offset } = get();

      const response = await consultationService.getConsultations({
        filters,
        sort_by: sortBy,
        sort_desc: sortDesc,
        limit,
        offset,
      });

      set({
        consultations: response.items,
        totalItems: response.total,
        isLoadingConsultations: false,
      });
    } catch (error) {
      console.error('Failed to fetch consultations:', error);
      set({
        isLoadingConsultations: false,
        error: 'Failed to load consultations',
      });
    }
  },

  // Fetch consultation detail
  fetchConsultationDetail: async (id: string) => {
    set({ isLoadingDetail: true, error: null });

    try {
      const detail = await consultationService.getConsultation(id);
      set({
        selectedConsultation: detail,
        isLoadingDetail: false,
      });
    } catch (error) {
      console.error('Failed to fetch consultation detail:', error);
      set({
        isLoadingDetail: false,
        error: 'Failed to load consultation details',
      });
    }
  },

  // Fetch tracked consultations
  fetchTrackedConsultations: async () => {
    set({ isLoadingTracked: true, error: null });

    try {
      const response = await consultationService.getTrackedConsultations();
      set({
        trackedConsultations: response.items || [],
        isLoadingTracked: false,
      });
    } catch (error) {
      console.error('Failed to fetch tracked consultations:', error);
      set({
        isLoadingTracked: false,
        error: 'Failed to load tracked consultations',
      });
    }
  },

  // Fetch reference data (DGs and policy areas)
  fetchReferenceData: async () => {
    set({ isLoadingReferenceData: true });

    try {
      const [dgs, policyAreas] = await Promise.all([
        consultationService.getDGs(),
        consultationService.getPolicyAreas(),
      ]);

      set({
        dgs,
        policyAreas,
        isLoadingReferenceData: false,
      });
    } catch (error) {
      console.error('Failed to fetch reference data:', error);
      set({ isLoadingReferenceData: false });
    }
  },

  // Track a consultation
  trackConsultation: async (id: string, options?: TrackingOptions) => {
    set({ isTracking: true, error: null });

    try {
      await consultationService.trackConsultation(id, options);

      // Refresh tracked consultations
      await get().fetchTrackedConsultations();

      // Update selected consultation if it's the one we just tracked
      const selectedConsultation = get().selectedConsultation;
      if (selectedConsultation && selectedConsultation.id === id) {
        await get().fetchConsultationDetail(id);
      }

      // Refresh main list to update is_tracked status
      await get().fetchConsultations();

      set({ isTracking: false });
    } catch (error) {
      console.error('Failed to track consultation:', error);
      set({
        isTracking: false,
        error: 'Failed to track consultation',
      });
      throw error;
    }
  },

  // Untrack a consultation
  untrackConsultation: async (id: string) => {
    set({ isTracking: true, error: null });

    try {
      await consultationService.untrackConsultation(id);

      // Refresh tracked consultations
      await get().fetchTrackedConsultations();

      // Update selected consultation if it's the one we just untracked
      const selectedConsultation = get().selectedConsultation;
      if (selectedConsultation && selectedConsultation.id === id) {
        await get().fetchConsultationDetail(id);
      }

      // Refresh main list
      await get().fetchConsultations();

      set({ isTracking: false });
    } catch (error) {
      console.error('Failed to untrack consultation:', error);
      set({
        isTracking: false,
        error: 'Failed to untrack consultation',
      });
      throw error;
    }
  },

  // Update tracking preferences
  updateTracking: async (id: string, options: UpdateTrackingOptions) => {
    set({ isTracking: true, error: null });

    try {
      await consultationService.updateTracking(id, options);

      // Refresh tracked consultations
      await get().fetchTrackedConsultations();

      set({ isTracking: false });
    } catch (error) {
      console.error('Failed to update tracking:', error);
      set({
        isTracking: false,
        error: 'Failed to update tracking preferences',
      });
      throw error;
    }
  },

  // Set filters
  setFilters: (filters: ConsultationFilters) => {
    set({ filters, offset: 0 }); // Reset to first page
    get().fetchConsultations();
  },

  // Set sort
  setSort: (sortBy: string, sortDesc: boolean) => {
    set({ sortBy, sortDesc });
    get().fetchConsultations();
  },

  // Set page offset
  setPage: (offset: number) => {
    set({ offset });
    get().fetchConsultations();
  },

  // Close detail modal
  closeDetail: () => {
    set({ selectedConsultation: null });
  },

  // Clear all filters
  clearFilters: () => {
    // Keep the Policy-Interest lens; clear only the manual refinements.
    set({
      filters: { my_interests: get().filters.my_interests ?? true },
      sortBy: 'end_date',
      sortDesc: false,
      offset: 0,
    });
    get().fetchConsultations();
  },

  // Clear error
  clearError: () => {
    set({ error: null });
  },
}));

// ============================================================================
// Display Constants
// ============================================================================

export const CONSULTATION_TYPE_INFO: Record<ConsultationType, { name: string; color: string }> = {
  public_consultation: { name: 'Public Consultation', color: '#059669' },
  call_for_evidence: { name: 'Call for Evidence', color: '#0693e3' },
  feedback: { name: 'Feedback', color: '#f97316' },
  roadmap: { name: 'Roadmap', color: '#8b5cf6' },
  initiative: { name: 'Initiative', color: '#6b7280' },
};

export const STATUS_INFO: Record<ConsultationStatus, { name: string; color: string }> = {
  open: { name: 'Open', color: '#059669' },
  upcoming: { name: 'Upcoming', color: '#3b82f6' },
  closed: { name: 'Closed', color: '#d97706' },
  outcome_published: { name: 'Outcome Published', color: '#0693e3' },
  withdrawn: { name: 'Withdrawn', color: '#6b7280' },
};

export const SUBMISSION_STATUS_INFO: Record<string, { name: string; color: string }> = {
  not_started: { name: 'Not Started', color: '#6b7280' },
  draft: { name: 'Draft in Progress', color: '#f97316' },
  submitted: { name: 'Submitted', color: '#059669' },
  not_participating: { name: 'Not Participating', color: '#9ca3af' },
};

// ============================================================================
// Hooks for specific use cases
// ============================================================================

/**
 * Hook for getting consultations closing soon
 */
export function useClosingSoonConsultations() {
  const { consultations, isLoadingConsultations, setFilters } = useConsultations();

  const loadClosingSoon = () => {
    setFilters({ status: 'open', closing_soon: true });
  };

  return {
    consultations: consultations.filter(c => c.is_closing_soon),
    isLoading: isLoadingConsultations,
    loadClosingSoon,
  };
}

/**
 * Hook for tracked consultations count
 */
export function useTrackedConsultationsCount() {
  const { trackedConsultations } = useConsultations();
  return trackedConsultations.length;
}
