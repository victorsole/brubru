// Gold Trading Monitor Types

export interface GoldSpotPrice {
  symbol: string;
  price: number;
  currency: string;
  change: number;
  changePercent: number;
  ytdChange: string;
  source: string;
}

export interface GoldETF {
  name: string;
  ticker: string;
  aum: string;
  ter: string;
  ytdReturn: string;
  exchange: string;
  region: 'eu' | 'us';
}

export interface TokenizedGold {
  symbol: string;
  name: string;
  issuer: string;
  price: number;
  change: string;
  marketCap: string;
  volume24h: string;
  marketShare: string;
}

export interface CentralBankReserves {
  iso: string;
  name: string;
  reserves: number;
  rank: number;
}

export interface GoldProducer {
  rank: number;
  country: string;
  production: number;
  share: string;
  change?: string;
}

export interface GoldRegulation {
  id: string;
  title: string;
  description: string;
  status: 'in_force' | 'upcoming' | 'guidance';
  deadline?: string;
  url?: string;
}

export interface GoldMetrics {
  xauUsd: number;
  xauEur: number;
  xauUsdYtd: string;
  xauEurYtd: string;
  globalEtfAum: string;
  etfHoldings: string;
  centralBankBuying: number;
  centralBankYear: number;
  globalDemand: string;
  mineProduction: string;
  tokenisedGoldCap: string;
  comexOpenInterest: string;
  allTimeHigh: number;
  allTimeHighDate: string;
}

export interface GoldDataSource {
  name: string;
  description: string;
  url: string;
}

export type ChartTimeframe = '1D' | '1W' | '1M' | '1Y' | '5Y';
export type ETFFilter = 'all' | 'eu' | 'us';
