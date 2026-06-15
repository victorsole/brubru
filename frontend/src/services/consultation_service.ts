/**
 * Consultation Service
 *
 * API client for EC Public Consultations (Have Your Say portal).
 *
 * Created: January 2026
 */

import axios from 'axios';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api/consultations`;

// ============================================================================
// Types
// ============================================================================

export type ConsultationType =
  | 'public_consultation'
  | 'call_for_evidence'
  | 'feedback'
  | 'roadmap'
  | 'initiative';

export type ConsultationStatus =
  | 'open'
  | 'upcoming'
  | 'closed'
  | 'outcome_published'
  | 'withdrawn';

export type SubmissionStatus =
  | 'not_started'
  | 'draft'
  | 'submitted'
  | 'not_participating';

export type DocumentType =
  | 'questionnaire'
  | 'impact_assessment'
  | 'draft_act'
  | 'explanatory_memo'
  | 'annex'
  | 'factsheet'
  | 'summary'
  | 'inception_impact_assessment'
  | 'roadmap'
  | 'outcome_report'
  | 'statistics'
  | 'other';

export interface ConsultationDocument {
  id: string;
  title: string;
  document_type: DocumentType;
  file_url?: string;
  file_size?: number;
  file_format?: string;
  language: string;
}

export interface ConsultationListItem {
  id: string;
  initiative_id: string;
  title: string;
  short_title?: string;
  consultation_type: ConsultationType;
  status: ConsultationStatus;
  dg_responsible?: string;
  dg_name?: string;
  policy_areas: string[];
  start_date?: string;
  end_date?: string;
  days_remaining?: number;
  is_closing_soon: boolean;
  feedback_count: number;
  relevance_score: number;
  is_tracked: boolean;
  portal_url?: string;
  // All-EU hub: 'commission' (Have Your Say) | 'agency' (EU agency consultation).
  source?: string;
  source_body?: string;
  body_name?: string;
}

export interface ConsultationDetail extends ConsultationListItem {
  publication_id?: string;
  description?: string;
  full_description?: string;
  objectives?: string;
  target_group?: string;
  views_count?: number;
  feedback_url?: string;
  com_references: string[];
  celex_numbers: string[];
  outcome_summary?: string;
  outcome_published_date?: string;
  outcome_document_url?: string;
  documents: ConsultationDocument[];
  user_notes?: string;
  tracked_since?: string;
  submission_status?: SubmissionStatus;
  created_at: string;
  last_updated: string;
}

export interface TrackedConsultation {
  consultation: ConsultationListItem;
  tracked_since: string;
  notify_on_deadline: boolean;
  notify_on_outcome: boolean;
  notify_days_before: number;
  submission_status: SubmissionStatus;
  notes?: string;
  priority: number;
  last_notified_at?: string;
}

export interface DGInfo {
  code: string;
  name: string;
  full_name: string;
}

export interface PolicyAreaInfo {
  code: string;
  name: string;
}

export interface ConsultationFilters {
  status?: ConsultationStatus;
  consultation_type?: ConsultationType;
  dg?: string;
  policy_area?: string;
  search?: string;
  closing_soon?: boolean;
  min_relevance?: number;
  my_interests?: boolean;
}

export interface TrackingOptions {
  notify_on_deadline?: boolean;
  notify_on_outcome?: boolean;
  notify_days_before?: number;
  notes?: string;
  priority?: number;
}

export interface UpdateTrackingOptions extends TrackingOptions {
  submission_status?: SubmissionStatus;
}

export interface SyncStatus {
  last_sync?: string;
  total_consultations: number;
  open_count: number;
  closed_count: number;
  outcome_count: number;
  consultations_by_dg: Record<string, number>;
  consultations_by_policy_area: Record<string, number>;
}

export interface SyncResult {
  added: number;
  updated: number;
  skipped: number;
  errors: number;
  status_changes: number;
  duration_seconds: number;
}

// ============================================================================
// AI Analysis Types (Yellow+ tier)
// ============================================================================

export interface ConsultationAnalysis {
  consultation_id: string;
  executive_summary: string;
  key_questions: string[];
  stakeholder_categories: string[];
  submission_requirements?: string;
  legislation_context?: string;
  key_provisions_under_review: string[];
  potential_impacts: string[];
  recommended_focus_areas: string[];
  confidence_score: number;
  generated_at: string;
}

// ============================================================================
// AI Proposals Types (Blue tier only)
// ============================================================================

export interface ProposalItem {
  id: number;
  question_addressed: string;
  proposed_response: string;
  supporting_arguments: string[];
  evidence_citations: string[];
  source_documents: string[];
  tone_suggestion: string;
  confidence_score: number;
}

export interface ProposalSet {
  consultation_id: string;
  overall_strategy: string;
  recommended_tone: string;
  key_messages: string[];
  proposals: ProposalItem[];
  tokens_used: number;
  generated_at: string;
}

export interface GenerateProposalsOptions {
  document_ids?: string[];
  focus_areas?: string[];
}

// ============================================================================
// API Client
// ============================================================================

export const consultationService = {
  // -------------------------------------------------------------------------
  // List and Search
  // -------------------------------------------------------------------------

  /**
   * Get consultations with optional filters
   */
  getConsultations: async (params: {
    filters?: ConsultationFilters;
    sort_by?: string;
    sort_desc?: boolean;
    limit?: number;
    offset?: number;
  }) => {
    const queryParams = new URLSearchParams();

    if (params.filters) {
      const { filters } = params;
      if (filters.status) queryParams.append('status', filters.status);
      if (filters.consultation_type) queryParams.append('consultation_type', filters.consultation_type);
      if (filters.dg) queryParams.append('dg', filters.dg);
      if (filters.policy_area) queryParams.append('policy_area', filters.policy_area);
      if (filters.search) queryParams.append('search', filters.search);
      if (filters.closing_soon !== undefined) queryParams.append('closing_soon', String(filters.closing_soon));
      if (filters.min_relevance !== undefined) queryParams.append('min_relevance', String(filters.min_relevance));
      if (filters.my_interests) queryParams.append('my_interests', 'true');
    }

    queryParams.append('sort_by', params.sort_by || 'end_date');
    queryParams.append('sort_desc', String(params.sort_desc ?? false));
    queryParams.append('limit', String(params.limit || 50));
    queryParams.append('offset', String(params.offset || 0));

    const response = await axios.get<{
      items: ConsultationListItem[];
      total: number;
      limit: number;
      offset: number;
      filters_applied?: Record<string, unknown>;
    }>(`${API_BASE}?${queryParams.toString()}`);

    return response.data;
  },

  /**
   * Get single consultation details
   */
  getConsultation: async (id: string) => {
    const response = await axios.get<ConsultationDetail>(`${API_BASE}/${id}`);
    return response.data;
  },

  /**
   * Search consultations by keyword
   */
  searchConsultations: async (query: string, limit = 20) => {
    const response = await axios.get<{
      items: ConsultationListItem[];
      total: number;
    }>(`${API_BASE}?search=${encodeURIComponent(query)}&limit=${limit}`);
    return response.data.items;
  },

  // -------------------------------------------------------------------------
  // Tracking
  // -------------------------------------------------------------------------

  /**
   * Get user's tracked consultations
   */
  getTrackedConsultations: async () => {
    const response = await axios.get<{
      items: TrackedConsultation[];
      total: number;
    }>(`${API_BASE}/tracked`);
    return response.data;
  },

  /**
   * Track a consultation
   */
  trackConsultation: async (id: string, options?: TrackingOptions) => {
    const response = await axios.post(`${API_BASE}/${id}/track`, options || {});
    return response.data;
  },

  /**
   * Untrack a consultation
   */
  untrackConsultation: async (id: string) => {
    const response = await axios.delete(`${API_BASE}/${id}/track`);
    return response.data;
  },

  /**
   * Update tracking preferences
   */
  updateTracking: async (id: string, options: UpdateTrackingOptions) => {
    const response = await axios.patch(`${API_BASE}/${id}/track`, options);
    return response.data;
  },

  // -------------------------------------------------------------------------
  // Reference Data
  // -------------------------------------------------------------------------

  /**
   * Get list of Directorate-Generals
   */
  getDGs: async () => {
    const response = await axios.get<{
      dgs: DGInfo[];
      total: number;
    }>(`${API_BASE}/dgs`);
    return response.data.dgs;
  },

  /**
   * Get list of policy areas
   */
  getPolicyAreas: async () => {
    const response = await axios.get<{
      policy_areas: PolicyAreaInfo[];
      total: number;
    }>(`${API_BASE}/policy-areas`);
    return response.data.policy_areas;
  },

  // -------------------------------------------------------------------------
  // Sync (Admin)
  // -------------------------------------------------------------------------

  /**
   * Get sync status
   */
  getSyncStatus: async () => {
    const response = await axios.get<SyncStatus>(`${API_BASE}/sync/status`);
    return response.data;
  },

  /**
   * Trigger sync
   */
  triggerSync: async (options?: { status?: string; max_pages?: number }) => {
    const params = new URLSearchParams();
    if (options?.status) params.append('status_filter', options.status);
    if (options?.max_pages) params.append('max_pages', String(options.max_pages));

    const response = await axios.post<SyncResult>(`${API_BASE}/sync?${params.toString()}`);
    return response.data;
  },

  // -------------------------------------------------------------------------
  // AI Analysis (Yellow+ tier)
  // -------------------------------------------------------------------------

  /**
   * Get AI analysis of a consultation
   */
  getAnalysis: async (consultationId: string) => {
    const response = await axios.get<ConsultationAnalysis>(
      `${API_BASE}/${consultationId}/analysis`
    );
    return response.data;
  },

  // -------------------------------------------------------------------------
  // AI Proposals (Blue tier only)
  // -------------------------------------------------------------------------

  /**
   * Generate AI proposals for a consultation
   */
  generateProposals: async (
    consultationId: string,
    options?: GenerateProposalsOptions
  ) => {
    const response = await axios.post<ProposalSet>(
      `${API_BASE}/${consultationId}/proposals`,
      options || {}
    );
    return response.data;
  },

  /**
   * Refine a specific proposal
   */
  refineProposal: async (
    consultationId: string,
    proposalId: number,
    userFeedback: string
  ) => {
    const response = await axios.post<ProposalItem>(
      `${API_BASE}/${consultationId}/proposals/refine`,
      {
        proposal_id: proposalId,
        user_feedback: userFeedback,
      }
    );
    return response.data;
  },
};

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get display label for consultation type
 */
export function getConsultationTypeLabel(type: ConsultationType): string {
  const labels: Record<ConsultationType, string> = {
    public_consultation: 'Public Consultation',
    call_for_evidence: 'Call for Evidence',
    feedback: 'Feedback',
    roadmap: 'Roadmap',
    initiative: 'Initiative',
  };
  return labels[type] || type;
}

/**
 * Get display label for consultation status
 */
export function getStatusLabel(status: ConsultationStatus): string {
  const labels: Record<ConsultationStatus, string> = {
    open: 'Open',
    upcoming: 'Upcoming',
    closed: 'Closed',
    outcome_published: 'Outcome Published',
    withdrawn: 'Withdrawn',
  };
  return labels[status] || status;
}

/**
 * Get color for consultation status
 */
export function getStatusColor(status: ConsultationStatus): string {
  const colors: Record<ConsultationStatus, string> = {
    open: '#059669',      // Green
    upcoming: '#3b82f6',  // Blue
    closed: '#d97706',    // Amber
    outcome_published: '#0693e3', // Light blue
    withdrawn: '#6b7280', // Gray
  };
  return colors[status] || '#6b7280';
}

/**
 * Format days remaining text
 */
export function formatDaysRemaining(days?: number): string {
  if (days === undefined || days === null) return '';
  if (days === 0) return 'Closes today';
  if (days === 1) return '1 day left';
  if (days <= 7) return `${days} days left`;
  if (days <= 30) return `${days} days remaining`;
  return '';
}

export default consultationService;
