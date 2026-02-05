import type {
  GoldMetrics,
  GoldETF,
  TokenizedGold,
  CentralBankReserves,
  GoldProducer,
  GoldRegulation,
  GoldDataSource,
} from '@/types/gold';

export const GOLD_METRICS: GoldMetrics = {
  xauUsd: 4665,
  xauEur: 4490,
  xauUsdYtd: '+2.8%',
  xauEurYtd: '+3.1%',
  globalEtfAum: '$890B',
  etfHoldings: '4,180 tonnes',
  centralBankBuying: 1037,
  centralBankYear: 2025,
  globalDemand: '5,120 tonnes',
  mineProduction: '3,720 tonnes',
  tokenisedGoldCap: '$7.52B',
  comexOpenInterest: '~520K contracts',
  allTimeHigh: 4690.02,
  allTimeHighDate: 'Jan 19, 2026',
};

export const GOLD_ETFS: GoldETF[] = [
  {
    name: 'SPDR Gold Shares',
    ticker: 'GLD',
    aum: '$134.0B',
    ter: '0.40%',
    ytdReturn: '+65.2%',
    exchange: 'NYSE',
    region: 'us',
  },
  {
    name: 'iShares Gold Trust',
    ticker: 'IAU',
    aum: '$112.0B',
    ter: '0.25%',
    ytdReturn: '+65.4%',
    exchange: 'NYSE',
    region: 'us',
  },
  {
    name: 'Xetra-Gold',
    ticker: '4GLD',
    aum: '€38.2B',
    ter: '0.00%',
    ytdReturn: '+68.1%',
    exchange: 'XETRA',
    region: 'eu',
  },
  {
    name: 'Xtrackers Physical Gold',
    ticker: 'XGDU',
    aum: '€6.5B',
    ter: '0.11%',
    ytdReturn: '+67.8%',
    exchange: 'XETRA',
    region: 'eu',
  },
  {
    name: 'iShares Physical Gold',
    ticker: 'PPFB',
    aum: '€26.2B',
    ter: '0.12%',
    ytdReturn: '+67.9%',
    exchange: 'LSE/XETRA',
    region: 'eu',
  },
];

export const TOKENIZED_GOLD: TokenizedGold[] = [
  {
    symbol: 'PAXG',
    name: 'PAX Gold',
    issuer: 'Paxos Trust Company',
    price: 4662,
    change: '+0.18%',
    marketCap: '$2.78B',
    volume24h: '$28.4M',
    marketShare: '37%',
  },
  {
    symbol: 'XAUT',
    name: 'Tether Gold',
    issuer: 'TG Commodities Ltd',
    price: 4658,
    change: '+0.15%',
    marketCap: '$4.28B',
    volume24h: '$18.7M',
    marketShare: '57%',
  },
];

export const CENTRAL_BANK_RESERVES: CentralBankReserves[] = [
  { iso: 'US', name: 'United States', reserves: 8134, rank: 1 },
  { iso: 'DE', name: 'Germany', reserves: 3352, rank: 2 },
  { iso: 'IT', name: 'Italy', reserves: 2452, rank: 3 },
  { iso: 'FR', name: 'France', reserves: 2437, rank: 4 },
  { iso: 'RU', name: 'Russia', reserves: 2333, rank: 5 },
  { iso: 'CN', name: 'China', reserves: 2304, rank: 6 },
  { iso: 'CH', name: 'Switzerland', reserves: 1040, rank: 7 },
  { iso: 'IN', name: 'India', reserves: 880, rank: 8 },
  { iso: 'JP', name: 'Japan', reserves: 846, rank: 9 },
  { iso: 'NL', name: 'Netherlands', reserves: 613, rank: 10 },
  { iso: 'TR', name: 'Turkey', reserves: 550, rank: 11 },
  { iso: 'PL', name: 'Poland', reserves: 472, rank: 12 },
  { iso: 'TW', name: 'Taiwan', reserves: 424, rank: 13 },
  { iso: 'PT', name: 'Portugal', reserves: 383, rank: 14 },
  { iso: 'KZ', name: 'Kazakhstan', reserves: 344, rank: 15 },
  { iso: 'SA', name: 'Saudi Arabia', reserves: 323, rank: 16 },
  { iso: 'GB', name: 'United Kingdom', reserves: 310, rank: 17 },
  { iso: 'ES', name: 'Spain', reserves: 282, rank: 18 },
  { iso: 'AT', name: 'Austria', reserves: 280, rank: 19 },
  { iso: 'BE', name: 'Belgium', reserves: 227, rank: 20 },
];

