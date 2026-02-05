// Startup Monitor Types

export type LegislationStatus = 'in_force' | 'proposed' | 'upcoming' | 'rumoured';

export interface CountryStartupData {
  iso: string;
  name: string;
  unicorns: number;
  funding2024: string;
  globalRank: number;
  keyHubs: string[];
  startupCount?: number;
  ecosystemValue?: string;
}

export interface StartupLegislation {
  id: string;
  title: string;
  description: string;
  status: LegislationStatus;
  timeline: string;
  url?: string;
}

export interface EUFundingProgram {
  name: string;
  description: string;
  totalBudget: string;
  subPrograms?: { name: string; budget: string }[];
  stats?: { label: string; value: string }[];
}

export interface FundingComparison {
  metric: string;
  euValue: string;
  usValue: string;
  gap: string;
  percentage: number;
}

export interface StartupMetrics {
  ecosystemValue: string;
  activeUnicorns: number;
  newUnicorns2025: number;
  vcFunding2024: string;
  vcFundingChange: string;
  activeStartups: string;
  newFounders2025: string;
  techGdpShare: string;
  deeptechShare: string;
  defenceTech2025: string;
  defenceTechChange: string;
  euIpoMedian: string;
  usIpoMedian: string;
  singleMarketTariff: string;
}

export interface DataSource {
  name: string;
  description: string;
  url: string;
}

export type MapMetric = 'unicorns' | 'funding' | 'rank';
