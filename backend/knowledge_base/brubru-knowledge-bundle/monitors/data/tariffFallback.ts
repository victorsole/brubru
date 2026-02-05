// Tariff & Trade War Monitor - Fallback Data
// Based on real 2025/2026 tariff rates from Yale Budget Lab, USTR, EC Trade, WTO, and official sources
// Last updated: January 2026

import {
  CountryTariffData,
  TariffTimelineEvent,
  SectorTariff,
  TradeWarMetrics,
  TradeNewsItem,
  TariffTrendData,
} from '@/types/tariff';

// ============================================================================
// COUNTRY TARIFF DATA - Real 2025 Rates
// Sources: USTR, EC Access2Markets, WTO, China Customs
// ============================================================================

export const FALLBACK_COUNTRY_TARIFFS: CountryTariffData[] = [
  // === MAJOR ECONOMIES ===
  {
    countryCode: 'CN',
    countryName: 'China',
    region: 'Asia',
    usTariffRate: 10, // Trump-Xi Busan truce (Oct 2025) - extended to Nov 2026
    euTariffRate: 9.8, // EU MFN + EV tariffs (up to 45.3% on EVs)
    chinaTariffRate: 0, // Self
    tariffOnUS: 10, // China matching 10% truce rate
    tariffOnEU: 7.4, // China's MFN rate on EU
    tradeWithUS: 582,
    tradeWithEU: 739,
    status: 'Negotiating',
    notes: 'Trump-Xi truce: 10% rate until Nov 2026. Peak was 145% in April 2025. Rare earth controls partially suspended.',
  },
  {
    countryCode: 'US',
    countryName: 'United States',
    region: 'North America',
    usTariffRate: 0, // Self
    euTariffRate: 15, // EU-US August 2025 deal
    chinaTariffRate: 31.9, // China's retaliatory tariffs
    tariffOnEU: 15, // US tariff on EU (August 2025 deal)
    tariffOnChina: 47.5,
    tradeWithEU: 892,
    tradeWithChina: 582,
    status: 'Negotiating',
    notes: 'August 2025 EU-US deal set 15% ceiling on most goods.',
  },
  {
    countryCode: 'JP',
    countryName: 'Japan',
    region: 'Asia',
    usTariffRate: 15, // US-Japan bilateral deal
    euTariffRate: 0, // EU-Japan EPA (2019)
    chinaTariffRate: 8.2,
    tariffOnUS: 4.2,
    tariffOnEU: 0,
    tradeWithUS: 218,
    tradeWithEU: 175,
    status: 'FTA',
    notes: 'US-Japan deal reduced tariffs to 15%. EU-Japan EPA in force since 2019.',
  },
  {
    countryCode: 'GB',
    countryName: 'United Kingdom',
    region: 'EU',
    usTariffRate: 10, // US-UK bilateral deal (with quota for autos)
    euTariffRate: 0, // UK-EU TCA (zero tariffs on rules-of-origin goods)
    chinaTariffRate: 7.8,
    tariffOnUS: 4.1,
    tariffOnEU: 0,
    tradeWithUS: 147,
    tradeWithEU: 426,
    status: 'FTA',
    notes: 'US-UK deal: 10% on autos up to 100k units, 25% above quota. 50% on steel/aluminum.',
  },
  {
    countryCode: 'CA',
    countryName: 'Canada',
    region: 'North America',
    usTariffRate: 5, // USMCA-compliant goods largely exempt, 35% on non-compliant
    euTariffRate: 0, // CETA in force
    chinaTariffRate: 6.8,
    tariffOnUS: 25, // Canadian retaliation (reduced)
    tariffOnEU: 0,
    tradeWithUS: 752,
    tradeWithEU: 98,
    status: 'FTA',
    notes: 'USMCA-compliant goods (85-95%) duty-free. 35% on non-USMCA goods. 50% on steel/aluminum.',
  },
  {
    countryCode: 'MX',
    countryName: 'Mexico',
    region: 'North America',
    usTariffRate: 5, // USMCA-compliant exempt, others 25%
    euTariffRate: 0, // EU-Mexico FTA (modernized 2020)
    chinaTariffRate: 7.2,
    tariffOnUS: 20,
    tariffOnEU: 0,
    tradeWithUS: 807,
    tradeWithEU: 76,
    status: 'FTA',
    notes: 'USMCA-compliant goods exempt. Mexico granted 90-day extension on increases.',
  },
  {
    countryCode: 'KR',
    countryName: 'South Korea',
    region: 'Asia',
    usTariffRate: 10, // Baseline reciprocal tariff
    euTariffRate: 0, // EU-Korea FTA (2011)
    chinaTariffRate: 8.5,
    tariffOnUS: 13.5,
    tariffOnEU: 0,
    tradeWithUS: 186,
    tradeWithEU: 132,
    status: 'Negotiating',
    notes: 'US-Korea FTA modified. Preliminary agreement reached July 2025.',
  },
  {
    countryCode: 'IN',
    countryName: 'India',
    region: 'Asia',
    usTariffRate: 50, // Highest reciprocal rate
    euTariffRate: 11.2, // EU GSP rates
    chinaTariffRate: 9.8,
    tariffOnUS: 18.3,
    tariffOnEU: 17.5,
    tradeWithUS: 128,
    tradeWithEU: 120,
    status: 'Trade War',
    notes: 'Highest US tariff rate along with Brazil. No FTA with EU (negotiations ongoing).',
  },
  {
    countryCode: 'BR',
    countryName: 'Brazil',
    region: 'South America',
    usTariffRate: 50, // Highest reciprocal rate
    euTariffRate: 10.8, // EU-Mercosur pending ratification
    chinaTariffRate: 8.2,
    tariffOnUS: 14.2,
    tariffOnEU: 12.5,
    tradeWithUS: 92,
    tradeWithEU: 86,
    status: 'Trade War',
    notes: 'Highest US tariff rate. EU-Mercosur FTA signed Dec 2024, pending ratification.',
  },
  {
    countryCode: 'VN',
    countryName: 'Vietnam',
    region: 'Asia',
    usTariffRate: 10, // Reduced from original 46% proposal
    euTariffRate: 0, // EU-Vietnam FTA (2020)
    chinaTariffRate: 5.2,
    tariffOnUS: 9.8,
    tariffOnEU: 0,
    tradeWithUS: 123,
    tradeWithEU: 58,
    status: 'Negotiating',
    notes: 'Preliminary US-Vietnam agreement reached July 2025.',
  },
  {
    countryCode: 'ID',
    countryName: 'Indonesia',
    region: 'Asia',
    usTariffRate: 10, // Baseline rate after preliminary agreement
    euTariffRate: 9.5, // EU GSP rates (CEPA negotiations)
    chinaTariffRate: 6.8,
    tariffOnUS: 8.5,
    tariffOnEU: 8.2,
    tradeWithUS: 38,
    tradeWithEU: 32,
    status: 'Negotiating',
    notes: 'Preliminary US-Indonesia agreement July 2025. EU-Indonesia CEPA under negotiation.',
  },
  {
    countryCode: 'TW',
    countryName: 'Taiwan',
    region: 'Asia',
    usTariffRate: 10, // Baseline reciprocal
    euTariffRate: 4.2, // MFN rates
    chinaTariffRate: 25, // ECFA suspended provisions
    tariffOnUS: 6.5,
    tariffOnEU: 5.8,
    tradeWithUS: 115,
    tradeWithEU: 52,
    status: 'Normal',
    notes: 'Key semiconductor supplier. CHIPS Act investments ongoing.',
  },
  {
    countryCode: 'TH',
    countryName: 'Thailand',
    region: 'Asia',
    usTariffRate: 10, // Baseline
    euTariffRate: 9.8, // GSP+
    chinaTariffRate: 5.5,
    tariffOnUS: 11.2,
    tariffOnEU: 9.5,
    tradeWithUS: 58,
    tradeWithEU: 42,
    status: 'Normal',
    notes: 'EU-Thailand FTA negotiations resumed 2024.',
  },
  {
    countryCode: 'SG',
    countryName: 'Singapore',
    region: 'Asia',
    usTariffRate: 10, // US-Singapore FTA grandfathered
    euTariffRate: 0, // EU-Singapore FTA (2019)
    chinaTariffRate: 0, // CSFTA
    tariffOnUS: 0,
    tariffOnEU: 0,
    tradeWithUS: 78,
    tradeWithEU: 85,
    status: 'FTA',
    notes: 'Major transshipment hub. FTAs with US, EU, China.',
  },
  {
    countryCode: 'AU',
    countryName: 'Australia',
    region: 'Oceania',
    usTariffRate: 10, // Baseline (AUSFTA applies)
    euTariffRate: 0, // EU-Australia FTA (entered force 2024)
    chinaTariffRate: 15, // Trade tensions ongoing
    tariffOnUS: 2.8,
    tariffOnEU: 0,
    tradeWithUS: 48,
    tradeWithEU: 62,
    status: 'FTA',
    notes: 'EU-Australia FTA in force since 2024. China wine tariffs dispute.',
  },
  {
    countryCode: 'NZ',
    countryName: 'New Zealand',
    region: 'Oceania',
    usTariffRate: 10, // Baseline
    euTariffRate: 0, // EU-NZ FTA (2024)
    chinaTariffRate: 4.5,
    tariffOnUS: 3.2,
    tariffOnEU: 0,
    tradeWithUS: 15,
    tradeWithEU: 12,
    status: 'FTA',
    notes: 'EU-New Zealand FTA entered force 2024.',
  },
  {
    countryCode: 'CH',
    countryName: 'Switzerland',
    region: 'EU',
    usTariffRate: 10, // Baseline
    euTariffRate: 0, // Bilateral agreements
    chinaTariffRate: 6.5,
    tariffOnUS: 4.2,
    tariffOnEU: 0,
    tradeWithUS: 78,
    tradeWithEU: 324,
    status: 'FTA',
    notes: 'Part of EFTA. Extensive bilateral agreements with EU.',
  },
  {
    countryCode: 'TR',
    countryName: 'Turkey',
    region: 'Middle East',
    usTariffRate: 10, // Baseline
    euTariffRate: 0, // Customs Union (1995)
    chinaTariffRate: 8.2,
    tariffOnUS: 12.5,
    tariffOnEU: 0,
    tradeWithUS: 32,
    tradeWithEU: 198,
    status: 'FTA',
    notes: 'EU-Turkey Customs Union. Modernization negotiations stalled.',
  },
  {
    countryCode: 'SA',
    countryName: 'Saudi Arabia',
    region: 'Middle East',
    usTariffRate: 10, // Baseline
    euTariffRate: 4.8, // MFN rates
    chinaTariffRate: 5.2,
    tariffOnUS: 5.5,
    tariffOnEU: 5.5,
    tradeWithUS: 42,
    tradeWithEU: 52,
    status: 'Normal',
    notes: 'Major oil exporter. GCC-EU FTA negotiations ongoing.',
  },
  {
    countryCode: 'IL',
    countryName: 'Israel',
    region: 'Middle East',
    usTariffRate: 0, // US-Israel FTA (1985)
    euTariffRate: 0, // EU-Israel Association Agreement
    chinaTariffRate: 7.8,
    tariffOnUS: 0,
    tariffOnEU: 0,
    tradeWithUS: 52,
    tradeWithEU: 48,
    status: 'FTA',
    notes: 'Longstanding FTAs with both US and EU.',
  },
  {
    countryCode: 'ZA',
    countryName: 'South Africa',
    region: 'Africa',
    usTariffRate: 10, // Baseline (AGOA applies)
    euTariffRate: 0, // EU-SADC EPA
    chinaTariffRate: 6.5,
    tariffOnUS: 8.2,
    tariffOnEU: 0,
    tradeWithUS: 18,
    tradeWithEU: 52,
    status: 'FTA',
    notes: 'AGOA beneficiary. EU-SADC EPA in force.',
  },
  {
    countryCode: 'RU',
    countryName: 'Russia',
    region: 'Asia',
    usTariffRate: 35, // Sanctions-related
    euTariffRate: 35, // Sanctions + suspended MFN
    chinaTariffRate: 5.5,
    tariffOnUS: 35,
    tariffOnEU: 35,
    tradeWithUS: 5, // Severely restricted
    tradeWithEU: 45, // Down from 280 pre-2022
    status: 'Sanctions',
    notes: 'MFN suspended by US, EU, UK. Comprehensive sanctions in place since 2022.',
  },
];

