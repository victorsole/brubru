/**
 * Proactive Chat openers.
 *
 * Fetches briefings Brubru wants to surface to the authenticated user. Each
 * briefing is grounded in real DB rows (see backend
 * services/proactive/trigger_engine.py); never mocks.
 */

import { create } from 'zustand';
import axios from 'axios';
import { useAuth } from './use_auth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export type ProactiveTriggerSource =
  | 'morning_brief'
  | 'new_file_match'
  | 'tracked_file_movement'
  | 'amendment_surge';

export interface ProactiveBriefing {
  trigger_source: ProactiveTriggerSource;
  title: string;
  summary: string;
  suggested_query: string;
  evidence_refs: string[];
  drill_down_path: string | null;
}

interface ProactivePendingResponse {
  briefings: ProactiveBriefing[];
  cap_reached: boolean;
}

interface ProactiveState {
  briefings: ProactiveBriefing[];
  dismissedTitles: Set<string>;
  isLoading: boolean;
  fetchPending: () => Promise<void>;
  dismiss: (title: string) => void;
  reset: () => void;
}

export const useProactive = create<ProactiveState>((set, get) => ({
  briefings: [],
  dismissedTitles: new Set<string>(),
  isLoading: false,

  fetchPending: async () => {
    const token = useAuth.getState().token;
    if (!token) {
      set({ briefings: [], isLoading: false });
      return;
    }
    set({ isLoading: true });
    try {
      const response = await axios.get<ProactivePendingResponse>(
        `${API_URL}/api/proactive/pending`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      set({ briefings: response.data.briefings || [], isLoading: false });
    } catch {
      set({ briefings: [], isLoading: false });
    }
  },

  dismiss: (title: string) => {
    const next = new Set(get().dismissedTitles);
    next.add(title);
    set({ dismissedTitles: next });
  },

  reset: () => set({ briefings: [], dismissedTitles: new Set<string>(), isLoading: false }),
}));
