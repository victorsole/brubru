/**
 * EU Calendar Service
 *
 * API client for the My EU Calendar feature.
 * Provides types, institution config, and API calls for calendar events.
 *
 * Created: February 2026
 */

import axios from 'axios';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api/eu-calendar`;

// ============================================================================
// Types
// ============================================================================

export type InstitutionType =
  | 'EP'
  | 'COUNCIL'
  | 'EUROPEAN_COUNCIL'
  | 'COMMISSION'
  | 'ECJ'
  | 'ECB'
  | 'ESMA'
  | 'EMA'
  | 'EBA'
  | 'EIOPA';

export type EventType =
  | 'plenary_session'
  | 'committee_week'
  | 'committee_meeting'
  | 'group_week'
  | 'recess'
  | 'council_meeting'
  | 'informal_meeting'
  | 'european_council_summit'
  | 'eurogroup'
  | 'commission_college_meeting'
  | 'court_hearing'
  | 'ecb_governing_council'
  | 'agency_event'
  | 'special_date'
  | 'comitology_meeting'
  | 'expert_group_meeting'
  | 'grant_deadline';

export type EventStatus =
  | 'scheduled'
  | 'confirmed'
  | 'tentative'
  | 'cancelled'
  | 'completed'
  | 'postponed';

export interface CalendarEvent {
  id: string;
  institution: InstitutionType;
  event_type: EventType;
  title: string;
  description?: string;
  start_date: string;
  end_date?: string;
  start_time?: string;
  end_time?: string;
  all_day: boolean;
  council_configuration?: string;
  ep_activity_type?: string;
  ep_committee_code?: string;
  commission_dg?: string;
  policy_areas: string[];
  status: EventStatus;
  source_url?: string;
  agenda_url?: string;
  procedure_refs: string[];
  related_documents: Record<string, unknown>;
  source: string;
  external_id?: string;
  created_at: string;
  last_updated?: string;
}

export interface CalendarFilters {
  date_from?: string;
  date_to?: string;
  institution?: string;
  event_type?: string;
  policy_area?: string;
  search?: string;
}

export interface TodayDigest {
  today_count: number;
  today_events: CalendarEvent[];
  tomorrow_count: number;
  tomorrow_events: CalendarEvent[];
  ai_summary?: string;
}

export interface InstitutionInfo {
  code: string;
  name: string;
  short_name: string;
  mdi_icon: string;
  colour: string;
  calendar_url?: string;
}

export interface PolicyAreaInfo {
  code: string;
  label: string;
  colour: string;
  ep_committee_codes: string[];
  council_configs: string[];
}

export interface SyncResult {
  source: string;
  added: number;
  updated: number;
  skipped: number;
  errors: number;
  duration_seconds: number;
}

export interface SyncAllResult {
  results: SyncResult[];
  total_added: number;
  total_updated: number;
  total_errors: number;
}

// ============================================================================
// Institution Config (frontend display)
// ============================================================================

export interface InstitutionConfig {
  label: string;
  shortLabel: string;
  mdiIcon: string;
  colour: string;
}

export const INSTITUTION_CONFIG: Record<InstitutionType, InstitutionConfig> = {
  EP: { label: 'European Parliament', shortLabel: 'EP', mdiIcon: 'mdi-account-group', colour: '#0693e3' },
  COUNCIL: { label: 'Council of the EU', shortLabel: 'Council', mdiIcon: 'mdi-bank', colour: '#059669' },
  EUROPEAN_COUNCIL: { label: 'European Council', shortLabel: 'Eur. Council', mdiIcon: 'mdi-star-four-points', colour: '#d97706' },
  COMMISSION: { label: 'European Commission', shortLabel: 'Commission', mdiIcon: 'mdi-domain', colour: '#9b51e0' },
  ECJ: { label: 'Court of Justice', shortLabel: 'ECJ', mdiIcon: 'mdi-gavel', colour: '#dc2626' },
  ECB: { label: 'European Central Bank', shortLabel: 'ECB', mdiIcon: 'mdi-currency-eur', colour: '#0369a1' },
  ESMA: { label: 'ESMA', shortLabel: 'ESMA', mdiIcon: 'mdi-chart-line', colour: '#7c3aed' },
  EMA: { label: 'EMA', shortLabel: 'EMA', mdiIcon: 'mdi-pill', colour: '#0d9488' },
  EBA: { label: 'EBA', shortLabel: 'EBA', mdiIcon: 'mdi-cash', colour: '#b45309' },
  EIOPA: { label: 'EIOPA', shortLabel: 'EIOPA', mdiIcon: 'mdi-shield-check', colour: '#6366f1' },
};

export const POLICY_AREA_CONFIG: Record<string, { label: string; colour: string }> = {
  digital_ai: { label: 'Digital & AI', colour: '#2563eb' },
  green_deal: { label: 'Green Deal', colour: '#16a34a' },
  trade: { label: 'Trade', colour: '#9333ea' },
  defence: { label: 'Defence', colour: '#475569' },
  health: { label: 'Health', colour: '#dc2626' },
  agriculture: { label: 'Agriculture', colour: '#ca8a04' },
  migration: { label: 'Migration', colour: '#ea580c' },
  budget: { label: 'Budget', colour: '#0891b2' },
};

export const EVENT_TYPE_LABELS: Record<EventType, string> = {
  plenary_session: 'Plenary Session',
  committee_week: 'Committee Week',
  committee_meeting: 'Committee Meeting',
  group_week: 'Group Week',
  recess: 'Recess',
  council_meeting: 'Council Meeting',
  informal_meeting: 'Informal Meeting',
  european_council_summit: 'European Council Summit',
  eurogroup: 'Eurogroup',
  commission_college_meeting: 'College Meeting',
  court_hearing: 'Court Hearing',
  ecb_governing_council: 'Governing Council',
  agency_event: 'Agency Event',
  special_date: 'Special Date',
  comitology_meeting: 'Comitology',
  expert_group_meeting: 'Expert Group',
  grant_deadline: 'Grant Deadline',
};

// ============================================================================
// API Client
// ============================================================================

export const euCalendarService = {
  /**
   * Get events in a date range (for calendar views)
   */
  getEventsInRange: async (
    dateFrom: string,
    dateTo: string,
    institution?: string,
    policyArea?: string,
    committeeCode?: string,
  ): Promise<{ date_from: string; date_to: string; total: number; events: CalendarEvent[] }> => {
    const params = new URLSearchParams();
    params.append('date_from', dateFrom);
    params.append('date_to', dateTo);
    if (institution) params.append('institution', institution);
    if (policyArea) params.append('policy_area', policyArea);
    if (committeeCode) params.append('committee_code', committeeCode);

    const response = await axios.get(`${API_BASE}/events/range?${params.toString()}`);
    return response.data;
  },

  /**
   * Get paginated events with filters
   */
  getEvents: async (params: {
    filters?: CalendarFilters;
    limit?: number;
    offset?: number;
  }): Promise<{ total: number; events: CalendarEvent[] }> => {
    const queryParams = new URLSearchParams();

    if (params.filters) {
      const { filters } = params;
      if (filters.date_from) queryParams.append('date_from', filters.date_from);
      if (filters.date_to) queryParams.append('date_to', filters.date_to);
      if (filters.institution) queryParams.append('institution', filters.institution);
      if (filters.event_type) queryParams.append('event_type', filters.event_type);
      if (filters.policy_area) queryParams.append('policy_area', filters.policy_area);
      if (filters.search) queryParams.append('search', filters.search);
    }

    queryParams.append('limit', String(params.limit || 50));
    queryParams.append('offset', String(params.offset || 0));

    const response = await axios.get(`${API_BASE}/events?${queryParams.toString()}`);
    return response.data;
  },

  /**
   * Get single event by ID
   */
  getEvent: async (id: string): Promise<CalendarEvent> => {
    const response = await axios.get(`${API_BASE}/events/${id}`);
    return response.data;
  },

  /**
   * Get today's digest (My EU Today)
   */
  getTodayDigest: async (): Promise<TodayDigest> => {
    const response = await axios.get(`${API_BASE}/events/today`);
    return response.data;
  },

  /**
   * Get list of institutions
   */
  getInstitutions: async (): Promise<InstitutionInfo[]> => {
    const response = await axios.get(`${API_BASE}/institutions`);
    return response.data;
  },

  /**
   * Get list of policy areas
   */
  getPolicyAreas: async (): Promise<PolicyAreaInfo[]> => {
    const response = await axios.get(`${API_BASE}/policy-areas`);
    return response.data;
  },

  /**
   * Trigger sync (Blue/Admin only)
   */
  triggerSync: async (): Promise<SyncAllResult> => {
    const response = await axios.post(`${API_BASE}/sync`);
    return response.data;
  },
};

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get institution colour by code
 */
export function getInstitutionColour(code: InstitutionType): string {
  return INSTITUTION_CONFIG[code]?.colour || '#6b7280';
}

/**
 * Get institution label by code
 */
export function getInstitutionLabel(code: InstitutionType): string {
  return INSTITUTION_CONFIG[code]?.shortLabel || code;
}

/**
 * Get event type display label
 */
export function getEventTypeLabel(eventType: EventType): string {
  return EVENT_TYPE_LABELS[eventType] || eventType;
}

/**
 * Format a date string for display (e.g. "Mon 24 Feb")
 */
export function formatCalendarDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
}

/**
 * Format time string (e.g. "14:30")
 */
export function formatCalendarTime(timeStr?: string): string {
  if (!timeStr) return '';
  return timeStr.substring(0, 5);
}

/**
 * Calculate days until an event
 */
export function daysUntilEvent(dateStr: string): number {
  const eventDate = new Date(dateStr + 'T00:00:00');
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = eventDate.getTime() - today.getTime();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

/**
 * Get countdown text for an event
 */
export function getCountdownText(dateStr: string): string | null {
  const days = daysUntilEvent(dateStr);
  if (days < 0) return null;
  if (days === 0) return 'Today';
  if (days === 1) return 'Tomorrow';
  if (days <= 7) return `in ${days} days`;
  return null;
}

/**
 * EP Committee code to short label mapping.
 * Covers all 26 EP committees.
 */
const COMMITTEE_LABELS: Record<string, string> = {
  AFET: 'Foreign Affairs',
  DROI: 'Human Rights',
  SEDE: 'Security & Defence',
  DEVE: 'Development',
  INTA: 'International Trade',
  EUDS: 'EU-US Relations',
  BUDG: 'Budgets',
  CONT: 'Budgetary Control',
  ECON: 'Economic & Monetary',
  FISC: 'Tax Matters',
  EMPL: 'Employment & Social',
  FEMM: "Women's Rights",
  HOUS: 'Housing',
  ENVI: 'Environment & Health',
  SANT: 'Public Health',
  ITRE: 'Industry & Energy',
  IMCO: 'Internal Market',
  TRAN: 'Transport & Tourism',
  REGI: 'Regional Development',
  AGRI: 'Agriculture',
  PECH: 'Fisheries',
  CULT: 'Culture & Education',
  JURI: 'Legal Affairs',
  AFCO: 'Constitutional Affairs',
  LIBE: 'Civil Liberties',
  PETI: 'Petitions',
};

/**
 * Get committee display label by code
 */
export function getCommitteeLabel(code: string): string {
  return COMMITTEE_LABELS[code.toUpperCase()] || code;
}

/**
 * Get all committee codes for filter UI
 */
export const ALL_COMMITTEE_CODES = Object.keys(COMMITTEE_LABELS);

export default euCalendarService;