// ============================================================================
// EU27 MFN TARIFF RATES - For EU tariff map
// Source: TARIC Database, EC Access2Markets (2025)
// ============================================================================

export const EU_MFN_TARIFFS: Record<string, { mfnRate: number; weightedAvg: number; agricultural: number; industrial: number }> = {
  // EU average MFN: 5.1% (simple), 2.7% (trade-weighted)
  US: { mfnRate: 15, weightedAvg: 15, agricultural: 12.8, industrial: 15 }, // Post-August 2025 deal
  CN: { mfnRate: 9.8, weightedAvg: 9.8, agricultural: 14.2, industrial: 8.5 }, // + EV tariffs up to 45.3%
  JP: { mfnRate: 0, weightedAvg: 0, agricultural: 0, industrial: 0 }, // EU-Japan EPA
  GB: { mfnRate: 0, weightedAvg: 0, agricultural: 0, industrial: 0 }, // TCA
  CH: { mfnRate: 0, weightedAvg: 0, agricultural: 2.5, industrial: 0 }, // EFTA
  NO: { mfnRate: 0, weightedAvg: 0, agricultural: 3.2, industrial: 0 }, // EEA
  KR: { mfnRate: 0, weightedAvg: 0, agricultural: 0, industrial: 0 }, // EU-Korea FTA
  CA: { mfnRate: 0, weightedAvg: 0, agricultural: 0, industrial: 0 }, // CETA
  MX: { mfnRate: 0, weightedAvg: 0, agricultural: 0, industrial: 0 }, // EU-Mexico
  SG: { mfnRate: 0, weightedAvg: 0, agricultural: 0, industrial: 0 }, // EU-Singapore
  VN: { mfnRate: 0, weightedAvg: 0, agricultural: 0, industrial: 0 }, // EVFTA
  AU: { mfnRate: 0, weightedAvg: 0, agricultural: 0, industrial: 0 }, // EU-Australia FTA (2024)
  NZ: { mfnRate: 0, weightedAvg: 0, agricultural: 0, industrial: 0 }, // EU-NZ FTA (2024)
  IN: { mfnRate: 11.2, weightedAvg: 9.8, agricultural: 15.2, industrial: 8.5 }, // GSP, FTA negotiating
  BR: { mfnRate: 10.8, weightedAvg: 8.5, agricultural: 14.5, industrial: 7.2 }, // Mercosur pending
  RU: { mfnRate: 35, weightedAvg: 35, agricultural: 35, industrial: 35 }, // Sanctions
  DEFAULT: { mfnRate: 5.1, weightedAvg: 2.7, agricultural: 12.2, industrial: 4.1 }, // EU average MFN
};

