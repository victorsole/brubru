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
    # European Biotech Act
    'biotech act': ['biotech_act'],
    'european biotech act': ['biotech_act'],
    'eu biotech act': ['biotech_act'],
    'biotech regulation': ['biotech_act'],
    'biotechnology act': ['biotech_act'],
    'biotechnology regulation': ['biotech_act'],
    'biomanufacturing': ['biotech_act'],
    'biomanufacturing regulation': ['biotech_act'],
    'biotech strategic project': ['biotech_act'],
    'health biotechnology': ['biotech_act'],
    'biotech competitiveness': ['biotech_act'],
    'biotech investment pilot': ['biotech_act'],
    'biosimilar': ['biotech_act'],
    'biosimilars': ['biotech_act'],
    'biosimilar regulation': ['biotech_act'],
    'biosecurity': ['biotech_act'],
    'biodefence': ['biotech_act'],
    'biodefense': ['biotech_act'],
    'biotechnology misuse': ['biotech_act'],
    'clinical trial regulation': ['biotech_act'],
    'clinical trials regulation': ['biotech_act'],
    'regulation 536/2014': ['biotech_act'],
    'clinical trial simplification': ['biotech_act'],
    'clinical trial authorisation': ['biotech_act'],
    'atmp': ['biotech_act'],
    'advanced therapy medicinal product': ['biotech_act'],
    'advanced therapy medicinal products': ['biotech_act'],
    'regulatory sandbox biotech': ['biotech_act'],
    'biotech sandbox': ['biotech_act'],
    'biotech cluster': ['biotech_act'],
    'biotechnology cluster': ['biotech_act'],
    'biotech vc': ['biotech_act'],
    'biotech venture capital': ['biotech_act'],
    'biotech funding': ['biotech_act'],
    'com(2025) 1022': ['biotech_act'],
    'com(2025)1022': ['biotech_act'],
    '2025/0406': ['biotech_act'],
    '2025/0406(cod)': ['biotech_act'],
    'varhelyi biotech': ['biotech_act'],
    'oliver varhelyi': ['biotech_act'],
    'acte biotechnologie': ['biotech_act'],
    'loi biotechnologie': ['biotech_act'],
    'biotechnologie': ['biotech_act'],
    'organismes genetiquement modifies': ['biotech_act'],
    'acto biotecnologia': ['biotech_act'],
    'ley biotecnologia': ['biotech_act'],
    'biotecnologia': ['biotech_act'],
    'llei biotecnologia': ['biotech_act'],
    'atto biotecnologia': ['biotech_act'],
    'biotechnologie verordnung': ['biotech_act'],
    'biotechnologiewet': ['biotech_act'],
    'biotech steering group': ['biotech_act'],
    'european health biotechnology steering group': ['biotech_act'],
    'health biotechnology support network': ['biotech_act'],
    'foresight panel emerging health': ['biotech_act'],
    'building the future with nature': ['biotech_act'],
    'com(2024) 137': ['biotech_act'],
    'life sciences strategy': ['biotech_act'],
    'choose europe for life sciences': ['biotech_act'],
    'com(2025) 525': ['biotech_act'],
    'biotech act ii': ['biotech_act'],
    'gene therapy regulation': ['biotech_act'],
    'cell therapy regulation': ['biotech_act'],
    'soho regulation biotech': ['biotech_act'],
    'supplementary protection certificate biotech': ['biotech_act'],
    'spc biotech': ['biotech_act'],
    'efsa biotech': ['biotech_act'],
    'ema biotech': ['biotech_act'],
    # Horizon Europe Grant Management
    'grant': ['horizon_europe_grant_management'],
    'mga': ['horizon_europe_grant_management'],
    'model grant agreement': ['horizon_europe_grant_management'],
    'consortium': ['horizon_europe_grant_management'],
    'horizon europe': ['horizon_europe_grant_management', 'fp10_ecf_competitiveness'],
    'horizon europe australia': ['fp10_ecf_competitiveness'],
    'australia association horizon': ['fp10_ecf_competitiveness'],
    'associated country horizon': ['fp10_ecf_competitiveness', 'horizon_europe_grant_management'],
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
    'competition policy annual report': ['competition_law_enforcement'],
    'yon-courtin': ['competition_law_enforcement'],
    'politica de competencia': ['competition_law_enforcement'],
    'politique de concurrence': ['competition_law_enforcement'],
    'concurrentiebeleid': ['competition_law_enforcement'],
    'politica di concorrenza': ['competition_law_enforcement'],

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
    'competitiveness fund': ['mff_2028_2034', 'fp10_ecf_competitiveness'],
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

    # FP10 and European Competitiveness Fund (ECF)
    'fp10': ['fp10_ecf_competitiveness'],
    'fp 10': ['fp10_ecf_competitiveness'],
    'fp-10': ['fp10_ecf_competitiveness'],
    '10th framework programme': ['fp10_ecf_competitiveness'],
    'tenth framework programme': ['fp10_ecf_competitiveness'],
    'framework programme 10': ['fp10_ecf_competitiveness'],
    'european competitiveness fund': ['fp10_ecf_competitiveness', 'mff_2028_2034'],
    'ecf': ['fp10_ecf_competitiveness'],
    'ecf regulation': ['fp10_ecf_competitiveness'],
    'com(2025)555': ['fp10_ecf_competitiveness'],
    'com(2025) 555': ['fp10_ecf_competitiveness'],
    'competitiveness seal': ['fp10_ecf_competitiveness'],
    'policy windows': ['fp10_ecf_competitiveness'],
    'horizon europe 2028': ['fp10_ecf_competitiveness'],
    'horizon europe successor': ['fp10_ecf_competitiveness'],
    'next horizon': ['fp10_ecf_competitiveness'],
    'research framework': ['fp10_ecf_competitiveness', 'horizon_europe_grant_management'],
    'research programme 2028': ['fp10_ecf_competitiveness'],
    'zaharieva': ['fp10_ecf_competitiveness'],
    'ekaterina zaharieva': ['fp10_ecf_competitiveness'],
    'research commissioner': ['fp10_ecf_competitiveness'],
    'erc budget': ['fp10_ecf_competitiveness'],
    'eic budget': ['fp10_ecf_competitiveness'],
    'excellent science': ['fp10_ecf_competitiveness'],
    'european research area': ['fp10_ecf_competitiveness'],
    'fp10 ecf': ['fp10_ecf_competitiveness'],
    'fp10 and ecf': ['fp10_ecf_competitiveness'],
    'ecf and fp10': ['fp10_ecf_competitiveness'],
    'link between fp10': ['fp10_ecf_competitiveness'],
    'next programmation': ['fp10_ecf_competitiveness', 'mff_2028_2034'],
    'prochaine programmation': ['fp10_ecf_competitiveness', 'mff_2028_2034'],
    'proxima programacion': ['fp10_ecf_competitiveness', 'mff_2028_2034'],
    'prossima programmazione': ['fp10_ecf_competitiveness', 'mff_2028_2034'],
    'volgende programmering': ['fp10_ecf_competitiveness', 'mff_2028_2034'],
    'propera programacio': ['fp10_ecf_competitiveness', 'mff_2028_2034'],
    'research innovation budget': ['fp10_ecf_competitiveness'],
    '175 billion': ['fp10_ecf_competitiveness'],
    '451 billion': ['fp10_ecf_competitiveness'],
    'draghi competitiveness': ['fp10_ecf_competitiveness', 'jrc_capitalism_sustainability_democracy'],
    'draghi report': ['fp10_ecf_competitiveness', 'jrc_capitalism_sustainability_democracy'],
    'letta report': ['jrc_capitalism_sustainability_democracy', '28th_regime_innovation_act'],
    'eu competitiveness gap': ['fp10_ecf_competitiveness', 'jrc_capitalism_sustainability_democracy'],
    'european model': ['jrc_capitalism_sustainability_democracy'],
    'social market economy': ['jrc_capitalism_sustainability_democracy'],
    'soziale marktwirtschaft': ['jrc_capitalism_sustainability_democracy'],
    'muresan': ['fp10_ecf_competitiveness', 'mff_2028_2034'],
    'carla tavares': ['fp10_ecf_competitiveness', 'mff_2028_2034'],

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
    'seafarer': ['employment_future_of_work'],
    'seafarers': ['employment_future_of_work'],
    'maritime labour': ['employment_future_of_work'],
    'directive 2015/1794': ['employment_future_of_work'],
    'drets dels mariners': ['employment_future_of_work'],
    'derechos de los marineros': ['employment_future_of_work'],
    'droits des gens de mer': ['employment_future_of_work'],

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
    '2026/0068': ['industrial_accelerator_act'],
    '2026/0068(cod)': ['industrial_accelerator_act'],
    'industrial acceleration area': ['industrial_accelerator_act'],
    'industrial acceleration areas': ['industrial_accelerator_act'],
    'tacit approval permitting': ['industrial_accelerator_act'],
    'one project one submission': ['industrial_accelerator_act'],
    'low-carbon steel': ['industrial_accelerator_act'],
    'low carbon steel': ['industrial_accelerator_act'],
    'low-carbon concrete': ['industrial_accelerator_act'],
    'low-carbon aluminium': ['industrial_accelerator_act'],
    'eu origin procurement': ['industrial_accelerator_act'],
    'foreign investment conditions': ['industrial_accelerator_act'],
    'fdi screening industrial': ['industrial_accelerator_act'],
    'eur 100 million investment': ['industrial_accelerator_act'],
    'manufacturing 20% gdp': ['industrial_accelerator_act'],
    'sejourne industrial': ['industrial_accelerator_act'],

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
    'novel food': ['novel_food_insects', 'bioeconomy_food_systems'],
    'novel food regulation': ['novel_food_insects'],
    'edible insects': ['novel_food_insects'],
    'insects as food': ['novel_food_insects'],
    'insect food': ['novel_food_insects'],
    'insect protein': ['novel_food_insects'],
    'mealworm': ['novel_food_insects'],
    'tenebrio molitor': ['novel_food_insects'],
    'acheta domesticus': ['novel_food_insects'],
    'house cricket': ['novel_food_insects'],
    'locusta migratoria': ['novel_food_insects'],
    'alphitobius diaperinus': ['novel_food_insects'],
    'ipiff': ['novel_food_insects'],
    'sell insects': ['novel_food_insects'],
    'vendre insectes': ['novel_food_insects'],
    'vender insectos': ['novel_food_insects'],
    'insetti commestibili': ['novel_food_insects'],
    'insectes comestibles': ['novel_food_insects'],
    'eetbare insecten': ['novel_food_insects'],
    'novel food authorisation': ['novel_food_insects'],
    'efsa insect': ['novel_food_insects'],
    'black soldier fly': ['novel_food_insects'],
    'regulation 2015/2283': ['novel_food_insects'],
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
    'nudifier': ['ai_act_regulation'],
    'nudifier apps': ['ai_act_regulation'],
    'nudification': ['ai_act_regulation'],
    'ai regulatory sandbox': ['ai_act_regulation'],
    'ai sandbox': ['ai_act_regulation'],
    'ai sandboxes': ['ai_act_regulation'],
    'institutional aspects of ai': ['ai_act_regulation'],
    'ai european integration': ['ai_act_regulation'],
    'kefalogiannis': ['ai_act_regulation'],
    'ai act omnibus': ['ai_act_regulation', 'digital_omnibus_package'],
    'ai act postponement': ['ai_act_regulation'],
    'ai act delay': ['ai_act_regulation'],
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
    'gas transmission': ['eu_energy_policy'],
    'lng': ['eu_energy_policy'],
    'lng infrastructure': ['eu_energy_policy'],
    'gas infrastructure': ['eu_energy_policy'],
    'electrification action plan': ['eu_energy_policy'],
    'electrification': ['eu_energy_policy'],
    'heating and cooling': ['eu_energy_policy'],
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
    'fusion energy': ['smr_strategy_nuclear', 'eu_energy_policy'],
    'fusion reactor': ['smr_strategy_nuclear', 'eu_energy_policy'],
    'fusion investment': ['smr_strategy_nuclear', 'eu_energy_policy'],
    'iter': ['smr_strategy_nuclear', 'eu_energy_policy'],
    'eurofusion': ['smr_strategy_nuclear', 'eu_energy_policy'],
    'fusion research': ['smr_strategy_nuclear', 'eu_energy_policy'],
    'energie de fusion': ['smr_strategy_nuclear', 'eu_energy_policy'],
    'energia de fusion': ['smr_strategy_nuclear', 'eu_energy_policy'],
    'energia da fusione': ['smr_strategy_nuclear', 'eu_energy_policy'],
    'fusie-energie': ['smr_strategy_nuclear', 'eu_energy_policy'],
    'nuclear decommissioning': ['eu_energy_policy'],
    'decommissioning assistance': ['eu_energy_policy'],
    'ignalina': ['eu_energy_policy'],
    'bohunice': ['eu_energy_policy'],
    'kozloduy': ['eu_energy_policy'],
    'desmantelamiento nuclear': ['eu_energy_policy'],
    'demantelement nucleaire': ['eu_energy_policy'],
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
    'plenary this week': ['ep_plenary_march_2026'],
    'brussels plenary': ['ep_plenary_march_2026'],
    'brussels mini-plenary': ['ep_plenary_march_2026'],
    'mini-plenary': ['ep_plenary_march_2026'],
    'what was voted': ['ep_plenary_march_2026'],
    'what did parliament vote': ['ep_plenary_march_2026'],
    'plenaria': ['ep_plenary_march_2026'],
    'sessio plenaria': ['ep_plenary_march_2026'],
    'debat plenari': ['ep_plenary_march_2026'],
    'debats plenaris': ['ep_plenary_march_2026'],
    'resumeix el debat': ['ep_plenary_march_2026'],
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
    'defence single market': ['ep_plenary_march_2026', 'safe_rearm_europe', 'eu_defence_procurement'],
    'defence projects': ['ep_plenary_march_2026', 'safe_rearm_europe', 'eu_defence_procurement'],
    'single market defence': ['ep_plenary_march_2026', 'safe_rearm_europe', 'eu_defence_procurement'],
    'public access documents': ['ep_plenary_march_2026'],
    'regulation 1049/2001': ['ep_plenary_march_2026'],
    'package travel': ['ep_plenary_march_2026', 'dsa_enforcement'],

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

    # 25-26 March mini-plenary (Brussels)
    'mini-plenary': ['ep_plenary_march_2026'],
    'miniplenary': ['ep_plenary_march_2026'],
    'mini plenary': ['ep_plenary_march_2026'],
    '25 march plenary': ['ep_plenary_march_2026'],
    '26 march plenary': ['ep_plenary_march_2026'],
    '25-26 march': ['ep_plenary_march_2026'],
    'bernd lange': ['ep_plenary_march_2026', 'eu_us_trade_deal_2026'],
    'a10-0069/2026': ['ep_plenary_march_2026', 'eu_us_trade_deal_2026'],
    'a10-0070/2026': ['ep_plenary_march_2026', 'eu_us_trade_deal_2026'],
    'a10-0067/2026': ['ep_plenary_march_2026', 'banking_union_reform'],
    'a10-0066/2026': ['ep_plenary_march_2026', 'banking_union_reform'],
    'a10-0065/2026': ['ep_plenary_march_2026', 'banking_union_reform'],
    'irene tinagli': ['ep_plenary_march_2026', 'banking_union_reform'],
    'return regulation': ['ep_plenary_march_2026'],
    'environmental quality standards': ['ep_plenary_march_2026'],
    # AFCO Defence Union report (2025/2212(INI))
    'defence union': ['ep_plenary_march_2026', 'safe_rearm_europe', 'eu_defence_procurement'],
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
    'crisi habitatge': ['eu_housing_crisis'],
    'habitatge': ['eu_housing_crisis'],
    'habitatge assequible': ['eu_housing_crisis'],
    'politica habitatge': ['eu_housing_crisis'],
    'logement': ['eu_housing_crisis'],
    'vivienda': ['eu_housing_crisis'],
    'alloggio': ['eu_housing_crisis'],
    'woning': ['eu_housing_crisis'],

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
    'glossary': ['eu_jargon'],
    'acquis': ['eu_jargon'],
    'acquis communautaire': ['eu_jargon'],
    'co-decision': ['eu_jargon'],
    'codecision': ['eu_jargon'],
    'comitology': ['eu_jargon'],
    'subsidiarity': ['eu_jargon'],
    'subsidiarity principle': ['eu_jargon'],
    'subsidiariteit': ['eu_jargon'],
    'subsidiariteitsbeginsel': ['eu_jargon'],
    'principi de subsidiarietat': ['eu_jargon'],
    'principio de subsidiariedad': ['eu_jargon'],
    'principe de subsidiarite': ['eu_jargon'],
    'principio di sussidiarieta': ['eu_jargon'],
    'proportionality': ['eu_jargon'],
    'qmv': ['eu_jargon'],
    'qualified majority voting': ['eu_jargon'],
    'ordinary legislative procedure': ['eu_jargon'],
    'special legislative procedure': ['eu_jargon'],
    'direct effect': ['eu_jargon'],
    'supremacy': ['eu_jargon'],
    'primacy': ['eu_jargon'],
    'preliminary ruling': ['eu_jargon'],
    'infringement procedure': ['eu_jargon'],
    'delegated act': ['eu_jargon'],
    'implementing act': ['eu_jargon'],
    'transposition': ['eu_jargon'],
    'opt-out': ['eu_jargon'],
    'enhanced cooperation': ['eu_jargon'],
    'passerelle clause': ['eu_jargon'],
    'yellow card': ['eu_jargon'],
    'orange card': ['eu_jargon'],
    'eu legal term': ['eu_jargon'],
    'eu terminology': ['eu_jargon'],
    'eu definition': ['eu_jargon'],

    # EU Fisheries Policy / Fisheries Control
    'fisheries': ['eu_fisheries_control'],
    'common fisheries policy': ['eu_fisheries_control'],
    'cfp': ['eu_fisheries_control'],
    'fishing quota': ['eu_fisheries_control'],
    'tac': ['eu_fisheries_control'],
    'total allowable catch': ['eu_fisheries_control'],
    'emfaf': ['eu_fisheries_control'],
    'illegal fishing': ['eu_fisheries_control'],
    'iuu fishing': ['eu_fisheries_control'],
    'discards': ['eu_fisheries_control'],
    'landing obligation': ['eu_fisheries_control'],
    'dg mare': ['eu_fisheries_control'],
    'fisheries partnership': ['eu_fisheries_control'],
    'aquaculture': ['eu_fisheries_control'],
    'maximum sustainable yield': ['eu_fisheries_control'],
    'msy': ['eu_fisheries_control'],
    'pesca': ['eu_fisheries_control'],
    'peche': ['eu_fisheries_control'],
    'visserij': ['eu_fisheries_control'],
    'fisheries control': ['eu_fisheries_control'],
    'fisheries control regulation': ['eu_fisheries_control'],
    '2023/2842': ['eu_fisheries_control'],
    'agrifish council': ['eu_fisheries_control'],
    'commissioner kadis': ['eu_fisheries_control'],
    'small-scale fisheries': ['eu_fisheries_control'],
    'coastal fisheries': ['eu_fisheries_control'],
    'efca': ['eu_fisheries_control'],

    # EU Agriculture Policy
    'agriculture': ['common_agricultural_policy'],
    'common agricultural policy': ['common_agricultural_policy'],
    'cap': ['common_agricultural_policy'],
    'farm to fork': ['common_agricultural_policy'],
    'direct payments': ['common_agricultural_policy'],
    'pillar i': ['common_agricultural_policy'],
    'pillar ii': ['common_agricultural_policy'],
    'rural development': ['common_agricultural_policy'],
    'dg agri': ['common_agricultural_policy'],
    'market intervention': ['common_agricultural_policy'],
    'agri-food': ['common_agricultural_policy'],
    'agrifood': ['common_agricultural_policy'],
    'organic farming': ['common_agricultural_policy'],
    'pesticides': ['common_agricultural_policy'],
    'sur regulation': ['common_agricultural_policy'],
    'eco-schemes': ['common_agricultural_policy'],
    'cap strategic plan': ['common_agricultural_policy'],
    'agricultura': ['common_agricultural_policy'],
    'landbouw': ['common_agricultural_policy'],
    'politique agricole': ['common_agricultural_policy'],

    # EU Humanitarian Aid and Civil Protection
    'humanitarian aid': ['eu_defence_procurement'],
    'civil protection': ['eu_defence_procurement'],
    'dg echo': ['eu_defence_procurement'],
    'echo': ['eu_defence_procurement'],
    'eu aid': ['eu_defence_procurement'],
    'crisis response': ['eu_defence_procurement'],
    'eu civil protection mechanism': ['eu_defence_procurement'],
    'ucpm': ['eu_defence_procurement', 'wildfire_risk_management'],
    'resceu': ['eu_defence_procurement', 'wildfire_risk_management'],
    'ercc': ['eu_defence_procurement'],
    'emergency response coordination': ['eu_defence_procurement'],
    'ajuda humanitaria': ['eu_defence_procurement'],
    'aide humanitaire': ['eu_defence_procurement'],
    'ayuda humanitaria': ['eu_defence_procurement'],
    'proteccion civil': ['eu_defence_procurement'],
    'protection civile': ['eu_defence_procurement'],

    # EU Trade Policy
    'trade policy': ['eu_trade_policy'],
    'common commercial policy': ['eu_trade_policy'],
    'free trade agreement': ['eu_trade_policy'],
    'fta': ['eu_trade_policy'],
    'trade agreement': ['eu_trade_policy'],
    'trade defence': ['eu_trade_defence', 'eu_trade_policy'],
    'trade defence instruments': ['eu_trade_defence'],
    'anti-dumping': ['eu_trade_defence', 'eu_trade_policy'],
    'anti-dumping duties': ['eu_trade_defence'],
    'antidumping': ['eu_trade_defence'],
    'dumping duty': ['eu_trade_defence'],
    'countervailing duties': ['eu_trade_defence', 'eu_trade_policy'],
    'anti-subsidy': ['eu_trade_defence'],
    'safeguard measures': ['eu_trade_defence', 'eu_trade_policy'],
    'safeguard duty': ['eu_trade_defence'],
    'steel safeguard': ['eu_trade_defence'],
    'price undertaking': ['eu_trade_defence'],
    'regulation 2016/1036': ['eu_trade_defence'],
    'regulation 2016/1037': ['eu_trade_defence'],
    'tron database': ['eu_trade_defence'],
    'mesures antidumping': ['eu_trade_defence'],
    'medidas antidumping': ['eu_trade_defence'],
    'mesures antidumping': ['eu_trade_defence'],
    'dazi antidumping': ['eu_trade_defence'],
    'antidumpingmaatregelen': ['eu_trade_defence'],
    'dg trade': ['eu_trade_policy', 'eu_trade_defence'],
    'wto': ['eu_trade_policy'],
    'gsp': ['eu_trade_policy'],
    'generalised scheme of preferences': ['eu_trade_policy'],
    'mercosur': ['eu_trade_policy'],
    'eu-mercosur': ['eu_trade_policy'],
    'regulation 2026/687': ['eu_trade_policy'],
    '2026/687': ['eu_trade_policy'],
    'safeguard mercosur': ['eu_trade_policy'],
    'safeguard agricultural': ['eu_trade_policy'],
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
    'consumer protection': ['dsa_enforcement'],
    'consumer rights': ['dsa_enforcement'],
    'consumer rights directive': ['dsa_enforcement'],
    'product safety': ['dsa_enforcement'],
    'general product safety': ['dsa_enforcement'],
    'dg just': ['dsa_enforcement', 'eu_migration_asylum_pact'],
    'unfair commercial practices': ['dsa_enforcement'],
    'consumer credit': ['dsa_enforcement'],
    'package travel': ['dsa_enforcement'],
    'passenger rights': ['dsa_enforcement'],
    'class action': ['dsa_enforcement'],
    'representative action': ['dsa_enforcement'],
    'consumer adr': ['dsa_enforcement'],
    'digital fairness': ['dsa_enforcement', 'digital_fairness_act'],
    'dark patterns': ['dsa_enforcement', 'digital_fairness_act'],
    'green claims': ['dsa_enforcement'],
    'greenwashing': ['dsa_enforcement'],
    'proteccion del consumidor': ['dsa_enforcement'],
    'protection des consommateurs': ['dsa_enforcement'],
    'consumentenbescherming': ['dsa_enforcement'],

    # EU Culture Policy
    'culture policy': ['eu_media_landscape'],
    'creative europe': ['eu_media_landscape'],
    'dg eac': ['eu_media_landscape', 'employment_future_of_work'],
    'cultural heritage': ['eu_media_landscape'],
    'media programme': ['eu_media_landscape'],
    'media sub-programme': ['eu_media_landscape'],
    'european capital of culture': ['eu_media_landscape'],
    'cultural diversity': ['eu_media_landscape'],
    'cultura': ['eu_media_landscape'],
    'politique culturelle': ['eu_media_landscape'],
    'cultuurbeleid': ['eu_media_landscape'],

    # EU Development Cooperation
    'development cooperation': ['eu_funding_ipa_enlargement'],
    'dg intpa': ['eu_funding_ipa_enlargement'],
    'dg devco': ['eu_funding_ipa_enlargement'],
    'ndici': ['eu_funding_ipa_enlargement'],
    'global europe': ['eu_funding_ipa_enlargement'],
    'neighbourhood': ['eu_funding_ipa_enlargement'],
    'european development fund': ['eu_funding_ipa_enlargement'],
    'edf': ['eu_funding_ipa_enlargement'],
    'oda': ['eu_funding_ipa_enlargement'],
    'official development assistance': ['eu_funding_ipa_enlargement'],
    'global gateway': ['global_gateway_strategy', 'eu_funding_ipa_enlargement'],
    'team europe': ['eu_funding_ipa_enlargement', 'global_gateway_strategy'],
    'acp': ['eu_funding_ipa_enlargement'],
    'cotonou': ['eu_funding_ipa_enlargement'],
    'samoa agreement': ['eu_funding_ipa_enlargement'],
    'cooperacion al desarrollo': ['eu_funding_ipa_enlargement'],
    'cooperation au developpement': ['eu_funding_ipa_enlargement'],
    'ontwikkelingssamenwerking': ['eu_funding_ipa_enlargement'],

    # EU Customs Policy
    'customs': ['union_customs_code_reform'],
    'customs union': ['union_customs_code_reform'],
    'customs code': ['union_customs_code_reform'],
    'union customs code': ['union_customs_code_reform'],
    'ucc': ['union_customs_code_reform'],
    'dg taxud': ['union_customs_code_reform', 'eu_budget_emu_law'],
    'common external tariff': ['union_customs_code_reform'],
    'customs reform': ['union_customs_code_reform'],
    'single window': ['union_customs_code_reform'],
    'eu customs authority': ['union_customs_code_reform'],
    'aeo': ['union_customs_code_reform'],
    'authorised economic operator': ['union_customs_code_reform'],
    'customs valuation': ['union_customs_code_reform'],
    'customs classification': ['union_customs_code_reform'],
    'combined nomenclature': ['union_customs_code_reform'],
    'taric': ['union_customs_code_reform'],
    'aduanas': ['union_customs_code_reform'],
    'douane': ['union_customs_code_reform'],

    # EU Human Rights
    'human rights': ['eu_equality_antidiscrimination'],
    'fundamental rights': ['eu_equality_antidiscrimination'],
    'charter of fundamental rights': ['eu_equality_antidiscrimination'],
    'fra': ['eu_equality_antidiscrimination'],
    'european convention human rights': ['eu_equality_antidiscrimination'],
    'echr': ['eu_equality_antidiscrimination'],
    'rule of law': ['eu_equality_antidiscrimination'],
    'rule of law mechanism': ['eu_equality_antidiscrimination'],
    'democracy': ['eu_equality_antidiscrimination'],
    'article 7 teu': ['eu_equality_antidiscrimination'],
    'conditionality regulation': ['eu_equality_antidiscrimination'],
    'dg just human rights': ['eu_equality_antidiscrimination'],
    'equality': ['eu_equality_antidiscrimination'],
    'anti-discrimination': ['eu_equality_antidiscrimination'],
    'gender equality': ['eu_equality_antidiscrimination'],
    'lgbtiq': ['eu_equality_antidiscrimination'],
    'roma inclusion': ['eu_equality_antidiscrimination'],
    'derechos humanos': ['eu_equality_antidiscrimination'],
    'droits de lhomme': ['eu_equality_antidiscrimination'],
    'mensenrechten': ['eu_equality_antidiscrimination'],
    'drets humans': ['eu_equality_antidiscrimination'],

    # EU Education, Youth and Sport
    'education policy': ['employment_future_of_work'],
    'erasmus': ['employment_future_of_work'],
    'erasmus+': ['employment_future_of_work'],
    'european education area': ['employment_future_of_work'],
    'bologna process': ['employment_future_of_work'],
    'ects': ['employment_future_of_work'],
    'european solidarity corps': ['employment_future_of_work'],
    'youth guarantee': ['employment_future_of_work', 'employment_future_of_work'],
    'digital education': ['employment_future_of_work'],
    'vocational training': ['employment_future_of_work'],
    'cedefop': ['employment_future_of_work'],
    'european universities': ['employment_future_of_work'],
    'educacion': ['employment_future_of_work'],
    'education': ['employment_future_of_work'],
    'onderwijs': ['employment_future_of_work'],

    # EU Enlargement Policy
    'enlargement': ['eu_funding_ipa_enlargement'],
    'accession': ['eu_funding_ipa_enlargement'],
    'candidate country': ['eu_funding_ipa_enlargement'],
    'dg near': ['eu_funding_ipa_enlargement'],
    'western balkans': ['eu_funding_ipa_enlargement'],
    'acquis chapters': ['eu_funding_ipa_enlargement'],
    'screening process': ['eu_funding_ipa_enlargement'],
    'copenhagen criteria': ['eu_funding_ipa_enlargement'],
    'stabilisation and association': ['eu_funding_ipa_enlargement'],
    'saa': ['eu_funding_ipa_enlargement'],
    'pre-accession': ['eu_funding_ipa_enlargement'],
    'ipa': ['eu_funding_ipa_enlargement'],
    'ipa iii': ['eu_funding_ipa_enlargement'],
    'ukraine accession': ['eu_funding_ipa_enlargement'],
    'moldova accession': ['eu_funding_ipa_enlargement'],
    'elargissement': ['eu_funding_ipa_enlargement'],
    'ampliacion': ['eu_funding_ipa_enlargement'],
    'uitbreiding': ['eu_funding_ipa_enlargement'],

    # EU Enterprise and SME Policy
    'enterprise': ['28th_regime_innovation_act'],
    'sme': ['28th_regime_innovation_act'],
    'small and medium': ['28th_regime_innovation_act'],
    'sme strategy': ['28th_regime_innovation_act'],
    'single market': ['28th_regime_innovation_act', 'digital_markets_act'],
    'dg grow': ['28th_regime_innovation_act', 'digital_markets_act'],
    'late payment directive': ['28th_regime_innovation_act'],
    'sme envoy': ['28th_regime_innovation_act'],
    'startup': ['28th_regime_innovation_act'],
    'scale-up': ['28th_regime_innovation_act'],
    'industrial strategy': ['28th_regime_innovation_act'],
    'sme relief package': ['28th_regime_innovation_act'],
    'think small first': ['28th_regime_innovation_act'],
    'empresa': ['28th_regime_innovation_act'],
    'entreprise': ['28th_regime_innovation_act'],
    'pyme': ['28th_regime_innovation_act'],
    'pme': ['28th_regime_innovation_act'],
    'mkb': ['28th_regime_innovation_act'],

    # EU Environment and Climate
    'environment policy': ['european_climate_law'],
    'green deal': ['european_climate_law'],
    'european green deal': ['european_climate_law'],
    'climate law': ['european_climate_law'],
    'climate neutrality': ['european_climate_law'],
    'nature restoration': ['european_climate_law'],
    'biodiversity': ['european_climate_law'],
    'biodiversity strategy': ['european_climate_law'],
    'circular economy': ['european_climate_law'],
    'waste framework directive': ['european_climate_law'],
    'packaging regulation': ['european_climate_law'],
    'water framework directive': ['european_climate_law'],
    'air quality': ['european_climate_law'],
    'ambient air quality directive': ['european_climate_law'],
    'industrial emissions directive': ['european_climate_law'],
    'ied': ['european_climate_law'],
    'seveso directive': ['european_climate_law'],
    'environmental impact assessment': ['european_climate_law'],
    'eia directive': ['european_climate_law'],
    'natura 2000': ['european_climate_law'],
    'habitats directive': ['european_climate_law'],
    'birds directive': ['european_climate_law'],
    'dg env': ['european_climate_law'],
    'dg clima': ['european_climate_law', 'eu_energy_policy'],
    'environmental liability': ['european_climate_law'],
    'deforestation regulation': ['european_climate_law'],
    'eudr': ['european_climate_law'],
    'medio ambiente': ['european_climate_law'],
    'environnement': ['european_climate_law'],
    'milieu': ['european_climate_law'],
    'medi ambient': ['european_climate_law'],
    'ambiente': ['european_climate_law'],

    # EU Taxation Policy
    'taxation': ['eu_budget_emu_law'],
    'tax policy': ['eu_budget_emu_law'],
    'vat': ['eu_budget_emu_law'],
    'vat directive': ['eu_budget_emu_law'],
    'excise': ['eu_budget_emu_law'],
    'excise duty': ['eu_budget_emu_law'],
    'minimum tax': ['eu_budget_emu_law'],
    'pillar one': ['eu_budget_emu_law'],
    'pillar two': ['eu_budget_emu_law'],
    'beps': ['eu_budget_emu_law'],
    'anti-tax avoidance': ['eu_budget_emu_law'],
    'atad': ['eu_budget_emu_law'],
    'dac': ['eu_budget_emu_law'],
    'directive on administrative cooperation': ['eu_budget_emu_law'],
    'unshell directive': ['eu_budget_emu_law'],
    'debra': ['eu_budget_emu_law'],
    'befit': ['eu_budget_emu_law'],
    'transfer pricing': ['eu_budget_emu_law'],
    'head': ['eu_budget_emu_law'],
    'carbon tax': ['eu_budget_emu_law'],
    'energy taxation directive': ['eu_budget_emu_law'],
    'tobacco taxation': ['eu_budget_emu_law'],
    'fiscalidad': ['eu_budget_emu_law'],
    'fiscalite': ['eu_budget_emu_law'],
    'belastingbeleid': ['eu_budget_emu_law'],
    'fiscalitat': ['eu_budget_emu_law'],

    # EU Fraud and Corruption
    'fraud': ['eu_financial_regulation_procurement'],
    'anti-fraud': ['eu_financial_regulation_procurement'],
    'pif directive': ['eu_financial_regulation_procurement'],
    'eu budget fraud': ['eu_financial_regulation_procurement'],
    'corruption': ['eu_financial_regulation_procurement'],
    'whistleblower': ['eu_financial_regulation_procurement'],
    'whistleblowing': ['eu_financial_regulation_procurement'],
    'whistleblower directive': ['eu_financial_regulation_procurement'],
    'money laundering': ['eu_financial_regulation_procurement'],
    'amld': ['eu_financial_regulation_procurement'],
    'anti-money laundering': ['eu_financial_regulation_procurement'],
    'aml package': ['eu_financial_regulation_procurement'],
    'amla': ['eu_financial_regulation_procurement'],
    'terrorist financing': ['eu_financial_regulation_procurement'],
    'beneficial ownership': ['eu_financial_regulation_procurement'],
    'fraude': ['eu_financial_regulation_procurement'],
    'corruption': ['eu_financial_regulation_procurement'],
    'blanchiment': ['eu_financial_regulation_procurement'],
    'witwassen': ['eu_financial_regulation_procurement'],

    # EU Justice and Security
    'justice': ['eu_migration_asylum_pact'],
    'area of freedom security and justice': ['eu_migration_asylum_pact'],
    'afsj': ['eu_migration_asylum_pact'],
    'schengen': ['eu_migration_asylum_pact'],
    'asylum': ['eu_migration_asylum_pact'],
    'migration': ['eu_migration_asylum_pact'],
    'migration pact': ['eu_migration_asylum_pact'],
    'frontex': ['eu_migration_asylum_pact'],
    'europol': ['eu_migration_asylum_pact'],
    'eurojust': ['eu_migration_asylum_pact'],
    'european arrest warrant': ['eu_migration_asylum_pact'],
    'mutual recognition': ['eu_migration_asylum_pact'],
    'dg home': ['eu_migration_asylum_pact'],
    'data protection': ['gdpr_data_protection'],
    'gdpr': ['gdpr_data_protection'],
    'law enforcement': ['eu_migration_asylum_pact'],
    'eu security union': ['eu_migration_asylum_pact'],
    'counter-terrorism': ['eu_migration_asylum_pact'],
    'organised crime': ['eu_migration_asylum_pact'],
    'cybersecurity': ['cybersecurity_act'],
    'seguridad': ['eu_migration_asylum_pact'],
    'securite': ['eu_migration_asylum_pact'],
    'veiligheid': ['eu_migration_asylum_pact'],
    'justicia': ['eu_migration_asylum_pact'],

    # EU Internal Market
    'internal market': ['digital_markets_act'],
    'single market act': ['digital_markets_act'],
    'four freedoms': ['digital_markets_act'],
    'free movement of goods': ['digital_markets_act'],
    'free movement of services': ['digital_markets_act'],
    'free movement of capital': ['digital_markets_act'],
    'free movement of workers': ['digital_markets_act'],
    'services directive': ['digital_markets_act'],
    'mutual recognition principle': ['digital_markets_act'],
    'standardisation': ['digital_markets_act'],
    'ce marking': ['digital_markets_act'],
    'market surveillance': ['digital_markets_act'],
    'digital single market': ['digital_markets_act'],
    'dsa': ['digital_markets_act'],
    'dma': ['digital_markets_act'],
    'digital services act': ['digital_markets_act'],
    'digital markets act': ['digital_markets_act'],
    'single market emergency instrument': ['digital_markets_act'],
    'smei': ['digital_markets_act'],
    'marche interieur': ['digital_markets_act'],
    'mercado interior': ['digital_markets_act'],
    'mercat interior': ['digital_markets_act'],
    'interne markt': ['digital_markets_act'],

    # EU Foreign and Security Policy
    'cfsp': ['eu_defence_procurement'],
    'common foreign and security policy': ['eu_defence_procurement'],
    'csdp': ['eu_defence_procurement'],
    'common security and defence': ['eu_defence_procurement'],
    'high representative': ['eu_defence_procurement'],
    'eeas': ['eu_defence_procurement'],
    'european external action service': ['eu_defence_procurement'],
    'eu sanctions': ['eu_defence_procurement'],
    'restrictive measures': ['eu_defence_procurement'],
    'sanctions libya': ['eu_defence_procurement'],
    'libya sanctions': ['eu_defence_procurement'],
    'libya': ['eu_defence_procurement'],
    'sanctions libye': ['eu_defence_procurement'],
    'sanciones libia': ['eu_defence_procurement'],
    'sancions libia': ['eu_defence_procurement'],
    'sanctions russia': ['eu_defence_procurement'],
    'russia sanctions': ['eu_defence_procurement'],
    'sanctions russie': ['eu_defence_procurement'],
    'sanciones rusia': ['eu_defence_procurement'],
    'sancions russia': ['eu_defence_procurement'],
    'sanctions syria': ['eu_defence_procurement'],
    'sanctions iran': ['eu_defence_procurement', 'iran_strait_hormuz_eu_response'],
    'sanctions belarus': ['eu_defence_procurement'],
    'eu defence': ['eu_defence_procurement'],
    'pesco': ['eu_defence_procurement'],
    'permanent structured cooperation': ['eu_defence_procurement'],
    'european defence fund': ['eu_defence_procurement'],
    'edf defence': ['eu_defence_procurement'],
    'eu military': ['eu_defence_procurement'],
    'eu missions': ['eu_defence_procurement'],
    'strategic compass': ['eu_defence_procurement'],
    'european peace facility': ['eu_defence_procurement'],
    'arms exports': ['eu_defence_procurement'],
    'white paper defence': ['eu_defence_procurement'],
    'readiness 2030': ['eu_defence_procurement'],
    'safe': ['eu_defence_procurement'],
    'politique etrangere': ['eu_defence_procurement'],
    'politica exterior': ['eu_defence_procurement'],
    'buitenlands beleid': ['eu_defence_procurement'],

    # EU External Relations
    'external relations': ['eu_trade_policy'],
    'association agreement': ['eu_trade_policy'],
    'partnership agreement': ['eu_trade_policy'],
    'eu-africa': ['eu_trade_policy'],
    'eu-china': ['eu_trade_policy'],
    'eu-us': ['eu_trade_policy'],
    'transatlantic': ['eu_trade_policy'],
    'eastern partnership': ['eu_trade_policy'],
    'european neighbourhood': ['eu_trade_policy'],
    'enp': ['eu_trade_policy'],
    'union for the mediterranean': ['eu_trade_policy'],
    'eu-latin america': ['eu_trade_policy'],
    'eu-asean': ['eu_trade_policy'],
    'relaciones exteriores': ['eu_trade_policy'],
    'relations exterieures': ['eu_trade_policy'],
    'buitenlandse betrekkingen': ['eu_trade_policy'],

    # EU Public Health
    'public health': ['eu_pharmaceutical_framework'],
    'health union': ['eu_pharmaceutical_framework'],
    'european health union': ['eu_pharmaceutical_framework'],
    'dg sante': ['eu_pharmaceutical_framework'],
    'ema': ['eu_pharmaceutical_framework', 'eu_pharmaceutical_framework'],
    'european medicines agency': ['eu_pharmaceutical_framework', 'eu_pharmaceutical_framework'],
    'ecdc': ['eu_pharmaceutical_framework'],
    'hera': ['eu_pharmaceutical_framework'],
    'pharmaceutical legislation': ['eu_pharmaceutical_framework', 'eu_pharmaceutical_legislation_reform'],
    'pharmaceutical strategy': ['eu_pharmaceutical_framework'],
    'health technology assessment': ['eu_pharmaceutical_framework'],
    'hta regulation': ['eu_pharmaceutical_framework'],
    'cross-border health': ['eu_pharmaceutical_framework'],
    'europe beating cancer': ['eu_beating_cancer_plan'],
    'cancer plan': ['eu_beating_cancer_plan'],
    'beating cancer': ['eu_beating_cancer_plan'],
    'cancer screening': ['eu_beating_cancer_plan'],
    'cancer inequalities': ['eu_beating_cancer_plan'],
    'hpv vaccination': ['eu_beating_cancer_plan'],
    'comprehensive cancer centre': ['eu_beating_cancer_plan'],
    'cancer imaging': ['eu_beating_cancer_plan'],
    'vasile-voiculescu': ['eu_beating_cancer_plan'],
    'cancer': ['eu_beating_cancer_plan'],
    'pla contra el cancer': ['eu_beating_cancer_plan'],
    'pla europeu contra el cancer': ['eu_beating_cancer_plan'],
    'plan contra el cancer': ['eu_beating_cancer_plan'],
    'plan cancer': ['eu_beating_cancer_plan'],
    'kankerbestrijding': ['eu_beating_cancer_plan'],
    'lotta contro il cancro': ['eu_beating_cancer_plan'],
    'mental health': ['eu_pharmaceutical_framework'],
    'antimicrobial resistance': ['eu_pharmaceutical_framework'],
    'amr': ['eu_pharmaceutical_framework'],
    'critical medicines': ['critical_medicines_act', 'eu_pharmaceutical_framework'],
    'salud publica': ['eu_pharmaceutical_framework'],
    'sante publique': ['eu_pharmaceutical_framework'],
    'volksgezondheid': ['eu_pharmaceutical_framework'],
    'salut publica': ['eu_pharmaceutical_framework'],
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
    'trade defense': ['eu_trade_defence', 'eu_trade_policy'],
    'foreign subsidies regulation': ['eu_trade_policy'],
    'cbam': ['eu_trade_policy'],
    'carbon border': ['eu_trade_policy'],
    'cbam certificate': ['eu_trade_policy'],
    'cbam certificates': ['eu_trade_policy'],
    'carbon border adjustment': ['eu_trade_policy'],
    'carbon leakage': ['eu_trade_policy'],
    'cbam importers': ['eu_trade_policy'],
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
    'unfair trading practices': ['eu_trade_policy'],
    'utp directive': ['eu_trade_policy'],
    'directive 2019/633': ['eu_trade_policy'],
    'regulation 2026/697': ['eu_trade_policy'],
    'unfair trading practices enforcement': ['eu_trade_policy'],
    'digital europe programme': ['eu_energy_policy'],
    'digital europe': ['eu_energy_policy'],
    'dep programme': ['eu_energy_policy'],
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
    'natura 2000 climate': ['natura_2000_sites_update'],
    'natura 2000 climate change': ['natura_2000_sites_update'],
    'natura 2000 adaptation': ['natura_2000_sites_update'],
    'natura 2000 fire': ['natura_2000_sites_update', 'wildfire_risk_management'],

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
    'regolamento sui mercati digitali': ['digital_markets_act'],
    'mercati digitali': ['digital_markets_act'],
    'wet digitale markten': ['digital_markets_act'],
    'gesetz uber digitale markte': ['digital_markets_act'],

    # SAFE / ReArm Europe / Readiness 2030
    'safe instrument': ['safe_rearm_europe'],
    'safe regulation': ['safe_rearm_europe'],
    'rearm europe': ['safe_rearm_europe'],
    'rearm': ['safe_rearm_europe'],
    'readiness 2030': ['safe_rearm_europe', 'eu_defence_procurement'],
    'defence loan': ['safe_rearm_europe'],
    'defence financing': ['safe_rearm_europe', 'eu_defence_procurement'],
    'defence procurement': ['safe_rearm_europe', 'eu_defence_procurement'],
    'eu defence spending': ['safe_rearm_europe', 'eu_defence_procurement'],
    'eu defence budget': ['safe_rearm_europe', 'eu_defence_procurement'],
    'european defence': ['safe_rearm_europe', 'eu_defence_procurement'],
    'defence industrial': ['safe_rearm_europe', 'eu_defence_procurement'],
    'defence industry': ['safe_rearm_europe', 'eu_defence_procurement'],
    'defence industrial base': ['safe_rearm_europe', 'eu_defence_procurement'],
    'dtib': ['safe_rearm_europe', 'eu_defence_procurement'],
    'edis': ['safe_rearm_europe', 'eu_defence_procurement'],
    'edip': ['safe_rearm_europe', 'eu_defence_procurement'],
    'kubilius': ['safe_rearm_europe', 'eu_defence_procurement'],
    'andrius kubilius': ['safe_rearm_europe', 'eu_defence_procurement'],
    'dg defis': ['eu_defence_procurement', 'eu_space_programme'],
    'nato 5%': ['safe_rearm_europe'],
    'defence union': ['safe_rearm_europe', 'eu_defence_procurement', 'ep_plenary_march_2026'],
    'common european defence': ['safe_rearm_europe', 'eu_defence_procurement', 'ep_plenary_march_2026'],
    'defensa europea': ['safe_rearm_europe', 'eu_defence_procurement'],
    'defense europeenne': ['safe_rearm_europe', 'eu_defence_procurement'],
    'difesa europea': ['safe_rearm_europe', 'eu_defence_procurement'],
    'difesa europeo': ['safe_rearm_europe', 'eu_defence_procurement'],
    'pacchetto difesa': ['safe_rearm_europe', 'eu_defence_procurement'],
    'europese defensie': ['safe_rearm_europe', 'eu_defence_procurement'],
    'eur 150 billion defence': ['safe_rearm_europe'],
    '150 billion loans': ['safe_rearm_europe'],
    'com(2025) 120': ['safe_rearm_europe'],
    '2025/0076': ['safe_rearm_europe'],
    # Defence capabilities and innovation
    'defence capabilities': ['safe_rearm_europe', 'eu_defence_procurement'],
    'military capabilities': ['safe_rearm_europe', 'eu_defence_procurement'],
    'ammunition production': ['eu_defence_procurement'],
    'joint procurement': ['eu_defence_procurement'],
    'collaborative procurement': ['eu_defence_procurement'],
    'european preference clause': ['eu_defence_procurement', 'safe_rearm_europe'],
    'defence r&d': ['eu_defence_procurement'],
    'european defence fund': ['eu_defence_procurement'],
    'escape clause defence': ['safe_rearm_europe'],
    'national escape clause': ['safe_rearm_europe'],
    'defence omnibus': ['eu_defence_procurement'],
    'virkkunen defence': ['eu_defence_procurement'],
    'henna virkkunen': ['eu_defence_procurement'],
    # AGILE -- expanded triggers
    'com(2026) 135': ['eu_defence_procurement'],
    '2026/0078': ['eu_defence_procurement'],
    'agile regulation': ['eu_defence_procurement'],
    'rapid defence innovation': ['eu_defence_procurement'],
    'defence disruptive': ['eu_defence_procurement'],
    'disruptive technologies defence': ['eu_defence_procurement'],
    'defence start-ups': ['eu_defence_procurement'],
    'defence startups funding': ['eu_defence_procurement'],
    'new defence players': ['eu_defence_procurement'],
    'helsing': ['eu_defence_procurement'],
    'frankenburg technologies': ['eu_defence_procurement'],
    'innovacion en defensa': ['eu_defence_procurement'],
    'innovacio en defensa': ['eu_defence_procurement'],
    'innovation en defense': ['eu_defence_procurement'],
    'innovazione nella difesa': ['eu_defence_procurement'],
    'defensie innovatie': ['eu_defence_procurement'],

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
    'innovation fund battery': ['battery_booster_strategy', 'innovation_fund'],
    # Innovation Fund (ETS-funded)
    'innovation fund': ['innovation_fund'],
    'innovation fund ets': ['innovation_fund'],
    'ets innovation fund': ['innovation_fund'],
    'innovation fund cinea': ['innovation_fund'],
    'cinea innovation': ['innovation_fund'],
    'innovation fund call': ['innovation_fund'],
    'innovation fund grant': ['innovation_fund'],
    'innovation fund project': ['innovation_fund'],
    'innovation fund auction': ['innovation_fund'],
    'innovation fund competitive bidding': ['innovation_fund'],
    'innovation fund hydrogen': ['innovation_fund'],
    'innovation fund decarbonisation': ['innovation_fund'],
    'eca special report 11': ['innovation_fund'],
    'eca 11/2026': ['innovation_fund'],
    'special report 11/2026': ['innovation_fund'],
    'eca innovation fund': ['innovation_fund'],
    'court of auditors innovation fund': ['innovation_fund'],
    'court of auditors innovation': ['innovation_fund'],
    'innovation fund ner 300': ['innovation_fund'],
    'ner 300': ['innovation_fund'],
    'innovation fund net-zero': ['innovation_fund'],
    'innovation fund net zero': ['innovation_fund'],
    'fonds pour innovation': ['innovation_fund'],
    'fondo de innovacion': ['innovation_fund'],
    'fondo per innovazione': ['innovation_fund'],
    'innovatiefonds': ['innovation_fund'],
    'fons innovacio': ['innovation_fund'],
    'innovationsfonds': ['innovation_fund'],
    'rfnbo auction': ['innovation_fund'],
    'rfnbo hydrogen': ['innovation_fund'],
    'european hydrogen bank auction': ['innovation_fund'],
    'clean-tech manufacturing call': ['innovation_fund'],
    'innovation fund large-scale': ['innovation_fund'],
    'innovation fund small-scale': ['innovation_fund'],
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

    # CSAM Regulation / Child Sexual Abuse Online
    'csam': ['csam_regulation_online'],
    'csam regulation': ['csam_regulation_online'],
    'child sexual abuse': ['csam_regulation_online'],
    'child sexual abuse online': ['csam_regulation_online'],
    'child sexual exploitation': ['csam_regulation_online'],
    'chat control': ['csam_regulation_online'],
    'chat controls': ['csam_regulation_online'],
    '2022/0155': ['csam_regulation_online'],
    'com(2022) 209': ['csam_regulation_online'],
    'com(2022)209': ['csam_regulation_online'],
    '2021/1232': ['csam_regulation_online'],
    '32021r1232': ['csam_regulation_online'],
    'eprivacy derogation': ['csam_regulation_online'],
    'temporary derogation csam': ['csam_regulation_online'],
    'voluntary csam detection': ['csam_regulation_online'],
    'csam detection': ['csam_regulation_online'],
    'child abuse material': ['csam_regulation_online'],
    'grooming online': ['csam_regulation_online'],
    'grooming detection': ['csam_regulation_online'],
    'child grooming': ['csam_regulation_online'],
    'eucsa': ['csam_regulation_online'],
    'eu centre child sexual abuse': ['csam_regulation_online'],
    'ncmec': ['csam_regulation_online'],
    'cybertipline': ['csam_regulation_online'],
    'photodna': ['csam_regulation_online'],
    'detection order csam': ['csam_regulation_online'],
    'zarzalejos csam': ['csam_regulation_online'],
    'birgit sippel': ['csam_regulation_online'],
    'child safety online': ['csam_regulation_online', 'dsa_enforcement'],
    'child protection online': ['csam_regulation_online', 'dsa_enforcement'],
    'protection of minors online': ['csam_regulation_online', 'dsa_enforcement'],
    'dsa minors': ['dsa_enforcement', 'csam_regulation_online'],
    'dsa article 28': ['dsa_enforcement', 'csam_regulation_online'],
    'age verification': ['csam_regulation_online', 'dsa_enforcement'],
    'online child safety': ['csam_regulation_online'],
    'abus sexual infantil': ['csam_regulation_online'],
    'abus sexuel enfants': ['csam_regulation_online'],
    'abuso sexual menores': ['csam_regulation_online'],
    'kindermisbruik': ['csam_regulation_online'],
    'abuso sessuale minori': ['csam_regulation_online'],
    'inhope': ['csam_regulation_online'],
    'operation cumberland': ['csam_regulation_online'],
    'ai generated csam': ['csam_regulation_online'],
    'sextortion': ['csam_regulation_online'],
    '2025/0429': ['csam_regulation_online'],
    'com(2025)0797': ['csam_regulation_online'],
    'special panel child safety': ['csam_regulation_online'],
    'bik strategy': ['csam_regulation_online'],
    'better internet for kids': ['csam_regulation_online'],

    # Digital Fairness Act
    'digital fairness act': ['digital_fairness_act'],
    'digital fairness': ['digital_fairness_act'],
    'dfa': ['digital_fairness_act'],
    'addictive design': ['digital_fairness_act'],
    'addictive design online': ['digital_fairness_act'],
    'dark patterns regulation': ['digital_fairness_act'],
    'dark patterns eu': ['digital_fairness_act'],
    'influencer marketing regulation': ['digital_fairness_act'],
    'influencer marketing eu': ['digital_fairness_act'],
    'influencer regulation': ['digital_fairness_act'],
    'kidfluencer': ['digital_fairness_act'],
    'kidfluencers': ['digital_fairness_act'],
    'loot boxes regulation': ['digital_fairness_act'],
    'loot boxes': ['digital_fairness_act'],
    'virtual currencies regulation': ['digital_fairness_act'],
    'subscription traps': ['digital_fairness_act'],
    'subscription cancellation': ['digital_fairness_act'],
    'confirmshaming': ['digital_fairness_act'],
    'roach motel': ['digital_fairness_act'],
    'sneak into basket': ['digital_fairness_act'],
    'forced continuity': ['digital_fairness_act'],
    'consumer fitness check': ['digital_fairness_act'],
    'fitness check consumer': ['digital_fairness_act'],
    'michael mcgrath': ['digital_fairness_act'],
    'influencer legal hub': ['digital_fairness_act'],
    'equite numerique': ['digital_fairness_act'],
    'equidad digital': ['digital_fairness_act'],
    'digitale eerlijkheid': ['digital_fairness_act'],
    'equita digitale': ['digital_fairness_act'],
    'equitat digital': ['digital_fairness_act'],

    # ePrivacy Directive and Regulation
    'eprivacy': ['eprivacy_regulation'],
    'eprivacy directive': ['eprivacy_regulation'],
    'eprivacy regulation': ['eprivacy_regulation'],
    'e-privacy': ['eprivacy_regulation'],
    'directive 2002/58': ['eprivacy_regulation'],
    '2002/58': ['eprivacy_regulation'],
    '32002l0058': ['eprivacy_regulation'],
    'cookie directive': ['eprivacy_regulation'],
    'cookie consent eu': ['eprivacy_regulation'],
    'cookie law': ['eprivacy_regulation'],
    'confidentiality of communications': ['eprivacy_regulation'],
    'confidentiality electronic communications': ['eprivacy_regulation'],
    'traffic data directive': ['eprivacy_regulation'],
    'metadata processing eu': ['eprivacy_regulation'],
    'direct marketing eu': ['eprivacy_regulation'],
    'unsolicited communications eu': ['eprivacy_regulation'],
    'soft opt-in': ['eprivacy_regulation'],
    'soft opt in': ['eprivacy_regulation'],
    'com(2017) 10': ['eprivacy_regulation'],
    'com(2017)10': ['eprivacy_regulation'],
    '2017/0003': ['eprivacy_regulation'],
    'privacy electronic communications': ['eprivacy_regulation'],
    'vie privee communications': ['eprivacy_regulation'],
    'privacidad comunicaciones': ['eprivacy_regulation'],
    'privacy comunicazioni': ['eprivacy_regulation'],
    'privacitat comunicacions': ['eprivacy_regulation'],
    'privacy elektronische communicatie': ['eprivacy_regulation'],

    # Cross-references: DMA-GDPR interplay
    'dma gdpr': ['digital_markets_act', 'dsa_enforcement'],
    'dma gdpr interplay': ['digital_markets_act'],
    'gatekeeper data protection': ['digital_markets_act'],
    'gatekeeper gdpr': ['digital_markets_act'],
    'dma consent': ['digital_markets_act'],

    # IPA III and EU Enlargement Funding
    'ipa': ['eu_funding_ipa_enlargement'],
    'ipa iii': ['eu_funding_ipa_enlargement'],
    'ipa 3': ['eu_funding_ipa_enlargement'],
    'ipa three': ['eu_funding_ipa_enlargement'],
    'pre-accession': ['eu_funding_ipa_enlargement'],
    'pre accession': ['eu_funding_ipa_enlargement'],
    'preaccession': ['eu_funding_ipa_enlargement'],
    'enlargement funding': ['eu_funding_ipa_enlargement'],
    'enlargement policy': ['eu_funding_ipa_enlargement'],
    'candidate country': ['eu_funding_ipa_enlargement'],
    'candidate countries': ['eu_funding_ipa_enlargement'],
    'western balkans': ['eu_funding_ipa_enlargement'],
    'western balkan': ['eu_funding_ipa_enlargement'],
    'reform and growth facility': ['eu_funding_ipa_enlargement'],
    'growth plan western balkans': ['eu_funding_ipa_enlargement'],
    'wbif': ['eu_funding_ipa_enlargement'],
    'western balkans investment framework': ['eu_funding_ipa_enlargement'],
    'ipard': ['eu_funding_ipa_enlargement'],
    'ipard iii': ['eu_funding_ipa_enlargement'],
    'albania eu': ['eu_funding_ipa_enlargement'],
    'albania funding': ['eu_funding_ipa_enlargement'],
    'kosovo eu': ['eu_funding_ipa_enlargement'],
    'montenegro eu': ['eu_funding_ipa_enlargement'],
    'north macedonia eu': ['eu_funding_ipa_enlargement'],
    'serbia eu': ['eu_funding_ipa_enlargement'],
    'bosnia eu': ['eu_funding_ipa_enlargement'],
    'eu accession': ['eu_funding_ipa_enlargement'],
    'accession process': ['eu_funding_ipa_enlargement'],
    'accession negotiations': ['eu_funding_ipa_enlargement'],
    'dg near': ['eu_funding_ipa_enlargement'],
    '2021/1529': ['eu_funding_ipa_enlargement'],
    'regulation 2021/1529': ['eu_funding_ipa_enlargement'],
    'eu funding albania': ['eu_funding_ipa_enlargement'],
    'eu funding balkans': ['eu_funding_ipa_enlargement'],
    'agrifood albania': ['eu_funding_ipa_enlargement'],
    'wine albania': ['eu_funding_ipa_enlargement'],
    'interreg ipa': ['eu_funding_ipa_enlargement'],
    'south adriatic': ['eu_funding_ipa_enlargement'],
    'cross-border cooperation balkans': ['eu_funding_ipa_enlargement'],
    'aide de preadhesion': ['eu_funding_ipa_enlargement'],
    'ayuda de preadhesion': ['eu_funding_ipa_enlargement'],
    'assistenza preadesione': ['eu_funding_ipa_enlargement'],
    'pretoetredingssteun': ['eu_funding_ipa_enlargement'],
    'ajuda de preadhesio': ['eu_funding_ipa_enlargement'],
    'fondi albania': ['eu_funding_ipa_enlargement'],
    'fondi ue albania': ['eu_funding_ipa_enlargement'],
    'fondi balcani': ['eu_funding_ipa_enlargement'],
    'progetti ue albania': ['eu_funding_ipa_enlargement'],
    'finanziamenti albania': ['eu_funding_ipa_enlargement'],
    'bandi albania': ['eu_funding_ipa_enlargement'],
    'albania agrifood': ['eu_funding_ipa_enlargement'],
    'albania agricoltura': ['eu_funding_ipa_enlargement'],
    'albania vino': ['eu_funding_ipa_enlargement'],
    'fonds albanie': ['eu_funding_ipa_enlargement'],
    'fondos albania': ['eu_funding_ipa_enlargement'],
    'eu funds albania': ['eu_funding_ipa_enlargement'],
    'eu grants albania': ['eu_funding_ipa_enlargement'],
    'eu grants balkans': ['eu_funding_ipa_enlargement'],
    "l'albania": ['eu_funding_ipa_enlargement'],
    "l'albanie": ['eu_funding_ipa_enlargement'],
    'fondi ue': ['eu_funding_ipa_enlargement'],
    'fondi europei': ['eu_funding_ipa_enlargement'],
    'fonds europeens': ['eu_funding_ipa_enlargement'],
    'fondos europeos': ['eu_funding_ipa_enlargement'],
    'fons europeus': ['eu_funding_ipa_enlargement'],

    # Iran War, Strait of Hormuz, EU Crisis Response
    'iran': ['iran_strait_hormuz_eu_response'],
    'iran war': ['iran_strait_hormuz_eu_response'],
    'iran conflict': ['iran_strait_hormuz_eu_response'],
    'strait of hormuz': ['iran_strait_hormuz_eu_response', 'eu_energy_policy'],
    'hormuz': ['iran_strait_hormuz_eu_response', 'eu_energy_policy'],
    'oil reserves': ['iran_strait_hormuz_eu_response', 'eu_energy_policy'],
    'oil price': ['iran_strait_hormuz_eu_response', 'eu_energy_policy'],
    'oil prices': ['iran_strait_hormuz_eu_response', 'eu_energy_policy'],
    'brent crude': ['iran_strait_hormuz_eu_response', 'eu_energy_policy'],
    'middle east': ['iran_strait_hormuz_eu_response'],
    'middle east crisis': ['iran_strait_hormuz_eu_response'],
    'eu crisis measures': ['iran_strait_hormuz_eu_response'],
    'eu crisis measures middle east': ['iran_strait_hormuz_eu_response'],
    'middle east energy': ['iran_strait_hormuz_eu_response', 'eu_energy_policy'],
    'gulf states': ['iran_strait_hormuz_eu_response'],
    'eu maritime mission': ['iran_strait_hormuz_eu_response'],
    'kallas maritime': ['iran_strait_hormuz_eu_response'],
    'guerre iran': ['iran_strait_hormuz_eu_response'],
    'guerra iran': ['iran_strait_hormuz_eu_response'],
    'oorlog iran': ['iran_strait_hormuz_eu_response'],
    'detruit ormuz': ['iran_strait_hormuz_eu_response'],
    'estrecho de ormuz': ['iran_strait_hormuz_eu_response'],
    'stretto di hormuz': ['iran_strait_hormuz_eu_response'],
    'straat van hormuz': ['iran_strait_hormuz_eu_response'],
    'estret dhormuz': ['iran_strait_hormuz_eu_response'],
    'red sea': ['iran_strait_hormuz_eu_response'],
    'red sea crisis': ['iran_strait_hormuz_eu_response'],
    'aspides': ['iran_strait_hormuz_eu_response'],
    'eunavfor': ['iran_strait_hormuz_eu_response', 'eu_defence_procurement'],
    'eunavfor atalanta': ['iran_strait_hormuz_eu_response', 'eu_defence_procurement'],
    'atalanta': ['iran_strait_hormuz_eu_response'],
    'indian ocean maritime': ['iran_strait_hormuz_eu_response'],
    'maritime operations red sea': ['iran_strait_hormuz_eu_response'],
    'houthi': ['iran_strait_hormuz_eu_response'],

    # Bosnia sanctions / Western Balkans restrictive measures
    'bosnia sanctions': ['eu_funding_ipa_enlargement'],
    'bosnia restrictive measures': ['eu_funding_ipa_enlargement'],
    'bosnia and herzegovina sanctions': ['eu_funding_ipa_enlargement'],
    'western balkans sanctions': ['eu_funding_ipa_enlargement'],

    # EU Inc. -- 28th Regime Corporate Legal Framework
    'eu inc': ['28th_regime_innovation_act'],
    'eu inc.': ['28th_regime_innovation_act'],
    '28th regime': ['28th_regime_innovation_act'],
    '28e regime': ['28th_regime_innovation_act'],
    '28. regime': ['28th_regime_innovation_act'],
    'twenty-eighth regime': ['28th_regime_innovation_act'],
    'european innovation act': ['28th_regime_innovation_act'],
    'innovation act': ['28th_regime_innovation_act'],
    'merger guidelines': ['28th_regime_innovation_act', 'competition_law_enforcement'],
    'merger guidelines review': ['28th_regime_innovation_act', 'competition_law_enforcement'],
    'eu corporate law': ['28th_regime_innovation_act'],
    'eu company law': ['28th_regime_innovation_act'],
    'cross-border company': ['28th_regime_innovation_act'],
    'regulatory sandbox': ['28th_regime_innovation_act'],
    'regulatory sandboxes': ['28th_regime_innovation_act'],
    'innovation principle': ['28th_regime_innovation_act'],
    'vingt-huitieme regime': ['28th_regime_innovation_act'],
    'regimen 28': ['28th_regime_innovation_act'],
    'regime 28': ['28th_regime_innovation_act'],
    '28esimo regime': ['28th_regime_innovation_act'],
    '28e regime eu': ['28th_regime_innovation_act'],
    'acte innovation europeen': ['28th_regime_innovation_act'],
    'acta innovacion europea': ['28th_regime_innovation_act'],
    'atto innovazione europea': ['28th_regime_innovation_act'],
    'europese innovatiewet': ['28th_regime_innovation_act'],
    'eu company form': ['28th_regime_innovation_act'],
    'eu-eso': ['28th_regime_innovation_act'],
    'eu employee stock option': ['28th_regime_innovation_act'],
    'employee stock option plan': ['28th_regime_innovation_act'],
    'digital register of shares': ['28th_regime_innovation_act'],
    'eu company certificate': ['28th_regime_innovation_act'],
    'company registration 48 hours': ['28th_regime_innovation_act'],
    'start a company in the eu': ['28th_regime_innovation_act'],
    'start a business in europe': ['28th_regime_innovation_act'],
    'eu startup legal form': ['28th_regime_innovation_act'],
    'eu scaleup': ['28th_regime_innovation_act'],
    'societas europaea': ['28th_regime_innovation_act'],
    'non-par value shares': ['28th_regime_innovation_act'],
    'eu insolvency startup': ['28th_regime_innovation_act'],
    'fast-track liquidation': ['28th_regime_innovation_act'],
    'bris interconnection': ['28th_regime_innovation_act'],
    'eu central interface': ['28th_regime_innovation_act'],
    'safe agreement eu': ['28th_regime_innovation_act'],
    'kiss convertible note': ['28th_regime_innovation_act'],
    'convertible instrument eu': ['28th_regime_innovation_act'],
    'creer une entreprise en europe': ['28th_regime_innovation_act'],
    'crear empresa en europa': ['28th_regime_innovation_act'],
    'eu bedrijf oprichten': ['28th_regime_innovation_act'],
    'creare impresa in europa': ['28th_regime_innovation_act'],
    'com(2026) 321': ['28th_regime_innovation_act'],
    'com(2026) 320': ['28th_regime_innovation_act'],

    # Digital Networks Act
    'digital networks act': ['digital_networks_act'],
    'digital networks': ['digital_networks_act'],
    'telecoms regulation': ['digital_networks_act'],
    'electronic communications code': ['digital_networks_act'],
    'eecc': ['digital_networks_act'],
    'spectrum management eu': ['digital_networks_act'],
    'satellite authorisation eu': ['digital_networks_act'],
    '5g regulation eu': ['digital_networks_act'],
    '6g regulation eu': ['digital_networks_act'],
    'telecoms single market': ['digital_networks_act'],
    'loi reseaux numeriques': ['digital_networks_act'],
    'ley redes digitales': ['digital_networks_act'],
    'legge reti digitali': ['digital_networks_act'],
    'digitale netwerkenwet': ['digital_networks_act'],
    'llei de xarxes digitals': ['digital_networks_act'],
    'dna telecoms': ['digital_networks_act'],
    'com(2026) 0016': ['digital_networks_act'],
    'com(2026)0016': ['digital_networks_act'],
    '2026/0013(cod)': ['digital_networks_act'],
    '2026/0013': ['digital_networks_act'],
    'copper switch-off': ['digital_networks_act'],
    'copper switch off': ['digital_networks_act'],
    'fibre to the home': ['digital_networks_act'],
    'ftth regulation': ['digital_networks_act'],
    'spectrum harmonisation': ['digital_networks_act'],
    'spectrum licence duration': ['digital_networks_act'],
    'satellite authorisation': ['digital_networks_act'],
    'net neutrality regulation': ['digital_networks_act'],
    'open internet regulation': ['digital_networks_act'],
    'berec regulation': ['digital_networks_act'],
    'office for digital networks': ['digital_networks_act'],
    'odn telecoms': ['digital_networks_act'],
    'radio spectrum policy': ['digital_networks_act'],
    'high-risk supplier 5g': ['digital_networks_act'],
    'huawei 5g ban': ['digital_networks_act'],
    'universal service obligation telecoms': ['digital_networks_act'],
    'network slicing': ['digital_networks_act'],
    'single-passport authorisation': ['digital_networks_act'],
    'telecoms single passport': ['digital_networks_act'],

    # EU-US Trade Deal 2026
    'eu us trade': ['eu_us_trade_deal_2026'],
    'eu-us trade': ['eu_us_trade_deal_2026'],
    'us trade deal': ['eu_us_trade_deal_2026'],
    'us tariffs': ['eu_us_trade_deal_2026'],
    'trump tariffs': ['eu_us_trade_deal_2026'],
    'trade war': ['eu_us_trade_deal_2026'],
    'transatlantic trade': ['eu_us_trade_deal_2026'],
    'trump trade': ['eu_us_trade_deal_2026'],
    'trump nato': ['iran_strait_hormuz_eu_response', 'eu_us_trade_deal_2026'],
    'borrell trade': ['eu_us_trade_deal_2026'],
    'eu-us deal': ['eu_us_trade_deal_2026'],
    'eu us deal': ['eu_us_trade_deal_2026'],
    'trade deal vote': ['eu_us_trade_deal_2026'],
    'inta committee': ['eu_us_trade_deal_2026'],
    'accord commercial ue-us': ['eu_us_trade_deal_2026'],
    'acuerdo comercial ue-eeuu': ['eu_us_trade_deal_2026'],
    'accordo commerciale ue-usa': ['eu_us_trade_deal_2026'],
    'handelsakkoord eu-vs': ['eu_us_trade_deal_2026'],
    'acord comercial ue-eua': ['eu_us_trade_deal_2026'],
    'com(2025)471': ['eu_us_trade_deal_2026'],
    'com(2025)472': ['eu_us_trade_deal_2026'],
    'com(2025) 471': ['eu_us_trade_deal_2026'],
    'com(2025) 472': ['eu_us_trade_deal_2026'],
    '2025/0261': ['eu_us_trade_deal_2026'],
    '2025/0260': ['eu_us_trade_deal_2026'],
    'bernd lange': ['eu_us_trade_deal_2026'],
    'framework agreement trade': ['eu_us_trade_deal_2026'],
    'tariff reductions us': ['eu_us_trade_deal_2026'],
    'tariff quotas us': ['eu_us_trade_deal_2026'],
    'customs duties us': ['eu_us_trade_deal_2026'],
    'section 232': ['eu_us_trade_deal_2026'],
    'reciprocal tariff': ['eu_us_trade_deal_2026'],

    # PPWR - Packaging and Packaging Waste Regulation
    'ppwr': ['ecodesign_digital_product_passport'],
    'packaging regulation': ['ecodesign_digital_product_passport'],
    'packaging waste regulation': ['ecodesign_digital_product_passport'],
    'packaging waste': ['ecodesign_digital_product_passport'],
    'single-use plastic': ['ecodesign_digital_product_passport'],
    'packaging law': ['ecodesign_digital_product_passport'],
    'reglamento envases': ['ecodesign_digital_product_passport'],
    'envases': ['ecodesign_digital_product_passport'],
    'residuos de envases': ['ecodesign_digital_product_passport'],
    'envases sostenibles': ['ecodesign_digital_product_passport'],
    'regulacio envasos': ['ecodesign_digital_product_passport'],
    'envasos': ['ecodesign_digital_product_passport'],
    'reglement emballages': ['ecodesign_digital_product_passport'],
    'emballages': ['ecodesign_digital_product_passport'],
    'regolamento imballaggi': ['ecodesign_digital_product_passport'],
    'imballaggi': ['ecodesign_digital_product_passport'],
    'verpakkingsverordening': ['ecodesign_digital_product_passport'],
    'verpakking': ['ecodesign_digital_product_passport'],

    # European Council March 2026
    'european council': ['iran_strait_hormuz_eu_response', 'mff_2028_2034', 'safe_rearm_europe', 'eu_competitiveness_council_debate'],
    'european council march': ['iran_strait_hormuz_eu_response', 'mff_2028_2034', 'safe_rearm_europe', 'eu_competitiveness_council_debate'],
    'european council summit': ['iran_strait_hormuz_eu_response', 'mff_2028_2034', 'safe_rearm_europe', 'eu_competitiveness_council_debate'],
    'european council 19 march': ['iran_strait_hormuz_eu_response', 'mff_2028_2034', 'safe_rearm_europe', 'eu_competitiveness_council_debate'],
    'european council 19-20 march': ['iran_strait_hormuz_eu_response', 'mff_2028_2034', 'safe_rearm_europe', 'eu_competitiveness_council_debate'],
    'euco': ['iran_strait_hormuz_eu_response', 'mff_2028_2034', 'eu_competitiveness_council_debate'],
    'eu summit': ['iran_strait_hormuz_eu_response', 'mff_2028_2034', 'eu_competitiveness_council_debate'],
    'eu leaders summit': ['iran_strait_hormuz_eu_response', 'mff_2028_2034', 'eu_competitiveness_council_debate'],
    'one europe one market': ['mff_2028_2034', '28th_regime_innovation_act'],
    'antonio costa': ['iran_strait_hormuz_eu_response'],
    'consejo europeo': ['iran_strait_hormuz_eu_response'],
    'conseil europeen': ['iran_strait_hormuz_eu_response'],
    'consiglio europeo': ['iran_strait_hormuz_eu_response'],
    'europese raad': ['iran_strait_hormuz_eu_response'],
    'consell europeu': ['iran_strait_hormuz_eu_response'],

    # European Climate Law
    'climate law': ['european_climate_law'],
    'european climate law': ['european_climate_law'],
    'climate neutrality': ['european_climate_law'],
    'climate neutral': ['european_climate_law'],
    '2040 target': ['european_climate_law'],
    '2040 climate': ['european_climate_law'],
    '2050 climate': ['european_climate_law'],
    'net zero': ['european_climate_law'],
    'net-zero': ['european_climate_law'],
    'ghg reduction': ['european_climate_law'],
    'greenhouse gas': ['european_climate_law'],
    'emissions reduction target': ['european_climate_law'],
    '90% reduction': ['european_climate_law'],
    '90 percent': ['european_climate_law'],
    'carbon credits': ['european_climate_law'],
    'international carbon credits': ['european_climate_law'],
    'ets2': ['european_climate_law', 'eu_energy_policy'],
    'emissions trading': ['european_climate_law', 'eu_energy_policy'],
    'esabcc': ['european_climate_law'],
    'scientific advisory board climate': ['european_climate_law'],
    'fit for 55': ['european_climate_law', 'eu_energy_policy'],
    'fitfor55': ['european_climate_law', 'eu_energy_policy'],
    '2021/1119': ['european_climate_law'],
    '2026/667': ['european_climate_law'],
    '2025/0524': ['european_climate_law'],
    'ondrej knotek': ['european_climate_law'],
    'knotek': ['european_climate_law'],
    'loi climat': ['european_climate_law'],
    'ley del clima': ['european_climate_law'],
    'ley europea del clima': ['european_climate_law'],
    'llei del clima': ['european_climate_law'],
    'llei europea del clima': ['european_climate_law'],
    'legge sul clima': ['european_climate_law'],
    'legge europea sul clima': ['european_climate_law'],
    'klimaatwet': ['european_climate_law'],
    'europese klimaatwet': ['european_climate_law'],
    'neutralite climatique': ['european_climate_law'],
    'neutralidad climatica': ['european_climate_law'],
    'neutralitat climatica': ['european_climate_law'],
    'neutralita climatica': ['european_climate_law'],
    'klimaatneutraliteit': ['european_climate_law'],
    'carbon budget': ['european_climate_law'],
    'effort sharing': ['european_climate_law'],
    'lulucf': ['european_climate_law'],
    'social climate fund': ['european_climate_law'],

    # ECB Monetary Policy
    'ecb': ['ecb_monetary_policy'],
    'european central bank': ['ecb_monetary_policy'],
    'interest rate': ['ecb_monetary_policy'],
    'interest rates': ['ecb_monetary_policy'],
    'deposit facility': ['ecb_monetary_policy'],
    'main refinancing': ['ecb_monetary_policy'],
    'monetary policy': ['ecb_monetary_policy'],
    'rate cut': ['ecb_monetary_policy'],
    'rate hike': ['ecb_monetary_policy'],
    'rate decision': ['ecb_monetary_policy'],
    'governing council': ['ecb_monetary_policy'],
    'lagarde': ['ecb_monetary_policy'],
    'christine lagarde': ['ecb_monetary_policy'],
    'inflation target': ['ecb_monetary_policy'],
    'taux directeur': ['ecb_monetary_policy'],
    'taux interet': ['ecb_monetary_policy'],
    'tipo de interes': ['ecb_monetary_policy'],
    'tipus interes': ['ecb_monetary_policy'],
    'tasso interesse': ['ecb_monetary_policy'],
    'rente': ['ecb_monetary_policy'],
    'politique monetaire': ['ecb_monetary_policy'],
    'politica monetaria': ['ecb_monetary_policy'],
    'monetair beleid': ['ecb_monetary_policy'],
    'exchange rate': ['ecb_monetary_policy'],
    'euro exchange': ['ecb_monetary_policy'],

    # EU Water Legislation
    'water framework directive': ['eu_water_legislation', 'european_climate_law'],
    'water directive': ['eu_water_legislation'],
    'water legislation': ['eu_water_legislation'],
    'water policy': ['eu_water_legislation'],
    'water law': ['eu_water_legislation'],
    'water quality': ['eu_water_legislation'],
    'drinking water': ['eu_water_legislation'],
    'groundwater': ['eu_water_legislation'],
    'bathing water': ['eu_water_legislation'],
    'wastewater': ['eu_water_legislation'],
    'urban wastewater': ['eu_water_legislation'],
    'water resilience': ['eu_water_legislation'],
    'water efficiency': ['eu_water_legislation'],
    'river basin': ['eu_water_legislation'],
    'flood directive': ['eu_water_legislation'],
    'nitrates directive': ['eu_water_legislation'],
    '2000/60': ['eu_water_legislation'],
    '2020/2184': ['eu_water_legislation'],
    'directive eau': ['eu_water_legislation'],
    'directiva agua': ['eu_water_legislation'],
    'directiva aigua': ['eu_water_legislation'],
    'direttiva acqua': ['eu_water_legislation'],
    'waterrichtlijn': ['eu_water_legislation'],
    'eau potable': ['eu_water_legislation'],
    'agua potable': ['eu_water_legislation'],
    'acqua potabile': ['eu_water_legislation'],
    'drinkwater': ['eu_water_legislation'],

    # EU Taxonomy and Sustainable Finance
    'eu taxonomy': ['eu_taxonomy_sustainable_finance'],
    'taxonomy regulation': ['eu_taxonomy_sustainable_finance'],
    'sustainable finance': ['eu_taxonomy_sustainable_finance'],
    'green taxonomy': ['eu_taxonomy_sustainable_finance'],
    'taxonomy aligned': ['eu_taxonomy_sustainable_finance'],
    'taxonomy eligible': ['eu_taxonomy_sustainable_finance'],
    'sfdr': ['eu_taxonomy_sustainable_finance'],
    'sustainable finance disclosure': ['eu_taxonomy_sustainable_finance'],
    'green bond': ['eu_taxonomy_sustainable_finance'],
    'green bonds': ['eu_taxonomy_sustainable_finance'],
    'csrd': ['eu_taxonomy_sustainable_finance'],
    'sustainability reporting': ['eu_taxonomy_sustainable_finance'],
    'technical screening criteria': ['eu_taxonomy_sustainable_finance'],
    'do no significant harm': ['eu_taxonomy_sustainable_finance'],
    'dnsh': ['eu_taxonomy_sustainable_finance'],
    '2020/852': ['eu_taxonomy_sustainable_finance'],
    '2019/2088': ['eu_taxonomy_sustainable_finance'],
    'taxonomie': ['eu_taxonomy_sustainable_finance'],
    'finance durable': ['eu_taxonomy_sustainable_finance'],
    'finanza sostenibile': ['eu_taxonomy_sustainable_finance'],
    'finanzas sostenibles': ['eu_taxonomy_sustainable_finance'],
    'finances durables': ['eu_taxonomy_sustainable_finance'],
    'duurzame financiering': ['eu_taxonomy_sustainable_finance'],
    'esg': ['eu_taxonomy_sustainable_finance'],
    'greenwashing': ['eu_taxonomy_sustainable_finance'],
    'platform sustainable finance': ['eu_taxonomy_sustainable_finance'],
    # Banking Union Reform (CMDI Package)
    'banking union': ['banking_union_reform'],
    'banking union reform': ['banking_union_reform'],
    'banking reform': ['banking_union_reform'],
    'bank reform': ['banking_union_reform'],
    'deposit protection': ['banking_union_reform'],
    'reforme bancaire': ['banking_union_reform'],
    'reforma bancaria': ['banking_union_reform'],
    'reforma bancaria': ['banking_union_reform'],
    'hervorming banken': ['banking_union_reform'],
    'cmdi': ['banking_union_reform'],
    'crisis management deposit insurance': ['banking_union_reform'],
    'single resolution mechanism': ['banking_union_reform'],
    'srm regulation': ['banking_union_reform'],
    'srm reform': ['banking_union_reform'],
    'brrd': ['banking_union_reform'],
    'bank recovery resolution': ['banking_union_reform'],
    'bank recovery and resolution': ['banking_union_reform'],
    'dgsd': ['banking_union_reform'],
    'deposit guarantee scheme': ['banking_union_reform'],
    'deposit guarantee': ['banking_union_reform'],
    'deposit insurance': ['banking_union_reform'],
    'edis': ['banking_union_reform'],
    'single resolution board': ['banking_union_reform'],
    'bail-in': ['banking_union_reform'],
    'bail in': ['banking_union_reform'],
    'bank resolution': ['banking_union_reform'],
    '806/2014': ['banking_union_reform'],
    '2014/59': ['banking_union_reform'],
    '2014/49': ['banking_union_reform'],
    '2023/0111': ['banking_union_reform'],
    '2023/0112': ['banking_union_reform'],
    '2023/0113': ['banking_union_reform'],
    'irene tinagli': ['banking_union_reform'],
    'union bancaire': ['banking_union_reform'],
    'union bancaria': ['banking_union_reform'],
    'unione bancaria': ['banking_union_reform'],
    'bankenunie': ['banking_union_reform'],
    'unio bancaria': ['banking_union_reform'],
    # CRM Act Amendment (ITRE, Chahim)
    'critical raw materials act': ['industrial_accelerator_act'],
    'crma': ['industrial_accelerator_act'],
    'crm act': ['industrial_accelerator_act'],
    'critical raw materials': ['industrial_accelerator_act'],
    'reg 2024/1252': ['industrial_accelerator_act'],
    '2024/1252': ['industrial_accelerator_act'],
    'mohammed chahim': ['industrial_accelerator_act'],
    'matieres premieres critiques': ['industrial_accelerator_act'],
    'materias primas criticas': ['industrial_accelerator_act'],
    'materies primeres critiques': ['industrial_accelerator_act'],
    'materie prime critiche': ['industrial_accelerator_act'],
    'kritieke grondstoffen': ['industrial_accelerator_act'],
    # NZIA Implementing Regulation
    '32026r0718': ['industrial_accelerator_act'],
    'reg 2026/718': ['industrial_accelerator_act'],
    '2026/718': ['industrial_accelerator_act'],
    'nzia implementing': ['industrial_accelerator_act'],
    # ETS for Buildings and Transport (Market Stability Reserve)
    'ets buildings': ['eu_water_legislation', 'european_climate_law'],
    'ets transport': ['eu_water_legislation', 'european_climate_law'],
    'ets brt': ['eu_water_legislation'],
    'market stability reserve buildings': ['eu_water_legislation'],
    'market stability reserve transport': ['eu_water_legislation'],
    # Environmental Quality Standards (Water)
    'environmental quality standards': ['eu_water_legislation'],
    'eqs directive': ['eu_water_legislation'],
    'priority substances': ['eu_water_legislation'],
    'pfas water': ['eu_water_legislation'],
    '2008/105': ['eu_water_legislation'],
    # Military Equipment Transport
    'military equipment transport': ['eu_defence_procurement'],
    'military transport framework': ['eu_defence_procurement'],
    'military mobility': ['eu_defence_procurement'],
    'qualitative military edge': ['eu_defence_procurement'],
    'agile defence': ['eu_defence_procurement'],
    'agile programme': ['eu_defence_procurement'],
    'agile innovation': ['eu_defence_procurement'],
    'defence innovation': ['eu_defence_procurement'],
    'defence innovation agency': ['eu_defence_procurement'],
    'defence startups': ['eu_defence_procurement'],
    'defence smes': ['eu_defence_procurement'],
    'disruptive defence': ['eu_defence_procurement'],
    'college 25 march': ['eu_defence_procurement'],
    'college meeting 25 march': ['eu_defence_procurement'],
    'college defence': ['eu_defence_procurement'],
    'college military': ['eu_defence_procurement'],
    # Wildfire Risk Management (Communication, 25 March 2026)
    'wildfire': ['wildfire_risk_management'],
    'wildfire risk': ['wildfire_risk_management'],
    'wildfire management': ['wildfire_risk_management'],
    'wildfires': ['wildfire_risk_management'],
    'forest fire': ['wildfire_risk_management'],
    'forest fires': ['wildfire_risk_management'],
    'incendies de foret': ['wildfire_risk_management'],
    'incendis forestals': ['wildfire_risk_management'],
    'incendios forestales': ['wildfire_risk_management'],
    'bosbrand': ['wildfire_risk_management'],
    'effis': ['wildfire_risk_management'],
    'firefighting fleet': ['wildfire_risk_management'],
    'resceu firefighting': ['wildfire_risk_management'],
    'firefighting aircraft': ['wildfire_risk_management'],
    'wildfire prevention': ['wildfire_risk_management'],
    'wildfire preparedness': ['wildfire_risk_management'],
    'wildland urban interface': ['wildfire_risk_management'],
    'fire risk management': ['wildfire_risk_management'],
    # Aviation and Air Transport Policy
    'aviation': ['aviation_transport_policy'],
    'aviation policy': ['aviation_transport_policy'],
    'aviation legislation': ['aviation_transport_policy'],
    'airline': ['aviation_transport_policy'],
    'airlines': ['aviation_transport_policy'],
    'air transport': ['aviation_transport_policy'],
    'air transport agreement': ['aviation_transport_policy'],
    'refueleu': ['aviation_transport_policy'],
    'refueleu aviation': ['aviation_transport_policy'],
    'sustainable aviation fuel': ['aviation_transport_policy'],
    'sustainable aviation fuels': ['aviation_transport_policy'],
    'saf mandate': ['aviation_transport_policy'],
    'saf blending': ['aviation_transport_policy'],
    'eu261': ['aviation_transport_policy'],
    'eu 261': ['aviation_transport_policy'],
    'passenger rights aviation': ['aviation_transport_policy'],
    'flight delay compensation': ['aviation_transport_policy'],
    'flight cancellation': ['aviation_transport_policy'],
    'single european sky': ['aviation_transport_policy'],
    'ses2+': ['aviation_transport_policy'],
    'airspace management': ['aviation_transport_policy'],
    'eurocontrol': ['aviation_transport_policy'],
    'easa': ['aviation_transport_policy'],
    'aviation safety': ['aviation_transport_policy'],
    'corsia': ['aviation_transport_policy'],
    'ets aviation': ['aviation_transport_policy'],
    'emissions trading aviation': ['aviation_transport_policy'],
    'airport slots': ['aviation_transport_policy'],
    'slot allocation': ['aviation_transport_policy'],
    'open skies': ['aviation_transport_policy'],
    'tran committee': ['aviation_transport_policy'],
    'transport committee': ['aviation_transport_policy'],
    'dg move aviation': ['aviation_transport_policy'],
    'filip cornelis': ['aviation_transport_policy'],
    'a4e': ['aviation_transport_policy'],
    'airlines for europe': ['aviation_transport_policy'],
    'drone regulation': ['aviation_transport_policy'],
    'u-space': ['aviation_transport_policy'],
    'aviation security': ['aviation_transport_policy'],
    'politica de aviacion': ['aviation_transport_policy'],
    'politique aerienne': ['aviation_transport_policy'],
    'luchtvaartbeleid': ['aviation_transport_policy'],
    'politica aeronautica': ['aviation_transport_policy'],
    'aviacio': ['aviation_transport_policy'],
    '2023/2405': ['aviation_transport_policy'],
    '32023r2405': ['aviation_transport_policy'],
    '2013/0186': ['aviation_transport_policy'],
    '2013/0072': ['aviation_transport_policy'],
    '32004r0261': ['aviation_transport_policy'],
    # Union Customs Code Reform (COM(2023)258)
    'union customs code': ['union_customs_code_reform', 'eu_customs_electronic_systems'],
    'union customs code reform': ['union_customs_code_reform'],
    'new customs code': ['union_customs_code_reform'],
    'customs code reform': ['union_customs_code_reform'],
    'customs code proposal': ['union_customs_code_reform'],
    'customs reform': ['union_customs_code_reform'],
    'customs authority': ['union_customs_code_reform'],
    'eu customs authority': ['union_customs_code_reform'],
    'customs data hub': ['union_customs_code_reform'],
    'eu customs data hub': ['union_customs_code_reform'],
    'com(2023)258': ['union_customs_code_reform'],
    'com(2023) 258': ['union_customs_code_reform'],
    '2023/0156': ['union_customs_code_reform'],
    '2023/0156(cod)': ['union_customs_code_reform'],
    '52023pc0258': ['union_customs_code_reform'],
    'regulation 952/2013': ['union_customs_code_reform', 'eu_customs_electronic_systems'],
    'ucc reform': ['union_customs_code_reform'],
    'ucc proposal': ['union_customs_code_reform'],
    'ucc revision': ['union_customs_code_reform'],
    'ucc amendments': ['union_customs_code_reform'],
    'dirk gotink': ['union_customs_code_reform'],
    'gotink customs': ['union_customs_code_reform'],
    'code des douanes': ['union_customs_code_reform'],
    'codigo aduanero': ['union_customs_code_reform'],
    'codice doganale': ['union_customs_code_reform'],
    'douanewetboek': ['union_customs_code_reform'],
    'reforme douaniere': ['union_customs_code_reform'],
    'reforma aduanera': ['union_customs_code_reform'],
    'riforma doganale': ['union_customs_code_reform'],
    'douanehervorming': ['union_customs_code_reform'],
    'codi duaner': ['union_customs_code_reform'],
    'codi de duanes': ['union_customs_code_reform'],
    'reforma duanera': ['union_customs_code_reform'],
    't9-0151/2024': ['union_customs_code_reform'],
    'a9-0065/2024': ['union_customs_code_reform'],
    'eori': ['union_customs_code_reform', 'eu_customs_electronic_systems'],
    'eori number': ['union_customs_code_reform', 'eu_customs_electronic_systems'],
    'eori numbers': ['union_customs_code_reform', 'eu_customs_electronic_systems'],
    'economic operator registration': ['union_customs_code_reform'],
    'economic operators registration': ['union_customs_code_reform'],
    'st-10462-2025': ['union_customs_code_reform'],
    'council customs compromise': ['union_customs_code_reform'],
    'presidency compromise customs': ['union_customs_code_reform'],
    # EV Charging Measuring Systems (Directive 2026/706)
    'ev charging': ['industrial_accelerator_act'],
    'ev charger': ['industrial_accelerator_act'],
    'electric vehicle supply equipment': ['industrial_accelerator_act'],
    'evse': ['industrial_accelerator_act'],
    'charging station regulation': ['industrial_accelerator_act'],
    'compressed gas measuring': ['industrial_accelerator_act'],
    '2026/706': ['industrial_accelerator_act'],
    '32026l0706': ['industrial_accelerator_act'],
    'directive 2026/706': ['industrial_accelerator_act'],
    'measuring systems directive': ['industrial_accelerator_act'],
    'borne de recharge': ['industrial_accelerator_act'],
    'punto de recarga': ['industrial_accelerator_act'],
    'punt de recarrega': ['industrial_accelerator_act'],
    'punto di ricarica': ['industrial_accelerator_act'],
    'laadpaal': ['industrial_accelerator_act'],
    # US Customs Duties (INTA)
    'us customs duties': ['eu_trade_policy', 'eu_us_trade_deal_2026'],
    'customs duties us': ['eu_trade_policy', 'eu_us_trade_deal_2026'],
    'bernd lange': ['eu_trade_policy'],
    # MFF Programmes (BUDG assessments)
    'erasmus 2028': ['mff_2028_2034'],
    'connecting europe facility 2028': ['mff_2028_2034'],
    'cef 2028': ['mff_2028_2034'],
    'single market programme 2028': ['mff_2028_2034'],
    'customs programme 2028': ['mff_2028_2034'],
    # Medical Devices Regulation (MDR)
    'medical devices regulation': ['medical_devices_regulation'],
    'medical device regulation': ['medical_devices_regulation'],
    'mdr regulation': ['medical_devices_regulation'],
    'mdr 2017/745': ['medical_devices_regulation'],
    '2017/745': ['medical_devices_regulation'],
    '32017r0745': ['medical_devices_regulation'],
    'eudamed': ['medical_devices_regulation'],
    'notified body medical': ['medical_devices_regulation'],
    'notified bodies medical': ['medical_devices_regulation'],
    'unique device identification': ['medical_devices_regulation'],
    'udi medical': ['medical_devices_regulation'],
    'medical device classification': ['medical_devices_regulation'],
    'class iii medical': ['medical_devices_regulation'],
    'ivdr': ['medical_devices_regulation'],
    'in vitro diagnostic': ['medical_devices_regulation'],
    'dispositifs medicaux': ['medical_devices_regulation'],
    'productos sanitarios': ['medical_devices_regulation'],
    'dispositivi medici': ['medical_devices_regulation'],
    'medische hulpmiddelen': ['medical_devices_regulation'],
    'productes sanitaris': ['medical_devices_regulation'],
    # EU Equality and Anti-Discrimination
    'lgbtiq': ['eu_equality_antidiscrimination'],
    'lgbtiq equality': ['eu_equality_antidiscrimination'],
    'lgbtiq strategy': ['eu_equality_antidiscrimination'],
    'lgbti rights': ['eu_equality_antidiscrimination'],
    'anti-discrimination': ['eu_equality_antidiscrimination'],
    'anti discrimination': ['eu_equality_antidiscrimination'],
    'equal treatment directive': ['eu_equality_antidiscrimination'],
    'horizontal directive equality': ['eu_equality_antidiscrimination'],
    'race equality directive': ['eu_equality_antidiscrimination'],
    'employment equality directive': ['eu_equality_antidiscrimination'],
    '2000/43': ['eu_equality_antidiscrimination'],
    '2000/78': ['eu_equality_antidiscrimination'],
    'com(2008)426': ['eu_equality_antidiscrimination'],
    'gender equality strategy': ['eu_equality_antidiscrimination'],
    'discrimination sexuelle': ['eu_equality_antidiscrimination'],
    'igualdad lgbtiq': ['eu_equality_antidiscrimination'],
    'igualdad de trato': ['eu_equality_antidiscrimination'],
    'parita di trattamento': ['eu_equality_antidiscrimination'],
    'gelijke behandeling': ['eu_equality_antidiscrimination'],
    'igualtat de tracte': ['eu_equality_antidiscrimination'],
    'discrimination': ['eu_equality_antidiscrimination'],
    'equality legislation': ['eu_equality_antidiscrimination'],
    'equal rights': ['eu_equality_antidiscrimination'],
    'hate crime eu': ['eu_equality_antidiscrimination'],
    'hate speech eu': ['eu_equality_antidiscrimination'],
    # European Health Data Space (EHDS)
    'european health data space': ['european_health_data_space'],
    'health data space': ['european_health_data_space'],
    'ehds': ['european_health_data_space'],
    'ehds regulation': ['european_health_data_space'],
    'myhealth@eu': ['european_health_data_space'],
    'healthdata@eu': ['european_health_data_space'],
    'health data access body': ['european_health_data_space'],
    'secondary use health data': ['european_health_data_space'],
    'electronic health record': ['european_health_data_space'],
    '2022/0140': ['european_health_data_space'],
    '2022/0140(cod)': ['european_health_data_space'],
    '32025r0327': ['european_health_data_space'],
    'com(2022)197': ['european_health_data_space'],
    'espace europeen donnees sante': ['european_health_data_space'],
    'espacio europeo datos sanitarios': ['european_health_data_space'],
    'spazio europeo dati sanitari': ['european_health_data_space'],
    'europese ruimte gezondheidsgegevens': ['european_health_data_space'],
    # Facilitation Directive (Anti-Smuggling)
    'facilitation directive': ['facilitation_directive_smuggling', 'eu_migration_asylum_pact'],
    'migrant smuggling': ['facilitation_directive_smuggling'],
    'anti-smuggling': ['facilitation_directive_smuggling'],
    'anti smuggling': ['facilitation_directive_smuggling'],
    'humanitarian exemption': ['facilitation_directive_smuggling'],
    'smuggling directive': ['facilitation_directive_smuggling'],
    'com(2023)755': ['facilitation_directive_smuggling'],
    '2023/0340': ['facilitation_directive_smuggling'],
    '2023/0340(cod)': ['facilitation_directive_smuggling'],
    'directive 2002/90': ['facilitation_directive_smuggling'],
    'passeurs': ['facilitation_directive_smuggling'],
    'trafico de migrantes': ['facilitation_directive_smuggling'],
    'traffico di migranti': ['facilitation_directive_smuggling'],
    'mensensmokkel': ['facilitation_directive_smuggling'],
    # Common Agricultural Policy (CAP)
    'common agricultural policy': ['common_agricultural_policy'],
    'cap reform': ['common_agricultural_policy'],
    'cap strategic plan': ['common_agricultural_policy'],
    'cap strategic plans': ['common_agricultural_policy'],
    'agricultural policy': ['common_agricultural_policy'],
    'direct payments farmers': ['common_agricultural_policy'],
    'eco-schemes': ['common_agricultural_policy'],
    'eco schemes': ['common_agricultural_policy'],
    'gaec': ['common_agricultural_policy'],
    'eagf': ['common_agricultural_policy'],
    'eafrd': ['common_agricultural_policy'],
    'rural development fund': ['common_agricultural_policy'],
    '2021/2115': ['common_agricultural_policy'],
    '2021/2116': ['common_agricultural_policy'],
    '32021r2115': ['common_agricultural_policy'],
    'cap simplification': ['common_agricultural_policy'],
    '2024/1468': ['common_agricultural_policy'],
    'politique agricole commune': ['common_agricultural_policy'],
    'politica agricola comune': ['common_agricultural_policy'],
    'politica agricola comun': ['common_agricultural_policy'],
    'gemeenschappelijk landbouwbeleid': ['common_agricultural_policy'],
    'pac reforma': ['common_agricultural_policy'],
    # EU Pact on Migration and Asylum
    'pact on migration': ['eu_migration_asylum_pact'],
    'migration pact': ['eu_migration_asylum_pact'],
    'asylum pact': ['eu_migration_asylum_pact'],
    'migration and asylum': ['eu_migration_asylum_pact'],
    'asylum procedures regulation': ['eu_migration_asylum_pact'],
    'screening regulation migration': ['eu_migration_asylum_pact'],
    'crisis regulation migration': ['eu_migration_asylum_pact'],
    'eurodac regulation': ['eu_migration_asylum_pact'],
    'solidarity mechanism migration': ['eu_migration_asylum_pact'],
    'border procedure asylum': ['eu_migration_asylum_pact'],
    '2024/1351': ['eu_migration_asylum_pact'],
    '2024/1348': ['eu_migration_asylum_pact'],
    '2024/1356': ['eu_migration_asylum_pact'],
    'pacte migration': ['eu_migration_asylum_pact'],
    'pacto migracion': ['eu_migration_asylum_pact'],
    'patto migrazione': ['eu_migration_asylum_pact'],
    'migratiepact': ['eu_migration_asylum_pact'],
    'pacte migració': ['eu_migration_asylum_pact'],

    # EU-Australia Trade Agreement (24 March 2026)
    'eu-australia': ['eu_australia_trade_agreement', 'eu_trade_policy'],
    'eu australia': ['eu_australia_trade_agreement', 'eu_trade_policy'],
    'australia trade': ['eu_australia_trade_agreement', 'eu_trade_policy'],
    'australia fta': ['eu_australia_trade_agreement', 'eu_trade_policy'],
    'australia deal': ['eu_australia_trade_agreement'],
    'australia agreement': ['eu_australia_trade_agreement'],
    'albanese': ['eu_australia_trade_agreement'],
    'acuerdo australia': ['eu_australia_trade_agreement'],
    'accord australie': ['eu_australia_trade_agreement'],
    'accordo australia': ['eu_australia_trade_agreement'],
    'australie overeenkomst': ['eu_australia_trade_agreement'],
    'acord australia': ['eu_australia_trade_agreement'],

    # Innovative Enterprises Definition (Recommendation 2026/720)
    'innovative enterprise': ['innovative_enterprises_definition'],
    'innovative startup': ['innovative_enterprises_definition'],
    'innovative scaleup': ['innovative_enterprises_definition'],
    'startup definition': ['innovative_enterprises_definition'],
    'scaleup definition': ['innovative_enterprises_definition'],
    'recommendation 2026/720': ['innovative_enterprises_definition'],
    '2026/720': ['innovative_enterprises_definition'],
    '32026h0720': ['innovative_enterprises_definition'],
    'startup nations': ['innovative_enterprises_definition'],
    'definicion startup': ['innovative_enterprises_definition'],
    'definition startup': ['innovative_enterprises_definition'],
    'entreprise innovante': ['innovative_enterprises_definition'],
    'empresa innovadora': ['innovative_enterprises_definition'],
    'innovatieve onderneming': ['innovative_enterprises_definition'],

    # Anti-Corruption Directive (2023/0135(COD))
    'anti-corruption': ['anti_corruption_directive'],
    'anti corruption': ['anti_corruption_directive'],
    'anticorruption': ['anti_corruption_directive'],
    'corruption directive': ['anti_corruption_directive'],
    'bribery directive': ['anti_corruption_directive'],
    'combating corruption': ['anti_corruption_directive'],
    '2023/0135': ['anti_corruption_directive'],
    'com(2023)234': ['anti_corruption_directive'],
    'framework decision 2003/568': ['anti_corruption_directive'],
    'lutte contre la corruption': ['anti_corruption_directive'],
    'lucha contra la corrupcion': ['anti_corruption_directive'],
    'lotta alla corruzione': ['anti_corruption_directive'],
    'corruptiebestrijding': ['anti_corruption_directive'],
    'lluita contra la corrupcio': ['anti_corruption_directive'],

    # Global Gateway Strategy
    'global gateway strategy': ['global_gateway_strategy'],
    'global gateway report': ['global_gateway_strategy'],
    'global gateway past impacts': ['global_gateway_strategy'],
    'global gateway future': ['global_gateway_strategy'],
    '2025/2073': ['global_gateway_strategy'],
    'a10-0045/2026': ['global_gateway_strategy'],
    'chloe ridel': ['global_gateway_strategy'],
    'hildegard bentele': ['global_gateway_strategy'],
    'belt and road': ['global_gateway_strategy'],
    'lobito corridor': ['global_gateway_strategy'],

    # UWWTD and medicine supply (plenary 26 March 2026)
    'uwwtd': ['eu_water_legislation'],
    'urban wastewater treatment directive': ['eu_water_legislation'],
    'wastewater medicine': ['eu_water_legislation'],
    'wastewater pharmaceutical': ['eu_water_legislation'],
    'medicine supply wastewater': ['eu_water_legislation'],
    '2026/2652': ['eu_water_legislation', 'ep_plenary_march_2026'],
    'o-000013/2026': ['eu_water_legislation', 'ep_plenary_march_2026'],
    'peter liese': ['eu_water_legislation', 'ep_plenary_march_2026'],
    'oliver schenk': ['eu_water_legislation', 'ep_plenary_march_2026'],

    # State aid (recent decisions March 2026)
    'state aid': ['competition_law_enforcement'],
    'state aid scheme': ['competition_law_enforcement'],
    'article 107': ['competition_law_enforcement'],
    'article 108': ['competition_law_enforcement'],
    'ceeag': ['competition_law_enforcement'],
    'offshore wind state aid': ['competition_law_enforcement'],
    'danish wind': ['competition_law_enforcement'],
    'french hydrogen': ['competition_law_enforcement'],
    'ayuda estatal': ['competition_law_enforcement'],
    'aide etat': ['competition_law_enforcement'],
    'staatssteun': ['competition_law_enforcement'],
    'aiuto di stato': ['competition_law_enforcement'],
    'ajut estatal': ['competition_law_enforcement'],

    # FIFA competition complaint
    'fifa': ['competition_law_enforcement'],
    'fifa ticket': ['competition_law_enforcement'],
    'world cup ticket': ['competition_law_enforcement'],
    'ticket pricing': ['competition_law_enforcement'],
    'fifa world cup': ['competition_law_enforcement'],

    # Late Payments Regulation (COM(2023)533, 2023/0323(COD))
    'late payment': ['late_payments_regulation'],
    'late payments': ['late_payments_regulation'],
    'late payment regulation': ['late_payments_regulation'],
    'late payments regulation': ['late_payments_regulation'],
    'late payment directive': ['late_payments_regulation'],
    'late payments directive': ['late_payments_regulation'],
    'combating late payment': ['late_payments_regulation'],
    'payment deadline': ['late_payments_regulation'],
    'payment deadlines': ['late_payments_regulation'],
    'com(2023)533': ['late_payments_regulation'],
    'com(2023) 533': ['late_payments_regulation'],
    '2023/0323': ['late_payments_regulation'],
    '2023/0323(cod)': ['late_payments_regulation'],
    'directive 2011/7': ['late_payments_regulation'],
    '2011/7/eu': ['late_payments_regulation'],
    'ivars ijabs': ['late_payments_regulation'],
    'roza thun': ['late_payments_regulation'],
    'thun und hohenstein': ['late_payments_regulation'],
    't9-0299/2024': ['late_payments_regulation'],
    'a9-0156/2024': ['late_payments_regulation'],
    'sme payment': ['late_payments_regulation'],
    'sme late payment': ['late_payments_regulation'],
    'observatory late payments': ['late_payments_regulation'],
    'pago tardio': ['late_payments_regulation'],
    'retard de paiement': ['late_payments_regulation'],
    'ritardo nei pagamenti': ['late_payments_regulation'],
    'betalingsachterstand': ['late_payments_regulation'],
    'pagament tardia': ['late_payments_regulation'],
    'morosidad': ['late_payments_regulation'],

    # EU Pharmaceutical Legal Framework (current laws in force)
    'pharmaceutical legal framework': ['eu_pharmaceutical_framework'],
    'pharmaceutical framework': ['eu_pharmaceutical_framework'],
    'eu pharmaceutical': ['eu_pharmaceutical_framework', 'eu_pharmaceutical_legislation_reform'],
    'pharma framework': ['eu_pharmaceutical_framework'],
    'pharmaceutical law': ['eu_pharmaceutical_framework', 'eu_pharmaceutical_legislation_reform'],
    'pharma law': ['eu_pharmaceutical_framework', 'eu_pharmaceutical_legislation_reform'],
    'eu pharma laws': ['eu_pharmaceutical_framework', 'eu_pharmaceutical_legislation_reform'],
    'medicinal products': ['eu_pharmaceutical_framework'],
    'medicines regulation': ['eu_pharmaceutical_framework'],
    'directive 2001/83': ['eu_pharmaceutical_framework', 'eu_pharmaceutical_legislation_reform'],
    'regulation 726/2004': ['eu_pharmaceutical_framework', 'eu_pharmaceutical_legislation_reform'],
    'centralised procedure': ['eu_pharmaceutical_framework'],
    'decentralised procedure medicines': ['eu_pharmaceutical_framework'],
    'mutual recognition procedure medicines': ['eu_pharmaceutical_framework'],
    'pharmacovigilance': ['eu_pharmaceutical_framework'],
    'eudravigilance': ['eu_pharmaceutical_framework'],
    'clinical trials regulation': ['eu_pharmaceutical_framework'],
    'regulation 536/2014': ['eu_pharmaceutical_framework'],
    'ctis': ['eu_pharmaceutical_framework'],
    'clinical trials information system': ['eu_pharmaceutical_framework'],
    'falsified medicines': ['eu_pharmaceutical_framework'],
    'directive 2011/62': ['eu_pharmaceutical_framework'],
    'eudralex': ['eu_pharmaceutical_framework'],
    'good manufacturing practice': ['eu_pharmaceutical_framework'],
    'gmp pharmaceutical': ['eu_pharmaceutical_framework'],
    'chmp': ['eu_pharmaceutical_framework'],
    'prac committee': ['eu_pharmaceutical_framework'],
    'paediatric investigation plan': ['eu_pharmaceutical_framework'],
    'pip paediatric': ['eu_pharmaceutical_framework'],
    'regulation 1901/2006': ['eu_pharmaceutical_framework'],
    'regulation 141/2000': ['eu_pharmaceutical_framework'],
    'regulation 1394/2007': ['eu_pharmaceutical_framework'],
    'advanced therapy medicinal': ['eu_pharmaceutical_framework', 'biotech_act'],
    'gene therapy regulation': ['eu_pharmaceutical_framework'],
    'somatic cell therapy': ['eu_pharmaceutical_framework'],
    'herbal medicines': ['eu_pharmaceutical_framework'],
    'directive 2004/24': ['eu_pharmaceutical_framework'],
    'european pharmacopoeia': ['eu_pharmaceutical_framework'],
    'edqm': ['eu_pharmaceutical_framework'],
    'marketing authorisation': ['eu_pharmaceutical_framework', 'eu_pharmaceutical_legislation_reform'],
    'marco farmaceutico': ['eu_pharmaceutical_framework'],
    'cadre pharmaceutique': ['eu_pharmaceutical_framework'],
    'quadro farmaceutico': ['eu_pharmaceutical_framework'],
    'farmaceutisch kader': ['eu_pharmaceutical_framework'],
    'marc farmaceutic': ['eu_pharmaceutical_framework'],
    'ley farmaceutica': ['eu_pharmaceutical_framework'],
    'legislacion farmaceutica': ['eu_pharmaceutical_framework'],
    'legislacio farmaceutica': ['eu_pharmaceutical_framework'],

    # EU Pharmaceutical Legislation Reform (2023/0131(COD) + 2023/0132(COD))
    'pharmaceutical reform': ['eu_pharmaceutical_legislation_reform'],
    'pharma reform': ['eu_pharmaceutical_legislation_reform'],
    'pharmaceutical legislation reform': ['eu_pharmaceutical_legislation_reform'],
    'pharma legislation reform': ['eu_pharmaceutical_legislation_reform'],
    'pharmaceutical package': ['eu_pharmaceutical_legislation_reform'],
    'medicines legislation reform': ['eu_pharmaceutical_legislation_reform'],
    'data exclusivity': ['eu_pharmaceutical_legislation_reform'],
    'market exclusivity': ['eu_pharmaceutical_legislation_reform'],
    'orphan medicines': ['eu_pharmaceutical_legislation_reform', 'eu_rare_diseases_policy'],
    'orphan drugs': ['eu_pharmaceutical_legislation_reform', 'eu_rare_diseases_policy'],
    'antimicrobial resistance': ['eu_pharmaceutical_legislation_reform'],
    'amr medicines': ['eu_pharmaceutical_legislation_reform'],
    'bolar exemption': ['eu_pharmaceutical_legislation_reform'],
    'generic medicines': ['eu_pharmaceutical_legislation_reform'],
    'biosimilar': ['eu_pharmaceutical_legislation_reform'],
    'dolors montserrat': ['eu_pharmaceutical_legislation_reform'],
    'tiemo wolken': ['eu_pharmaceutical_legislation_reform'],
    'tiemo wölken': ['eu_pharmaceutical_legislation_reform'],
    '2023/0132': ['eu_pharmaceutical_legislation_reform'],
    '2023/0131': ['eu_pharmaceutical_legislation_reform'],
    '2023/0132(cod)': ['eu_pharmaceutical_legislation_reform'],
    '2023/0131(cod)': ['eu_pharmaceutical_legislation_reform'],
    'com(2023)192': ['eu_pharmaceutical_legislation_reform'],
    'com(2023)193': ['eu_pharmaceutical_legislation_reform'],
    'ema reform': ['eu_pharmaceutical_legislation_reform'],
    'reforma farmaceutica': ['eu_pharmaceutical_legislation_reform'],
    'reforme pharmaceutique': ['eu_pharmaceutical_legislation_reform'],
    'riforma farmaceutica': ['eu_pharmaceutical_legislation_reform'],
    'geneesmiddelenwetgeving': ['eu_pharmaceutical_legislation_reform'],
    'reforma farmaceutica ue': ['eu_pharmaceutical_legislation_reform'],

    # Critical Medicines Act (COM(2025)102, 2025/0102(COD))
    'critical medicines': ['critical_medicines_act'],
    'critical medicines act': ['critical_medicines_act'],
    'medicine shortages': ['critical_medicines_act'],
    'medicament critique': ['critical_medicines_act'],
    'medicamentos criticos': ['critical_medicines_act'],
    'medicaments critiques': ['critical_medicines_act'],
    'farmaci critici': ['critical_medicines_act'],
    'kritieke geneesmiddelen': ['critical_medicines_act'],
    'medicaments critics': ['critical_medicines_act'],
    'api manufacturing': ['critical_medicines_act'],
    'active pharmaceutical ingredients': ['critical_medicines_act'],
    'medicine supply chain': ['critical_medicines_act'],
    'drug shortages': ['critical_medicines_act'],
    'com(2025)102': ['critical_medicines_act'],
    '2025/0102': ['critical_medicines_act'],
    '2025/0102(cod)': ['critical_medicines_act'],
    'tomislav sokol critical': ['critical_medicines_act'],
    'critical medicines alliance': ['critical_medicines_act'],
    'strategic projects medicines': ['critical_medicines_act'],
    'shortage prevention': ['critical_medicines_act', 'eu_pharmaceutical_legislation_reform'],

    # Water Pollution / PFAS
    'pfas': ['water_pollution_pfas'],
    'forever chemicals': ['water_pollution_pfas'],
    'forever chemical': ['water_pollution_pfas'],
    'per- and polyfluoroalkyl': ['water_pollution_pfas'],
    'polyfluoroalkyl': ['water_pollution_pfas'],
    'perfluoroalkyl': ['water_pollution_pfas'],
    'pfos': ['water_pollution_pfas'],
    'pfoa': ['water_pollution_pfas'],
    'pfhxs': ['water_pollution_pfas'],
    'water pollution': ['water_pollution_pfas'],
    'water quality': ['water_pollution_pfas'],
    'groundwater pollution': ['water_pollution_pfas'],
    'surface water pollution': ['water_pollution_pfas'],
    'drinking water directive': ['water_pollution_pfas'],
    'drinking water': ['water_pollution_pfas'],
    '2020/2184': ['water_pollution_pfas'],
    '32020l2184': ['water_pollution_pfas'],
    'environmental quality standards': ['water_pollution_pfas'],
    '2008/105': ['water_pollution_pfas'],
    'water framework directive': ['water_pollution_pfas'],
    'microplastics': ['water_pollution_pfas'],
    'antimicrobial resistance water': ['water_pollution_pfas'],
    'zero pollution': ['water_pollution_pfas'],
    'zero pollution action plan': ['water_pollution_pfas'],
    'water contamination': ['water_pollution_pfas'],
    'contaminants water': ['water_pollution_pfas'],
    'pharmaceuticals water': ['water_pollution_pfas'],
    'pollutants water': ['water_pollution_pfas'],

    # EU Returns Policy Reform (Return Regulation)
    'return regulation': ['returns_policy_reform'],
    'return directive': ['returns_policy_reform'],
    'returns policy': ['returns_policy_reform'],
    'return policy': ['returns_policy_reform'],
    'eu returns': ['returns_policy_reform'],
    'return of third-country nationals': ['returns_policy_reform'],
    'return third-country': ['returns_policy_reform'],
    'irregular migration return': ['returns_policy_reform'],
    'deportation eu': ['returns_policy_reform'],
    'removal third-country': ['returns_policy_reform'],
    'malik azmani': ['returns_policy_reform'],
    'com(2025)0101': ['returns_policy_reform'],
    'com(2025)101': ['returns_policy_reform'],
    '2025/0059': ['returns_policy_reform'],
    '2025/0059(cod)': ['returns_policy_reform'],
    '2008/115': ['returns_policy_reform'],
    'return decision': ['returns_policy_reform'],
    'voluntary departure': ['returns_policy_reform'],
    'european return order': ['returns_policy_reform'],
    'detention migrants': ['returns_policy_reform'],
    'entry ban migration': ['returns_policy_reform'],
    'return hubs': ['returns_policy_reform'],
    'magnus brunner return': ['returns_policy_reform'],
    'a10-0048/2026': ['returns_policy_reform'],

    # EU Cybersecurity Act
    'cybersecurity act': ['cybersecurity_act'],
    'cybersecurity certification': ['cybersecurity_act'],
    'enisa': ['cybersecurity_act'],
    'cybersecurity agency': ['cybersecurity_act'],
    '2019/881': ['cybersecurity_act'],
    '32019r0881': ['cybersecurity_act'],
    'cybersecurity act 2': ['cybersecurity_act'],
    'com(2026)11': ['cybersecurity_act'],
    'com(2026) 11': ['cybersecurity_act'],
    '2026/0011': ['cybersecurity_act'],
    '2026/0011(cod)': ['cybersecurity_act'],
    'ict supply chain security': ['cybersecurity_act'],
    'eucc': ['cybersecurity_act'],
    'eucs': ['cybersecurity_act'],
    'eu cloud certification': ['cybersecurity_act'],
    'cybersecurity certification framework': ['cybersecurity_act'],
    'eccf': ['cybersecurity_act'],
    'managed security services': ['cybersecurity_act'],
    '2025/37': ['cybersecurity_act'],
    'marketa gregorova': ['cybersecurity_act'],
    'gregorova cybersecurity': ['cybersecurity_act'],
    'cyber resilience act': ['cybersecurity_act'],
    '2024/2847': ['cybersecurity_act'],
    'nis2 omnibus': ['cybersecurity_act'],
    '2026/0012': ['cybersecurity_act'],
    'cybersecurity reserve': ['cybersecurity_act'],
    'cybersecurity package 2026': ['cybersecurity_act'],

    # EU-US Trade Deal - 26 March 2026 plenary triggers
    'turnberry': ['eu_us_trade_deal_2026'],
    'turnberry deal': ['eu_us_trade_deal_2026'],
    'sunrise clause': ['eu_us_trade_deal_2026'],
    'suspension clause trade': ['eu_us_trade_deal_2026'],

    # Banking Union - final adoption triggers
    'dgsd2': ['banking_union_reform'],
    'brrd3': ['banking_union_reform'],
    'srmr3': ['banking_union_reform'],
    'deposit guarantee reform': ['banking_union_reform'],
    'bank resolution reform': ['banking_union_reform'],
    'cmdi': ['banking_union_reform'],
    'crisis management deposit insurance': ['banking_union_reform'],
    'a10-0065/2026': ['banking_union_reform'],
    'a10-0066/2026': ['banking_union_reform'],
    'a10-0067/2026': ['banking_union_reform'],
    'peter-hansen': ['banking_union_reform'],
    'niedermayer': ['banking_union_reform'],
    'tinagli': ['banking_union_reform'],

    # AI Act Amendments 2026
    'nudification': ['ai_act_amendments_2026', 'ai_act_regulation'],
    'ai nudifier': ['ai_act_amendments_2026', 'ai_act_regulation'],
    'ai nudification': ['ai_act_amendments_2026'],
    'ai act delay': ['ai_act_amendments_2026'],
    'ai act amendment': ['ai_act_amendments_2026'],
    'high-risk ai delay': ['ai_act_amendments_2026'],
    'ai act high-risk': ['ai_act_amendments_2026', 'ai_act_regulation'],

    # EU Customs Reform
    'eu customs reform': ['eu_customs_reform'],
    'customs reform': ['eu_customs_reform'],
    'customs authority': ['eu_customs_reform'],
    'eu customs authority': ['eu_customs_reform'],
    'customs data hub': ['eu_customs_reform'],
    'com(2023) 258': ['eu_customs_reform'],
    'com(2023)258': ['eu_customs_reform'],
    '2023/0156': ['eu_customs_reform'],
    'customs union reform': ['eu_customs_reform'],
    'reforme douaniere': ['eu_customs_reform'],
    'reforma aduanera': ['eu_customs_reform'],

    # Water Pollution - 2nd reading adoption
    'a10-0063/2026': ['water_pollution_pfas'],
    'javi lopez water': ['water_pollution_pfas'],
    '2022/0344': ['water_pollution_pfas'],

    # SAFE approvals + AGILE defence
    'safe approvals': ['safe_rearm_europe'],
    'safe funding': ['safe_rearm_europe'],
    'agile programme': ['eu_defence_procurement'],
    'agile defense': ['eu_defence_procurement'],
    'com(2026) 135': ['eu_defence_procurement'],
    'com(2026)135': ['eu_defence_procurement'],
    '2026/0078': ['eu_defence_procurement'],
    'rapid defence innovation': ['eu_defence_procurement'],

    # Anti-corruption - final adoption
    'anti-corruption directive': ['anti_corruption_directive'],
    'anticorruption directive': ['anti_corruption_directive'],
    'illicit enrichment': ['anti_corruption_directive'],
    'eu corruption law': ['anti_corruption_directive'],
    'com(2023)234': ['anti_corruption_directive'],
    'com(2023) 234': ['anti_corruption_directive'],
    '2023/0135': ['anti_corruption_directive'],

    # WTO MC14 outcome + CPTPP + MPIA (30 Mar 2026)
    'mc14 outcome': ['eu_trade_policy'],
    'mc14 no deal': ['eu_trade_policy'],
    'wto no deal': ['eu_trade_policy'],
    'eu-cptpp': ['eu_trade_policy'],
    'cptpp': ['eu_trade_policy'],
    'mpia': ['eu_trade_policy'],
    'multi-party interim appeal': ['eu_trade_policy'],
    'appellate body': ['eu_trade_policy'],
    'polyamide yarn': ['eu_trade_policy'],
    'polyamide yarns': ['eu_trade_policy'],
    '2026/734': ['eu_trade_policy'],
    '32026r0734': ['eu_trade_policy'],
    'electrical steel safeguard': ['eu_trade_policy'],
    'grain-oriented electrical steel': ['eu_trade_policy'],
    'goes safeguard': ['eu_trade_policy'],

    # DORA ITS update (30 Mar 2026)
    '2026/722': ['financial_supervision_eba'],
    '32026r0722': ['financial_supervision_eba'],
    'dora incident reporting': ['financial_supervision_eba'],
    'ict incident reporting': ['financial_supervision_eba'],

    # Rail/waterway state aid GBER (30 Mar 2026)
    '2026/562': ['aviation_transport_policy'],
    '32026r0562': ['aviation_transport_policy'],
    'rail state aid': ['aviation_transport_policy'],
    'rail gber': ['aviation_transport_policy'],
    'inland waterway state aid': ['aviation_transport_policy'],
    'multimodal state aid': ['aviation_transport_policy'],
    'modal shift incentive': ['aviation_transport_policy'],

    # Cohesion mid-term review (30 Mar 2026)
    'mid-term review cohesion': ['cohesion_policy_audit'],
    'cohesion mid-term': ['cohesion_policy_audit'],
    'cohesion review 2026': ['cohesion_policy_audit'],

    # STEP platform (30 Mar 2026)
    'step platform': ['fp10_ecf_competitiveness'],
    'strategic technologies europe': ['fp10_ecf_competitiveness'],
    'step 29 billion': ['fp10_ecf_competitiveness'],
    'step mobilises': ['fp10_ecf_competitiveness'],

    # WTO MC14 outcomes (31 Mar 2026)
    'mc14': ['eu_trade_policy'],
    'wto ministerial': ['eu_trade_policy'],
    'wto ministerial conference': ['eu_trade_policy'],
    'yaounde': ['eu_trade_policy'],
    'yaoundé': ['eu_trade_policy'],
    'investment facilitation development': ['eu_trade_policy'],
    'ifd agreement': ['eu_trade_policy'],
    'e-commerce moratorium': ['eu_trade_policy'],

    # April 2026 plenary (31 Mar 2026)
    'april plenary': ['ep_plenary_march_2026'],
    'plenary april': ['ep_plenary_march_2026'],
    'next plenary': ['ep_plenary_march_2026'],
    'april strasbourg': ['ep_plenary_march_2026'],
    '27-30 april': ['ep_plenary_march_2026'],
    'april 2026 plenary': ['ep_plenary_march_2026'],
    'ukraine 90 billion loan': ['ep_plenary_march_2026'],
    'eu magnitsky act': ['ep_plenary_march_2026'],
    'air passenger rights': ['ep_plenary_march_2026', 'aviation_transport_policy'],

    # EDIP work programme (31 Mar 2026)
    'edip work programme': ['eu_defence_procurement'],
    'defence calls': ['eu_defence_procurement'],
    'defence calls for proposals': ['eu_defence_procurement'],
    'defence work programme': ['eu_defence_procurement'],

    # Entry/Exit System (31 Mar 2026)
    'entry exit system': ['eu_migration_asylum_pact'],
    'entry/exit system': ['eu_migration_asylum_pact'],
    'ees': ['eu_migration_asylum_pact'],
    'ees operational': ['eu_migration_asylum_pact'],
    'smart borders': ['eu_migration_asylum_pact'],
    'etias': ['eu_migration_asylum_pact'],

    # MFF rapporteurs (31 Mar 2026)
    'mff rapporteur': ['mff_2028_2034'],
    'budget rapporteur': ['mff_2028_2034'],
    'muresan': ['mff_2028_2034'],
    'carla tavares': ['mff_2028_2034'],

    # European Business Wallets (ITRE, 30 Mar 2026)
    'european business wallets': ['digital_omnibus_package'],
    'business wallet': ['digital_omnibus_package'],

    # Critical Raw Materials amendment (ITRE, 30 Mar 2026)
    'critical raw materials amendment': ['industrial_accelerator_act'],
    'crma amendment': ['industrial_accelerator_act'],
    '2024/1252 amendment': ['industrial_accelerator_act'],

    # GDPR / Data Protection (training 31 Mar 2026)
    'gdpr': ['gdpr_data_protection'],
    'general data protection regulation': ['gdpr_data_protection'],
    'data protection': ['gdpr_data_protection'],
    'data protection regulation': ['gdpr_data_protection'],
    'rgpd': ['gdpr_data_protection'],
    'proteccion de datos': ['gdpr_data_protection'],
    'proteccio de dades': ['gdpr_data_protection'],
    'protezione dei dati': ['gdpr_data_protection'],
    'gegevensbescherming': ['gdpr_data_protection'],
    'protection des donnees': ['gdpr_data_protection'],
    '2016/679': ['gdpr_data_protection'],
    'data subject rights': ['gdpr_data_protection'],
    'right to be forgotten': ['gdpr_data_protection'],
    'data breach notification': ['gdpr_data_protection'],
    'data protection officer': ['gdpr_data_protection'],
    'dpo': ['gdpr_data_protection'],
    'edpb': ['gdpr_data_protection'],
    'data protection authority': ['gdpr_data_protection'],
    'schrems': ['gdpr_data_protection'],
    'eu-us data privacy framework': ['gdpr_data_protection'],

    # EU Chips Act (training 31 Mar 2026)
    'chips act': ['eu_chips_act'],
    'eu chips act': ['eu_chips_act'],
    'semiconductor': ['eu_chips_act'],
    'semiconductors': ['eu_chips_act'],
    'chips for europe': ['eu_chips_act'],
    'chips joint undertaking': ['eu_chips_act'],
    '2023/1781': ['eu_chips_act'],
    'semiconductor alliance': ['eu_chips_act'],
    'chip manufacturing': ['eu_chips_act'],
    'wafer fabrication': ['eu_chips_act'],
    'intel magdeburg': ['eu_chips_act'],
    'tsmc dresden': ['eu_chips_act'],
    'ley de chips': ['eu_chips_act'],
    'llei de xips': ['eu_chips_act'],
    'loi sur les puces': ['eu_chips_act'],
    'legge sui chip': ['eu_chips_act'],
    'chipswet': ['eu_chips_act'],

    # EU Deforestation Regulation (training 31 Mar 2026)
    'deforestation': ['eu_deforestation_regulation'],
    'deforestation regulation': ['eu_deforestation_regulation'],
    'eudr': ['eu_deforestation_regulation'],
    'eu deforestation': ['eu_deforestation_regulation'],
    '2023/1115': ['eu_deforestation_regulation'],
    'deforestation-free': ['eu_deforestation_regulation'],
    'deforestation free products': ['eu_deforestation_regulation'],
    'palm oil deforestation': ['eu_deforestation_regulation'],
    'soy deforestation': ['eu_deforestation_regulation'],
    'timber regulation': ['eu_deforestation_regulation'],
    'deforestacion': ['eu_deforestation_regulation'],
    'desforestacio': ['eu_deforestation_regulation'],
    'deforestacio': ['eu_deforestation_regulation'],
    'reglament de deforestacio': ['eu_deforestation_regulation'],
    'deforestation ue': ['eu_deforestation_regulation'],
    'deforestazione': ['eu_deforestation_regulation'],
    'ontbossing': ['eu_deforestation_regulation'],

    # Nature Restoration Law (training 31 Mar 2026)
    'nature restoration': ['nature_restoration_law'],
    'nature restoration law': ['nature_restoration_law'],
    'restoration law': ['nature_restoration_law'],
    '2024/1991': ['nature_restoration_law'],
    'ecosystem restoration': ['nature_restoration_law'],
    'biodiversity 2030': ['nature_restoration_law'],
    'biodiversity strategy': ['nature_restoration_law'],
    'rewetting peatlands': ['nature_restoration_law'],
    'free-flowing rivers': ['nature_restoration_law'],
    'national restoration plan': ['nature_restoration_law'],
    'restauration de la nature': ['nature_restoration_law'],
    'restauracion de la naturaleza': ['nature_restoration_law'],
    'restauracio de la natura': ['nature_restoration_law'],
    'ripristino della natura': ['nature_restoration_law'],
    'natuurherstel': ['nature_restoration_law'],
    'pollinator decline': ['nature_restoration_law'],

    # EU-Mexico Strategic Partnership (AFET/INTA, 30 Mar 2026)
    'eu-mexico': ['eu_trade_policy'],
    'eu mexico': ['eu_trade_policy'],
    'mexico strategic partnership': ['eu_trade_policy'],

    # ECI conversion practices ban (30 Mar 2026)
    'conversion practices': ['eu_equality_antidiscrimination'],
    'european citizens initiative 2026': ['eu_equality_antidiscrimination'],
    '2026/770': ['eu_equality_antidiscrimination'],

    # EUNAVFOR MED IRINI (30 Mar 2026)
    'eunavfor irini': ['eu_defence_procurement'],
    'irini force commander': ['eu_defence_procurement'],
    '2026/768': ['eu_defence_procurement'],

    # EU Designs Regulation codification (30 Mar 2026)
    'eu designs regulation': ['eu_trade_policy'],
    'designs regulation': ['eu_trade_policy'],
    '2026/715': ['eu_trade_policy'],
    '32026r0715': ['eu_trade_policy'],
    'eu design codification': ['eu_trade_policy'],
    'community design': ['eu_trade_policy'],
    'registered design': ['eu_trade_policy'],

    # EUNAVFOR MED IRINI operation (30 Mar 2026)
    'eunavfor med': ['eu_defence_procurement'],
    'operation irini': ['eu_defence_procurement'],
    'irini': ['eu_defence_procurement'],
    'libya arms embargo': ['eu_defence_procurement'],
    'mediterranean military operation': ['eu_defence_procurement'],

    # JRC GECO 2025 clean energy competitiveness (30 Mar 2026)
    'geco 2025': ['clean_energy_investment_strategy'],
    'geco report': ['clean_energy_investment_strategy'],
    'clean energy competitiveness': ['clean_energy_investment_strategy'],
    'jrc clean energy': ['clean_energy_investment_strategy'],
    'jrc energy report': ['clean_energy_investment_strategy'],
    'clean tech competitiveness': ['clean_energy_investment_strategy'],
    'technology competitiveness energy': ['clean_energy_investment_strategy'],

    # Global Gateway own-initiative report (30 Mar 2026)
    'global gateway report': ['global_gateway_strategy'],
    'a10-0045/2026': ['global_gateway_strategy', 'ep_plenary_march_2026'],

    # MiFID II / MiFIR - Financial Markets Regulation (training 3 Apr 2026)
    'mifid': ['eu_financial_markets_mifid'],
    'mifid ii': ['eu_financial_markets_mifid'],
    'mifid 2': ['eu_financial_markets_mifid'],
    'mifir': ['eu_financial_markets_mifid'],
    'markets in financial instruments': ['eu_financial_markets_mifid'],
    'financial instruments directive': ['eu_financial_markets_mifid'],
    'investment services directive': ['eu_financial_markets_mifid'],
    'securities markets regulation': ['eu_financial_markets_mifid'],
    'consolidated tape': ['eu_financial_markets_mifid'],
    'consolidated tape provider': ['eu_financial_markets_mifid'],
    'payment for order flow': ['eu_financial_markets_mifid'],
    'pfof': ['eu_financial_markets_mifid'],
    'systematic internaliser': ['eu_financial_markets_mifid'],
    'trading venue': ['eu_financial_markets_mifid'],
    'trading venues': ['eu_financial_markets_mifid'],
    'best execution': ['eu_financial_markets_mifid'],
    'transaction reporting': ['eu_financial_markets_mifid'],
    'pre-trade transparency': ['eu_financial_markets_mifid'],
    'post-trade transparency': ['eu_financial_markets_mifid'],
    'investment firm regulation': ['eu_financial_markets_mifid'],
    'commodity derivatives position': ['eu_financial_markets_mifid'],
    '2014/65/eu': ['eu_financial_markets_mifid'],
    '32014l0065': ['eu_financial_markets_mifid'],
    '600/2014': ['eu_financial_markets_mifid'],
    '32014r0600': ['eu_financial_markets_mifid'],
    'com(2021)726': ['eu_financial_markets_mifid'],
    'com(2021) 726': ['eu_financial_markets_mifid'],
    'com(2021)727': ['eu_financial_markets_mifid'],
    'com(2021) 727': ['eu_financial_markets_mifid'],
    '2021/0384(cod)': ['eu_financial_markets_mifid'],
    '2021/0385(cod)': ['eu_financial_markets_mifid'],
    'directive mifid': ['eu_financial_markets_mifid'],
    'mercados financieros': ['eu_financial_markets_mifid'],
    'instrumentos financieros': ['eu_financial_markets_mifid'],
    'mercats financers': ['eu_financial_markets_mifid'],
    'instruments financers': ['eu_financial_markets_mifid'],
    'marches financiers': ['eu_financial_markets_mifid'],
    'instruments financiers': ['eu_financial_markets_mifid'],
    'mercati finanziari': ['eu_financial_markets_mifid'],
    'strumenti finanziari': ['eu_financial_markets_mifid'],
    'financiele markten': ['eu_financial_markets_mifid'],
    'financiele instrumenten': ['eu_financial_markets_mifid'],

    # EU Food Safety and Pesticide Regulation (training 3 Apr 2026)
    'pesticide': ['eu_food_safety_pesticides'],
    'pesticides': ['eu_food_safety_pesticides'],
    'pesticide regulation': ['eu_food_safety_pesticides'],
    'pesticide residues': ['eu_food_safety_pesticides'],
    'maximum residue level': ['eu_food_safety_pesticides'],
    'maximum residue levels': ['eu_food_safety_pesticides'],
    'plant protection product': ['eu_food_safety_pesticides'],
    'plant protection products': ['eu_food_safety_pesticides'],
    'food safety pesticide': ['eu_food_safety_pesticides'],
    'glyphosate': ['eu_food_safety_pesticides'],
    'active substance approval': ['eu_food_safety_pesticides'],
    'scopaff': ['eu_food_safety_pesticides'],
    'efsa pesticide': ['eu_food_safety_pesticides'],
    'efsa residues': ['eu_food_safety_pesticides'],
    'pesticide database': ['eu_food_safety_pesticides'],
    'sustainable use pesticides': ['eu_food_safety_pesticides'],
    'sur pesticides': ['eu_food_safety_pesticides'],
    '1107/2009': ['eu_food_safety_pesticides'],
    '396/2005': ['eu_food_safety_pesticides'],
    '32009r1107': ['eu_food_safety_pesticides'],
    '32005r0396': ['eu_food_safety_pesticides'],
    '2009/128/ec': ['eu_food_safety_pesticides'],
    'com(2022)305': ['eu_food_safety_pesticides'],
    'com(2022) 305': ['eu_food_safety_pesticides'],
    'pesticida': ['eu_food_safety_pesticides'],
    'pesticidas': ['eu_food_safety_pesticides'],
    'plaguicidas': ['eu_food_safety_pesticides'],
    'residus de pesticides': ['eu_food_safety_pesticides'],
    'residuos de pesticidas': ['eu_food_safety_pesticides'],
    'residus de plaguicides': ['eu_food_safety_pesticides'],
    'pesticides ue': ['eu_food_safety_pesticides'],
    'pesticidi': ['eu_food_safety_pesticides'],
    'residui di pesticidi': ['eu_food_safety_pesticides'],
    'bestrijdingsmiddelen': ['eu_food_safety_pesticides'],
    'pesticiden': ['eu_food_safety_pesticides'],
    'seguretat alimentaria': ['eu_food_safety_pesticides'],
    'securite alimentaire pesticides': ['eu_food_safety_pesticides'],
    'sicurezza alimentare pesticidi': ['eu_food_safety_pesticides'],
    'voedselveiligheid pesticiden': ['eu_food_safety_pesticides'],
    'food safety regulation': ['eu_food_safety_pesticides'],
    'import tolerance': ['eu_food_safety_pesticides'],
    'import tolerances': ['eu_food_safety_pesticides'],
    'emergency authorisation pesticide': ['eu_food_safety_pesticides'],
    'article 53 pesticide': ['eu_food_safety_pesticides'],
    'neonicotinoid': ['eu_food_safety_pesticides'],
    'neonicotinoids': ['eu_food_safety_pesticides'],
    'endocrine disruptor pesticide': ['eu_food_safety_pesticides'],
    'flame retardants food': ['eu_food_safety_pesticides'],
    'contaminants food': ['eu_food_safety_pesticides'],
    'food contaminants': ['eu_food_safety_pesticides'],
    'phytosanitary': ['eu_food_safety_pesticides'],
    'phytosanitary controls': ['eu_food_safety_pesticides'],

    # Multilingual triggers for existing guides (training 3 Apr 2026 round 6-10)
    # Sanctions - multilingual (eu_defence_procurement covers CFSP/sanctions)
    'sancties myanmar': ['eu_defence_procurement'],
    'sancties tegen myanmar': ['eu_defence_procurement'],
    'sanctions birmanie': ['eu_defence_procurement'],
    'sanzioni myanmar': ['eu_defence_procurement'],
    'sanciones myanmar': ['eu_defence_procurement'],
    'sancions myanmar': ['eu_defence_procurement'],
    'sancions contra libia': ['eu_defence_procurement'],
    'regim de sancions': ['eu_defence_procurement'],
    'sanctions contre la libye': ['eu_defence_procurement'],
    'sanzioni contro la libia': ['eu_defence_procurement'],
    'sanciones contra libia': ['eu_defence_procurement'],

    # State aid - multilingual (competition_law_enforcement)
    'aiuti di stato': ['competition_law_enforcement'],
    'aide d etat': ['competition_law_enforcement'],
    'ayudas de estado': ['competition_law_enforcement'],
    'ajuts d estat': ['competition_law_enforcement'],
    'staatssteun': ['competition_law_enforcement'],

    # Biocides - multilingual (reach_chemicals_regulation)
    'produits biocides': ['reach_chemicals_regulation'],
    'productos biocidas': ['reach_chemicals_regulation'],
    'productes biocides': ['reach_chemicals_regulation'],
    'prodotti biocidi': ['reach_chemicals_regulation'],
    'biociden': ['reach_chemicals_regulation'],
    'biocides': ['reach_chemicals_regulation'],

    # Open data directive (no dedicated guide -- route to general digital/data)
    'open data directive': ['ecodesign_digital_product_passport'],
    'dades obertes': ['ecodesign_digital_product_passport'],
    'datos abiertos': ['ecodesign_digital_product_passport'],
    'donnees ouvertes': ['ecodesign_digital_product_passport'],
    'dati aperti': ['ecodesign_digital_product_passport'],
    'open data': ['ecodesign_digital_product_passport'],

    # Digital identity / eIDAS (ecodesign_digital_product_passport covers digital regs)
    'digital identity': ['ecodesign_digital_product_passport'],
    'eu digital identity': ['ecodesign_digital_product_passport'],
    'digital identity wallet': ['ecodesign_digital_product_passport'],
    'eidas': ['ecodesign_digital_product_passport'],
    'eidas regulation': ['ecodesign_digital_product_passport'],
    'identitat digital': ['ecodesign_digital_product_passport'],
    'identidad digital': ['ecodesign_digital_product_passport'],
    'identite numerique': ['ecodesign_digital_product_passport'],
    'identita digitale': ['ecodesign_digital_product_passport'],
    'digitale identiteit': ['ecodesign_digital_product_passport'],

    # Wine export / agrifood Albania (eu_funding_ipa_enlargement)
    'esportare vino': ['eu_funding_ipa_enlargement'],
    'importare vino': ['eu_funding_ipa_enlargement', 'eu_trade_policy'],
    'requisiti importare': ['eu_trade_policy', 'eu_funding_ipa_enlargement'],
    'requisiti ue': ['eu_trade_policy'],
    'exportar vi': ['eu_funding_ipa_enlargement'],
    'exportar vino': ['eu_funding_ipa_enlargement'],
    'importar vino': ['eu_trade_policy', 'eu_funding_ipa_enlargement'],
    'wine export': ['eu_funding_ipa_enlargement', 'eu_trade_policy'],
    'wine import': ['eu_trade_policy'],
    'vino biologico': ['eu_funding_ipa_enlargement'],
    'organic wine': ['eu_funding_ipa_enlargement'],

    # JRC Capitalism, Sustainability and Democracy report (training 3 Apr 2026)
    'jrc144547': ['jrc_capitalism_sustainability_democracy'],
    'capitalism sustainability and democracy': ['jrc_capitalism_sustainability_democracy'],
    'capitalism sustainability democracy': ['jrc_capitalism_sustainability_democracy'],
    'future-proofing the european model': ['jrc_capitalism_sustainability_democracy'],
    'future proofing the european model': ['jrc_capitalism_sustainability_democracy'],
    'schumpeterian triangle': ['jrc_capitalism_sustainability_democracy'],
    'dynamic triangle': ['jrc_capitalism_sustainability_democracy'],
    'fair and sustainable economy': ['jrc_capitalism_sustainability_democracy'],
    'fase working paper': ['jrc_capitalism_sustainability_democracy'],
    'luc soete': ['jrc_capitalism_sustainability_democracy'],
    'sylvia schwaag serger': ['jrc_capitalism_sustainability_democracy'],
    'mikel landabaso': ['jrc_capitalism_sustainability_democracy'],
    'johan stierna': ['jrc_capitalism_sustainability_democracy'],
    'integrated orchestration': ['jrc_capitalism_sustainability_democracy'],
    'territorial myopia': ['jrc_capitalism_sustainability_democracy', 'cohesion_policy_audit'],
    'geography of discontent': ['jrc_capitalism_sustainability_democracy', 'cohesion_policy_audit'],
    'middle tech trap': ['jrc_capitalism_sustainability_democracy', 'eu_chips_act'],
    'quantum policymaking': ['jrc_capitalism_sustainability_democracy'],
    'creative resource efficiency': ['jrc_capitalism_sustainability_democracy'],
    'triangle of hope': ['jrc_capitalism_sustainability_democracy'],
    'triangle of sadness': ['jrc_capitalism_sustainability_democracy'],
    'capitalisme durabilite democratie': ['jrc_capitalism_sustainability_democracy'],
    'capitalismo sostenibilidad democracia': ['jrc_capitalism_sustainability_democracy'],
    'capitalisme sostenibilitat democracia': ['jrc_capitalism_sustainability_democracy'],
    'capitalismo sostenibilita democrazia': ['jrc_capitalism_sustainability_democracy'],

    # Multilingual triggers batch 2 (training 3 Apr 2026, rounds 1-10 session 2)

    # Parent-subsidiary directive / cross-border taxation (eu_budget_emu_law)
    'parent-subsidiary directive': ['eu_budget_emu_law'],
    'parent subsidiary directive': ['eu_budget_emu_law'],
    'parent-subsidiary': ['eu_budget_emu_law'],
    'parent subsidiary': ['eu_budget_emu_law'],
    'cross-border taxation': ['eu_budget_emu_law'],
    'directiva matrius i filials': ['eu_budget_emu_law'],
    'societa madri e figlie': ['eu_budget_emu_law'],
    'directive societes meres filiales': ['eu_budget_emu_law'],
    'sociedades matrices y filiales': ['eu_budget_emu_law'],
    'moeder-dochterrichtlijn': ['eu_budget_emu_law'],
    '2011/96/eu': ['eu_budget_emu_law'],
    '2015/121': ['eu_budget_emu_law'],

    # Basel Convention / hazardous waste (reach_chemicals_regulation covers environmental chemicals)
    'conveni de basilea': ['reach_chemicals_regulation'],
    'convenio de basilea': ['reach_chemicals_regulation'],
    'convention de bale': ['reach_chemicals_regulation'],
    'convenzione di basilea': ['reach_chemicals_regulation'],
    'verdrag van bazel': ['reach_chemicals_regulation'],
    'hazardous waste': ['reach_chemicals_regulation'],
    'residus perillosos': ['reach_chemicals_regulation'],
    'residuos peligrosos': ['reach_chemicals_regulation'],
    'dechets dangereux': ['reach_chemicals_regulation'],
    'rifiuti pericolosi': ['reach_chemicals_regulation'],
    'gevaarlijk afval': ['reach_chemicals_regulation'],

    # Food/feed additives (eu_food_safety_pesticides -- closest match)
    'food additive': ['eu_food_safety_pesticides'],
    'food additives': ['eu_food_safety_pesticides'],
    'feed additive': ['eu_food_safety_pesticides'],
    'feed additives': ['eu_food_safety_pesticides'],
    'food additive regulation': ['eu_food_safety_pesticides'],
    'additifs alimentaires': ['eu_food_safety_pesticides'],
    'aditivos alimentarios': ['eu_food_safety_pesticides'],
    'additivi alimentari': ['eu_food_safety_pesticides'],
    'voedseladditieven': ['eu_food_safety_pesticides'],

    # Avian influenza / animal health (eu_food_safety_pesticides -- food safety adjacent)
    'avian influenza': ['eu_food_safety_pesticides'],
    'bird flu': ['eu_food_safety_pesticides'],
    'gripe aviar': ['eu_food_safety_pesticides'],
    'grippe aviaire': ['eu_food_safety_pesticides'],
    'influenza aviaria': ['eu_food_safety_pesticides'],
    'vogelgriep': ['eu_food_safety_pesticides'],

    # Anti-circumvention / trade defence (eu_trade_defence)
    'anti-circumvention': ['eu_trade_defence'],
    'circumvention investigation': ['eu_trade_defence'],
    'circumvention': ['eu_trade_defence'],

    # Excise duty (eu_budget_emu_law covers tax/fiscal)
    'excise duty': ['eu_budget_emu_law'],
    'excise duties': ['eu_budget_emu_law'],
    'accijns': ['eu_budget_emu_law'],
    'accijnzen': ['eu_budget_emu_law'],
    'accise': ['eu_budget_emu_law'],
    'impuestos especiales': ['eu_budget_emu_law'],
    'impostos especials': ['eu_budget_emu_law'],

    # Professional qualifications (employment_future_of_work)
    'professional qualifications': ['employment_future_of_work'],
    'recognition of qualifications': ['employment_future_of_work'],
    'cualificaciones profesionales': ['employment_future_of_work'],
    'reconocimiento de cualificaciones': ['employment_future_of_work'],
    'qualifications professionnelles': ['employment_future_of_work'],
    'reconnaissance des qualifications': ['employment_future_of_work'],
    'beroepskwalificaties': ['employment_future_of_work'],
    'erkenning van beroepskwalificaties': ['employment_future_of_work'],
    'qualifiche professionali': ['employment_future_of_work'],
    'riconoscimento delle qualifiche': ['employment_future_of_work'],
    'qualificacions professionals': ['employment_future_of_work'],
    '2005/36/ec': ['employment_future_of_work'],

    # Schengen (eu_migration_asylum_pact covers JHA/Schengen)
    'schengen information system': ['eu_migration_asylum_pact'],
    'sistema d informacio de schengen': ['eu_migration_asylum_pact'],
    'sistema de informacion de schengen': ['eu_migration_asylum_pact'],
    'systeme d information schengen': ['eu_migration_asylum_pact'],
    'sistema informativo schengen': ['eu_migration_asylum_pact'],
    'schengen informatiesysteem': ['eu_migration_asylum_pact'],

    # European Citizens Initiative (committee_of_the_regions covers participatory democracy)
    'initiative citoyenne europeenne': ['committee_of_the_regions'],
    'iniciativa ciudadana europea': ['committee_of_the_regions'],
    'iniciativa ciutadana europea': ['committee_of_the_regions'],
    'iniziativa dei cittadini europei': ['committee_of_the_regions'],
    'europees burgerinitiatief': ['committee_of_the_regions'],

    # Restrictive measures / sanctions - multilingual (eu_defence_procurement)
    'medidas restrictivas': ['eu_defence_procurement'],
    'mesures restrictives': ['eu_defence_procurement'],
    'misure restrittive': ['eu_defence_procurement'],
    'beperkende maatregelen': ['eu_defence_procurement'],
    'mesures restrictives de la ue': ['eu_defence_procurement'],
    'sanciones rusia': ['eu_defence_procurement'],
    'sanciones contra rusia': ['eu_defence_procurement'],

    # EU Solidarity Fund (eu_budget_emu_law covers EU budget instruments)
    'solidarity fund': ['eu_budget_emu_law'],
    'eu solidarity fund': ['eu_budget_emu_law'],
    'european solidarity fund': ['eu_budget_emu_law'],
    'fondo de solidaridad': ['eu_budget_emu_law'],
    'fondo de solidaridad de la ue': ['eu_budget_emu_law'],
    'fonds de solidarite': ['eu_budget_emu_law'],
    'fondo di solidarieta': ['eu_budget_emu_law'],
    'solidariteitsfonds': ['eu_budget_emu_law'],
    'eu solidariteitsfonds': ['eu_budget_emu_law'],

    # CBAM / Carbon border adjustment - multilingual (eu_trade_policy)
    'mecanisme d ajust en frontera per carboni': ['eu_trade_policy'],
    'mecanismo de ajuste en frontera': ['eu_trade_policy'],
    'mecanisme d ajustement carbone': ['eu_trade_policy'],
    'meccanismo di adeguamento del carbonio': ['eu_trade_policy'],
    'koolstofgrenscorrectie': ['eu_trade_policy'],

    # Excessive deficit procedure - multilingual (european_semester_annual_report_2026)
    'excessive deficit procedure': ['european_semester_annual_report_2026'],
    'excessive deficit': ['european_semester_annual_report_2026'],
    'deficit procedure': ['european_semester_annual_report_2026'],
    'procedura per disavanzo eccessivo': ['european_semester_annual_report_2026'],
    'disavanzo eccessivo': ['european_semester_annual_report_2026'],
    'procedimiento de deficit excesivo': ['european_semester_annual_report_2026'],
    'procedure de deficit excessif': ['european_semester_annual_report_2026'],
    'buitensporigtekortprocedure': ['european_semester_annual_report_2026'],

    # Customs cooperation - multilingual (eu_trade_policy)
    'customs cooperation': ['eu_trade_policy'],
    'cooperation douaniere': ['eu_trade_policy'],
    'cooperazione doganale': ['eu_trade_policy'],
    'cooperacion aduanera': ['eu_trade_policy'],
    'douanesamenwerking': ['eu_trade_policy'],

    # Rules of origin - multilingual (eu_trade_policy)
    'normas de origen': ['eu_trade_policy'],
    'normes d origen': ['eu_trade_policy'],
    'regles d origine': ['eu_trade_policy'],
    'norme di origine': ['eu_trade_policy'],
    'oorsprongsregels': ['eu_trade_policy'],

    # RoHS / hazardous substances electronics (reach_chemicals_regulation)
    'rohs': ['reach_chemicals_regulation'],
    'rohs directive': ['reach_chemicals_regulation'],
    'hazardous substances electronics': ['reach_chemicals_regulation'],
    'substancies perilloses': ['reach_chemicals_regulation'],
    'sustancias peligrosas': ['reach_chemicals_regulation'],
    'substances dangereuses': ['reach_chemicals_regulation'],
    'sostanze pericolose': ['reach_chemicals_regulation'],
    'gevaarlijke stoffen': ['reach_chemicals_regulation'],

    # EU military missions Africa - multilingual (eu_defence_procurement)
    'missions militaires': ['eu_defence_procurement'],
    'misiones militares': ['eu_defence_procurement'],
    'missions militars': ['eu_defence_procurement'],
    'missioni militari': ['eu_defence_procurement'],
    'militaire missies': ['eu_defence_procurement'],

    # EU Drugs Agency - missing ES trigger
    'agencia europea de drogas': ['eu_drugs_agency_euda'],
    'agencia de drogas ue': ['eu_drugs_agency_euda'],

    # Belgrade-Pristina - multilingual (eu_special_representatives)
    'dialeg belgrad-pristina': ['eu_special_representatives'],
    'dialeg belgrad pristina': ['eu_special_representatives'],
    'dialogo belgrado-pristina': ['eu_special_representatives'],
    'dialogo belgrado pristina': ['eu_special_representatives'],
    'dialogue belgrade-pristina': ['eu_special_representatives'],

    # Asylum fund - multilingual (eu_justice_security)
    'asielfonds': ['eu_migration_asylum_pact'],
    'europees asielfonds': ['eu_migration_asylum_pact'],
    'fondo de asilo': ['eu_migration_asylum_pact'],
    'fonds d asile': ['eu_migration_asylum_pact'],
    'fondo asilo': ['eu_migration_asylum_pact'],

    # Geographical indications / PDO / PGI (eu_australia_trade_agreement covers GIs)
    'geographical indication': ['eu_australia_trade_agreement'],
    'geographical indications': ['eu_australia_trade_agreement'],
    'protected designation of origin': ['eu_australia_trade_agreement'],
    'denominacion de origen protegida': ['eu_australia_trade_agreement'],
    'denominacions d origen protegides': ['eu_australia_trade_agreement'],
    'appellation d origine protegee': ['eu_australia_trade_agreement'],
    'denominazione di origine protetta': ['eu_australia_trade_agreement'],
    'beschermde oorsprongsbenaming': ['eu_australia_trade_agreement'],

    # EU Special Representatives / Kosovo / CFSP (training 3 Apr 2026)
    'eu special representative': ['eu_special_representatives'],
    'eusr': ['eu_special_representatives'],
    'eusr kosovo': ['eu_special_representatives'],
    'eusr bosnia': ['eu_special_representatives'],
    'eusr sahel': ['eu_special_representatives'],
    'eusr human rights': ['eu_special_representatives'],
    'eusr central asia': ['eu_special_representatives'],
    'eusr horn of africa': ['eu_special_representatives'],
    'eusr middle east': ['eu_special_representatives'],
    'eusr south caucasus': ['eu_special_representatives'],
    'eusr gulf': ['eu_special_representatives'],
    'eusr great lakes': ['eu_special_representatives'],
    'aivo orav': ['eu_special_representatives'],
    'peter sorensen belgrade': ['eu_special_representatives'],
    'belgrade-pristina dialogue': ['eu_special_representatives'],
    'belgrade pristina': ['eu_special_representatives'],
    'eulex kosovo': ['eu_special_representatives'],
    'eulex': ['eu_special_representatives'],
    'eu office kosovo': ['eu_special_representatives'],
    'representant especial de la ue': ['eu_special_representatives'],
    'representante especial de la ue': ['eu_special_representatives'],
    'representant special de l ue': ['eu_special_representatives'],
    'rappresentante speciale ue': ['eu_special_representatives'],
    'eu speciaal vertegenwoordiger': ['eu_special_representatives'],
    'luigi soreca bosnia': ['eu_special_representatives'],
    'kaja kallas special representative': ['eu_special_representatives'],

    # EU Drugs Agency / EUDA / EMCDDA (training 3 Apr 2026)
    'emcdda': ['eu_drugs_agency_euda'],
    'euda': ['eu_drugs_agency_euda'],
    'eu drugs agency': ['eu_drugs_agency_euda'],
    'european drugs agency': ['eu_drugs_agency_euda'],
    'drugs agency': ['eu_drugs_agency_euda'],
    'drug monitoring': ['eu_drugs_agency_euda'],
    'european drug report': ['eu_drugs_agency_euda'],
    'drug report europe': ['eu_drugs_agency_euda'],
    'illicit drugs eu': ['eu_drugs_agency_euda'],
    'drug policy eu': ['eu_drugs_agency_euda'],
    'eu drug strategy': ['eu_drugs_agency_euda'],
    'new psychoactive substances': ['eu_drugs_agency_euda'],
    'reitox': ['eu_drugs_agency_euda'],
    'reitox network': ['eu_drugs_agency_euda'],
    '2023/1322': ['eu_drugs_agency_euda'],
    '32023r1322': ['eu_drugs_agency_euda'],
    'agencia de drogas de la ue': ['eu_drugs_agency_euda'],
    'agence des drogues': ['eu_drugs_agency_euda'],
    'agenzia droga': ['eu_drugs_agency_euda'],
    'agencia de drogues': ['eu_drugs_agency_euda'],
    'drugsagentschap': ['eu_drugs_agency_euda'],
    'drug precursor': ['eu_drugs_agency_euda'],
    'drug precursors': ['eu_drugs_agency_euda'],
    'synthetic opioids eu': ['eu_drugs_agency_euda'],
    'fentanyl eu': ['eu_drugs_agency_euda'],

    # EU Railway Regulation (training 3 Apr 2026)
    'railway regulation': ['eu_railway_regulation'],
    'railway package': ['eu_railway_regulation'],
    'fourth railway package': ['eu_railway_regulation'],
    '4th railway package': ['eu_railway_regulation'],
    'railway safety': ['eu_railway_regulation'],
    'railway safety directive': ['eu_railway_regulation'],
    'railway interoperability': ['eu_railway_regulation'],
    'rail interoperability': ['eu_railway_regulation'],
    'rail safety': ['eu_railway_regulation'],
    'rail regulation': ['eu_railway_regulation'],
    'rail transport eu': ['eu_railway_regulation'],
    'single european railway area': ['eu_railway_regulation'],
    'eu agency for railways': ['eu_railway_regulation'],
    'european railway agency': ['eu_railway_regulation'],
    'ertms': ['eu_railway_regulation'],
    'european rail traffic management': ['eu_railway_regulation'],
    'train control system': ['eu_railway_regulation'],
    'rail freight corridor': ['eu_railway_regulation'],
    'rail freight corridors': ['eu_railway_regulation'],
    'high-speed rail eu': ['eu_railway_regulation'],
    'high speed rail': ['eu_railway_regulation'],
    'rail passenger rights': ['eu_railway_regulation'],
    '2016/796': ['eu_railway_regulation'],
    '2016/797': ['eu_railway_regulation'],
    '2016/798': ['eu_railway_regulation'],
    '2012/34/eu': ['eu_railway_regulation'],
    '32016r0796': ['eu_railway_regulation'],
    'ferrocarril ue': ['eu_railway_regulation'],
    'seguretat ferroviaria': ['eu_railway_regulation'],
    'ferroviaire ue': ['eu_railway_regulation'],
    'securite ferroviaire': ['eu_railway_regulation'],
    'ferrovia ue': ['eu_railway_regulation'],
    'sicurezza ferroviaria': ['eu_railway_regulation'],
    'spoorwegveiligheid': ['eu_railway_regulation'],
    'spoorwegen eu': ['eu_railway_regulation'],
    'paquete ferroviario': ['eu_railway_regulation'],
    'paquet ferroviari': ['eu_railway_regulation'],
    'paquet ferroviaire': ['eu_railway_regulation'],
    'pacchetto ferroviario': ['eu_railway_regulation'],
    'spoorwegpakket': ['eu_railway_regulation'],

    # EU Competitiveness Council Debate -- Member State Positions
    'competitiveness debate': ['eu_competitiveness_council_debate', 'fp10_ecf_competitiveness'],
    'competitiveness council': ['eu_competitiveness_council_debate'],
    'competitiveness compass': ['eu_competitiveness_council_debate', 'industrial_accelerator_act'],
    'com(2025)30': ['eu_competitiveness_council_debate'],
    'com(2025) 30': ['eu_competitiveness_council_debate'],
    'member state positions': ['eu_competitiveness_council_debate'],
    'member state positions competitiveness': ['eu_competitiveness_council_debate'],
    'council positions competitiveness': ['eu_competitiveness_council_debate'],
    'state aid reform': ['eu_competitiveness_council_debate', 'competition_law_enforcement'],
    'state aid flexibility': ['eu_competitiveness_council_debate', 'competition_law_enforcement'],
    'state aid rules': ['eu_competitiveness_council_debate', 'competition_law_enforcement'],
    'relax state aid': ['eu_competitiveness_council_debate'],
    'made in eu': ['eu_competitiveness_council_debate', 'industrial_accelerator_act'],
    'made in europe': ['eu_competitiveness_council_debate', 'industrial_accelerator_act'],
    'european preference': ['eu_competitiveness_council_debate', 'industrial_accelerator_act', 'eu_defence_procurement'],
    'european preference procurement': ['eu_competitiveness_council_debate', 'industrial_accelerator_act'],
    'eu preference': ['eu_competitiveness_council_debate'],
    'buy european': ['eu_competitiveness_council_debate', 'industrial_accelerator_act'],
    'buy european act': ['eu_competitiveness_council_debate', 'industrial_accelerator_act'],
    'climate rollback': ['eu_competitiveness_council_debate', 'european_climate_law'],
    'climate vs competitiveness': ['eu_competitiveness_council_debate'],
    'green deal rollback': ['eu_competitiveness_council_debate', 'european_climate_law'],
    'ets competitiveness': ['eu_competitiveness_council_debate', 'european_climate_law'],
    'ets2 delay': ['eu_competitiveness_council_debate', 'european_climate_law'],
    'ets2 postponement': ['eu_competitiveness_council_debate', 'european_climate_law'],
    'regulatory simplification': ['eu_competitiveness_council_debate', 'industrial_accelerator_act'],
    'cutting red tape': ['eu_competitiveness_council_debate'],
    'red tape eu': ['eu_competitiveness_council_debate'],
    'simplification omnibus': ['eu_competitiveness_council_debate'],
    'omnibus simplification': ['eu_competitiveness_council_debate'],
    'competitiveness gap': ['eu_competitiveness_council_debate', 'fp10_ecf_competitiveness', 'jrc_capitalism_sustainability_democracy'],
    'industrial policy eu': ['eu_competitiveness_council_debate', 'industrial_accelerator_act'],
    'eu industrial policy': ['eu_competitiveness_council_debate', 'industrial_accelerator_act'],
    'subsidies vs single market': ['eu_competitiveness_council_debate'],
    'france state aid': ['eu_competitiveness_council_debate'],
    'germany competitiveness': ['eu_competitiveness_council_debate'],
    'netherlands state aid': ['eu_competitiveness_council_debate'],
    'frugal states': ['eu_competitiveness_council_debate'],
    'national champions': ['eu_competitiveness_council_debate'],
    'sovereign fund': ['eu_competitiveness_council_debate'],
    'eu sovereign fund': ['eu_competitiveness_council_debate'],
    'level playing field single market': ['eu_competitiveness_council_debate'],
    'who wants what competitiveness': ['eu_competitiveness_council_debate'],
    'council debate competitiveness': ['eu_competitiveness_council_debate'],
    'council debate industrial': ['eu_competitiveness_council_debate'],
    # Multilingual -- competitiveness council debate
    'debat competitivitat': ['eu_competitiveness_council_debate'],
    'debat competitivite': ['eu_competitiveness_council_debate'],
    'debate competitividad': ['eu_competitiveness_council_debate'],
    'dibattito competitivita': ['eu_competitiveness_council_debate'],
    'concurrentiedebat': ['eu_competitiveness_council_debate'],
    'aide d\'etat': ['eu_competitiveness_council_debate', 'competition_law_enforcement'],
    'ayuda de estado': ['eu_competitiveness_council_debate', 'competition_law_enforcement'],
    'ajut d\'estat': ['eu_competitiveness_council_debate', 'competition_law_enforcement'],
    'aiuto di stato': ['eu_competitiveness_council_debate', 'competition_law_enforcement'],
    'staatssteun': ['eu_competitiveness_council_debate', 'competition_law_enforcement'],
    'preference europeenne': ['eu_competitiveness_council_debate'],
    'preferencia europea': ['eu_competitiveness_council_debate'],
    'preferenza europea': ['eu_competitiveness_council_debate'],
    'europese voorkeur': ['eu_competitiveness_council_debate'],
    'preferencia europea compres': ['eu_competitiveness_council_debate'],
    # === Spanish outreach training triggers (April 2026) ===
    # Social: anti-poverty, child guarantee, minimum wages, disability
    'anti-poverty': ['employment_future_of_work'],
    'anti-poverty strategy': ['employment_future_of_work'],
    'estrategia contra la pobreza': ['employment_future_of_work'],
    'child guarantee': ['employment_future_of_work'],
    'garantia infantil': ['employment_future_of_work'],
    'garantia juvenil': ['employment_future_of_work'],
    'minimum wage': ['employment_future_of_work', 'eu_social_dialogue'],
    'minimum wages': ['employment_future_of_work', 'eu_social_dialogue'],
    'salario minimo': ['employment_future_of_work', 'eu_social_dialogue'],
    'adequate minimum wages directive': ['employment_future_of_work'],
    'disability rights': ['employment_future_of_work'],
    'disability strategy': ['employment_future_of_work'],
    'derechos discapacidad': ['employment_future_of_work'],
    'personas con discapacidad': ['employment_future_of_work'],
    'european disability card': ['employment_future_of_work'],
    # Civil society: transparency register, lobbying, NGO
    'transparency register': ['lobbying_methodology'],
    'registro de transparencia': ['lobbying_methodology'],
    'lobbying rules': ['lobbying_methodology'],
    'transparency rules': ['lobbying_methodology'],
    'normas de transparencia': ['lobbying_methodology'],
    'rules for lobbying': ['lobbying_methodology'],
    'lobby register': ['lobbying_methodology'],
    'interinstitutional agreement lobbying': ['lobbying_methodology'],
    'ngo funding': ['eu_social_dialogue'],
    'ngo regulation': ['eu_social_dialogue'],
    'financiacion ong': ['eu_social_dialogue'],
    'civil society funding': ['eu_social_dialogue'],
    # Finance: Solvency II, Listing Act, Basel
    'solvency ii': ['financial_supervision_eba'],
    'solvency ii review': ['financial_supervision_eba'],
    'solvencia ii': ['financial_supervision_eba'],
    'insurance regulation': ['financial_supervision_eba'],
    'eiopa': ['financial_supervision_eba'],
    'listing act': ['eu_financial_markets_mifid'],
    'eu listing act': ['eu_financial_markets_mifid'],
    'capital markets union': ['eu_financial_markets_mifid'],
    'ipo regulation': ['eu_financial_markets_mifid'],
    'basel iv': ['banking_union_reform'],
    'basel implementation': ['banking_union_reform'],
    'capital requirements': ['banking_union_reform'],
    'crr': ['banking_union_reform'],
    'crd': ['banking_union_reform'],
    # Agriculture: animal welfare
    'animal welfare': ['common_agricultural_policy'],
    'bienestar animal': ['common_agricultural_policy'],
    'animal transport': ['common_agricultural_policy'],
    'transporte de animales': ['common_agricultural_policy'],
    # Transport: TEN-T
    'ten-t': ['aviation_transport_policy'],
    'trans-european transport network': ['aviation_transport_policy'],
    'ten-t regulation': ['aviation_transport_policy'],
    'transport infrastructure': ['aviation_transport_policy'],
    'infraestructura de transporte': ['aviation_transport_policy'],
    # Trade: intellectual property
    'intellectual property': ['eu_trade_policy'],
    'propiedad intelectual': ['eu_trade_policy'],
    'patent protection': ['eu_trade_policy'],
    'trademark regulation': ['eu_trade_policy'],
    'unitary patent': ['eu_trade_policy'],
    # Research: open science
    'open science': ['fp10_ecf_competitiveness'],
    'open access': ['fp10_ecf_competitiveness'],
    'ciencia abierta': ['fp10_ecf_competitiveness'],
    'research data sharing': ['fp10_ecf_competitiveness'],
    # EP committee codes -> policy guides
    'itre committee': ['eu_energy_policy', 'fp10_ecf_competitiveness'],
    'itre': ['eu_energy_policy', 'fp10_ecf_competitiveness'],
    'meps on itre': ['eu_energy_policy'],
    'envi committee': ['european_climate_law', 'eu_food_safety_pesticides'],
    'econ committee': ['eu_financial_markets_mifid', 'banking_union_reform'],
    'imco committee': ['ecodesign_digital_product_passport'],
    'tran committee': ['aviation_transport_policy'],
    'agri committee': ['common_agricultural_policy'],
    'pech committee': ['common_agricultural_policy'],
    'libe committee': ['csam_regulation_online'],
    'juri committee': ['eu_trade_policy'],
    'empl committee': ['employment_future_of_work'],
    'inta committee': ['eu_trade_policy'],
    # Digital: Data Act, algorithmic accountability
    'data act': ['ecodesign_digital_product_passport'],
    'eu data act': ['ecodesign_digital_product_passport'],
    'regulation 2023/2854': ['ecodesign_digital_product_passport'],
    'data sharing': ['ecodesign_digital_product_passport'],
    'data access rights': ['ecodesign_digital_product_passport'],
    'iot data': ['ecodesign_digital_product_passport'],
    'algorithmic accountability': ['ai_act_regulation'],
    'algorithmic transparency': ['ai_act_regulation'],
    'automated decision': ['ai_act_regulation'],
    'automated decision-making': ['ai_act_regulation'],
    # Health: clinical trials, paediatric medicines
    'clinical trials': ['eu_pharmaceutical_framework'],
    'clinical trial regulation': ['eu_pharmaceutical_framework'],
    'regulation 536/2014': ['eu_pharmaceutical_framework'],
    'ensayos clinicos': ['eu_pharmaceutical_framework'],
    'paediatric medicines': ['eu_pharmaceutical_legislation_reform', 'critical_medicines_act'],
    'paediatric regulation': ['eu_pharmaceutical_legislation_reform'],
    'pediatric medicines': ['eu_pharmaceutical_legislation_reform', 'critical_medicines_act'],
    'medicamentos pediatricos': ['eu_pharmaceutical_legislation_reform'],
    'children medicines': ['eu_pharmaceutical_legislation_reform'],
    # Finance: PSD3/PSR, NPL, retail investment
    'psd3': ['eu_financial_markets_mifid'],
    'payment services directive': ['eu_financial_markets_mifid'],
    'payment services regulation': ['eu_financial_markets_mifid'],
    'psr': ['eu_financial_markets_mifid'],
    'open banking': ['eu_financial_markets_mifid'],
    'non-performing loans': ['banking_union_reform'],
    'non performing loans': ['banking_union_reform'],
    'npl': ['banking_union_reform'],
    'npl directive': ['banking_union_reform'],
    'credit servicers': ['banking_union_reform'],
    'retail investment strategy': ['eu_financial_markets_mifid'],
    'retail investor': ['eu_financial_markets_mifid'],
    'retail investors': ['eu_financial_markets_mifid'],
    'investment advice': ['eu_financial_markets_mifid'],
    'inducements ban': ['eu_financial_markets_mifid'],
    # Agriculture: wine PDO, soil health, food waste
    'wine labelling': ['common_agricultural_policy'],
    'wine regulation': ['common_agricultural_policy'],
    'pdo': ['common_agricultural_policy'],
    'pgi': ['common_agricultural_policy'],
    'geographical indication': ['common_agricultural_policy'],
    'denominacion de origen': ['common_agricultural_policy'],
    'indicacion geografica': ['common_agricultural_policy'],
    'soil health': ['nature_restoration_law'],
    'soil health law': ['nature_restoration_law'],
    'soil monitoring': ['nature_restoration_law'],
    'soil strategy': ['nature_restoration_law'],
    'food waste': ['eu_food_safety_pesticides'],
    'food waste reduction': ['eu_food_safety_pesticides'],
    'desperdicio alimentario': ['eu_food_safety_pesticides'],
    'food loss': ['eu_food_safety_pesticides'],
    # Transport: maritime, combined transport, urban mobility
    'maritime transport': ['aviation_transport_policy'],
    'shipping regulation': ['aviation_transport_policy'],
    'port regulation': ['aviation_transport_policy'],
    'transporte maritimo': ['aviation_transport_policy'],
    'combined transport': ['aviation_transport_policy'],
    'multimodal transport': ['aviation_transport_policy'],
    'intermodal transport': ['aviation_transport_policy'],
    'transporte combinado': ['aviation_transport_policy'],
    'urban mobility': ['aviation_transport_policy'],
    'urban transport': ['aviation_transport_policy'],
    'movilidad urbana': ['aviation_transport_policy'],
    'sustainable urban mobility': ['aviation_transport_policy'],
    # Research: Marie Curie
    'marie curie': ['fp10_ecf_competitiveness'],
    'marie sklodowska-curie': ['fp10_ecf_competitiveness'],
    'msca': ['fp10_ecf_competitiveness'],
    'msca fellowship': ['fp10_ecf_competitiveness'],
    'postdoctoral fellowship': ['fp10_ecf_competitiveness'],
    'becas marie curie': ['fp10_ecf_competitiveness'],
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
        self.guide_freshness: Dict[str, datetime] = {}  # Guide last-modified dates for staleness tracking
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
        """Load reference guide Markdown files into memory with freshness tracking"""
        if not self.guides_dir.exists():
            logger.info(f"Guides directory not found: {self.guides_dir}")
            return

        for md_file in self.guides_dir.glob("*.md"):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    key = md_file.stem  # e.g., "eu_jargon", "council_guide"
                    self.guides[key] = content

                    # Track freshness: use file mtime as last-verified date
                    mtime = datetime.fromtimestamp(md_file.stat().st_mtime)
                    self.guide_freshness[key] = mtime

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

    def _extract_quick_facts(self, content: str) -> str:
        """
        Extract the QUICK FACTS block from a guide's content.

        Returns the text between '## QUICK FACTS' and the next '##' heading,
        or the first 500 chars if no QUICK FACTS block exists.
        """
        qf_match = re.search(
            r'##\s*QUICK\s*FACTS\s*\n(.*?)(?=\n##\s|\Z)',
            content,
            re.DOTALL | re.IGNORECASE
        )
        if qf_match:
            return qf_match.group(1).strip()
        # Fallback: return first 500 chars after the title
        title_end = content.find('\n', content.find('#'))
        if title_end != -1:
            return content[title_end:title_end + 500].strip()
        return content[:500].strip()

    def get_guide_staleness(self, guide_name: str, stale_after_days: int = 30) -> Optional[str]:
        """
        Check if a guide is stale and return a caveat string if so.

        Mirrors Claude Code's memory staleness signal: when a memory is older
        than a threshold, inject a warning so the AI knows to verify.

        Args:
            guide_name: Guide identifier
            stale_after_days: Number of days after which a guide is considered stale

        Returns:
            Staleness caveat string, or None if guide is fresh
        """
        mtime = self.guide_freshness.get(guide_name)
        if not mtime:
            return None

        age_days = (datetime.now() - mtime).days
        if age_days > stale_after_days:
            return (
                f"[STALENESS NOTE: This guide was last updated {age_days} days ago "
                f"({mtime.strftime('%d %B %Y')}). Positions, statuses, or dates "
                f"may have evolved since then. Verify key facts before presenting "
                f"as current.]"
            )
        return None

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

    def search_guides(self, query: str, output_mode: str = 'full') -> List[Dict[str, Any]]:
        """
        Search guides by keyword triggers and content matching.

        Uses a two-pass approach:
        1. Keyword triggers: check if any trigger phrases appear in the query
           (higher priority, more precise matching)
        2. Content search: fallback to searching guide names and content
           (lower priority, broader matching)

        Args:
            query: Search query (searches triggers, name, and content)
            output_mode: Controls what data is returned per guide:
                - 'full': guide ID, title, snippet, full content available via get_guide()
                - 'quick_facts': guide ID, title, and QUICK FACTS block only (for ranking)
                - 'titles_only': guide ID and title only (lowest token cost)

        Returns:
            List of matching guides with context snippets, ordered by relevance
        """
        query_lower = query.lower()
        triggered_guides = set()
        matches = []
        seen_ids = set()

        # Pass 1: Keyword trigger matching (highest priority)
        # Check multi-word triggers first (longer = more specific), then single-word
        # Short triggers (<=4 chars) use word-boundary matching to avoid false positives
        # (e.g., "ects" in "insects", "ern" in "modern", "cap" in "capital")
        sorted_triggers = sorted(GUIDE_KEYWORD_TRIGGERS.keys(), key=len, reverse=True)
        for trigger in sorted_triggers:
            if len(trigger) <= 4:
                # Word-boundary match for short triggers
                if re.search(r'(?<![a-z])' + re.escape(trigger) + r'(?![a-z])', query_lower):
                    for guide_id in GUIDE_KEYWORD_TRIGGERS[trigger]:
                        if guide_id in self.guides and guide_id not in seen_ids:
                            triggered_guides.add(guide_id)
            else:
                if trigger in query_lower:
                    for guide_id in GUIDE_KEYWORD_TRIGGERS[trigger]:
                        if guide_id in self.guides and guide_id not in seen_ids:
                            triggered_guides.add(guide_id)

        # Add triggered guides first (they are the most relevant)
        for guide_id in triggered_guides:
            content = self.guides[guide_id]
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else guide_id.replace('_', ' ').title()

            match_data = {
                'id': guide_id,
                'title': title,
                'trigger_matched': True
            }

            if output_mode != 'titles_only':
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
                match_data['snippet'] = snippet

            if output_mode == 'quick_facts':
                match_data['quick_facts'] = self._extract_quick_facts(content)

            matches.append(match_data)
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

                match_data = {
                    'id': name,
                    'title': title,
                    'trigger_matched': False
                }

                if output_mode != 'titles_only':
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
                    match_data['snippet'] = snippet

                if output_mode == 'quick_facts':
                    match_data['quick_facts'] = self._extract_quick_facts(content)

                matches.append(match_data)
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
