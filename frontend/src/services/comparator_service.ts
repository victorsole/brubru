/**
 * Comparator Service
 *
 * API client for the Comparator feature: spreadsheet-style legislative-file
 * comparison grids with verifiable per-cell citations.
 *
 * Backend: backend/api/comparator.py
 */

import axios from 'axios';
import { useAuth } from '../hooks/use_auth';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api/comparator`;

function authHeaders() {
  const token = useAuth.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ============================================================================
// Types
// ============================================================================

export interface ColumnDef {
  key: string;
  label: string;
}

export interface CitationObject {
  source?: string;
  procedure_ref?: string;
  url?: string;
  celex?: string;
  pe_reference?: string;
  doc_type?: string;
  event_type?: string;
  event_date?: string;
  as_of?: string;
  verbatim?: string;
  [k: string]: unknown;
}

export interface Cell {
  file_ref: string;
  column_key: string;
  value_text: string | null;
  citation: CitationObject | null;
  computation_status: 'pending' | 'computed' | 'failed' | 'stale';
  computation_error: string | null;
  computed_at: string | null;
}

export interface GridSummary {
  id: string;
  name: string;
  file_refs: string[];
  columns: ColumnDef[];
  created_at: string;
  updated_at: string;
  cell_count: number;
}

export interface SearchHit {
  file_ref: string;
  label: string;
  subtitle: string | null;
  type: 'celex' | 'oeil';
  alias: string | null;
  source: 'alias' | 'celex' | 'oeil' | 'my_files' | 'suggested';
  committee: string | null;
  deep_dive_url: string | null;
  deep_dive_short_title: string | null;
}

export interface SearchResponse {
  query: string;
  hits: SearchHit[];
}

export interface SuggestedResponse {
  files: SearchHit[];
  my_committees: string[];
}

export interface ResolveResponse {
  metadata: Record<string, SearchHit>;
}

export interface GridDetail extends GridSummary {
  cells: Cell[];
  file_metadata: Record<string, SearchHit>;
}

export interface TierLimits {
  max_grids: number;
  max_rows: number;
  max_cols: number;
}

export interface GridList {
  grids: GridSummary[];
  total: number;
  tier_limits: TierLimits;
}

export interface ComputeResponse {
  grid_id: string;
  cells_computed: number;
  cells_failed: number;
  duration_seconds: number;
}

export interface CatalogResponse {
  columns: ColumnDef[];
}

export interface GridCreatePayload {
  name: string;
  file_refs?: string[];
  columns?: ColumnDef[];
}

export interface GridPatchPayload {
  name?: string;
  file_refs?: string[];
  columns?: ColumnDef[];
}

// ============================================================================
// API
// ============================================================================

export const comparatorService = {
  async getCatalog(): Promise<CatalogResponse> {
    const res = await axios.get(`${API_BASE}/catalog`);
    return res.data;
  },

  async listGrids(): Promise<GridList> {
    const res = await axios.get(`${API_BASE}/grids`, { headers: authHeaders() });
    return res.data;
  },

  async getGrid(gridId: string): Promise<GridDetail> {
    const res = await axios.get(`${API_BASE}/grids/${gridId}`, { headers: authHeaders() });
    return res.data;
  },

  async createGrid(body: GridCreatePayload): Promise<GridDetail> {
    const res = await axios.post(`${API_BASE}/grids`, body, { headers: authHeaders() });
    return res.data;
  },

  async patchGrid(gridId: string, body: GridPatchPayload): Promise<GridDetail> {
    const res = await axios.patch(`${API_BASE}/grids/${gridId}`, body, { headers: authHeaders() });
    return res.data;
  },

  async deleteGrid(gridId: string): Promise<void> {
    await axios.delete(`${API_BASE}/grids/${gridId}`, { headers: authHeaders() });
  },

  async computeGrid(gridId: string): Promise<ComputeResponse> {
    const res = await axios.post(`${API_BASE}/grids/${gridId}/compute`, {}, { headers: authHeaders() });
    return res.data;
  },

  async search(q: string, limit: number = 12): Promise<SearchResponse> {
    const res = await axios.get(`${API_BASE}/search`, {
      params: { q, limit },
    });
    return res.data;
  },

  async myFiles(): Promise<SearchHit[]> {
    const res = await axios.get(`${API_BASE}/my-files`, { headers: authHeaders() });
    return res.data;
  },

  async suggested(): Promise<SuggestedResponse> {
    const res = await axios.get(`${API_BASE}/suggested`, { headers: authHeaders() });
    return res.data;
  },

  async resolve(refs: string[]): Promise<ResolveResponse> {
    const res = await axios.post(`${API_BASE}/resolve`, { refs });
    return res.data;
  },
};