// ============================================================================
// US TARIFF RATES BY COUNTRY - For US tariff map
// Source: USTR, Tax Foundation, Congress.gov (January 2025)
// ============================================================================

export const US_TARIFF_RATES: Record<string, { rate: number; notes: string; sector?: Record<string, number> }> = {
  CN: {
    rate: 10,
    notes: 'Trump-Xi Busan truce (Oct 2025) - 10% rate extended until Nov 2026. Was 145% at peak.',
    sector: { steel: 25, aluminum: 25, electronics: 10, autos: 25, semiconductors: 10 }
  },
  EU: {
    rate: 15,
    notes: 'August 2025 deal. Single 15% ceiling across most sectors.',
    sector: { steel: 25, aluminum: 25, autos: 25, spirits: 25, other: 15 }
  },
  DE: { rate: 15, notes: 'EU member - 15% baseline' },
  FR: { rate: 15, notes: 'EU member - 15% baseline' },
  IT: { rate: 15, notes: 'EU member - 15% baseline' },
  ES: { rate: 15, notes: 'EU member - 15% baseline' },
  NL: { rate: 15, notes: 'EU member - 15% baseline' },
  BE: { rate: 15, notes: 'EU member - 15% baseline' },
  JP: {
    rate: 15,
    notes: 'US-Japan bilateral deal September 2025.',
    sector: { autos: 15, steel: 25, other: 15 }
  },
  GB: {
    rate: 10,
    notes: 'US-UK deal. 25% on steel/aluminum. Auto quota system.',
    sector: { steel: 50, aluminum: 50, autos: 10, autoQuotaExcess: 25 }
  },
  CA: {
    rate: 5,
    notes: 'USMCA-compliant exempt (85-95%). 35% on non-compliant.',
    sector: { nonUsmca: 35, steel: 50, aluminum: 50, energy: 10, potash: 10 }
  },
  MX: {
    rate: 5,
    notes: 'USMCA-compliant exempt. 90-day extension granted.',
    sector: { nonUsmca: 25, autos: 25 }
  },
  KR: {
    rate: 10,
    notes: 'Preliminary agreement July 2025.',
  },
  IN: {
    rate: 50,
    notes: 'Highest reciprocal rate. No bilateral agreement.',
  },
  BR: {
    rate: 50,
    notes: 'Highest reciprocal rate. No bilateral agreement.',
  },
  VN: {
    rate: 10,
    notes: 'Preliminary agreement July 2025. Reduced from 46% proposal.',
  },
  ID: {
    rate: 10,
    notes: 'Preliminary agreement July 2025.',
  },
  PH: {
    rate: 10,
    notes: 'Preliminary agreement July 2025.',
  },
  TW: {
    rate: 10,
    notes: 'Baseline reciprocal. Key semiconductor supplier.',
  },
  TH: { rate: 10, notes: 'Baseline reciprocal tariff.' },
  MY: { rate: 10, notes: 'Baseline reciprocal tariff.' },
  SG: { rate: 10, notes: 'US-Singapore FTA applies.' },
  AU: { rate: 10, notes: 'AUSFTA applies for most goods.' },
  NZ: { rate: 10, notes: 'Baseline reciprocal tariff.' },
  IL: { rate: 0, notes: 'US-Israel FTA (1985).' },
  RU: { rate: 35, notes: 'Sanctions. MFN suspended.' },
  DEFAULT: { rate: 10, notes: 'Baseline 10% reciprocal tariff on all imports.' },
};

