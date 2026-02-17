/**
 * Commission Documents State Management
 *
 * Zustand store for managing EC Commission Documents data.
 * Handles fetching documents, tracking, and filters.
 *
 * Created: February 2026
 */

import { create } from 'zustand';
import axios from 'axios';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api`;

// Types
export type CommissionDocType = 'COM' | 'SWD' | 'SEC' | 'C' | 'JOIN' | 'OJ' | 'PV';

export interface CommissionDocItem {
  id: string;
  reference: string;
  title: string;
  doc_type: CommissionDocType;
  publication_date?: string;
  dg_responsible?: string;
  procedure_ref?: string;
  portal_url?: string;
  celex?: string;
  last_updated: string;
}

export interface CommissionDocDetail extends CommissionDocItem {
  languages: string[];
  legislative_carriage_id?: string;
  first_seen: string;
  scraped_at?: string;
  is_tracked: boolean;
  user_notes?: string;
  tracked_since?: string;
}

export interface TrackedCommissionDoc {
  document: CommissionDocItem;
  tracked_since: string;
  notes?: string;
  notify_on_new_documents: boolean;
}

export interface CommissionDocFilters {
  doc_type?: CommissionDocType;
  dg?: string;
  search?: string;
  date_from?: string;
  date_to?: string;
}

interface CommissionDocumentsState {
  // Data
  items: CommissionDocItem[];
  selectedItem: CommissionDocDetail | null;
  trackedItems: TrackedCommissionDoc[];
  totalItems: number;

  // Filters
  filters: CommissionDocFilters;
  sortBy: string;
  sortDesc: boolean;
  limit: number;
  offset: number;

  // Loading states
  isLoadingItems: boolean;
  isLoadingDetail: boolean;
  isLoadingTracked: boolean;
  isTracking: boolean;

  // Actions
  fetchItems: () => Promise<void>;
  fetchItemDetail: (itemId: string) => Promise<void>;
  fetchTrackedItems: () => Promise<void>;
  trackItem: (itemId: string, notes?: string) => Promise<void>;
  untrackItem: (itemId: string) => Promise<void>;
  setFilters: (filters: CommissionDocFilters) => void;
  setSort: (sortBy: string, sortDesc: boolean) => void;
  setPage: (offset: number) => void;
  closeItemDetail: () => void;
  clearFilters: () => void;
}

export const useCommissionDocuments = create<CommissionDocumentsState>((set, get) => ({
  // Initial state
  items: [],
  selectedItem: null,
  trackedItems: [],
  totalItems: 0,
  filters: {},
  sortBy: 'publication_date',
  sortDesc: true,
  limit: 50,
  offset: 0,
  isLoadingItems: false,
  isLoadingDetail: false,
  isLoadingTracked: false,
  isTracking: false,

  // Fetch items with current filters
  fetchItems: async () => {
    set({ isLoadingItems: true });

    try {
      const { filters, sortBy, sortDesc, limit, offset } = get();

      const params = new URLSearchParams();
      if (filters.doc_type) params.append('doc_type', filters.doc_type);
      if (filters.dg) params.append('dg', filters.dg);
      if (filters.search) params.append('search', filters.search);
      if (filters.date_from) params.append('date_from', filters.date_from);
      if (filters.date_to) params.append('date_to', filters.date_to);
      params.append('sort_by', sortBy);
      params.append('sort_desc', sortDesc.toString());
      params.append('limit', limit.toString());
      params.append('offset', offset.toString());

      const response = await axios.get<{
        items: CommissionDocItem[];
        total: number;
        limit: number;
        offset: number;
      }>(`${API_BASE}/commission-documents/items?${params.toString()}`);

      set({
        items: response.data.items,
        totalItems: response.data.total,
        isLoadingItems: false,
      });
    } catch (error) {
      console.error('Failed to fetch Commission documents:', error);
      set({ isLoadingItems: false });
    }
  },

  // Fetch item detail
  fetchItemDetail: async (itemId: string) => {
    set({ isLoadingDetail: true });

    try {
      const response = await axios.get<CommissionDocDetail>(
        `${API_BASE}/commission-documents/items/${itemId}`
      );

      set({
        selectedItem: response.data,
        isLoadingDetail: false,
      });
    } catch (error) {
      console.error('Failed to fetch document detail:', error);
      set({ isLoadingDetail: false });
    }
  },

  // Fetch tracked items
  fetchTrackedItems: async () => {
    set({ isLoadingTracked: true });

    try {
      const response = await axios.get<{
        items: TrackedCommissionDoc[];
        total: number;
      }>(`${API_BASE}/commission-documents/tracked`);

      set({
        trackedItems: response.data.items || [],
        isLoadingTracked: false,
      });
    } catch (error) {
      console.error('Failed to fetch tracked Commission documents:', error);
      set({ isLoadingTracked: false });
    }
  },

  // Track an item
  trackItem: async (itemId: string, notes?: string) => {
    set({ isTracking: true });

    try {
      await axios.post(`${API_BASE}/commission-documents/track/${itemId}`, {
        notes,
      });

      await get().fetchTrackedItems();

      const selectedItem = get().selectedItem;
      if (selectedItem && selectedItem.id === itemId) {
        await get().fetchItemDetail(itemId);
      }

      set({ isTracking: false });
    } catch (error) {
      console.error('Failed to track document:', error);
      set({ isTracking: false });
      throw error;
    }
  },

  // Untrack an item
  untrackItem: async (itemId: string) => {
    set({ isTracking: true });

    try {
      await axios.delete(`${API_BASE}/commission-documents/track/${itemId}`);

      await get().fetchTrackedItems();

      const selectedItem = get().selectedItem;
      if (selectedItem && selectedItem.id === itemId) {
        await get().fetchItemDetail(itemId);
      }

      set({ isTracking: false });
    } catch (error) {
      console.error('Failed to untrack document:', error);
      set({ isTracking: false });
      throw error;
    }
  },

  // Set filters (resets to page 1)
  setFilters: (filters: CommissionDocFilters) => {
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
      sortBy: 'publication_date',
      sortDesc: true,
      offset: 0,
    });
    get().fetchItems();
  },
}));

// Document type display info
export const DOC_TYPE_INFO: Record<CommissionDocType, { name: string; color: string }> = {
  COM: { name: 'COM', color: '#0066cc' },
  SWD: { name: 'SWD', color: '#d97706' },
  SEC: { name: 'SEC', color: '#64748b' },
  C: { name: 'C', color: '#6b7280' },
  JOIN: { name: 'JOIN', color: '#7c3aed' },
  OJ: { name: 'OJ', color: '#059669' },
  PV: { name: 'PV', color: '#e11d48' },
};

export const DOC_TYPE_LABELS: Record<CommissionDocType, string> = {
  COM: 'Commission Document (proposals, communications)',
  SWD: 'Staff Working Document (impact assessments)',
  SEC: 'Secretariat-General Document',
  C: 'C Document (delegated/implementing acts)',
  JOIN: 'Joint Document (Commission + High Representative)',
  OJ: 'Official Journal (adopted legislation)',
  PV: 'Proces-Verbal (Commission meeting minutes)',
};
