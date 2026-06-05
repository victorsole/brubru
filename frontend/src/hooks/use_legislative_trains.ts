/**
 * Legislative Trains State Management
 *
 * Zustand store for managing EU Legislative Train data.
 * Handles fetching trains, files, and AI enrichment.
 */

import { create } from 'zustand';
import axios from 'axios';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api`;

// Types
export interface LegislativeFile {
  id: string;
  file_id: string;
  title: string;
  description?: string;
  current_status: string;
  policy_areas: string[];
  ai_summary?: string;
  ai_policy_classifications?: Array<{
    label: string;
    score: number;
  }>;
  enriched_at?: string;
  last_updated?: string;
}

export interface TrackedFile {
  id: string;
  carriage_id: string;  // Database UUID for untracking
  file_id: string;      // Slug for detail endpoint
  title: string;
  current_status: string;
  previous_status?: string;
  oeil_procedure_ref?: string;
  celex_numbers?: string[];  // For loading in Amendator
  lead_committee?: string;
  tracked_since: string;
  last_updated?: string;
  is_blocked?: boolean;
  days_in_current_status?: number;
}

export interface LegislativeChange {
  file_id: string;
  title: string;
  change_type: 'status_change' | 'new_document' | 'blocking';
  old_value?: string;
  new_value?: string;
  changed_at: string;
  description?: string;
}

export interface KeyPlayer {
  name: string;
  role: string;
  political_group?: string;
  country?: string;
  mep_id?: string;
  photo_url?: string;
}

export interface TimelineEvent {
  date: string;
  event_type: string;
  description?: string;
  summary?: string;
  result?: string;
  documents?: Array<{ url: string; title?: string }>;
}

export interface LegislativeTrain {
  id: string;
  priority_number: number;
  name: string;
  description?: string;
  commission_term: string;
  total_files: number;
  files_by_status: Record<string, number>;
  created_at?: string;
  updated_at?: string;
  files?: LegislativeFile[];
}

export interface LegislativeFileDetail {
  id: string;
  file_id: string;
  train_id?: string;
  title: string;
  description?: string;
  current_status: string;
  status_history?: any[];
  days_in_current_status?: number;
  is_blocked: boolean;
  oeil_procedure_ref?: string;
  celex_numbers?: string[];
  legal_text_url?: string;
  lead_committee?: string;
  opinion_committees?: string[];
  committees?: string[];
  rapporteur_mep_id?: string;
  policy_areas: string[];
  ai_summary?: string;
  ai_policy_classifications?: Array<{
    label: string;
    score: number;
  }>;
  ai_entities?: Array<{
    type: string;
    text: string;
    confidence: number;
  }>;
  first_seen?: string;
  last_updated?: string;
  enriched_at?: string;
  enrichment_quality?: string;
  // EP Legislative Train editorial "state of play" narrative (joined by OEIL ref).
  legislative_train_summary?: string | null;
  legislative_train_url?: string | null;
  legislative_train_updated_at?: string | null;
}

interface LegislativeTrainState {
  // Data
  trains: LegislativeTrain[];
  selectedFile: LegislativeFileDetail | null;
  selectedFileIds: string[];  // For batch AI analysis
  trackedFiles: TrackedFile[];
  recentChanges: LegislativeChange[];
  keyPlayers: KeyPlayer[];
  timelineEvents: TimelineEvent[];

  // Loading states
  isLoadingTrains: boolean;
  isLoadingFileDetail: boolean;
  isAnalyzing: boolean;
  isLoadingTrackedFiles: boolean;
  isLoadingChanges: boolean;
  isLoadingKeyPlayers: boolean;
  isLoadingTimeline: boolean;
  isTracking: boolean;

  // Actions
  fetchTrains: () => Promise<void>;
  fetchFileDetail: (fileId: string) => Promise<void>;
  analyzeFile: (fileId: string) => Promise<void>;
  analyzeBatch: (fileIds: string[]) => Promise<void>;
  toggleFileSelection: (fileId: string) => void;
  clearFileSelection: () => void;
  closeFileDetail: () => void;

  // Tracked files actions
  fetchTrackedFiles: () => Promise<void>;
  fetchRecentChanges: (hours?: number) => Promise<void>;
  trackFile: (identifier: string, byCarriageId?: boolean) => Promise<void>;
  untrackFile: (identifier: string, byCarriageId?: boolean) => Promise<void>;
  fetchKeyPlayers: (carriageId: string) => Promise<void>;
  fetchTimeline: (carriageId: string) => Promise<void>;
}

export const useLegislativeTrains = create<LegislativeTrainState>((set, get) => ({
  // Initial state
  trains: [],
  selectedFile: null,
  selectedFileIds: [],
  trackedFiles: [],
  recentChanges: [],
  keyPlayers: [],
  timelineEvents: [],
  isLoadingTrains: false,
  isLoadingFileDetail: false,
  isAnalyzing: false,
  isLoadingTrackedFiles: false,
  isLoadingChanges: false,
  isLoadingKeyPlayers: false,
  isLoadingTimeline: false,
  isTracking: false,

  // Fetch all trains with their files
  fetchTrains: async () => {
    set({ isLoadingTrains: true });

    try {
      const response = await axios.get<{ trains: LegislativeTrain[] }>(
        `${API_BASE}/bubble/legislative-trains?include_files=true`
      );

      set({
        trains: response.data.trains,
        isLoadingTrains: false,
      });
    } catch (error) {
      console.error('Failed to fetch legislative trains:', error);
      set({ isLoadingTrains: false });
    }
  },

  // Fetch detailed info for a specific file
  fetchFileDetail: async (fileId: string) => {
    set({ isLoadingFileDetail: true });

    try {
      const response = await axios.get<LegislativeFileDetail>(
        `${API_BASE}/bubble/legislative-files/${fileId}`
      );

      set({
        selectedFile: response.data,
        isLoadingFileDetail: false,
      });
    } catch (error) {
      console.error('Failed to fetch file detail:', error);
      set({ isLoadingFileDetail: false });
    }
  },

  // AI analyze a single file
  analyzeFile: async (fileId: string) => {
    set({ isAnalyzing: true });

    try {
      await axios.post(`${API_BASE}/bubble/legislative-files/${fileId}/analyze`);

      // Refresh the file detail if it's currently selected
      const currentFile = get().selectedFile;
      if (currentFile && currentFile.file_id === fileId) {
        await get().fetchFileDetail(fileId);
      }

      // Refresh trains to update enrichment status
      await get().fetchTrains();

      set({ isAnalyzing: false });
    } catch (error) {
      console.error('Failed to analyze file:', error);
      set({ isAnalyzing: false });
      throw error;
    }
  },

  // AI analyze multiple files
  analyzeBatch: async (fileIds: string[]) => {
    set({ isAnalyzing: true });

    try {
      await axios.post(`${API_BASE}/bubble/legislative-files/analyze-batch`, fileIds);

      // Refresh trains to update enrichment status
      await get().fetchTrains();

      // Clear selection
      set({
        selectedFileIds: [],
        isAnalyzing: false,
      });
    } catch (error) {
      console.error('Failed to batch analyze files:', error);
      set({ isAnalyzing: false });
      throw error;
    }
  },

  // Toggle file selection for batch analysis
  toggleFileSelection: (fileId: string) => {
    set(state => {
      const isSelected = state.selectedFileIds.includes(fileId);
      return {
        selectedFileIds: isSelected
          ? state.selectedFileIds.filter(id => id !== fileId)
          : [...state.selectedFileIds, fileId],
      };
    });
  },

  // Clear file selection
  clearFileSelection: () => {
    set({ selectedFileIds: [] });
  },

  // Close file detail modal
  closeFileDetail: () => {
    set({ selectedFile: null });
  },

  // Fetch user's tracked files
  fetchTrackedFiles: async () => {
    set({ isLoadingTrackedFiles: true });

    try {
      const response = await axios.get<{ tracked_files: TrackedFile[] }>(
        `${API_BASE}/legislative-train/tracked`
      );

      set({
        trackedFiles: response.data.tracked_files || [],
        isLoadingTrackedFiles: false,
      });
    } catch (error) {
      console.error('Failed to fetch tracked files:', error);
      set({ isLoadingTrackedFiles: false });
    }
  },

  // Fetch recent changes for tracked files
  fetchRecentChanges: async (_hours: number = 168) => {
    set({ isLoadingChanges: true });

    try {
      // Note: Changes endpoint not yet implemented in legislative-train API
      // For now, return empty array
      set({
        recentChanges: [],
        isLoadingChanges: false,
      });
    } catch (error) {
      console.error('Failed to fetch recent changes:', error);
      set({ isLoadingChanges: false });
    }
  },

  // Track a legislative file - supports both procedure ref and carriage ID
  trackFile: async (identifier: string, byCarriageId: boolean = false) => {
    set({ isTracking: true });

    try {
      if (byCarriageId) {
        // Track by carriage UUID
        await axios.post(`${API_BASE}/legislative-train/track/${identifier}`);
      } else {
        // Track by procedure reference
        await axios.post(
          `${API_BASE}/legislative-train/track/by-procedure?procedure_ref=${encodeURIComponent(identifier)}`
        );
      }

      // Refresh tracked files
      await get().fetchTrackedFiles();

      set({ isTracking: false });
    } catch (error) {
      console.error('Failed to track file:', error);
      set({ isTracking: false });
      throw error;
    }
  },

  // Untrack a legislative file - supports both procedure ref and carriage ID
  untrackFile: async (identifier: string, byCarriageId: boolean = false) => {
    set({ isTracking: true });

    try {
      if (byCarriageId) {
        // Untrack by carriage UUID
        await axios.delete(`${API_BASE}/legislative-train/track/${identifier}`);
      } else {
        // Untrack by procedure reference
        await axios.delete(
          `${API_BASE}/legislative-train/track/by-procedure?procedure_ref=${encodeURIComponent(identifier)}`
        );
      }

      // Refresh tracked files
      await get().fetchTrackedFiles();

      set({ isTracking: false });
    } catch (error) {
      console.error('Failed to untrack file:', error);
      set({ isTracking: false });
      throw error;
    }
  },

  // Fetch key players for a carriage
  fetchKeyPlayers: async (carriageId: string) => {
    set({ isLoadingKeyPlayers: true });

    try {
      const response = await axios.get<{ key_players: KeyPlayer[] }>(
        `${API_BASE}/legislative-train/carriages/${carriageId}/key-players`
      );

      set({
        keyPlayers: response.data.key_players || [],
        isLoadingKeyPlayers: false,
      });
    } catch (error) {
      console.error('Failed to fetch key players:', error);
      set({ isLoadingKeyPlayers: false });
    }
  },

  // Fetch timeline events for a carriage
  fetchTimeline: async (carriageId: string) => {
    set({ isLoadingTimeline: true });

    try {
      const response = await axios.get<{ timeline: TimelineEvent[] }>(
        `${API_BASE}/legislative-train/carriages/${carriageId}/timeline`
      );

      set({
        timelineEvents: response.data.timeline || [],
        isLoadingTimeline: false,
      });
    } catch (error) {
      console.error('Failed to fetch timeline:', error);
      set({ isLoadingTimeline: false });
    }
  },
}));