// ============================================================================
// CHINA TARIFF RATES BY COUNTRY - For China tariff map
// Source: China Customs, WTO Tariff Profiles (2025)
// ============================================================================

export const CHINA_TARIFF_RATES: Record<string, { rate: number; notes: string }> = {
  US: {
    rate: 31.9,
    notes: 'Retaliatory tariffs. Agricultural products suspended May 2025.',
  },
  EU: {
    rate: 7.4,
    notes: 'MFN rates. Up to 42.7% on pork/dairy (retaliation for EV tariffs).',
  },
  DE: { rate: 7.4, notes: 'EU member - MFN rate' },
  FR: { rate: 7.4, notes: 'EU member - MFN rate' },
  IT: { rate: 7.4, notes: 'EU member - MFN rate' },
  ES: { rate: 7.4, notes: 'EU member - MFN rate' },
  JP: { rate: 8.2, notes: 'MFN rates apply.' },
  GB: { rate: 7.8, notes: 'MFN rates apply.' },
  KR: { rate: 8.5, notes: 'China-Korea FTA partial coverage.' },
  AU: { rate: 15, notes: 'Trade tensions. Wine, barley, coal restrictions.' },
  TW: { rate: 25, notes: 'ECFA suspended provisions. Political tensions.' },
  ASEAN: { rate: 0, notes: 'ASEAN-China FTA (ACFTA) - zero tariffs.' },
  VN: { rate: 5.2, notes: 'ACFTA rates.' },
  TH: { rate: 5.5, notes: 'ACFTA rates.' },
  SG: { rate: 0, notes: 'China-Singapore FTA.' },
  MY: { rate: 5.8, notes: 'ACFTA rates.' },
  ID: { rate: 6.8, notes: 'ACFTA rates.' },
  RU: { rate: 5.5, notes: 'Increased trade post-sanctions.' },
  DEFAULT: { rate: 7.4, notes: 'Average MFN rate.' },
};

// ============================================================================
// SECTOR-SPECIFIC TARIFFS - Key Industries
// Source: USTR, EC Trade, WTO
// ============================================================================

