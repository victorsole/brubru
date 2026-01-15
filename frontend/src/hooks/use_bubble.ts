/**
 * My EU Bubble State Management
 *
 * Zustand store for managing My EU Bubble data and state.
 * Handles documents, RSS feeds, subscriptions, and user interactions.
 */

import { create } from 'zustand';
import axios from 'axios';

// Types
export interface RSSEntry {
  id: string;
  feed_id: string;
  title: string;
  link: string;
  published_at: string;
  summary?: string;
  author?: string;
  categories: string[];
  institution?: string;
  is_read?: boolean;
  is_saved?: boolean;
  ai_summary?: string;
}

export interface UserDocument {
  id: string;
  document_type: 'amendment' | 'analysis' | 'strategy' | 'note';
  title: string;
  content?: string;
  policy_areas?: string[];
  tags?: string[];
  celex_number?: string;
  procedure_reference?: string;
  amendment_status?: string;
  created_at: string;
  updated_at: string;
  word_count?: number;
}

export interface FeedSubscription {
  id: string;
  feed_id: string;
  is_active: boolean;
  notification_enabled: boolean;
  feed?: {
    name: string;
    source: string;
  };
}

export interface UserStats {
  total_subscriptions: number;
  active_subscriptions: number;
  total_reads: number;
  total_saves: number;
  average_reading_time_seconds?: number;
  favorite_sources: string[];
  most_read_categories: string[];
}

export interface DocumentStats {
  total_documents: number;
  total_amendments?: number;
  by_type: Record<string, number>;
  by_policy_area: Record<string, number>;
  total_word_count: number;
}

interface BubbleState {
  // RSS Feeds
  feedEntries: RSSEntry[];
  unreadCount: number;
  isLoadingFeeds: boolean;
  availableSources: string[];

  // Documents
  documents: UserDocument[];
  selectedDocument: UserDocument | null;
  isLoadingDocuments: boolean;

  // Subscriptions
  subscriptions: FeedSubscription[];
  isLoadingSubscriptions: boolean;

  // Statistics
  userStats: UserStats | null;
  documentStats: DocumentStats | null;

  // Filters
  activeFilters: {
    sources: string[];
    policyAreas: string[];
    documentTypes: string[];
    unreadOnly: boolean;
  };

  // Actions - RSS Feeds
  fetchLatestFeeds: (filters?: {
    sources?: string[];
    unread_only?: boolean;
    limit?: number;
  }) => Promise<void>;
  fetchAvailableSources: () => Promise<void>;
  markAsRead: (entryId: string, readingTime?: number) => Promise<void>;
  saveEntry: (entryId: string, notes?: string, tags?: string[]) => Promise<void>;
  unsaveEntry: (savedId: string) => Promise<void>;

  // Actions - Documents
  fetchDocuments: (filters?: {
    document_type?: string;
    policy_areas?: string[];
    search?: string;
  }) => Promise<void>;
  createDocument: (document: Partial<UserDocument>) => Promise<void>;
  updateDocument: (id: string, updates: Partial<UserDocument>) => Promise<void>;
  deleteDocument: (id: string) => Promise<void>;
  selectDocument: (document: UserDocument | null) => void;

  // Actions - Subscriptions
  fetchSubscriptions: () => Promise<void>;
  subscribeToFeed: (feedId: string) => Promise<void>;
  unsubscribeFromFeed: (subscriptionId: string) => Promise<void>;

  // Actions - Statistics
  fetchUserStats: () => Promise<void>;
  fetchDocumentStats: () => Promise<void>;

