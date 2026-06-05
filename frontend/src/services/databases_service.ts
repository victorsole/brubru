/**
 * Brubru Databases service (MEUB Section 4.2). Wraps /api/databases:
 * knowledge-library stats + the Policy Areas Explorer ("who does what").
 */
import axios from 'axios';
import { useAuth } from '../hooks/use_auth';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api/databases`;

function authHeaders() {
  const token = useAuth.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface LibraryItem {
  slug?: string;
  title: string;
  url: string | null;
  languages?: string[];
  celex?: string | null;
  name?: string;
}
export interface LibraryStats {
  canon: { count: number; url: string; items: LibraryItem[] };
  deep_dive: { count: number; url: string; items: LibraryItem[] };
  guides: { count: number; url: string };
  catalan: { count: number; url: string | null; items: LibraryItem[] };
}

export interface CanonItem {
  slug?: string;
  title: string;
  celex?: string | null;
  doc_type?: string | null;
  year?: string | null;
  family_label?: string | null;
  languages: string[];
  url: string | null;
  lang_urls?: Record<string, string>;
  chips: string[];
  articles?: number | null;
  titles?: number | null;
}
export interface CanonResult {
  count: number;
  site_url: string;
  languages: number;
  items: CanonItem[];
}

export interface GuideCategory { title: string; count: number; color: string; icon: string }
export interface GuidesResult {
  count: number;
  file_count: number;
  categories: GuideCategory[];
  url: string;
}

export interface CatalanItem { name: string; title: string; url: string }
export interface CatalanResult { count: number; url: string; items: CatalanItem[] }

export interface BeresolMonitor { monitor: string; title: string; description: string; public_url: string }
export interface BeresolMonitorsResult {
  available: boolean;
  reason?: string;
  name?: string;
  description?: string;
  created_date?: string;
  count?: number;
  source_url?: string;
  monitors: BeresolMonitor[];
}
export interface BeresolMonitorDetail {
  available: boolean;
  reason?: string;
  monitor?: string;
  title?: string;
  public_url?: string;
  created_date?: string;
  body_html?: string;
  body_txt?: string;
}

export interface ResearchSource {
  id: string;
  group: 'foresight' | 'research';
  icon: string;
  color: string;
  name: string;
  full: string;
  landing: string;
  search: string;
  has_feed: boolean;
  is_pi_match: boolean;
}
export interface ResearchCatalogue { pi_active: boolean; count: number; sources: ResearchSource[] }
export interface ResearchFeedItem { title: string; url: string; date?: string; snippet?: string }
export interface ResearchSummary {
  available: boolean;
  reason?: string;
  summary?: string;
  model?: string;
  kind?: string;
  cached?: boolean;
  url?: string;
}

export interface PolicyBody { code: string; name: string }
export interface PolicyArea {
  name: string;
  is_pi_match: boolean;
  committees: PolicyBody[];
  dgs: PolicyBody[];
  council_configs: PolicyBody[];
  policy_tags: string[];
  body_count: number;
}
export interface PolicyAreasResult {
  pi_active: boolean;
  areas: PolicyArea[];
}

export const databasesService = {
  libraryStats: async (): Promise<LibraryStats> => {
    const r = await axios.get(`${API_BASE}/library-stats`, { headers: authHeaders() });
    return r.data;
  },
  policyAreas: async (myInterests: boolean): Promise<PolicyAreasResult> => {
    const r = await axios.get(`${API_BASE}/policy-areas?my_interests=${myInterests}`, { headers: authHeaders() });
    return r.data;
  },
  canon: async (): Promise<CanonResult> => {
    const r = await axios.get(`${API_BASE}/canon`, { headers: authHeaders() });
    return r.data;
  },
  guides: async (): Promise<GuidesResult> => {
    const r = await axios.get(`${API_BASE}/guides`, { headers: authHeaders() });
    return r.data;
  },
  catalan: async (): Promise<CatalanResult> => {
    const r = await axios.get(`${API_BASE}/catalan`, { headers: authHeaders() });
    return r.data;
  },
  beresolMonitors: async (): Promise<BeresolMonitorsResult> => {
    const r = await axios.get(`${API_BASE}/beresol-monitors`, { headers: authHeaders() });
    return r.data;
  },
  beresolMonitor: async (slug: string): Promise<BeresolMonitorDetail> => {
    const r = await axios.get(`${API_BASE}/beresol-monitors/${slug}`, { headers: authHeaders() });
    return r.data;
  },
  researchSources: async (myInterests: boolean): Promise<ResearchCatalogue> => {
    const r = await axios.get(`${API_BASE}/research-sources?my_interests=${myInterests}`, { headers: authHeaders() });
    return r.data;
  },
  researchFeed: async (sourceId: string): Promise<ResearchFeedItem[]> => {
    const r = await axios.get(`${API_BASE}/research-feed/${sourceId}`, { headers: authHeaders() });
    return r.data.items || [];
  },
  researchSummary: async (url: string): Promise<ResearchSummary> => {
    const r = await axios.post(`${API_BASE}/research-summary`, { url }, { headers: authHeaders() });
    return r.data;
  },
};
