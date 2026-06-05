/**
 * EU Canon registry.
 *
 * Maps CELEX numbers (and law-cluster names as a fallback) to the URL of the
 * Brubru eucanon public explainer page. This is what lets the chat and the
 * EU Law Comply cluster card surface a "Read the plain-language explainer"
 * reminder.
 *
 * As we add more eucanon pages, add entries here. Both CELEX and cluster-name
 * keys are supported because some clusters may not have a primary CELEX (yet).
 */

export const EUCANON_BY_CELEX: Record<string, string> = {
  '32013R0575': '/eucanon/2013-575_crr/',
  '32024R2754': '/eucanon/2024-2754_china_bev_duties/',
  '32020R0776': '/eucanon/2020-776_china_egypt_glass_fibre/',
  '32022R0433': '/eucanon/2022-433_india_indonesia_stainless_steel/',
  '32019R2175': '/eucanon/2019-2175_esas_review/',
  '32016R0429': '/eucanon/2016-429_animal_health_law/',
  '32023R1114': '/eucanon/2023-1114_mica/',
  '32024R1689': '/eucanon/2024-1689_aiact/',
  '32025R0500': '/eucanon/2025-500_morocco_aluminium_wheels/',
  '32017R0625': '/eucanon/2017-625_official_controls/',
  '32021R2011': '/eucanon/2021-2011_optical_fibre_cables/',
  '32004R0726': '/eucanon/2004-726_ema/',
  '32000R0141': '/eucanon/2000-141_orphan/',
  '32014R0536': '/eucanon/2014-536_ctr/',
  '32007R1394': '/eucanon/2007-1394_atmp/',
  '32006R1901': '/eucanon/2006-1901_paediatric/',
  '32001L0083': '/eucanon/2001-83_community_code/',
  '32004L0024': '/eucanon/2004-24_herbal/',
  '32010L0084': '/eucanon/2010-84_pharmacovigilance/',
  '32011L0062': '/eucanon/2011-62_falsified_medicines/',
  '32012L0026': '/eucanon/2012-26_pv_amend/',
};

export const EUCANON_BY_CLUSTER_NAME: Record<string, string> = {
  'CRR / CRD IV - Bank Prudential Requirements': '/eucanon/2013-575_crr/',
  'China BEV Countervailing Duties (Reg 2024/2754)': '/eucanon/2024-2754_china_bev_duties/',
  'China and Egypt GFF Countervailing Duties (Reg 2020/776)': '/eucanon/2020-776_china_egypt_glass_fibre/',
  'India and Indonesia Stainless Steel Countervailing Duties (Reg 2022/433)': '/eucanon/2022-433_india_indonesia_stainless_steel/',
  'ESAs Review (Reg 2019/2175)': '/eucanon/2019-2175_esas_review/',
  'Animal Health Law (Reg 2016/429)': '/eucanon/2016-429_animal_health_law/',
  'MiCA (Reg 2023/1114)': '/eucanon/2023-1114_mica/',
  'AI Act Package': '/eucanon/2024-1689_aiact/',
  'AI Act (Reg 2024/1689)': '/eucanon/2024-1689_aiact/',
  'Morocco Aluminium Road Wheels Countervailing Duties (Reg 2025/500)': '/eucanon/2025-500_morocco_aluminium_wheels/',
  'Official Controls Regulation (Reg 2017/625)': '/eucanon/2017-625_official_controls/',
  'Optical Fibre Cables China Anti-Dumping Duties (Reg 2021/2011)': '/eucanon/2021-2011_optical_fibre_cables/',
  'EMA and the Centralised Procedure (Reg 726/2004)': '/eucanon/2004-726_ema/',
  'Orphan Medicinal Products (Reg 141/2000)': '/eucanon/2000-141_orphan/',
  'Clinical Trials Regulation (Reg 536/2014)': '/eucanon/2014-536_ctr/',
  'Advanced Therapy Medicinal Products (Reg 1394/2007)': '/eucanon/2007-1394_atmp/',
  'Paediatric Medicines (Reg 1901/2006)': '/eucanon/2006-1901_paediatric/',
};

export interface EucanonLookupInput {
  name?: string;
  primary_celex?: string | null;
}

export function getEucanonUrl(input: EucanonLookupInput): string | null {
  if (input.primary_celex && EUCANON_BY_CELEX[input.primary_celex]) {
    return EUCANON_BY_CELEX[input.primary_celex];
  }
  if (input.name && EUCANON_BY_CLUSTER_NAME[input.name]) {
    return EUCANON_BY_CLUSTER_NAME[input.name];
  }
  return null;
}
