// CMU Monitor Fallback Data
// Static data to ensure dashboard works when APIs are unavailable

import type {
  CMULegislativeItem,
  SIUPillar,
  CMUMetrics,
  CalendarEvent,
  CMUNewsItem,
  ResearchPublication,
  QuickStat,
} from '@/types/cmu';

// SIU Pillars with progress
export const FALLBACK_SIU_PILLARS: SIUPillar[] = [
  {
    id: 'citizens_savings',
    name: 'Citizens & Savings',
    icon: 'Users',
    progress: 25,
    color: 'primary',
  },
  {
    id: 'investment_financing',
    name: 'Investment & Financing',
    icon: 'TrendingUp',
    progress: 30,
    color: 'primary',
  },
  {
    id: 'integration_scale',
    name: 'Integration & Scale',
    icon: 'Globe',
    progress: 15,
    color: 'accent',
  },
  {
    id: 'supervision',
    name: 'Supervision',
    icon: 'Shield',
    progress: 20,
    color: 'accent',
  },
];

// Quick Stats (verified from ECB, AFME, Draghi Report - Jan 2026)
export const FALLBACK_QUICK_STATS: QuickStat[] = [
  {
    label: 'Cross-border holdings',
    value: '70% of GDP',
    sources: ['ecb'],
  },
  {
    label: 'Household savings in deposits',
    value: '€11.5 trillion',
    sources: ['ecb'],
  },
  {
    label: 'EU share of global market cap',
    value: '11%',
    sources: ['afme'],
  },
  {
    label: 'Annual capital flight to US',
    value: '€300B',
    color: 'destructive',
    sources: ['draghi_report'],
  },
  {
    label: 'Draghi investment gap',
    value: '€750-800B/yr',
    color: 'accent',
    sources: ['draghi_report'],
  },
];

// CMU Metrics (verified from ECB, AFME, World Bank, Draghi Report - Jan 2026)
export const FALLBACK_METRICS: CMUMetrics = {
  overallProgress: 32,
  legislationAdopted: 43,
  actionPlanProgress: '5/16',
  integrationIndex: 0.15,

  // EU vs US comparison (AFME Capital Markets Union KPIs 2024, World Bank)
  euMarketCapGDP: 55,          // EU-27 avg ~55% (varies by country, e.g. France 110%, Germany 50%)
  usMarketCapGDP: 195,         // US ~195% (Dec 2024, World Bank/CEIC)
  euVCGDP: 0.06,               // EU VC ~0.06% GDP (Invest Europe 2024)
  usVCGDP: 0.65,               // US VC ~0.65% GDP (NVCA 2024)
  euHouseholdInvGDP: 93,       // AFME: EU household financial assets 93% GDP
  usHouseholdInvGDP: 298,      // AFME: US household financial assets 298% GDP
  euInvPerAdult: 42,           // €42k average (Credit Suisse Global Wealth)
  usInvPerAdult: 192,          // $192k average (Credit Suisse Global Wealth)
  euIPOCount: 98,              // 2024 EU IPOs (EY IPO Report)
  usIPOCount: 176,             // 2024 US IPOs (EY IPO Report)
  euIPOProceeds: 12.8,         // €12.8B 2024 (EY)
  usIPOProceeds: 33.2,         // $33.2B 2024 (EY)

  // Quick stats
  crossBorderHoldingsGDP: 70,
  householdSavingsDeposits: 11.5, // €11.5 trillion (ECB 2024)
  euGlobalMarketCapShare: 11,     // ~11% of global market cap
  annualCapitalFlightUS: 300,
  draghiInvestmentGap: '€750-800B/yr',

  // Integration trend data (2015-2024)
  integrationTrend: [
    { year: 2015, priceIndex: 0.12, quantityIndex: 0.18 },
    { year: 2016, priceIndex: 0.13, quantityIndex: 0.17 },
    { year: 2017, priceIndex: 0.14, quantityIndex: 0.16 },
    { year: 2018, priceIndex: 0.15, quantityIndex: 0.16 },
    { year: 2019, priceIndex: 0.152, quantityIndex: 0.155 },
    { year: 2020, priceIndex: 0.14, quantityIndex: 0.14 },
    { year: 2021, priceIndex: 0.145, quantityIndex: 0.145 },
    { year: 2022, priceIndex: 0.148, quantityIndex: 0.15 },
    { year: 2023, priceIndex: 0.15, quantityIndex: 0.152 },
    { year: 2024, priceIndex: 0.15, quantityIndex: 0.15 },
  ],

  lastUpdated: new Date(),
};

