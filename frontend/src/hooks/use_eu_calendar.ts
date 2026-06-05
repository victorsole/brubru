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

  // Filters — cascading dropdowns (Phase B): single-select institution -> dependent
  // department (committee / DG / Council configuration) + policy area.
  selectedInstitution: string;   // '' = all
  selectedDepartment: string;    // '' = all (committee | DG | config, per institution)
  selectedPolicyArea: string;    // '' = all
  selectedEventType: string;     // '' = all (plenary / committee / council / summit / …)
  bodies: Record<string, { code: string; name: string; kind?: string }[]>;
  myInterests: boolean;
  searchQuery: string;
  // Legacy chip state (kept for compatibility; the UI now uses the dropdowns above)
  activeInstitutions: Set<InstitutionType>;
  activePolicyAreas: Set<string>;
  activeCommittees: Set<string>;

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
  setMyInterests: (on: boolean) => void;
  fetchBodies: () => Promise<void>;
  setInstitution: (code: string) => void;
  setDepartment: (code: string) => void;
  setPolicyArea: (code: string) => void;
  setEventType: (code: string) => void;
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
  selectedInstitution: '',
  selectedDepartment: '',
  selectedPolicyArea: '',
  selectedEventType: '',
  bodies: {},
  activeInstitutions: new Set<InstitutionType>(),
  activePolicyAreas: new Set<string>(),
  activeCommittees: new Set<string>(),
  myInterests: false,
  searchQuery: '',
  isLoading: false,
  isLoadingDigest: false,
  error: null,

  // Fetch events for current view
  fetchEvents: async () => {
    set({ isLoading: true, error: null });

    try {
      const { viewMode, currentDate, selectedInstitution, selectedDepartment, selectedPolicyArea, selectedEventType, myInterests } = get();
      const { dateFrom, dateTo } = getDateRange(viewMode, currentDate);

      const instFilter = selectedInstitution || undefined;
      const paFilter = selectedPolicyArea || undefined;
      let etFilter = selectedEventType || undefined;
      // The dependent "department" maps to a different column per institution.
      let cmFilter: string | undefined;
      let dgFilter: string | undefined;
      let cfgFilter: string | undefined;
      let orgFilter: string | undefined;
      if (selectedDepartment) {
        if (selectedInstitution === 'EP') {
          // EP values are type-prefixed: committee:AGRI | organiser:Renew Europe | eventtype:plenary_session
          const idx = selectedDepartment.indexOf(':');
          const kind = idx >= 0 ? selectedDepartment.slice(0, idx) : 'committee';
          const val = idx >= 0 ? selectedDepartment.slice(idx + 1) : selectedDepartment;
          if (kind === 'committee') cmFilter = val;
          else if (kind === 'organiser') orgFilter = val;
          else if (kind === 'eventtype') etFilter = val;
        } else if (selectedInstitution === 'COMMISSION') dgFilter = selectedDepartment;
        else if (selectedInstitution === 'COUNCIL') cfgFilter = selectedDepartment;
      }

      const response = await euCalendarService.getEventsInRange(
        dateFrom, dateTo, instFilter, paFilter, cmFilter, myInterests, dgFilter, cfgFilter, etFilter, orgFilter
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

  // Toggle institution filter.
  //
  // Semantics: an EMPTY set means "no filter, show every institution"
  // (this is how the UI renders all chips as active on first load). The
  // first click while empty therefore populates the set with everything
  // *except* the clicked code (the user is deselecting one). Symmetric
  // collapse: if a click would result in a full set, clear it instead so
  // we return to the "all-active default" state.
  toggleInstitution: (code: InstitutionType) => {
    const { activeInstitutions } = get();
    const all = PHASE1_INSTITUTIONS;
    let updated: Set<InstitutionType>;
    if (activeInstitutions.size === 0) {
      // From "all active" → deselect the clicked one.
      updated = new Set(all.filter((c) => c !== code));
    } else {
      updated = new Set(activeInstitutions);
      if (updated.has(code)) {
        updated.delete(code);
      } else {
        updated.add(code);
      }
      // If the user has re-selected everything, collapse back to empty
      // ("all-active default") so we don't send a redundant filter.
      if (updated.size === all.length) {
        updated = new Set<InstitutionType>();
      }
    }
    set({ activeInstitutions: updated });
    get().fetchEvents();
  },

  // Toggle policy area filter. Same semantics as institutions.
  togglePolicyArea: (code: string) => {
    const { activePolicyAreas } = get();
    const all = POLICY_AREA_CODES;
    let updated: Set<string>;
    if (activePolicyAreas.size === 0) {
      updated = new Set(all.filter((c) => c !== code));
    } else {
      updated = new Set(activePolicyAreas);
      if (updated.has(code)) {
        updated.delete(code);
      } else {
        updated.add(code);
      }
      if (updated.size === all.length) {
        updated = new Set<string>();
      }
    }
    set({ activePolicyAreas: updated });
    get().fetchEvents();
  },

  // Toggle committee filter. Committees stay off by default (the row only
  // appears when EP is in the active institutions), so we keep the
  // simpler "click to add / click to remove" toggle without the
  // empty-means-all rule.
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

  // PI lens: restrict to events touching the user's Policy Interests. The
  // backend resolves the interests from the signed-in user; we just pass the flag.
  setMyInterests: (on: boolean) => {
    set({ myInterests: on });
    get().fetchEvents();
  },

  // Cascading dropdowns (Phase B): institution -> dependent department.
  fetchBodies: async () => {
    try {
      const bodies = await euCalendarService.getBodies();
      set({ bodies });
    } catch (error) {
      console.error('Failed to fetch calendar bodies:', error);
    }
  },

  setInstitution: (code: string) => {
    // Changing institution resets the dependent department.
    set({ selectedInstitution: code, selectedDepartment: '' });
    get().fetchEvents();
  },

  setDepartment: (code: string) => {
    set({ selectedDepartment: code });
    get().fetchEvents();
  },

  setPolicyArea: (code: string) => {
    set({ selectedPolicyArea: code });
    get().fetchEvents();
  },

  setEventType: (code: string) => {
    set({ selectedEventType: code });
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
      selectedInstitution: '',
      selectedDepartment: '',
      selectedPolicyArea: '',
      selectedEventType: '',
      activeInstitutions: new Set(),
      activePolicyAreas: new Set(),
      activeCommittees: new Set(),
      myInterests: false,
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
 * All available institution filter options. THIRD_PARTY surfaces euagenda.eu
 * events (think tanks, conferences, webinars, training) added 22 April 2026.
 */
export const PHASE1_INSTITUTIONS: InstitutionType[] = [
  'EP', 'COUNCIL', 'EUROPEAN_COUNCIL', 'COMMISSION', 'ECB', 'EMA',
  // All-EU bodies with calendar events (1 Jun 2026)
  'COR', 'FRA', 'EU_OSHA', 'CEPOL', 'EIT', 'EUROFOUND', 'EEAS',
  'THIRD_PARTY',
];

// The four core EU institutions (+ ECB) get their own optgroup; everything else
// is grouped under "Agencies & bodies" so the growing list stays easy to scan.
export const CORE_INSTITUTIONS: InstitutionType[] = [
  'EP', 'COUNCIL', 'EUROPEAN_COUNCIL', 'COMMISSION', 'ECB',
];

// Event types offered in the calendar's "Type" filter (the meaningful subset of
// EventType). Labels are i18n'd in the component via calendar.eventType.<code>.
export const FILTERABLE_EVENT_TYPES: string[] = [
  'plenary_session', 'committee_meeting', 'council_meeting', 'european_council_summit',
  'eurogroup', 'commission_college_meeting', 'conference', 'webinar', 'workshop',
  'agency_event', 'court_hearing',
];

// EP "body" dropdown — the non-committee groups. Values are type-prefixed so the
// hook routes them to the right backend filter (committee_code / organiser /
// event_type). Committees come from the /bodies endpoint (bodies['EP']).
export const EP_DELEGATION_OPTIONS: { value: string; label: string }[] = [
  { value: 'committee:DELE', label: 'All delegations' },
];
export const EP_GROUP_OPTIONS: { value: string; label: string }[] = [
  { value: 'organiser:S&D Group', label: 'S&D' },
  { value: 'organiser:Renew Europe', label: 'Renew Europe' },
  { value: 'organiser:ECR Group', label: 'ECR' },
  { value: 'organiser:Greens/EFA', label: 'Greens/EFA' },
];
export const EP_OTHER_OPTIONS: { value: string; label: string }[] = [
  { value: 'eventtype:plenary_session', label: 'Plenary' },
  { value: 'organiser:EPRS', label: 'EPRS (research events)' },
];

/**
 * All policy area codes for filters
 */
export const POLICY_AREA_CODES = Object.keys(POLICY_AREA_CONFIG);
