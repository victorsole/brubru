/**
 * Dashboard cockpit state.
 *
 * One fetch returns six tile envelopes plus profile completeness. Tiles
 * carry either real items or an honest empty state with a CTA — never mocks.
 */

import { create } from 'zustand';
import axios from 'axios';
import { useAuth } from './use_auth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export type TileEmptyReason =
  | 'no_profile'
  | 'no_tracked_files'
  | 'no_recent_activity'
  | 'no_matches';

export interface TileEmptyState {
  reason: TileEmptyReason;
  message: string;
  cta_label: string;
  cta_path: string;
}

interface TileBase {
  total: number;
  empty_state: TileEmptyState | null;
  drill_down_path: string;
  chat_handoff_prompt: string | null;
}

export interface NewThisWeekItem {
  carriage_id: string;
  title: string;
  procedure_ref?: string | null;
  current_status?: string | null;
  policy_areas: string[];
  matched_interests: string[];
  created_at?: string | null;
}

export interface TrackedFileMovingItem {
  carriage_id: string;
  title: string;
  procedure_ref?: string | null;
  old_status?: string | null;
  new_status?: string | null;
  changed_at?: string | null;
}

export interface PositionStressItem {
  carriage_id: string;
  title: string;
  procedure_ref?: string | null;
  signal: 'snapshot_refreshed' | 'amendments_tabled' | 'status_moved';
  detail: string;
  detected_at?: string | null;
}

export interface CalendarEventItem {
  event_id: string;
  title: string;
  institution?: string | null;
  event_type?: string | null;
  start_date: string;
  end_date?: string | null;
  source_url?: string | null;
  policy_areas: string[];
}

export interface ComplianceSignalItem {
  eu_law_id: number;
  celex?: string | null;
  title: string;
  policy_area?: string | null;
  adopted_on?: string | null;
}

export interface VoiceOpportunityItem {
  consultation_id: string;
  title: string;
  initiative_id?: string | null;
  end_date?: string | null;
  days_until_deadline?: number | null;
  policy_areas: string[];
}

export interface DashboardTiles {
  new_this_week: TileBase & { items: NewThisWeekItem[] };
  tracked_files_moving: TileBase & { items: TrackedFileMovingItem[] };
  positions_under_stress: TileBase & { items: PositionStressItem[] };
  next_seven_days: TileBase & { items: CalendarEventItem[] };
  compliance_signals: TileBase & { items: ComplianceSignalItem[] };
  voice_opportunities: TileBase & { items: VoiceOpportunityItem[] };
}

export interface ProfileCompleteness {
  score: number;
  has_policy_interests: boolean;
  has_organisation: boolean;
  has_country: boolean;
  has_tracked_files: boolean;
}

export interface DashboardResponse {
  tiles: DashboardTiles;
  profile_completeness: ProfileCompleteness;
  generated_at: string;
}

interface DashboardState {
  data: DashboardResponse | null;
  isLoading: boolean;
  error: string | null;
  fetchTiles: () => Promise<void>;
  reset: () => void;
}

export const useDashboard = create<DashboardState>((set) => ({
  data: null,
  isLoading: false,
  error: null,

  fetchTiles: async () => {
    const token = useAuth.getState().token;
    if (!token) {
      set({ data: null, error: null, isLoading: false });
      return;
    }
    set({ isLoading: true, error: null });
    try {
      const response = await axios.get<DashboardResponse>(
        `${API_URL}/api/dashboard/tiles`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      set({ data: response.data, isLoading: false });
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } };
      const detail = axiosErr.response?.data?.detail;
      set({
        data: null,
        error: detail || 'Failed to load dashboard tiles',
        isLoading: false,
      });
    }
  },

  reset: () => set({ data: null, isLoading: false, error: null }),
}));
