/**
 * Texts Adopted State Management
 *
 * Zustand store for managing EP Texts Adopted data.
 * Handles fetching texts, tracking, and filters.
 *
 * Created: February 2026
 */

import { create } from 'zustand';
import axios from 'axios';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api`;

// Types
export type TextType =
  | 'resolution'
  | 'legislative_resolution'
  | 'decision'
  | 'recommendation'
  | 'other';

export interface TextAdopted {
  id: string;
  ta_reference: string;
  title: string;
  text_type: TextType;
  adoption_date: string;
  procedure_ref?: string;
  parliamentary_term: number;
  committees: string[];
  rapporteur_name?: string;
  source_url?: string;
  full_text_url?: string;
  last_updated: string;
}

export interface TextAdoptedDetail extends TextAdopted {
  description?: string;
  full_text?: string;
  rapporteur_mep_id?: string;
  celex_number?: string;
  vote_results?: {
    for?: number;
    against?: number;
    abstentions?: number;
  };
  related_documents: Array<{
    title: string;
    url: string;
    type?: string;
  }>;
  pdf_url?: string;
  legislative_carriage_id?: string;
  first_seen: string;
  scraped_at?: string;
  is_tracked: boolean;
  user_notes?: string;
  tracked_since?: string;
}

export interface TrackedTextAdopted {
  text: TextAdopted;
  tracked_since: string;
  notes?: string;
}

export interface ParliamentaryTerm {
  term: number;
  years: string;
  prefix: string;
  text_count: number;
}

export interface TextsAdoptedFilters {
  text_type?: TextType;
  parliamentary_term?: number;
  search?: string;
  procedure_ref?: string;
  date_from?: string;
  date_to?: string;
}

interface TextsAdoptedState {
  // Data
  items: TextAdopted[];
  selectedItem: TextAdoptedDetail | null;
  trackedItems: TrackedTextAdopted[];
  terms: ParliamentaryTerm[];
  totalItems: number;

  // Filters
  filters: TextsAdoptedFilters;
  sortBy: string;
  sortDesc: boolean;
  limit: number;
  offset: number;

  // Loading states
  isLoadingItems: boolean;
  isLoadingDetail: boolean;
  isLoadingTracked: boolean;
  isLoadingTerms: boolean;
  isTracking: boolean;

  // Actions
  fetchItems: () => Promise<void>;
  fetchItemDetail: (itemId: string) => Promise<void>;
  fetchTrackedItems: () => Promise<void>;
  fetchTerms: () => Promise<void>;
  trackItem: (itemId: string, notes?: string) => Promise<void>;
  untrackItem: (itemId: string) => Promise<void>;
  setFilters: (filters: TextsAdoptedFilters) => void;
  setSort: (sortBy: string, sortDesc: boolean) => void;
  setPage: (offset: number) => void;
  closeItemDetail: () => void;
  clearFilters: () => void;
}

export const useTextsAdopted = create<TextsAdoptedState>((set, get) => ({
  // Initial state
  items: [],
  selectedItem: null,
  trackedItems: [],
  terms: [],
  totalItems: 0,
  filters: {},
  sortBy: 'adoption_date',
  sortDesc: true,
  limit: 50,
  offset: 0,
  isLoadingItems: false,
  isLoadingDetail: false,
  isLoadingTracked: false,
  isLoadingTerms: false,
  isTracking: false,

  // Fetch items with current filters
  fetchItems: async () => {
    set({ isLoadingItems: true });

    try {
      const { filters, sortBy, sortDesc, limit, offset } = get();

      const params = new URLSearchParams();
      if (filters.text_type) params.append('text_type', filters.text_type);
      if (filters.parliamentary_term !== undefined) params.append('parliamentary_term', filters.parliamentary_term.toString());
      if (filters.search) params.append('search', filters.search);
      if (filters.procedure_ref) params.append('procedure_ref', filters.procedure_ref);
      if (filters.date_from) params.append('date_from', filters.date_from);
      if (filters.date_to) params.append('date_to', filters.date_to);
      params.append('sort_by', sortBy);
      params.append('sort_desc', sortDesc.toString());
      params.append('limit', limit.toString());
      params.append('offset', offset.toString());

      const response = await axios.get<{
        items: TextAdopted[];
        total: number;
        limit: number;
        offset: number;
      }>(`${API_BASE}/texts-adopted/items?${params.toString()}`);

      set({
        items: response.data.items,
        totalItems: response.data.total,
        isLoadingItems: false,
      });
    } catch (error) {
      console.error('Failed to fetch texts adopted:', error);
      set({ isLoadingItems: false });
    }
  },

  // Fetch item detail
  fetchItemDetail: async (itemId: string) => {
    set({ isLoadingDetail: true });

    try {
      const response = await axios.get<TextAdoptedDetail>(
        `${API_BASE}/texts-adopted/items/${itemId}`
      );

      set({
        selectedItem: response.data,
        isLoadingDetail: false,
      });
    } catch (error) {
      console.error('Failed to fetch text detail:', error);
      set({ isLoadingDetail: false });
    }
  },

  // Fetch tracked items
  fetchTrackedItems: async () => {
    set({ isLoadingTracked: true });

    try {
      const response = await axios.get<{
        items: TrackedTextAdopted[];
        total: number;
      }>(`${API_BASE}/texts-adopted/tracked`);

      set({
        trackedItems: response.data.items || [],
        isLoadingTracked: false,
      });
    } catch (error) {
      console.error('Failed to fetch tracked texts:', error);
      set({ isLoadingTracked: false });
    }
  },

  // Fetch available terms
  fetchTerms: async () => {
    set({ isLoadingTerms: true });

    try {
      const response = await axios.get<{
        terms: ParliamentaryTerm[];
      }>(`${API_BASE}/texts-adopted/terms`);

      set({
        terms: response.data.terms || [],
        isLoadingTerms: false,
      });
    } catch (error) {
      console.error('Failed to fetch terms:', error);
      set({ isLoadingTerms: false });
    }
  },

  // Track an item
  trackItem: async (itemId: string, notes?: string) => {
    set({ isTracking: true });

    try {
      await axios.post(`${API_BASE}/texts-adopted/track/${itemId}`, {
        notes,
      });

      await get().fetchTrackedItems();

      const selectedItem = get().selectedItem;
      if (selectedItem && selectedItem.id === itemId) {
        await get().fetchItemDetail(itemId);
      }

      set({ isTracking: false });
    } catch (error) {
      console.error('Failed to track text:', error);
      set({ isTracking: false });
      throw error;
    }
  },

  // Untrack an item
  untrackItem: async (itemId: string) => {
    set({ isTracking: true });

    try {
      await axios.delete(`${API_BASE}/texts-adopted/track/${itemId}`);

      await get().fetchTrackedItems();

      const selectedItem = get().selectedItem;
      if (selectedItem && selectedItem.id === itemId) {
        await get().fetchItemDetail(itemId);
      }

      set({ isTracking: false });
    } catch (error) {
      console.error('Failed to untrack text:', error);
      set({ isTracking: false });
      throw error;
    }
  },

  // Set filters (resets to page 1)
  setFilters: (filters: TextsAdoptedFilters) => {
    set({ filters, offset: 0 });
    get().fetchItems();
  },

  // Set sort
  setSort: (sortBy: string, sortDesc: boolean) => {
    set({ sortBy, sortDesc });
    get().fetchItems();
  },

  // Set page offset
  setPage: (offset: number) => {
    set({ offset });
    get().fetchItems();
  },

  // Close item detail
  closeItemDetail: () => {
    set({ selectedItem: null });
  },

  // Clear all filters
  clearFilters: () => {
    set({
      filters: {},
      sortBy: 'adoption_date',
      sortDesc: true,
      offset: 0,
    });
    get().fetchItems();
  },
}));

// Text type display names and colours
export const TEXT_TYPE_INFO: Record<TextType, { name: string; color: string }> = {
  resolution: { name: 'Resolution', color: '#b91c1c' },
  legislative_resolution: { name: 'Legislative Resolution', color: '#0066cc' },
  decision: { name: 'Decision', color: '#d97706' },
  recommendation: { name: 'Recommendation', color: '#7c3aed' },
  other: { name: 'Other', color: '#6b7280' },
};
