/** MEP Watch service (MEUB Section 3). /api/mep-watch: MEPs ranked by activity on your interests + per-MEP questions. */
import axios from 'axios';
import { useAuth } from '../hooks/use_auth';
const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api/mep-watch`;
function authHeaders() { const t = useAuth.getState().token; return t ? { Authorization: `Bearer ${t}` } : {}; }
export interface MepSocialPost { platform: string; posted_at: string | null; text: string; url: string; }
export interface MepRow { name: string; mep_id: string | null; profile_url: string | null; question_count: number; latest_date: string | null; sample_subjects: string[]; latest_social?: MepSocialPost[]; }
export interface MepQuestion { reference: string; type: string; subject: string; submitted_date: string | null; answered: boolean; source_url: string; }
export const mepWatchService = {
  list: async (myInterests: boolean, search?: string): Promise<{ pi_active: boolean; total_meps: number; items: MepRow[] }> => {
    const p = new URLSearchParams({ my_interests: String(myInterests) }); if (search) p.append('search', search);
    return (await axios.get(`${API_BASE}?${p}`, { headers: authHeaders() })).data;
  },
  questions: async (mep: string, myInterests: boolean): Promise<{ mep: string; mep_id: string | null; profile_url: string | null; total: number; questions: MepQuestion[] }> =>
    (await axios.get(`${API_BASE}/questions?mep=${encodeURIComponent(mep)}&my_interests=${myInterests}`, { headers: authHeaders() })).data,
};
