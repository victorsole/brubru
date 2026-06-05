/**
 * Prediction Service
 *
 * API client for legislative predictions.
 * Follows the mockup design in docs/mockups/predictions-tab.html
 *
 * Created: February 2026
 */

import axios from 'axios';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api/predictions`;

// ============================================================================
// Types
// ============================================================================

export type OutcomeType = 'adopted' | 'blocked' | 'withdrawn' | 'uncertain';
export type StagnationLevel = 'normal' | 'warning' | 'alert' | 'critical';
export type GroupPosition = 'FOR' | 'AGAINST' | 'ABSTENTION' | 'SPLIT';
export type CouncilRiskLevel = 'low' | 'medium' | 'high' | 'critical';

export interface OutcomeProbability {
  outcome: string;
  probability: number;
  description: string;
}

export interface TimelinePrediction {
  procedure_ref: string;
  current_status: string;
  days_in_status: number;
  predicted_days_remaining: number;
  confidence: number;
  lower_bound_25?: number;
  upper_bound_75?: number;
  model_version: string;
  prediction_method: string;
  similar_procedures: Array<{
    ref: string;
    title: string;
    days: number;
  }>;
}

export interface OutcomePrediction {
  procedure_ref: string;
  current_status: string;
  predicted_outcome: OutcomeType;
  confidence: number;
  probabilities: OutcomeProbability[];
  model_version: string;
  top_factors: Array<{
    factor: string;
    importance: number;
    direction: string;
  }>;
}

export interface GroupPositionPrediction {
  group_code: string;
  group_name: string;
  predicted_position: GroupPosition;
  confidence: number;
  expected_cohesion: number;
  prob_for: number;
  prob_against: number;
  prob_abstention: number;
  factors: Array<{
    factor: string;
    effect: string;
  }>;
}

export interface PlenaryVotePrediction {
  procedure_ref: string;
  title?: string;
  predicted_outcome: 'PASS' | 'FAIL' | 'UNCERTAIN';
  confidence: number;
  predicted_margin: number;
  estimated_for: number;
  estimated_against: number;
  estimated_abstention: number;
  total_meps: number;
  group_predictions: GroupPositionPrediction[];
  swing_groups: string[];
}

export interface StagnationAlert {
  procedure_ref: string;
  title: string;
  current_status: string;
  days_in_status: number;
  stagnation_level: StagnationLevel;
  last_update?: string;
}

export interface DelegationDeviation {
  country_code: string;
  country_name: string;
  group_code: string;
  deviation_risk: 'low' | 'moderate' | 'high';
  deviation_probability: number;
  likely_direction: string;
  national_interest_factor: number;
  governing_status: string;
  reasons: string[];
}

export interface CohesionAnalysis {
  entity_type: string;
  entity_code: string;
  cohesion_score: number;
  cohesion_level: string;
  votes_analyzed: number;
  majority_position: string;
  position_breakdown: Record<string, number>;
}

export interface ModelInfo {
  timeline_model: {
    loaded: boolean;
    version?: string;
    feature_count?: number;
    feature_importance?: Record<string, number>;
  };
  outcome_model: {
    loaded: boolean;
    version?: string;
    feature_count?: number;
    class_distribution?: Record<string, number>;
  };
}

// ============================================================================
// Phase 4 Types: QMV, Committee, Council
// ============================================================================

export type QMVOutcome = 'PASS' | 'FAIL' | 'INSUFFICIENT_DATA';
export type BlockingRiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';
export type CommitteeVoteOutcome = 'APPROVE' | 'REJECT' | 'AMEND_HEAVILY' | 'SPLIT';
export type MemberStatePosition = 'SUPPORT' | 'OPPOSE' | 'UNDECIDED' | 'ABSTAIN';

export interface QMVResult {
  outcome: QMVOutcome;
  states_for: number;
  states_against: number;
  states_abstain: number;
  states_undecided: number;
  states_for_pct: number;
  population_for_pct: number;
  meets_state_threshold: boolean;
  meets_population_threshold: boolean;
  blocking_minority_possible: boolean;
  margin_states: number;
  margin_population_pct: number;
}

export interface BlockingCoalition {
  has_blocking_minority: boolean;
  risk_level: BlockingRiskLevel;
  current_blocking_states: string[];
  current_blocking_population_pct: number;
  potential_coalitions: Array<{
    states: string[];
    population_pct: number;
    probability: number;
  }>;
  swing_states: string[];
}

export interface CommitteeVotePrediction {
  committee_code: string;
  committee_name: string;
  procedure_ref: string;
  predicted_outcome: CommitteeVoteOutcome;
  confidence: number;
  expected_margin: number;
  estimated_for: number;
  estimated_against: number;
  estimated_abstain: number;
  rapporteur_group?: string;
  shadow_positions: Record<string, string>;
  amendment_risk: 'low' | 'moderate' | 'high';
  key_groups_to_watch: string[];
}

export interface CommitteeInfo {
  code: string;
  name: string;
  full_members: number;
  substitutes: number;
  total: number;
  group_distribution: Record<string, number>;
  pro_eu_balance: number;
  eurosceptic_balance: number;
}

export interface MemberStatePositionInfo {
  country_code: string;
  country_name: string;
  position: MemberStatePosition;
  confidence: number;
  key_concerns: string[];
  red_lines: string[];
  european_family_positions: Record<string, string>;
}

export interface CouncilVotePrediction {
  procedure_ref: string;
  title?: string;
  predicted_outcome: 'PASS' | 'FAIL' | 'UNCERTAIN';
  confidence: number;
  qmv_result: QMVResult;
  state_positions: MemberStatePositionInfo[];
  blocking_risk: BlockingCoalition;
  key_concerns: string[];
  compromise_areas: string[];
}

// ============================================================================
// Resolution Leading Indicator Types
// ============================================================================

export type ResolutionType = 'INL' | 'INI' | 'RSP' | 'OTHER';
export type MatchMethod = 'OEIL_CROSSREF' | 'COMMISSION_FOLLOWUP' | 'TITLE_SIMILARITY' | 'EUROVOC_MATCH' | 'MANUAL';
export type ResolutionSentiment = 'STRONG_SUPPORT' | 'MODERATE_SUPPORT' | 'MIXED' | 'LOW_SUPPORT' | 'NO_DATA';

export interface ResolutionIndicator {
  resolution_id: string;
  procedure_ref: string;
  title: string;
  resolution_type: ResolutionType;
  adoption_date?: string;
  vote_for: number;
  vote_against: number;
  vote_abstention: number;
  vote_total: number;
  support_percentage: number;
  lead_committee?: string;
  rapporteur?: string;
  match_method: MatchMethod;
  match_confidence: number;
  days_before_legislation?: number;
  oeil_url?: string;
}

export interface ResolutionLeadingIndicatorSummary {
  total_resolutions: number;
  by_type: Record<ResolutionType, number>;
  by_method: Record<MatchMethod, number>;
  average_support: number;
  weighted_sentiment: ResolutionSentiment;
}

export interface ResolutionLeadingIndicatorResponse {
  procedure_ref: string;
  title?: string;
  resolutions: ResolutionIndicator[];
  summary: ResolutionLeadingIndicatorSummary;
}

// ============================================================================
// Composite Types (for the UI)
// ============================================================================

export interface PredictionSummary {
  id: string;
  procedure_ref: string;
  title: string;
  overall_confidence: number;
  timeline?: TimelinePrediction;
  outcome?: OutcomePrediction;
  ep_vote?: PlenaryVotePrediction;
  council_risk?: CouncilRiskLevel;
  predicted_at: string;
  // UI state
  is_expanded?: boolean;
}

export interface PredictionQuota {
  used: number;
  total: number;
  reset_date: string;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get timeline prediction for a procedure
 */
export async function getTimelinePrediction(
  procedureRef: string,
  useML: boolean = true
): Promise<TimelinePrediction> {
  const response = await axios.post<TimelinePrediction>(
    `${API_BASE}/timeline/${encodeURIComponent(procedureRef)}`,
    null,
    { params: { use_ml: useML } }
  );
  return response.data;
}

/**
 * Get outcome prediction for a procedure
 */
export async function getOutcomePrediction(
  procedureRef: string
): Promise<OutcomePrediction> {
  const response = await axios.post<OutcomePrediction>(
    `${API_BASE}/outcome/${encodeURIComponent(procedureRef)}`
  );
  return response.data;
}

/**
 * Get EP plenary vote prediction
 */
export async function getEPVotePrediction(
  procedureRef: string,
  leadCommittee?: string,
  rapporteurGroup?: string
): Promise<PlenaryVotePrediction> {
  const response = await axios.post<PlenaryVotePrediction>(
    `${API_BASE}/vote/ep/${encodeURIComponent(procedureRef)}`,
    null,
    {
      params: {
        lead_committee: leadCommittee,
        rapporteur_group: rapporteurGroup,
      },
    }
  );
  return response.data;
}

/**
 * Get single group position prediction
 */
export async function getGroupPositionPrediction(
  groupCode: string,
  procedureRef: string,
  leadCommittee?: string,
  rapporteurGroup?: string
): Promise<GroupPositionPrediction> {
  const response = await axios.get<GroupPositionPrediction>(
    `${API_BASE}/vote/group/${encodeURIComponent(groupCode)}`,
    {
      params: {
        procedure_ref: procedureRef,
        lead_committee: leadCommittee,
        rapporteur_group: rapporteurGroup,
      },
    }
  );
  return response.data;
}

/**
 * Get group cohesion analysis
 */
export async function getGroupCohesion(
  groupCode: string
): Promise<CohesionAnalysis> {
  const response = await axios.get<CohesionAnalysis>(
    `${API_BASE}/cohesion/${encodeURIComponent(groupCode)}`
  );
  return response.data;
}

/**
 * Get delegation deviation predictions
 */
export async function getDelegationDeviations(
  groupCode: string,
  procedureRef: string,
  leadCommittee?: string,
  expectedPosition: string = 'FOR'
): Promise<DelegationDeviation[]> {
  const response = await axios.get<DelegationDeviation[]>(
    `${API_BASE}/delegations/${encodeURIComponent(groupCode)}`,
    {
      params: {
        procedure_ref: procedureRef,
        lead_committee: leadCommittee,
        expected_position: expectedPosition,
      },
    }
  );
  return response.data;
}

/**
 * Get stagnation alerts
 */
export async function getStagnationAlerts(
  minLevel: StagnationLevel = 'warning',
  limit: number = 50
): Promise<StagnationAlert[]> {
  const response = await axios.get<StagnationAlert[]>(
    `${API_BASE}/stagnation-alerts`,
    {
      params: { min_level: minLevel, limit },
    }
  );
  return response.data;
}

/**
 * Get model information
 */
export async function getModelInfo(): Promise<ModelInfo> {
  const response = await axios.get<ModelInfo>(`${API_BASE}/model-info`);
  return response.data;
}

// ============================================================================
// Phase 4 API Functions: QMV, Committee, Council
// ============================================================================

/**
 * Calculate QMV outcome
 */
export async function calculateQMV(
  supportingStates: string[],
  opposingStates: string[] = [],
  abstainingStates: string[] = []
): Promise<QMVResult> {
  const response = await axios.post<QMVResult>(
    `${API_BASE}/qmv/calculate`,
    null,
    {
      params: {
        supporting_states: supportingStates,
        opposing_states: opposingStates,
        abstaining_states: abstainingStates,
      },
      paramsSerializer: (params) => {
        const searchParams = new URLSearchParams();
        Object.entries(params).forEach(([key, value]) => {
          if (Array.isArray(value)) {
            value.forEach((v) => searchParams.append(key, v));
          } else if (value !== undefined) {
            searchParams.append(key, String(value));
          }
        });
        return searchParams.toString();
      },
    }
  );
  return response.data;
}

/**
 * Analyze blocking minority risk
 */
export async function analyzeBlockingMinority(
  baseOpposed: string[],
  potentialSwing: string[] = []
): Promise<BlockingCoalition> {
  const response = await axios.post<BlockingCoalition>(
    `${API_BASE}/qmv/blocking-analysis`,
    null,
    {
      params: {
        base_opposed: baseOpposed,
        potential_swing: potentialSwing,
      },
      paramsSerializer: (params) => {
        const searchParams = new URLSearchParams();
        Object.entries(params).forEach(([key, value]) => {
          if (Array.isArray(value)) {
            value.forEach((v) => searchParams.append(key, v));
          } else if (value !== undefined) {
            searchParams.append(key, String(value));
          }
        });
        return searchParams.toString();
      },
    }
  );
  return response.data;
}

/**
 * Predict committee vote outcome
 */
export async function getCommitteeVotePrediction(
  committeeCode: string,
  procedureRef: string,
  rapporteurGroup?: string,
  shadowPositions?: Record<string, string>,
  policyArea?: string
): Promise<CommitteeVotePrediction> {
  const response = await axios.post<CommitteeVotePrediction>(
    `${API_BASE}/committee/${encodeURIComponent(committeeCode)}/vote`,
    null,
    {
      params: {
        procedure_ref: procedureRef,
        rapporteur_group: rapporteurGroup,
        shadow_positions: shadowPositions ? JSON.stringify(shadowPositions) : undefined,
        policy_area: policyArea,
      },
    }
  );
  return response.data;
}

/**
 * Get committee information
 */
export async function getCommitteeInfo(
  committeeCode: string
): Promise<CommitteeInfo> {
  const response = await axios.get<CommitteeInfo>(
    `${API_BASE}/committee/${encodeURIComponent(committeeCode)}/info`
  );
  return response.data;
}

/**
 * Predict Council vote outcome
 */
export async function getCouncilVotePrediction(
  procedureRef: string,
  policyArea?: string
): Promise<CouncilVotePrediction> {
  const response = await axios.post<CouncilVotePrediction>(
    `${API_BASE}/council/vote/${encodeURIComponent(procedureRef)}`,
    null,
    {
      params: { policy_area: policyArea },
    }
  );
  return response.data;
}

/**
 * Get inferred member state position
 */
export async function getMemberStatePosition(
  countryCode: string,
  procedureRef: string,
  policyArea?: string
): Promise<MemberStatePositionInfo> {
  const response = await axios.get<MemberStatePositionInfo>(
    `${API_BASE}/council/position/${encodeURIComponent(countryCode)}`,
    {
      params: {
        procedure_ref: procedureRef,
        policy_area: policyArea,
      },
    }
  );
  return response.data;
}

// ============================================================================
// Resolution Leading Indicator API Functions
// ============================================================================

/**
 * Get resolution leading indicators for a legislative procedure
 *
 * Returns EP resolutions (INL, INI, RSP) that are linked to or related to
 * the given legislative procedure, along with vote statistics.
 *
 * @param procedureRef - OEIL procedure reference (e.g., "2024/0138(COD)")
 * @param title - Procedure title for similarity search
 * @param includeSimilar - Whether to include title-similarity matches
 */
export async function getResolutionLeadingIndicators(
  procedureRef: string,
  title?: string,
  includeSimilar: boolean = true
): Promise<ResolutionLeadingIndicatorResponse> {
  const response = await axios.get<ResolutionLeadingIndicatorResponse>(
    `${API_BASE}/resolutions/${encodeURIComponent(procedureRef)}`,
    {
      params: {
        title,
        include_similar: includeSimilar,
      },
    }
  );
  return response.data;
}

// ============================================================================
// Composite Functions (fetch all predictions for a procedure)
// ============================================================================

/**
 * Get full prediction summary for a procedure
 */
export async function getFullPrediction(
  procedureRef: string,
  title: string,
  leadCommittee?: string,
  rapporteurGroup?: string
): Promise<PredictionSummary> {
  // Fetch all predictions in parallel
  const [timeline, outcome, epVote] = await Promise.all([
    getTimelinePrediction(procedureRef).catch(() => undefined),
    getOutcomePrediction(procedureRef).catch(() => undefined),
    getEPVotePrediction(procedureRef, leadCommittee, rapporteurGroup).catch(
      () => undefined
    ),
  ]);

  // Calculate overall confidence as weighted average
  const confidences: number[] = [];
  if (timeline) confidences.push(timeline.confidence);
  if (outcome) confidences.push(outcome.confidence);
  if (epVote) confidences.push(epVote.confidence);

  const overallConfidence =
    confidences.length > 0
      ? confidences.reduce((a, b) => a + b, 0) / confidences.length
      : 0.5;

  // Estimate council risk (simplified)
  let councilRisk: CouncilRiskLevel = 'medium';
  if (outcome?.confidence && outcome.confidence > 0.75) {
    councilRisk = outcome.predicted_outcome === 'adopted' ? 'low' : 'high';
  }

  return {
    id: `pred-${procedureRef}-${Date.now()}`,
    procedure_ref: procedureRef,
    title,
    overall_confidence: overallConfidence,
    timeline,
    outcome,
    ep_vote: epVote,
    council_risk: councilRisk,
    predicted_at: new Date().toISOString(),
    is_expanded: false,
  };
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Format confidence as percentage string
 */
export function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

/**
 * Get confidence level (for styling)
 */
export function getConfidenceLevel(
  confidence: number
): 'high' | 'medium' | 'low' {
  if (confidence >= 0.7) return 'high';
  if (confidence >= 0.5) return 'medium';
  return 'low';
}

/**
 * Format predicted date from days remaining
 */
export function formatPredictedDate(daysRemaining: number): string {
  const targetDate = new Date();
  targetDate.setDate(targetDate.getDate() + daysRemaining);

  const quarter = Math.ceil((targetDate.getMonth() + 1) / 3);
  return `Q${quarter} ${targetDate.getFullYear()}`;
}

/**
 * Get outcome label for display
 */
export function getOutcomeLabel(outcome: OutcomeType): string {
  const labels: Record<OutcomeType, string> = {
    adopted: 'Adopted',
    blocked: 'Blocked',
    withdrawn: 'Withdrawn',
    uncertain: 'Uncertain',
  };
  return labels[outcome] || outcome;
}

/**
 * Get council risk label for display
 */
export function getCouncilRiskLabel(risk: CouncilRiskLevel): string {
  const labels: Record<CouncilRiskLevel, string> = {
    low: 'Low Risk',
    medium: 'Medium',
    high: 'High Risk',
    critical: 'Critical',
  };
  return labels[risk] || risk;
}

/**
 * Calculate stroke offset for circular gauge (283 = full circumference)
 */
export function calculateGaugeOffset(confidence: number): number {
  return 283 - 283 * confidence;
}

/**
 * Get group position bar class
 */
export function getPositionBarClass(position: GroupPosition): string {
  switch (position) {
    case 'FOR':
      return 'ep-group__bar-fill--for';
    case 'AGAINST':
      return 'ep-group__bar-fill--against';
    case 'SPLIT':
    case 'ABSTENTION':
      return 'ep-group__bar-fill--split';
    default:
      return '';
  }
}

/**
 * Get position text class
 */
export function getPositionTextClass(position: GroupPosition): string {
  switch (position) {
    case 'FOR':
      return 'ep-group__position--for';
    case 'AGAINST':
      return 'ep-group__position--against';
    case 'SPLIT':
    case 'ABSTENTION':
      return 'ep-group__position--split';
    default:
      return '';
  }
}

// ============================================================================
// PI lens + calibration (Section 4 alignment)
// ============================================================================

const POSITIONS_BASE = `${import.meta.env.VITE_API_URL || ''}/api/positions`;

export interface PredictionPickerFile {
  carriage_id: string;
  procedure_ref?: string;
  title?: string;
  lead_committee?: string;
  current_status?: string;
  is_tracked: boolean;
  is_pi_match: boolean;
}
export interface InterestFiles {
  pi_active: boolean;
  tracked: PredictionPickerFile[];
  suggested: PredictionPickerFile[];
}

// Reuses the shared PI-bucketed carriage list (tracked + suggested-by-interests).
export async function getInterestFiles(myInterests: boolean): Promise<InterestFiles> {
  const response = await axios.get<InterestFiles>(`${POSITIONS_BASE}/`, {
    params: { my_interests: myInterests, limit: 40 },
  });
  return response.data;
}

export interface CalibrationResult {
  has_vote: boolean;
  procedure_ref: string;
  level?: string;
  result?: string;
  votes_for?: number;
  votes_against?: number;
  votes_abstention?: number;
  group_breakdown?: Record<string, any>;
  vote_date?: string | null;
  ta_reference?: string | null;
  source_url?: string | null;
}

// Actual roll-call outcome for predicted-vs-actual calibration.
export async function getCalibration(procedureRef: string): Promise<CalibrationResult> {
  const response = await axios.get<CalibrationResult>(
    `${API_BASE}/calibration/${encodeURIComponent(procedureRef)}`,
  );
  return response.data;
}
