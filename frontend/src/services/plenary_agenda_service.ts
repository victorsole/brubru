/** EP Plenary Order of Business service (MEUB Section 3). /api/plenary-agenda. */
import axios from 'axios';
import { useAuth } from '../hooks/use_auth';
const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api/plenary-agenda`;
function authHeaders() { const t = useAuth.getState().token; return t ? { Authorization: `Bearer ${t}` } : {}; }
export interface PlenarySession { date: string | null; end_date: string | null; title: string; agenda_url: string | null; }
export interface PlenaryBusiness { ta_reference: string | null; title: string; procedure_ref: string | null; committees: string[]; adoption_date: string | null; document_url: string | null; oeil_url: string | null; }
export interface PlenaryOoB { pi_active: boolean; sessions: PlenarySession[]; business: PlenaryBusiness[]; business_total: number; plenary_votes: number; }
export const plenaryAgendaService = {
  get: async (myInterests: boolean, search?: string): Promise<PlenaryOoB> => {
    const p = new URLSearchParams({ my_interests: String(myInterests) }); if (search) p.append('search', search);
    return (await axios.get(`${API_BASE}?${p}`, { headers: authHeaders() })).data;
  },
};
