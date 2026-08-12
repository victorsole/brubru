/**
 * EU institutional link helpers.
 * Generates URLs for OEIL, EULT (EU Law Tracker), RegDel, and EUR-Lex from procedure references.
 */

/**
 * Extract the procedure type code from a procedure reference.
 * Example: "2021/0106(COD)" -> "COD", "2024/0035(APP)" -> "APP"
 */
export function getProcedureType(procedureRef: string): string | null {
  if (!procedureRef) return null;
  const match = procedureRef.match(/\(([A-Z]+)\)$/);
  return match ? match[1] : null;
}

/**
 * Generate EU Law Tracker URL from a procedure reference.
 * Pattern: https://law-tracker.europa.eu/procedure/{YEAR}_{NUMBER}?lang=en
 * Example: "2021/0106(COD)" -> "https://law-tracker.europa.eu/procedure/2021_106?lang=en"
 *
 * Note: EULT only covers ordinary legislative procedure (COD) files.
 * Returns null for special procedures, implementing acts, and delegated acts.
 */
export function getEultUrl(procedureRef: string): string | null {
  if (!procedureRef) return null;

  // EULT only covers COD (ordinary legislative procedure) files
  const procType = getProcedureType(procedureRef);
  if (procType !== 'COD') return null;

  // Extract year and number from formats like "2021/0106(COD)"
  const match = procedureRef.match(/^(\d{4})\/(\d+)\([A-Z]+\)$/);
  if (!match) return null;

  const year = match[1];
  const number = parseInt(match[2], 10); // strips leading zeros

  return `https://law-tracker.europa.eu/procedure/${year}_${number}?lang=en`;
}

/**
 * Generate Register of Delegated and Implementing Acts URL.
 * Returns the URL for non-OLP procedures (delegated acts, implementing acts, etc.).
 * Returns null for COD (ordinary legislative procedure) files.
 */
export function getRegDelUrl(procedureRef: string): string | null {
  if (!procedureRef) return null;

  const procType = getProcedureType(procedureRef);
  // RegDel is relevant for non-COD procedures (delegated/implementing acts)
  if (!procType || procType === 'COD') return null;

  return 'https://webgate.ec.europa.eu/regdel/#/home';
}

/**
 * Generate OEIL URL from a procedure reference.
 */
export function getOeilUrl(procedureRef: string): string {
  return `https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${encodeURIComponent(procedureRef)}`;
}

/**
 * EUR-Lex permalink for a CELEX number.
 *
 * Lived as a private copy in dashboard_cockpit, parliamentary_questions_tab and
 * consultation_detail, while legislative_file_detail rendered CELEX numbers as
 * plain text: every tracked-file card showed "CELEX: 32026D1736" with no way to
 * reach the act. A citation the reader cannot open is half a citation.
 */
export function eurLexUrl(celex: string): string {
  return `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:${encodeURIComponent(celex.trim())}`;
}
