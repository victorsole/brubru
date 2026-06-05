/**
 * Parliamentary Questions service (MEUB Section 3). Wraps
 * /api/parliamentary-questions: PI-filtered list, new-count warn badge, detail,
 * and the AI "why this matters" explainer.
 */
import axios from 'axios';
import { useAuth } from '../hooks/use_auth';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api/parliamentary-questions`;

function authHeaders() {
  const token = useAuth.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface QuestionMep {
  id: string | null;
  name: string | null;
  profile_url: string | null;
}

export interface QuestionSummary {
  reference: string;
  type: string;                 // written | oral | priority | question_time
  subject: string;
  submitted_date: string | null;
  answered_date: string | null;
  meps: QuestionMep[];
  answering_institution: string | null;
  answering_commissioner: string | null;
  related_celex: string[];
  procedure_ref: string | null;
  matches_tracked?: boolean;
  source_url: string | null;
  answer_url: string | null;
  answered: boolean;
}

export interface QuestionDetail extends QuestionSummary {
  text_question: string | null;
  text_answer: string | null;
  parliamentary_term: number;
  committees: string[];
  ai_explainer: string | null;
}

export const parliamentaryQuestionsService = {
  list: async (params: {
    myInterests: boolean; myFiles?: boolean; questionType?: string; answered?: boolean;
    search?: string; limit?: number; offset?: number;
  }): Promise<{ total: number; pi_active: boolean; files_active?: boolean; has_tracked_files?: boolean; items: QuestionSummary[] }> => {
    const p = new URLSearchParams();
    p.append('my_interests', String(params.myInterests));
    if (params.myFiles) p.append('my_files', 'true');
    if (params.questionType) p.append('question_type', params.questionType);
    if (params.answered !== undefined) p.append('answered', String(params.answered));
    if (params.search) p.append('search', params.search);
    p.append('limit', String(params.limit ?? 60));
    p.append('offset', String(params.offset ?? 0));
    const r = await axios.get(`${API_BASE}?${p.toString()}`, { headers: authHeaders() });
    return r.data;
  },

  newCount: async (days = 7): Promise<{ count: number; days: number; pi_active: boolean }> => {
    const r = await axios.get(`${API_BASE}/new-count?days=${days}`, { headers: authHeaders() });
    return r.data;
  },

  get: async (reference: string): Promise<QuestionDetail> => {
    const r = await axios.get(`${API_BASE}/${encodeURIComponent(reference)}`, { headers: authHeaders() });
    return r.data;
  },

  explain: async (reference: string): Promise<{ reference: string; explainer: string; cached: boolean }> => {
    const r = await axios.post(`${API_BASE}/${encodeURIComponent(reference)}/explain`, {}, { headers: authHeaders() });
    return r.data;
  },
};
