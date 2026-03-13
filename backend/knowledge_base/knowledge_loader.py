"""
Knowledge Base Loader

Loads and indexes internal knowledge base (calendars, institutions, templates)
for use in AI chat context.

Features:
- Load JSON reference data (calendars, institutions) into memory
- Index templates into ChromaDB for semantic search
- Provide unified query interface
- Hot-reload support for knowledge updates
"""

import logging
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)


# Keyword triggers for guide matching
# Maps keywords (lowercase) to guide file stems that should be surfaced
# when those keywords appear in user queries
GUIDE_KEYWORD_TRIGGERS: Dict[str, List[str]] = {
    # EU Rare Diseases Policy
    'rare disease': ['eu_rare_diseases_policy'],
    'rare diseases': ['eu_rare_diseases_policy'],
    'orphan drug': ['eu_rare_diseases_policy'],
    'orphan medicine': ['eu_rare_diseases_policy'],
    'orphan medicinal': ['eu_rare_diseases_policy'],
    'orphan regulation': ['eu_rare_diseases_policy'],
    'orphan designation': ['eu_rare_diseases_policy'],
    'european reference network': ['eu_rare_diseases_policy'],
    'ern': ['eu_rare_diseases_policy'],
    'erdera': ['eu_rare_diseases_policy'],
    'eurordis': ['eu_rare_diseases_policy'],
    'orphanet': ['eu_rare_diseases_policy'],
    'orphacode': ['eu_rare_diseases_policy'],
    'newborn screening': ['eu_rare_diseases_policy'],
    'diagnostic odyssey': ['eu_rare_diseases_policy'],
    'rare disease action plan': ['eu_rare_diseases_policy'],
    'erdri': ['eu_rare_diseases_policy'],
    'jardin': ['eu_rare_diseases_policy'],
    'sant committee': ['eu_rare_diseases_policy'],
    '141/2000': ['eu_rare_diseases_policy'],
    'maladie rare': ['eu_rare_diseases_policy'],
    'enfermedad rara': ['eu_rare_diseases_policy'],
    'malattia rara': ['eu_rare_diseases_policy'],
    'zeldzame ziekte': ['eu_rare_diseases_policy'],
    'malaltia rara': ['eu_rare_diseases_policy'],
    # Horizon Europe Grant Management
    'grant': ['horizon_europe_grant_management'],
    'mga': ['horizon_europe_grant_management'],
    'model grant agreement': ['horizon_europe_grant_management'],
    'consortium': ['horizon_europe_grant_management'],
    'horizon europe': ['horizon_europe_grant_management'],
    'gap process': ['horizon_europe_grant_management'],
    'eligible costs': ['horizon_europe_grant_management'],
    'lump sum': ['horizon_europe_grant_management'],
    'grant agreement preparation': ['horizon_europe_grant_management'],
    'form c': ['horizon_europe_grant_management'],

    # EU Financial Regulation Procurement
    'procurement': ['eu_financial_regulation_procurement'],
    'tender': ['eu_financial_regulation_procurement'],
    'framework contract': ['eu_financial_regulation_procurement'],
    'financial regulation': ['eu_financial_regulation_procurement', 'eu_budget_emu_law'],
    'evaluation committee': ['eu_financial_regulation_procurement'],
    'open procedure': ['eu_financial_regulation_procurement'],
    'restricted procedure': ['eu_financial_regulation_procurement'],
    'competitive dialogue': ['eu_financial_regulation_procurement'],
    'lafr': ['eu_financial_regulation_procurement'],
    'la fr': ['eu_financial_regulation_procurement'],
    'le rf': ['eu_financial_regulation_procurement'],
    'the fr': ['eu_financial_regulation_procurement'],
    'reglamento financiero': ['eu_financial_regulation_procurement'],
    'reglement financier': ['eu_financial_regulation_procurement'],

    # Competition Law Enforcement
    'antitrust': ['competition_law_enforcement'],
    'cartel': ['competition_law_enforcement'],
    'article 101': ['competition_law_enforcement'],
    'article 102': ['competition_law_enforcement'],
    'dawn raid': ['competition_law_enforcement'],
    'leniency': ['competition_law_enforcement'],
    'dg comp': ['competition_law_enforcement'],
    'dominance': ['competition_law_enforcement'],
    'merger control': ['competition_law_enforcement'],
    'statement of objections': ['competition_law_enforcement'],
    'fining guidelines': ['competition_law_enforcement'],

    # EU Budget and EMU Law
    'mff': ['mff_2028_2034', 'eu_budget_emu_law'],
    'multiannual financial framework': ['mff_2028_2034', 'eu_budget_emu_law'],
    'own resources': ['mff_2028_2034', 'eu_budget_emu_law'],
    'esm': ['eu_budget_emu_law'],
    'olaf': ['eu_budget_emu_law', 'cohesion_policy_audit'],
    'eppo': ['eu_budget_emu_law'],
    'eib': ['eu_budget_emu_law'],
    'investeu': ['eu_budget_emu_law', 'knowledge_valorisation_tech_transfer'],
    'budget': ['eu_budget_emu_law', 'mff_2028_2034'],
    'discharge': ['eu_budget_emu_law'],
    'stability and growth pact': ['eu_budget_emu_law'],

    # MFF 2028-2034
    'mff 2028': ['mff_2028_2034'],
    'mff 2028-2034': ['mff_2028_2034'],
    'long-term budget': ['mff_2028_2034', 'eu_budget_emu_law'],
    'long term budget': ['mff_2028_2034', 'eu_budget_emu_law'],
    'eu budget 2028': ['mff_2028_2034'],
    'budget 2028-2034': ['mff_2028_2034'],
    'competitiveness fund': ['mff_2028_2034'],
    'national and regional partnership': ['mff_2028_2034'],
    'partnership plans': ['mff_2028_2034'],
    'global europe fund': ['mff_2028_2034'],
    'gef': ['mff_2028_2034'],
    'ngeu repayment': ['mff_2028_2034'],
    'next generation eu repayment': ['mff_2028_2034'],
    'heading 1': ['mff_2028_2034'],
    'heading 2': ['mff_2028_2034'],
    'heading 3': ['mff_2028_2034'],
    'heading 4': ['mff_2028_2034'],
    'budget heading': ['mff_2028_2034'],
    'commitment appropriation': ['mff_2028_2034', 'eu_budget_emu_law'],
    'payment appropriation': ['mff_2028_2034', 'eu_budget_emu_law'],
    'budget ceiling': ['mff_2028_2034', 'eu_budget_emu_law'],
    'expenditure ceiling': ['mff_2028_2034', 'eu_budget_emu_law'],
    'tobacco excise duty own resource': ['mff_2028_2034'],
    'tedor': ['mff_2028_2034'],
    'e-waste own resource': ['mff_2028_2034'],
    'corporate resource for europe': ['mff_2028_2034'],
    'core own resource': ['mff_2028_2034'],
    'cap cuts': ['mff_2028_2034'],
    'cap reduction': ['mff_2028_2034'],
    'cap budget': ['mff_2028_2034'],
    'ukraine reserve': ['mff_2028_2034'],
    'ukraine financial': ['mff_2028_2034'],
    'ukraine support': ['mff_2028_2034'],
    'ukraine funding': ['mff_2028_2034'],
    'ukraine reconstruction': ['mff_2028_2034'],
    'ukraine loan': ['mff_2028_2034'],
    '2025/0570': ['mff_2028_2034'],
    'com(2025) 570': ['mff_2028_2034'],
    'com(2025) 571': ['mff_2028_2034'],
    'cadre financier pluriannuel': ['mff_2028_2034'],
    'marco financiero plurianual': ['mff_2028_2034'],
    'mehrjähriger finanzrahmen': ['mff_2028_2034'],
    'quadro finanziario pluriennale': ['mff_2028_2034'],
    'meerjarig financieel kader': ['mff_2028_2034'],

    # Employment and Future of Work
    'platform work': ['employment_future_of_work'],
    'right to disconnect': ['employment_future_of_work'],
    'youth guarantee': ['employment_future_of_work'],
    'esf+': ['employment_future_of_work', 'cohesion_policy_audit'],
    'algorithmic management': ['employment_future_of_work'],
    'just transition fund': ['employment_future_of_work', 'cohesion_policy_audit'],
    'pillar of social rights': ['employment_future_of_work'],
    'platform workers': ['employment_future_of_work'],
    'traineeships': ['employment_future_of_work'],
    'union of skills': ['employment_future_of_work'],
    'skills strategy': ['employment_future_of_work'],
    'labour shortages': ['employment_future_of_work'],
    'reskilling': ['employment_future_of_work'],
    'upskilling': ['employment_future_of_work'],

    # Industrial Accelerator Act
    'industrial accelerator': ['industrial_accelerator_act'],
    'industrial accelerator act': ['industrial_accelerator_act'],
    'industrial decarbonisation accelerator': ['industrial_accelerator_act'],
    'clean industrial deal': ['industrial_accelerator_act', 'eu_energy_policy'],
    'low-carbon label': ['industrial_accelerator_act'],
    'low carbon label': ['industrial_accelerator_act'],
    'carbon intensity label': ['industrial_accelerator_act'],
    'lead markets': ['industrial_accelerator_act'],
    'industrial decarbonisation': ['industrial_accelerator_act'],
    'decarbonisation accelerator': ['industrial_accelerator_act'],
    'com(2026)100': ['industrial_accelerator_act'],
    'ccfd': ['industrial_accelerator_act', 'eu_energy_policy'],
    'carbon contracts for difference': ['industrial_accelerator_act', 'eu_energy_policy'],
    'clean industry state aid': ['industrial_accelerator_act'],
    'cisaf': ['industrial_accelerator_act'],
    'industrial decarbonisation bank': ['industrial_accelerator_act'],
    'permitting bottleneck': ['industrial_accelerator_act'],
    'net-zero industry act': ['industrial_accelerator_act'],
    'nzia': ['industrial_accelerator_act'],
    # Multilingual
    'accelerateur industriel': ['industrial_accelerator_act'],
    'acelerador industrial': ['industrial_accelerator_act'],
    'acceleratore industriale': ['industrial_accelerator_act'],
    'industriele versneller': ['industrial_accelerator_act'],
    'descarbonitzacio industrial': ['industrial_accelerator_act'],
    'christophe grudler': ['industrial_accelerator_act'],
    'grudler': ['industrial_accelerator_act'],

    # European Semester Communication
    'european semester': ['european_semester_communication', 'european_semester_annual_report_2026'],
    'economic forecast': ['european_semester_communication'],
    'rrf': ['european_semester_communication', 'eu_budget_emu_law'],
    'recovery and resilience': ['european_semester_communication', 'eu_budget_emu_law'],
    'digital euro': ['european_semester_communication'],
    'csr': ['european_semester_communication'],
    'country report': ['european_semester_communication'],
    'country-specific recommendation': ['european_semester_communication'],
    'annual sustainable growth survey': ['european_semester_communication'],
    # European Semester Annual Report 2026
    'semester annual report': ['european_semester_annual_report_2026'],
    'semester report 2026': ['european_semester_annual_report_2026'],
    'economic policy coordination annual': ['european_semester_annual_report_2026'],
    'employment social priorities 2026': ['european_semester_annual_report_2026'],
    'nela riehl': ['european_semester_annual_report_2026'],
    'kira marie peter-hansen': ['european_semester_annual_report_2026'],
    'peter-hansen': ['european_semester_annual_report_2026'],
    '2025/2182': ['european_semester_annual_report_2026'],
    '2025/2183': ['european_semester_annual_report_2026'],
    'a10-0033': ['european_semester_annual_report_2026'],
    'a10-0032': ['european_semester_annual_report_2026'],
    'autumn package': ['european_semester_annual_report_2026', 'european_semester_communication'],

    # Cohesion Policy Audit
    'cohesion': ['cohesion_policy_audit', 'mff_2028_2034'],
    'audit': ['cohesion_policy_audit'],
    'erdf': ['cohesion_policy_audit'],
    'arachne': ['cohesion_policy_audit'],
    'error rate': ['cohesion_policy_audit'],
    'shared management': ['cohesion_policy_audit'],
    'managing authority': ['cohesion_policy_audit'],
    'audit authority': ['cohesion_policy_audit'],
    'financial corrections': ['cohesion_policy_audit'],
    'common provisions regulation': ['cohesion_policy_audit'],

    # Financial Supervision (EBA/MiCA/DORA)
    'eba': ['financial_supervision_eba'],
    'eiopa': ['financial_supervision_eba'],
    'esma': ['financial_supervision_eba'],
    'prudential': ['financial_supervision_eba'],
    'on-site inspection': ['financial_supervision_eba'],
    'supervisory college': ['financial_supervision_eba'],
    'ctpp': ['financial_supervision_eba'],
    'mica': ['financial_supervision_eba'],
    'dora': ['financial_supervision_eba'],
    'crypto-asset': ['financial_supervision_eba'],
    'significant token': ['financial_supervision_eba'],

    # Eurostat Statistics Production
    'eurostat': ['eurostat_statistics_production'],
    'itss': ['eurostat_statistics_production'],
    'fats': ['eurostat_statistics_production'],
    'fdi': ['eurostat_statistics_production'],
    'ebops': ['eurostat_statistics_production'],
    'statistics': ['eurostat_statistics_production'],
    'asymmetry': ['eurostat_statistics_production'],
    'data quality': ['eurostat_statistics_production'],
    'nsi': ['eurostat_statistics_production'],
    'trade in services': ['eurostat_statistics_production'],

    # Knowledge Valorisation and Technology Transfer
    'knowledge valorisation': ['knowledge_valorisation_tech_transfer'],
    'technology transfer': ['knowledge_valorisation_tech_transfer'],
    'trl': ['knowledge_valorisation_tech_transfer'],
    'ip management': ['knowledge_valorisation_tech_transfer'],
    'era': ['knowledge_valorisation_tech_transfer'],
    'eic': ['knowledge_valorisation_tech_transfer'],
    'eic pathfinder': ['knowledge_valorisation_tech_transfer'],
    'eic accelerator': ['knowledge_valorisation_tech_transfer'],
    'spin-off': ['knowledge_valorisation_tech_transfer'],
    'technology readiness': ['knowledge_valorisation_tech_transfer'],
    'valley of death': ['knowledge_valorisation_tech_transfer'],

    # Bioeconomy and Food Systems
    'bioeconomy': ['bioeconomy_food_systems'],
    'food2030': ['bioeconomy_food_systems'],
    'scar': ['bioeconomy_food_systems'],
    'alternative proteins': ['bioeconomy_food_systems'],
    'living labs': ['bioeconomy_food_systems'],
    'food systems': ['bioeconomy_food_systems'],
    'cellular agriculture': ['bioeconomy_food_systems'],
    'precision fermentation': ['bioeconomy_food_systems'],
    'novel food': ['bioeconomy_food_systems'],
    'biorefinery': ['bioeconomy_food_systems'],

    # EU Space Programme
    'galileo': ['eu_space_programme'],
    'copernicus': ['eu_space_programme'],
    'iris2': ['eu_space_programme'],
    'space act': ['eu_space_programme'],
    'space debris': ['eu_space_programme'],
    'euspa': ['eu_space_programme'],
    'autonomous access': ['eu_space_programme'],
    'ariane': ['eu_space_programme'],
    'sentinel': ['eu_space_programme'],
    'space programme': ['eu_space_programme'],
    'egnos': ['eu_space_programme'],

    # Road Safety, Autonomous Vehicles and ADAS
    'road safety': ['road_safety_autonomous_vehicles'],
    'adas': ['road_safety_autonomous_vehicles'],
    'autonomous vehicle': ['road_safety_autonomous_vehicles'],
    'automated driving': ['road_safety_autonomous_vehicles'],
    'self-driving': ['road_safety_autonomous_vehicles'],
    'vehicle safety': ['road_safety_autonomous_vehicles'],
    'type-approval': ['road_safety_autonomous_vehicles'],
    'type approval': ['road_safety_autonomous_vehicles'],
    'general safety regulation': ['road_safety_autonomous_vehicles'],
    'gsr': ['road_safety_autonomous_vehicles'],
    'emergency braking': ['road_safety_autonomous_vehicles'],
    'lane keeping': ['road_safety_autonomous_vehicles'],
    'speed assistance': ['road_safety_autonomous_vehicles'],
    'ecall': ['road_safety_autonomous_vehicles'],
    'euro ncap': ['road_safety_autonomous_vehicles'],
    'unece': ['road_safety_autonomous_vehicles'],
    'dg move': ['road_safety_autonomous_vehicles'],
    'vehicle autonom': ['road_safety_autonomous_vehicles'],
    'vehicule autonome': ['road_safety_autonomous_vehicles'],
    'seguretat viaria': ['road_safety_autonomous_vehicles'],
    'securite routiere': ['road_safety_autonomous_vehicles'],
    'seguridad vial': ['road_safety_autonomous_vehicles'],
    'driving licence': ['road_safety_autonomous_vehicles'],
    'connected vehicle': ['road_safety_autonomous_vehicles'],
    'cybersecurity vehicle': ['road_safety_autonomous_vehicles'],

    # REACH and Chemicals Regulation
    'reach': ['reach_chemicals_regulation'],
    'chemicals': ['reach_chemicals_regulation'],
    'chemical substances': ['reach_chemicals_regulation'],
    'echa': ['reach_chemicals_regulation'],
    'pfas': ['reach_chemicals_regulation'],
    'svhc': ['reach_chemicals_regulation'],
    'substances of very high concern': ['reach_chemicals_regulation'],
    'restriction proposal': ['reach_chemicals_regulation'],
    'annex xiv': ['reach_chemicals_regulation'],
    'annex xvii': ['reach_chemicals_regulation'],
    'authorisation list': ['reach_chemicals_regulation'],
    'candidate list': ['reach_chemicals_regulation'],
    'microplastics': ['reach_chemicals_regulation'],
    'bisphenol': ['reach_chemicals_regulation'],
    'clp regulation': ['reach_chemicals_regulation'],
    'biocidal': ['reach_chemicals_regulation'],
    'chemicals strategy': ['reach_chemicals_regulation'],
    'one substance one assessment': ['reach_chemicals_regulation'],
    'osoa': ['reach_chemicals_regulation'],
    'reglament reach': ['reach_chemicals_regulation'],
    'safe and sustainable by design': ['reach_chemicals_regulation'],
    'ssbd': ['reach_chemicals_regulation'],
    'ssbd chemicals': ['reach_chemicals_regulation'],
    'safe by design': ['reach_chemicals_regulation'],

    # Digital Markets Act (DMA)
    'digital markets act': ['digital_markets_act'],
    'dma': ['digital_markets_act'],
    'dma compliance': ['digital_markets_act'],
    'dma enforcement': ['digital_markets_act'],
    'gatekeeper': ['digital_markets_act'],
    'gatekeepers': ['digital_markets_act'],
    'core platform service': ['digital_markets_act'],
    'core platform services': ['digital_markets_act'],
    'self-preferencing': ['digital_markets_act'],
    'sideloading': ['digital_markets_act'],
    'app store regulation': ['digital_markets_act'],
    'anti-steering': ['digital_markets_act'],
    'interoperability messaging': ['digital_markets_act'],
    'regulation 2022/1925': ['digital_markets_act'],
    '32022r1925': ['digital_markets_act'],
    '2022/1925': ['digital_markets_act'],
    'dma gatekeeper': ['digital_markets_act'],
    'dma template': ['digital_markets_act'],
    'dma article 5': ['digital_markets_act'],
    'dma article 6': ['digital_markets_act'],
    'dma article 7': ['digital_markets_act'],
    'digital markets': ['digital_markets_act'],
    'marche numerique': ['digital_markets_act'],
    'mercado digital': ['digital_markets_act'],
    'mercat digital': ['digital_markets_act'],
    'mercato digitale': ['digital_markets_act'],
    'digitale markt': ['digital_markets_act'],
    'controleur dacces': ['digital_markets_act'],

    # Corporate Sustainability Due Diligence (CSDDD)
    'csddd': ['corporate_sustainability_due_diligence'],
    'cs3d': ['corporate_sustainability_due_diligence'],
    'due diligence directive': ['corporate_sustainability_due_diligence'],
    'corporate sustainability due diligence': ['corporate_sustainability_due_diligence'],
    'supply chain due diligence': ['corporate_sustainability_due_diligence'],
    'value chain due diligence': ['corporate_sustainability_due_diligence'],
    'human rights due diligence': ['corporate_sustainability_due_diligence'],
    'directive 2024/1760': ['corporate_sustainability_due_diligence'],
    '32024l1760': ['corporate_sustainability_due_diligence'],
    '2024/1760': ['corporate_sustainability_due_diligence'],
    'lara wolters': ['corporate_sustainability_due_diligence'],
    'transition plan climate': ['corporate_sustainability_due_diligence'],
    'devoir de vigilance': ['corporate_sustainability_due_diligence'],
    'diligencia debida': ['corporate_sustainability_due_diligence'],
    'dovere di diligenza': ['corporate_sustainability_due_diligence'],
    'zorgplicht': ['corporate_sustainability_due_diligence'],
    'diligencia deguda': ['corporate_sustainability_due_diligence'],
    'csrd': ['corporate_sustainability_due_diligence'],
    'corporate sustainability reporting': ['corporate_sustainability_due_diligence'],

    # Multilingual, Translation and Content Localisation Law
    'translation': ['multilingual_content_law'],
    'localisation': ['multilingual_content_law'],
    'localization': ['multilingual_content_law'],
    'multilingual': ['multilingual_content_law'],
    'language requirements': ['multilingual_content_law'],
    'official languages': ['multilingual_content_law'],
    'content localisation': ['multilingual_content_law'],
    'content localization': ['multilingual_content_law'],
    'subtitling': ['multilingual_content_law'],
    'audio description': ['multilingual_content_law'],
    'labelling language': ['multilingual_content_law'],
    'etranslation': ['multilingual_content_law'],
    'avmsd': ['multilingual_content_law'],
    'audiovisual media': ['multilingual_content_law'],
    'european works': ['multilingual_content_law'],
    'media freedom': ['multilingual_content_law'],
    'en 17100': ['multilingual_content_law'],
    'dg translation': ['multilingual_content_law'],
    'linguistic diversity': ['multilingual_content_law'],
    'plain language': ['multilingual_content_law'],
    'package leaflet': ['multilingual_content_law'],
    'food labelling': ['multilingual_content_law'],

    # AI Act and Digital Omnibus
    'ai act': ['ai_act_regulation'],
    'artificial intelligence act': ['ai_act_regulation'],
    'regulation 2024/1689': ['ai_act_regulation'],
    'ai regulation': ['ai_act_regulation'],
    'high-risk ai': ['ai_act_regulation'],
    'high risk ai': ['ai_act_regulation'],
    'prohibited ai': ['ai_act_regulation'],
    'ai compliance': ['ai_act_regulation'],
    'gpai': ['ai_act_regulation'],
    'general-purpose ai': ['ai_act_regulation'],
    'general purpose ai': ['ai_act_regulation'],
    'ai office': ['ai_act_regulation'],
    'ai board': ['ai_act_regulation'],
    'conformity assessment ai': ['ai_act_regulation'],
    'ai literacy': ['ai_act_regulation'],
    'ai system': ['ai_act_regulation'],
    'systemic risk ai': ['ai_act_regulation'],
    'biometric identification': ['ai_act_regulation'],
    'social scoring': ['ai_act_regulation'],
    'digital omnibus': ['digital_omnibus_package', 'ai_act_regulation'],
    'omnibus ai': ['digital_omnibus_package', 'ai_act_regulation'],
    'omnibus digital': ['digital_omnibus_package', 'ai_act_regulation'],
    'omnibus data': ['digital_omnibus_package'],
    'omnibus gdpr': ['digital_omnibus_package'],
    'omnibus cyber': ['digital_omnibus_package'],
    'digital simplification': ['digital_omnibus_package'],
    'digital fitness check': ['digital_omnibus_package'],
    'com 2025 836': ['digital_omnibus_package'],
    'com 2025 837': ['digital_omnibus_package'],
    'com(2025) 836': ['digital_omnibus_package'],
    'com(2025) 837': ['digital_omnibus_package'],
    'cookie consent reform': ['digital_omnibus_package'],
    'eprivacy omnibus': ['digital_omnibus_package'],
    'single entry point incident': ['digital_omnibus_package'],
    'data governance act repeal': ['digital_omnibus_package'],
    'smc small mid-cap': ['digital_omnibus_package'],
    'agentic ai regulation': ['digital_omnibus_package', 'ai_act_regulation'],
    'omnibus simplification': ['digital_omnibus_package'],
    'simplificacio digital': ['digital_omnibus_package'],
    'simplificacion digital': ['digital_omnibus_package'],
    'simplification numerique': ['digital_omnibus_package'],
    'llei ia': ['ai_act_regulation'],
    'ley de ia': ['ai_act_regulation'],
    'loi sur l\'ia': ['ai_act_regulation'],
    'reglamento de ia': ['ai_act_regulation'],
    'intelligenza artificiale': ['ai_act_regulation'],
    'kunstmatige intelligentie': ['ai_act_regulation'],
    # EU Energy Policy
    'energy policy': ['eu_energy_policy'],
    'energy union': ['eu_energy_policy'],
    'energy security': ['eu_energy_policy'],
    'energy prices': ['citizens_energy_package', 'eu_energy_policy'],
    'energy cost': ['citizens_energy_package', 'eu_energy_policy'],
    'cost of energy': ['citizens_energy_package', 'eu_energy_policy'],
    'affordable energy': ['citizens_energy_package', 'eu_energy_policy'],
    'energy crisis': ['eu_energy_policy'],
    'energy poverty': ['citizens_energy_package', 'eu_energy_policy'],
    'repowereu': ['eu_energy_policy'],
    'repower eu': ['eu_energy_policy'],
    'renewable energy': ['eu_energy_policy'],
    'renewable energy directive': ['eu_energy_policy'],
    'red iii': ['eu_energy_policy'],
    'red iv': ['eu_energy_policy'],
    'clean energy': ['eu_energy_policy'],
    'clean energy package': ['eu_energy_policy', 'clean_energy_investment_strategy', 'citizens_energy_package'],
    'energy package': ['eu_energy_policy', 'clean_energy_investment_strategy', 'citizens_energy_package'],
    'commission energy package': ['eu_energy_policy', 'clean_energy_investment_strategy', 'citizens_energy_package'],
    'energy cooperation': ['eu_energy_policy'],
    'energy partnership': ['eu_energy_policy'],
    'energy community': ['eu_energy_policy', 'citizens_energy_package'],
    'energy communities': ['eu_energy_policy', 'citizens_energy_package'],
    'energy efficiency': ['eu_energy_policy'],
    'energy efficiency directive': ['eu_energy_policy'],
    'electricity market': ['eu_energy_policy'],
    'gas market': ['eu_energy_policy'],
    'gas storage': ['eu_energy_policy'],
    'hydrogen strategy': ['eu_energy_policy'],
    'hydrogen market': ['eu_energy_policy'],
    'ennoh': ['eu_energy_policy'],
    'energy task force': ['eu_energy_policy'],
    'energy union task force': ['eu_energy_policy'],
    'dg ener': ['eu_energy_policy'],
    'acer': ['eu_energy_policy'],
    'remit': ['eu_energy_policy'],
    'entso-e': ['eu_energy_policy'],
    'entso-g': ['eu_energy_policy'],
    'fit for 55 energy': ['eu_energy_policy'],
    'fit for 55': ['eu_energy_policy'],
    'cbam': ['eu_energy_policy'],
    'carbon border': ['eu_energy_policy'],
    'eu ets': ['eu_energy_policy'],
    'emissions trading': ['eu_energy_policy'],
    'ecodesign': ['ecodesign_digital_product_passport', 'eu_energy_policy'],
    'energy labelling': ['eu_energy_policy'],
    'energy label': ['eu_energy_policy'],
    'ten-e': ['eu_energy_policy'],
    'energy infrastructure': ['eu_energy_policy'],
    'trans-european energy': ['eu_energy_policy'],
    'nuclear energy': ['smr_strategy_nuclear', 'eu_energy_policy'],
    'euratom': ['smr_strategy_nuclear', 'eu_energy_policy'],
    'nuclear safety': ['smr_strategy_nuclear', 'eu_energy_policy'],
    'methane emissions': ['eu_energy_policy'],
    'carbon capture': ['eu_energy_policy'],
    'ccs': ['eu_energy_policy'],
    'offshore oil': ['eu_energy_policy'],
    'offshore gas': ['eu_energy_policy'],
    'fueleu': ['eu_energy_policy'],
    'fueleu maritime': ['eu_energy_policy'],
    'afir': ['eu_energy_policy'],
    'alternative fuels': ['eu_energy_policy'],
    'clean industrial deal': ['eu_energy_policy'],
    'epbd': ['eu_energy_policy'],
    'building energy performance': ['eu_energy_policy'],
    'social climate fund': ['citizens_energy_package', 'eu_energy_policy'],
    'energy statistics': ['eu_energy_policy'],
    'necp': ['eu_energy_policy'],
    'national energy': ['eu_energy_policy'],
    # Multilingual
    'energia': ['eu_energy_policy'],
    'politique energetique': ['eu_energy_policy'],
    'politica energetica': ['eu_energy_policy'],
    'energiebeleid': ['eu_energy_policy'],
    'energiesicherheit': ['eu_energy_policy'],
    'energie renouvelable': ['eu_energy_policy'],
    'eficiencia energetica': ['eu_energy_policy'],
    'efficienza energetica': ['eu_energy_policy'],
    'energies renovables': ['eu_energy_policy'],
    'marche de lelectricite': ['eu_energy_policy'],
    'mercado electrico': ['eu_energy_policy'],
    'energie nucleaire': ['eu_energy_policy'],
    'seguridad energetica': ['eu_energy_policy'],
    'seguretat energetica': ['eu_energy_policy'],
    'maritime strategy': ['eu_energy_policy'],
    'ports strategy': ['eu_energy_policy'],
    'maritime sector': ['eu_energy_policy'],
    'eu ports': ['eu_energy_policy'],
    'shipbuilding': ['eu_energy_policy'],
    'blue economy': ['eu_energy_policy'],
    'estrategia maritima': ['eu_energy_policy'],
    'strategie maritime': ['eu_energy_policy'],

    # SMR Strategy (COM(2026) 117)
    'small modular reactor': ['smr_strategy_nuclear', 'eu_energy_policy'],
    'smr': ['smr_strategy_nuclear', 'eu_energy_policy'],
    'smrs': ['smr_strategy_nuclear', 'eu_energy_policy'],
    'modular reactor': ['smr_strategy_nuclear'],
    'nuclear smr': ['smr_strategy_nuclear'],
    'smr alliance': ['smr_strategy_nuclear'],
    'smr industrial alliance': ['smr_strategy_nuclear'],
    'advanced modular reactor': ['smr_strategy_nuclear'],
    'amr nuclear': ['smr_strategy_nuclear'],
    'microreactor': ['smr_strategy_nuclear'],
    'smr valley': ['smr_strategy_nuclear'],
    'smr deployment': ['smr_strategy_nuclear'],
    'nuclear industrial alliance': ['smr_strategy_nuclear'],
    'com(2026) 117': ['smr_strategy_nuclear'],
    'pinc': ['smr_strategy_nuclear', 'eu_energy_policy'],
    'nuclear illustrative programme': ['smr_strategy_nuclear'],
    'reacteur modulaire': ['smr_strategy_nuclear'],
    'reactor modular': ['smr_strategy_nuclear'],
    'reattore modulare': ['smr_strategy_nuclear'],
    'modulaire reactor': ['smr_strategy_nuclear'],
    'kleinreaktor': ['smr_strategy_nuclear'],

    # Citizens Energy Package (COM(2026) 115)
    'citizens energy package': ['citizens_energy_package', 'eu_energy_policy'],
    'citizens energy': ['citizens_energy_package'],
    'energy community': ['citizens_energy_package', 'eu_energy_policy'],
    'energy communities': ['citizens_energy_package', 'eu_energy_policy'],
    'energy sharing': ['citizens_energy_package'],
    'supplier switching': ['citizens_energy_package'],
    'energy bills': ['citizens_energy_package'],
    'electricity bill': ['citizens_energy_package'],
    'electricity price': ['citizens_energy_package', 'eu_energy_policy'],
    'energy prosumer': ['citizens_energy_package'],
    'prosumer': ['citizens_energy_package'],
    'energy disconnection': ['citizens_energy_package'],
    'disconnection safeguard': ['citizens_energy_package'],
    'one-stop shop energy': ['citizens_energy_package'],
    'energy efficiency as a service': ['citizens_energy_package', 'clean_energy_investment_strategy'],
    'com(2026) 115': ['citizens_energy_package'],
    '32026h0536': ['citizens_energy_package'],
    '32026h0537': ['citizens_energy_package'],
    'paquet citoyen energie': ['citizens_energy_package'],
    'paquete ciudadano energia': ['citizens_energy_package'],
    'pacchetto cittadini energia': ['citizens_energy_package'],
    'energiepakket burgers': ['citizens_energy_package'],

    # Clean Energy Investment Strategy (COM(2026) 116)
    'clean energy investment': ['clean_energy_investment_strategy', 'eu_energy_policy'],
    'clean energy investment strategy': ['clean_energy_investment_strategy'],
    'energy investment': ['clean_energy_investment_strategy', 'eu_energy_policy'],
    'energy investment strategy': ['clean_energy_investment_strategy'],
    'cef energy': ['clean_energy_investment_strategy', 'eu_energy_policy'],
    'cef-energy': ['clean_energy_investment_strategy', 'eu_energy_policy'],
    'energy transition investment council': ['clean_energy_investment_strategy'],
    'sii fund': ['clean_energy_investment_strategy'],
    'strategic infrastructure investment': ['clean_energy_investment_strategy'],
    'grid operator balance sheet': ['clean_energy_investment_strategy'],
    'operator securitisation': ['clean_energy_investment_strategy'],
    'energy securitisation': ['clean_energy_investment_strategy'],
    'investeu energy': ['clean_energy_investment_strategy'],
    'eib energy': ['clean_energy_investment_strategy'],
    'com(2026) 116': ['clean_energy_investment_strategy'],
    'strategie investissement energie': ['clean_energy_investment_strategy'],
    'estrategia inversion energia': ['clean_energy_investment_strategy'],
    'strategia investimento energia': ['clean_energy_investment_strategy'],
    'investeringsstrategie energie': ['clean_energy_investment_strategy'],

    # 2026 Energy Package (umbrella triggers)
    'energy package 2026': ['clean_energy_investment_strategy', 'smr_strategy_nuclear', 'citizens_energy_package', 'eu_energy_policy'],
    '2026 energy package': ['clean_energy_investment_strategy', 'smr_strategy_nuclear', 'citizens_energy_package', 'eu_energy_policy'],
    'energy package march 2026': ['clean_energy_investment_strategy', 'smr_strategy_nuclear', 'citizens_energy_package'],
    'march 2026 energy': ['clean_energy_investment_strategy', 'smr_strategy_nuclear', 'citizens_energy_package'],
    'paquet energie 2026': ['clean_energy_investment_strategy', 'smr_strategy_nuclear', 'citizens_energy_package'],
    'paquete energetico 2026': ['clean_energy_investment_strategy', 'smr_strategy_nuclear', 'citizens_energy_package'],

    'north sea summit': ['eu_energy_policy'],
    'north sea energy': ['eu_energy_policy'],
    'savings and investments union': ['eu_energy_policy', 'financial_supervision_eba'],

    # EP Plenary March 2026
    'ep debate': ['ep_plenary_march_2026'],
    'ep debates': ['ep_plenary_march_2026'],
    'parliament debate': ['ep_plenary_march_2026'],
    'parliament debates': ['ep_plenary_march_2026'],
    'european parliament debate': ['ep_plenary_march_2026'],
    'debates in parliament': ['ep_plenary_march_2026'],
    'debates in the european parliament': ['ep_plenary_march_2026'],
    'plenary debate': ['ep_plenary_march_2026'],
    'plenary debates': ['ep_plenary_march_2026'],
    'plenary': ['ep_plenary_march_2026'],
    'plenary agenda': ['ep_plenary_march_2026'],
    'plenary week': ['ep_plenary_march_2026'],
    'strasbourg': ['ep_plenary_march_2026'],
    'plenary session': ['ep_plenary_march_2026'],
    'plenary vote': ['ep_plenary_march_2026'],
    'ep plenary': ['ep_plenary_march_2026'],
    'parliament plenary': ['ep_plenary_march_2026'],
    'this week parliament': ['ep_plenary_march_2026'],
    'this week ep': ['ep_plenary_march_2026'],
    'plenaria': ['ep_plenary_march_2026'],
    'session pleniere': ['ep_plenary_march_2026'],
    'plenaire vergadering': ['ep_plenary_march_2026'],
    'insolvency': ['ep_plenary_march_2026'],
    'insolvency law': ['ep_plenary_march_2026'],
    'emil radev': ['ep_plenary_march_2026'],
    'talent pool': ['ep_plenary_march_2026'],
    'eu talent pool': ['ep_plenary_march_2026'],
    'abir al-sahlani': ['ep_plenary_march_2026'],
    'al-sahlani': ['ep_plenary_march_2026'],
    'ecb vice-president': ['ep_plenary_march_2026'],
    'eba chairperson': ['ep_plenary_march_2026'],
    'european chief prosecutor': ['ep_plenary_march_2026'],
    'chief prosecutor': ['ep_plenary_march_2026'],
    'return directive': ['ep_plenary_march_2026'],
    'return rules': ['ep_plenary_march_2026'],
    'eu return': ['ep_plenary_march_2026'],
    'defence single market': ['ep_plenary_march_2026', 'safe_rearm_europe'],
    'defence projects': ['ep_plenary_march_2026', 'safe_rearm_europe'],
    'single market defence': ['ep_plenary_march_2026', 'safe_rearm_europe'],
    'public access documents': ['ep_plenary_march_2026'],
    'regulation 1049/2001': ['ep_plenary_march_2026'],
    'package travel': ['ep_plenary_march_2026', 'eu_consumer_protection'],

    # Tobacco Taxation Directive recast (ECON, 2025/0580(CNS))
    'tobacco taxation': ['ep_plenary_march_2026'],
    'tobacco directive': ['ep_plenary_march_2026'],
    'tobacco excise': ['ep_plenary_march_2026'],
    'excise duty tobacco': ['ep_plenary_march_2026'],
    'tomas kubin': ['ep_plenary_march_2026'],
    '2025/0580': ['ep_plenary_march_2026'],
    'pe784.398': ['ep_plenary_march_2026'],

    # Single Market and Customs Programme 2028-2034 (IMCO, 2025/0590(COD))
    'single market programme': ['ep_plenary_march_2026'],
    'customs programme': ['ep_plenary_march_2026'],
    'single market customs 2028': ['ep_plenary_march_2026'],
    'adnan dibrani': ['ep_plenary_march_2026'],
    '2025/0590': ['ep_plenary_march_2026'],
    'pe785.258': ['ep_plenary_march_2026'],

    # AFCO Defence Union report (2025/2212(INI))
    'defence union': ['ep_plenary_march_2026', 'safe_rearm_europe'],
    'common european defence': ['ep_plenary_march_2026', 'safe_rearm_europe'],
    'salvatore de meo': ['ep_plenary_march_2026'],
    '2025/2212': ['ep_plenary_march_2026'],

    # Copyright and Generative AI
    'copyright ai': ['copyright_generative_ai'],
    'copyright generative': ['copyright_generative_ai'],
    'copyright and ai': ['copyright_generative_ai'],
    'generative ai copyright': ['copyright_generative_ai'],
    'axel voss': ['copyright_generative_ai'],
    'a10-0019/2026': ['copyright_generative_ai'],
    '2025/2058': ['copyright_generative_ai'],
    'ai training data': ['copyright_generative_ai'],
    'ai copyright': ['copyright_generative_ai'],
    'text data mining': ['copyright_generative_ai'],
    'tdm opt-out': ['copyright_generative_ai'],
    'ai training copyright': ['copyright_generative_ai'],
    'genai copyright': ['copyright_generative_ai'],
    'copyright numérique': ['copyright_generative_ai'],
    'derechos de autor ia': ['copyright_generative_ai'],
    'diritti autore ia': ['copyright_generative_ai'],

    # EU Housing Crisis
    'housing crisis': ['eu_housing_crisis'],
    'housing policy': ['eu_housing_crisis'],
    'housing affordability': ['eu_housing_crisis'],
    'affordable housing': ['eu_housing_crisis'],
    'social housing': ['eu_housing_crisis'],
    'hous committee': ['eu_housing_crisis'],
    'housing committee': ['eu_housing_crisis'],
    'a10-0025/2026': ['eu_housing_crisis'],
    '2025/2070': ['eu_housing_crisis'],
    'borja gimenez': ['eu_housing_crisis'],
    'gimenez larraz': ['eu_housing_crisis'],
    'housing simplification': ['eu_housing_crisis'],
    'rent prices': ['eu_housing_crisis'],
    'housing permit': ['eu_housing_crisis'],
    'homelessness eu': ['eu_housing_crisis'],
    'energy poverty housing': ['eu_housing_crisis'],
    'crise du logement': ['eu_housing_crisis'],
    'crisis vivienda': ['eu_housing_crisis'],
    'crisi abitativa': ['eu_housing_crisis'],
    'woningcrisis': ['eu_housing_crisis'],

    # ESPR and Digital Product Passport
    'digital product passport': ['ecodesign_digital_product_passport'],
    'product passport': ['ecodesign_digital_product_passport'],
    'dpp': ['ecodesign_digital_product_passport'],
    'espr': ['ecodesign_digital_product_passport'],
    'ecodesign regulation': ['ecodesign_digital_product_passport'],
    'ecodesign requirements': ['ecodesign_digital_product_passport'],
    'sustainable products regulation': ['ecodesign_digital_product_passport'],
    '2024/1781': ['ecodesign_digital_product_passport'],
    '32024r1781': ['ecodesign_digital_product_passport'],
    'regulation 2024/1781': ['ecodesign_digital_product_passport'],
    '2022/0095': ['ecodesign_digital_product_passport'],
    'dpp registry': ['ecodesign_digital_product_passport'],
    'product registry': ['ecodesign_digital_product_passport'],
    'eprel': ['ecodesign_digital_product_passport'],
    'energy labelling registry': ['ecodesign_digital_product_passport'],
    'battery passport': ['ecodesign_digital_product_passport'],
    'alessandra moretti': ['ecodesign_digital_product_passport'],
    'ecodesign forum': ['ecodesign_digital_product_passport'],
    'unsold products': ['ecodesign_digital_product_passport'],
    'destruction unsold': ['ecodesign_digital_product_passport'],
    'green public procurement': ['ecodesign_digital_product_passport'],
    'circular economy products': ['ecodesign_digital_product_passport'],
    'product sustainability': ['ecodesign_digital_product_passport'],
    'recycled content': ['ecodesign_digital_product_passport'],
    'product durability': ['ecodesign_digital_product_passport'],
    'reparability': ['ecodesign_digital_product_passport'],
    'right to repair': ['ecodesign_digital_product_passport'],
    'gs1': ['ecodesign_digital_product_passport'],
    # Multilingual
    'passeport numerique produit': ['ecodesign_digital_product_passport'],
    'passaport digital producte': ['ecodesign_digital_product_passport'],
    'pasaporte digital producto': ['ecodesign_digital_product_passport'],
    'passaporto digitale prodotto': ['ecodesign_digital_product_passport'],
    'digitaal productpaspoort': ['ecodesign_digital_product_passport'],

    # Committee of the Regions (CoR)
    'committee of the regions': ['committee_of_the_regions'],
    'committee of regions': ['committee_of_the_regions'],
    'cor plenary': ['committee_of_the_regions'],
    'cor opinion': ['committee_of_the_regions'],
    'cor session': ['committee_of_the_regions'],
    'comite de les regions': ['committee_of_the_regions'],
    'comite de las regiones': ['committee_of_the_regions'],
    'comite des regions': ['committee_of_the_regions'],
    'comitato delle regioni': ['committee_of_the_regions'],
    'comite van de regio': ['committee_of_the_regions'],
    'ausschuss der regionen': ['committee_of_the_regions'],
    'regional authorities': ['committee_of_the_regions'],
    'local authorities eu': ['committee_of_the_regions'],
    'subsidiarity': ['committee_of_the_regions'],
    'territorial cohesion': ['committee_of_the_regions'],
    'eu regions week': ['committee_of_the_regions'],
    'regpex': ['committee_of_the_regions'],
    'egtc': ['committee_of_the_regions'],
    'kata tutto': ['committee_of_the_regions'],
    'cor civex': ['committee_of_the_regions'],
    'cor coter': ['committee_of_the_regions'],
    'cor econ': ['committee_of_the_regions'],
    'cor enve': ['committee_of_the_regions'],
    'cor nat': ['committee_of_the_regions'],
    'cor sedec': ['committee_of_the_regions'],

    # EU Social Dialogue and Collective Bargaining
    'social dialogue': ['eu_social_dialogue'],
    'european social dialogue': ['eu_social_dialogue'],
    'collective bargaining': ['eu_social_dialogue'],
    'collective agreement': ['eu_social_dialogue'],
    'social partners': ['eu_social_dialogue'],
    'etuc': ['eu_social_dialogue'],
    'businesseurope': ['eu_social_dialogue'],
    'sgi europe': ['eu_social_dialogue'],
    'smeunited': ['eu_social_dialogue'],
    'european works council': ['eu_social_dialogue'],
    'works council': ['eu_social_dialogue'],
    'ewc directive': ['eu_social_dialogue'],
    'posted workers': ['eu_social_dialogue'],
    'posting of workers': ['eu_social_dialogue'],
    'minimum wages directive': ['eu_social_dialogue'],
    'adequate minimum wages': ['eu_social_dialogue'],
    'pay transparency': ['eu_social_dialogue'],
    'viking line': ['eu_social_dialogue'],
    'laval': ['eu_social_dialogue'],
    'albany': ['eu_social_dialogue'],
    'article 154 tfeu': ['eu_social_dialogue'],
    'article 155 tfeu': ['eu_social_dialogue'],
    'dg empl': ['eu_social_dialogue'],
    'epsco': ['eu_social_dialogue'],
    'european labour authority': ['eu_social_dialogue'],
    'ela': ['eu_social_dialogue'],
    'eurofound': ['eu_social_dialogue'],
    'industrial relations': ['eu_social_dialogue'],
    'pillar of social rights': ['eu_social_dialogue', 'employment_future_of_work'],
    'worker information': ['eu_social_dialogue'],
    'worker consultation': ['eu_social_dialogue'],
    # Multilingual
    'dialogue social': ['eu_social_dialogue'],
    'dialogo social': ['eu_social_dialogue'],
    'dialeg social': ['eu_social_dialogue'],
    'sociale dialoog': ['eu_social_dialogue'],
    'negociacion colectiva': ['eu_social_dialogue'],
    'negociacio collectiva': ['eu_social_dialogue'],
    'negociation collective': ['eu_social_dialogue'],
    'contrattazione collettiva': ['eu_social_dialogue'],
    'salaire minimum': ['eu_social_dialogue'],
    'salario minimo': ['eu_social_dialogue'],
    'salari minim': ['eu_social_dialogue'],
    'minimumloon': ['eu_social_dialogue'],
    'travailleurs detaches': ['eu_social_dialogue'],
    'trabajadores desplazados': ['eu_social_dialogue'],
    'treballadors desplacats': ['eu_social_dialogue'],
    'val duchesse': ['eu_social_dialogue'],
    'framework agreement': ['eu_social_dialogue'],
    'sectoral dialogue': ['eu_social_dialogue'],
    'decision 98/500': ['eu_social_dialogue'],
    'telework agreement': ['eu_social_dialogue'],
    'parental leave directive': ['eu_social_dialogue'],
    'fixed-term work': ['eu_social_dialogue'],
    'part-time work directive': ['eu_social_dialogue'],
    'temporary agency work': ['eu_social_dialogue'],

    # EUR-Lex Glossary of EU Legal Terms
    'glossary': ['eu_glossary_eurlex'],
    'acquis': ['eu_glossary_eurlex'],
    'acquis communautaire': ['eu_glossary_eurlex'],
    'co-decision': ['eu_glossary_eurlex'],
    'codecision': ['eu_glossary_eurlex'],
    'comitology': ['eu_glossary_eurlex'],
    'subsidiarity': ['eu_glossary_eurlex'],
    'proportionality': ['eu_glossary_eurlex'],
    'qmv': ['eu_glossary_eurlex'],
    'qualified majority voting': ['eu_glossary_eurlex'],
    'ordinary legislative procedure': ['eu_glossary_eurlex'],
    'special legislative procedure': ['eu_glossary_eurlex'],
    'direct effect': ['eu_glossary_eurlex'],
    'supremacy': ['eu_glossary_eurlex'],
    'primacy': ['eu_glossary_eurlex'],
    'preliminary ruling': ['eu_glossary_eurlex'],
    'infringement procedure': ['eu_glossary_eurlex'],
    'delegated act': ['eu_glossary_eurlex'],
    'implementing act': ['eu_glossary_eurlex'],
    'transposition': ['eu_glossary_eurlex'],
    'opt-out': ['eu_glossary_eurlex'],
    'enhanced cooperation': ['eu_glossary_eurlex'],
    'passerelle clause': ['eu_glossary_eurlex'],
    'yellow card': ['eu_glossary_eurlex'],
    'orange card': ['eu_glossary_eurlex'],
    'eu legal term': ['eu_glossary_eurlex'],
    'eu terminology': ['eu_glossary_eurlex'],
    'eu definition': ['eu_glossary_eurlex'],

    # EU Fisheries Policy
    'fisheries': ['eu_fisheries_policy'],
    'common fisheries policy': ['eu_fisheries_policy'],
    'cfp': ['eu_fisheries_policy'],
    'fishing quota': ['eu_fisheries_policy'],
    'tac': ['eu_fisheries_policy'],
    'total allowable catch': ['eu_fisheries_policy'],
    'emfaf': ['eu_fisheries_policy'],
    'illegal fishing': ['eu_fisheries_policy'],
    'iuu fishing': ['eu_fisheries_policy'],
    'discards': ['eu_fisheries_policy'],
    'landing obligation': ['eu_fisheries_policy'],
    'dg mare': ['eu_fisheries_policy'],
    'fisheries partnership': ['eu_fisheries_policy'],
    'aquaculture': ['eu_fisheries_policy'],
    'maximum sustainable yield': ['eu_fisheries_policy'],
    'msy': ['eu_fisheries_policy'],
    'pesca': ['eu_fisheries_policy'],
    'peche': ['eu_fisheries_policy'],
    'visserij': ['eu_fisheries_policy'],

    # EU Agriculture Policy
    'agriculture': ['eu_agriculture_policy'],
    'common agricultural policy': ['eu_agriculture_policy'],
    'cap': ['eu_agriculture_policy'],
    'farm to fork': ['eu_agriculture_policy'],
    'direct payments': ['eu_agriculture_policy'],
    'pillar i': ['eu_agriculture_policy'],
    'pillar ii': ['eu_agriculture_policy'],
    'rural development': ['eu_agriculture_policy'],
    'dg agri': ['eu_agriculture_policy'],
    'market intervention': ['eu_agriculture_policy'],
    'agri-food': ['eu_agriculture_policy'],
    'agrifood': ['eu_agriculture_policy'],
    'organic farming': ['eu_agriculture_policy'],
    'pesticides': ['eu_agriculture_policy'],
    'sur regulation': ['eu_agriculture_policy'],
    'eco-schemes': ['eu_agriculture_policy'],
    'cap strategic plan': ['eu_agriculture_policy'],
    'agricultura': ['eu_agriculture_policy'],
    'landbouw': ['eu_agriculture_policy'],
    'politique agricole': ['eu_agriculture_policy'],

    # EU Humanitarian Aid and Civil Protection
    'humanitarian aid': ['eu_humanitarian_civil_protection'],
    'civil protection': ['eu_humanitarian_civil_protection'],
    'dg echo': ['eu_humanitarian_civil_protection'],
    'echo': ['eu_humanitarian_civil_protection'],
    'eu aid': ['eu_humanitarian_civil_protection'],
    'crisis response': ['eu_humanitarian_civil_protection'],
    'eu civil protection mechanism': ['eu_humanitarian_civil_protection'],
    'ucpm': ['eu_humanitarian_civil_protection'],
    'resceu': ['eu_humanitarian_civil_protection'],
    'ercc': ['eu_humanitarian_civil_protection'],
    'emergency response coordination': ['eu_humanitarian_civil_protection'],
    'ajuda humanitaria': ['eu_humanitarian_civil_protection'],
    'aide humanitaire': ['eu_humanitarian_civil_protection'],
    'ayuda humanitaria': ['eu_humanitarian_civil_protection'],
    'proteccion civil': ['eu_humanitarian_civil_protection'],
    'protection civile': ['eu_humanitarian_civil_protection'],

    # EU Trade Policy
    'trade policy': ['eu_trade_policy'],
    'common commercial policy': ['eu_trade_policy'],
    'free trade agreement': ['eu_trade_policy'],
    'fta': ['eu_trade_policy'],
    'trade agreement': ['eu_trade_policy'],
    'trade defence': ['eu_trade_policy'],
    'anti-dumping': ['eu_trade_policy'],
    'countervailing duties': ['eu_trade_policy'],
    'safeguard measures': ['eu_trade_policy'],
    'dg trade': ['eu_trade_policy'],
    'wto': ['eu_trade_policy'],
    'gsp': ['eu_trade_policy'],
    'generalised scheme of preferences': ['eu_trade_policy'],
    'mercosur': ['eu_trade_policy'],
    'ceta': ['eu_trade_policy'],
    'eu-uk trade': ['eu_trade_policy'],
    'rules of origin': ['eu_trade_policy'],
    'trade sanctions': ['eu_trade_policy'],
    'economic coercion': ['eu_trade_policy'],
    'foreign subsidies regulation': ['eu_trade_policy'],
    'fsr': ['eu_trade_policy'],
    'international procurement instrument': ['eu_trade_policy'],
    'ipi': ['eu_trade_policy'],
    'politique commerciale': ['eu_trade_policy'],
    'politica comercial': ['eu_trade_policy'],
    'handelsbeleid': ['eu_trade_policy'],

    # EU Consumer Protection
    'consumer protection': ['eu_consumer_protection'],
    'consumer rights': ['eu_consumer_protection'],
    'consumer rights directive': ['eu_consumer_protection'],
    'product safety': ['eu_consumer_protection'],
    'general product safety': ['eu_consumer_protection'],
    'dg just': ['eu_consumer_protection', 'eu_justice_security'],
    'unfair commercial practices': ['eu_consumer_protection'],
    'consumer credit': ['eu_consumer_protection'],
    'package travel': ['eu_consumer_protection'],
    'passenger rights': ['eu_consumer_protection'],
    'class action': ['eu_consumer_protection'],
    'representative action': ['eu_consumer_protection'],
    'consumer adr': ['eu_consumer_protection'],
    'digital fairness': ['eu_consumer_protection'],
    'dark patterns': ['eu_consumer_protection'],
    'green claims': ['eu_consumer_protection'],
    'greenwashing': ['eu_consumer_protection'],
    'proteccion del consumidor': ['eu_consumer_protection'],
    'protection des consommateurs': ['eu_consumer_protection'],
    'consumentenbescherming': ['eu_consumer_protection'],

    # EU Culture Policy
    'culture policy': ['eu_culture_policy'],
    'creative europe': ['eu_culture_policy'],
    'dg eac': ['eu_culture_policy', 'eu_education_youth_sport'],
    'cultural heritage': ['eu_culture_policy'],
    'media programme': ['eu_culture_policy'],
    'media sub-programme': ['eu_culture_policy'],
    'european capital of culture': ['eu_culture_policy'],
    'cultural diversity': ['eu_culture_policy'],
    'cultura': ['eu_culture_policy'],
    'politique culturelle': ['eu_culture_policy'],
    'cultuurbeleid': ['eu_culture_policy'],

    # EU Development Cooperation
    'development cooperation': ['eu_development_cooperation'],
    'dg intpa': ['eu_development_cooperation'],
    'dg devco': ['eu_development_cooperation'],
    'ndici': ['eu_development_cooperation'],
    'global europe': ['eu_development_cooperation'],
    'neighbourhood': ['eu_development_cooperation'],
    'european development fund': ['eu_development_cooperation'],
    'edf': ['eu_development_cooperation'],
    'oda': ['eu_development_cooperation'],
    'official development assistance': ['eu_development_cooperation'],
    'global gateway': ['eu_development_cooperation'],
    'team europe': ['eu_development_cooperation'],
    'acp': ['eu_development_cooperation'],
    'cotonou': ['eu_development_cooperation'],
    'samoa agreement': ['eu_development_cooperation'],
    'cooperacion al desarrollo': ['eu_development_cooperation'],
    'cooperation au developpement': ['eu_development_cooperation'],
    'ontwikkelingssamenwerking': ['eu_development_cooperation'],

    # EU Customs Policy
    'customs': ['eu_customs_policy'],
    'customs union': ['eu_customs_policy'],
    'customs code': ['eu_customs_policy'],
    'union customs code': ['eu_customs_policy'],
    'ucc': ['eu_customs_policy'],
    'dg taxud': ['eu_customs_policy', 'eu_taxation_policy'],
    'common external tariff': ['eu_customs_policy'],
    'customs reform': ['eu_customs_policy'],
    'single window': ['eu_customs_policy'],
    'eu customs authority': ['eu_customs_policy'],
    'aeo': ['eu_customs_policy'],
    'authorised economic operator': ['eu_customs_policy'],
    'customs valuation': ['eu_customs_policy'],
    'customs classification': ['eu_customs_policy'],
    'combined nomenclature': ['eu_customs_policy'],
    'taric': ['eu_customs_policy'],
    'aduanas': ['eu_customs_policy'],
    'douane': ['eu_customs_policy'],

    # EU Human Rights
    'human rights': ['eu_human_rights'],
    'fundamental rights': ['eu_human_rights'],
    'charter of fundamental rights': ['eu_human_rights'],
    'fra': ['eu_human_rights'],
    'european convention human rights': ['eu_human_rights'],
    'echr': ['eu_human_rights'],
    'rule of law': ['eu_human_rights'],
    'rule of law mechanism': ['eu_human_rights'],
    'democracy': ['eu_human_rights'],
    'article 7 teu': ['eu_human_rights'],
    'conditionality regulation': ['eu_human_rights'],
    'dg just human rights': ['eu_human_rights'],
    'equality': ['eu_human_rights'],
    'anti-discrimination': ['eu_human_rights'],
    'gender equality': ['eu_human_rights'],
    'lgbtiq': ['eu_human_rights'],
    'roma inclusion': ['eu_human_rights'],
    'derechos humanos': ['eu_human_rights'],
    'droits de lhomme': ['eu_human_rights'],
    'mensenrechten': ['eu_human_rights'],
    'drets humans': ['eu_human_rights'],

    # EU Education, Youth and Sport
    'education policy': ['eu_education_youth_sport'],
    'erasmus': ['eu_education_youth_sport'],
    'erasmus+': ['eu_education_youth_sport'],
    'european education area': ['eu_education_youth_sport'],
    'bologna process': ['eu_education_youth_sport'],
    'ects': ['eu_education_youth_sport'],
    'european solidarity corps': ['eu_education_youth_sport'],
    'youth guarantee': ['eu_education_youth_sport', 'employment_future_of_work'],
    'digital education': ['eu_education_youth_sport'],
    'vocational training': ['eu_education_youth_sport'],
    'cedefop': ['eu_education_youth_sport'],
    'european universities': ['eu_education_youth_sport'],
    'educacion': ['eu_education_youth_sport'],
    'education': ['eu_education_youth_sport'],
    'onderwijs': ['eu_education_youth_sport'],

    # EU Enlargement Policy
    'enlargement': ['eu_enlargement_policy'],
    'accession': ['eu_enlargement_policy'],
    'candidate country': ['eu_enlargement_policy'],
    'dg near': ['eu_enlargement_policy'],
    'western balkans': ['eu_enlargement_policy'],
    'acquis chapters': ['eu_enlargement_policy'],
    'screening process': ['eu_enlargement_policy'],
    'copenhagen criteria': ['eu_enlargement_policy'],
    'stabilisation and association': ['eu_enlargement_policy'],
    'saa': ['eu_enlargement_policy'],
    'pre-accession': ['eu_enlargement_policy'],
    'ipa': ['eu_enlargement_policy'],
    'ipa iii': ['eu_enlargement_policy'],
    'ukraine accession': ['eu_enlargement_policy'],
    'moldova accession': ['eu_enlargement_policy'],
    'elargissement': ['eu_enlargement_policy'],
    'ampliacion': ['eu_enlargement_policy'],
    'uitbreiding': ['eu_enlargement_policy'],

    # EU Enterprise and SME Policy
    'enterprise': ['eu_enterprise_sme_policy'],
    'sme': ['eu_enterprise_sme_policy'],
    'small and medium': ['eu_enterprise_sme_policy'],
    'sme strategy': ['eu_enterprise_sme_policy'],
    'single market': ['eu_enterprise_sme_policy', 'eu_internal_market'],
    'dg grow': ['eu_enterprise_sme_policy', 'eu_internal_market'],
    'late payment directive': ['eu_enterprise_sme_policy'],
    'sme envoy': ['eu_enterprise_sme_policy'],
    'startup': ['eu_enterprise_sme_policy'],
    'scale-up': ['eu_enterprise_sme_policy'],
    'industrial strategy': ['eu_enterprise_sme_policy'],
    'sme relief package': ['eu_enterprise_sme_policy'],
    'think small first': ['eu_enterprise_sme_policy'],
    'empresa': ['eu_enterprise_sme_policy'],
    'entreprise': ['eu_enterprise_sme_policy'],
    'pyme': ['eu_enterprise_sme_policy'],
    'pme': ['eu_enterprise_sme_policy'],
    'mkb': ['eu_enterprise_sme_policy'],

    # EU Environment and Climate
    'environment policy': ['eu_environment_climate'],
    'green deal': ['eu_environment_climate'],
    'european green deal': ['eu_environment_climate'],
    'climate law': ['eu_environment_climate'],
    'climate neutrality': ['eu_environment_climate'],
    'nature restoration': ['eu_environment_climate'],
    'biodiversity': ['eu_environment_climate'],
    'biodiversity strategy': ['eu_environment_climate'],
    'circular economy': ['eu_environment_climate'],
    'waste framework directive': ['eu_environment_climate'],
    'packaging regulation': ['eu_environment_climate'],
    'water framework directive': ['eu_environment_climate'],
    'air quality': ['eu_environment_climate'],
    'ambient air quality directive': ['eu_environment_climate'],
    'industrial emissions directive': ['eu_environment_climate'],
    'ied': ['eu_environment_climate'],
    'seveso directive': ['eu_environment_climate'],
    'environmental impact assessment': ['eu_environment_climate'],
    'eia directive': ['eu_environment_climate'],
    'natura 2000': ['eu_environment_climate'],
    'habitats directive': ['eu_environment_climate'],
    'birds directive': ['eu_environment_climate'],
    'dg env': ['eu_environment_climate'],
    'dg clima': ['eu_environment_climate', 'eu_energy_policy'],
    'environmental liability': ['eu_environment_climate'],
    'deforestation regulation': ['eu_environment_climate'],
    'eudr': ['eu_environment_climate'],
    'medio ambiente': ['eu_environment_climate'],
    'environnement': ['eu_environment_climate'],
    'milieu': ['eu_environment_climate'],
    'medi ambient': ['eu_environment_climate'],
    'ambiente': ['eu_environment_climate'],

    # EU Taxation Policy
    'taxation': ['eu_taxation_policy'],
    'tax policy': ['eu_taxation_policy'],
    'vat': ['eu_taxation_policy'],
    'vat directive': ['eu_taxation_policy'],
    'excise': ['eu_taxation_policy'],
    'excise duty': ['eu_taxation_policy'],
    'minimum tax': ['eu_taxation_policy'],
    'pillar one': ['eu_taxation_policy'],
    'pillar two': ['eu_taxation_policy'],
    'beps': ['eu_taxation_policy'],
    'anti-tax avoidance': ['eu_taxation_policy'],
    'atad': ['eu_taxation_policy'],
    'dac': ['eu_taxation_policy'],
    'directive on administrative cooperation': ['eu_taxation_policy'],
    'unshell directive': ['eu_taxation_policy'],
    'debra': ['eu_taxation_policy'],
    'befit': ['eu_taxation_policy'],
    'transfer pricing': ['eu_taxation_policy'],
    'head': ['eu_taxation_policy'],
    'carbon tax': ['eu_taxation_policy'],
    'energy taxation directive': ['eu_taxation_policy'],
    'tobacco taxation': ['eu_taxation_policy'],
    'fiscalidad': ['eu_taxation_policy'],
    'fiscalite': ['eu_taxation_policy'],
    'belastingbeleid': ['eu_taxation_policy'],
    'fiscalitat': ['eu_taxation_policy'],

    # EU Fraud and Corruption
    'fraud': ['eu_fraud_corruption'],
    'anti-fraud': ['eu_fraud_corruption'],
    'pif directive': ['eu_fraud_corruption'],
    'eu budget fraud': ['eu_fraud_corruption'],
    'corruption': ['eu_fraud_corruption'],
    'whistleblower': ['eu_fraud_corruption'],
    'whistleblowing': ['eu_fraud_corruption'],
    'whistleblower directive': ['eu_fraud_corruption'],
    'money laundering': ['eu_fraud_corruption'],
    'amld': ['eu_fraud_corruption'],
    'anti-money laundering': ['eu_fraud_corruption'],
    'aml package': ['eu_fraud_corruption'],
    'amla': ['eu_fraud_corruption'],
    'terrorist financing': ['eu_fraud_corruption'],
    'beneficial ownership': ['eu_fraud_corruption'],
    'fraude': ['eu_fraud_corruption'],
    'corruption': ['eu_fraud_corruption'],
    'blanchiment': ['eu_fraud_corruption'],
    'witwassen': ['eu_fraud_corruption'],

    # EU Justice and Security
    'justice': ['eu_justice_security'],
    'area of freedom security and justice': ['eu_justice_security'],
    'afsj': ['eu_justice_security'],
    'schengen': ['eu_justice_security'],
    'asylum': ['eu_justice_security'],
    'migration': ['eu_justice_security'],
    'migration pact': ['eu_justice_security'],
    'frontex': ['eu_justice_security'],
    'europol': ['eu_justice_security'],
    'eurojust': ['eu_justice_security'],
    'european arrest warrant': ['eu_justice_security'],
    'mutual recognition': ['eu_justice_security'],
    'dg home': ['eu_justice_security'],
    'data protection': ['eu_justice_security'],
    'gdpr': ['eu_justice_security'],
    'law enforcement': ['eu_justice_security'],
    'eu security union': ['eu_justice_security'],
    'counter-terrorism': ['eu_justice_security'],
    'organised crime': ['eu_justice_security'],
    'cybersecurity': ['eu_justice_security'],
    'seguridad': ['eu_justice_security'],
    'securite': ['eu_justice_security'],
    'veiligheid': ['eu_justice_security'],
    'justicia': ['eu_justice_security'],

    # EU Internal Market
    'internal market': ['eu_internal_market'],
    'single market act': ['eu_internal_market'],
    'four freedoms': ['eu_internal_market'],
    'free movement of goods': ['eu_internal_market'],
    'free movement of services': ['eu_internal_market'],
    'free movement of capital': ['eu_internal_market'],
    'free movement of workers': ['eu_internal_market'],
    'services directive': ['eu_internal_market'],
    'mutual recognition principle': ['eu_internal_market'],
    'standardisation': ['eu_internal_market'],
    'ce marking': ['eu_internal_market'],
    'market surveillance': ['eu_internal_market'],
    'digital single market': ['eu_internal_market'],
    'dsa': ['eu_internal_market'],
    'dma': ['eu_internal_market'],
    'digital services act': ['eu_internal_market'],
    'digital markets act': ['eu_internal_market'],
    'single market emergency instrument': ['eu_internal_market'],
    'smei': ['eu_internal_market'],
    'marche interieur': ['eu_internal_market'],
    'mercado interior': ['eu_internal_market'],
    'mercat interior': ['eu_internal_market'],
    'interne markt': ['eu_internal_market'],

    # EU Foreign and Security Policy
    'cfsp': ['eu_foreign_security_policy'],
    'common foreign and security policy': ['eu_foreign_security_policy'],
    'csdp': ['eu_foreign_security_policy'],
    'common security and defence': ['eu_foreign_security_policy'],
    'high representative': ['eu_foreign_security_policy'],
    'eeas': ['eu_foreign_security_policy'],
    'european external action service': ['eu_foreign_security_policy'],
    'eu sanctions': ['eu_foreign_security_policy'],
    'restrictive measures': ['eu_foreign_security_policy'],
    'eu defence': ['eu_foreign_security_policy'],
    'pesco': ['eu_foreign_security_policy'],
    'permanent structured cooperation': ['eu_foreign_security_policy'],
    'european defence fund': ['eu_foreign_security_policy'],
    'edf defence': ['eu_foreign_security_policy'],
    'eu military': ['eu_foreign_security_policy'],
    'eu missions': ['eu_foreign_security_policy'],
    'strategic compass': ['eu_foreign_security_policy'],
    'european peace facility': ['eu_foreign_security_policy'],
    'arms exports': ['eu_foreign_security_policy'],
    'white paper defence': ['eu_foreign_security_policy'],
    'readiness 2030': ['eu_foreign_security_policy'],
    'safe': ['eu_foreign_security_policy'],
    'politique etrangere': ['eu_foreign_security_policy'],
    'politica exterior': ['eu_foreign_security_policy'],
    'buitenlands beleid': ['eu_foreign_security_policy'],

    # EU External Relations
    'external relations': ['eu_external_relations'],
    'association agreement': ['eu_external_relations'],
    'partnership agreement': ['eu_external_relations'],
    'eu-africa': ['eu_external_relations'],
    'eu-china': ['eu_external_relations'],
    'eu-us': ['eu_external_relations'],
    'transatlantic': ['eu_external_relations'],
    'eastern partnership': ['eu_external_relations'],
    'european neighbourhood': ['eu_external_relations'],
    'enp': ['eu_external_relations'],
    'union for the mediterranean': ['eu_external_relations'],
    'eu-latin america': ['eu_external_relations'],
    'eu-asean': ['eu_external_relations'],
    'relaciones exteriores': ['eu_external_relations'],
    'relations exterieures': ['eu_external_relations'],
    'buitenlandse betrekkingen': ['eu_external_relations'],

    # EU Public Health
    'public health': ['eu_public_health'],
    'health union': ['eu_public_health'],
    'european health union': ['eu_public_health'],
    'dg sante': ['eu_public_health'],
    'ema': ['eu_public_health'],
    'european medicines agency': ['eu_public_health'],
    'ecdc': ['eu_public_health'],
    'hera': ['eu_public_health'],
    'pharmaceutical legislation': ['eu_public_health'],
    'pharmaceutical strategy': ['eu_public_health'],
    'health technology assessment': ['eu_public_health'],
    'hta regulation': ['eu_public_health'],
    'cross-border health': ['eu_public_health'],
    'europe beating cancer': ['eu_public_health'],
    'cancer plan': ['eu_public_health'],
    'mental health': ['eu_public_health'],
    'antimicrobial resistance': ['eu_public_health'],
    'amr': ['eu_public_health'],
    'critical medicines': ['eu_public_health'],
    'salud publica': ['eu_public_health'],
    'sante publique': ['eu_public_health'],
    'volksgezondheid': ['eu_public_health'],
    'salut publica': ['eu_public_health'],
    # DG GROW Databases
    'dg grow': ['dg_grow_databases'],
    'notified body': ['dg_grow_databases'],
    'notified bodies': ['dg_grow_databases'],
    'nando': ['dg_grow_databases'],
    'conformity assessment': ['dg_grow_databases'],
    'ce marking': ['dg_grow_databases'],
    'ce mark': ['dg_grow_databases'],
    'tris': ['dg_grow_databases'],
    'technical regulation': ['dg_grow_databases'],
    'technical regulations': ['dg_grow_databases'],
    'standstill period': ['dg_grow_databases'],
    '2015/1535': ['dg_grow_databases'],
    'tbt notification': ['dg_grow_databases'],
    'trade barrier': ['dg_grow_databases'],
    'trade barriers': ['dg_grow_databases'],
    'technical barriers to trade': ['dg_grow_databases'],
    'industrial ecosystem': ['dg_grow_databases'],
    'industrial ecosystems': ['dg_grow_databases'],
    'emi monitor': ['dg_grow_databases'],
    'single market compliance': ['dg_grow_databases'],
    'product safety': ['dg_grow_databases'],
    'market surveillance': ['dg_grow_databases'],
    'cosing': ['dg_grow_databases'],
    'icsms': ['dg_grow_databases'],
    'regulated profession': ['dg_grow_databases'],
    'enorm': ['dg_grow_databases'],
    'standardisation request': ['dg_grow_databases'],
    'harmonised standard': ['dg_grow_databases'],
    'machinery directive': ['dg_grow_databases'],
    'low voltage directive': ['dg_grow_databases'],
    'pressure equipment': ['dg_grow_databases'],
    'medical device regulation': ['dg_grow_databases'],
    'construction products regulation': ['dg_grow_databases'],
    'ppe regulation': ['dg_grow_databases'],
    'personal protective equipment': ['dg_grow_databases'],
    'radio equipment directive': ['dg_grow_databases'],

    # Gender Equality Strategy 2026-2030
    'gender equality': ['gender_equality_strategy'],
    'gender equality strategy': ['gender_equality_strategy'],
    'gender pay gap': ['gender_equality_strategy'],
    'gender pension gap': ['gender_equality_strategy'],
    'pay transparency': ['gender_equality_strategy'],
    'pay transparency directive': ['gender_equality_strategy'],
    'women on boards': ['gender_equality_strategy'],
    'violence against women': ['gender_equality_strategy'],
    'gender-based violence': ['gender_equality_strategy'],
    'femm committee': ['gender_equality_strategy'],
    'femm': ['gender_equality_strategy'],
    'women rights': ['gender_equality_strategy'],
    "women's rights": ['gender_equality_strategy'],
    'gender mainstreaming': ['gender_equality_strategy'],
    'eige': ['gender_equality_strategy'],
    'istanbul convention': ['gender_equality_strategy'],
    'work-life balance': ['gender_equality_strategy'],
    'igualdad de genero': ['gender_equality_strategy'],
    'igualtat de genere': ['gender_equality_strategy'],
    'egalite des genres': ['gender_equality_strategy'],
    'parita di genere': ['gender_equality_strategy'],
    'gendergelijkheid': ['gender_equality_strategy'],
    'ip/26/526': ['gender_equality_strategy'],

    # Intergenerational Fairness Strategy
    'intergenerational fairness': ['intergenerational_fairness_strategy'],
    'intergenerational': ['intergenerational_fairness_strategy'],
    'future generations': ['intergenerational_fairness_strategy'],
    'generational fairness': ['intergenerational_fairness_strategy'],
    'demography forum': ['intergenerational_fairness_strategy'],
    'demographic change': ['intergenerational_fairness_strategy'],
    'ageing population': ['intergenerational_fairness_strategy'],
    'youth policy': ['intergenerational_fairness_strategy'],
    'old-age dependency': ['intergenerational_fairness_strategy'],
    'pension sustainability': ['intergenerational_fairness_strategy'],
    'glenn micallef': ['intergenerational_fairness_strategy'],
    'ip/26/535': ['intergenerational_fairness_strategy'],
    'justicia intergeneracional': ['intergenerational_fairness_strategy'],
    'justicia intergeneracional': ['intergenerational_fairness_strategy'],
    'equitat intergeneracional': ['intergenerational_fairness_strategy'],

    # Farmers' Food Supply Chain (CMO amendment)
    'food supply chain': ['bioeconomy_food_systems'],
    'farmers position': ['bioeconomy_food_systems'],
    "farmers' position": ['bioeconomy_food_systems'],
    'cmo regulation': ['bioeconomy_food_systems'],
    'common market organisation': ['bioeconomy_food_systems'],
    'producer organisations': ['bioeconomy_food_systems'],
    'celine imart': ['bioeconomy_food_systems'],
    'meat labelling': ['bioeconomy_food_systems'],
    'lab-grown meat': ['bioeconomy_food_systems'],
    'dairy contracts': ['bioeconomy_food_systems'],
    'food fraud': ['bioeconomy_food_systems'],
    'food safety': ['bioeconomy_food_systems'],
    'food traceability': ['bioeconomy_food_systems'],
    '2024/0319': ['bioeconomy_food_systems'],

    # EU Trade Policy
    'trade policy': ['eu_trade_policy'],
    'trade agreement': ['eu_trade_policy'],
    'free trade': ['eu_trade_policy'],
    'fta': ['eu_trade_policy'],
    'ceta': ['eu_trade_policy'],
    'mercosur': ['eu_trade_policy'],
    'dg trade': ['eu_trade_policy'],
    'inta committee': ['eu_trade_policy'],
    'inta': ['eu_trade_policy'],
    'anti-dumping': ['eu_trade_policy'],
    'anti-subsidy': ['eu_trade_policy'],
    'trade defence': ['eu_trade_policy'],
    'trade defense': ['eu_trade_policy'],
    'foreign subsidies regulation': ['eu_trade_policy'],
    'cbam': ['eu_trade_policy'],
    'carbon border': ['eu_trade_policy'],
    'digital trade agreement': ['eu_trade_policy'],
    'sefcovic': ['eu_trade_policy'],
    'gsp': ['eu_trade_policy'],
    'generalised system of preferences': ['eu_trade_policy'],
    'anti-coercion': ['eu_trade_policy'],
    'trade sanctions': ['eu_trade_policy'],
    'export controls': ['eu_trade_policy'],
    'dual-use': ['eu_trade_policy'],
    'ipi': ['eu_trade_policy'],
    'international procurement instrument': ['eu_trade_policy'],
    'politica comercial': ['eu_trade_policy'],
    'politique commerciale': ['eu_trade_policy'],
    'politica comercial ue': ['eu_trade_policy'],
    'handelspolitik': ['eu_trade_policy'],
    'tariff': ['eu_trade_policy'],
    'tariffs': ['eu_trade_policy'],
    'trade war': ['eu_trade_policy'],
    'trump tariff': ['eu_trade_policy'],
    'us tariff': ['eu_trade_policy'],
    'retaliatory tariff': ['eu_trade_policy'],
    'grids package': ['eu_energy_policy', 'clean_energy_investment_strategy'],
    'electricity grid': ['eu_energy_policy'],
    'power grid': ['eu_energy_policy'],
    'grid integration': ['eu_energy_policy'],
    'energy council': ['eu_energy_policy'],

    # EU Customs Electronic Systems
    'customs electronic': ['eu_customs_electronic_systems'],
    'customs systems': ['eu_customs_electronic_systems'],
    'union customs code': ['eu_customs_electronic_systems'],
    'ucc': ['eu_customs_electronic_systems'],
    'customs data hub': ['eu_customs_electronic_systems'],
    'ics2': ['eu_customs_electronic_systems'],
    'import control system': ['eu_customs_electronic_systems'],
    'ncts': ['eu_customs_electronic_systems'],
    'taric': ['eu_customs_electronic_systems'],
    'customs reform': ['eu_customs_electronic_systems'],
    'customs declaration': ['eu_customs_electronic_systems'],
    'entry summary declaration': ['eu_customs_electronic_systems'],
    'customs authority': ['eu_customs_electronic_systems'],
    'electronic customs': ['eu_customs_electronic_systems'],
    'customs digitali': ['eu_customs_electronic_systems'],
    'sistemas aduaneros': ['eu_customs_electronic_systems'],
    'systemes douaniers': ['eu_customs_electronic_systems'],
    'sistemes duaners': ['eu_customs_electronic_systems'],

    # EU Staff Categories and Grades
    'ast-1': ['eu_staff_categories_grades'],
    'ast-2': ['eu_staff_categories_grades'],
    'ast-3': ['eu_staff_categories_grades'],
    'ast 1': ['eu_staff_categories_grades'],
    'ast 2': ['eu_staff_categories_grades'],
    'ast 3': ['eu_staff_categories_grades'],
    'ad 5': ['eu_staff_categories_grades'],
    'ad 7': ['eu_staff_categories_grades'],
    'staff regulations': ['eu_staff_categories_grades'],
    'eu grades': ['eu_staff_categories_grades'],
    'eu salary': ['eu_staff_categories_grades'],
    'eu official salary': ['eu_staff_categories_grades'],
    'function group': ['eu_staff_categories_grades'],
    'contract agent': ['eu_staff_categories_grades'],
    'temporary agent': ['eu_staff_categories_grades'],
    'epso competition': ['eu_staff_categories_grades'],
    'blue book': ['eu_staff_categories_grades'],
    'seconded national expert': ['eu_staff_categories_grades'],
    'sne': ['eu_staff_categories_grades'],
    'expatriation allowance': ['eu_staff_categories_grades'],
    'ast/sc': ['eu_staff_categories_grades'],
    'categorias funcionarios': ['eu_staff_categories_grades'],
    'categories fonctionnaires': ['eu_staff_categories_grades'],
    'categories funcionaris': ['eu_staff_categories_grades'],

    # Georgia Visa Suspension
    'georgia visa': ['georgia_visa_suspension'],
    'georgia': ['georgia_visa_suspension'],
    'georgian': ['georgia_visa_suspension'],
    'georgian dream': ['georgia_visa_suspension'],
    'visa suspension': ['georgia_visa_suspension'],
    'visa exemption': ['georgia_visa_suspension'],
    'visa liberalisation': ['georgia_visa_suspension'],
    'visa liberalization': ['georgia_visa_suspension'],
    'predator spyware': ['georgia_visa_suspension'],
    'khoshtaria': ['georgia_visa_suspension'],
    '2026/496': ['georgia_visa_suspension'],
    '32026r0496': ['georgia_visa_suspension'],
    'georgie': ['georgia_visa_suspension'],

    # Transport Community Treaty
    'transport community': ['transport_community_treaty'],
    'transport community treaty': ['transport_community_treaty'],
    'western balkans transport': ['transport_community_treaty'],
    '2026/523': ['transport_community_treaty'],
    '32026d0523': ['transport_community_treaty'],
    'regional steering committee': ['transport_community_treaty'],
    'balkans transport': ['transport_community_treaty'],

    # Natura 2000 Sites Update
    'natura 2000': ['natura_2000_sites_update'],
    'natura2000': ['natura_2000_sites_update'],
    'sites of community importance': ['natura_2000_sites_update'],
    'sci': ['natura_2000_sites_update'],
    'special areas of conservation': ['natura_2000_sites_update'],
    'sac': ['natura_2000_sites_update'],
    'habitats directive': ['natura_2000_sites_update'],
    '2026/401': ['natura_2000_sites_update'],
    '32026d0401': ['natura_2000_sites_update'],
    'biogeographical region': ['natura_2000_sites_update'],
    '92/43': ['natura_2000_sites_update'],

    # European Council and Council of the EU Personnel Directory
    'european council': ['european_council_and_council_personnel', 'council_guide'],
    'euco': ['european_council_and_council_personnel'],
    'council of the eu': ['european_council_and_council_personnel', 'council_guide'],
    'council secretariat': ['european_council_and_council_personnel'],
    'general secretariat of the council': ['european_council_and_council_personnel'],
    'gsc': ['european_council_and_council_personnel'],
    'coreper': ['european_council_and_council_personnel', 'council_guide'],
    'permanent representative': ['european_council_and_council_personnel', 'council_guide'],
    'permanent representation': ['european_council_and_council_personnel', 'council_guide'],
    'consejo europeo': ['european_council_and_council_personnel'],
    'conseil europeen': ['european_council_and_council_personnel'],
    'consell europeu': ['european_council_and_council_personnel'],
    'consiglio europeo': ['european_council_and_council_personnel'],
    'europese raad': ['european_council_and_council_personnel'],
    'antonio costa': ['european_council_and_council_personnel'],
    'therese blanchet': ['european_council_and_council_personnel'],
    'heads of state': ['european_council_and_council_personnel'],
    'heads of government': ['european_council_and_council_personnel'],
    'council presidency': ['european_council_and_council_personnel', 'council_guide'],
    'rotating presidency': ['european_council_and_council_personnel', 'council_guide'],
    'council formation': ['european_council_and_council_personnel', 'council_guide'],
    'council configuration': ['european_council_and_council_personnel', 'council_guide'],
    'ecofin': ['european_council_and_council_personnel', 'council_guide'],
    'agrifish': ['european_council_and_council_personnel', 'council_guide'],
    'epsco': ['european_council_and_council_personnel', 'council_guide'],
    'gac': ['european_council_and_council_personnel', 'council_guide'],
    'fac': ['european_council_and_council_personnel', 'council_guide'],
    'jha council': ['european_council_and_council_personnel', 'council_guide'],
    'tte council': ['european_council_and_council_personnel', 'council_guide'],
    'council working party': ['european_council_and_council_personnel', 'council_guide'],
    'working party': ['council_guide'],
    'antici group': ['council_guide'],
    'mertens group': ['council_guide'],
    'council legal service': ['european_council_and_council_personnel'],
    'emer finnegan': ['european_council_and_council_personnel'],
    'didier seeuws': ['european_council_and_council_personnel'],
    'government representative': ['european_council_and_council_personnel'],
    'consilium': ['european_council_and_council_personnel', 'council_guide'],
    'eurogroup': ['european_council_and_council_personnel'],
    'tuomas saarenheimo': ['european_council_and_council_personnel'],
    'secretaria general del consejo': ['european_council_and_council_personnel'],
    'secretariat general du conseil': ['european_council_and_council_personnel'],
    'secretaria general del consell': ['european_council_and_council_personnel'],
    'raad van de eu': ['european_council_and_council_personnel'],
    'consejo de la ue': ['european_council_and_council_personnel'],
    'conseil de l\'ue': ['european_council_and_council_personnel'],
    'consell de la ue': ['european_council_and_council_personnel'],

    # European Parliament Personnel Directory
    'ep secretariat': ['european_parliament_personnel'],
    'ep secretary general': ['european_parliament_personnel'],
    'secretary general of the parliament': ['european_parliament_personnel'],
    'secretariat general of the european parliament': ['european_parliament_personnel'],
    'alessandro chiocchetti': ['european_parliament_personnel'],
    'ep dg': ['european_parliament_personnel'],
    'ep directorate': ['european_parliament_personnel'],
    'dg presidency ep': ['european_parliament_personnel'],
    'dg communication ep': ['european_parliament_personnel'],
    'dg personnel ep': ['european_parliament_personnel'],
    'dg translation ep': ['european_parliament_personnel'],
    'dg finance ep': ['european_parliament_personnel'],
    'eprs director': ['european_parliament_personnel'],
    'parliamentary research services': ['european_parliament_personnel'],
    'ep legal service': ['european_parliament_personnel'],
    'freddy drexler': ['european_parliament_personnel'],
    'ep bureau': ['european_parliament_personnel'],
    'group secretariat': ['european_parliament_personnel'],
    'political group staff': ['european_parliament_personnel'],
    'political group secretary': ['european_parliament_personnel'],
    'ppe secretariat': ['european_parliament_personnel'],
    'sd secretariat': ['european_parliament_personnel'],
    'renew secretariat': ['european_parliament_personnel'],
    'ecr secretariat': ['european_parliament_personnel'],
    'greens secretariat': ['european_parliament_personnel'],
    'left secretariat': ['european_parliament_personnel'],
    'ep administration': ['european_parliament_personnel'],
    'ep staff': ['european_parliament_personnel'],
    'ep personnel': ['european_parliament_personnel'],
    'parliament official': ['european_parliament_personnel'],
    'roberta metsola': ['european_parliament_personnel'],
    'secretaria general del parlamento': ['european_parliament_personnel'],
    'secretariat general du parlement': ['european_parliament_personnel'],
    'secretaria general del parlament': ['european_parliament_personnel'],
    'segretariato generale del parlamento': ['european_parliament_personnel'],
    'secretariaat-generaal van het parlement': ['european_parliament_personnel'],
    'ep interparliamentary delegation': ['european_parliament_personnel'],
    'ep delegation': ['european_parliament_personnel'],
    'parlamento europeo personal': ['european_parliament_personnel'],
    'parlement europeen personnel': ['european_parliament_personnel'],
    'parlament europeu personal': ['european_parliament_personnel'],
    # Corporate Sustainability Due Diligence Directive (CSDDD)
    'csddd': ['corporate_sustainability_due_diligence'],
    'cs3d': ['corporate_sustainability_due_diligence'],
    'due diligence directive': ['corporate_sustainability_due_diligence'],
    'corporate due diligence': ['corporate_sustainability_due_diligence'],
    'corporate sustainability due diligence': ['corporate_sustainability_due_diligence'],
    'sustainability due diligence': ['corporate_sustainability_due_diligence'],
    'supply chain due diligence': ['corporate_sustainability_due_diligence'],
    'value chain due diligence': ['corporate_sustainability_due_diligence'],
    'directive 2024/1760': ['corporate_sustainability_due_diligence'],
    '2024/1760': ['corporate_sustainability_due_diligence'],
    '32024l1760': ['corporate_sustainability_due_diligence'],
    '2022/0051': ['corporate_sustainability_due_diligence'],
    'lara wolters': ['corporate_sustainability_due_diligence'],
    'human rights due diligence': ['corporate_sustainability_due_diligence'],
    'environmental due diligence': ['corporate_sustainability_due_diligence'],
    'climate transition plan': ['corporate_sustainability_due_diligence'],
    'transition plan directive': ['corporate_sustainability_due_diligence'],
    'lieferkettensorgfaltspflichtengesetz': ['corporate_sustainability_due_diligence'],
    'lksg': ['corporate_sustainability_due_diligence'],
    'loi de vigilance': ['corporate_sustainability_due_diligence'],
    'duty of vigilance': ['corporate_sustainability_due_diligence'],
    'supply chain liability': ['corporate_sustainability_due_diligence'],
    'adverse impacts value chain': ['corporate_sustainability_due_diligence'],
    'forced labour regulation': ['corporate_sustainability_due_diligence'],
    'deforestation due diligence': ['corporate_sustainability_due_diligence'],
    'conflict minerals due diligence': ['corporate_sustainability_due_diligence'],
    'corporate sustainability directive': ['corporate_sustainability_due_diligence'],
    # CSDDD multilingual
    'devoir de vigilance': ['corporate_sustainability_due_diligence'],
    'debida diligencia empresarial': ['corporate_sustainability_due_diligence'],
    'diligencia debida corporativa': ['corporate_sustainability_due_diligence'],
    'dovere di diligenza': ['corporate_sustainability_due_diligence'],
    'zorgplicht bedrijven': ['corporate_sustainability_due_diligence'],
    'diligencia deguda corporativa': ['corporate_sustainability_due_diligence'],

    # Digital Markets Act (DMA)
    'digital markets act': ['digital_markets_act'],
    'dma': ['digital_markets_act'],
    'gatekeeper': ['digital_markets_act'],
    'gatekeepers': ['digital_markets_act'],
    'gatekeeper designation': ['digital_markets_act'],
    'core platform service': ['digital_markets_act'],
    'core platform services': ['digital_markets_act'],
    'self-preferencing': ['digital_markets_act'],
    'anti-steering': ['digital_markets_act'],
    'sideloading': ['digital_markets_act'],
    'app store regulation': ['digital_markets_act'],
    'third-party app store': ['digital_markets_act'],
    'messaging interoperability': ['digital_markets_act'],
    'interoperability messaging': ['digital_markets_act'],
    'frand access': ['digital_markets_act'],
    '2022/1925': ['digital_markets_act'],
    '32022r1925': ['digital_markets_act'],
    'regulation 2022/1925': ['digital_markets_act'],
    '2022/0003': ['digital_markets_act'],
    'dma compliance': ['digital_markets_act'],
    'dma enforcement': ['digital_markets_act'],
    'dma gatekeeper': ['digital_markets_act'],
    'dma obligations': ['digital_markets_act'],
    'digital fitness check': ['digital_markets_act'],
    'alphabet gatekeeper': ['digital_markets_act'],
    'apple gatekeeper': ['digital_markets_act'],
    'meta gatekeeper': ['digital_markets_act'],
    'amazon gatekeeper': ['digital_markets_act'],
    'microsoft gatekeeper': ['digital_markets_act'],
    'bytedance gatekeeper': ['digital_markets_act'],
    'teresa ribera dma': ['digital_markets_act'],
    'henna virkkunen dma': ['digital_markets_act'],
    'contestability': ['digital_markets_act'],
    'platform regulation': ['digital_markets_act'],
    # DMA multilingual
    'ley de mercados digitales': ['digital_markets_act'],
    'llei de mercats digitals': ['digital_markets_act'],
    'loi sur les marches numeriques': ['digital_markets_act'],
    'legge sui mercati digitali': ['digital_markets_act'],
    'wet digitale markten': ['digital_markets_act'],
    'gesetz uber digitale markte': ['digital_markets_act'],

    # SAFE / ReArm Europe / Readiness 2030
    'safe instrument': ['safe_rearm_europe'],
    'safe regulation': ['safe_rearm_europe'],
    'rearm europe': ['safe_rearm_europe'],
    'rearm': ['safe_rearm_europe'],
    'readiness 2030': ['safe_rearm_europe'],
    'defence loan': ['safe_rearm_europe'],
    'defence financing': ['safe_rearm_europe'],
    'defence procurement': ['safe_rearm_europe'],
    'eu defence spending': ['safe_rearm_europe'],
    'eu defence budget': ['safe_rearm_europe'],
    'european defence': ['safe_rearm_europe'],
    'defence industrial': ['safe_rearm_europe'],
    'edis': ['safe_rearm_europe'],
    'edip': ['safe_rearm_europe'],
    'kubilius': ['safe_rearm_europe'],
    'andrius kubilius': ['safe_rearm_europe'],
    'nato 5%': ['safe_rearm_europe'],
    'defence union': ['safe_rearm_europe', 'ep_plenary_march_2026'],
    'common european defence': ['safe_rearm_europe', 'ep_plenary_march_2026'],
    'defensa europea': ['safe_rearm_europe'],
    'defense europeenne': ['safe_rearm_europe'],
    'difesa europea': ['safe_rearm_europe'],
    'europese defensie': ['safe_rearm_europe'],
    'eur 150 billion defence': ['safe_rearm_europe'],
    '150 billion loans': ['safe_rearm_europe'],
    'com(2025) 120': ['safe_rearm_europe'],
    '2025/0076': ['safe_rearm_europe'],

    # WTO MC14 (added to eu_trade_policy)
    'mc14': ['eu_trade_policy'],
    'wto ministerial': ['eu_trade_policy'],
    'ministerial conference': ['eu_trade_policy'],
    'yaounde': ['eu_trade_policy'],
    'dispute settlement': ['eu_trade_policy'],
    'wto reform': ['eu_trade_policy'],
    'b10-0155': ['eu_trade_policy'],
    'e-commerce moratorium': ['eu_trade_policy'],
    'fisheries subsidies wto': ['eu_trade_policy'],

    # Eurodac and New Pact on Migration and Asylum
    'eurodac': ['eurodac_asylum_migration'],
    'regulation 2024/1358': ['eurodac_asylum_migration'],
    '2024/1358': ['eurodac_asylum_migration'],
    'decision 2026/533': ['eurodac_asylum_migration'],
    '2026/533': ['eurodac_asylum_migration'],
    'asylum database': ['eurodac_asylum_migration'],
    'biometric asylum': ['eurodac_asylum_migration'],
    'migration pact': ['eurodac_asylum_migration'],
    'new pact migration': ['eurodac_asylum_migration'],
    'pact on migration': ['eurodac_asylum_migration'],
    'ammr': ['eurodac_asylum_migration'],
    'dublin regulation': ['eurodac_asylum_migration'],
    'dublin iv': ['eurodac_asylum_migration'],
    'screening regulation': ['eurodac_asylum_migration'],
    'asylum procedure regulation': ['eurodac_asylum_migration'],
    'crisis regulation migration': ['eurodac_asylum_migration'],
    'eu-lisa': ['eurodac_asylum_migration'],
    'eu lisa': ['eurodac_asylum_migration'],
    'dg home': ['eurodac_asylum_migration'],
    'magnus brunner': ['eurodac_asylum_migration'],
    'asylum seekers': ['eurodac_asylum_migration'],
    'irregular migration': ['eurodac_asylum_migration'],
    'migration asylum': ['eurodac_asylum_migration'],
    'asilo': ['eurodac_asylum_migration'],
    'migracion': ['eurodac_asylum_migration'],
    'migration et asile': ['eurodac_asylum_migration'],
    'migrazione': ['eurodac_asylum_migration'],
    'migratie': ['eurodac_asylum_migration'],

    # Battery Booster Strategy
    'battery booster': ['battery_booster_strategy'],
    'battery booster strategy': ['battery_booster_strategy'],
    'battery booster facility': ['battery_booster_strategy'],
    'battery facility': ['battery_booster_strategy'],
    'eu battery': ['battery_booster_strategy'],
    'battery production': ['battery_booster_strategy'],
    'battery cell': ['battery_booster_strategy'],
    'battery manufacturing': ['battery_booster_strategy'],
    'battery value chain': ['battery_booster_strategy'],
    'regulation 2023/1542': ['battery_booster_strategy'],
    'battery regulation': ['battery_booster_strategy'],
    'c(2025) 8950': ['battery_booster_strategy'],
    'innovation fund battery': ['battery_booster_strategy'],
    'automotive package': ['battery_booster_strategy'],
    'eu automotive': ['battery_booster_strategy'],
    'ramp-up phase': ['battery_booster_strategy'],
    'european battery alliance': ['battery_booster_strategy'],
    'eit innoenergy': ['battery_booster_strategy'],
    'batterie ue': ['battery_booster_strategy'],
    'estrategia baterias': ['battery_booster_strategy'],
    'strategie batteries': ['battery_booster_strategy'],
    'strategia batterie': ['battery_booster_strategy'],
    'batterijstrategie': ['battery_booster_strategy'],

    # European Grids Package
    'grids package': ['energy_grids_package'],
    'grid package': ['energy_grids_package'],
    'energy grids': ['energy_grids_package'],
    'electricity grids': ['energy_grids_package'],
    'grid investment': ['energy_grids_package'],
    'grid permitting': ['energy_grids_package'],
    'ten-e': ['energy_grids_package'],
    'ten-e regulation': ['energy_grids_package'],
    'trans-european energy': ['energy_grids_package'],
    'cross-border grid': ['energy_grids_package'],
    'interconnection target': ['energy_grids_package'],
    'electricity interconnection': ['energy_grids_package'],
    'offshore grid': ['energy_grids_package'],
    'offshore wind grid': ['energy_grids_package'],
    'meshed offshore': ['energy_grids_package'],
    'cross-border cost allocation': ['energy_grids_package'],
    'cbca': ['energy_grids_package'],
    'anticipatory investment': ['energy_grids_package'],
    'grid bottleneck': ['energy_grids_package'],
    'distribution grid': ['energy_grids_package'],
    'transmission grid': ['energy_grids_package'],
    'tso': ['energy_grids_package'],
    'dso': ['energy_grids_package'],
    'entso-e': ['energy_grids_package'],
    'acer arbitration': ['energy_grids_package'],
    'energy council 16 march': ['energy_grids_package'],
    'tte energy': ['energy_grids_package'],
    '584 billion': ['energy_grids_package'],
    '2022/869': ['energy_grids_package'],
    '32022r0869': ['energy_grids_package'],
    'paquet reseaux': ['energy_grids_package'],
    'redes electricas': ['energy_grids_package'],
    'xarxes electrices': ['energy_grids_package'],
    'reti elettriche': ['energy_grids_package'],
    'elektriciteitsnetwerk': ['energy_grids_package'],

    # Package Travel Directive Revision
    'package travel': ['package_travel_directive'],
    'package travel directive': ['package_travel_directive'],
    'package holiday': ['package_travel_directive'],
    'linked travel arrangement': ['package_travel_directive'],
    'dynamic package': ['package_travel_directive'],
    'travel directive': ['package_travel_directive'],
    '2015/2302': ['package_travel_directive'],
    '32015l2302': ['package_travel_directive'],
    'directive 2015/2302': ['package_travel_directive'],
    'holiday cancellation': ['package_travel_directive'],
    'holiday refund': ['package_travel_directive'],
    'package refund': ['package_travel_directive'],
    'insolvency protection travel': ['package_travel_directive'],
    'tour operator': ['package_travel_directive'],
    'online travel agency': ['package_travel_directive'],
    'ota regulation': ['package_travel_directive'],
    'booking platform regulation': ['package_travel_directive'],
    'travel voucher': ['package_travel_directive'],
    'com(2023)905': ['package_travel_directive'],
    'dg just travel': ['package_travel_directive'],
    'imco travel': ['package_travel_directive'],
    'consumer protection travel': ['package_travel_directive'],
    'voyage a forfait': ['package_travel_directive'],
    'viaje combinado': ['package_travel_directive'],
    'viatge combinat': ['package_travel_directive'],
    'pacchetto turistico': ['package_travel_directive'],
    'pakketreis': ['package_travel_directive'],

    # Digital Services Act Enforcement
    'dsa enforcement': ['dsa_enforcement'],
    'dsa case': ['dsa_enforcement'],
    'dsa cases': ['dsa_enforcement'],
    'digital services act enforcement': ['dsa_enforcement'],
    'digital services act': ['dsa_enforcement'],
    'dsa': ['dsa_enforcement'],
    '2022/2065': ['dsa_enforcement'],
    '32022r2065': ['dsa_enforcement'],
    'regulation 2022/2065': ['dsa_enforcement'],
    'vlop': ['dsa_enforcement'],
    'vlops': ['dsa_enforcement'],
    'vlose': ['dsa_enforcement'],
    'vloses': ['dsa_enforcement'],
    'very large online platform': ['dsa_enforcement'],
    'very large online search engine': ['dsa_enforcement'],
    'digital services coordinator': ['dsa_enforcement'],
    'dsc': ['dsa_enforcement'],
    'tiktok dsa': ['dsa_enforcement'],
    'tiktok case': ['dsa_enforcement'],
    'dsa.100109': ['dsa_enforcement'],
    '52026dsa100109': ['dsa_enforcement'],
    'systemic risk assessment': ['dsa_enforcement'],
    'dsa risk assessment': ['dsa_enforcement'],
    'content moderation': ['dsa_enforcement'],
    'illegal content online': ['dsa_enforcement'],
    'trusted flagger': ['dsa_enforcement'],
    'dsa transparency': ['dsa_enforcement'],
    'dsa audit': ['dsa_enforcement'],
    'platform regulation': ['dsa_enforcement'],
    'online platform regulation': ['dsa_enforcement'],
    'dark patterns dsa': ['dsa_enforcement'],
    'researcher data access': ['dsa_enforcement'],
    'article 40 dsa': ['dsa_enforcement'],
    'dg cnect': ['dsa_enforcement'],
    'henna virkkunen': ['dsa_enforcement'],
    '6% turnover': ['dsa_enforcement'],
    'dsa penalty': ['dsa_enforcement'],
    'dsa fine': ['dsa_enforcement'],
    'services numeriques': ['dsa_enforcement'],
    'servicios digitales': ['dsa_enforcement'],
    'serveis digitals': ['dsa_enforcement'],
    'servizi digitali': ['dsa_enforcement'],
    'digitale diensten': ['dsa_enforcement'],

    # EU Common Military List
    'common military list': ['eu_common_military_list'],
    'military list': ['eu_common_military_list'],
    'military export controls': ['eu_common_military_list'],
    'arms export': ['eu_common_military_list', 'eu_trade_policy'],
    'arms export controls': ['eu_common_military_list'],
    'military technology export': ['eu_common_military_list'],
    '2008/944/cfsp': ['eu_common_military_list'],
    'common position 2008/944': ['eu_common_military_list'],
    'coarm': ['eu_common_military_list'],
    'wassenaar arrangement': ['eu_common_military_list'],
    'wassenaar': ['eu_common_military_list'],
    'munitions list': ['eu_common_military_list'],
    'military equipment export': ['eu_common_military_list'],
    'dual-use': ['eu_common_military_list'],
    'dual use regulation': ['eu_common_military_list'],
    '52026xg01640': ['eu_common_military_list'],
    'liste militaire': ['eu_common_military_list'],
    'lista militar': ['eu_common_military_list'],
    'llista militar': ['eu_common_military_list'],
    'lista militare': ['eu_common_military_list'],
    'militaire lijst': ['eu_common_military_list'],

    # EU Defence Procurement
    'defence procurement': ['eu_defence_procurement'],
    'defense procurement': ['eu_defence_procurement'],
    'joint procurement defence': ['eu_defence_procurement'],
    'joint defence procurement': ['eu_defence_procurement'],
    'edip': ['eu_defence_procurement', 'safe_rearm_europe'],
    'edf': ['eu_defence_procurement', 'safe_rearm_europe'],
    'european defence fund': ['eu_defence_procurement', 'safe_rearm_europe'],
    'european defence industrial programme': ['eu_defence_procurement'],
    'defence industrial strategy': ['eu_defence_procurement'],
    'edis': ['eu_defence_procurement', 'safe_rearm_europe'],
    'dtib': ['eu_defence_procurement'],
    'defence technological industrial base': ['eu_defence_procurement'],
    'collaborative procurement': ['eu_defence_procurement'],
    '35% procurement': ['eu_defence_procurement'],
    'defence industry': ['eu_defence_procurement', 'safe_rearm_europe'],
    '32025r2643': ['eu_defence_procurement'],
    'dg defis': ['eu_defence_procurement', 'safe_rearm_europe'],
    'andrius kubilius': ['eu_defence_procurement', 'safe_rearm_europe'],
    'european preference clause': ['eu_defence_procurement', 'safe_rearm_europe'],
    'approvisionnement defense': ['eu_defence_procurement'],
    'adquisiciones defensa': ['eu_defence_procurement'],
    'approvvigionamento difesa': ['eu_defence_procurement'],
    'defensie inkoop': ['eu_defence_procurement'],

    # Tobacco Excise Directive
    'tobacco excise': ['tobacco_excise_directive'],
    'tobacco taxation': ['tobacco_excise_directive'],
    'tobacco excise directive': ['tobacco_excise_directive'],
    'tobacco duty': ['tobacco_excise_directive'],
    'cigarette tax': ['tobacco_excise_directive'],
    'excise duty tobacco': ['tobacco_excise_directive'],
    '2011/64/eu': ['tobacco_excise_directive'],
    '32011l0064': ['tobacco_excise_directive'],
    'directive 2011/64': ['tobacco_excise_directive'],
    'heated tobacco products': ['tobacco_excise_directive'],
    'htp excise': ['tobacco_excise_directive'],
    'e-cigarette tax': ['tobacco_excise_directive'],
    'e-cigarette excise': ['tobacco_excise_directive'],
    'nicotine pouch': ['tobacco_excise_directive'],
    'vaping tax': ['tobacco_excise_directive'],
    'tomas kubin': ['tobacco_excise_directive'],
    'kubin': ['tobacco_excise_directive'],
    'tobacco own resource': ['tobacco_excise_directive', 'mff_2028_2034'],
    'accises tabac': ['tobacco_excise_directive'],
    'impuesto tabaco': ['tobacco_excise_directive'],
    'accisa tabacco': ['tobacco_excise_directive'],
    'tabaksaccijns': ['tobacco_excise_directive'],
    'impost tabac': ['tobacco_excise_directive'],

    # Cross-references: DMA-GDPR interplay
    'dma gdpr': ['digital_markets_act', 'dsa_enforcement'],
    'dma gdpr interplay': ['digital_markets_act'],
    'gatekeeper data protection': ['digital_markets_act'],
    'gatekeeper gdpr': ['digital_markets_act'],
    'dma consent': ['digital_markets_act'],
}


