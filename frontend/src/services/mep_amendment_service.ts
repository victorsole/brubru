/**
 * MEP Amendment Service
 *
 * API client for EP committee amendment data.
 * Endpoints: /api/mep-amendments/*
 *
 * Created: February 2026
 */

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api/mep-amendments`;

// ============================================================================
// Types
// ============================================================================

export interface MEPAmendment {
  id: string;
  procedure_reference: string;
  committee_code: string;
  pe_reference: string;
  amendment_number: number;
  author_names: string[];
  political_group: string | null;
  on_behalf_of_group: boolean;
  element_type: string;
  element_number: string | null;
  element_reference: string;
  amendment_type: 'modification' | 'suppression' | 'addition';
  original_text: string;
  proposed_text: string;
  justification: string | null;
  original_language: string;
  source_url: string;
  parsing_confidence: number;
  document_date: string | null;
}

export interface MEPAmendmentListResponse {
  items: MEPAmendment[];
  total: number;
  limit: number;
  offset: number;
  filters_applied: Record<string, string> | null;
}

export interface AmendmentDocument {
  id: string;
  procedure_reference: string;
  committee_code: string;
  pe_reference: string;
  document_type: string;
  document_date: string | null;
  doceo_url: string;
  rapporteur_name: string | null;
  total_amendments: number;
  status: string;
  error_message: string | null;
  scraped_at: string | null;
}

export interface GroupAmendmentCount {
  political_group: string;
  count: number;
  percentage: number;
}

export interface ElementAmendmentCount {
  element_reference: string;
  element_type: string;
  count: number;
}

export interface TypeAmendmentCount {
  amendment_type: string;
  count: number;
  percentage: number;
}

export interface RapporteurInfo {
  name: string;
  political_group: string | null;
  photo_url: string | null;
  mep_id: string | null;
}

export interface AmendmentStats {
  procedure_reference: string;
  total_amendments: number;
  total_documents: number;
  committees: string[];
  rapporteur: RapporteurInfo | null;
  by_group: GroupAmendmentCount[];
  by_element: ElementAmendmentCount[];
  by_type: TypeAmendmentCount[];
  top_authors: Array<{ name: string; group: string; count: number }>;
}

export interface AmendmentFilters {
  group?: string;
  author?: string;
  element_type?: string;
  amendment_type?: string;
  committee?: string;
}

// ============================================================================
// Alignment Scoring Types (Phase 4)
// ============================================================================

export interface AlignmentScoreItem {
  mep_amendment_id: string;
  score: number;
  explanation: string | null;
  author_names: string[];
  political_group: string | null;
  element_reference: string;
  amendment_type: string;
}

export interface AlignmentResponse {
  procedure_reference: string;
  policy_position_hash: string;
  total_scored: number;
  score_distribution: Record<string, number>;
  scores: AlignmentScoreItem[];
}

export interface ComparisonAlly {
  name: string;
  group: string;
  avg_score: number;
  count: number;
}

export interface LandscapeGroup {
  group: string;
  avg_score: number;
  count: number;
}

export interface ComparisonData {
  best_allies: ComparisonAlly[];
  coverage_gaps: { user_unique: string[]; blind_spots: string[] };
  political_landscape: {
    supportive: LandscapeGroup[];
    mixed: LandscapeGroup[];
    opposed: LandscapeGroup[];
  };
}

// ============================================================================
// API Functions
// ============================================================================

function authHeaders(token: string): Record<string, string> {
  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
}

/**
 * List amendments for a procedure with optional filters.
 */
export async function listAmendments(
  procedureRef: string,
  token: string,
  filters: AmendmentFilters = {},
  limit = 20,
  offset = 0
): Promise<MEPAmendmentListResponse> {
  const params = new URLSearchParams();
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  if (filters.group) params.set('group', filters.group);
  if (filters.author) params.set('author', filters.author);
  if (filters.element_type) params.set('element_type', filters.element_type);
  if (filters.amendment_type) params.set('amendment_type', filters.amendment_type);
  if (filters.committee) params.set('committee', filters.committee);

  const res = await fetch(
    `${API_BASE}/${encodeURIComponent(procedureRef)}?${params}`,
    { headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Failed to list amendments: ${res.status}`);
  return res.json();
}

/**
 * Get aggregated statistics for a procedure.
 */
export async function getStats(
  procedureRef: string,
  token: string
): Promise<AmendmentStats> {
  const res = await fetch(
    `${API_BASE}/${encodeURIComponent(procedureRef)}/stats`,
    { headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Failed to get stats: ${res.status}`);
  return res.json();
}

/**
 * List parsed documents for a procedure.
 */
export async function listDocuments(
  procedureRef: string,
  token: string
): Promise<{ items: AmendmentDocument[]; total: number }> {
  const res = await fetch(
    `${API_BASE}/${encodeURIComponent(procedureRef)}/documents`,
    { headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Failed to list documents: ${res.status}`);
  return res.json();
}

/**
 * Trigger fetch & parse for a procedure.
 */
export async function fetchAmendments(
  procedureRef: string,
  token: string,
  force = false
): Promise<{
  procedure_reference: string;
  documents_found: number;
  documents_parsed: number;
  amendments_stored: number;
  errors: string[];
}> {
  const res = await fetch(
    `${API_BASE}/fetch/${encodeURIComponent(procedureRef)}`,
    {
      method: 'POST',
      headers: authHeaders(token),
      body: JSON.stringify({ force_refetch: force }),
    }
  );
  if (!res.ok) throw new Error(`Failed to fetch amendments: ${res.status}`);
  return res.json();
}

/**
 * Get unique procedure references that have amendment data.
 * Uses the sync-status endpoint (admin) or lists documents grouped by procedure.
 * For non-admin users, we query a known set of procedures from tracked files.
 */
export async function getAvailableProcedures(
  token: string
): Promise<Array<{ procedure_ref: string; committee: string; total_amendments: number }>> {
  // Use sync-status for admin, fall back to a lightweight approach
  try {
    const res = await fetch(`${API_BASE}/sync-status`, {
      headers: authHeaders(token),
    });
    if (res.ok) {
      const data = await res.json();
      // Extract procedures from by_committee data
      return Object.entries(data.by_committee || {}).map(([committee, count]) => ({
        procedure_ref: committee,
        committee,
        total_amendments: count as number,
      }));
    }
  } catch {
    // Not admin - that's fine
  }
  return [];
}

// ============================================================================
// Alignment Scoring API (Phase 4)
// ============================================================================

/**
 * Score MEP amendments against a policy position using AI.
 * Results are cached server-side.
 */
export async function scoreAlignment(
  procedureRef: string,
  token: string,
  policyPosition: string,
): Promise<AlignmentResponse> {
  const res = await fetch(
    `${API_BASE}/${encodeURIComponent(procedureRef)}/alignment`,
    {
      method: 'POST',
      headers: authHeaders(token),
      body: JSON.stringify({ policy_position: policyPosition }),
    }
  );
  if (!res.ok) throw new Error(`Alignment scoring failed: ${res.status}`);
  return res.json();
}

/**
 * Get comparative analysis from cached alignment scores.
 */
export async function getComparison(
  procedureRef: string,
  token: string,
  policyPositionHash: string,
): Promise<ComparisonData> {
  const params = new URLSearchParams({ policy_position_hash: policyPositionHash });
  const res = await fetch(
    `${API_BASE}/${encodeURIComponent(procedureRef)}/comparison?${params}`,
    { headers: authHeaders(token) }
  );
  if (!res.ok) throw new Error(`Comparison failed: ${res.status}`);
  return res.json();
}
