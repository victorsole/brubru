// EU Capital Markets Union Monitor Types

// Data source tracking
export type DataSource =
  | 'european_commission'
  | 'eur_lex'
  | 'ecb'
  | 'esma'
  | 'eba'
  | 'eiopa'
  | 'eprs'
  | 'jrc'
  | 'eib'
  | 'eif'
  | 'eca'
  | 'bruegel'
  | 'letta_report'
  | 'draghi_report'
  | 'afme'
  | 'imf'
  | 'eurostat'
  | 'sifted'
  | 'invest_europe'
  | 'dealroom'
  | 'pitchbook'
  | 'web_search';

export type CMUCategory =
  | 'market_infrastructure'
  | 'investment_funds'
  | 'transparency'
  | 'retail'
  | 'supervision'
  | 'securitization'
  | 'taxation'
  | 'company_law';

export type LegislativeStatus =
  | 'proposed'
  | 'ep_reading'
  | 'council'
  | 'trilogue'
  | 'adopted'
  | 'in_force';

// Core entities
export interface CMULegislativeItem {
  id: string;
  celexNumber: string;
  title: string;
  shortTitle: string;
  type: 'regulation' | 'directive' | 'decision' | 'recommendation';
  status: LegislativeStatus;
  category: CMUCategory;
  dateProposed?: string;
  dateAdopted?: string;
  dateInForce?: string;
  eurLexUrl: string;
  summary?: string;
  sources: DataSource[];
}

export interface SIUPillar {
  id: 'citizens_savings' | 'investment_financing' | 'integration_scale' | 'supervision';
  name: string;
  icon: string;
  progress: number;
  color: 'primary' | 'accent';
}

export interface CMUMetrics {
  // Overall progress
  overallProgress: number;
  legislationAdopted: number;
  actionPlanProgress: string;
  integrationIndex: number;

  // EU vs US comparison
  euMarketCapGDP: number;
  usMarketCapGDP: number;
  euVCGDP: number;
  usVCGDP: number;
  euHouseholdInvGDP: number;
  usHouseholdInvGDP: number;
  euInvPerAdult: number;
  usInvPerAdult: number;
  euIPOCount: number;
  usIPOCount: number;
  euIPOProceeds: number;
  usIPOProceeds: number;

  // Quick stats
  crossBorderHoldingsGDP: number;
  householdSavingsDeposits: number;
  euGlobalMarketCapShare: number;
  annualCapitalFlightUS: number;
  draghiInvestmentGap: string;

  // Integration trend data
  integrationTrend: { year: number; priceIndex: number; quantityIndex: number }[];

  lastUpdated: Date;
}

export interface CalendarEvent {
  id: string;
  date: string;
  title: string;
  type: 'deadline' | 'proposal' | 'review' | 'implementation' | 'strategy';
  description?: string;
  linkedLegislation?: string;
  sources: DataSource[];
}

export interface CMUNewsItem {
  id: string;
  title: string;
  description?: string;
  url: string;
  source: DataSource;
  sourceLabel: string;
  publishedAt: Date;
  category?: CMUCategory;
}

export interface ResearchPublication {
  id: string;
  title: string;
  author?: string;
  organization: DataSource;
  organizationLabel: string;
  publishedAt: string;
  url: string;
  abstract?: string;
  iconColor: 'primary' | 'accent' | 'secondary' | 'destructive';
}

export interface QuickStat {
  label: string;
  value: string;
  color?: 'default' | 'destructive' | 'accent';
  sources: DataSource[];
}

// Data source metadata
export const DATA_SOURCE_LABELS: Record<DataSource, string> = {
  european_commission: 'EC',
  eur_lex: 'EUR-Lex',
  ecb: 'ECB',
  esma: 'ESMA',
  eba: 'EBA',
  eiopa: 'EIOPA',
  eprs: 'EPRS',
  jrc: 'JRC',
  eib: 'EIB',
  eif: 'EIF',
  eca: 'ECA',
  bruegel: 'Bruegel',
  letta_report: 'Letta',
  draghi_report: 'Draghi',
  afme: 'AFME',
  imf: 'IMF',
  eurostat: 'Eurostat',
  sifted: 'Sifted',
  invest_europe: 'Invest EU',
  dealroom: 'Dealroom',
  pitchbook: 'PitchBook',
  web_search: 'Web',
};

export const DATA_SOURCE_FULL_NAMES: Record<DataSource, string> = {
  european_commission: 'European Commission',
  eur_lex: 'EUR-Lex',
  ecb: 'European Central Bank',
  esma: 'ESMA',
  eba: 'EBA',
  eiopa: 'EIOPA',
  eprs: 'EP Research Service',
  jrc: 'Joint Research Centre',
  eib: 'European Investment Bank',
  eif: 'European Investment Fund',
  eca: 'Court of Auditors',
  bruegel: 'Bruegel',
  letta_report: 'Letta Report',
  draghi_report: 'Draghi Report',
  afme: 'AFME',
  imf: 'International Monetary Fund',
  eurostat: 'Eurostat',
  sifted: 'Sifted',
  invest_europe: 'Invest Europe',
  dealroom: 'Dealroom',
  pitchbook: 'PitchBook',
  web_search: 'Web Search',
};

export const DATA_SOURCE_TYPES: Record<DataSource, string> = {
  european_commission: 'Policy & Strategy',
  eur_lex: 'Legislation',
  ecb: 'Statistics',
  esma: 'Markets',
  eba: 'Banking',
  eiopa: 'Insurance',
  eprs: 'Research',
  jrc: 'Analysis',
  eib: 'Investment',
  eif: 'Investment',
  eca: 'Audit',
  bruegel: 'Think Tank',
  letta_report: 'Strategy',
  draghi_report: 'Strategy',
  afme: 'Industry',
  imf: 'Research',
  eurostat: 'Statistics',
  sifted: 'News',
  invest_europe: 'Industry',
  dealroom: 'Data',
  pitchbook: 'Data',
  web_search: 'News',
};

export const CMU_CATEGORY_LABELS: Record<CMUCategory, string> = {
  market_infrastructure: 'Infrastructure',
  investment_funds: 'Funds',
  transparency: 'Transparency',
  retail: 'Retail',
  supervision: 'Supervision',
  securitization: 'Securitization',
  taxation: 'Taxation',
  company_law: 'Company Law',
};