export const FALLBACK_SECTOR_TARIFFS: SectorTariff[] = [
  { sector: 'Automobiles', hsCode: '87', usTariff: 25, euTariff: 10, chinaTariff: 15, tradingVolume: 1420, affected: 'High' },
  { sector: 'Steel & Iron', hsCode: '72', usTariff: 25, euTariff: 25, chinaTariff: 8, tradingVolume: 185, affected: 'High' },
  { sector: 'Aluminum', hsCode: '76', usTariff: 25, euTariff: 25, chinaTariff: 6, tradingVolume: 78, affected: 'High' },
  { sector: 'Semiconductors', hsCode: '8542', usTariff: 47.5, euTariff: 0, chinaTariff: 0, tradingVolume: 580, affected: 'High' },
  { sector: 'Electric Vehicles', hsCode: '8703.80', usTariff: 100, euTariff: 45.3, chinaTariff: 15, tradingVolume: 125, affected: 'High' },
  { sector: 'Solar Panels', hsCode: '8541.40', usTariff: 47.5, euTariff: 0, chinaTariff: 5, tradingVolume: 42, affected: 'Medium' },
  { sector: 'Batteries', hsCode: '8507', usTariff: 47.5, euTariff: 0, chinaTariff: 6, tradingVolume: 68, affected: 'High' },
  { sector: 'Pharmaceuticals', hsCode: '30', usTariff: 15, euTariff: 0, chinaTariff: 4.5, tradingVolume: 215, affected: 'Medium' },
  { sector: 'Agricultural Machinery', hsCode: '84.32', usTariff: 15, euTariff: 0, chinaTariff: 8, tradingVolume: 32, affected: 'Low' },
  { sector: 'Whiskey/Spirits', hsCode: '2208', usTariff: 25, euTariff: 25, chinaTariff: 12, tradingVolume: 18, affected: 'Medium' },
  { sector: 'Wine', hsCode: '2204', usTariff: 15, euTariff: 0, chinaTariff: 42.7, tradingVolume: 12, affected: 'Medium' },
  { sector: 'Dairy Products', hsCode: '04', usTariff: 15, euTariff: 12.8, chinaTariff: 42.7, tradingVolume: 28, affected: 'High' },
  { sector: 'Pork', hsCode: '0203', usTariff: 10, euTariff: 0, chinaTariff: 42.7, tradingVolume: 15, affected: 'High' },
  { sector: 'Soybeans', hsCode: '1201', usTariff: 0, euTariff: 0, chinaTariff: 0, tradingVolume: 42, affected: 'Low' },
  { sector: 'Lumber', hsCode: '44', usTariff: 15, euTariff: 0, chinaTariff: 5, tradingVolume: 24, affected: 'Low' },
];

// ============================================================================
// TRADE WAR METRICS - Global Dashboard
// Sources: Yale Budget Lab, WTO, IMF, USTR, EC Trade (January 2026)
// ============================================================================

export const FALLBACK_TRADE_WAR_METRICS: TradeWarMetrics = {
  // US Metrics - Yale Budget Lab November 2025
  usAvgTariffApplied: 16.8, // Yale Budget Lab: highest since 1935 (14.4pp increase)
  usTariffRevenue: 250, // billions USD projected 2025-2035 avg annual ($2.5T over decade)
  usRetaliationFaced: 245, // billions USD worth of goods facing retaliation

  // EU Metrics
  euAvgTariffApplied: 1.8, // Trade-weighted MFN (2.8% with countermeasures)
  euCountermeasuresValue: 93, // billions EUR authorized
  euGoodsAffected: 72, // billions EUR of EU exports to US affected

  // China Metrics
  chinaAvgTariffApplied: 5.5, // Elevated due to retaliatory tariffs on US/EU
  chinaRetaliationValue: 125, // billions USD worth of US goods
  chinaTradeSurplus: 1000, // billions USD (2025, first time above $1T)

  // Global Impact
  globalTradeDecline: -2.8, // percentage YoY change
  wtoDisputesFiled: 47, // Active tariff-related disputes
  lastUpdated: new Date('2026-01-05'),
};

// ============================================================================
// TRADE WAR TIMELINE - Key Events 2024-2025
// Source: Reuters, Politico, USTR, EC Trade
// ============================================================================