// Legislative Pipeline Items
export const FALLBACK_LEGISLATION: CMULegislativeItem[] = [
  // Proposed
  {
    id: 'faster-wht',
    celexNumber: 'COM/2022/702',
    title: 'Faster and Safer Relief of Excess Withholding Taxes',
    shortTitle: 'FASTER WHT',
    type: 'regulation',
    status: 'proposed',
    category: 'taxation',
    dateProposed: '2022-06-01',
    eurLexUrl: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52022PC0702',
    summary: 'Framework for faster relief of excess withholding taxes on cross-border securities investments',
    sources: ['eur_lex', 'european_commission'],
  },
  {
    id: 'insolvency-iii',
    celexNumber: 'COM/2022/761',
    title: 'Harmonising certain aspects of insolvency law',
    shortTitle: 'Insolvency III',
    type: 'directive',
    status: 'proposed',
    category: 'market_infrastructure',
    dateProposed: '2022-12-07',
    eurLexUrl: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52022PC0761',
    summary: 'Proposal for harmonising insolvency proceedings across the EU',
    sources: ['eur_lex', 'european_commission'],
  },
  {
    id: '28th-regime',
    celexNumber: 'COM/2026/XXX',
    title: '28th Regime / EU-Inc',
    shortTitle: 'EU-Inc',
    type: 'regulation',
    status: 'proposed',
    category: 'company_law',
    dateProposed: '2026-01-20',
    eurLexUrl: 'https://www.eu-inc.org/',
    summary: 'Pan-European company structure announced by VdL at Davos. Legislative proposal expected March 2026.',
    sources: ['european_commission'],
  },
  {
    id: 'market-integration-package',
    celexNumber: 'COM/2025/MIS',
    title: 'Market Integration & Supervision Package',
    shortTitle: 'MIS Package',
    type: 'regulation',
    status: 'proposed',
    category: 'market_infrastructure',
    dateProposed: '2025-12-04',
    eurLexUrl: 'https://finance.ec.europa.eu/publications/market-integration-package_en',
    summary: 'Three legislative proposals amending 19 pieces of EU legislation to address capital markets fragmentation',
    sources: ['european_commission', 'esma'],
  },
  // EP Reading
  {
    id: 'ris',
    celexNumber: '2023/0166(COD)',
    title: 'Retail Investment Strategy',
    shortTitle: 'Retail Investment Strategy',
    type: 'directive',
    status: 'ep_reading',
    category: 'retail',
    dateProposed: '2023-05-24',
    eurLexUrl: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52023PC0279',
    summary: 'Package to enhance retail investor participation in capital markets',
    sources: ['eur_lex', 'eprs'],
  },
  {
    id: 'securitization-review',
    celexNumber: '2024/0XXX(COD)',
    title: 'Securitization Framework Review',
    shortTitle: 'Securitization Review',
    type: 'regulation',
    status: 'ep_reading',
    category: 'securitization',
    eurLexUrl: '#',
    summary: 'Review of the STS securitization framework to revitalize EU securitization market',
    sources: ['european_commission', 'eba'],
  },
  // Council
  {
    id: 'pepp-review',
    celexNumber: '2022/0403(COD)',
    title: 'Pan-European Personal Pension Product Review',
    shortTitle: 'PEPP Review',
    type: 'regulation',
    status: 'council',
    category: 'retail',
    dateProposed: '2022-12-01',
    eurLexUrl: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52022PC0763',
    summary: 'Amendments to enhance PEPP uptake and cross-border portability',
    sources: ['eur_lex', 'eiopa'],
  },
  // Adopted
  {
    id: 'listing-act',
    celexNumber: '2024/2809',
    title: 'Listing Act Package',
    shortTitle: 'Listing Act',
    type: 'regulation',
    status: 'adopted',
    category: 'market_infrastructure',
    dateProposed: '2022-12-07',
    dateAdopted: '2024-10-14',
    eurLexUrl: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R2809',
    summary: 'Simplifies listing requirements for EU capital markets',
    sources: ['eur_lex'],
  },
  {
    id: 'eltif-2',
    celexNumber: '2023/606',
    title: 'European Long-Term Investment Funds 2.0',
    shortTitle: 'ELTIF 2.0',
    type: 'regulation',
    status: 'adopted',
    category: 'investment_funds',
    dateProposed: '2021-11-25',
    dateAdopted: '2023-03-15',
    dateInForce: '2024-01-10',
    eurLexUrl: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R0606',
    summary: 'Reformed ELTIF framework with more flexible investment rules',
    sources: ['eur_lex'],
  },
  // In Force
  {
    id: 'mifid-ii',
    celexNumber: '2014/65/EU',
    title: 'Markets in Financial Instruments Directive II',
    shortTitle: 'MiFID II',
    type: 'directive',
    status: 'in_force',
    category: 'market_infrastructure',
    dateAdopted: '2014-05-15',
    dateInForce: '2018-01-03',
    eurLexUrl: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32014L0065',
    summary: 'Core framework for EU securities markets regulation',
    sources: ['eur_lex'],
  },
  {
    id: 'mifir',
    celexNumber: '600/2014',
    title: 'Markets in Financial Instruments Regulation',
    shortTitle: 'MiFIR',
    type: 'regulation',
    status: 'in_force',
    category: 'market_infrastructure',
    dateAdopted: '2014-05-15',
    dateInForce: '2018-01-03',
    eurLexUrl: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32014R0600',
    summary: 'Transparency and trading rules for securities markets',
    sources: ['eur_lex'],
  },
  {
    id: 'emir',
    celexNumber: '648/2012',
    title: 'European Market Infrastructure Regulation',
    shortTitle: 'EMIR',
    type: 'regulation',
    status: 'in_force',
    category: 'market_infrastructure',
    dateAdopted: '2012-07-04',
    dateInForce: '2012-08-16',
    eurLexUrl: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32012R0648',
    summary: 'Framework for OTC derivatives, central counterparties and trade repositories',
    sources: ['eur_lex'],
  },
  {
    id: 'csdr',
    celexNumber: '909/2014',
    title: 'Central Securities Depositories Regulation',
    shortTitle: 'CSDR',
    type: 'regulation',
    status: 'in_force',
    category: 'market_infrastructure',
    dateAdopted: '2014-07-23',
    dateInForce: '2014-09-17',
    eurLexUrl: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32014R0909',
    summary: 'Rules for securities settlement and CSDs',
    sources: ['eur_lex'],
  },
  {
    id: 'sftr',
    celexNumber: '2015/2365',
    title: 'Securities Financing Transactions Regulation',
    shortTitle: 'SFTR',
    type: 'regulation',
    status: 'in_force',
    category: 'transparency',
    dateAdopted: '2015-11-25',
    dateInForce: '2016-01-12',
    eurLexUrl: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32015R2365',
    summary: 'Transparency requirements for securities financing transactions',
    sources: ['eur_lex'],
  },
];

