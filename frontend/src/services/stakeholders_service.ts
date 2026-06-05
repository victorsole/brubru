/**
 * Stakeholder Mapping service (MEUB Section 4 - Strategy). Wraps /api/stakeholders:
 * the PI-aware actor graph (file mode or PI-overview) + the focusable-files list.
 */
import axios from 'axios';
import { useAuth } from '../hooks/use_auth';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api/stakeholders`;

function authHeaders() {
  const token = useAuth.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Bound every call so a hung backend surfaces an error instead of an endless spinner.
const TIMEOUT = 25000;

export type SMInstitution = 'file' | 'ep' | 'ec' | 'council' | 'stakeholder';
export type SMNodeType = 'file' | 'committee' | 'mep' | 'dg' | 'official' | 'council_config' | 'org';

export interface SMNode {
  id: string;
  type: SMNodeType;
  institution: SMInstitution;
  label: string;
  sublabel?: string;
  relevance: number;
  pi_match?: boolean;
  stance?: 'support' | 'oppose' | 'amend' | null;
  url?: string | null;
  meta?: Record<string, any>;
}
export interface SMEdge {
  source: string;
  target: string;
  rel: string;
  source_kind: string;
  weight?: number;
}
export interface SMGraph {
  mode: 'file' | 'pi';
  focus: { id: string; label: string };
  pi_active: boolean;
  nodes: SMNode[];
  edges: SMEdge[];
  counts: Record<string, number>;
  sources_used: string[];
  not_found?: boolean;
}
export interface SMFile { ref: string; title?: string; committee?: string; status?: string | null }
export interface SMFilesResult { tracked: boolean; files: SMFile[] }

export interface SMPerson { name: string; function?: string | null; email?: string | null }
export interface SMUnit { code: string; name: string; relevant: boolean; head?: SMPerson | null }
export interface SMDirectorate { code: string; name: string; relevant: boolean; director?: SMPerson | null; units: SMUnit[] }
export interface SMDgContacts {
  dg: string; dg_name: string; url: string;
  director_general?: SMPerson | null; deputies: SMPerson[];
  directorates: SMDirectorate[]; relevant_count: number;
}
export interface SMContactsResult { dgs: SMDgContacts[]; pi_active: boolean }
export interface SMDirectoryResult { section: string; total: number; page: number; page_size: number; items: SMNode[] }

function qs(file: string | undefined, myInterests: boolean): string {
  const p = new URLSearchParams();
  if (file) p.set('file', file);
  p.set('my_interests', String(myInterests));
  return `?${p.toString()}`;
}

export const stakeholdersService = {
  graph: async (file?: string, myInterests = true): Promise<SMGraph> => {
    const r = await axios.get(`${API_BASE}/graph${qs(file, myInterests)}`, { headers: authHeaders(), timeout: TIMEOUT });
    return r.data;
  },
  files: async (myInterests = true): Promise<SMFilesResult> => {
    const r = await axios.get(`${API_BASE}/files?my_interests=${myInterests}`, { headers: authHeaders(), timeout: TIMEOUT });
    return r.data;
  },
  contacts: async (file?: string, myInterests = true): Promise<SMContactsResult> => {
    const r = await axios.get(`${API_BASE}/contacts${qs(file, myInterests)}`, { headers: authHeaders(), timeout: TIMEOUT });
    return r.data;
  },
  contactsByDg: async (dg: string): Promise<SMContactsResult> => {
    const r = await axios.get(`${API_BASE}/contacts?dg=${encodeURIComponent(dg)}`, { headers: authHeaders(), timeout: TIMEOUT });
    return r.data;
  },
  directory: async (section: string, q = '', page = 1, pageSize = 30): Promise<SMDirectoryResult> => {
    const p = new URLSearchParams({ section, q, page: String(page), page_size: String(pageSize) });
    const r = await axios.get(`${API_BASE}/directory?${p.toString()}`, { headers: authHeaders(), timeout: TIMEOUT });
    return r.data;
  },
  strategyDraft: async (file: string): Promise<{ title: string; objectives: string; content: string; procedure_reference?: string; stakeholders: string[] }> => {
    const r = await axios.get(`${API_BASE}/strategy-draft?file=${encodeURIComponent(file)}`, { headers: authHeaders(), timeout: TIMEOUT });
    return r.data;
  },
};
