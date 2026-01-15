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
}

interface LegislativeTrainState {
  // Data
  trains: LegislativeTrain[];
  selectedFile: LegislativeFileDetail | null;
  selectedFileIds: string[];  // For batch AI analysis

  // Loading states
  isLoadingTrains: boolean;
  isLoadingFileDetail: boolean;
  isAnalyzing: boolean;

  // Actions
  fetchTrains: () => Promise<void>;
  fetchFileDetail: (fileId: string) => Promise<void>;
  analyzeFile: (fileId: string) => Promise<void>;
  analyzeBatch: (fileIds: string[]) => Promise<void>;
  toggleFileSelection: (fileId: string) => void;
  clearFileSelection: () => void;
  closeFileDetail: () => void;
}

export const useLegislativeTrains = create<LegislativeTrainState>((set, get) => ({
  // Initial state
  trains: [],
  selectedFile: null,
  selectedFileIds: [],
  isLoadingTrains: false,
  isLoadingFileDetail: false,
  isAnalyzing: false,

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
}));