// Calendar Events
export const FALLBACK_CALENDAR: CalendarEvent[] = [
  {
    id: 'sec-proposal',
    date: 'Q2 2025',
    title: 'Securitization Proposal',
    type: 'proposal',
    description: 'Commission proposal for STS framework revision',
    sources: ['european_commission'],
  },
  {
    id: 'fin-literacy',
    date: 'Q3 2025',
    title: 'Financial Literacy Strategy',
    type: 'strategy',
    description: 'EU-wide financial literacy framework adoption',
    sources: ['european_commission'],
  },
  {
    id: 'pepp-revision',
    date: 'Nov 2025',
    title: 'PEPP Revision Proposal',
    type: 'proposal',
    description: 'Revised PEPP framework proposal',
    sources: ['european_commission', 'eiopa'],
  },
  {
    id: 'esap-operational',
    date: 'Jul 2026',
    title: 'ESAP Operational',
    type: 'deadline',
    description: 'European Single Access Point goes live',
    sources: ['european_commission', 'esma'],
  },
  {
    id: 'siu-review',
    date: 'Q2 2027',
    title: 'SIU Mid-Term Review',
    type: 'review',
    description: 'Mid-term review of Savings and Investment Union progress',
    sources: ['european_commission'],
  },
  {
    id: 'listing-act-full',
    date: '2028',
    title: 'Listing Act Full Application',
    type: 'deadline',
    description: 'Full application of Listing Act provisions',
    sources: ['eur_lex'],
  },
  {
    id: 'esa-review',
    date: '2029',
    title: 'ESA Review Implementation',
    type: 'review',
    description: 'European Supervisory Authorities review implementation',
    sources: ['european_commission', 'esma'],
  },
];