  // Actions - Filters
  setFilters: (filters: Partial<BubbleState['activeFilters']>) => void;
  clearFilters: () => void;
}

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api`;

export const useBubble = create<BubbleState>((set) => ({
  // Initial state
  feedEntries: [],
  unreadCount: 0,
  isLoadingFeeds: false,
  availableSources: [],

  documents: [],
  selectedDocument: null,
  isLoadingDocuments: false,

  subscriptions: [],
  isLoadingSubscriptions: false,

  userStats: null,
  documentStats: null,

  activeFilters: {
    sources: [],
    policyAreas: [],
    documentTypes: [],
    unreadOnly: false,
  },

  // RSS Feeds Actions
  fetchLatestFeeds: async (filters = {}) => {
    set({ isLoadingFeeds: true });

    try {
      const params: any = {
        limit: filters.limit || 50,
      };

      if (filters.sources && filters.sources.length > 0) {
        params.sources = filters.sources.join(',');
      }

      if (filters.unread_only) {
        params.unread_only = true;
      }

      const response = await axios.get(`${API_BASE}/bubble/feeds`, { params });

      set({
        feedEntries: response.data.entries,
        unreadCount: response.data.entries.filter((e: RSSEntry) => !e.is_read).length,
        isLoadingFeeds: false,
      });
    } catch (error) {
      console.error('Failed to fetch feeds:', error);
      set({ isLoadingFeeds: false });
    }
  },

  fetchAvailableSources: async () => {
    try {
      const response = await axios.get(`${API_BASE}/bubble/sources`);
      set({ availableSources: response.data });
    } catch (error) {
      console.error('Failed to fetch available sources:', error);
    }
  },

  markAsRead: async (entryId: string, readingTime?: number) => {
    try {
      await axios.post(`${API_BASE}/bubble/entries/${entryId}/read`, {
        reading_time_seconds: readingTime,
        clicked_link: true,
      });

      // Update local state
      set(state => ({
        feedEntries: state.feedEntries.map(entry =>
          entry.id === entryId ? { ...entry, is_read: true } : entry
        ),
        unreadCount: Math.max(0, state.unreadCount - 1),
      }));
    } catch (error) {
      console.error('Failed to mark as read:', error);
    }
  },

  saveEntry: async (entryId: string, notes?: string, tags?: string[]) => {
    try {
      await axios.post(`${API_BASE}/bubble/entries/${entryId}/save`, {
        notes,
        tags,
      });

      // Update local state
      set(state => ({
        feedEntries: state.feedEntries.map(entry =>
          entry.id === entryId ? { ...entry, is_saved: true } : entry
        ),
      }));
    } catch (error) {
      console.error('Failed to save entry:', error);
    }
  },

  unsaveEntry: async (savedId: string) => {
    try {
      await axios.delete(`${API_BASE}/bubble/saved/${savedId}`);
    } catch (error) {
      console.error('Failed to unsave entry:', error);
    }
  },

  // Documents Actions
  fetchDocuments: async (filters = {}) => {
    set({ isLoadingDocuments: true });

    try {
      const params: any = {};

      if (filters.document_type) {
        params.document_type = filters.document_type;
      }

      if (filters.policy_areas && filters.policy_areas.length > 0) {
        params.policy_areas = filters.policy_areas;
      }

      if (filters.search) {
        params.search = filters.search;
      }

      const response = await axios.get(`${API_BASE}/documents`, { params });

      set({
        documents: response.data.documents,
        isLoadingDocuments: false,
      });
    } catch (error) {
      console.error('Failed to fetch documents:', error);
      set({ isLoadingDocuments: false });
    }
  },

  createDocument: async (document: Partial<UserDocument>) => {
    try {
      const response = await axios.post(`${API_BASE}/documents`, document);

      set(state => ({
        documents: [response.data, ...state.documents],
      }));
    } catch (error) {
      console.error('Failed to create document:', error);
      throw error;
    }
  },

  updateDocument: async (id: string, updates: Partial<UserDocument>) => {
    try {
      const response = await axios.patch(`${API_BASE}/documents/${id}`, updates);

      set(state => ({
        documents: state.documents.map(doc =>
          doc.id === id ? response.data : doc
        ),
        selectedDocument: state.selectedDocument?.id === id ? response.data : state.selectedDocument,
      }));
    } catch (error) {
      console.error('Failed to update document:', error);
      throw error;
    }
  },

  deleteDocument: async (id: string) => {
    try {
      await axios.delete(`${API_BASE}/documents/${id}`);

      set(state => ({
        documents: state.documents.filter(doc => doc.id !== id),
        selectedDocument: state.selectedDocument?.id === id ? null : state.selectedDocument,
      }));
    } catch (error) {
      console.error('Failed to delete document:', error);
      throw error;
    }
  },

  selectDocument: (document: UserDocument | null) => {
    set({ selectedDocument: document });
  },

  // Subscriptions Actions
  fetchSubscriptions: async () => {
    set({ isLoadingSubscriptions: true });

    try {
      const response = await axios.get(`${API_BASE}/bubble/subscriptions`);

      set({
        subscriptions: response.data,
        isLoadingSubscriptions: false,
      });
    } catch (error) {
      console.error('Failed to fetch subscriptions:', error);
      set({ isLoadingSubscriptions: false });
    }
  },

  subscribeToFeed: async (feedId: string) => {
    try {
      const response = await axios.post(`${API_BASE}/bubble/subscriptions`, {
        feed_id: feedId,
        notification_enabled: false
      });

      set(state => ({
        subscriptions: [...state.subscriptions, response.data],
      }));
    } catch (error) {
      console.error('Failed to subscribe:', error);
      throw error;
    }
  },

  unsubscribeFromFeed: async (subscriptionId: string) => {
    try {
      await axios.delete(`${API_BASE}/bubble/subscriptions/${subscriptionId}`);

      set(state => ({
        subscriptions: state.subscriptions.filter(sub => sub.id !== subscriptionId),
      }));
    } catch (error) {
      console.error('Failed to unsubscribe:', error);
      throw error;
    }
  },

  // Statistics Actions
  fetchUserStats: async () => {
    try {
      const response = await axios.get(`${API_BASE}/bubble/stats`);
      set({ userStats: response.data });
    } catch (error) {
      console.error('Failed to fetch user stats:', error);
    }
  },

  fetchDocumentStats: async () => {
    try {
      console.log('📡 Fetching document stats from:', `${API_BASE}/documents/stats/summary`);
      const response = await axios.get(`${API_BASE}/documents/stats/summary`);
      console.log('✅ Document stats received:', response.data);
      console.log('📊 Total amendments in response:', response.data.total_amendments);
      set({ documentStats: response.data });
    } catch (error) {
      console.error('Failed to fetch document stats:', error);
      // Set empty stats on error to prevent undefined issues
      set({
        documentStats: {
          total_documents: 0,
          total_amendments: 0,
          by_type: {},
          by_policy_area: {},
          total_word_count: 0
        }
      });
    }
  },

  // Filter Actions
  setFilters: (filters: Partial<BubbleState['activeFilters']>) => {
    set(state => ({
      activeFilters: {
        ...state.activeFilters,
        ...filters,
      },
    }));
  },

  clearFilters: () => {
    set({
      activeFilters: {
        sources: [],
        policyAreas: [],
        documentTypes: [],
        unreadOnly: false,
      },
    });
  },
}));
