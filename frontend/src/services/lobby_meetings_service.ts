/**
 * Lobby Meetings service (MEUB Section 3). Wraps /api/lobby-meetings:
 * PI-filtered Commission Transparency Register meetings + a dashboard stats call.
 */
import axios from 'axios';
import { useAuth } from '../hooks/use_auth';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api/lobby-meetings`;

function authHeaders() {
  const token = useAuth.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface LobbyMeeting {
  id: string;
  meeting_date: string | null;
  host_name: string | null;
  host_role: string | null;
  host_dg: string | null;
  host_dg_name: string | null;
  host_cabinet: string | null;
  subject: string;
  organisation_met: string;
  transparency_register_id: string | null;
  transparency_register_url: string | null;
  representatives: string | null;
  location: string | null;
  source_url: string;
  org_website?: string | null;
  org_register_url?: string | null;
  org_category?: string | null;
  org_country?: string | null;
  org_fte?: number | null;
  org_ep_passes?: number | null;
}

export interface MepMeeting {
  id: string;
  meeting_date: string | null;
  mep_id: string | null;
  mep_name: string | null;
  role: string | null;
  committee: string | null;
  procedure_ref: string | null;
  procedure_url: string | null;
  organisation: string;
  org_website: string | null;
  org_register_url: string | null;
  transparency_register_id: string | null;
  source: string;
  source_url: string | null;
}

export interface ParliamentResult {
  total: number;
  pi_active: boolean;
  distinct_meps: number;
  distinct_organisations: number;
  top_organisations: { organisation: string; count: number }[];
  items: MepMeeting[];
}

export interface ComparisonResult {
  pi_active: boolean;
  counts: {
    both: number; commission_only: number; parliament_only: number;
    commission_total: number; parliament_total: number;
  };
  both: { organisation: string; commission: number; parliament: number; total: number }[];
  commission_only: { organisation: string; commission: number }[];
  parliament_only: { organisation: string; parliament: number }[];
}

export interface SpendLeader {
  organisation: string; costs_min: number | null; costs_max: number | null; fte: number | null;
  category: string | null; website: string | null; register_url: string | null; tr_id: string | null;
  commission: number; parliament: number;
}
export interface FootprintResult {
  pi_active: boolean;
  total_organisations: number;
  spend_leaders: SpendLeader[];
  category_mix: { type: string; count: number }[];
  access_depth: { level: string; label: string; direct: number; staff: number }[];
  deepest_access: { organisation: string; reached_rapporteur: boolean; parliament: number; commission: number; website: string | null; tr_id: string | null }[];
}
export interface OrgFootprint {
  organisation: string;
  identity: {
    tr_id: string | null; website: string | null; register_url: string | null;
    category: string | null; balance_type: string; country: string | null; fte: number | null;
    costs_min: number | null; costs_max: number | null;
  };
  commission_count: number; parliament_count: number;
  reached_rapporteur: boolean; best_access_label: string | null;
  dgs_met: { code: string; name: string | null }[];
  meps_met: { name: string; role: string | null }[];
  dossiers: string[];
  timeline: { month: string; count: number }[];
  commission_meetings: { meeting_date: string | null; host_dg: string | null; host_name: string | null; subject: string | null }[];
  parliament_meetings: { meeting_date: string | null; mep_name: string | null; role: string | null; committee: string | null; procedure_ref: string | null; procedure_url: string | null }[];
}

export interface LobbyStats {
  pi_active: boolean;
  total: number;
  distinct_organisations: number;
  distinct_dgs: number;
  recent_90d: number;
  top_organisations: { organisation: string; count: number }[];
  top_dgs: { dg: string; dg_name: string | null; count: number }[];
  monthly: { month: string; count: number }[];
}

interface Params { myInterests: boolean; dg?: string; search?: string; }

function qs(p: Params, extra?: Record<string, string | number>) {
  const u = new URLSearchParams();
  u.append('my_interests', String(p.myInterests));
  if (p.dg) u.append('dg', p.dg);
  if (p.search) u.append('search', p.search);
  for (const [k, v] of Object.entries(extra || {})) u.append(k, String(v));
  return u.toString();
}

export const lobbyMeetingsService = {
  list: async (p: Params, limit = 60, offset = 0): Promise<{ total: number; pi_active: boolean; items: LobbyMeeting[] }> => {
    const r = await axios.get(`${API_BASE}?${qs(p, { limit, offset })}`, { headers: authHeaders() });
    return r.data;
  },
  stats: async (p: Params): Promise<LobbyStats> => {
    const r = await axios.get(`${API_BASE}/stats?${qs(p)}`, { headers: authHeaders() });
    return r.data;
  },
  parliament: async (p: Params, limit = 80, offset = 0): Promise<ParliamentResult> => {
    const u = new URLSearchParams();
    u.append('my_interests', String(p.myInterests));
    if (p.search) u.append('search', p.search);
    u.append('limit', String(limit)); u.append('offset', String(offset));
    const r = await axios.get(`${API_BASE}/parliament?${u.toString()}`, { headers: authHeaders() });
    return r.data;
  },
  comparison: async (myInterests: boolean): Promise<ComparisonResult> => {
    const r = await axios.get(`${API_BASE}/comparison?my_interests=${myInterests}`, { headers: authHeaders() });
    return r.data;
  },
  footprint: async (myInterests: boolean): Promise<FootprintResult> => {
    const r = await axios.get(`${API_BASE}/footprint?my_interests=${myInterests}`, { headers: authHeaders() });
    return r.data;
  },
  orgFootprint: async (name?: string, trId?: string | null): Promise<OrgFootprint> => {
    const u = new URLSearchParams();
    if (name) u.append('name', name);
    if (trId) u.append('tr_id', trId);
    const r = await axios.get(`${API_BASE}/org?${u.toString()}`, { headers: authHeaders() });
    return r.data;
  },
};