// News Items (real news, sorted most recent first - Jan 2026)
export const FALLBACK_NEWS: CMUNewsItem[] = [
  {
    id: 'news-0',
    title: 'Von der Leyen announces EU-Inc at Davos',
    description: 'Commission President announces the EU will create "a truly European company structure" called EU-Inc. Legislative proposal expected March 2026.',
    url: 'https://www.eu-inc.org/',
    source: 'european_commission',
    sourceLabel: 'WEF Davos',
    publishedAt: new Date('2026-01-20'),
  },
  {
    id: 'news-1',
    title: 'Council agrees position on revitalising EU securitisation market',
    description: 'EU ministers agree position on securitisation proposals as part of the Savings and Investment Union strategy',
    url: 'https://www.consilium.europa.eu/en/press/press-releases/2025/12/19/savings-and-investment-union-council-agrees-position-on-revitalising-the-eu-s-securitisation-market/',
    source: 'european_commission',
    sourceLabel: 'Council',
    publishedAt: new Date('2025-12-19'),
  },
  {
    id: 'news-2',
    title: 'CMU deal possible within a year, says Commissioner Albuquerque',
    description: 'Financial Services Commissioner states EU can reach Capital Markets Union deal within a year if political will exists',
    url: 'https://www.euronews.com/my-europe/2025/12/15/capital-markets-union-deal-possible-within-a-year-commissioner-albuquerque-tells-euronews',
    source: 'european_commission',
    sourceLabel: 'Euronews',
    publishedAt: new Date('2025-12-15'),
  },
  {
    id: 'news-3',
    title: 'Commission adopts Market Integration Package',
    description: 'Comprehensive package to remove barriers and unlock EU single market potential for financial services, following Draghi report recommendations',
    url: 'https://finance.ec.europa.eu/publications/market-integration-package_en',
    source: 'european_commission',
    sourceLabel: 'EC',
    publishedAt: new Date('2025-12-04'),
  },
  {
    id: 'news-4',
    title: 'ESMA welcomes Market Integration Package proposals',
    description: 'EU financial markets regulator publishes Spotlight on Markets newsletter underlining importance of deeper, more integrated capital markets',
    url: 'https://www.esma.europa.eu/press-news/esma-news/esma-publishes-latest-spotlight-markets-newsletter-featuring-updates-market',
    source: 'esma',
    sourceLabel: 'ESMA',
    publishedAt: new Date('2025-12-04'),
  },
  {
    id: 'news-5',
    title: 'Commission proposes securitisation framework amendments',
    description: 'Proposals to revitalise securitisation market by reducing regulatory burdens and enhancing risk sensitivity',
    url: 'https://finance.ec.europa.eu/regulation-and-supervision/savings-and-investments-union_en',
    source: 'european_commission',
    sourceLabel: 'EC',
    publishedAt: new Date('2025-06-17'),
  },
];

// Research Publications (real publications with verified URLs - Dec 2025)
export const FALLBACK_RESEARCH: ResearchPublication[] = [
  {
    id: 'research-1',
    title: 'Savings and Investments Union: Overview and State of Play',
    author: 'EPRS',
    organization: 'eprs',
    organizationLabel: 'EPRS',
    publishedAt: 'Nov 2025',
    url: 'https://epthinktank.eu/2025/11/19/savings-and-investments-union-overview-and-state-of-play/',
    abstract: 'European Parliament briefing on SIU strategy implementation status and key proposals',
    iconColor: 'primary',
  },
  {
    id: 'research-2',
    title: "Europe's Elusive Savings and Investment Union",
    author: 'IMF - Ravi Balakrishnan',
    organization: 'imf',
    organizationLabel: 'IMF',
    publishedAt: 'June 2025',
    url: 'https://www.imf.org/en/publications/fandd/issues/2025/06/europes-elusive-savings-and-investment-union-ravi-balakrishnan',
    abstract: 'Analysis of challenges and obstacles facing the EU Savings and Investment Union',
    iconColor: 'secondary',
  },
  {
    id: 'research-3',
    title: 'The Future of European Competitiveness',
    author: 'Mario Draghi',
    organization: 'draghi_report',
    organizationLabel: 'Draghi',
    publishedAt: 'Sept 2024',
    url: 'https://commission.europa.eu/topics/competitiveness/draghi-report_en',
    abstract: '€750-800B annual investment needs, CMU as priority for EU competitiveness',
    iconColor: 'accent',
  },
  {
    id: 'research-4',
    title: 'Much More Than a Market',
    author: 'Enrico Letta',
    organization: 'letta_report',
    organizationLabel: 'Letta',
    publishedAt: 'April 2024',
    url: 'https://www.consilium.europa.eu/media/ny3j24sm/much-more-than-a-market-report-by-enrico-letta.pdf',
    abstract: 'Single Market reform proposals including the Savings and Investment Union vision',
    iconColor: 'primary',
  },
  {
    id: 'research-5',
    title: 'How can the EU achieve its aim of a Savings and Investments Union?',
    author: 'Bruegel',
    organization: 'bruegel',
    organizationLabel: 'Bruegel',
    publishedAt: '2025',
    url: 'https://www.bruegel.org/newsletter/how-can-eu-achieve-its-aim-savings-and-investments-union',
    abstract: 'Policy analysis on key obstacles and pathways to achieving the SIU',
    iconColor: 'secondary',
  },
];

// Helper functions
export function getLegislationByStatus(status: CMULegislativeItem['status']): CMULegislativeItem[] {
  return FALLBACK_LEGISLATION.filter((item) => item.status === status);
}

export function getInForceLegislationCount(): number {
  return FALLBACK_LEGISLATION.filter((item) => item.status === 'in_force').length;
}

export function calculateOverallProgress(): number {
  const pillarsAvg =
    FALLBACK_SIU_PILLARS.reduce((acc, p) => acc + p.progress, 0) / FALLBACK_SIU_PILLARS.length;
  return Math.round(pillarsAvg);
}