export const FALLBACK_TIMELINE_EVENTS: TariffTimelineEvent[] = [
  {
    id: 'tw-1',
    date: new Date('2025-01-20'),
    actor: 'US',
    target: 'All Countries',
    action: 'Threat',
    description: 'Trump inauguration. Announces tariff policy review.',
    source: 'White House',
  },
  {
    id: 'tw-2',
    date: new Date('2025-02-01'),
    actor: 'US',
    target: 'China, Canada, Mexico',
    action: 'Tariff Increase',
    rate: 25,
    previousRate: 0,
    description: 'Executive orders: 25% on Canada/Mexico, 10% additional on China via IEEPA.',
    source: 'USTR',
  },
  {
    id: 'tw-3',
    date: new Date('2025-03-04'),
    actor: 'China',
    target: 'US',
    action: 'Retaliation',
    rate: 15,
    description: '15% on chicken, wheat, corn, cotton; 10% on soybeans, pork, beef.',
    source: 'China Customs',
  },
  {
    id: 'tw-4',
    date: new Date('2025-03-12'),
    actor: 'US',
    target: 'All',
    action: 'Tariff Increase',
    rate: 25,
    description: 'Steel and aluminum tariffs at 25% take effect globally.',
    source: 'USTR',
  },
  {
    id: 'tw-5',
    date: new Date('2025-04-02'),
    actor: 'US',
    target: 'Global',
    action: 'Tariff Increase',
    rate: 10,
    description: '"Liberation Day" tariffs: 10% baseline + country-specific reciprocal rates.',
    source: 'White House',
  },
  {
    id: 'tw-6',
    date: new Date('2025-04-09'),
    actor: 'EU',
    target: 'US',
    action: 'Retaliation',
    rate: 25,
    description: 'EU countermeasures: 25% on $21B of US imports approved.',
    source: 'EC Trade',
  },
  {
    id: 'tw-7',
    date: new Date('2025-04-12'),
    actor: 'US',
    target: 'China',
    action: 'Tariff Increase',
    rate: 145,
    previousRate: 104,
    description: 'Peak tariff escalation: US tariffs on China reach 145%.',
    source: 'USTR',
  },
  {
    id: 'tw-8',
    date: new Date('2025-04-12'),
    actor: 'China',
    target: 'US',
    action: 'Retaliation',
    rate: 125,
    description: 'China matches with 125% tariffs on US goods.',
    source: 'China Customs',
  },
  {
    id: 'tw-9',
    date: new Date('2025-05-14'),
    actor: 'US',
    target: 'China',
    action: 'Agreement',
    rate: 10,
    previousRate: 145,
    description: 'US-China tariff truce: Mutual reduction to 10% baseline.',
    source: 'White House',
  },
  {
    id: 'tw-10',
    date: new Date('2025-05-28'),
    actor: 'Other',
    target: 'US',
    action: 'Other',
    description: 'US Court of International Trade rules IEEPA tariffs illegal.',
    source: 'USCIT',
  },
  {
    id: 'tw-11',
    date: new Date('2025-07-12'),
    actor: 'EU',
    target: 'US',
    action: 'Threat',
    description: 'EU expands countermeasure list to EUR 93B following 30% tariff threat.',
    source: 'EC Trade',
  },
  {
    id: 'tw-12',
    date: new Date('2025-07-31'),
    actor: 'US',
    target: 'Multiple',
    action: 'Agreement',
    description: 'Preliminary deals with Indonesia, Vietnam, Philippines, Korea, UK.',
    source: 'USTR',
  },
  {
    id: 'tw-13',
    date: new Date('2025-08-21'),
    actor: 'EU',
    target: 'US',
    action: 'Agreement',
    rate: 15,
    description: 'EU-US framework: 15% ceiling on most goods. Spirits excluded.',
    source: 'EC Trade',
    sourceUrl: 'https://policy.trade.ec.europa.eu/news/joint-statement-united-states-european-union-framework-agreement-reciprocal-fair-and-balanced-trade-2025-08-21_en',
  },
  {
    id: 'tw-14',
    date: new Date('2025-11-10'),
    actor: 'US',
    target: 'China',
    action: 'Agreement',
    description: 'Trump-Xi meeting: 10% rate extended until November 2026.',
    source: 'White House',
    sourceUrl: 'https://www.whitehouse.gov/fact-sheets/2025/11/fact-sheet-president-donald-j-trump-strikes-deal-on-economic-and-trade-relations-with-china/',
  },
  {
    id: 'tw-15',
    date: new Date('2026-01-17'),
    actor: 'US',
    target: 'EU',
    action: 'Tariff Increase',
    rate: 10,
    description: 'Trump announces 10% tariffs on 8 European countries (DK, FI, FR, DE, NL, NO, SE, UK) starting Feb 1, 2026 over Greenland dispute. To increase to 25% on June 1.',
    source: 'White House',
    sourceUrl: 'https://www.nbcnews.com/business/economy/trump-denmark-european-tariffs-greenland-deal-rcna254551',
  },
  {
    id: 'tw-16',
    date: new Date('2026-01-18'),
    actor: 'EU',
    target: 'US',
    action: 'Threat',
    description: 'EU ambassadors hold emergency meeting; France requests activation of Anti-Coercion Instrument. €108B in retaliatory tariffs discussed.',
    source: 'Financial Times',
    sourceUrl: 'https://www.cnn.com/2026/01/18/business/europe-greenland-trump-tariffs-trade',
  },
];

// ============================================================================
// TRADE WAR TREND DATA - Historical Tariff Rates
// Sources: World Bank (TM.TAX.MRCH.WM.AR.ZS), WTO Tariff Profiles, Yale Budget Lab
// ============================================================================

export const FALLBACK_TARIFF_TRENDS: TariffTrendData[] = [
  // Pre-trade war baseline - World Bank data
  { year: 2018, usAvgTariff: 1.6, euAvgTariff: 1.8, chinaAvgTariff: 3.4, globalTradeVolume: 25.3 },
  // First Trump trade war begins - tariffs on China start
  { year: 2019, usAvgTariff: 2.5, euAvgTariff: 1.8, chinaAvgTariff: 4.0, globalTradeVolume: 25.0 },
  // COVID impact, tariffs maintained
  { year: 2020, usAvgTariff: 2.5, euAvgTariff: 1.8, chinaAvgTariff: 3.8, globalTradeVolume: 22.3 },
  // Biden maintains Trump tariffs
  { year: 2021, usAvgTariff: 2.4, euAvgTariff: 1.7, chinaAvgTariff: 3.6, globalTradeVolume: 28.5 },
  { year: 2022, usAvgTariff: 2.4, euAvgTariff: 1.7, chinaAvgTariff: 3.5, globalTradeVolume: 31.8 },
  // WTO 2023 data - US 2.2%, China 3.0% trade-weighted
  { year: 2023, usAvgTariff: 2.2, euAvgTariff: 1.7, chinaAvgTariff: 3.0, globalTradeVolume: 30.5 },
  // Pre-Trump 2.0 baseline - World Bank 2024 data
  { year: 2024, usAvgTariff: 2.5, euAvgTariff: 1.8, chinaAvgTariff: 3.2, globalTradeVolume: 32.0 },
  // Yale Budget Lab November 2025: US 16.8% (highest since 1935)
  // EU increased due to countermeasures, China due to retaliation
  { year: 2025, usAvgTariff: 16.8, euAvgTariff: 2.8, chinaAvgTariff: 5.5, globalTradeVolume: 31.1 },
];

