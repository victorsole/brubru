// Tariff & Trade War Monitor Types

export interface CountryTariffData {
  countryCode: string;
  countryName: string;
  region: 'EU' | 'North America' | 'Asia' | 'South America' | 'Africa' | 'Oceania' | 'Middle East';
  // Tariffs imposed BY each major power
  usTariffRate: number; // US tariff on this country
  euTariffRate: number; // EU tariff on this country
  chinaTariffRate: number; // China tariff on this country
  // Tariffs imposed ON each major power (retaliation)
  tariffOnUS?: number; // This country's tariff on US
  tariffOnEU?: number; // This country's tariff on EU
  tariffOnChina?: number; // This country's tariff on China
  // Trade volume (billions USD)
  tradeWithUS?: number;
  tradeWithEU?: number;
  tradeWithChina?: number;
  // Status
  status: 'Normal' | 'FTA' | 'Trade War' | 'Sanctions' | 'Negotiating';
  notes?: string;
}

export interface TariffTimelineEvent {
  id: string;
  date: Date;
  actor: 'US' | 'EU' | 'China' | 'Other';
  target: string;
  action: 'Tariff Increase' | 'Tariff Decrease' | 'Retaliation' | 'Agreement' | 'Threat' | 'Suspension';
  rate?: number;
  previousRate?: number;
  description: string;
  source: string;
  sourceUrl?: string;
}

export interface SectorTariff {
  sector: string;
  hsCode?: string;
  usTariff: number;
  euTariff: number;
  chinaTariff: number;
  tradingVolume: number; // billions USD
  affected: 'High' | 'Medium' | 'Low';
}

export interface TradeWarMetrics {
  // US Metrics
  usAvgTariffApplied: number;
  usTariffRevenue: number; // billions USD
  usRetaliationFaced: number; // billions USD worth of goods
  // EU Metrics
  euAvgTariffApplied: number;
  euCountermeasuresValue: number; // billions EUR
  euGoodsAffected: number; // billions EUR
  // China Metrics
  chinaAvgTariffApplied: number;
  chinaRetaliationValue: number; // billions USD
  chinaTradeSurplus: number; // billions USD
  // Global Impact
  globalTradeDecline: number; // percentage
  wtoDisputesFiled: number;
  lastUpdated: Date;
}

export interface TradeAgreement {
  id: string;
  name: string;
  parties: string[];
  status: 'In Force' | 'Negotiating' | 'Suspended' | 'Terminated';
  dateEntered?: Date;
  keyProvisions: string[];
  tariffElimination: number; // percentage of tariff lines
}

export interface TradeNewsItem {
  id: string;
  title: string;
  link: string;
  pubDate: Date;
  source: string;
  category: 'US-EU' | 'US-China' | 'EU-China' | 'WTO' | 'General';
  description?: string;
}

export interface TariffTrendData {
  year: number;
  month?: number;
  usAvgTariff: number;
  euAvgTariff: number;
  chinaAvgTariff: number;
  globalTradeVolume: number; // trillions USD
}

