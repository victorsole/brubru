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
};

export const EUCANON_BY_CLUSTER_NAME: Record<string, string> = {
  'CRR / CRD IV - Bank Prudential Requirements': '/eucanon/2013-575_crr/',
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