export const GOLD_PRODUCERS: GoldProducer[] = [
  { rank: 1, country: 'China', production: 380, share: '11.5%' },
  { rank: 2, country: 'Russia', production: 310, share: '9.4%' },
  { rank: 3, country: 'Australia', production: 290, share: '8.8%' },
  { rank: 4, country: 'Canada', production: 202, share: '6.1%', change: '+98% decade' },
  { rank: 5, country: 'United States', production: 160, share: '4.8%', change: '-6% YoY' },
];

export const GOLD_REGULATIONS: GoldRegulation[] = [
  {
    id: 'mifid2',
    title: 'MiFID II',
    description: 'Investment services directive covering gold ETFs and futures trading',
    status: 'in_force',
    url: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex%3A32014L0065',
  },
  {
    id: 'mica',
    title: 'MiCA Regulation',
    description: 'Crypto-asset regulation covering tokenised gold (PAXG, XAUT)',
    status: 'in_force',
    url: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32023R1114',
  },
  {
    id: 'afm-casp',
    title: 'AFM CASP Deadline',
    description: 'Dutch transitional period for crypto-asset service providers ended',
    status: 'in_force',
    deadline: '30 June 2025',
    url: 'https://www.afm.nl/en/sector/themas/cryptos',
  },
  {
    id: 'esma-guidance',
    title: 'ESMA Information-Only Test',
    description: '5-test framework determining when tracking tools require licensing',
    status: 'guidance',
    url: 'https://www.esma.europa.eu/sites/default/files/library/esma35-43-3448_supervisory_briefing_on_the_supervision_of_investment_services_firms.pdf',
  },
];

export const GOLD_DATA_SOURCES: GoldDataSource[] = [
  { name: 'LBMA', description: 'Price Benchmark', url: 'https://www.lbma.org.uk/' },
  { name: 'WGC', description: 'Gold Council', url: 'https://www.gold.org/goldhub' },
  { name: 'CME', description: 'COMEX Futures', url: 'https://www.cmegroup.com/' },
  { name: 'Metals-API', description: 'Spot Prices', url: 'https://metals-api.com/' },
  { name: 'CoinGecko', description: 'Tokenized Gold', url: 'https://www.coingecko.com/' },
  { name: 'EUR-Lex', description: 'EU Law', url: 'https://eur-lex.europa.eu/' },
  { name: 'AFM', description: 'Dutch Regulator', url: 'https://www.afm.nl/' },
  { name: 'ESMA', description: 'EU Regulator', url: 'https://www.esma.europa.eu/' },
];

export const CHART_DATA: Record<string, { open: string; high: string; low: string; prev: string }> = {
  '1D': { open: '$4,595', high: '$4,691', low: '$4,595', prev: '$4,595' },
  '1W': { open: '$4,520', high: '$4,691', low: '$4,480', prev: '$4,515' },
  '1M': { open: '$4,540', high: '$4,691', low: '$4,420', prev: '$4,535' },
  '1Y': { open: '$2,716', high: '$4,691', low: '$2,689', prev: '$2,711' },
  '5Y': { open: '$1,850', high: '$4,691', low: '$1,680', prev: '$1,845' },
};