// Key countries and regions for mapping
export const MAJOR_TRADING_PARTNERS = [
  // G7
  { code: 'US', name: 'United States', region: 'North America' as const },
  { code: 'CA', name: 'Canada', region: 'North America' as const },
  { code: 'MX', name: 'Mexico', region: 'North America' as const },
  { code: 'JP', name: 'Japan', region: 'Asia' as const },
  { code: 'GB', name: 'United Kingdom', region: 'EU' as const },
  // EU27
  { code: 'DE', name: 'Germany', region: 'EU' as const },
  { code: 'FR', name: 'France', region: 'EU' as const },
  { code: 'IT', name: 'Italy', region: 'EU' as const },
  { code: 'ES', name: 'Spain', region: 'EU' as const },
  { code: 'NL', name: 'Netherlands', region: 'EU' as const },
  { code: 'BE', name: 'Belgium', region: 'EU' as const },
  { code: 'PL', name: 'Poland', region: 'EU' as const },
  { code: 'SE', name: 'Sweden', region: 'EU' as const },
  { code: 'AT', name: 'Austria', region: 'EU' as const },
  { code: 'IE', name: 'Ireland', region: 'EU' as const },
  // Asia
  { code: 'CN', name: 'China', region: 'Asia' as const },
  { code: 'KR', name: 'South Korea', region: 'Asia' as const },
  { code: 'TW', name: 'Taiwan', region: 'Asia' as const },
  { code: 'IN', name: 'India', region: 'Asia' as const },
  { code: 'VN', name: 'Vietnam', region: 'Asia' as const },
  { code: 'ID', name: 'Indonesia', region: 'Asia' as const },
  { code: 'TH', name: 'Thailand', region: 'Asia' as const },
  { code: 'MY', name: 'Malaysia', region: 'Asia' as const },
  { code: 'SG', name: 'Singapore', region: 'Asia' as const },
  { code: 'PH', name: 'Philippines', region: 'Asia' as const },
  // South America
  { code: 'BR', name: 'Brazil', region: 'South America' as const },
  { code: 'AR', name: 'Argentina', region: 'South America' as const },
  { code: 'CL', name: 'Chile', region: 'South America' as const },
  { code: 'CO', name: 'Colombia', region: 'South America' as const },
  // Middle East
  { code: 'SA', name: 'Saudi Arabia', region: 'Middle East' as const },
  { code: 'AE', name: 'UAE', region: 'Middle East' as const },
  { code: 'IL', name: 'Israel', region: 'Middle East' as const },
  { code: 'TR', name: 'Turkey', region: 'Middle East' as const },
  // Africa
  { code: 'ZA', name: 'South Africa', region: 'Africa' as const },
  { code: 'EG', name: 'Egypt', region: 'Africa' as const },
  { code: 'NG', name: 'Nigeria', region: 'Africa' as const },
  // Oceania
  { code: 'AU', name: 'Australia', region: 'Oceania' as const },
  { code: 'NZ', name: 'New Zealand', region: 'Oceania' as const },
  // Russia
  { code: 'RU', name: 'Russia', region: 'Asia' as const },
];

// Data source types for attribution
export enum TariffDataSource {
  USTR = 'USTR',
  EC_TRADE = 'EC Trade',
  EUROSTAT = 'Eurostat',
  WTO = 'WTO',
  UNCTAD = 'UNCTAD',
  IMF = 'IMF',
  WORLD_BANK = 'World Bank',
  TARIC = 'TARIC',
  CHINA_CUSTOMS = 'China Customs',
  USITC = 'USITC',
  REUTERS = 'Reuters',
  POLITICO = 'Politico',
}

export const DATA_SOURCE_URLS: Record<TariffDataSource, string> = {
  [TariffDataSource.USTR]: 'https://ustr.gov/',
  [TariffDataSource.EC_TRADE]: 'https://policy.trade.ec.europa.eu/',
  [TariffDataSource.EUROSTAT]: 'https://ec.europa.eu/eurostat',
  [TariffDataSource.WTO]: 'https://www.wto.org/english/tratop_e/tariffs_e/tariff_data_e.htm',
  [TariffDataSource.UNCTAD]: 'https://unctad.org/',
  [TariffDataSource.IMF]: 'https://www.imf.org/',
  [TariffDataSource.WORLD_BANK]: 'https://data.worldbank.org/',
  [TariffDataSource.TARIC]: 'https://taxation-customs.ec.europa.eu/customs/calculation-customs-duties/customs-tariff/eu-customs-tariff-taric_en',
  [TariffDataSource.CHINA_CUSTOMS]: 'http://english.customs.gov.cn/',
  [TariffDataSource.USITC]: 'https://www.usitc.gov/',
  [TariffDataSource.REUTERS]: 'https://www.reuters.com/',
  [TariffDataSource.POLITICO]: 'https://www.politico.eu/',
};
