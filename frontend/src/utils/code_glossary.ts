/**
 * Code glossary — plain-language expansions for the institutional codes that
 * appear as bare chips across MEUB (EP committees, Council configurations,
 * procedure types, voting terms). Used by the shared <CodeChip>/<InfoDot> so
 * "LIBE" / "ECOFIN" / "INL" / "QMV" always carry the same explanation
 * everywhere, instead of each tab inventing its own (or none).
 *
 * Expansions are deliberately in English here as a fallback; tabs that already
 * have a localised, data-backed name (e.g. the committees list) should keep
 * using that and only fall back to the glossary when no name is available.
 */

// EP standing committees + the two subcommittees (codes as used in OEIL / doceo).
export const EP_COMMITTEES: Record<string, string> = {
  AFET: 'Foreign Affairs',
  DROI: 'Human Rights (subcommittee)',
  SEDE: 'Security and Defence (subcommittee)',
  DEVE: 'Development',
  INTA: 'International Trade',
  BUDG: 'Budgets',
  CONT: 'Budgetary Control',
  ECON: 'Economic and Monetary Affairs',
  FISC: 'Tax Matters (subcommittee)',
  EMPL: 'Employment and Social Affairs',
  ENVI: 'Environment, Public Health and Food Safety',
  SANT: 'Public Health (subcommittee)',
  ITRE: 'Industry, Research and Energy',
  IMCO: 'Internal Market and Consumer Protection',
  TRAN: 'Transport and Tourism',
  REGI: 'Regional Development',
  AGRI: 'Agriculture and Rural Development',
  PECH: 'Fisheries',
  CULT: 'Culture and Education',
  JURI: 'Legal Affairs',
  LIBE: 'Civil Liberties, Justice and Home Affairs',
  AFCO: 'Constitutional Affairs',
  FEMM: "Women's Rights and Gender Equality",
  PETI: 'Petitions',
  EUDS: 'European Democracy Shield (special committee)',
};

// Council of the EU configurations.
export const COUNCIL_CONFIGS: Record<string, string> = {
  GAC: 'General Affairs Council',
  FAC: 'Foreign Affairs Council',
  ECOFIN: 'Economic and Financial Affairs Council',
  JHA: 'Justice and Home Affairs Council',
  EPSCO: 'Employment, Social Policy, Health and Consumer Affairs Council',
  COMPET: 'Competitiveness Council',
  TTE: 'Transport, Telecommunications and Energy Council',
  AGRIFISH: 'Agriculture and Fisheries Council',
  ENV: 'Environment Council',
  EYC: 'Education, Youth, Culture and Sport Council',
  EYCS: 'Education, Youth, Culture and Sport Council',
};

// OEIL procedure-type suffixes (the bit in brackets in e.g. 2024/0176(COD)).
export const PROCEDURE_TYPES: Record<string, string> = {
  COD: 'Ordinary legislative procedure — a new EU law decided jointly by Parliament and Council',
  CNS: 'Consultation procedure — Council decides after consulting Parliament',
  APP: 'Consent procedure — Parliament must approve without amending',
  NLE: 'Consent to an international agreement',
  INL: 'Legislative-initiative report — Parliament asks the Commission to propose a law',
  INI: "Own-initiative report — Parliament's political position, not binding law",
  RSP: 'Resolution on a topical subject',
  RSO: 'Resolution on an internal Parliament matter',
  DEA: 'Scrutiny of a delegated act',
  RPS: 'Scrutiny of an implementing act',
  BUD: 'Annual budget procedure',
  DEC: 'Budgetary discharge',
  IMM: 'Parliamentary immunity matter',
  REG: "Parliament's Rules of Procedure",
};

// Standalone terms / acronyms.
export const TERMS: Record<string, string> = {
  QMV: 'Qualified majority voting — 55% of member states representing at least 65% of the EU population',
  OEIL: "The Parliament's Legislative Observatory (procedure files)",
  CELEX: "EUR-Lex's unique identifier for an EU legal document",
  PI: 'Your Policy Interests',
};

/** Expand a bracketed procedure ref like "2024/0176(COD)" to its type sentence. */
export function procedureTypeFor(ref?: string | null): string | null {
  if (!ref) return null;
  const m = ref.match(/\(([A-Z]+)\)/);
  return m ? PROCEDURE_TYPES[m[1]] || null : null;
}

/** One lookup across every map. Returns a plain-language string, or null. */
export function glossaryFor(code?: string | null): string | null {
  if (!code) return null;
  const c = code.trim().toUpperCase();
  return (
    EP_COMMITTEES[c] ||
    COUNCIL_CONFIGS[c] ||
    PROCEDURE_TYPES[c] ||
    TERMS[c] ||
    procedureTypeFor(code) ||
    null
  );
}