class KnowledgeLoader:
    """
    Load and manage internal knowledge base.

    Architecture:
    - Static JSON files (calendars, institutions) → In-memory cache
    - Templates (Markdown) → ChromaDB vector store
    - Unified query interface for AI context
    """

    def __init__(self, knowledge_base_dir: str = None):
        """
        Initialize knowledge loader.

        Args:
            knowledge_base_dir: Path to knowledge_base directory
        """
        if knowledge_base_dir is None:
            # Default to backend/knowledge_base
            current_dir = Path(__file__).parent
            knowledge_base_dir = str(current_dir)

        self.knowledge_base_dir = Path(knowledge_base_dir)

        # Directories
        self.calendars_dir = self.knowledge_base_dir / "calendars"
        self.institutions_dir = self.knowledge_base_dir / "institutions"
        self.templates_dir = self.knowledge_base_dir / "templates"
        self.organigrammes_dir = self.knowledge_base_dir / "ec_organigrammes" / "json"
        self.analytics_dir = self.knowledge_base_dir / "analytics"
        self.guides_dir = self.knowledge_base_dir / "guides"
        self.requirements_dir = self.knowledge_base_dir / "requirements"

        # In-memory caches
        self.calendars: Dict[str, Any] = {}
        self.institutions: Dict[str, Any] = {}
        self.templates: Dict[str, str] = {}
        self.organigrammes: Dict[str, Any] = {}  # DG organizational charts
        self.analytics: Dict[str, Any] = {}      # Analytics snapshots (e.g., EU law)
        self.guides: Dict[str, str] = {}         # Reference guides (EU jargon, resources, etc.)
        self.requirements: Dict[str, Any] = {}   # EU law requirements by cluster

        # Metadata
        self.last_loaded: Optional[datetime] = None
        self.stats: Dict[str, int] = {}

        logger.info(f"Initialized KnowledgeLoader at {self.knowledge_base_dir}")

    def load_all(self) -> Dict[str, Any]:
        """
        Load all knowledge base content.

        Returns:
            Statistics about loaded content
        """
        logger.info("Loading knowledge base...")
        start_time = datetime.now()

        # Load reference data
        self._load_calendars()
        self._load_institutions()
        self._load_templates()
        self._load_organigrammes()
        self._load_analytics()
        self._load_guides()
        self._load_requirements()

        self.last_loaded = datetime.now()
        load_time = (self.last_loaded - start_time).total_seconds()

        # Count total requirements across all clusters
        total_requirements = sum(
            len(cluster.get('requirements', []))
            for cluster in self.requirements.values()
        )

        self.stats = {
            'calendars': len(self.calendars),
            'institutions': len(self.institutions),
            'templates': len(self.templates),
            'organigrammes': len(self.organigrammes),
            'analytics': len(self.analytics),
            'guides': len(self.guides),
            'requirement_clusters': len(self.requirements),
            'total_requirements': total_requirements,
            'load_time_seconds': load_time
        }

        logger.info(f"Loaded knowledge base in {load_time:.2f}s: {self.stats}")
        return self.stats

    # =========================================================================
    # Loading Methods
    # =========================================================================

    def _load_calendars(self):
        """Load calendar JSON files into memory"""
        if not self.calendars_dir.exists():
            logger.warning(f"Calendars directory not found: {self.calendars_dir}")
            return

        for json_file in self.calendars_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    key = json_file.stem  # e.g., "ep_calendar_2025"
                    self.calendars[key] = data
                    logger.debug(f"Loaded calendar: {key}")
            except Exception as e:
                logger.error(f"Failed to load calendar {json_file}: {str(e)}")

    def _load_institutions(self):
        """Load institution JSON files into memory"""
        if not self.institutions_dir.exists():
            logger.warning(f"Institutions directory not found: {self.institutions_dir}")
            return

        for json_file in self.institutions_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    key = json_file.stem  # e.g., "commissioners"
                    self.institutions[key] = data
                    logger.debug(f"Loaded institution data: {key}")
            except Exception as e:
                logger.error(f"Failed to load institution data {json_file}: {str(e)}")

    def _load_templates(self):
        """Load template Markdown files into memory"""
        if not self.templates_dir.exists():
            logger.warning(f"Templates directory not found: {self.templates_dir}")
            return

        for md_file in self.templates_dir.glob("*.md"):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    key = md_file.stem  # e.g., "briefing_note"
                    self.templates[key] = content
                    logger.debug(f"Loaded template: {key}")
            except Exception as e:
                logger.error(f"Failed to load template {md_file}: {str(e)}")

    def _load_organigrammes(self):
        """Load EC organigramme JSON files into memory"""
        if not self.organigrammes_dir.exists():
            logger.warning(f"Organigrammes directory not found: {self.organigrammes_dir}")
            return

        for json_file in self.organigrammes_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    key = json_file.stem  # e.g., "CLIMA", "AGRI"
                    self.organigrammes[key] = data
                    logger.debug(f"Loaded organigramme: {key}")
            except Exception as e:
                logger.error(f"Failed to load organigramme {json_file}: {str(e)}")

    def _load_analytics(self):
        """Load analytics snapshots (e.g., eu_law_snapshot.json)"""
        if not self.analytics_dir.exists():
            # Not critical; analytics are optional
            logger.info(f"Analytics directory not found: {self.analytics_dir}")
            return

        for json_file in self.analytics_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    key = json_file.stem  # e.g., "eu_law_snapshot"
                    self.analytics[key] = data
                    logger.debug(f"Loaded analytics snapshot: {key}")
            except Exception as e:
                logger.error(f"Failed to load analytics snapshot {json_file}: {str(e)}")

    def get_analytics_snapshot(self, key: str) -> Optional[Dict[str, Any]]:
        """Get analytics snapshot by key (e.g., 'eu_law_snapshot')."""
        return self.analytics.get(key)

    def _load_guides(self):
        """Load reference guide Markdown files into memory"""
        if not self.guides_dir.exists():
            logger.info(f"Guides directory not found: {self.guides_dir}")
            return

        for md_file in self.guides_dir.glob("*.md"):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    key = md_file.stem  # e.g., "eu_jargon", "council_guide"
                    self.guides[key] = content
                    logger.debug(f"Loaded guide: {key}")
            except Exception as e:
                logger.error(f"Failed to load guide {md_file}: {str(e)}")

    def _load_requirements(self):
        """Load EU law requirements from JSON files into memory"""
        if not self.requirements_dir.exists():
            logger.info(f"Requirements directory not found: {self.requirements_dir}")
            return

        for json_file in self.requirements_dir.glob("*.json"):
            # Skip index file
            if json_file.name.startswith("_"):
                continue

            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Use cluster_id as key for quick lookup
                    cluster_id = data.get('cluster_id')
                    if cluster_id:
                        self.requirements[str(cluster_id)] = data
                        logger.debug(f"Loaded requirements for cluster {cluster_id}: {data.get('cluster_name')}")
            except Exception as e:
                logger.error(f"Failed to load requirements {json_file}: {str(e)}")

        # Load index if exists
        index_path = self.requirements_dir / "_index.json"
        if index_path.exists():
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    self.requirements['_index'] = json.load(f)
                    logger.debug("Loaded requirements index")
            except Exception as e:
                logger.error(f"Failed to load requirements index: {str(e)}")

    # =========================================================================
    # Query Methods - Reference Data
    # =========================================================================

    def query_calendar(
        self,
        year: int = None,
        month: str = None,
        activity_type: str = None
    ) -> Dict[str, Any]:
        """
        Query calendar data.

        Args:
            year: Calendar year (2025, 2026)
            month: Month name (january, february, etc.)
            activity_type: Activity type filter (plenary_session, committee_week, etc.)

        Returns:
            Filtered calendar data

        Example:
            >>> query_calendar(year=2025, month="january", activity_type="plenary_session")
        """
        if year:
            calendar_key = f"ep_calendar_{year}"
            if calendar_key not in self.calendars:
                return {"error": f"Calendar for year {year} not found"}

            calendar = self.calendars[calendar_key]

            # Filter by month if specified
            if month:
                month_lower = month.lower()
                if month_lower in calendar.get('months', {}):
                    month_data = calendar['months'][month_lower]

                    # Filter by activity type if specified
                    if activity_type:
                        filtered_weeks = [
                            week for week in month_data.get('weeks', [])
                            if week.get('activity_type') == activity_type
                        ]
                        return {
                            'year': year,
                            'month': month,
                            'activity_type': activity_type,
                            'weeks': filtered_weeks
                        }

                    return month_data
                else:
                    return {"error": f"Month {month} not found in {year} calendar"}

            return calendar

        # No specific year, return all calendars
        return self.calendars

    def query_institution(
        self,
        institution_type: str,
        query_filter: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Query institution data.

        Args:
            institution_type: Type of institution data
                - "commissioners"
                - "ec_dg"
                - "ep_organisational_structure"
                - "eu_institutions"
                - "eu_policies"
                - "permreps"
            query_filter: Optional filters (e.g., {"country": "Germany"})

        Returns:
            Institution data (filtered if applicable)

        Example:
            >>> query_institution("commissioners", {"country": "Spain"})
            >>> query_institution("ep_organisational_structure")
        """
        if institution_type not in self.institutions:
            return {"error": f"Institution type '{institution_type}' not found"}

        data = self.institutions[institution_type]

        # If no filter, return all
        if not query_filter:
            return data

        # Apply filters (basic implementation)
        # This is simplified - you can make it more sophisticated
        return data

    def find_commissioner(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Find commissioner by name, country, or portfolio.

        Args:
            query: Search query (name, country, or portfolio keyword)

        Returns:
            Commissioner data or None

        Example:
            >>> find_commissioner("agriculture")
            >>> find_commissioner("Spain")
        """
        commissioners_data = self.institutions.get("commissioners", {})
        college = commissioners_data.get("college", {})

        query_lower = query.lower()

        # Search in president
        president = college.get("president", {})
        if self._matches_commissioner(president, query_lower):
            return president

        # Search in EVPs
        for evp in college.get("executive_vice_presidents", []):
            if self._matches_commissioner(evp, query_lower):
                return evp

        # Search in commissioners
        for commissioner in college.get("commissioners", []):
            if self._matches_commissioner(commissioner, query_lower):
                return commissioner

        return None

    def _matches_commissioner(self, commissioner: Dict[str, Any], query: str) -> bool:
        """Check if commissioner matches query"""
        searchable_fields = [
            commissioner.get("name", ""),
            commissioner.get("country", ""),
            commissioner.get("portfolio", ""),
            str(commissioner.get("additional_portfolio", "")),
        ]

        searchable_text = " ".join(searchable_fields).lower()
        return query in searchable_text

    def find_committee(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Find EP committee by acronym or name.

        Args:
            query: Committee acronym (e.g., "ENVI") or partial name

        Returns:
            Committee data or None
        """
        ep_structure = self.institutions.get("ep_organisational_structure", {})
        committees_data = ep_structure.get("parliamentary_committees", {})

        query_upper = query.upper()
        query_lower = query.lower()

        # Search in categories
        for category in committees_data.get("categories", []):
            for committee in category.get("committees", []):
                # Match acronym
                if committee.get("acronym") == query_upper:
                    return committee
                # Match name
                if query_lower in committee.get("full_name", "").lower():
                    return committee

        # Search in subcommittees
        for subcommittee in committees_data.get("subcommittees", []):
            if subcommittee.get("acronym") == query_upper:
                return subcommittee
            if query_lower in subcommittee.get("full_name", "").lower():
                return subcommittee

        # Search in special committees
        for special in committees_data.get("special_committees", []):
            if special.get("acronym") == query_upper:
                return special
            if query_lower in special.get("full_name", "").lower():
                return special

        return None

    # =========================================================================
    # Organigramme Query Methods (EC Personnel)
    # =========================================================================

    def get_dg_organigramme(self, dg_code: str) -> Optional[Dict[str, Any]]:
        """
        Get organigramme for a specific DG.

        Args:
            dg_code: DG code (e.g., "GROW", "CLIMA", "TRADE")

        Returns:
            Organigramme data or None

        Example:
            >>> get_dg_organigramme("GROW")
        """
        dg_upper = dg_code.upper()
        return self.organigrammes.get(dg_upper)

    def list_all_dgs(self) -> List[Dict[str, str]]:
        """
        List all available DGs.

        Returns:
            List of DG codes and names
        """
        dgs = []
        for dg_code, org in self.organigrammes.items():
            dgs.append({
                'dg_code': dg_code,
                'dg_name': org.get('dg_name', ''),
                'director_general': (
                    org['director_general'] if isinstance(org.get('director_general'), str)
                    else org.get('director_general', {}).get('name', 'Unknown') if isinstance(org.get('director_general'), dict)
                    else 'Unknown'
                )
            })
        return sorted(dgs, key=lambda x: x['dg_code'])

    def find_person_in_commission(self, name: str) -> List[Dict[str, Any]]:
        """
        Find a person across all Commission DGs.

        Args:
            name: Person's name (partial match supported)

        Returns:
            List of matches with DG and position info

        Example:
            >>> find_person_in_commission("Kerstin")
        """
        name_lower = name.lower()
        matches = []

        for dg_code, org in self.organigrammes.items():
            # Check Director-General
            if 'director_general' in org:
                dg_info = org['director_general']
                dg_name = dg_info.get('name', '')
                if name_lower in dg_name.lower():
                    matches.append({
                        'name': dg_name,
                        'position': 'Director-General',
                        'dg': dg_code,
                        'dg_name': org.get('dg_name', '')
                    })

            # Check Deputy Directors-General
            for ddg in org.get('deputy_directors_general', []):
                ddg_name = ddg.get('name', '')
                if name_lower in ddg_name.lower():
                    matches.append({
                        'name': ddg_name,
                        'position': 'Deputy Director-General',
                        'dg': dg_code,
                        'dg_name': org.get('dg_name', ''),
                        'responsibilities': ddg.get('responsibilities')
                    })

            # Check Principal Advisers
            for adviser in org.get('principal_advisers', []):
                adviser_name = adviser.get('name', '')
                if name_lower in adviser_name.lower() and adviser_name.lower() != 'not shown':
                    matches.append({
                        'name': adviser_name,
                        'position': 'Principal Adviser',
                        'dg': dg_code,
                        'dg_name': org.get('dg_name', ''),
                        'area': adviser.get('area')
                    })

            # Search in directorates
            for directorate in org.get('directorates', []):
                # Check Director (string format)
                director = directorate.get('director', '')
                if isinstance(director, str) and name_lower in director.lower():
                    matches.append({
                        'name': director,
                        'position': 'Director',
                        'dg': dg_code,
                        'dg_name': org.get('dg_name', ''),
                        'directorate': directorate.get('name'),
                        'directorate_code': directorate.get('code')
                    })

                # Check units
                for unit in directorate.get('units', []):
                    # Head of Unit (string format)
                    head = unit.get('head', '')
                    if isinstance(head, str) and name_lower in head.lower() and head.lower() != 'not shown':
                        matches.append({
                            'name': head,
                            'position': 'Head of Unit',
                            'dg': dg_code,
                            'dg_name': org.get('dg_name', ''),
                            'unit': unit.get('name'),
                            'unit_code': unit.get('code')
                        })

        return matches

    def get_director_general(self, dg_code: str) -> Optional[Dict[str, Any]]:
        """
        Get Director-General info for a DG.

        Args:
            dg_code: DG code (e.g., "GROW", "CLIMA")

        Returns:
            DG info with name, assistants, etc. or None

        Example:
            >>> get_director_general("GROW")
            {"name": "Kerstin Jorna", "assistants": [...]}
        """
        org = self.get_dg_organigramme(dg_code)
        if org and 'director_general' in org:
            return org['director_general']
        return None

    def find_unit_by_name(self, unit_name_query: str, dg_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find units by name across DGs.

        Args:
            unit_name_query: Unit name or keyword
            dg_code: Optional DG to search in (searches all if None)

        Returns:
            List of matching units
        """
        query_lower = unit_name_query.lower()
        matches = []

        # Determine which DGs to search
        search_orgs = {}
        if dg_code:
            dg_upper = dg_code.upper()
            if dg_upper in self.organigrammes:
                search_orgs[dg_upper] = self.organigrammes[dg_upper]
        else:
            search_orgs = self.organigrammes

        for dg, org in search_orgs.items():
            for directorate in org.get('directorates', []):
                for unit in directorate.get('units', []):
                    unit_name = unit.get('name', '')
                    if query_lower in unit_name.lower():
                        matches.append({
                            'dg': dg,
                            'dg_name': org.get('dg_name', ''),
                            'directorate': directorate.get('name'),
                            'unit_code': unit.get('code'),
                            'unit_name': unit_name,
                            'head': unit.get('head', {}).get('name')
                        })

        return matches

    def get_dg_structure_summary(self, dg_code: str) -> Optional[Dict[str, Any]]:
        """
        Get high-level structure summary of a DG.

        Args:
            dg_code: DG code

        Returns:
            Structure summary with leadership and organizational info

        Example:
            >>> get_dg_structure_summary("GROW")
        """
        org = self.get_dg_organigramme(dg_code)
        if not org:
            return None

        # Get director general name
        dg_info = org.get('director_general', {})
        dg_name = dg_info.get('name') if isinstance(dg_info, dict) else None

        # Get deputy DGs
        deputy_dgs = []
        for ddg in org.get('deputy_directors_general', []):
            if 'name' in ddg:
                deputy_dgs.append({
                    'name': ddg['name'],
                    'responsibilities': ddg.get('responsibilities')
                })

        # Count units across directorates
        num_units = 0
        for directorate in org.get('directorates', []):
            num_units += len(directorate.get('units', []))

        summary = {
            'dg_code': dg_code.upper(),
            'dg_name': org.get('dg_name'),
            'executive_vice_president': org.get('executive_vice_president'),
            'director_general': dg_name,
            'deputy_directors_general': deputy_dgs,
            'num_directorates': len(org.get('directorates', [])),
            'num_units': num_units,
            'num_agencies': len(org.get('agencies', [])),
            'date_of_effect': org.get('date_of_effect')
        }

        return summary

    # =========================================================================
    # Template Methods
    # =========================================================================

    def get_template(self, template_name: str) -> Optional[str]:
        """
        Get template content by name.

        Args:
            template_name: Template identifier (e.g., "briefing_note")

        Returns:
            Template content (Markdown) or None
        """
        return self.templates.get(template_name)

    def list_templates(self) -> List[Dict[str, str]]:
        """
        List all available templates.

        Returns:
            List of template metadata
        """
        templates_list = []
        for name, content in self.templates.items():
            # Extract title from content (first # heading)
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else name.replace('_', ' ').title()

            templates_list.append({
                'id': name,
                'title': title,
                'length': len(content)
            })

        return templates_list

    def search_templates(self, query: str) -> List[str]:
        """
        Search templates by keyword (simple text search).

        Args:
            query: Search query

        Returns:
            List of matching template names
        """
        query_lower = query.lower()
        matches = []

        for name, content in self.templates.items():
            # Search in name and content
            if query_lower in name.lower() or query_lower in content.lower():
                matches.append(name)

        return matches

    # =========================================================================
    # Guide Methods (Reference Knowledge)
    # =========================================================================

    def get_guide(self, guide_name: str) -> Optional[str]:
        """
        Get guide content by name.

        Args:
            guide_name: Guide identifier (e.g., "eu_jargon", "council_guide")

        Returns:
            Guide content (Markdown) or None

        Available guides:
            - eu_jargon: EU terminology glossary
            - eu_resources: Key EU websites and tools
            - working_with_apas: Guide to parliamentary assistants
            - monitoring_tips: EU policy monitoring best practices
            - council_guide: How the Council works
            - commission_guide: How the Commission works
            - event_planning_brussels: Organising EU events
        """
        return self.guides.get(guide_name)

    def list_guides(self) -> List[Dict[str, str]]:
        """
        List all available guides.

        Returns:
            List of guide metadata with id, title, and description
        """
        guides_list = []
        for name, content in self.guides.items():
            # Extract title from content (first # heading)
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else name.replace('_', ' ').title()

            # Extract first paragraph as description
            desc_match = re.search(r'^#[^\n]+\n+([^\n#]+)', content)
            description = desc_match.group(1).strip() if desc_match else ""

            guides_list.append({
                'id': name,
                'title': title,
                'description': description,
                'length': len(content)
            })

        return guides_list

    def search_guides(self, query: str) -> List[Dict[str, Any]]:
        """
        Search guides by keyword triggers and content matching.

        Uses a two-pass approach:
        1. Keyword triggers: check if any trigger phrases appear in the query
           (higher priority, more precise matching)
        2. Content search: fallback to searching guide names and content
           (lower priority, broader matching)

        Args:
            query: Search query (searches triggers, name, and content)

        Returns:
            List of matching guides with context snippets, ordered by relevance
        """
        query_lower = query.lower()
        triggered_guides = set()
        matches = []
        seen_ids = set()

        # Pass 1: Keyword trigger matching (highest priority)
        # Check multi-word triggers first (longer = more specific), then single-word
        sorted_triggers = sorted(GUIDE_KEYWORD_TRIGGERS.keys(), key=len, reverse=True)
        for trigger in sorted_triggers:
            if trigger in query_lower:
                for guide_id in GUIDE_KEYWORD_TRIGGERS[trigger]:
                    if guide_id in self.guides and guide_id not in seen_ids:
                        triggered_guides.add(guide_id)

        # Add triggered guides first (they are the most relevant)
        for guide_id in triggered_guides:
            content = self.guides[guide_id]
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else guide_id.replace('_', ' ').title()

            # Find context around the query match in content
            content_lower = content.lower()
            idx = content_lower.find(query_lower)
            if idx != -1:
                start = max(0, idx - 50)
                end = min(len(content), idx + len(query_lower) + 100)
                snippet = content[start:end].strip()
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."
            else:
                # Use the first paragraph after the title as snippet
                para_match = re.search(r'^#[^\n]+\n+([^\n#]+)', content)
                snippet = para_match.group(1).strip()[:150] + "..." if para_match else ""

            matches.append({
                'id': guide_id,
                'title': title,
                'snippet': snippet,
                'trigger_matched': True
            })
            seen_ids.add(guide_id)

        # Pass 2: Content search (fallback for guides not already matched by triggers)
        # Split query into individual words for broader matching
        # Filter out common words that would match too many guides
        stopwords = {
            'what', 'when', 'where', 'which', 'that', 'this', 'these', 'those',
            'have', 'does', 'will', 'would', 'could', 'should', 'about', 'with',
            'from', 'they', 'their', 'there', 'been', 'being', 'some', 'more',
            'also', 'than', 'then', 'very', 'just', 'like', 'make', 'made',
            'need', 'know', 'help', 'work', 'want', 'into', 'over', 'after',
            'before', 'between', 'under', 'through', 'during', 'each', 'only',
            'most', 'much', 'many', 'such', 'well', 'good', 'best',
        }
        query_words = [w for w in query_lower.split() if len(w) > 3 and w not in stopwords]

        for name, content in self.guides.items():
            if name in seen_ids:
                continue

            # Check if the full query or any significant word matches
            content_lower = content.lower()
            name_lower = name.lower()

            full_match = query_lower in name_lower or query_lower in content_lower
            word_matches = sum(1 for w in query_words if w in name_lower or w in content_lower)

            # Require either full match or at least 3 word matches (stricter to reduce noise)
            if full_match or word_matches >= 3:
                title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                title = title_match.group(1) if title_match else name.replace('_', ' ').title()

                idx = content_lower.find(query_lower)
                if idx != -1:
                    start = max(0, idx - 50)
                    end = min(len(content), idx + len(query_lower) + 100)
                    snippet = content[start:end].strip()
                    if start > 0:
                        snippet = "..." + snippet
                    if end < len(content):
                        snippet = snippet + "..."
                else:
                    snippet = ""

                matches.append({
                    'id': name,
                    'title': title,
                    'snippet': snippet,
                    'trigger_matched': False
                })
                seen_ids.add(name)

        return matches

    def get_all_guides_content(self) -> str:
        """
        Get concatenated content of all guides for AI context.

        Returns:
            All guides content as a single string with separators
        """
        parts = []
        for name, content in sorted(self.guides.items()):
            parts.append(f"=== {name.upper().replace('_', ' ')} ===\n\n{content}")
        return "\n\n".join(parts)

    # =========================================================================
    # Requirements Methods (EU Law Compliance)
    # =========================================================================

    def get_requirements_for_cluster(self, cluster_id: int) -> Optional[Dict[str, Any]]:
        """
        Get all requirements for a specific cluster.

        Args:
            cluster_id: Cluster ID (1-21)

        Returns:
            Cluster data with requirements list

        Example:
            >>> get_requirements_for_cluster(1)  # GDPR
            {"cluster_id": 1, "cluster_name": "GDPR Package", "requirements": [...]}
        """
        return self.requirements.get(str(cluster_id))

    def get_requirements_index(self) -> Optional[Dict[str, Any]]:
        """
        Get the requirements index with summary of all clusters.

        Returns:
            Index with cluster summaries and counts
        """
        return self.requirements.get('_index')

    def list_requirement_clusters(self) -> List[Dict[str, Any]]:
        """
        List all clusters with extracted requirements.

        Returns:
            List of cluster summaries with counts
        """
        clusters = []
        for key, data in self.requirements.items():
            if key.startswith('_'):
                continue
            clusters.append({
                'cluster_id': data.get('cluster_id'),
                'cluster_name': data.get('cluster_name'),
                'policy_area': data.get('policy_area'),
                'total_requirements': data.get('total_requirements', len(data.get('requirements', []))),
                'total_laws': data.get('total_laws', 0)
            })
        return sorted(clusters, key=lambda x: x.get('cluster_id', 0))

    def search_requirements(
        self,
        query: str,
        cluster_id: Optional[int] = None,
        criticality: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search requirements by keyword.

        Args:
            query: Search query (searches in requirement text and keywords)
            cluster_id: Optional cluster to search in
            criticality: Filter by criticality (critical, important, recommended)

        Returns:
            List of matching requirements with cluster context

        Example:
            >>> search_requirements("data breach", cluster_id=1)
            >>> search_requirements("notification", criticality="critical")
        """
        query_lower = query.lower()
        matches = []

        # Determine which clusters to search
        if cluster_id:
            clusters_to_search = [self.requirements.get(str(cluster_id))]
        else:
            clusters_to_search = [
                data for key, data in self.requirements.items()
                if not key.startswith('_')
            ]

        for cluster_data in clusters_to_search:
            if not cluster_data:
                continue

            cluster_name = cluster_data.get('cluster_name', '')
            cluster_id_val = cluster_data.get('cluster_id')

            for req in cluster_data.get('requirements', []):
                # Apply criticality filter
                if criticality and req.get('criticality') != criticality:
                    continue

                # Search in text and keywords
                req_text = req.get('requirement_text', '').lower()
                keywords = ' '.join(req.get('keywords', [])).lower()
                article = req.get('article', '').lower()
                law_title = req.get('law_title', '').lower()

                if (query_lower in req_text or
                    query_lower in keywords or
                    query_lower in article or
                    query_lower in law_title):

                    matches.append({
                        **req,
                        'cluster_name': cluster_name,
                        'cluster_id': cluster_id_val
                    })

        return matches

    def get_critical_requirements(self, cluster_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all critical requirements (highest priority).

        Args:
            cluster_id: Optional cluster to filter by

        Returns:
            List of critical requirements
        """
        return self.search_requirements("", cluster_id=cluster_id, criticality="critical")

    def get_requirements_by_entity(
        self,
        entity_type: str,
        cluster_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get requirements applicable to a specific entity type.

        Args:
            entity_type: Entity type (e.g., "data controller", "online platform")
            cluster_id: Optional cluster to filter by

        Returns:
            List of applicable requirements

        Example:
            >>> get_requirements_by_entity("online platform")
            >>> get_requirements_by_entity("data controller", cluster_id=1)
        """
        entity_lower = entity_type.lower()
        matches = []

        if cluster_id:
            clusters_to_search = [self.requirements.get(str(cluster_id))]
        else:
            clusters_to_search = [
                data for key, data in self.requirements.items()
                if not key.startswith('_')
            ]

        for cluster_data in clusters_to_search:
            if not cluster_data:
                continue

            cluster_name = cluster_data.get('cluster_name', '')
            cluster_id_val = cluster_data.get('cluster_id')

            for req in cluster_data.get('requirements', []):
                applicable = req.get('applicable_entity', '').lower()
                if entity_lower in applicable:
                    matches.append({
                        **req,
                        'cluster_name': cluster_name,
                        'cluster_id': cluster_id_val
                    })

        return matches

    def get_requirements_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics of all requirements.

        Returns:
            Summary with counts by cluster, criticality, etc.
        """
        summary = {
            'total_clusters': 0,
            'total_requirements': 0,
            'by_criticality': {'critical': 0, 'important': 0, 'recommended': 0},
            'clusters': []
        }

        for key, data in self.requirements.items():
            if key.startswith('_'):
                continue

            summary['total_clusters'] += 1
            reqs = data.get('requirements', [])
            summary['total_requirements'] += len(reqs)

            # Count by criticality
            for req in reqs:
                crit = req.get('criticality', 'important')
                if crit in summary['by_criticality']:
                    summary['by_criticality'][crit] += 1

            summary['clusters'].append({
                'cluster_id': data.get('cluster_id'),
                'cluster_name': data.get('cluster_name'),
                'requirement_count': len(reqs)
            })

        summary['clusters'].sort(key=lambda x: x.get('cluster_id', 0))
        return summary

    def get_guide_for_topic(self, topic: str) -> Optional[str]:
        """
        Get the most relevant guide for a topic.

        Args:
            topic: Topic keyword (e.g., "jargon", "council", "monitoring")

        Returns:
            Guide content or None
        """
        topic_lower = topic.lower()

        # Direct mappings
        topic_map = {
            # EU Jargon
            'jargon': 'eu_jargon',
            'terminology': 'eu_jargon',
            'glossary': 'eu_jargon',
            'terms': 'eu_jargon',
            'acronyms': 'eu_jargon',
            # EU Resources
            'resources': 'eu_resources',
            'websites': 'eu_resources',
            'tools': 'eu_resources',
            'links': 'eu_resources',
            # Working with APAs
            'apa': 'working_with_apas',
            'assistant': 'working_with_apas',
            'assistants': 'working_with_apas',
            'parliamentary': 'working_with_apas',
            # Monitoring
            'monitoring': 'monitoring_tips',
            'tracking': 'monitoring_tips',
            'alerts': 'monitoring_tips',
            # Council
            'council': 'council_guide',
            'coreper': 'council_guide',
            'working party': 'council_guide',
            # Commission
            'commission': 'commission_guide',
            'dg': 'commission_guide',
            'consultation': 'commission_guide',
            # Events
            'event': 'event_planning_brussels',
            'events': 'event_planning_brussels',
            'conference': 'event_planning_brussels',
            'brussels': 'event_planning_brussels',
            # Lobbying Methodology (NEW)
            'lobby': 'lobbying_methodology',
            'lobbying': 'lobbying_methodology',
            'advocacy': 'lobbying_methodology',
            'influence': 'lobbying_methodology',
            'campaign': 'lobbying_methodology',
            'strategy': 'lobbying_methodology',
            'engage': 'lobbying_methodology',
            'engagement': 'lobbying_methodology',
            'position paper': 'lobbying_methodology',
            'amendment': 'lobbying_methodology',
            'trilogue': 'lobbying_methodology',
            'intervention': 'lobbying_methodology',
            'timing': 'lobbying_methodology',
            'coalition': 'lobbying_methodology',
            # Stakeholder Mapping (NEW)
            'stakeholder': 'stakeholder_mapping',
            'stakeholders': 'stakeholder_mapping',
            'mapping': 'stakeholder_mapping',
            'decision-maker': 'stakeholder_mapping',
            'decision maker': 'stakeholder_mapping',
            'rapporteur': 'stakeholder_mapping',
            'shadow': 'stakeholder_mapping',
            'mep': 'stakeholder_mapping',
            'influence matrix': 'stakeholder_mapping',
            'prioritise': 'stakeholder_mapping',
            'prioritize': 'stakeholder_mapping',
            # Public Affairs Industry (NEW)
            'consultancy': 'public_affairs_industry',
            'consultant': 'public_affairs_industry',
            'public affairs': 'public_affairs_industry',
            'professional': 'public_affairs_industry',
            'deliverable': 'public_affairs_industry',
            'position paper': 'public_affairs_industry',
            'brief': 'public_affairs_industry',
            'briefing': 'public_affairs_industry',
            # Brubru Features
            'brubru': 'brubru_features',
            'tracked files': 'brubru_features',
            'track file': 'brubru_features',
            'my eu bubble': 'brubru_features',
            'legislative train': 'brubru_features',
            'oeil sync': 'brubru_features',
            'eurlex sync': 'brubru_features',
            'eur-lex sync': 'brubru_features',
            'celex': 'brubru_features',
            'procedure reference': 'brubru_features',
            'data sources': 'brubru_features',
            'amendator': 'brubru_features',
            'load from tracked': 'brubru_features',
        }

        # Check direct mapping
        if topic_lower in topic_map:
            guide_name = topic_map[topic_lower]
            return self.guides.get(guide_name)

        # Fallback: search all guides
        for name, content in self.guides.items():
            if topic_lower in name.lower() or topic_lower in content.lower():
                return content

        return None

    # =========================================================================
    # Preparation for Vector Store
    # =========================================================================

    def prepare_templates_for_embedding(self) -> List[Dict[str, Any]]:
        """
        Prepare templates for ChromaDB indexing.

        Returns:
            List of documents ready for vector store:
            [
                {
                    "id": "template_briefing_note",
                    "text": "content...",
                    "metadata": {
                        "type": "template",
                        "name": "briefing_note",
                        "title": "Briefing Note Template",
                        "category": "consultancy"
                    }
                }
            ]
        """
        documents = []

        for name, content in self.templates.items():
            # Extract title
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else name.replace('_', ' ').title()

            # Infer category from name
            category = self._infer_template_category(name)

            doc = {
                "id": f"template_{name}",
                "text": content,
                "metadata": {
                    "type": "template",
                    "name": name,
                    "title": title,
                    "category": category,
                    "source": "internal_knowledge_base"
                }
            }
            documents.append(doc)

        return documents

    def _infer_template_category(self, template_name: str) -> str:
        """Infer category from template name"""
        name_lower = template_name.lower()

        if 'briefing' in name_lower or 'note' in name_lower:
            return 'briefing'
        elif 'position' in name_lower or 'paper' in name_lower:
            return 'position_paper'
        elif 'event' in name_lower or 'planning' in name_lower:
            return 'event_management'
        elif 'monitoring' in name_lower or 'tracking' in name_lower:
            return 'monitoring'
        elif 'strategy' in name_lower or 'advocacy' in name_lower:
            return 'strategy'
        elif 'stakeholder' in name_lower or 'mapping' in name_lower:
            return 'stakeholder_analysis'
        else:
            return 'general'

    # =========================================================================
    # Statistics & Utilities
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics"""
        return {
            **self.stats,
            'last_loaded': self.last_loaded.isoformat() if self.last_loaded else None,
            'knowledge_base_dir': str(self.knowledge_base_dir),
            'template_categories': self._get_template_categories(),
            'dg_organigrammes': list(self.organigrammes.keys()),
            'guides_available': list(self.guides.keys())
        }

    def _get_template_categories(self) -> Dict[str, int]:
        """Count templates by category"""
        categories = {}
        for name in self.templates.keys():
            category = self._infer_template_category(name)
            categories[category] = categories.get(category, 0) + 1
        return categories

    def reload(self) -> Dict[str, Any]:
        """Reload all knowledge base content"""
        logger.info("Reloading knowledge base...")

        # Clear caches
        self.calendars.clear()
        self.institutions.clear()
        self.templates.clear()
        self.organigrammes.clear()
        self.analytics.clear()
        self.guides.clear()
        self.requirements.clear()

        # Reload
        return self.load_all()


# Global singleton
_knowledge_loader: Optional[KnowledgeLoader] = None


def get_knowledge_loader(knowledge_base_dir: str = None) -> KnowledgeLoader:
    """
    Get global knowledge loader instance.

    Args:
        knowledge_base_dir: Path to knowledge_base directory

    Returns:
        KnowledgeLoader instance
    """
    global _knowledge_loader

    if _knowledge_loader is None:
        _knowledge_loader = KnowledgeLoader(knowledge_base_dir)
        _knowledge_loader.load_all()

    return _knowledge_loader
