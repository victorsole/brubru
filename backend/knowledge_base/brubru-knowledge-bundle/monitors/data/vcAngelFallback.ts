import type {
  VCMarketMetrics,
  VCLegislation,
  AngelTaxScheme,
  ELTIFDataPoint,
  VCKeyDate,
} from '@/types/vcAngel';

export const VC_MARKET_METRICS: VCMarketMetrics = {
  euGlobalShare: '5%',
  usGlobalShare: '52%',
  chinaGlobalShare: '40%',
  euAvgFundSize: '€60M',
  usAvgFundSize: '€130M+',
  euUnicorns: 110,
  usUnicorns: 687,
  euPensionFundShare: '7%',
  usPensionFundShare: '~20%',
};

export const VC_LEGISLATION: VCLegislation[] = [
  {
    id: 'euveca',
    name: 'European Venture Capital Funds Regulation',
    shortName: 'EuVECA',
    legalBasis: 'Regulation (EU) No 345/2013',
    status: 'under_review',
    statusLabel: 'Under Review',
    description: 'Voluntary label for qualifying VC fund managers to market funds across the EU without full AIFMD compliance.',
    keyProvisions: [
      '70% rule: Must invest 70% in qualifying SME investments',
      'Manager threshold: Available to managers with AuM below €500M',
      'EU passport: Cross-border marketing throughout the EU',
      'Minimum €100,000 investor commitment',
    ],
    eurLexUrl: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32013R0345',
  },
  {
    id: 'eusef',
    name: 'European Social Entrepreneurship Funds Regulation',
    shortName: 'EuSEF',
    legalBasis: 'Regulation (EU) No 346/2013',
    status: 'under_review',
    statusLabel: 'Under Review',
    description: 'Dedicated framework for funds investing in social enterprises with measurable positive social impact.',
    keyProvisions: [
      'Same regulatory architecture as EuVECA',
      'Investments must have demonstrable social objectives',
      'Supports vulnerable/marginalised groups',
      'EU-wide passporting for social impact funds',
    ],
    eurLexUrl: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32013R0346',
  },
  {
    id: 'eltif2',
    name: 'European Long-Term Investment Funds 2.0',
    shortName: 'ELTIF 2.0',
    legalBasis: 'Regulation (EU) 2023/606',
    status: 'in_force',
    statusLabel: 'In Force',
    description: 'Retail-accessible investment in long-term assets including infrastructure, SMEs, and innovative enterprises.',
    keyProvisions: [
      'Removed €10,000 minimum investment per ELTIF',
      'Removed 10% cap on retail investor portfolio allocation',
      'Expanded eligible assets to €1.5B market cap companies',
      'Semi-liquid structures with secondary market trading',
    ],
    eurLexUrl: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R0606',
  },
  {
    id: 'aifmd2',
    name: 'Alternative Investment Fund Managers Directive II',
    shortName: 'AIFMD II',
    legalBasis: 'Directive (EU) 2024/927',
    status: 'transposition',
    statusLabel: 'Transposition',
    description: 'Overarching regulatory framework for alternative investment funds, including VC funds above €500M threshold.',
    keyProvisions: [
      'New rules for loan-originating AIFs',
      'Clarified delegation requirements',
      'Enhanced liquidity management tools',
      'Improved transparency and reporting',
    ],
    eurLexUrl: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0061',
    deadline: 'April 2026',
  },
];

