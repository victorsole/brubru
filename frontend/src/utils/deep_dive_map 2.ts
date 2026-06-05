/**
 * Deep Dive Map
 *
 * Maps procedure references to deep-dive HTML page URLs.
 * Used by both the Analytics tab (Deep Dive Library) and
 * My Files tracked file cards (Deep Dive link button).
 */

export interface DeepDive {
  title: string;
  shortTitle: string;
  comReference: string;
  procedureRef: string;
  basePath: string;
  languages: string[];
  color: string;
  icon: string;
}

export const DEEP_DIVES: DeepDive[] = [
  {
    title: 'EU Inc.: the 28th Regime for European Companies',
    shortTitle: 'EU Inc.',
    comReference: 'COM(2026) 321',
    procedureRef: '2026/0074(COD)',
    basePath: '/eu-inc',
    languages: ['en', 'fr', 'es', 'it', 'nl', 'ca'],
    color: '#0693e3',
    icon: 'mdi-domain',
  },
  {
    title: 'European Biotech Act',
    shortTitle: 'Biotech Act',
    comReference: 'COM(2025) 1022',
    procedureRef: '2025/0406(COD)',
    basePath: '/biotech-act',
    languages: ['en', 'fr', 'es', 'it', 'nl', 'ca'],
    color: '#059669',
    icon: 'mdi-dna',
  },
  {
    title: 'Industrial Accelerator Act',
    shortTitle: 'Industrial Accelerator',
    comReference: 'COM(2026) 100',
    procedureRef: '2026/0068(COD)',
    basePath: '/industrial-accelerator-act',
    languages: ['en', 'fr', 'es', 'it', 'nl', 'ca'],
    color: '#9b51e0',
    icon: 'mdi-factory',
  },
  {
    title: 'Late Payments Regulation',
    shortTitle: 'Late Payments',
    comReference: 'COM(2023) 533',
    procedureRef: '2023/0323(COD)',
    basePath: '/late-payments',
    languages: ['en', 'fr', 'es', 'it', 'nl', 'ca'],
    color: '#dc2626',
    icon: 'mdi-clock-alert-outline',
  },
  {
    title: 'EU Pharmaceutical Laws: The Complete Framework',
    shortTitle: 'EU Pharma Laws',
    comReference: 'COM(2023) 192 + COM(2023) 193',
    procedureRef: '2023/0131(COD)',
    basePath: '/pharma-laws',
    languages: ['en', 'fr', 'es', 'it', 'nl', 'ca'],
    color: '#d97706',
    icon: 'mdi-pill',
  },
  {
    title: 'Digital Networks Act: Rewiring Europe\'s Telecoms',
    shortTitle: 'Digital Networks Act',
    comReference: 'COM(2026) 16',
    procedureRef: '2026/0013(COD)',
    basePath: '/digital-networks-act',
    languages: ['en', 'fr', 'es', 'it', 'nl', 'ca'],
    color: '#9b51e0',
    icon: 'mdi-access-point-network',
  },
  {
    title: 'Combating Child Sexual Abuse Online (CSAM Regulation)',
    shortTitle: 'CSAM Regulation',
    comReference: 'COM(2022) 209',
    procedureRef: '2022/0155(COD)',
    basePath: '/csam-regulation',
    languages: ['en'],
    color: '#dc2626',
    icon: 'mdi-shield-alert-outline',
  },
  {
    title: 'EU-Andorra Association Agreement',
    shortTitle: 'EU-Andorra AA',
    comReference: 'COM(2024) 191',
    procedureRef: '2024/0102(NLE)',
    basePath: '/legislacio-ue-catala/eu-andorra',
    languages: ['ca'],
    color: '#d52b1e',
    icon: 'mdi-mountain',
  },
];

/**
 * Lookup deep dive by procedure reference.
 * Returns the deep dive entry or undefined if no match.
 */
export function getDeepDiveForProcedure(procedureRef: string): DeepDive | undefined {
  return DEEP_DIVES.find(d => d.procedureRef === procedureRef);
}

/**
 * Get the URL for a deep dive in a given language.
 */
export function getDeepDiveUrl(deepDive: DeepDive, lang: string = 'en'): string {
  if (lang === 'en') return `${deepDive.basePath}/index.html`;
  return `${deepDive.basePath}/${lang}.html`;
}

const LANG_LABELS: Record<string, string> = {
  en: 'EN',
  fr: 'FR',
  es: 'ES',
  it: 'IT',
  nl: 'NL',
  ca: 'CA',
};

export { LANG_LABELS };
