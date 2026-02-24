/**
 * EU Calendar State Management
 *
 * Zustand store for the My EU Calendar feature.
 * Manages events, view mode, filters, and the My EU Today digest.
 *
 * Created: February 2026
 */

import { create } from 'zustand';
import {
  euCalendarService,
  POLICY_AREA_CONFIG,
} from '../services/eu_calendar_service';
import type {
  CalendarEvent,
  InstitutionType,
  TodayDigest,
} from '../services/eu_calendar_service';

// ============================================================================
// Types
// ============================================================================

export type ViewMode = 'month' | 'week' | 'day';

interface EUCalendarState {
  // Data
  events: CalendarEvent[];
  selectedEvent: CalendarEvent | null;
  todayDigest: TodayDigest | null;

  // View
  viewMode: ViewMode;
  currentDate: Date;

  // Filters
  activeInstitutions: Set<InstitutionType>;
  activePolicyAreas: Set<string>;
  activeCommittees: Set<string>;
  searchQuery: string;

  // Loading
  isLoading: boolean;
  isLoadingDigest: boolean;
  error: string | null;

  // Actions
  fetchEvents: () => Promise<void>;
  fetchTodayDigest: () => Promise<void>;
  setViewMode: (mode: ViewMode) => void;
  navigateDate: (direction: 'prev' | 'next' | 'today') => void;
  goToDate: (date: Date) => void;
  toggleInstitution: (code: InstitutionType) => void;
  togglePolicyArea: (code: string) => void;
  toggleCommittee: (code: string) => void;
  selectEvent: (event: CalendarEvent | null) => void;
  setSearchQuery: (query: string) => void;
  clearFilters: () => void;
  clearError: () => void;
}

// ============================================================================
// Helpers
// ============================================================================

function getDateRange(viewMode: ViewMode, currentDate: Date): { dateFrom: string; dateTo: string } {
  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  const day = currentDate.getDate();
  const dayOfWeek = currentDate.getDay();

  let from: Date;
  let to: Date;

  switch (viewMode) {
    case 'month': {
      // Start from first day of month's week, end at last day of month's week
      from = new Date(year, month, 1);
      // Go back to Monday of that week
      const firstDayOfWeek = from.getDay();
      const offset = firstDayOfWeek === 0 ? 6 : firstDayOfWeek - 1;
      from.setDate(from.getDate() - offset);
      // End of month + extend to Sunday
      to = new Date(year, month + 1, 0);
      const lastDayOfWeek = to.getDay();
      const endOffset = lastDayOfWeek === 0 ? 0 : 7 - lastDayOfWeek;
      to.setDate(to.getDate() + endOffset);
      break;
    }
    case 'week': {
      // Monday to Sunday
      const mondayOffset = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
      from = new Date(year, month, day - mondayOffset);
      to = new Date(from);
      to.setDate(to.getDate() + 6);
      break;
    }
    case 'day': {
      from = new Date(year, month, day);
      to = new Date(year, month, day);
      break;
    }
  }

  return {
    dateFrom: formatDateISO(from),
    dateTo: formatDateISO(to),
  };
}

function formatDateISO(d: Date): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

// ============================================================================
// Store
// ============================================================================

