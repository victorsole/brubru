/**
 * Transcripts service (MEUB Section 3). Wraps /api/transcripts:
 * catalog of completed transcripts, PI suggestions, on-demand transcription
 * (Blue tier), job polling, and save-to-My-Files.
 */
import axios from 'axios';
import { useAuth } from '../hooks/use_auth';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api/transcripts`;

function authHeaders() {
  const token = useAuth.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface TranscriptSummary {
  id: string;
  institution: string;
  committee_code: string;
  meeting_date: string | null;
  title: string;
  language: string;
  word_count: number;
  duration_minutes: number;
  procedure_refs: string[];
  status: string;
  has_recording: boolean;
  has_agenda?: boolean;
}

export interface AgendaItem {
  number: number;
  title: string;
  procedure_ref?: string | null;
  procedure_type?: string | null;
  dossier_ref?: string | null;
  rapporteur?: string | null;
  responsible?: string[];
  actions?: string[];
  doc_refs?: string[];
  start_time?: number | null;   // seconds into the recording
  end_time?: number | null;
  agenda_source_url?: string | null;
}

export interface TranscriptSegment { s: number; t: string; }

export interface TranscriptDetail extends TranscriptSummary {
  transcript_text: string | null;
  agenda_items: AgendaItem[];
  segments: TranscriptSegment[] | null;
  video_url: string | null;
  speakers: any[];
  multimedia_url: string | null;
  engine: string | null;
  error_message: string | null;
  summary_langs: string[];
}

export interface SummaryResult {
  id: string;
  lang: string;
  available_langs: string[];
  summary: string | null;
  model: string | null;
  generated_at: string | null;
  can_generate: boolean;
}

export const transcriptsService = {
  facets: async (): Promise<{ institutions: string[]; bodies: Record<string, string[]> }> => {
    const r = await axios.get(`${API_BASE}/facets`, { headers: authHeaders() });
    return r.data;
  },

  list: async (myInterests: boolean, search?: string, institution?: string, body?: string): Promise<{ total: number; items: TranscriptSummary[] }> => {
    const p = new URLSearchParams();
    if (myInterests) p.append('my_interests', 'true');
    if (institution) p.append('institution', institution);
    if (body) p.append('body', body);
    if (search) p.append('search', search);
    const r = await axios.get(`${API_BASE}?${p.toString()}`, { headers: authHeaders() });
    return r.data;
  },

  suggestions: async (myInterests: boolean, institution?: string, body?: string): Promise<{ items: TranscriptSummary[]; can_transcribe: boolean }> => {
    const p = new URLSearchParams({ my_interests: String(myInterests) });
    if (institution) p.append('institution', institution);
    if (body) p.append('body', body);
    const r = await axios.get(`${API_BASE}/suggestions?${p.toString()}`, { headers: authHeaders() });
    return r.data;
  },

  get: async (id: string): Promise<TranscriptDetail> => {
    const r = await axios.get(`${API_BASE}/${id}`, { headers: authHeaders() });
    return r.data;
  },

  transcribe: async (id: string): Promise<{ id: string; status: string; message: string }> => {
    const r = await axios.post(`${API_BASE}/${id}/transcribe`, {}, { headers: authHeaders() });
    return r.data;
  },

  status: async (id: string): Promise<{ id: string; status: string; stage: string | null; progress: number | null; word_count: number; error_message: string | null }> => {
    const r = await axios.get(`${API_BASE}/${id}/status`, { headers: authHeaders() });
    return r.data;
  },

  saveToFiles: async (id: string): Promise<{ document_id: string; title: string }> => {
    const r = await axios.post(`${API_BASE}/${id}/save-to-files`, {}, { headers: authHeaders() });
    return r.data;
  },

  attachAgenda: async (id: string): Promise<{ id: string; agenda_items: AgendaItem[]; cached: boolean }> => {
    const r = await axios.post(`${API_BASE}/${id}/agenda`, {}, { headers: authHeaders() });
    return r.data;
  },

  getSummary: async (id: string, lang: string): Promise<SummaryResult> => {
    const r = await axios.get(`${API_BASE}/${id}/summary?lang=${encodeURIComponent(lang)}`, { headers: authHeaders() });
    return r.data;
  },

  generateSummary: async (id: string, lang: string): Promise<SummaryResult> => {
    const r = await axios.post(`${API_BASE}/${id}/summary?lang=${encodeURIComponent(lang)}`, {}, { headers: authHeaders() });
    return r.data;
  },
};
