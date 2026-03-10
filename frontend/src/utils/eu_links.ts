/**
 * EU institutional link helpers.
 * Generates URLs for OEIL, EULT (EU Law Tracker), and EUR-Lex from procedure references.
 */

/**
 * Generate EU Law Tracker URL from a procedure reference.
 * Pattern: https://law-tracker.europa.eu/procedure/{YEAR}_{NUMBER}?lang=en
 * Example: "2021/0106(COD)" -> "https://law-tracker.europa.eu/procedure/2021_106?lang=en"
 *
 * Note: EULT only covers new files from May 2024 onwards, plus some older ones.
 */
export function getEultUrl(procedureRef: string): string | null {
  if (!procedureRef) return null;

  // Extract year and number from formats like "2021/0106(COD)" or "2025/0580(CNS)"
  const match = procedureRef.match(/^(\d{4})\/(\d+)\([A-Z]+\)$/);
  if (!match) return null;

  const year = match[1];
  const number = parseInt(match[2], 10); // strips leading zeros

  return `https://law-tracker.europa.eu/procedure/${year}_${number}?lang=en`;
}

/**
 * Generate OEIL URL from a procedure reference.
 */
export function getOeilUrl(procedureRef: string): string {
  return `https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${encodeURIComponent(procedureRef)}`;
}