export const useEUCalendar = create<EUCalendarState>((set, get) => ({
  // Initial state
  events: [],
  selectedEvent: null,
  todayDigest: null,
  viewMode: 'month',
  currentDate: new Date(),
  activeInstitutions: new Set<InstitutionType>(),
  activePolicyAreas: new Set<string>(),
  activeCommittees: new Set<string>(),
  searchQuery: '',
  isLoading: false,
  isLoadingDigest: false,
  error: null,

  // Fetch events for current view
  fetchEvents: async () => {
    set({ isLoading: true, error: null });

    try {
      const { viewMode, currentDate, activeInstitutions, activePolicyAreas, activeCommittees } = get();
      const { dateFrom, dateTo } = getDateRange(viewMode, currentDate);

      // Build institution filter
      const instFilter = activeInstitutions.size > 0
        ? Array.from(activeInstitutions).join(',')
        : undefined;

      // Build policy area filter
      const paFilter = activePolicyAreas.size > 0
        ? Array.from(activePolicyAreas).join(',')
        : undefined;

      // Build committee filter
      const cmFilter = activeCommittees.size > 0
        ? Array.from(activeCommittees).join(',')
        : undefined;

      const response = await euCalendarService.getEventsInRange(
        dateFrom, dateTo, instFilter, paFilter, cmFilter
      );

      set({
        events: response.events,
        isLoading: false,
      });
    } catch (error) {
      console.error('Failed to fetch calendar events:', error);
      set({
        isLoading: false,
        error: 'Failed to load calendar events',
      });
    }
  },

  // Fetch My EU Today digest
  fetchTodayDigest: async () => {
    set({ isLoadingDigest: true });

    try {
      const digest = await euCalendarService.getTodayDigest();
      set({
        todayDigest: digest,
        isLoadingDigest: false,
      });
    } catch (error) {
      console.error('Failed to fetch today digest:', error);
      set({ isLoadingDigest: false });
    }
  },

  // Set view mode
  setViewMode: (mode: ViewMode) => {
    set({ viewMode: mode });
    get().fetchEvents();
  },

  // Navigate date
  navigateDate: (direction: 'prev' | 'next' | 'today') => {
    const { viewMode, currentDate } = get();

    if (direction === 'today') {
      set({ currentDate: new Date() });
      get().fetchEvents();
      return;
    }

    const delta = direction === 'prev' ? -1 : 1;
    const newDate = new Date(currentDate);

    switch (viewMode) {
      case 'month':
        newDate.setMonth(newDate.getMonth() + delta);
        break;
      case 'week':
        newDate.setDate(newDate.getDate() + delta * 7);
        break;
      case 'day':
        newDate.setDate(newDate.getDate() + delta);
        break;
    }

    set({ currentDate: newDate });
    get().fetchEvents();
  },

  // Go to specific date (e.g. clicking a day in month view)
  goToDate: (date: Date) => {
    set({ currentDate: date, viewMode: 'day' });
    get().fetchEvents();
  },

  // Toggle institution filter
  toggleInstitution: (code: InstitutionType) => {
    const { activeInstitutions } = get();
    const updated = new Set(activeInstitutions);
    if (updated.has(code)) {
      updated.delete(code);
    } else {
      updated.add(code);
    }
    set({ activeInstitutions: updated });
    get().fetchEvents();
  },

  // Toggle policy area filter
  togglePolicyArea: (code: string) => {
    const { activePolicyAreas } = get();
    const updated = new Set(activePolicyAreas);
    if (updated.has(code)) {
      updated.delete(code);
    } else {
      updated.add(code);
    }
    set({ activePolicyAreas: updated });
    get().fetchEvents();
  },

  // Toggle committee filter
  toggleCommittee: (code: string) => {
    const { activeCommittees } = get();
    const updated = new Set(activeCommittees);
    if (updated.has(code)) {
      updated.delete(code);
    } else {
      updated.add(code);
    }
    set({ activeCommittees: updated });
    get().fetchEvents();
  },

  // Select event for detail modal
  selectEvent: (event: CalendarEvent | null) => {
    set({ selectedEvent: event });
  },

  // Set search query
  setSearchQuery: (query: string) => {
    set({ searchQuery: query });
  },

  // Clear all filters
  clearFilters: () => {
    set({
      activeInstitutions: new Set(),
      activePolicyAreas: new Set(),
      activeCommittees: new Set(),
      searchQuery: '',
    });
    get().fetchEvents();
  },

  // Clear error
  clearError: () => {
    set({ error: null });
  },
}));

// ============================================================================
// Derived Data Helpers
// ============================================================================

/**
 * Get events grouped by date (for month/week views)
 */
export function groupEventsByDate(events: CalendarEvent[]): Map<string, CalendarEvent[]> {
  const grouped = new Map<string, CalendarEvent[]>();
  for (const event of events) {
    const date = event.start_date;
    if (!grouped.has(date)) {
      grouped.set(date, []);
    }
    grouped.get(date)!.push(event);
  }
  return grouped;
}

/**
 * Get all institution codes that have active events
 */
export function getActiveInstitutionCodes(events: CalendarEvent[]): InstitutionType[] {
  const codes = new Set<InstitutionType>();
  for (const event of events) {
    codes.add(event.institution);
  }
  return Array.from(codes);
}

/**
 * All available institution filter options (Phase 1: EP, Council, Eur. Council, Commission)
 */
export const PHASE1_INSTITUTIONS: InstitutionType[] = [
  'EP', 'COUNCIL', 'EUROPEAN_COUNCIL', 'COMMISSION', 'ECB',
];

/**
 * All policy area codes for filters
 */
export const POLICY_AREA_CODES = Object.keys(POLICY_AREA_CONFIG);