// ============================================================================
// MONTHLY TARIFF TREND DATA - January 2024 to January 2026
// Sources: Yale Budget Lab, World Bank, WTO
// ============================================================================

export interface MonthlyTariffData {
  date: string; // Format: "Jan 24", "Feb 24", etc.
  fullDate: string; // Format: "2024-01"
  usAvgTariff: number;
  euAvgTariff: number;
  chinaAvgTariff: number;
}

export const FALLBACK_MONTHLY_TARIFF_TRENDS: MonthlyTariffData[] = [
  // 2024 - Baseline period (Biden administration maintained Trump 1.0 tariffs)
  { date: 'Jan 24', fullDate: '2024-01', usAvgTariff: 2.5, euAvgTariff: 1.8, chinaAvgTariff: 3.2 },
  { date: 'Feb 24', fullDate: '2024-02', usAvgTariff: 2.5, euAvgTariff: 1.8, chinaAvgTariff: 3.2 },
  { date: 'Mar 24', fullDate: '2024-03', usAvgTariff: 2.5, euAvgTariff: 1.8, chinaAvgTariff: 3.2 },
  { date: 'Apr 24', fullDate: '2024-04', usAvgTariff: 2.5, euAvgTariff: 1.8, chinaAvgTariff: 3.2 },
  { date: 'May 24', fullDate: '2024-05', usAvgTariff: 2.5, euAvgTariff: 1.8, chinaAvgTariff: 3.2 },
  { date: 'Jun 24', fullDate: '2024-06', usAvgTariff: 2.5, euAvgTariff: 1.8, chinaAvgTariff: 3.2 },
  { date: 'Jul 24', fullDate: '2024-07', usAvgTariff: 2.5, euAvgTariff: 1.8, chinaAvgTariff: 3.2 },
  { date: 'Aug 24', fullDate: '2024-08', usAvgTariff: 2.5, euAvgTariff: 1.8, chinaAvgTariff: 3.2 },
  { date: 'Sep 24', fullDate: '2024-09', usAvgTariff: 2.5, euAvgTariff: 1.8, chinaAvgTariff: 3.2 },
  { date: 'Oct 24', fullDate: '2024-10', usAvgTariff: 2.5, euAvgTariff: 1.8, chinaAvgTariff: 3.2 },
  { date: 'Nov 24', fullDate: '2024-11', usAvgTariff: 2.5, euAvgTariff: 1.8, chinaAvgTariff: 3.2 },
  { date: 'Dec 24', fullDate: '2024-12', usAvgTariff: 2.5, euAvgTariff: 1.8, chinaAvgTariff: 3.2 },
  // 2025 - Trump 2.0 begins (Yale Budget Lab data)
  { date: 'Jan 25', fullDate: '2025-01', usAvgTariff: 2.4, euAvgTariff: 1.8, chinaAvgTariff: 3.2 }, // Pre-inauguration baseline
  { date: 'Feb 25', fullDate: '2025-02', usAvgTariff: 5.2, euAvgTariff: 1.8, chinaAvgTariff: 4.0 }, // Feb 1: 25% CA/MX, 10% CN
  { date: 'Mar 25', fullDate: '2025-03', usAvgTariff: 8.5, euAvgTariff: 1.8, chinaAvgTariff: 4.8 }, // Mar 12: Steel/aluminum 25%
  { date: 'Apr 25', fullDate: '2025-04', usAvgTariff: 28.0, euAvgTariff: 2.2, chinaAvgTariff: 8.5 }, // Apr 2: "Liberation Day" + Apr 12: peak 145% on China
  { date: 'May 25', fullDate: '2025-05', usAvgTariff: 18.0, euAvgTariff: 2.4, chinaAvgTariff: 5.5 }, // May 14: US-China truce to 10%
  { date: 'Jun 25', fullDate: '2025-06', usAvgTariff: 18.5, euAvgTariff: 2.5, chinaAvgTariff: 5.5 },
  { date: 'Jul 25', fullDate: '2025-07', usAvgTariff: 20.6, euAvgTariff: 2.6, chinaAvgTariff: 5.5 }, // Yale: highest since 1910
  { date: 'Aug 25', fullDate: '2025-08', usAvgTariff: 18.5, euAvgTariff: 2.8, chinaAvgTariff: 5.5 }, // Aug 21: EU-US deal at 15%
  { date: 'Sep 25', fullDate: '2025-09', usAvgTariff: 18.0, euAvgTariff: 2.8, chinaAvgTariff: 5.5 },
  { date: 'Oct 25', fullDate: '2025-10', usAvgTariff: 18.0, euAvgTariff: 2.8, chinaAvgTariff: 5.5 }, // Oct 30: Trump-Xi Busan
  { date: 'Nov 25', fullDate: '2025-11', usAvgTariff: 16.8, euAvgTariff: 2.8, chinaAvgTariff: 5.5 }, // Yale: 16.8% highest since 1935
  { date: 'Dec 25', fullDate: '2025-12', usAvgTariff: 16.8, euAvgTariff: 2.8, chinaAvgTariff: 5.5 },
  // 2026
  { date: 'Jan 26', fullDate: '2026-01', usAvgTariff: 16.8, euAvgTariff: 2.8, chinaAvgTariff: 5.2 }, // China cuts 935 tariffs
];

