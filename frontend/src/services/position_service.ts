// frontend/src/services/position_service.ts
import axios from 'axios';
import { useAuth } from '../hooks/use_auth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const authHeaders = () => {
  const token = useAuth.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export interface GroupPosition {
  group_code: string;
  stance: string;
  confidence: string;
  cohesion: number;
  rationale: string;
  amendment_count: number;
  top_amendments: Array<Record<string, any>>;
}

export interface MemberStatePosition {
  country_code: string;
  country_name: string;
  stance: string;
  confidence: string;
  rationale: string;
  signal_count: number;
}

export interface CommissionBlock {
  title?: string;
  description?: string;
  com_references?: string[];
  celex_numbers?: string[];
  text_type?: string;
  proposal_date?: string | null;
  documents?: Array<Record<string, any>>;
  lead_dg?: string | null;
}

export interface ParliamentBlock {
  lead_committee?: string;
  opinion_committees?: string[];
  rapporteur?: string;
  rapporteur_group?: string;
  groups: GroupPosition[];
  amendment_activity: {
    total: number;
    by_group: Record<string, number>;
    by_mep_top: Array<{ mep: string; group: string; count: number }>;
  };
  plenary_adopted?: { adopted: boolean; date?: string; reference?: string };
}

export interface CouncilBlock {
  member_states: MemberStatePosition[];
  summary: {
    supporting_count?: number;
    opposing_count?: number;
    undecided_count?: number;
    supporting?: string[];
    opposing?: string[];
  };
  oeil_events?: Array<Record<string, any>>;
  general_approach_adopted?: boolean;
}

export interface UserPosition {
  stance: string;
  notes?: string;
  evidence_urls?: string[];
  priority_articles?: string[];
  last_updated?: string;
}

export interface PositionResponse {
  carriage_id: string;
  procedure_ref: string;
  title?: string;
  data_completeness: string;
  confidence: string;
  commission_position: CommissionBlock;
  parliament_position: ParliamentBlock;
  council_position: CouncilBlock;
  sources: Record<string, any>;
  user_position?: UserPosition | null;
  is_tracked: boolean;
  generated_at?: string;
}

export interface AmendmentArticle {
  article: string;
  by_group: Record<string, number>;
  attributed_total: number;
  unattributed: number;
  total: number;
}
export interface AmendmentDrilldown {
  carriage_id: string;
  procedure_ref: string;
  articles: AmendmentArticle[];
}

export interface PositionListItem {
  carriage_id: string;
  procedure_ref?: string;
  title?: string;
  lead_committee?: string;
  current_status?: string;
  is_tracked: boolean;
  is_recently_updated: boolean;
  is_pi_match: boolean;
  user_stance?: string | null;
  has_snapshot: boolean;
}

export interface PositionListResponse {
  pi_active: boolean;
  tracked: PositionListItem[];
  suggested: PositionListItem[];
}

export interface LobbyingOrg {
  organisation: string;
  website: string | null;
  register_url: string | null;
  transparency_register_id: string | null;
  meetings: number;
  reached_rapporteur: boolean;
  best_access: number;
  best_label: string | null;
  meps: string[];
  first_meeting: string | null;
  last_meeting: string | null;
}
export interface LobbyingOutcome {
  status: string | null;
  has_vote: boolean;
  result: string | null;
  vote_date: string | null;
  vote_level: string | null;
}
export interface LobbyingResult {
  procedure_ref: string | null;
  total: number;
  organisations: LobbyingOrg[];
  outcome?: LobbyingOutcome;
}

export interface ActualVote {
  has_vote: boolean;
  level?: string;
  result?: string;
  votes_for?: number;
  votes_against?: number;
  votes_abstention?: number;
  group_breakdown?: Record<string, any>;
  vote_date?: string | null;
  ta_reference?: string | null;
  title?: string;
  source_url?: string | null;
  committee_code?: string | null;
}

export interface OrgPosition {
  stance: string;
  summary: string | null;
  excerpt: string | null;
  consultation_title: string | null;
  dg: string | null;
  source_url: string | null;
  date: string | null;
}
export interface AlignmentOrg {
  organisation: string;
  transparency_register_id: string | null;
  meetings: number;
  reached_rapporteur: boolean;
  has_position: boolean;
  positions: OrgPosition[];
}
export interface AlignmentResult {
  procedure_ref: string | null;
  outcome?: LobbyingOutcome;
  coverage: { lobbying_orgs: number; with_position: number };
  organisations: AlignmentOrg[];
}

export const positionService = {
  async list(myInterests = true, limit = 40): Promise<PositionListResponse> {
    const { data } = await axios.get<PositionListResponse>(`${API_URL}/api/positions/`, {
      headers: authHeaders(),
      params: { my_interests: myInterests, limit },
    });
    return data;
  },

  async lobbying(carriageId: string): Promise<LobbyingResult> {
    const { data } = await axios.get<LobbyingResult>(`${API_URL}/api/positions/${carriageId}/lobbying`, {
      headers: authHeaders(),
    });
    return data;
  },

  async actualVote(carriageId: string): Promise<ActualVote> {
    const { data } = await axios.get<ActualVote>(`${API_URL}/api/positions/${carriageId}/actual-vote`, {
      headers: authHeaders(),
    });
    return data;
  },

  async alignment(carriageId: string): Promise<AlignmentResult> {
    const { data } = await axios.get<AlignmentResult>(`${API_URL}/api/positions/${carriageId}/alignment`, {
      headers: authHeaders(),
    });
    return data;
  },

  async get(carriageId: string, refresh = false): Promise<PositionResponse> {
    const { data } = await axios.get<PositionResponse>(`${API_URL}/api/positions/${carriageId}`, {
      headers: authHeaders(),
      params: refresh ? { refresh: true } : {},
    });
    return data;
  },

  async amendments(carriageId: string): Promise<AmendmentDrilldown> {
    const { data } = await axios.get<AmendmentDrilldown>(`${API_URL}/api/positions/${carriageId}/amendments`, {
      headers: authHeaders(),
    });
    return data;
  },

  async saveUserPosition(carriageId: string, payload: UserPosition): Promise<PositionResponse> {
    const { data } = await axios.patch<PositionResponse>(
      `${API_URL}/api/positions/${carriageId}/user-position`,
      payload,
      { headers: authHeaders() },
    );
    return data;
  },

  async refresh(carriageId: string): Promise<PositionResponse> {
    const { data } = await axios.post<PositionResponse>(
      `${API_URL}/api/positions/${carriageId}/refresh`,
      {},
      { headers: authHeaders() },
    );
    return data;
  },
};