export const ANGEL_TAX_SCHEMES: AngelTaxScheme[] = [
  {
    countryCode: 'BE',
    countryName: 'Belgium',
    schemeName: 'Tax Shelter for Startups',
    taxRelief: '30-45%',
    maxInvestment: '€100,000/year',
    holdingPeriod: '4 years',
    conditions: 'Investment in qualifying startup <4 years old',
  },
  {
    countryCode: 'FR',
    countryName: 'France',
    schemeName: 'JEI (Jeunes Entreprises Innovantes)',
    taxRelief: '30%',
    maxInvestment: '€75,000 (single) / €150,000 (couple)',
    holdingPeriod: '5 years',
    conditions: 'Investment in innovative startup <10 years old',
  },
  {
    countryCode: 'DE',
    countryName: 'Germany',
    schemeName: 'INVEST Grant',
    taxRelief: '15% + 25% exit',
    maxInvestment: '€500,000/year',
    holdingPeriod: '3 years',
    conditions: 'Investment ≥€10,000 in innovative startup',
  },
  {
    countryCode: 'IT',
    countryName: 'Italy',
    schemeName: 'Innovative Startup Deduction',
    taxRelief: 'Up to 50%',
    maxInvestment: '€100,000/year (startups)',
    holdingPeriod: '3 years',
    conditions: 'Investment in innovative startup/SME',
  },
  {
    countryCode: 'PT',
    countryName: 'Portugal',
    schemeName: 'Programa Semente',
    taxRelief: '25%',
    maxInvestment: '€100,000/year',
    holdingPeriod: 'N/A',
    conditions: 'Investment in early-stage innovative startup',
  },
  {
    countryCode: 'IE',
    countryName: 'Ireland',
    schemeName: 'Employment & Investment Incentive (EII)',
    taxRelief: 'Up to 40%',
    maxInvestment: '€15M lifetime per company',
    holdingPeriod: '4 years',
    conditions: 'Investment in qualifying trading company',
  },
  {
    countryCode: 'NL',
    countryName: 'Netherlands',
    schemeName: 'Angel Investment Deduction',
    taxRelief: '30%',
    maxInvestment: '€100,000/year',
    holdingPeriod: '3 years',
    conditions: 'Investment in qualifying innovative SME',
  },
  {
    countryCode: 'ES',
    countryName: 'Spain',
    schemeName: 'Startup Law Deduction',
    taxRelief: '50%',
    maxInvestment: '€100,000/year',
    holdingPeriod: '3 years',
    conditions: 'Investment in newly formed innovative company',
  },
  {
    countryCode: 'AT',
    countryName: 'Austria',
    schemeName: 'Startup Funding Incentive',
    taxRelief: '25%',
    maxInvestment: '€50,000/year',
    holdingPeriod: '5 years',
    conditions: 'Investment in qualifying startup',
  },
  {
    countryCode: 'PL',
    countryName: 'Poland',
    schemeName: 'IP Box + Angel Relief',
    taxRelief: '19%',
    maxInvestment: 'No cap',
    holdingPeriod: '2 years',
    conditions: 'Investment in innovative company',
  },
];

export const ELTIF_GROWTH_DATA: ELTIFDataPoint[] = [
  { year: 2023, fundsMarketed: 100, aumBillions: 2.4 },
  { year: 2024, fundsMarketed: 118, aumBillions: 12.0 },
  { year: 2025, fundsMarketed: 183, aumBillions: 20.5 },
];

export const VC_KEY_DATES: VCKeyDate[] = [
  { date: 'Q1 2024', event: 'ELTIF 2.0 enters into force', status: 'past' },
  { date: 'April 2024', event: 'AIFMD II enters into force', status: 'past' },
  { date: 'October 2024', event: 'ELTIF 2.0 RTS adopted', status: 'past' },
  { date: 'March 2025', event: 'Savings and Investments Union launched', status: 'past' },
  { date: 'May 2025', event: 'EU Startup and Scaleup Strategy launched', status: 'past' },
  { date: 'July 2025', event: 'European Innovation Act consultation', status: 'past' },
  { date: 'Q4 2025', event: 'EuVECA review technical advice expected', status: 'current' },
  { date: 'Q1 2026', event: '28th Regime legislative proposal expected', status: 'upcoming' },
  { date: 'Q1 2026', event: 'European Innovation Act proposal expected', status: 'upcoming' },
  { date: 'Early 2026', event: 'Scaleup Europe Fund operations begin', status: 'upcoming' },
  { date: 'April 2026', event: 'AIFMD II transposition deadline', status: 'upcoming' },
];

// Helper function to get tax relief as a number for map colouring
export function getTaxReliefValue(scheme: AngelTaxScheme): number {
  const relief = scheme.taxRelief;
  // Extract the first number from the string
  const match = relief.match(/(\d+)/);
  return match ? parseInt(match[1], 10) : 0;
}
