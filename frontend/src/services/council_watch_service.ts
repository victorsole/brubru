/** Council Watch service (MEUB Section 3). /api/council-watch: unified meetings+outcomes feed + stats. */
import axios from 'axios';
import { useAuth } from '../hooks/use_auth';
const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api/council-watch`;
function authHeaders() { const t = useAuth.getState().token; return t ? { Authorization: `Bearer ${t}` } : {}; }
export interface CouncilItem { kind: 'meeting' | 'outcome'; date: string | null; title: string; configuration: string | null; summary: string | null; url: string | null; image_url?: string | null; institution?: string; }
export interface PermRep { code: string; name: string; region?: boolean; home: string; about?: string; who?: string; news?: string; }
export interface CouncilStats { pi_active: boolean; upcoming_meetings: number; total_meetings: number; recent_outcomes: number; your_configurations: string[]; council_votes: number; }
export const councilWatchService = {
  list: async (myInterests: boolean, kind = 'all', search?: string): Promise<{ total: number; pi_active: boolean; items: CouncilItem[] }> => {
    const p = new URLSearchParams({ my_interests: String(myInterests), kind }); if (search) p.append('search', search);
    return (await axios.get(`${API_BASE}?${p}`, { headers: authHeaders() })).data;
  },
  stats: async (myInterests: boolean): Promise<CouncilStats> =>
    (await axios.get(`${API_BASE}/stats?my_interests=${myInterests}`, { headers: authHeaders() })).data,
  permreps: async (): Promise<{ items: PermRep[]; total: number }> =>
    (await axios.get(`${API_BASE}/permreps`, { headers: authHeaders() })).data,
  summarise: async (item: CouncilItem, lang: string): Promise<{ summary: string; lang: string; cached: boolean }> =>
    (await axios.post(`${API_BASE}/summarise`,
      { title: item.title, summary: item.summary, kind: item.kind, configuration: item.configuration, lang },
      { headers: authHeaders() })).data,
};
