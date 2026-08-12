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
  '32018L1972': '/eucanon/2018-1972_eecc/',
  '32009L0138': '/eucanon/2009-138_solvency2/',
  '32014L0065': '/eucanon/2014-65_mifid2/',
  '32018D0859': '/eucanon/2018-859_amazon_state_aid/',
  '32017D1283': '/eucanon/2017-1283_apple_state_aid/',
  '32023D1683': '/eucanon/2023-1683_la_rochelle_airport/',
  '32016D0633': '/eucanon/2016-633_nimes_airport/',
  '32025D1963': '/eucanon/2025-1963_cineca/',
  '32020D1412': '/eucanon/2020-1412_tirrenia/',
  '32016R0679': '/eucanon/2016-679_gdpr/',
  '32022R2065': '/eucanon/2022-2065_dsa/',
  '32022R1925': '/eucanon/2022-1925_dma/',
  '32022L2555': '/eucanon/2022-2555_nis2/',
  '32023R0956': '/eucanon/2023-956_cbam/',
  '32022R2554': '/eucanon/2022-2554_dora/',
  '32025R0327': '/eucanon/2025-327_ehds/',
  '32025R0040': '/eucanon/2025-40_ppwr/',
  '32025L1892': '/eucanon/2025-1892_wfd_textiles/',
  '32022L2464': '/eucanon/2022-2464_csrd/',
  '32024L1760': '/eucanon/2024-1760_csddd/',
  '32023R1542': '/eucanon/2023-1542_batteries/',
  '32024R1781': '/eucanon/2024-1781_espr/',
  '32024R1252': '/eucanon/2024-1252_crma/',
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
  'European Electronic Communications Code (Directive 2018/1972)': '/eucanon/2018-1972_eecc/',
  'Solvency II (Directive 2009/138/EC)': '/eucanon/2009-138_solvency2/',
  'MiFID II (Directive 2014/65/EU)': '/eucanon/2014-65_mifid2/',
  'Amazon State Aid Decision (Decision (EU) 2018/859)': '/eucanon/2018-859_amazon_state_aid/',
  'Apple State Aid Decision (Decision (EU) 2017/1283)': '/eucanon/2017-1283_apple_state_aid/',
  'La Rochelle Airport State Aid Decision (Decision (EU) 2023/1683)': '/eucanon/2023-1683_la_rochelle_airport/',
  'Nimes Airport State Aid Decision (Decision (EU) 2016/633)': '/eucanon/2016-633_nimes_airport/',
  'Cineca State Aid Decision (Decision (EU) 2025/1963)': '/eucanon/2025-1963_cineca/',
  'Tirrenia State Aid Decision (Decision (EU) 2020/1412)': '/eucanon/2020-1412_tirrenia/',
  'Textile EPR and Food Waste Package': '/eucanon/2025-1892_wfd_textiles/',
  // These four canon clusters were merged into their package clusters on
  // 8 Aug 2026 (scripts/merge_duplicate_clusters.py), because EU Law Comply was
  // offering two entries for the same law with very different depth. The
  // GET /clusters payload carries no primary_celex, so getEucanonUrl resolves by
  // NAME -- deleting these names alone would have silently killed the explainer
  // link on the surviving cards. Both spellings are kept: the retired canon
  // names for any cached client, and the package names that are live now.
  'GDPR (Regulation (EU) 2016/679)': '/eucanon/2016-679_gdpr/',
  'GDPR Package (Data Protection)': '/eucanon/2016-679_gdpr/',
  'Digital Services Act (Regulation (EU) 2022/2065)': '/eucanon/2022-2065_dsa/',
  'Digital Services Act Package': '/eucanon/2022-2065_dsa/',
  'Digital Markets Act (Regulation (EU) 2022/1925)': '/eucanon/2022-1925_dma/',
  'Digital Markets Act Package': '/eucanon/2022-1925_dma/',
  'NIS2 Directive (Directive (EU) 2022/2555)': '/eucanon/2022-2555_nis2/',
  'NIS2 Directive (Cybersecurity)': '/eucanon/2022-2555_nis2/',
  'CBAM Package (Carbon Border Adjustment Mechanism)': '/eucanon/2023-956_cbam/',
  'CBAM (Regulation (EU) 2023/956)': '/eucanon/2023-956_cbam/',
  'DORA - Digital Operational Resilience Act': '/eucanon/2022-2554_dora/',
  'DORA (Regulation (EU) 2022/2554)': '/eucanon/2022-2554_dora/',
  'EHDS - European Health Data Space': '/eucanon/2025-327_ehds/',
  'European Health Data Space (Regulation (EU) 2025/327)': '/eucanon/2025-327_ehds/',
  'PPWR - Packaging and Packaging Waste Regulation': '/eucanon/2025-40_ppwr/',
  'Packaging and Packaging Waste Regulation (Regulation (EU) 2025/40)': '/eucanon/2025-40_ppwr/',
  'CSRD - Corporate Sustainability Reporting Directive': '/eucanon/2022-2464_csrd/',
  'Corporate Sustainability Reporting Directive (Directive (EU) 2022/2464)': '/eucanon/2022-2464_csrd/',
  'CSDDD - Corporate Sustainability Due Diligence Directive': '/eucanon/2024-1760_csddd/',
  'Corporate Sustainability Due Diligence Directive (Directive (EU) 2024/1760)': '/eucanon/2024-1760_csddd/',
  'EU Batteries Regulation (Reg 2023/1542)': '/eucanon/2023-1542_batteries/',
  'Batteries Regulation (Regulation (EU) 2023/1542)': '/eucanon/2023-1542_batteries/',
  'Textiles: EPR, Ecodesign and Digital Product Passport (DPP-TEX)': '/eucanon/digital-product-passport/',
  'EU Digital Product Passport (ESPR Reg 2024/1781)': '/eucanon/digital-product-passport/',
  'EU Digital Product Passport regime (ESPR + product laws)': '/eucanon/digital-product-passport/',
  'ESPR - Ecodesign for Sustainable Products Regulation (Reg 2024/1781)': '/eucanon/2024-1781_espr/',
  'CRMA - Critical Raw Materials Act (Reg 2024/1252)': '/eucanon/2024-1252_crma/',
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
