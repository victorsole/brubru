/**
 * Committee Work State Management
 *
 * Zustand store for managing EP Committee Work in Progress data.
 * Handles fetching work items, tracking, and filters.
 *
 * Created: January 2026
 */

import { create } from 'zustand';
import axios from 'axios';
import i18n from '../i18n/config';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api`;

// Types
// OEIL procedure-type code. Free string in the DB (varchar, migration 093);
// the union lists the codes we currently store but unknown codes are tolerated.
export type ProcedureType =
  | 'COD' | 'CNS' | 'APP' | 'NLE' | 'INI' | 'INL' | 'RSP' | 'RSO' | 'REG'
  | 'RPS' | 'DEA' | 'IMM' | 'BUD' | 'BUI' | 'DEC' | 'GBD' | 'ACI' | 'COS' | 'DCE'
  | (string & {});
export type CommitteeRole = 'lead' | 'associated' | 'opinion';
export type CommitteeWorkStatus =
  | 'in_committee'
  | 'awaiting_vote'
  | 'tabled'
  | 'adopted'
  | 'rejected'
  | 'withdrawn'
  | 'pending'
  | 'completed'
  | 'unknown';

export interface CommitteeWorkItem {
  id: string;
  procedure_ref: string;
  committee_code: string;
  title: string;
  description?: string;
  procedure_type: ProcedureType;
  committee_role: CommitteeRole;
  relevance_score: number;
  rapporteur_name?: string;
  rapporteur_mep_id?: string;
  status: CommitteeWorkStatus;
  status_text?: string;
  oeil_url?: string;
  ep_page_url?: string;
  last_updated: string;
  first_seen?: string;
  legislative_carriage_id?: string | null;
  // eMeeting enrichment: the opinion / draft opinion this committee tabled.
  committee_documents?: Array<{
    doc_kind: string;
    title?: string | null;
    item_title?: string | null;
    meeting_date?: string | null;
    pdf_url?: string | null;
    source_url?: string | null;
  }>;
}

export interface CommitteeWorkItemDetail extends CommitteeWorkItem {
  full_description?: string;
  stage?: string;
  shadow_rapporteurs: Array<{
    name: string;
    group?: string;
    mep_id?: string;
  }>;
  timeline_events: Array<{
    date: string;
    event: string;
    status?: string;
  }>;
  vote_date?: string;
  vote_result?: string;
  related_documents: Array<{
    title: string;
    url: string;
    type?: string;
  }>;
  celex_numbers: string[];
  legislative_carriage_id?: string;
  eurlex_url?: string;
  source_url?: string;
  first_seen: string;
  scraped_at?: string;
  is_tracked: boolean;
  user_notes?: string;
  tracked_since?: string;
}

export interface TrackedCommitteeWorkItem {
  work_item: CommitteeWorkItem;
  tracked_since: string;
  notify_on_status_change: boolean;
  notify_on_rapporteur_change: boolean;
  notify_on_new_documents: boolean;
  notes?: string;
  last_notified_at?: string;
}

export interface Committee {
  code: string;
  name: string;
  full_name: string;
  policy_area: string;
}

export interface CommitteeWorkFilters {
  committee_code?: string;
  procedure_type?: ProcedureType;
  status?: CommitteeWorkStatus;
  search?: string;
  min_relevance?: number;
  has_rapporteur?: boolean;
}

interface CommitteeWorkState {
  // Data
  items: CommitteeWorkItem[];
  selectedItem: CommitteeWorkItemDetail | null;
  trackedItems: TrackedCommitteeWorkItem[];
  committees: Committee[];
  totalItems: number;

  // Filters
  filters: CommitteeWorkFilters;
  sortBy: string;
  sortDesc: boolean;
  limit: number;
  offset: number;

  // Loading states
  isLoadingItems: boolean;
  isLoadingDetail: boolean;
  isLoadingTracked: boolean;
  isLoadingCommittees: boolean;
  isTracking: boolean;

  // Actions
  fetchItems: () => Promise<void>;
  fetchItemDetail: (itemId: string) => Promise<void>;
  fetchTrackedItems: () => Promise<void>;
  fetchCommittees: () => Promise<void>;
  trackItem: (itemId: string, options?: {
    notify_on_status_change?: boolean;
    notify_on_rapporteur_change?: boolean;
    notify_on_new_documents?: boolean;
    notes?: string;
  }) => Promise<void>;
  untrackItem: (itemId: string) => Promise<void>;
  updateTracking: (itemId: string, options: {
    notify_on_status_change?: boolean;
    notify_on_rapporteur_change?: boolean;
    notify_on_new_documents?: boolean;
    notes?: string;
  }) => Promise<void>;
  setFilters: (filters: CommitteeWorkFilters) => void;
  setSort: (sortBy: string, sortDesc: boolean) => void;
  setPage: (offset: number) => void;
  closeItemDetail: () => void;
  clearFilters: () => void;
}

export const useCommitteeWork = create<CommitteeWorkState>((set, get) => ({
  // Initial state
  items: [],
  selectedItem: null,
  trackedItems: [],
  committees: [],
  totalItems: 0,
  filters: {},
  sortBy: 'last_updated',
  sortDesc: true,
  limit: 50,
  offset: 0,
  isLoadingItems: false,
  isLoadingDetail: false,
  isLoadingTracked: false,
  isLoadingCommittees: false,
  isTracking: false,

  // Fetch items with current filters
  fetchItems: async () => {
    set({ isLoadingItems: true });

    try {
      const { filters, sortBy, sortDesc, limit, offset } = get();

      const params = new URLSearchParams();
      if (filters.committee_code) params.append('committee_code', filters.committee_code);
      if (filters.procedure_type) params.append('procedure_type', filters.procedure_type);
      if (filters.status) params.append('status', filters.status);
      if (filters.search) params.append('search', filters.search);
      if (filters.min_relevance !== undefined) params.append('min_relevance', filters.min_relevance.toString());
      if (filters.has_rapporteur !== undefined) params.append('has_rapporteur', filters.has_rapporteur.toString());
      params.append('sort_by', sortBy);
      params.append('sort_desc', sortDesc.toString());
      params.append('limit', limit.toString());
      params.append('offset', offset.toString());

      const response = await axios.get<{
        items: CommitteeWorkItem[];
        total: number;
        limit: number;
        offset: number;
      }>(`${API_BASE}/committee-work/items?${params.toString()}`);

      set({
        items: response.data.items,
        totalItems: response.data.total,
        isLoadingItems: false,
      });
    } catch (error) {
      console.error('Failed to fetch committee work items:', error);
      set({ isLoadingItems: false });
    }
  },

  // Fetch item detail
  fetchItemDetail: async (itemId: string) => {
    set({ isLoadingDetail: true });

    try {
      const response = await axios.get<CommitteeWorkItemDetail>(
        `${API_BASE}/committee-work/items/${itemId}`
      );

      set({
        selectedItem: response.data,
        isLoadingDetail: false,
      });
    } catch (error) {
      console.error('Failed to fetch item detail:', error);
      set({ isLoadingDetail: false });
    }
  },

  // Fetch tracked items
  fetchTrackedItems: async () => {
    set({ isLoadingTracked: true });

    try {
      const response = await axios.get<{
        items: TrackedCommitteeWorkItem[];
        total: number;
      }>(`${API_BASE}/committee-work/tracked`);

      set({
        trackedItems: response.data.items || [],
        isLoadingTracked: false,
      });
    } catch (error) {
      console.error('Failed to fetch tracked items:', error);
      set({ isLoadingTracked: false });
    }
  },

  // Fetch committees list
  fetchCommittees: async () => {
    set({ isLoadingCommittees: true });

    try {
      const response = await axios.get<{
        committees: Committee[];
        total: number;
      }>(`${API_BASE}/committee-work/committees`);

      set({
        committees: response.data.committees || [],
        isLoadingCommittees: false,
      });
    } catch (error) {
      console.error('Failed to fetch committees:', error);
      set({ isLoadingCommittees: false });
    }
  },

  // Track an item
  trackItem: async (itemId: string, options = {}) => {
    set({ isTracking: true });

    try {
      await axios.post(`${API_BASE}/committee-work/track/${itemId}`, {
        notify_on_status_change: options.notify_on_status_change ?? true,
        notify_on_rapporteur_change: options.notify_on_rapporteur_change ?? true,
        notify_on_new_documents: options.notify_on_new_documents ?? true,
        notes: options.notes,
      });

      // Refresh tracked items
      await get().fetchTrackedItems();

      // Update selected item if it's the one we just tracked
      const selectedItem = get().selectedItem;
      if (selectedItem && selectedItem.id === itemId) {
        await get().fetchItemDetail(itemId);
      }

      set({ isTracking: false });
    } catch (error) {
      console.error('Failed to track item:', error);
      set({ isTracking: false });
      throw error;
    }
  },

  // Untrack an item
  untrackItem: async (itemId: string) => {
    set({ isTracking: true });

    try {
      await axios.delete(`${API_BASE}/committee-work/track/${itemId}`);

      // Refresh tracked items
      await get().fetchTrackedItems();

      // Update selected item if it's the one we just untracked
      const selectedItem = get().selectedItem;
      if (selectedItem && selectedItem.id === itemId) {
        await get().fetchItemDetail(itemId);
      }

      set({ isTracking: false });
    } catch (error) {
      console.error('Failed to untrack item:', error);
      set({ isTracking: false });
      throw error;
    }
  },

  // Update tracking preferences
  updateTracking: async (itemId: string, options) => {
    set({ isTracking: true });

    try {
      await axios.patch(`${API_BASE}/committee-work/track/${itemId}`, options);

      // Refresh tracked items
      await get().fetchTrackedItems();

      set({ isTracking: false });
    } catch (error) {
      console.error('Failed to update tracking:', error);
      set({ isTracking: false });
      throw error;
    }
  },

  // Set filters
  setFilters: (filters: CommitteeWorkFilters) => {
    set({ filters, offset: 0 }); // Reset to first page when filters change
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
      sortBy: 'last_updated',
      sortDesc: true,
      offset: 0,
    });
    get().fetchItems();
  },
}));

// Procedure type display names and colors. Keyed by string so any OEIL code
// resolves; callers fall back to the raw code for anything not listed.
// `name` is a lazy getter so the label follows the active UI language.
const procType = (key: string, fallback: string, color: string, score: number) => ({
  get name(): string { return i18n.t(key, { defaultValue: fallback }); },
  color,
  score,
});
export const PROCEDURE_TYPE_INFO: Record<string, { name: string; color: string; score: number }> = {
  COD: procType('committeeWork.typeCod', 'Ordinary legislative', '#0066cc', 100),
  INL: procType('committeeWork.typeInl', 'Legislative initiative', '#0066cc', 90),
  APP: procType('committeeWork.typeApp', 'Consent', '#7c3aed', 80),
  CNS: procType('committeeWork.typeCns', 'Consultation', '#059669', 70),
  ACI: procType('committeeWork.typeAci', 'Interinstitutional agreement', '#6b7280', 65),
  BUD: procType('committeeWork.typeBud', 'Budget', '#0891b2', 60),
  GBD: procType('committeeWork.typeGbd', 'General budget', '#0891b2', 60),
  BUI: procType('committeeWork.typeBui', 'Budget initiative', '#0891b2', 58),
  DEC: procType('committeeWork.typeDec', 'Discharge', '#0891b2', 58),
  NLE: procType('committeeWork.typeNle', 'Agreement / appointment', '#d97706', 50),
  RSP: procType('committeeWork.typeRsp', 'Resolution', '#8b5cf6', 45),
  RSO: procType('committeeWork.typeRso', 'Internal resolution', '#8b5cf6', 42),
  INI: procType('committeeWork.typeIni', 'Own-initiative', '#6b7280', 40),
  COS: procType('committeeWork.typeCos', 'Strategy paper', '#6b7280', 40),
  DCE: procType('committeeWork.typeDce', 'Written declaration', '#9ca3af', 38),
  DEA: procType('committeeWork.typeDea', 'Delegated-act scrutiny', '#94a3b8', 30),
  RPS: procType('committeeWork.typeRps', 'Implementing-act scrutiny', '#94a3b8', 30),
  REG: procType('committeeWork.typeReg', 'Rules of Procedure', '#9ca3af', 25),
  IMM: procType('committeeWork.typeImm', 'MEP immunity', '#9ca3af', 15),
};

// Status display names and colors (lazy-translated, same pattern as above)
const statusInfo = (key: string, fallback: string, color: string) => ({
  get name(): string { return i18n.t(key, { defaultValue: fallback }); },
  color,
});
export const STATUS_INFO: Record<CommitteeWorkStatus, { name: string; color: string }> = {
  in_committee: statusInfo('committeeWork.statusInCommittee', 'In Committee', '#3b82f6'),
  awaiting_vote: statusInfo('committeeWork.statusAwaitingVote', 'Awaiting Vote', '#f59e0b'),
  tabled: statusInfo('amendmentsTab.statusTabled', 'Tabled', '#10b981'),
  adopted: statusInfo('amendmentsTab.statusAdopted', 'Adopted', '#059669'),
  rejected: statusInfo('amendmentsTab.statusRejected', 'Rejected', '#ef4444'),
  withdrawn: statusInfo('amendmentsTab.statusWithdrawn', 'Withdrawn', '#6b7280'),
  pending: statusInfo('committeeWork.statusPending', 'Pending', '#8b5cf6'),
  completed: statusInfo('committeeWork.statusCompleted', 'Completed', '#10b981'),
  unknown: statusInfo('committeeWork.statusUnknown', 'Unknown', '#9ca3af'),
};
