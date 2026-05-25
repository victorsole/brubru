/**
 * EU Canon registry.
 *
 * Maps CELEX numbers (and law-cluster names as a fallback) to the URL of the
 * Brubru eucanon public explainer page. This is what lets the chat and the
 * EU Law Comply cluster card surface a "Read the plain-language explainer"
 * reminder.
 *
 * As we add more eucanon pages, add entries here. Both CELEX and cluster-name
 * keys are supported because some clusters may not have a primary CELEX (yet).
 */

export const EUCANON_BY_CELEX: Record<string, string> = {
  '32013R0575': '/eucanon/2013-575_crr/',
  '32024R2754': '/eucanon/2024-2754_china_bev_duties/',
  '32020R0776': '/eucanon/2020-776_china_egypt_glass_fibre/',
  '32022R0433': '/eucanon/2022-433_india_indonesia_stainless_steel/',
};

export const EUCANON_BY_CLUSTER_NAME: Record<string, string> = {
  'CRR / CRD IV - Bank Prudential Requirements': '/eucanon/2013-575_crr/',
  'China BEV Countervailing Duties (Reg 2024/2754)': '/eucanon/2024-2754_china_bev_duties/',
  'China and Egypt GFF Countervailing Duties (Reg 2020/776)': '/eucanon/2020-776_china_egypt_glass_fibre/',
  'India and Indonesia Stainless Steel Countervailing Duties (Reg 2022/433)': '/eucanon/2022-433_india_indonesia_stainless_steel/',
};

export interface EucanonLookupInput {
  name?: string;
  primary_celex?: string | null;
}

export function getEucanonUrl(input: EucanonLookupInput): string | null {
  if (input.primary_celex && EUCANON_BY_CELEX[input.primary_celex]) {
    return EUCANON_BY_CELEX[input.primary_celex];
  }
  if (input.name && EUCANON_BY_CLUSTER_NAME[input.name]) {
    return EUCANON_BY_CLUSTER_NAME[input.name];
  }
  return null;
}
