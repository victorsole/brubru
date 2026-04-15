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

export interface AmendmentDrilldown {
  carriage_id: string;
  procedure_ref: string;
  articles: Array<{ article: string; by_group: Record<string, number>; total: number }>;
}

export interface TrackedPositionListItem {
  carriage_id: string;
  procedure_ref: string;
  title?: string;
  confidence: string;
  data_completeness: string;
  parliament_summary: {
    groups: number;
    amendments: number;
    rapporteur?: string;
    rapporteur_group?: string;
  };
  council_summary: {
    supporting_count?: number;
    opposing_count?: number;
    undecided_count?: number;
  };
  user_stance?: string | null;
  generated_at?: string;
}

export const positionService = {
  async list(limit = 50): Promise<TrackedPositionListItem[]> {
    const { data } = await axios.get<TrackedPositionListItem[]>(`${API_URL}/api/positions/`, {
      headers: authHeaders(),
      params: { limit },
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