// ============================================================================
// TRADE NEWS - Recent Headlines (Updated January 2026)
// Sources: Reuters, Euronews, Bloomberg, White House, EC Trade
// ============================================================================

export const FALLBACK_TRADE_NEWS: TradeNewsItem[] = [
  {
    id: 'tn-0a',
    title: 'Trump announces 10% tariffs on 8 European countries over Greenland dispute',
    link: 'https://www.nbcnews.com/business/economy/trump-denmark-european-tariffs-greenland-deal-rcna254551',
    pubDate: new Date('2026-01-17'),
    source: 'NBC News',
    category: 'US-EU',
    description: 'New 10% tariffs on Denmark, Finland, France, Germany, Netherlands, Norway, Sweden, UK starting Feb 1. Will rise to 25% on June 1.',
  },
  {
    id: 'tn-0b',
    title: 'EU prepares €108B "trade bazooka" response to Trump Greenland tariffs',
    link: 'https://www.cnn.com/2026/01/18/business/europe-greenland-trump-tariffs-trade',
    pubDate: new Date('2026-01-18'),
    source: 'CNN',
    category: 'US-EU',
    description: 'France requests activation of Anti-Coercion Instrument; 8 European countries issue joint statement of solidarity with Denmark.',
  },
  {
    id: 'tn-1',
    title: 'China slashes tariffs on 935 items in strategic trade war pivot',
    link: 'https://asiatimes.com/2026/01/china-slashes-hundreds-of-tariffs-in-strategic-trade-war-twist/',
    pubDate: new Date('2026-01-01'),
    source: 'Asia Times',
    category: 'US-China',
    description: 'Beginning January 1, 2026, China reduces import duties below MFN rates to fortify industrial base.',
  },
  {
    id: 'tn-2',
    title: 'US and China head into 2026 with fragile trade truce',
    link: 'https://www.bloomberg.com/news/newsletters/2025-12-29/us-china-trade-truce',
    pubDate: new Date('2025-12-29'),
    source: 'Bloomberg',
    category: 'US-China',
    description: 'Trump and Xi broker ceasefire on tariffs, but tension flares on Taiwan and rare earths.',
  },
  {
    id: 'tn-3',
    title: 'In 2025, global trade cracked as Europe hurt by US tariffs and China shock',
    link: 'https://www.euronews.com/my-europe/2025/12/29/in-2025-global-trade-cracked-as-europe-hurt-by-us-tariffs-and-new-china-shock',
    pubDate: new Date('2025-12-29'),
    source: 'Euronews',
    category: 'US-EU',
    description: 'Chinese goods to EU surged 15% between Nov 2024-2025 as trade flows reroute to Europe.',
  },
  {
    id: 'tn-4',
    title: 'China keeps rare earth limits for US despite Trump-Xi supply deal',
    link: 'https://www.bloomberg.com/news/articles/2025-12-24/us-rare-earth-buyers-still-see-china-curbs-despite-trump-deal',
    pubDate: new Date('2025-12-24'),
    source: 'Bloomberg',
    category: 'US-China',
    description: 'US buyers still face restrictions on rare earths needed for permanent magnets despite October deal.',
  },
  {
    id: 'tn-5',
    title: 'Yale Budget Lab: US tariff rate hits 16.8%, highest since 1935',
    link: 'https://budgetlab.yale.edu/research/state-us-tariffs-november-17-2025',
    pubDate: new Date('2025-11-17'),
    source: 'Yale Budget Lab',
    category: 'General',
    description: 'US effective tariff rate reaches 16.8% after 14.4 percentage point increase from 2024 baseline.',
  },
  {
    id: 'tn-6',
    title: 'Trump-Xi meeting: 10% tariff rate extended until November 2026',
    link: 'https://www.whitehouse.gov/fact-sheets/2025/11/fact-sheet-president-donald-j-trump-strikes-deal-on-economic-and-trade-relations-with-china/',
    pubDate: new Date('2025-11-10'),
    source: 'White House',
    category: 'US-China',
    description: 'Liberation Day tariffs suspended at 10% for one year following Trump-Xi Busan summit.',
  },
  {
    id: 'tn-7',
    title: 'China rare earth export controls jeopardize EU auto, tech, defense sectors',
    link: 'https://epthinktank.eu/2025/11/24/chinas-rare-earth-export-restrictions/',
    pubDate: new Date('2025-11-24'),
    source: 'EU Parliament',
    category: 'EU-China',
    description: 'EU supply chains remain vulnerable despite partial suspension of October controls.',
  },
  {
    id: 'tn-8',
    title: 'EU-US framework sets 15% tariff ceiling, spirits excluded',
    link: 'https://policy.trade.ec.europa.eu/news/joint-statement-united-states-european-union-framework-agreement-reciprocal-fair-and-balanced-trade-2025-08-21_en',
    pubDate: new Date('2025-08-21'),
    source: 'EC Trade',
    category: 'US-EU',
    description: 'Single 15% rate agreed for most goods; US demands EU cut industrial tariffs in 2026 legislation.',
  },
];
