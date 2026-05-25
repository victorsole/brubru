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
    # News updates 1 May 2026 (Friday Labour Day) — 4 new guides
    # Terrible Ten Single Market barriers + proportionality guidance (DG GROW 30 Apr 2026)
    'terrible ten': ['terrible_ten_single_market_barriers'],
    'terrible 10': ['terrible_ten_single_market_barriers'],
    'single market barriers': ['terrible_ten_single_market_barriers'],
    'proportionality guidance': ['terrible_ten_single_market_barriers'],
    'smtd': ['terrible_ten_single_market_barriers'],
    'single market transparency directive': ['terrible_ten_single_market_barriers'],
    '32015l1535': ['terrible_ten_single_market_barriers'],
    'directive 2015/1535': ['terrible_ten_single_market_barriers'],
    'tris notification': ['terrible_ten_single_market_barriers'],
    'technical regulation information system': ['terrible_ten_single_market_barriers'],
    'ip/26/901': ['terrible_ten_single_market_barriers'],
    'simpler clearer rulebook': ['terrible_ten_single_market_barriers'],
    'diez terribles': ['terrible_ten_single_market_barriers'],
    'barreras mercado único': ['terrible_ten_single_market_barriers'],
    'barreras mercado unico': ['terrible_ten_single_market_barriers'],
    'directiva transparencia mercado único': ['terrible_ten_single_market_barriers'],
    'dix terribles': ['terrible_ten_single_market_barriers'],
    'barrières marché unique': ['terrible_ten_single_market_barriers'],
    'barrieres marche unique': ['terrible_ten_single_market_barriers'],
    'directive transparence marché unique': ['terrible_ten_single_market_barriers'],
    'dieci terribili': ['terrible_ten_single_market_barriers'],
    'barriere mercato unico': ['terrible_ten_single_market_barriers'],
    'deu terribles': ['terrible_ten_single_market_barriers'],
    'barreres mercat únic': ['terrible_ten_single_market_barriers'],
    'barreres mercat unic': ['terrible_ten_single_market_barriers'],
    'tien verschrikkelijke': ['terrible_ten_single_market_barriers'],
    'belemmeringen interne markt': ['terrible_ten_single_market_barriers'],
    # Europol Regulation revision (Q2 2026 expected, EPRS 29 Apr 2026)
    'europol regulation': ['europol_regulation_revision_2026'],
    'europol revision': ['europol_regulation_revision_2026'],
    'revising europol': ['europol_regulation_revision_2026'],
    'reg 2022/991': ['europol_regulation_revision_2026'],
    '32022r0991': ['europol_regulation_revision_2026'],
    'reg 2016/794': ['europol_regulation_revision_2026'],
    '32016r0794': ['europol_regulation_revision_2026'],
    'eprs_bri(2026)774717': ['europol_regulation_revision_2026'],
    'eisele europol': ['europol_regulation_revision_2026'],
    'europol q2 2026': ['europol_regulation_revision_2026'],
    'europol mandate revision': ['europol_regulation_revision_2026'],
    'reglamento europol': ['europol_regulation_revision_2026'],
    'revisión europol': ['europol_regulation_revision_2026'],
    'revision europol': ['europol_regulation_revision_2026'],
    'règlement europol': ['europol_regulation_revision_2026'],
    'reglement europol': ['europol_regulation_revision_2026'],
    'révision europol': ['europol_regulation_revision_2026'],
    'regolamento europol': ['europol_regulation_revision_2026'],
    'revisione europol': ['europol_regulation_revision_2026'],
    'reglament europol': ['europol_regulation_revision_2026'],
    'europol verordening': ['europol_regulation_revision_2026'],
    'herziening europol': ['europol_regulation_revision_2026'],
    # Circular Economy Act 2026 (DG ENV high-level talks 30 Apr 2026, College 6 May 2026)
    'circular economy act': ['eu_circular_economy_act_2026'],
    'cea 2026': ['eu_circular_economy_act_2026'],
    'roswall circular': ['eu_circular_economy_act_2026'],
    'séjourné circular': ['eu_circular_economy_act_2026'],
    'sejourne circular': ['eu_circular_economy_act_2026'],
    'secondary raw materials': ['eu_circular_economy_act_2026'],
    'srm policy': ['eu_circular_economy_act_2026'],
    'end of waste eu': ['eu_circular_economy_act_2026'],
    'recycled content thresholds': ['eu_circular_economy_act_2026'],
    'ley economía circular': ['eu_circular_economy_act_2026'],
    'ley economia circular': ['eu_circular_economy_act_2026'],
    'materias primas secundarias': ['eu_circular_economy_act_2026'],
    'loi économie circulaire': ['eu_circular_economy_act_2026'],
    'loi economie circulaire': ['eu_circular_economy_act_2026'],
    'matières premières secondaires': ['eu_circular_economy_act_2026'],
    'matieres premieres secondaires': ['eu_circular_economy_act_2026'],
    'legge economia circolare': ['eu_circular_economy_act_2026'],
    'materie prime secondarie': ['eu_circular_economy_act_2026'],
    'llei economia circular': ['eu_circular_economy_act_2026'],
    'matèries primeres secundàries': ['eu_circular_economy_act_2026'],
    'materies primeres secundaries': ['eu_circular_economy_act_2026'],
    'wet circulaire economie': ['eu_circular_economy_act_2026'],
    'secundaire grondstoffen': ['eu_circular_economy_act_2026'],
    # EU Sanctions Implementation Framework (7th Coordinators Forum + 9th high-level mtg 30 Apr 2026)
    'eu sanctions framework': ['eu_sanctions_implementation_framework'],
    'sanctions coordinators forum': ['eu_sanctions_implementation_framework'],
    'sanctions implementation': ['eu_sanctions_implementation_framework'],
    "o'sullivan sanctions": ['eu_sanctions_implementation_framework'],
    'osullivan sanctions': ['eu_sanctions_implementation_framework'],
    'eu sanctions envoy': ['eu_sanctions_implementation_framework'],
    'david o\'sullivan': ['eu_sanctions_implementation_framework'],
    'reg 833/2014': ['eu_sanctions_implementation_framework'],
    '32014r0833': ['eu_sanctions_implementation_framework'],
    'directive 2024/1226': ['eu_sanctions_implementation_framework'],
    '32024l1226': ['eu_sanctions_implementation_framework'],
    'sanctions criminalisation': ['eu_sanctions_implementation_framework'],
    'article 215 tfeu': ['eu_sanctions_implementation_framework'],
    'sanctions circumvention': ['eu_sanctions_implementation_framework'],
    'russia sanctions packages': ['eu_sanctions_implementation_framework'],
    'sanciones ue framework': ['eu_sanctions_implementation_framework'],
    'enviado especial sanciones': ['eu_sanctions_implementation_framework'],
    'foro coordinadores sanciones': ['eu_sanctions_implementation_framework'],
    'sanctions ue cadre': ['eu_sanctions_implementation_framework'],
    'envoyé spécial sanctions': ['eu_sanctions_implementation_framework'],
    'envoye special sanctions': ['eu_sanctions_implementation_framework'],
    'forum coordinateurs sanctions': ['eu_sanctions_implementation_framework'],
    'sanzioni ue quadro': ['eu_sanctions_implementation_framework'],
    'inviato sanzioni': ['eu_sanctions_implementation_framework'],
    'sancions ue': ['eu_sanctions_implementation_framework'],
    'enviat especial sancions': ['eu_sanctions_implementation_framework'],
    'eu sanctiekader': ['eu_sanctions_implementation_framework'],
    'eu sanctiegezant': ['eu_sanctions_implementation_framework'],
    # News updates 28 April 2026 (Tuesday plenary day 2 Strasbourg)
    # New Genomic Techniques (NGT) for plant breeding -- Council adopted 21 April 2026
    'new genomic techniques': ['new_genomic_techniques_plant_breeding'],
    'ngt regulation': ['new_genomic_techniques_plant_breeding'],
    'ngt plants': ['new_genomic_techniques_plant_breeding'],
    'ngt category 1': ['new_genomic_techniques_plant_breeding'],
    'ngt category 2': ['new_genomic_techniques_plant_breeding'],
    'ngt plant breeding': ['new_genomic_techniques_plant_breeding'],
    'targeted mutagenesis': ['new_genomic_techniques_plant_breeding'],
    'cisgenesis': ['new_genomic_techniques_plant_breeding'],
    'precision breeding eu': ['new_genomic_techniques_plant_breeding'],
    'gene-edited plants eu': ['new_genomic_techniques_plant_breeding'],
    'gene edited plants eu': ['new_genomic_techniques_plant_breeding'],
    'com(2023) 411': ['new_genomic_techniques_plant_breeding'],
    '2023/0226(cod)': ['new_genomic_techniques_plant_breeding'],
    'polfjärd ngt': ['new_genomic_techniques_plant_breeding'],
    'polfjard ngt': ['new_genomic_techniques_plant_breeding'],
    'c-528/16': ['new_genomic_techniques_plant_breeding'],
    'confédération paysanne': ['new_genomic_techniques_plant_breeding'],
    'confederation paysanne': ['new_genomic_techniques_plant_breeding'],
    'nouvelles techniques génomiques': ['new_genomic_techniques_plant_breeding'],
    'nouvelles techniques genomiques': ['new_genomic_techniques_plant_breeding'],
    'nuevas técnicas genómicas': ['new_genomic_techniques_plant_breeding'],
    'nuevas tecnicas genomicas': ['new_genomic_techniques_plant_breeding'],
    'noves tècniques genòmiques': ['new_genomic_techniques_plant_breeding'],
    'noves tecniques genomiques': ['new_genomic_techniques_plant_breeding'],
    'nuove tecniche genomiche': ['new_genomic_techniques_plant_breeding'],
    'nieuwe genomische technieken': ['new_genomic_techniques_plant_breeding'],
    # Forest Reproductive Material (new guide)
    'forest reproductive material': ['forest_reproductive_material_regulation'],
    'frm regulation': ['forest_reproductive_material_regulation'],
    'directive 1999/105': ['forest_reproductive_material_regulation'],
    '31999l0105': ['forest_reproductive_material_regulation'],
    'pe787.674': ['forest_reproductive_material_regulation'],
    'dorfmann forest': ['forest_reproductive_material_regulation'],
    'matériel forestier de reproduction': ['forest_reproductive_material_regulation'],
    'material forestal de reproducción': ['forest_reproductive_material_regulation'],
    'material forestal reproductiu': ['forest_reproductive_material_regulation'],
    'materiale forestale di moltiplicazione': ['forest_reproductive_material_regulation'],
    'bosbouwkundig teeltmateriaal': ['forest_reproductive_material_regulation'],
    # EU corporate tax policy 2026 (new guide)
    'eu corporate tax policy': ['eu_corporate_tax_policy_2026'],
    'kollár corporate tax': ['eu_corporate_tax_policy_2026'],
    'kollar corporate tax': ['eu_corporate_tax_policy_2026'],
    'pe781.467': ['eu_corporate_tax_policy_2026'],
    'corporate tax changing environment': ['eu_corporate_tax_policy_2026'],
    'pillar two implementation': ['eu_corporate_tax_policy_2026'],
    'befit proposal': ['eu_corporate_tax_policy_2026'],
    'fiscalité des entreprises ue': ['eu_corporate_tax_policy_2026'],
    'política fiscal corporativa ue': ['eu_corporate_tax_policy_2026'],
    'política fiscal corporativa ue catalan': ['eu_corporate_tax_policy_2026'],
    'tassazione società ue': ['eu_corporate_tax_policy_2026'],
    'eu vennootschapsbelasting': ['eu_corporate_tax_policy_2026'],
    # Welfare of dogs and cats traceability (new guide)
    'welfare dogs and cats': ['welfare_dogs_cats_traceability'],
    'dogs and cats traceability': ['welfare_dogs_cats_traceability'],
    'companion animals traceability': ['welfare_dogs_cats_traceability'],
    'com(2023) 769': ['welfare_dogs_cats_traceability'],
    '2023/0421(cod)': ['welfare_dogs_cats_traceability'],
    'vrecionová': ['welfare_dogs_cats_traceability'],
    'vrecionova': ['welfare_dogs_cats_traceability'],
    'puppy trafficking': ['welfare_dogs_cats_traceability'],
    'pet microchipping eu': ['welfare_dogs_cats_traceability'],
    'illegal puppy trade': ['welfare_dogs_cats_traceability'],
    'bien-être chiens et chats': ['welfare_dogs_cats_traceability'],
    'bienestar perros y gatos': ['welfare_dogs_cats_traceability'],
    'benestar gossos i gats': ['welfare_dogs_cats_traceability'],
    'benessere cani e gatti': ['welfare_dogs_cats_traceability'],
    'welzijn honden en katten': ['welfare_dogs_cats_traceability'],
    # Transboundary water governance (new guide)
    'transboundary water governance': ['transboundary_water_governance'],
    'water bankruptcy': ['transboundary_water_governance'],
    'water extremes': ['transboundary_water_governance'],
    'bridging water extremes': ['transboundary_water_governance'],
    'eprs_bri(2026)785730': ['transboundary_water_governance'],
    'eu water resilience strategy': ['transboundary_water_governance'],
    'com(2025) 280': ['transboundary_water_governance'],
    'unece water convention': ['transboundary_water_governance'],
    'gouvernance eau transfrontalière': ['transboundary_water_governance'],
    'gobernanza agua transfronteriza': ['transboundary_water_governance'],
    'governança aigua transfronterera': ['transboundary_water_governance'],
    'governance acque transfrontaliere': ['transboundary_water_governance'],
    'grensoverschrijdend waterbeheer': ['transboundary_water_governance'],
    # Updates to existing guides (28 April 2026)
    'gpai signatory taskforce': ['ai_act_regulation'],
    'gpai code of practice safety security': ['ai_act_regulation'],
    'third gpai signatory taskforce': ['ai_act_regulation'],
    'google android dma interoperability': ['digital_markets_act'],
    'android dma interoperability': ['digital_markets_act'],
    'b10-0190/2026': ['digital_markets_act'],
    'imco motion dma enforcement': ['digital_markets_act'],
    'cavazzini schwab dma': ['digital_markets_act'],
    # DMA Review Report COM(2026) 178 final + ENFORCEMENT MILESTONES (added 5 May 2026)
    'dma review report': ['digital_markets_act'],
    'dma review com(2026) 178': ['digital_markets_act'],
    'com(2026) 178': ['digital_markets_act'],
    'swd(2026) 123': ['digital_markets_act'],
    'ip/26/914': ['digital_markets_act'],
    'dma fit for purpose': ['digital_markets_act'],
    'digital fitness check': ['digital_markets_act'],
    'dma article 53': ['digital_markets_act'],
    'cloud market investigation dma': ['digital_markets_act'],
    'microsoft azure dma designation': ['digital_markets_act'],
    'aws dma designation': ['digital_markets_act'],
    'dma cloud computing': ['digital_markets_act'],
    'dma ai services scope': ['digital_markets_act'],
    'révision dma': ['digital_markets_act'],
    'revision dma': ['digital_markets_act'],
    'rapport révision dma': ['digital_markets_act'],
    'revisión dma': ['digital_markets_act'],
    'informe revisión dma': ['digital_markets_act'],
    'dma herziening': ['digital_markets_act'],
    'dma überprüfung': ['digital_markets_act'],
    'dma uberprufung': ['digital_markets_act'],
    'revisione dma': ['digital_markets_act'],
    'revisió dma': ['digital_markets_act'],
    # Cybersecurity Act 2 / ENISA revision draft report (added 5 May 2026)
    'cybersecurity act 2': ['cybersecurity_act'],
    'cybersecurity act ii': ['cybersecurity_act'],
    'cybersecurity act revision': ['cybersecurity_act'],
    'enisa revision': ['cybersecurity_act'],
    'enisa mandate review': ['cybersecurity_act'],
    '2026/0011(cod)': ['cybersecurity_act'],
    'com(2026) 11': ['cybersecurity_act'],
    'gregorova draft report': ['cybersecurity_act'],
    'gregorová projet de rapport': ['cybersecurity_act'],
    'projet rapport gregorová': ['cybersecurity_act'],
    'gregorova ponente proyecto': ['cybersecurity_act'],
    'révision loi cybersécurité': ['cybersecurity_act'],
    'revision ley ciberseguridad': ['cybersecurity_act'],
    'cybersecurity act 2 itre': ['cybersecurity_act'],
    'csa 2': ['cybersecurity_act'],
    # Industrial Accelerator Act draft report tabled 5 May (added 5 May 2026)
    'grudler dibrani draft report': ['industrial_accelerator_act'],
    'industrial accelerator joint draft': ['industrial_accelerator_act'],
    'imco inta itre joint report': ['industrial_accelerator_act'],
    '2026/0068 draft report': ['industrial_accelerator_act'],
    'projet rapport accélérateur industriel': ['industrial_accelerator_act'],
    'proyecto informe acelerador industrial': ['industrial_accelerator_act'],
    'progetto relazione acceleratore industriale': ['industrial_accelerator_act'],
    # Digital Networks Act draft report tabled 5 May (added 5 May 2026)
    'kobosko draft report': ['digital_networks_act'],
    'kobosko projet de rapport': ['digital_networks_act'],
    'kobosko proyecto informe': ['digital_networks_act'],
    'kobosko progetto relazione': ['digital_networks_act'],
    '2026/0013 draft report': ['digital_networks_act'],
    'dna draft report itre': ['digital_networks_act'],
    # EU joins Global Coalition on Telecommunications (GCOT) -- NEW guide (added 5 May 2026)
    'global coalition on telecommunications': ['eu_global_coalition_telecommunications'],
    'gcot': ['eu_global_coalition_telecommunications'],
    'eu strategic partner gcot': ['eu_global_coalition_telecommunications'],
    'eu joins gcot': ['eu_global_coalition_telecommunications'],
    'gcot ottawa': ['eu_global_coalition_telecommunications'],
    'coalition mondiale télécommunications': ['eu_global_coalition_telecommunications'],
    'coalition mondiale telecommunications': ['eu_global_coalition_telecommunications'],
    'coalición mundial telecomunicaciones': ['eu_global_coalition_telecommunications'],
    'coalicion mundial telecomunicaciones': ['eu_global_coalition_telecommunications'],
    'coalizione globale telecomunicazioni': ['eu_global_coalition_telecommunications'],
    'coalitie wereldwijde telecommunicatie': ['eu_global_coalition_telecommunications'],
    '6g supply chain security': ['eu_global_coalition_telecommunications', 'digital_networks_act'],
    # EU4Health 2027 priorities -- NEW guide (added 5 May 2026)
    'eu4health 2027': ['eu4health_2027_priorities'],
    'eu4health 2027 priorities': ['eu4health_2027_priorities'],
    'eu4health priorities consultation': ['eu4health_2027_priorities'],
    'eu4health work programme 2027': ['eu4health_2027_priorities'],
    'htacg flash report': ['eu4health_2027_priorities'],
    'health technology assessment coordination group': ['eu4health_2027_priorities'],
    'eu4health prioridades 2027': ['eu4health_2027_priorities'],
    'eu4health priorités 2027': ['eu4health_2027_priorities'],
    'eu4health priorita 2027': ['eu4health_2027_priorities'],
    'eu4health prioriteiten 2027': ['eu4health_2027_priorities'],
    # Cohesion Mid-Term Review re-surface (added 5 May 2026)
    'mid-term review cohesion': ['cohesion_policy_midterm_review'],
    'cohesion mtr results': ['cohesion_policy_midterm_review'],
    'résultats révision mi-parcours cohésion': ['cohesion_policy_midterm_review'],
    'resultados revisión intermedia cohesión': ['cohesion_policy_midterm_review'],
    'risultati revisione intermedia coesione': ['cohesion_policy_midterm_review'],
    # Roswall keynote IFAT Munich + TUM Munich (added 5 May 2026)
    'roswall ifat munich': ['eu_circular_economy_act_2026'],
    'roswall tum munich': ['eu_circular_economy_act_2026'],
    'ifat munich 2026': ['eu_circular_economy_act_2026'],
    'tum europe-week 2026': ['eu_circular_economy_act_2026'],
    'council recommendation euro area economic policy': ['eu_budget_emu_law'],
    'c_202602434': ['eu_budget_emu_law'],
    'recommandation politique économique zone euro': ['eu_budget_emu_law'],
    'recomendación política económica zona euro': ['eu_budget_emu_law'],
    'raccomandazione politica economica area euro': ['eu_budget_emu_law'],
    '2025/2247(bui)': ['eu_budget_emu_law'],
    'ep estimates revenue 2027': ['eu_budget_emu_law'],
    'ai data centres in space': ['ai_act_regulation', 'apply_ai_strategy_public_sector'],
    'orbital data centres': ['ai_act_regulation', 'apply_ai_strategy_public_sector'],
    'stoa 774746': ['ai_act_regulation', 'apply_ai_strategy_public_sector'],
    'stoa 774725': ['better_regulation_enforcement_communication', 'apply_ai_strategy_public_sector'],
    'etools regulatory simplification': ['better_regulation_enforcement_communication'],
    # Politico AI & Tech Week 2026 (Brussels, 5-7 May 2026) -- speakers + event triggers (added 30 April 2026)
    'politico ai & tech week': ['politico_ai_tech_week_2026'],
    'politico ai tech week': ['politico_ai_tech_week_2026'],
    'politico ai & tech summit': ['politico_ai_tech_week_2026'],
    'politico ai tech summit': ['politico_ai_tech_week_2026'],
    'politico ai & tech week 2026': ['politico_ai_tech_week_2026'],
    'politico tech summit brussels': ['politico_ai_tech_week_2026'],
    'ai & tech week brussels': ['politico_ai_tech_week_2026'],
    'ai tech week brussels': ['politico_ai_tech_week_2026'],
    'politico europe ai summit': ['politico_ai_tech_week_2026'],
    'sommet ia tech politico': ['politico_ai_tech_week_2026'],
    'cumbre ia tech politico': ['politico_ai_tech_week_2026'],
    'summit ia tech politico': ['politico_ai_tech_week_2026'],
    'ai-tech-week-2026': ['politico_ai_tech_week_2026'],
    # Commission speakers
    'renate nikolay': ['politico_ai_tech_week_2026', 'dsa_enforcement'],
    'nikolay dg cnect': ['politico_ai_tech_week_2026', 'dsa_enforcement'],
    'nikolay deputy director general': ['politico_ai_tech_week_2026', 'dsa_enforcement'],
    'cnect deputy dg': ['politico_ai_tech_week_2026', 'dsa_enforcement'],
    'ekaterina zaharieva': ['politico_ai_tech_week_2026', 'fp10_ecf_competitiveness', '28th_regime_innovation_act'],
    'commissioner zaharieva': ['politico_ai_tech_week_2026', 'fp10_ecf_competitiveness'],
    'startups research innovation commissioner': ['politico_ai_tech_week_2026', 'fp10_ecf_competitiveness'],
    'thibaut kleiner': ['politico_ai_tech_week_2026', 'digital_networks_act'],
    'kleiner future networks': ['politico_ai_tech_week_2026', 'digital_networks_act'],
    'cnect future networks director': ['politico_ai_tech_week_2026', 'digital_networks_act'],
    'kilian gross': ['politico_ai_tech_week_2026', 'ai_act_regulation', 'apply_ai_strategy_public_sector'],
    'gross enabling emerging tech': ['politico_ai_tech_week_2026', 'ai_act_regulation'],
    'cnect enabling emerging': ['politico_ai_tech_week_2026', 'ai_act_regulation'],
    'bjorn juretzki': ['politico_ai_tech_week_2026', 'digital_omnibus_package'],
    'björn juretzki': ['politico_ai_tech_week_2026', 'digital_omnibus_package'],
    'juretzki data policy': ['politico_ai_tech_week_2026', 'digital_omnibus_package'],
    'cnect data policy unit': ['politico_ai_tech_week_2026', 'digital_omnibus_package'],
    # MEP speakers
    'christel schaldemose': ['politico_ai_tech_week_2026', 'dsa_enforcement'],
    'schaldemose dsa': ['politico_ai_tech_week_2026', 'dsa_enforcement'],
    'ep vice-president schaldemose': ['politico_ai_tech_week_2026', 'dsa_enforcement'],
    'schaldemose digital transformation': ['politico_ai_tech_week_2026', 'dsa_enforcement'],
    'eva maydell': ['politico_ai_tech_week_2026', 'ai_act_regulation', 'digital_networks_act'],
    'maydell mep': ['politico_ai_tech_week_2026', 'ai_act_regulation'],
    'maydell ai act shadow': ['politico_ai_tech_week_2026', 'ai_act_regulation'],
    'bart groothuis': ['politico_ai_tech_week_2026', 'cybersecurity_act'],
    'groothuis nis2': ['politico_ai_tech_week_2026', 'cybersecurity_act'],
    'groothuis cybersecurity': ['politico_ai_tech_week_2026', 'cybersecurity_act'],
    'marketa gregorova': ['politico_ai_tech_week_2026', 'cybersecurity_act', 'csam_regulation_online'],
    'markéta gregorová': ['politico_ai_tech_week_2026', 'cybersecurity_act'],
    'gregorova cybersecurity act': ['politico_ai_tech_week_2026', 'cybersecurity_act'],
    'arba kokalari': ['politico_ai_tech_week_2026', 'ai_act_regulation', 'dsa_enforcement'],
    'kokalari mep': ['politico_ai_tech_week_2026', 'ai_act_regulation'],
    # External speakers
    'cristina caffarra': ['politico_ai_tech_week_2026'],
    'eurostack': ['politico_ai_tech_week_2026'],
    'marietje schaake': ['politico_ai_tech_week_2026'],
    'sean perryman': ['politico_ai_tech_week_2026'],
    'audrey plonk oecd': ['politico_ai_tech_week_2026'],
    'daniel privitera kira': ['politico_ai_tech_week_2026'],
    'frank karlitschek nextcloud': ['politico_ai_tech_week_2026'],
    'claudio teixeira beuc': ['politico_ai_tech_week_2026'],
    'cláudio teixeira': ['politico_ai_tech_week_2026'],
    'itxaso dominguez edri': ['politico_ai_tech_week_2026'],
    'itxaso domínguez': ['politico_ai_tech_week_2026'],
    'ricardo gutierrez ejf': ['politico_ai_tech_week_2026'],
    'ricardo gutiérrez efj': ['politico_ai_tech_week_2026'],
    'sonia livingstone lse': ['politico_ai_tech_week_2026'],
    'maya noel france digitale': ['politico_ai_tech_week_2026'],
    'maya noël': ['politico_ai_tech_week_2026'],
    'cieltje van achter flemish': ['politico_ai_tech_week_2026'],
    'nicholas banasevic microsoft': ['politico_ai_tech_week_2026'],
    # EU Merger Guidelines 2026 (public consultation draft, 30 April 2026)
    'eu merger guidelines': ['eu_merger_guidelines_2026', 'competition_law_enforcement'],
    'eu merger guidelines 2026': ['eu_merger_guidelines_2026'],
    'new eu merger guidelines': ['eu_merger_guidelines_2026'],
    'new merger guidelines': ['eu_merger_guidelines_2026'],
    'merger guidelines revision': ['eu_merger_guidelines_2026'],
    'commission merger guidelines draft': ['eu_merger_guidelines_2026'],
    'eu merger control reform': ['eu_merger_guidelines_2026'],
    'merger guidelines public consultation': ['eu_merger_guidelines_2026'],
    'merger guidelines draft 2026': ['eu_merger_guidelines_2026'],
    'lignes directrices concentrations': ['eu_merger_guidelines_2026'],
    'directrices concentraciones ue': ['eu_merger_guidelines_2026'],
    'orientacions concentracions ue': ['eu_merger_guidelines_2026'],
    'linee guida concentrazioni ue': ['eu_merger_guidelines_2026'],
    'richtsnoeren concentraties': ['eu_merger_guidelines_2026'],
    'horizontal merger guidelines 2024': ['eu_merger_guidelines_2026'],
    'non-horizontal merger guidelines 2008': ['eu_merger_guidelines_2026'],
    'siec test': ['eu_merger_guidelines_2026', 'competition_law_enforcement'],
    'significant impediment to effective competition': ['eu_merger_guidelines_2026'],
    'eumr article 2': ['eu_merger_guidelines_2026'],
    'eumr article 21': ['eu_merger_guidelines_2026'],
    'eumr article 21(4)': ['eu_merger_guidelines_2026'],
    'article 21 eumr legitimate interests': ['eu_merger_guidelines_2026'],
    'innovation shield': ['eu_merger_guidelines_2026'],
    'killer acquisition shield': ['eu_merger_guidelines_2026'],
    'reverse killer acquisition': ['eu_merger_guidelines_2026'],
    'failing firm doctrine': ['eu_merger_guidelines_2026'],
    'failing division': ['eu_merger_guidelines_2026'],
    'loss of head-to-head competition': ['eu_merger_guidelines_2026'],
    'loss of innovation competition': ['eu_merger_guidelines_2026'],
    'loss of investment expansion competition': ['eu_merger_guidelines_2026'],
    'loss of potential competition': ['eu_merger_guidelines_2026'],
    'foreclosure merger guidelines': ['eu_merger_guidelines_2026'],
    'entrenchment dominant position': ['eu_merger_guidelines_2026'],
    'merger coordination effects': ['eu_merger_guidelines_2026'],
    'merger efficiencies guidelines': ['eu_merger_guidelines_2026'],
    'dynamic efficiencies merger': ['eu_merger_guidelines_2026'],
    'dynamic competitive potential': ['eu_merger_guidelines_2026'],
    'innovation space merger': ['eu_merger_guidelines_2026'],
    'merger counterfactual': ['eu_merger_guidelines_2026'],
    'startup merger control': ['eu_merger_guidelines_2026', '28th_regime_innovation_act'],
    'small innovative company merger': ['eu_merger_guidelines_2026'],
    'media plurality merger review': ['eu_merger_guidelines_2026', 'eu_media_landscape'],
    'prudential rules merger': ['eu_merger_guidelines_2026', 'banking_union_reform'],
    'public security merger article 21': ['eu_merger_guidelines_2026'],
    'one-stop-shop merger': ['eu_merger_guidelines_2026'],
    'siec test merger': ['eu_merger_guidelines_2026'],
    'ck telecoms judgment': ['eu_merger_guidelines_2026', 'competition_law_enforcement'],
    'brasserie nationale merger': ['eu_merger_guidelines_2026'],
    'dow dupont merger': ['eu_merger_guidelines_2026'],
    'bayer monsanto merger': ['eu_merger_guidelines_2026'],
    'pfizer seagen merger': ['eu_merger_guidelines_2026'],
    'microsoft linkedin merger': ['eu_merger_guidelines_2026'],
    'arcelormittal ilva merger': ['eu_merger_guidelines_2026'],
    'lufthansa austrian merger failing firm': ['eu_merger_guidelines_2026'],
    'vig aegon cee article 21': ['eu_merger_guidelines_2026'],
    'unicredit banco bpm merger': ['eu_merger_guidelines_2026'],
    'defence readiness merger': ['eu_merger_guidelines_2026', 'eu_defence_procurement'],
    'resilience supply chain merger': ['eu_merger_guidelines_2026'],
    'scale-enhancing merger': ['eu_merger_guidelines_2026'],
    'celex 32004r0139': ['eu_merger_guidelines_2026', 'competition_law_enforcement'],
    'regulation 139/2004': ['eu_merger_guidelines_2026', 'competition_law_enforcement'],
    'eumr regulation': ['eu_merger_guidelines_2026', 'competition_law_enforcement'],
    '2025/2262(reg)': ['afco_institutional_framework_review'],
    '2025/2263(ini)': ['afco_institutional_framework_review'],
    '2026/2012(ini)': ['afco_institutional_framework_review'],
    '2026/2013(ini)': ['afco_institutional_framework_review'],
    'rule 135 amendments': ['afco_institutional_framework_review'],
    'icc ukraine consent vote': ['international_claims_commission_ukraine'],
    'iccu consent vote': ['international_claims_commission_ukraine'],
    'pe786.697': ['international_claims_commission_ukraine'],
    'gahler ukraine report': ['international_claims_commission_ukraine'],
    'cohesion policy mtr results': ['cohesion_policy_audit', 'cohesion_policy_midterm_review'],
    'cohesion mid-term review results': ['cohesion_policy_audit', 'cohesion_policy_midterm_review'],
    'kadis ocean diplomacy': ['eu_fisheries_control'],
    'ocean diplomacy fisheries competitiveness': ['eu_fisheries_control'],
    'eessc my voice my choice': ['consent_based_rape_definition'],
    'safe and accessible abortion eessc': ['consent_based_rape_definition'],
    'consent-based rape vrecionova': ['consent_based_rape_definition'],
    'incir scheuring-wielgus': ['consent_based_rape_definition'],
    'tran mff transport investing': ['mff_2028_2034'],
    'casp_stu(2026)783532': ['mff_2028_2034'],
    'eprs_ata(2026)785729': ['mff_2028_2034'],
    'pe786.987': ['mff_2028_2034'],
    'pe786.988': ['mff_2028_2034'],
    # AI agents under EU law (new 20 April 2026 from arXiv 2604.04604v1)
    'ai agents compliance': ['ai_agents_compliance_architecture_eu'],
    'ai agents eu law': ['ai_agents_compliance_architecture_eu'],
    'agentic systems': ['ai_agents_compliance_architecture_eu'],
    'autonomous ai agent': ['ai_agents_compliance_architecture_eu'],
    'llm tool calling': ['ai_agents_compliance_architecture_eu'],
    'behavioural drift': ['ai_agents_compliance_architecture_eu'],
    'behavioral drift': ['ai_agents_compliance_architecture_eu'],
    'article 50 transparency': ['ai_agents_compliance_architecture_eu'],
    'article 14 oversight': ['ai_agents_compliance_architecture_eu'],
    'article 15(4)': ['ai_agents_compliance_architecture_eu'],
    'agent compliance stack': ['ai_agents_compliance_architecture_eu'],
    '9-instrument compliance': ['ai_agents_compliance_architecture_eu'],
    'nine-instrument compliance': ['ai_agents_compliance_architecture_eu'],
    'annex iii high-risk': ['ai_agents_compliance_architecture_eu'],
    'substantial modification ai': ['ai_agents_compliance_architecture_eu'],
    'non-human identity': ['ai_agents_compliance_architecture_eu'],
    'nannini leon smith': ['ai_agents_compliance_architecture_eu'],
    'arxiv 2604.04604': ['ai_agents_compliance_architecture_eu'],
    # Harmonised standards M/613 + M/606
    'm/613': ['ai_act_harmonised_standards_m613'],
    'm/606': ['ai_act_harmonised_standards_m613'],
    'standardisation request m/613': ['ai_act_harmonised_standards_m613'],
    'standardisation request m/606': ['ai_act_harmonised_standards_m613'],
    'jtc 21': ['ai_act_harmonised_standards_m613'],
    'cen/cenelec jtc 21': ['ai_act_harmonised_standards_m613'],
    'pren 18286': ['ai_act_harmonised_standards_m613'],
    'pren 18228': ['ai_act_harmonised_standards_m613'],
    'pren 18229': ['ai_act_harmonised_standards_m613'],
    'pren 18282': ['ai_act_harmonised_standards_m613'],
    'pren 18283': ['ai_act_harmonised_standards_m613'],
    'pren 18284': ['ai_act_harmonised_standards_m613'],
    'qms for ai': ['ai_act_harmonised_standards_m613'],
    'harmonised standards ai act': ['ai_act_harmonised_standards_m613'],
    'harmonized standards ai act': ['ai_act_harmonised_standards_m613'],
    'presumption of conformity ai': ['ai_act_harmonised_standards_m613'],
    'iso iec jtc 1 sc 42': ['ai_act_harmonised_standards_m613'],
    # News updates 20 April 2026
    'cmdi package': ['banking_union_reform'],
    'crisis management deposit insurance': ['banking_union_reform'],
    'banking resolution 2026': ['banking_union_reform'],
    'regulation 2026/808': ['banking_union_reform'],
    'directive 2026/804': ['banking_union_reform'],
    'directive 2026/806': ['banking_union_reform'],
    'magyar technical meetings': ['hungary_election_2026_magyar'],
    'incoming hungarian government': ['hungary_election_2026_magyar'],
    'druzhba pipeline hungary': ['hungary_election_2026_magyar'],
    'emergency energy plan': ['iran_strait_hormuz_eu_response', 'eu_energy_policy'],
    'commission emergency energy': ['iran_strait_hormuz_eu_response', 'eu_energy_policy'],
    'rfnbo review': ['eu_energy_policy'],
    'directive 2026/805': ['eu_water_legislation'],
    'water framework 2026 amendment': ['eu_water_legislation'],
    'cra delegated regulation': ['cybersecurity_act'],
    'regulation 2026/881': ['cybersecurity_act'],
    'cyber resilience vulnerability handling': ['cybersecurity_act'],
    'afco institutional framework': ['afco_institutional_framework_review'],
    'article 19 teu': ['afco_institutional_framework_review'],
    '2025/2263(ini)': ['afco_institutional_framework_review'],
    '2026/2012(ini)': ['afco_institutional_framework_review'],
    '2026/2013(ini)': ['afco_institutional_framework_review'],
    'airspace block performance': ['aviation_transport_policy'],
    'fab performance plan': ['aviation_transport_policy'],
    'decision 2026/865': ['aviation_transport_policy'],
    'decision 2026/867': ['aviation_transport_policy'],
    'ukraine facility methodology': ['eu_recovery_resilience_facility'],
    'xc02328': ['eu_recovery_resilience_facility'],
    'islands in the eu': ['eu_islands_insular_territories'],
    'insular territories': ['eu_islands_insular_territories'],
    'island regions eu': ['eu_islands_insular_territories'],
    'outermost regions': ['eu_islands_insular_territories'],
    'article 349 tfeu': ['eu_islands_insular_territories'],
    'clean energy for eu islands': ['eu_islands_insular_territories'],
    'eu islands': ['eu_islands_insular_territories'],
    'sicily eu': ['eu_islands_insular_territories'],
    'sardinia eu': ['eu_islands_insular_territories'],
    'corsica': ['eu_islands_insular_territories'],
    'mallorca eu': ['eu_islands_insular_territories'],
    'malta island': ['eu_islands_insular_territories'],
    'canary islands': ['eu_islands_insular_territories'],
    'azores': ['eu_islands_insular_territories'],
    'madeira': ['eu_islands_insular_territories'],
    'reunion eu region': ['eu_islands_insular_territories'],

    # Platform regulation guides (added 19 April 2026 — outreach campaign)
    'discord': ['discord_platform_regulation'],
    'discord inc': ['discord_platform_regulation'],
    'discord eu': ['discord_platform_regulation'],
    'discord regulation': ['discord_platform_regulation'],
    'discord brussels': ['discord_platform_regulation'],
    'discord dsa': ['discord_platform_regulation'],
    'grindr': ['grindr_platform_regulation'],
    'grindr eu': ['grindr_platform_regulation'],
    'grindr regulation': ['grindr_platform_regulation'],
    'grindr gdpr': ['grindr_platform_regulation'],
    'grindr datatilsynet': ['grindr_platform_regulation'],
    'yubo': ['yubo_platform_regulation'],
    'twelve app': ['yubo_platform_regulation'],
    'twelve app sas': ['yubo_platform_regulation'],
    'yubo regulation': ['yubo_platform_regulation'],
    'yubo eu': ['yubo_platform_regulation'],
    'loi studer': ['yubo_platform_regulation'],
    'automattic': ['automattic_platform_regulation'],
    'wordpress.com': ['automattic_platform_regulation'],
    'tumblr': ['automattic_platform_regulation'],
    'woocommerce': ['automattic_platform_regulation'],
    'automattic eu': ['automattic_platform_regulation'],
    'coinbase': ['coinbase_platform_regulation'],
    'coinbase eu': ['coinbase_platform_regulation'],
    'coinbase mica': ['coinbase_platform_regulation'],
    'coinbase ireland': ['coinbase_platform_regulation'],
    'epic games': ['epic_games_platform_regulation'],
    'fortnite': ['epic_games_platform_regulation'],
    'unreal engine': ['epic_games_platform_regulation'],
    'uefn': ['epic_games_platform_regulation'],
    'epic games eu': ['epic_games_platform_regulation'],
    'epic dma': ['epic_games_platform_regulation'],
    'nextdoor': ['nextdoor_platform_regulation'],
    'nextdoor eu': ['nextdoor_platform_regulation'],
    'nextdoor milltown': ['nextdoor_platform_regulation'],
    'roblox': ['roblox_platform_regulation'],
    'roblox corporation': ['roblox_platform_regulation'],
    'roblox eu': ['roblox_platform_regulation'],
    'roblox dsa': ['roblox_platform_regulation'],
    'hadadi': ['roblox_platform_regulation'],

    # EU Automotive Omnibus (new April 2026)
    'eu automotive': ['eu_automotive_omnibus'],
    '2035 ice ban': ['eu_automotive_omnibus'],
    '2035 ban': ['eu_automotive_omnibus'],
    'ice ban dilution': ['eu_automotive_omnibus'],
    'automotive sector eu': ['eu_automotive_omnibus'],
    'car industry eu': ['eu_automotive_omnibus'],
    'automotive competitiveness': ['eu_automotive_omnibus'],
    'co2 cars regulation': ['eu_automotive_omnibus'],
    '2019/631': ['eu_automotive_omnibus'],
    'european cars industry': ['eu_automotive_omnibus'],
    'automotive omnibus': ['eu_automotive_omnibus'],
    'eu automotive omnibus': ['eu_automotive_omnibus'],
    'automotive action plan': ['eu_automotive_omnibus'],
    'automotive industrial action plan': ['eu_automotive_omnibus'],
    'aiap': ['eu_automotive_omnibus'],
    'com(2025)95': ['eu_automotive_omnibus'],
    'co2 standards cars': ['eu_automotive_omnibus'],
    'co2 cars flexibility': ['eu_automotive_omnibus'],
    '2035 ban cars': ['eu_automotive_omnibus'],
    'ice ban 2035': ['eu_automotive_omnibus'],
    'afir charging': ['eu_automotive_omnibus'],
    'type approval vehicles': ['eu_automotive_omnibus'],
    'roadworthiness package': ['eu_automotive_omnibus'],
    '2025/0096': ['eu_automotive_omnibus'],
    'car manufacturers eu': ['eu_automotive_omnibus'],
    'acea': ['eu_automotive_omnibus'],
    'clepa': ['eu_automotive_omnibus'],
    # Film and media financing
    'creative europe film': ['eu_film_media_financing'],
    'creative europe funding': ['eu_film_media_financing'],
    'film funding eu': ['eu_film_media_financing'],
    'cinema funding eu': ['eu_film_media_financing'],
    'audiovisual funding': ['eu_film_media_financing'],
    'film subsidies eu': ['eu_film_media_financing'],
    'film co-production eu': ['eu_film_media_financing'],
    'european film production': ['eu_film_media_financing'],
    'small member states film': ['eu_film_media_financing'],
    'smaller member states film': ['eu_film_media_financing'],
    'luxembourg film': ['eu_film_media_financing'],
    'estonian film': ['eu_film_media_financing'],
    'latvia film': ['eu_film_media_financing'],
    'slovenia film': ['eu_film_media_financing'],
    'malta film': ['eu_film_media_financing'],
    'cyprus film': ['eu_film_media_financing'],
    'independent film producer': ['eu_film_media_financing'],
    'film festivals': ['eu_film_media_financing'],
    'film festival support': ['eu_film_media_financing'],
    'eu film festival': ['eu_film_media_financing'],
    'cinema network europa': ['eu_film_media_financing'],
    'films on the move': ['eu_film_media_financing'],
    'smaller countries film': ['eu_film_media_financing'],
    'low capacity film': ['eu_film_media_financing'],
    'film financing': ['eu_film_media_financing'],
    'eu film financing': ['eu_film_media_financing'],
    'creative europe': ['eu_film_media_financing'],
    'creative europe media': ['eu_film_media_financing'],
    'media strand': ['eu_film_media_financing'],
    'films smaller member states': ['eu_film_media_financing'],
    'european film': ['eu_film_media_financing'],
    'european cinema': ['eu_film_media_financing'],
    'eurimages': ['eu_film_media_financing'],
    'avmsd article 13': ['eu_film_media_financing'],
    'audiovisual media services directive': ['eu_film_media_financing'],
    'slate funding': ['eu_film_media_financing'],
    'europa cinemas': ['eu_film_media_financing'],
    'cult committee': ['eu_film_media_financing'],
    'film festival eu support': ['eu_film_media_financing'],
    'cinema communication state aid': ['eu_film_media_financing'],
    # AML
    'amla crypto': ['eu_anti_money_laundering'],
    'amla supervision': ['eu_anti_money_laundering'],
    'aml crypto': ['eu_anti_money_laundering'],
    'aml supervision eu': ['eu_anti_money_laundering'],
    'crypto firms aml': ['eu_anti_money_laundering'],
    'casp supervision': ['eu_anti_money_laundering'],
    'aml package 2024': ['eu_anti_money_laundering'],
    'money laundering eu': ['eu_anti_money_laundering'],
    'money laundering directive': ['eu_anti_money_laundering'],
    'anti money laundering': ['eu_anti_money_laundering'],
    'anti-money laundering': ['eu_anti_money_laundering'],
    'aml': ['eu_anti_money_laundering'],
    'amla': ['eu_anti_money_laundering'],
    'aml authority': ['eu_anti_money_laundering'],
    'amld6': ['eu_anti_money_laundering'],
    'amlr': ['eu_anti_money_laundering'],
    '6th aml directive': ['eu_anti_money_laundering'],
    '6amld': ['eu_anti_money_laundering'],
    '2024/1624': ['eu_anti_money_laundering'],
    '2024/1620': ['eu_anti_money_laundering'],
    '2024/1640': ['eu_anti_money_laundering'],
    'single rulebook aml': ['eu_anti_money_laundering'],
    'beneficial ownership register': ['eu_anti_money_laundering'],
    'beneficial owner': ['eu_anti_money_laundering'],
    'cash payment limit': ['eu_anti_money_laundering'],
    'fiu financial intelligence unit': ['eu_anti_money_laundering'],
    'fiu.net': ['eu_anti_money_laundering'],
    'bruna szego': ['eu_anti_money_laundering'],
    'casps aml': ['eu_anti_money_laundering'],
    'crypto aml': ['eu_anti_money_laundering'],
    'mica aml': ['eu_anti_money_laundering'],
    'travel rule': ['eu_anti_money_laundering'],
    'football clubs aml': ['eu_anti_money_laundering'],
    'luxury goods aml': ['eu_anti_money_laundering'],
    'golden visas aml': ['eu_anti_money_laundering'],
    'blanchiment argent': ['eu_anti_money_laundering'],
    'blanqueo capitales': ['eu_anti_money_laundering'],
    'blanqueig capitals': ['eu_anti_money_laundering'],
    'antiriciclaggio': ['eu_anti_money_laundering'],
    'witwassen': ['eu_anti_money_laundering'],
    # Recovery and Resilience Facility
    'latvia recovery': ['eu_recovery_resilience_facility'],
    'latvia resilience plan': ['eu_recovery_resilience_facility'],
    'poland recovery': ['eu_recovery_resilience_facility'],
    'italy pnrr status': ['eu_recovery_resilience_facility'],
    'spain plan recuperacion': ['eu_recovery_resilience_facility'],
    'recovery plan status': ['eu_recovery_resilience_facility'],
    'rrp status': ['eu_recovery_resilience_facility'],
    'rrp implementation': ['eu_recovery_resilience_facility'],
    'rrp absorption': ['eu_recovery_resilience_facility'],
    'rrf payment request': ['eu_recovery_resilience_facility'],
    'rrf milestone': ['eu_recovery_resilience_facility'],
    'rrf': ['eu_recovery_resilience_facility'],
    'recovery and resilience facility': ['eu_recovery_resilience_facility'],
    'recovery resilience facility': ['eu_recovery_resilience_facility'],
    'nrrp': ['eu_recovery_resilience_facility'],
    'national recovery and resilience plan': ['eu_recovery_resilience_facility'],
    'national recovery plan': ['eu_recovery_resilience_facility'],
    'rrp': ['eu_recovery_resilience_facility'],
    'nextgenerationeu': ['eu_recovery_resilience_facility'],
    'ngeu': ['eu_recovery_resilience_facility'],
    'next generation eu': ['eu_recovery_resilience_facility'],
    'repowereu chapter': ['eu_recovery_resilience_facility'],
    'repowereu rrf': ['eu_recovery_resilience_facility'],
    '2021/241': ['eu_recovery_resilience_facility'],
    'sg recover': ['eu_recovery_resilience_facility'],
    'rrf scoreboard': ['eu_recovery_resilience_facility'],
    'milestones and targets': ['eu_recovery_resilience_facility'],
    'super milestones': ['eu_recovery_resilience_facility'],
    'dnsh do no significant harm': ['eu_recovery_resilience_facility'],
    'latvia rrp': ['eu_recovery_resilience_facility'],
    'latvia recovery plan': ['eu_recovery_resilience_facility'],
    'poland rrp': ['eu_recovery_resilience_facility'],
    'poland recovery plan': ['eu_recovery_resilience_facility'],
    'italy pnrr': ['eu_recovery_resilience_facility'],
    'spain recovery plan': ['eu_recovery_resilience_facility'],
    'hungary rrp': ['eu_recovery_resilience_facility', 'hungary_election_2026_magyar'],
    'france rrp': ['eu_recovery_resilience_facility'],
    'germany rrp': ['eu_recovery_resilience_facility'],
    # Additional EPRS/news triggers
    'post 2027 mff': ['mff_2028_2034'],
    'post-2027 mff': ['mff_2028_2034'],
    'post 2027 budget': ['mff_2028_2034'],
    'post-2027 budget': ['mff_2028_2034'],
    'mff background': ['mff_2028_2034'],
    'mff post-2027': ['mff_2028_2034'],
    'next mff': ['mff_2028_2034'],
    'new mff': ['mff_2028_2034'],
    'dark web markets': ['cybersecurity_act'],
    'darknet markets': ['cybersecurity_act'],
    'operation spectr': ['cybersecurity_act'],
    'operation cronos': ['cybersecurity_act'],
    'dark web law enforcement': ['cybersecurity_act'],
    'tor i2p': ['cybersecurity_act'],
    'dark web': ['cybersecurity_act'],
    'darkweb': ['cybersecurity_act'],
    'tor network': ['cybersecurity_act'],
    'ransomware': ['cybersecurity_act'],
    'ransomware resilience': ['cybersecurity_act'],
    'santa marta': ['european_climate_law'],
    'transitioning away fossil fuels': ['european_climate_law'],
    'fossil fuel phase-down': ['european_climate_law'],
    'cop28 follow-up': ['european_climate_law'],
    '28th tax regime': ['28th_regime_innovation_act'],
    '28th regime tax': ['28th_regime_innovation_act'],
    'optional tax regime': ['28th_regime_innovation_act'],
    'eu us trade 908 billion': ['eu_us_trade_deal_2026'],
    'eu us trade statistics': ['eu_us_trade_deal_2026'],
    'eu us trade data': ['eu_us_trade_deal_2026'],
    'eu us trade 2025': ['eu_us_trade_deal_2026'],
    'eu us goods trade': ['eu_us_trade_deal_2026'],
    'eu us services trade': ['eu_us_trade_deal_2026'],
    'eu us fdi': ['eu_us_trade_deal_2026'],
    'eu us investment': ['eu_us_trade_deal_2026'],
    'eu us investment relations': ['eu_us_trade_deal_2026'],
    'transatlantic trade stats': ['eu_us_trade_deal_2026'],
    'transatlantic economy': ['eu_us_trade_deal_2026'],
    'eu trade surplus us': ['eu_us_trade_deal_2026'],
    'eu services deficit us': ['eu_us_trade_deal_2026'],
    'germany us exports': ['eu_us_trade_deal_2026'],
    'ireland us services': ['eu_us_trade_deal_2026'],
    'eprs 785679': ['eu_us_trade_deal_2026'],
    'pe 785.679': ['eu_us_trade_deal_2026'],
    'eprs_ata(2026)785679': ['eu_us_trade_deal_2026'],
    'organic chemicals exports us': ['eu_us_trade_deal_2026'],
    'eu pharma exports us': ['eu_us_trade_deal_2026'],
    'eu auto exports us': ['eu_us_trade_deal_2026'],
    'eu oil imports us': ['eu_us_trade_deal_2026'],
    'eu us fdi stocks': ['eu_us_trade_deal_2026'],
    'trade to gdp ratio eu us': ['eu_us_trade_deal_2026'],
    'eu surplus us goods': ['eu_us_trade_deal_2026'],
    'eu us goods surplus': ['eu_us_trade_deal_2026'],
    'eu us trade balance': ['eu_us_trade_deal_2026'],
    'eu trade partner us': ['eu_us_trade_deal_2026'],
    'us main trading partner': ['eu_us_trade_deal_2026'],
    'member state exports to us': ['eu_us_trade_deal_2026'],
    'member state trade with us': ['eu_us_trade_deal_2026'],
    'eu us services exports': ['eu_us_trade_deal_2026'],
    'eu us chemicals trade': ['eu_us_trade_deal_2026'],
    'eu us pharma trade': ['eu_us_trade_deal_2026'],
    'eu surplus': ['eu_us_trade_deal_2026'],
    'eu trade surplus': ['eu_us_trade_deal_2026'],
    'eu trade balance': ['eu_us_trade_deal_2026'],
    'trade balance united states': ['eu_us_trade_deal_2026'],
    'eu exports to us': ['eu_us_trade_deal_2026'],
    'eu exports to united states': ['eu_us_trade_deal_2026'],
    'eu imports from us': ['eu_us_trade_deal_2026'],
    'eu imports from united states': ['eu_us_trade_deal_2026'],
    'exports to united states': ['eu_us_trade_deal_2026'],
    'organic chemicals eu exports': ['eu_us_trade_deal_2026'],
    'chemicals exports us': ['eu_us_trade_deal_2026'],
    'us trade relations': ['eu_us_trade_deal_2026'],
    'eu us trade relations': ['eu_us_trade_deal_2026'],
    'exports services to us': ['eu_us_trade_deal_2026'],
    'exports services to united states': ['eu_us_trade_deal_2026'],
    'services to us': ['eu_us_trade_deal_2026'],
    'services to united states': ['eu_us_trade_deal_2026'],
    'country exports most services': ['eu_us_trade_deal_2026'],
    'organic chemicals exports': ['eu_us_trade_deal_2026'],
    'chemicals exports growth': ['eu_us_trade_deal_2026'],
    'goods trade 908': ['eu_us_trade_deal_2026'],
    'services trade 827': ['eu_us_trade_deal_2026'],
    'eu us trade infographic': ['eu_us_trade_deal_2026'],
    'patient centred health': ['pharma_sector_regulatory_landscape'],
    'patient-centred health research': ['pharma_sector_regulatory_landscape'],
    'generational change agriculture': ['common_agricultural_policy'],
    'young farmers': ['common_agricultural_policy'],
    'young farmer payment': ['common_agricultural_policy'],
    'countemissionseu': ['aviation_transport_policy'],
    'count emissions eu': ['aviation_transport_policy'],
    'transport emissions measurement': ['aviation_transport_policy'],
    'iso 14083': ['aviation_transport_policy'],
    'chocolate cartel': ['competition_law_enforcement'],
    'anthony whelan': ['competition_law_enforcement'],
    'whelan': ['competition_law_enforcement'],
    'whelan appointment': ['competition_law_enforcement'],
    'whelan dg comp': ['competition_law_enforcement'],
    'whelan competition': ['competition_law_enforcement'],
    'new dg comp': ['competition_law_enforcement'],
    'dg competition director general': ['competition_law_enforcement'],
    'dg comp director general': ['competition_law_enforcement'],
    'head of dg comp': ['competition_law_enforcement'],
    'competition directorate general': ['competition_law_enforcement'],
    'olivier guersent successor': ['competition_law_enforcement'],
    'merger guidelines revision': ['competition_law_enforcement'],
    'honda astemo': ['competition_law_enforcement'],
    'honda / astemo': ['competition_law_enforcement'],
    'valea rockaway': ['competition_law_enforcement'],
    'rockaway media': ['competition_law_enforcement'],
    'm.12286': ['competition_law_enforcement'],
    'm.12295': ['competition_law_enforcement'],
    # Sudan humanitarian crisis
    'sudan': ['sudan_humanitarian_crisis'],
    'sudan war': ['sudan_humanitarian_crisis'],
    'sudan humanitarian': ['sudan_humanitarian_crisis'],
    'sudan crisis': ['sudan_humanitarian_crisis'],
    'sudan conflict': ['sudan_humanitarian_crisis'],
    'rapid support forces': ['sudan_humanitarian_crisis'],
    'rsf sudan': ['sudan_humanitarian_crisis'],
    'sudanese armed forces': ['sudan_humanitarian_crisis'],
    'saf sudan': ['sudan_humanitarian_crisis'],
    'burhan': ['sudan_humanitarian_crisis'],
    'hemedti': ['sudan_humanitarian_crisis'],
    'darfur': ['sudan_humanitarian_crisis'],
    'sudan famine': ['sudan_humanitarian_crisis'],
    'soudan': ['sudan_humanitarian_crisis'],
    'sudan sanctions': ['sudan_humanitarian_crisis'],
    # EU Disability Rights post-2024
    'disability rights': ['eu_disability_rights_post2024'],
    'disability strategy': ['eu_disability_rights_post2024'],
    'disability rights post-2024': ['eu_disability_rights_post2024'],
    'persons with disabilities': ['eu_disability_rights_post2024'],
    'eu disability card': ['eu_disability_rights_post2024'],
    'eu parking card': ['eu_disability_rights_post2024'],
    'european accessibility act': ['eu_disability_rights_post2024'],
    'accessibility act': ['eu_disability_rights_post2024'],
    'union of equality disability': ['eu_disability_rights_post2024'],
    'un crpd': ['eu_disability_rights_post2024'],
    'crpd': ['eu_disability_rights_post2024'],
    'disability rights 2030': ['eu_disability_rights_post2024'],
    'droits des personnes handicapees': ['eu_disability_rights_post2024'],
    'persones amb discapacitat': ['eu_disability_rights_post2024'],
    'personas con discapacidad': ['eu_disability_rights_post2024'],
    '2025/2057': ['eu_disability_rights_post2024'],
    # European Defence Union
    'european defence union': ['european_defence_union'],
    'common european defence union': ['european_defence_union'],
    'defence union': ['european_defence_union'],
    'common defence policy': ['european_defence_union'],
    'article 42 teu': ['european_defence_union'],
    'pesco': ['european_defence_union'],
    'permanent structured cooperation': ['european_defence_union'],
    'strategic compass': ['european_defence_union'],
    'safe instrument': ['european_defence_union'],
    'rearm europe': ['european_defence_union'],
    'kubilius defence': ['european_defence_union'],
    'defence commissioner': ['european_defence_union'],
    'edip': ['european_defence_union'],
    'european defence industry programme': ['european_defence_union'],
    'white paper european defence': ['european_defence_union'],
    '2025/2212': ['european_defence_union'],
    # Electricity supplier switching and ETS (route to energy)
    '24 hour switching': ['eu_energy_policy'],
    '24-hour switching': ['eu_energy_policy'],
    'electricity supplier switching': ['eu_energy_policy'],
    'supplier switching': ['eu_energy_policy'],
    'ets update 2026': ['eu_energy_policy'],
    'ets aviation maritime': ['eu_energy_policy'],
    'rfnbo': ['eu_energy_policy'],
    'rfnbo delegated act': ['eu_energy_policy'],
    'renewable hydrogen production criteria': ['eu_energy_policy'],
    'renewable hydrogen rules': ['eu_energy_policy'],
    'green hydrogen criteria': ['eu_energy_policy'],
    'green hydrogen rules eu': ['eu_energy_policy'],
    'hydrogen delegated act': ['eu_energy_policy'],
    '2023/1184': ['eu_energy_policy'],
    'accelerateeu': ['eu_energy_policy'],
    'accelerate eu': ['eu_energy_policy'],
    'accelerate eu communication': ['eu_energy_policy'],
    'energy crisis communication': ['eu_energy_policy'],
    'hydrogen europe lobby': ['eu_energy_policy'],
    'additionality hydrogen': ['eu_energy_policy'],
    'temporal correlation hydrogen': ['eu_energy_policy'],
    'age verification app': ['csam_regulation_online'],
    'eu age verification app details': ['csam_regulation_online'],
    'von der leyen age verification': ['csam_regulation_online'],
    'virkkunen age verification': ['csam_regulation_online'],
    'children safety online panel': ['csam_regulation_online'],
    # PSLF Just Transition (route to cohesion)
    'pslf': ['cohesion_policy_audit'],
    'public sector loan facility': ['cohesion_policy_audit'],
    'just transition pslf': ['cohesion_policy_audit'],
    # European biotech act (guide already has biotech triggers, add EPRS-specific)
    'european biotech act': ['biotech_act'],
    '2025/0406': ['biotech_act'],
    # CSAM LIBE draft report
    '2025/0429': ['csam_regulation_online'],
    'sippel csam': ['csam_regulation_online'],
    'csam derogation extension': ['csam_regulation_online'],
    # Trade defence PETI unfair competition
    'unfair competition third countries': ['eu_trade_defence'],
    '2025/2955': ['eu_trade_defence'],
    'petitions 0072/2025': ['eu_trade_defence'],
    # MFF 2028-2034 IIA
    '2025/2159': ['mff_2028_2034'],
    'iia budgetary discipline': ['mff_2028_2034'],
    'interinstitutional agreement budgetary': ['mff_2028_2034'],
    # MFF Council state of play
    'negotiating box': ['mff_2028_2034'],
    'mff negotiating box': ['mff_2028_2034'],
    'danish presidency mff': ['mff_2028_2034'],
    'mff danish presidency': ['mff_2028_2034'],
    'general affairs council mff': ['mff_2028_2034'],
    'mff council position': ['mff_2028_2034'],
    'mff agreement 2026': ['mff_2028_2034'],
    'mff adoption 2027': ['mff_2028_2034'],
    'long-term budget': ['mff_2028_2034'],
    'long term budget': ['mff_2028_2034'],
    'eu long-term budget': ['mff_2028_2034'],
    # CSDDD Omnibus I scope reduction
    'csddd omnibus': ['corporate_sustainability_due_diligence'],
    'omnibus csddd': ['corporate_sustainability_due_diligence'],
    'csddd scope reduction': ['corporate_sustainability_due_diligence'],
    'csddd 974': ['corporate_sustainability_due_diligence'],
    'somo datahub': ['corporate_sustainability_due_diligence'],
    'andreas rasche': ['corporate_sustainability_due_diligence'],
    'csddd review 2031': ['corporate_sustainability_due_diligence'],
    'csddd review clause': ['corporate_sustainability_due_diligence'],
    'omnibus i review clause': ['corporate_sustainability_due_diligence'],
    'due diligence 974 groups': ['corporate_sustainability_due_diligence'],
    # CBAM downstream goods extension
    'cbam downstream': ['cbam_downstream_goods_extension'],
    'cbam extension': ['cbam_downstream_goods_extension'],
    'cbam scope extension': ['cbam_downstream_goods_extension'],
    'cbam downstream goods': ['cbam_downstream_goods_extension'],
    'cbam anti-circumvention': ['cbam_downstream_goods_extension'],
    'carbon border adjustment downstream': ['cbam_downstream_goods_extension'],
    'chahim cbam': ['cbam_downstream_goods_extension'],
    'mohammed chahim': ['cbam_downstream_goods_extension'],
    '2025/0419': ['cbam_downstream_goods_extension'],
    'com(2025) 989': ['cbam_downstream_goods_extension'],
    'com(2025)0989': ['cbam_downstream_goods_extension'],
    'pe786.835': ['cbam_downstream_goods_extension'],
    'pe786835': ['cbam_downstream_goods_extension'],
    'cbam article 27a': ['cbam_downstream_goods_extension'],
    'cbam international carbon credits': ['cbam_downstream_goods_extension'],
    'cbam ldc': ['cbam_downstream_goods_extension'],
    'pre-consumer scrap': ['cbam_downstream_goods_extension'],
    # Varhelyi (Hungary's Commissioner)
    'varhelyi': ['hungary_election_2026_magyar', 'biotech_act'],
    'oliver varhelyi': ['hungary_election_2026_magyar', 'biotech_act'],
    'oliver varhelyi commissioner': ['hungary_election_2026_magyar'],
    'hungarys commissioner': ['hungary_election_2026_magyar'],
    "hungary's commissioner": ['hungary_election_2026_magyar'],
    'orbans man in brussels': ['hungary_election_2026_magyar'],
    "orban's man in brussels": ['hungary_election_2026_magyar'],
    'hungarian commissioner': ['hungary_election_2026_magyar'],
    'commissioner varhelyi': ['hungary_election_2026_magyar', 'biotech_act'],
    'varhelyi sante': ['hungary_election_2026_magyar', 'biotech_act'],
    'varhelyi health': ['hungary_election_2026_magyar', 'biotech_act'],
    'varhelyi removal': ['hungary_election_2026_magyar'],
    'remove commissioner': ['hungary_election_2026_magyar'],
    'eu merger guidelines': ['competition_law_enforcement'],
    'ribera whelan': ['competition_law_enforcement'],
    'big tech competition eu': ['competition_law_enforcement'],
    # Apply AI Strategy / public sector
    'apply ai strategy': ['apply_ai_strategy_public_sector', 'ai_continent_action_plan'],
    'apply ai': ['apply_ai_strategy_public_sector', 'ai_continent_action_plan'],
    'com(2025)723': ['apply_ai_strategy_public_sector'],
    'com 2025 723': ['apply_ai_strategy_public_sector'],
    'ai public sector': ['apply_ai_strategy_public_sector'],
    'ai public administration': ['apply_ai_strategy_public_sector'],
    'ai public administrations': ['apply_ai_strategy_public_sector'],
    'ai in public sector': ['apply_ai_strategy_public_sector'],
    'ai in government': ['apply_ai_strategy_public_sector'],
    'ai government adoption': ['apply_ai_strategy_public_sector'],
    'govtech eu': ['apply_ai_strategy_public_sector'],
    'eu govtech': ['apply_ai_strategy_public_sector'],
    'govtech market': ['apply_ai_strategy_public_sector'],
    'govtech4all': ['apply_ai_strategy_public_sector'],
    'public sector tech watch': ['apply_ai_strategy_public_sector'],
    'pstw': ['apply_ai_strategy_public_sector'],
    'public sector tech': ['apply_ai_strategy_public_sector'],
    'jrc143539': ['apply_ai_strategy_public_sector', 'ai_continent_action_plan'],
    'jrc 143539': ['apply_ai_strategy_public_sector'],
    'jrc apply ai': ['apply_ai_strategy_public_sector'],
    'pair pathway': ['apply_ai_strategy_public_sector'],
    'public sector ai interoperability': ['apply_ai_strategy_public_sector'],
    'genai4eu': ['apply_ai_strategy_public_sector', 'ai_continent_action_plan'],
    'genai for public administrations': ['apply_ai_strategy_public_sector'],
    'ai on demand platform': ['apply_ai_strategy_public_sector'],
    'ai observatory': ['apply_ai_strategy_public_sector'],
    'apply ai alliance': ['apply_ai_strategy_public_sector'],
    'lifesaver estonia': ['apply_ai_strategy_public_sector'],
    'genai4lex': ['apply_ai_strategy_public_sector'],
    'destination earth ai': ['apply_ai_strategy_public_sector'],
    'ai literacy public sector': ['apply_ai_strategy_public_sector'],
    'interoperable europe framework ai': ['apply_ai_strategy_public_sector'],
    'fundamental rights impact assessment': ['apply_ai_strategy_public_sector'],
    'fria ai act': ['apply_ai_strategy_public_sector'],
    'annex iii ai act': ['apply_ai_strategy_public_sector'],
    'ai act public administration': ['apply_ai_strategy_public_sector'],
    'european digital innovation hubs ai': ['apply_ai_strategy_public_sector'],
    'edih ai': ['apply_ai_strategy_public_sector'],
    'leontina sandu': ['apply_ai_strategy_public_sector'],
    'francesca campolongo': ['apply_ai_strategy_public_sector'],
    'lucilla sioli': ['apply_ai_strategy_public_sector'],
    'ai adoption public administrations': ['apply_ai_strategy_public_sector'],
    'digital-2025-ai-08': ['apply_ai_strategy_public_sector'],
    # DSA minors guidelines April 2026 explainer
    'dsa minors guidelines': ['csam_regulation_online', 'dsa_enforcement'],
    'dsa protection of minors': ['csam_regulation_online', 'dsa_enforcement'],
    'protection of minors online': ['csam_regulation_online'],
    'kids online safety eu': ['csam_regulation_online'],
    'teens online safety eu': ['csam_regulation_online'],
    'age assurance platform': ['csam_regulation_online'],
    'age estimation eu': ['csam_regulation_online'],
    'age verification app': ['csam_regulation_online'],
    'eu age verification app': ['csam_regulation_online'],
    'eu digital identity wallet age': ['csam_regulation_online'],
    'digital age of majority': ['csam_regulation_online'],
    'loot boxes minors': ['csam_regulation_online'],
    'infinite scroll minors': ['csam_regulation_online'],
    'addictive design minors': ['csam_regulation_online'],
    'digital services coordinator': ['dsa_enforcement'],
    'trusted flaggers dsa': ['dsa_enforcement'],
    'cyberbullying eu action plan': ['csam_regulation_online'],
    'tiktok minors eu': ['csam_regulation_online'],
    'instagram minors eu': ['csam_regulation_online'],
    'roblox minors eu': ['csam_regulation_online'],
    'discord minors eu': ['csam_regulation_online'],
    'tiktok teens dsa': ['csam_regulation_online'],
    'tiktok minors dsa': ['csam_regulation_online'],
    'tiktok keep teens safe': ['csam_regulation_online'],
    'keep teens safe': ['csam_regulation_online'],
    'teens safe under dsa': ['csam_regulation_online'],
    'teens safe online': ['csam_regulation_online'],
    'kids safe under dsa': ['csam_regulation_online'],
    'kids safe online eu': ['csam_regulation_online'],
    'children safe online eu': ['csam_regulation_online'],
    'instagram teens dsa': ['csam_regulation_online'],
    'snapchat minors dsa': ['csam_regulation_online'],
    'roblox dsa': ['csam_regulation_online'],
    'roblox minors dsa': ['csam_regulation_online'],
    'roblox minors rules': ['csam_regulation_online'],
    'minecraft dsa': ['csam_regulation_online'],
    'twitch dsa minors': ['csam_regulation_online'],
    'youtube dsa minors': ['csam_regulation_online'],
    'digital age verification': ['csam_regulation_online', 'dsa_enforcement'],
    'verify age online eu': ['csam_regulation_online', 'dsa_enforcement'],
    'eu age app': ['csam_regulation_online'],
    'age check app eu': ['csam_regulation_online'],
    'verificacion edad digital': ['csam_regulation_online'],
    'verificacio edat digital': ['csam_regulation_online'],
    'verificazione eta digitale': ['csam_regulation_online'],
    'verification age numerique': ['csam_regulation_online'],
    'leeftijdsverificatie eu': ['csam_regulation_online'],
    'minors platform dsa rules': ['csam_regulation_online'],
    'chocolate antitrust': ['competition_law_enforcement'],
    'confectionery cartel': ['competition_law_enforcement'],
    'dg comp inspection': ['competition_law_enforcement'],
    'mid term review cohesion': ['cohesion_policy_audit'],
    'mid-term review cohesion': ['cohesion_policy_audit'],
    'cohesion mid-term review': ['cohesion_policy_audit'],
    'pslf': ['cohesion_policy_audit'],
    'public sector loan facility': ['cohesion_policy_audit'],
    'just transition mechanism pslf': ['cohesion_policy_audit'],
    'oilseed rape ms11': ['eu_food_safety_pesticides'],
    'gmo oilseed rape': ['eu_food_safety_pesticides'],
    'ms11 gmo': ['eu_food_safety_pesticides'],
    'common european defence union': ['eu_defence_procurement'],
    'ep proxy voting': ['eu_equality_antidiscrimination'],
    'proxy voting meps': ['eu_equality_antidiscrimination'],
    'proxy voting for pregnant meps': ['eu_equality_antidiscrimination'],
    'proxy voting pregnant': ['eu_equality_antidiscrimination'],
    'pregnant meps': ['eu_equality_antidiscrimination'],
    'mep maternity': ['eu_equality_antidiscrimination'],
    'proxy vote plenary': ['eu_equality_antidiscrimination'],
    'maternity meps': ['eu_equality_antidiscrimination'],
    'electoral act amendment': ['eu_equality_antidiscrimination'],
    'radioactive waste directive': ['smr_strategy_nuclear'],
    'radioactive shipments': ['smr_strategy_nuclear'],
    'temporary crisis framework': ['smr_strategy_nuclear'],
    'state aid temporary crisis': ['smr_strategy_nuclear'],
    'dg agri trade surplus': ['common_agricultural_policy'],
    'eu agri food trade surplus': ['common_agricultural_policy'],
    'eu pharma trade surplus': ['pharma_sector_regulatory_landscape'],
    'pharma trade surplus 221': ['pharma_sector_regulatory_landscape'],
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
    'industrial accelerator rapporteur': ['industrial_accelerator_act'],
    'industrial accelerator itre': ['industrial_accelerator_act'],
    'adnan dibrani': ['industrial_accelerator_act'],
    'dibrani imco': ['industrial_accelerator_act'],
    'industrial accelerator preparatory phase': ['industrial_accelerator_act'],
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
    'recovery and resilience': ['eu_recovery_resilience_facility', 'european_semester_communication', 'eu_budget_emu_law'],
    'recovery and resilience plan': ['eu_recovery_resilience_facility'],
    'recovery and resilience facility': ['eu_recovery_resilience_facility'],
    'recovery and resilience regulation': ['eu_recovery_resilience_facility'],
    'latvia recovery and resilience': ['eu_recovery_resilience_facility'],
    'poland recovery and resilience': ['eu_recovery_resilience_facility'],
    'italy recovery and resilience': ['eu_recovery_resilience_facility'],
    'spain recovery and resilience': ['eu_recovery_resilience_facility'],
    'france recovery and resilience': ['eu_recovery_resilience_facility'],
    'germany recovery and resilience': ['eu_recovery_resilience_facility'],
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
    'meta whatsapp ai': ['digital_markets_act'],
    'third-party ai assistant whatsapp': ['digital_markets_act'],
    'whatsapp ai assistant': ['digital_markets_act'],
    'dma interim measures': ['digital_markets_act'],
    'dma interim measure': ['digital_markets_act'],
    'meta dma whatsapp': ['digital_markets_act'],
    'meta pay-to-play ai': ['digital_markets_act'],
    'whatsapp interoperability ai': ['digital_markets_act'],
    'meta charge sheet dma': ['digital_markets_act'],

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
    'remit ii': ['eu_energy_policy'],
    'energy market integrity': ['eu_energy_policy'],
    'pci list': ['eu_energy_policy'],
    'pci pmi': ['eu_energy_policy'],
    'cross-border energy projects': ['eu_energy_policy'],
    'gas coordination group': ['eu_energy_policy'],
    'decarbonisation fund': ['eu_energy_policy'],
    'temporary decarbonisation fund': ['eu_energy_policy'],
    'ev charging rules': ['eu_energy_policy'],
    'hydrogen refilling': ['eu_energy_policy'],
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
    'epbd recast': ['eu_energy_policy'],
    'epbd delegated act': ['eu_energy_policy'],
    'epbd annex iii': ['eu_energy_policy'],
    'energy performance of buildings directive': ['eu_energy_policy'],
    'energy performance buildings annex iii': ['eu_energy_policy'],
    'directive 2024/1275': ['eu_energy_policy'],
    '2024/1275': ['eu_energy_policy'],
    'delegated regulation 2026/52': ['eu_energy_policy'],
    '2026/52': ['eu_energy_policy'],
    'cost-optimal level buildings': ['eu_energy_policy'],
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
    'steel safeguards': ['eu_trade_defence'],
    'eu steel measure': ['eu_trade_defence'],
    'new steel measure': ['eu_trade_defence'],
    'steel overcapacity': ['eu_trade_defence'],
    'global steel overcapacity': ['eu_trade_defence'],
    'steel agreement 2026': ['eu_trade_defence'],
    'tariff rate quota steel': ['eu_trade_defence'],
    'trq steel': ['eu_trade_defence'],
    'crm aggregation platform': ['industrial_accelerator_act'],
    'critical raw materials platform': ['industrial_accelerator_act'],
    'critical raw materials demand aggregation': ['industrial_accelerator_act'],
    'aggregateeu raw materials': ['industrial_accelerator_act'],
    'raw materials joint purchasing': ['industrial_accelerator_act'],
    'price undertaking': ['eu_trade_defence'],
    'regulation 2016/1036': ['eu_trade_defence'],
    'regulation 2016/1037': ['eu_trade_defence'],
    'tron database': ['eu_trade_defence'],
    'terephthalic acid': ['eu_trade_defence'],
    'terephthalic': ['eu_trade_defence'],
    'anti-dumping korea': ['eu_trade_defence'],
    'anti-dumping united states': ['eu_trade_defence'],
    '2026/801': ['eu_trade_defence'],
    '2026/846': ['eu_trade_defence'],
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
    'product safety': ['dsa_enforcement', 'eu_product_safety_consumer'],
    'general product safety': ['dsa_enforcement', 'eu_product_safety_consumer'],
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
    'ndici': ['eu_funding_ipa_enlargement', 'global_gateway_strategy'],
    'global europe': ['eu_funding_ipa_enlargement', 'global_gateway_strategy'],
    'ndici amendment': ['global_gateway_strategy'],
    'ndici efficiency': ['global_gateway_strategy'],
    'regulation 2026/995': ['global_gateway_strategy'],
    '2026/995': ['global_gateway_strategy'],
    'external action guarantee': ['global_gateway_strategy'],
    'external action guarantee efficiency': ['global_gateway_strategy'],
    'eag efficiency': ['global_gateway_strategy'],
    'efsd plus': ['global_gateway_strategy'],
    'efsd+ guarantee': ['global_gateway_strategy'],
    '2021/947 amendment': ['global_gateway_strategy'],
    'eu armenia summit': ['eu_funding_ipa_enlargement'],
    'eu-armenia summit': ['eu_funding_ipa_enlargement'],
    'yerevan summit': ['eu_funding_ipa_enlargement'],
    'cepa armenia': ['eu_funding_ipa_enlargement'],
    'armenia resilience and growth plan': ['eu_funding_ipa_enlargement'],
    'armenia 270 million': ['eu_funding_ipa_enlargement'],
    'eu-armenia comprehensive partnership': ['eu_funding_ipa_enlargement'],
    'rrf closure': ['eu_recovery_resilience_facility'],
    'rrf closure guidelines': ['eu_recovery_resilience_facility'],
    'recovery resilience facility closure': ['eu_recovery_resilience_facility'],
    'final phase rrf': ['eu_recovery_resilience_facility'],
    'rrp closure': ['eu_recovery_resilience_facility'],
    'c_202602614': ['eu_recovery_resilience_facility'],
    'rrf 31 december 2026': ['eu_recovery_resilience_facility'],
    'arachne rrf': ['eu_recovery_resilience_facility'],
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
    'rule of law conditionality': ['eu_equality_antidiscrimination'],
    'conditionality regulation': ['eu_equality_antidiscrimination'],
    'article 7': ['eu_equality_antidiscrimination'],
    'hungary': ['hungary_election_2026_magyar', 'eu_equality_antidiscrimination'],
    'hungary eu': ['hungary_election_2026_magyar', 'eu_equality_antidiscrimination'],
    'orban': ['hungary_election_2026_magyar', 'eu_equality_antidiscrimination'],
    'orbán': ['hungary_election_2026_magyar', 'eu_equality_antidiscrimination'],
    'viktor orban': ['hungary_election_2026_magyar'],
    'fidesz': ['hungary_election_2026_magyar', 'eu_equality_antidiscrimination'],
    'peter magyar': ['hungary_election_2026_magyar'],
    'péter magyar': ['hungary_election_2026_magyar'],
    'magyar': ['hungary_election_2026_magyar'],
    'tisza party': ['hungary_election_2026_magyar'],
    'tisza': ['hungary_election_2026_magyar'],
    'hungary election': ['hungary_election_2026_magyar'],
    'hungary 2026 election': ['hungary_election_2026_magyar'],
    'hungary frozen funds': ['hungary_election_2026_magyar'],
    'hungary rrf': ['hungary_election_2026_magyar'],
    'hungary cohesion': ['hungary_election_2026_magyar'],
    'hungary brussels reset': ['hungary_election_2026_magyar'],
    'hungary grand bargain': ['hungary_election_2026_magyar'],
    'sovereignty protection act': ['hungary_election_2026_magyar'],
    'hongrie': ['hungary_election_2026_magyar', 'eu_equality_antidiscrimination'],
    'hongrie élection': ['hungary_election_2026_magyar'],
    'hungria': ['hungary_election_2026_magyar', 'eu_equality_antidiscrimination'],
    'hungria elecciones': ['hungary_election_2026_magyar'],
    'ungheria': ['hungary_election_2026_magyar', 'eu_equality_antidiscrimination'],
    'hongarije': ['hungary_election_2026_magyar', 'eu_equality_antidiscrimination'],
    'hongria': ['hungary_election_2026_magyar'],
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
    'rene repasi': ['28th_regime_innovation_act'],
    'mcgrath jurI presentation': ['28th_regime_innovation_act'],
    'eu inc juri presentation': ['28th_regime_innovation_act'],
    'commissioner mcgrath 28th regime': ['28th_regime_innovation_act'],
    'eu inc 4 may 2026': ['28th_regime_innovation_act'],
    'juri 4 may eu inc': ['28th_regime_innovation_act'],
    'axel voss eu inc': ['28th_regime_innovation_act'],
    'arash saeidi': ['28th_regime_innovation_act'],
    '2026/0074': ['28th_regime_innovation_act'],
    '2026/0074(cod)': ['28th_regime_innovation_act'],
    'réné repasi': ['28th_regime_innovation_act'],
    'repasi eu inc': ['28th_regime_innovation_act'],
    'repasi rapporteur': ['28th_regime_innovation_act'],
    'a10-0269/2025': ['28th_regime_innovation_act'],
    'a10-0269': ['28th_regime_innovation_act'],
    '2025/2079(inl)': ['28th_regime_innovation_act'],
    '2025/2079': ['28th_regime_innovation_act'],
    'societas europaea unificata': ['28th_regime_innovation_act'],
    's.eu regime': ['28th_regime_innovation_act'],
    'juri 28th regime': ['28th_regime_innovation_act'],
    'eu inc rapporteur': ['28th_regime_innovation_act'],
    'eu inc juri': ['28th_regime_innovation_act'],
    'rene.repasi@europarl.europa.eu': ['28th_regime_innovation_act'],
    'erasmus school of law': ['28th_regime_innovation_act'],
    'repasi linkedin': ['28th_regime_innovation_act'],
    'eu inc end of 2026': ['28th_regime_innovation_act'],
    'three institutions eu inc': ['28th_regime_innovation_act'],
    'eu inc trilogue': ['28th_regime_innovation_act'],
    'axel voss eu inc': ['28th_regime_innovation_act'],
    'axel voss 28th regime': ['28th_regime_innovation_act'],
    'voss shadow rapporteur': ['28th_regime_innovation_act'],
    'arash saeidi': ['28th_regime_innovation_act'],
    'saeidi eu inc': ['28th_regime_innovation_act'],
    'la france insoumise eu inc': ['28th_regime_innovation_act'],
    'the left eu inc': ['28th_regime_innovation_act'],
    'shadow rapporteurs eu inc': ['28th_regime_innovation_act'],
    'euinc.me': ['28th_regime_innovation_act'],
    'delors centre eu inc': ['28th_regime_innovation_act'],
    'one europe one market paper': ['28th_regime_innovation_act'],
    'jacques delors eu inc': ['28th_regime_innovation_act'],
    'central digital register eu inc': ['28th_regime_innovation_act'],
    'workers participation eu inc': ['28th_regime_innovation_act'],
    'juri assignment 31 march': ['28th_regime_innovation_act'],
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
    'amld': ['eu_anti_money_laundering', 'eu_financial_regulation_procurement'],
    'anti-money laundering': ['eu_financial_regulation_procurement'],
    'aml package': ['eu_anti_money_laundering', 'eu_financial_regulation_procurement'],
    'amla': ['eu_anti_money_laundering', 'eu_financial_regulation_procurement'],
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
    'eu defence funding': ['eu_defence_procurement'],
    'eu defence budget': ['eu_defence_procurement'],
    'eu defence spending': ['eu_defence_procurement'],
    'defence spending': ['eu_defence_procurement'],
    'defence budget': ['eu_defence_procurement'],
    'how much does the eu spend on defence': ['eu_defence_procurement'],
    'eu military spending': ['eu_defence_procurement'],
    'defense funding': ['eu_defence_procurement'],
    'defense budget': ['eu_defence_procurement'],
    'defense spending': ['eu_defence_procurement'],
    'finançament defensa': ['eu_defence_procurement'],
    'defensa europea': ['eu_defence_procurement', 'safe_rearm_europe'],
    'defensa ue': ['eu_defence_procurement', 'safe_rearm_europe'],
    'financiacion defensa': ['eu_defence_procurement'],
    'financement defense': ['eu_defence_procurement'],
    'finanziamento difesa': ['eu_defence_procurement'],
    'defensiebudget': ['eu_defence_procurement'],
    'pressupost defensa': ['eu_defence_procurement'],
    '131 billion defence': ['eu_defence_procurement', 'mff_2028_2034'],
    'edirpa': ['eu_defence_procurement'],
    'asap ammunition': ['eu_defence_procurement'],
    'military mobility': ['eu_defence_procurement'],
    'european peace facility epf': ['eu_defence_procurement'],
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
    'product safety': ['dg_grow_databases', 'eu_product_safety_consumer'],
    'market surveillance': ['dg_grow_databases', 'eu_product_safety_consumer'],
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
    'dsa minors': ['csam_regulation_online', 'dsa_enforcement'],
    'dsa guidelines minors': ['csam_regulation_online', 'dsa_enforcement'],
    'dsa guidelines on protection of minors': ['csam_regulation_online'],
    'protection minors online platforms': ['csam_regulation_online'],
    'dsa kids teens': ['csam_regulation_online'],
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
    'addictive design': ['digital_fairness_act', 'csam_regulation_online'],
    'addictive design online': ['digital_fairness_act', 'csam_regulation_online'],
    'addictive design minors infinite scroll': ['csam_regulation_online'],
    'infinite scroll autoplay minors': ['csam_regulation_online'],
    'addictive design for minors': ['csam_regulation_online'],
    'addictive features minors': ['csam_regulation_online'],
    'addictive design disabled minors': ['csam_regulation_online'],
    'features disabled for minors': ['csam_regulation_online'],
    'dark patterns regulation': ['digital_fairness_act'],
    'dark patterns eu': ['digital_fairness_act'],
    'influencer marketing regulation': ['digital_fairness_act'],
    'influencer marketing eu': ['digital_fairness_act'],
    'influencer regulation': ['digital_fairness_act'],
    'kidfluencer': ['digital_fairness_act'],
    'kidfluencers': ['digital_fairness_act'],
    'loot boxes regulation': ['digital_fairness_act'],
    'loot boxes': ['csam_regulation_online', 'digital_fairness_act'],
    'loot boxes minors allowed': ['csam_regulation_online'],
    'loot box ban children': ['csam_regulation_online'],
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
    'serbia funding': ['eu_funding_ipa_enlargement'],
    'funding to serbia': ['eu_funding_ipa_enlargement'],
    'funding serbia': ['eu_funding_ipa_enlargement'],
    'serbia': ['eu_funding_ipa_enlargement'],
    'montenegro': ['eu_funding_ipa_enlargement'],
    'serbia democracy': ['eu_funding_ipa_enlargement'],
    'serbia rule of law': ['eu_funding_ipa_enlargement'],
    'montenegro security': ['eu_funding_ipa_enlargement'],
    'montenegro accession': ['eu_funding_ipa_enlargement'],
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
    'regulatory sandbox': ['28th_regime_innovation_act', 'pharma_sector_regulatory_landscape'],
    'regulatory sandboxes': ['28th_regime_innovation_act', 'pharma_sector_regulatory_landscape'],
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
    'dna rapporteur': ['digital_networks_act'],
    'michal kobosko': ['digital_networks_act'],
    'kobosko': ['digital_networks_act'],
    'kobosko renew poland': ['digital_networks_act'],
    'pilar del castillo vera dna': ['digital_networks_act'],
    'matthias ecke dna': ['digital_networks_act'],
    'damian boeselager dna': ['digital_networks_act'],
    'jussi saramo dna': ['digital_networks_act'],
    'ana vasconcelos imco': ['digital_networks_act'],
    'dna 27 april': ['digital_networks_act'],
    'dna committee referral': ['digital_networks_act'],
    '2026/0013': ['digital_networks_act'],
    '2026/0013(cod)': ['digital_networks_act'],
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

    # EU-Mercosur Interim Trade Agreement (provisional application from 1 May 2026)
    'mercosur': ['eu_mercosur_trade_agreement', 'eu_trade_policy'],
    'eu-mercosur': ['eu_mercosur_trade_agreement', 'eu_trade_policy'],
    'eu mercosur': ['eu_mercosur_trade_agreement', 'eu_trade_policy'],
    'mercosur interim trade agreement': ['eu_mercosur_trade_agreement'],
    'mercosur ita': ['eu_mercosur_trade_agreement'],
    'mercosur empa': ['eu_mercosur_trade_agreement'],
    'mercosur partnership agreement': ['eu_mercosur_trade_agreement'],
    'mercosur 1 may': ['eu_mercosur_trade_agreement'],
    'mercosur provisional application': ['eu_mercosur_trade_agreement'],
    '22026a00184': ['eu_mercosur_trade_agreement'],
    'argentina brazil paraguay uruguay': ['eu_mercosur_trade_agreement'],
    'mercosur safeguard': ['eu_mercosur_trade_agreement', 'eu_trade_defence'],
    '32026r0687': ['eu_mercosur_trade_agreement', 'eu_trade_defence'],
    'reglamento mercosur': ['eu_mercosur_trade_agreement'],
    'accord mercosur': ['eu_mercosur_trade_agreement'],
    'accordo mercosur': ['eu_mercosur_trade_agreement'],
    'mercosur akkoord': ['eu_mercosur_trade_agreement'],
    'acord mercosur': ['eu_mercosur_trade_agreement'],

    # One Europe One Market Roadmap (Cyprus EUCO 23-24 April 2026, end-2027 target)
    'one europe one market': ['single_market_one_europe_roadmap'],
    'one europe, one market': ['single_market_one_europe_roadmap'],
    'single market roadmap': ['single_market_one_europe_roadmap'],
    'single market deepening': ['single_market_one_europe_roadmap'],
    'cyprus euco roadmap': ['single_market_one_europe_roadmap'],
    'metsola christodoulides von der leyen': ['single_market_one_europe_roadmap'],
    'feuille de route marche unique': ['single_market_one_europe_roadmap'],
    'mercato unico europeo roadmap': ['single_market_one_europe_roadmap'],
    'eengemaakte markt routekaart': ['single_market_one_europe_roadmap'],
    'mercat unic europeu': ['single_market_one_europe_roadmap'],
    'una europa un mercado': ['single_market_one_europe_roadmap'],

    # EU-US Critical Minerals MoU (24 April 2026)
    'eu us critical minerals': ['eu_trade_policy'],
    'critical minerals mou': ['eu_trade_policy'],
    'sefcovic critical minerals': ['eu_trade_policy'],
    'memorandum of understanding critical minerals': ['eu_trade_policy'],
    'ip 26 862': ['eu_trade_policy'],

    # Latin America EU Relations
    'latin america eu': ['latin_america_eu_relations'],
    'eu latin america': ['latin_america_eu_relations'],
    'celac eu': ['latin_america_eu_relations'],
    'eu celac': ['latin_america_eu_relations'],
    'colombia 2026 elections': ['latin_america_eu_relations'],
    'colombia presidential elections': ['latin_america_eu_relations'],
    'colombia ahead of 2026': ['latin_america_eu_relations'],
    'eu colombia': ['latin_america_eu_relations'],
    'andean community': ['latin_america_eu_relations'],
    'cariforum': ['latin_america_eu_relations'],
    'eu chile': ['latin_america_eu_relations'],
    'eu mexico global agreement': ['latin_america_eu_relations', 'eu_trade_policy'],
    'eu cuba': ['latin_america_eu_relations'],
    'eu venezuela': ['latin_america_eu_relations'],
    'lithium triangle': ['latin_america_eu_relations'],
    'amerique latine ue': ['latin_america_eu_relations'],
    'america latina ue': ['latin_america_eu_relations'],
    'amerika llatina ue': ['latin_america_eu_relations'],

    # European Education Area 2021-2030
    'european education area': ['european_education_area_2021_2030'],
    'european education area 2030': ['european_education_area_2021_2030'],
    'eea strategic framework': ['european_education_area_2021_2030'],
    'erasmus plus': ['european_education_area_2021_2030'],
    'erasmus+': ['european_education_area_2021_2030'],
    'european universities initiative': ['european_education_area_2021_2030'],
    'bologna process': ['european_education_area_2021_2030'],
    'digcomp': ['european_education_area_2021_2030'],
    'greencomp': ['european_education_area_2021_2030'],
    'european education summit': ['european_education_area_2021_2030'],
    'eu education benchmarks 2030': ['european_education_area_2021_2030'],
    'espace europeen education': ['european_education_area_2021_2030'],
    'espacio europeo educacion': ['european_education_area_2021_2030'],
    'spazio europeo istruzione': ['european_education_area_2021_2030'],
    'europese onderwijsruimte': ['european_education_area_2021_2030'],
    'espai europeu educacio': ['european_education_area_2021_2030'],

    # EU Aviation and Aeronautics Strategy (consultation from 24 April 2026)
    'eu aviation strategy': ['aviation_transport_policy'],
    'aviation and aeronautics strategy': ['aviation_transport_policy'],
    'azea roadmap': ['aviation_transport_policy'],
    'estrategia aviacion ue': ['aviation_transport_policy'],
    'strategie aviation ue': ['aviation_transport_policy'],

    # Article 19 TEU AFCO institutional framework
    'article 19 teu': ['afco_institutional_framework_review'],
    'article 19 ue': ['afco_institutional_framework_review'],
    'institutional framework union law': ['afco_institutional_framework_review'],
    '2025/2263(ini)': ['afco_institutional_framework_review'],
    'pe770.052': ['afco_institutional_framework_review'],
    'afco draft report 2025/2263': ['afco_institutional_framework_review'],
    'national authorities application union law': ['afco_institutional_framework_review'],
    'sven simon afco': ['afco_institutional_framework_review'],

    # Proxy voting in plenary (2025/2195(INL), Wed 29 vote)
    'proxy voting plenary': ['afco_institutional_framework_review'],
    'proxy voting pregnancy': ['afco_institutional_framework_review'],
    '2025/2195(inl)': ['afco_institutional_framework_review'],
    'european electoral act amendment proxy': ['afco_institutional_framework_review'],
    'vote par procuration plenary': ['afco_institutional_framework_review'],

    # Chornobyl 40 years anniversary
    'chornobyl 40 years': ['smr_strategy_nuclear'],
    'chernobyl 40 years': ['smr_strategy_nuclear'],
    'safeguarding chornobyl': ['smr_strategy_nuclear'],
    'chornobyl recovery nuclear safety': ['smr_strategy_nuclear'],
    'dombrovskis chornobyl': ['smr_strategy_nuclear'],

    # Global Green Bond Initiative Fund (24 April 2026, EUR 20 billion)
    'global green bond initiative': ['global_gateway_strategy'],
    'global green bond fund': ['global_gateway_strategy'],
    'eu 20 billion sustainable infrastructure': ['global_gateway_strategy'],

    # SCCS opinions (CBD + silver in cosmetics, 24 April 2026)
    'sccs cbd cosmetics': ['pharma_sector_regulatory_landscape'],
    'cannabidiol cosmetics': ['pharma_sector_regulatory_landscape'],
    'sccs silver cosmetics': ['pharma_sector_regulatory_landscape'],
    'silver cosmetic products': ['pharma_sector_regulatory_landscape'],
    'cosmetics regulation annex': ['pharma_sector_regulatory_landscape'],

    # LVMH leather deforestation pushback
    'lvmh leather deforestation': ['eu_deforestation_regulation'],
    'luxury fashion eudr': ['eu_deforestation_regulation'],

    # SEDE 8 April minutes / EU defence union 27 April update
    'sede 8 april 2026': ['european_defence_union'],
    'cj57_pv 2026 04 08': ['european_defence_union'],
    'kubilius eastern border': ['european_defence_union'],

    # Wed 29 plenary EU Middle East Crisis Response
    'eu middle east crisis response': ['iran_strait_hormuz_eu_response'],
    'wednesday 29 april middle east debate': ['iran_strait_hormuz_eu_response'],

    # Tuesday 28 plenary consent-based rape press conference
    'consent based rape press conference 28 april': ['consent_based_rape_definition'],
    '20260424ipr41929': ['consent_based_rape_definition'],

    # MFF Metsola statement
    'metsola europe cannot face new era old budget': ['mff_2028_2034'],
    '20260424ipr41902': ['mff_2028_2034'],

    # ERDF management EPRS briefing
    'erdf 2004 accession states': ['cohesion_policy_midterm_review'],
    'management control structures erdf': ['cohesion_policy_midterm_review'],

    # EU-Andorra Association Agreement (procedures 2024/0101(NLE) + 2024/0102(NLE), still preparatory phase as of April 2026)
    'andorra': ['eu_andorra_association_agreement'],
    'principality of andorra': ['eu_andorra_association_agreement'],
    'principat d andorra': ['eu_andorra_association_agreement'],
    'principat andorra': ['eu_andorra_association_agreement'],
    'principado de andorra': ['eu_andorra_association_agreement'],
    'principaute d andorre': ['eu_andorra_association_agreement'],
    'andorra eu': ['eu_andorra_association_agreement'],
    'eu andorra': ['eu_andorra_association_agreement'],
    'andorra ue': ['eu_andorra_association_agreement'],
    'andorra unio europea': ['eu_andorra_association_agreement'],
    'andorra association agreement': ['eu_andorra_association_agreement'],
    'eu andorra association': ['eu_andorra_association_agreement'],
    'acord associacio andorra': ['eu_andorra_association_agreement'],
    'acord d associacio': ['eu_andorra_association_agreement'],
    'acuerdo de asociacion andorra': ['eu_andorra_association_agreement'],
    'accord d association andorre': ['eu_andorra_association_agreement'],
    'accordo di associazione andorra': ['eu_andorra_association_agreement'],
    'andorra san marino': ['eu_andorra_association_agreement'],
    'san marino andorra': ['eu_andorra_association_agreement'],
    'micro state agreement': ['eu_andorra_association_agreement'],
    'micro states eu': ['eu_andorra_association_agreement'],
    'micro-state association': ['eu_andorra_association_agreement'],
    'small state association': ['eu_andorra_association_agreement'],
    '2024/0101(nle)': ['eu_andorra_association_agreement'],
    '2024/0102(nle)': ['eu_andorra_association_agreement'],
    '2024/0101': ['eu_andorra_association_agreement'],
    '2024/0102': ['eu_andorra_association_agreement'],
    'com(2024) 189': ['eu_andorra_association_agreement'],
    'com(2024) 191': ['eu_andorra_association_agreement'],
    'com(2024)189': ['eu_andorra_association_agreement'],
    'com(2024)191': ['eu_andorra_association_agreement'],
    '52024pc0189': ['eu_andorra_association_agreement'],
    '52024pc0191': ['eu_andorra_association_agreement'],
    'pe 766.263': ['eu_andorra_association_agreement'],
    'pe770.052': ['eu_andorra_association_agreement'],
    'zovko andorra': ['eu_andorra_association_agreement'],
    'ballarin cereza': ['eu_andorra_association_agreement'],
    'cap de govern andorra': ['eu_andorra_association_agreement'],
    'xavier espot': ['eu_andorra_association_agreement'],
    'andorraue': ['eu_andorra_association_agreement'],
    'co-principality': ['eu_andorra_association_agreement'],
    'coprincipality': ['eu_andorra_association_agreement'],
    'bishop of urgell': ['eu_andorra_association_agreement'],
    'sammarinese': ['eu_andorra_association_agreement'],
    'andorran government': ['eu_andorra_association_agreement'],
    'monaco withdrew': ['eu_andorra_association_agreement'],
    'monaco eu agreement': ['eu_andorra_association_agreement'],
    'efta working party': ['eu_andorra_association_agreement'],
    'article 8 teu': ['eu_andorra_association_agreement'],
    'declaration 3 article 8': ['eu_andorra_association_agreement'],
    'declaration no 3 on article 8': ['eu_andorra_association_agreement'],

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
    'photonic chips': ['competition_law_enforcement'],
    'italian photonic': ['competition_law_enforcement'],
    'photonic chips state aid': ['competition_law_enforcement'],
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

    # Pharma Sector: Full Regulatory Landscape (environmental, trade, procurement, compounding, sandbox)
    'pharma regulatory landscape': ['pharma_sector_regulatory_landscape'],
    'pharmaceutical sector': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_framework'],
    'pharma sector': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_framework'],
    'efpia': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_framework'],
    'pharmaceutical industry': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_framework'],
    'pharma industry': ['pharma_sector_regulatory_landscape'],
    'pharma compounding': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_legislation_reform'],
    'compounding': ['pharma_sector_regulatory_landscape'],
    'pharmacy compounding': ['pharma_sector_regulatory_landscape'],
    'pharmaceutical compounding': ['pharma_sector_regulatory_landscape'],
    'pharma sandbox': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_legislation_reform'],
    'regulatory sandbox pharma': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_legislation_reform'],
    'regulatory sandbox pharmaceutical': ['pharma_sector_regulatory_landscape'],
    'pharma procurement': ['pharma_sector_regulatory_landscape'],
    'hospital procurement': ['pharma_sector_regulatory_landscape'],
    'medicine procurement': ['pharma_sector_regulatory_landscape'],
    'pharmaceutical procurement': ['pharma_sector_regulatory_landscape'],
    'joint procurement medicines': ['pharma_sector_regulatory_landscape'],
    'pharma trade': ['pharma_sector_regulatory_landscape'],
    'pharmaceutical trade': ['pharma_sector_regulatory_landscape'],
    'us eu pharma': ['pharma_sector_regulatory_landscape'],
    'fda ema': ['pharma_sector_regulatory_landscape'],
    'gmp mutual recognition': ['pharma_sector_regulatory_landscape'],
    'pharma tariffs': ['pharma_sector_regulatory_landscape'],
    'pharma fta': ['pharma_sector_regulatory_landscape'],
    'international cooperation pharma': ['pharma_sector_regulatory_landscape'],
    'international cooperation pharmaceuticals': ['pharma_sector_regulatory_landscape'],
    'ich pharmaceuticals': ['pharma_sector_regulatory_landscape'],
    'pharma epr': ['pharma_sector_regulatory_landscape'],
    'extended producer responsibility pharma': ['pharma_sector_regulatory_landscape'],
    'micropollutants pharma': ['pharma_sector_regulatory_landscape'],
    'wastewater pharma': ['pharma_sector_regulatory_landscape'],
    'uwwtd pharma': ['pharma_sector_regulatory_landscape'],
    'pfas pharma': ['pharma_sector_regulatory_landscape', 'water_pollution_pfas'],
    'reach pharma': ['pharma_sector_regulatory_landscape', 'reach_chemicals_regulation'],
    'api manufacturing': ['pharma_sector_regulatory_landscape'],
    'active pharmaceutical ingredient': ['pharma_sector_regulatory_landscape'],
    'pharma china dependency': ['pharma_sector_regulatory_landscape'],
    'pharma supply chain': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_legislation_reform'],
    'biosecure act': ['pharma_sector_regulatory_landscape'],
    'drug pricing eu': ['pharma_sector_regulatory_landscape'],
    'pharma deep dive': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_framework'],
    'legislacion farmaceutica': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_framework'],
    'legislacio farmaceutica': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_framework'],
    'legislation pharmaceutique': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_framework'],
    'farmaceutische wetgeving': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_framework'],
    'legislazione farmaceutica': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_framework'],
    'pharma package': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_legislation_reform'],
    'paquet pharmaceutique': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_legislation_reform'],
    'paquete farmaceutico': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_legislation_reform'],
    'hta regulation': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_framework'],
    'health technology assessment': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_framework'],
    '2021/2282': ['pharma_sector_regulatory_landscape'],
    'eudamed': ['pharma_sector_regulatory_landscape'],
    'falsified medicines': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_framework'],
    'serialisation medicines': ['pharma_sector_regulatory_landscape'],
    'supplementary protection certificate': ['pharma_sector_regulatory_landscape'],
    'spc pharma': ['pharma_sector_regulatory_landscape'],
    'ema fees': ['pharma_sector_regulatory_landscape'],
    'veterinary medicinal': ['pharma_sector_regulatory_landscape'],
    'orphan medicinal products': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_framework'],
    'advanced therapy': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_framework'],
    'atmp': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_framework'],
    'phage therapy': ['pharma_sector_regulatory_landscape'],
    'personalised medicine': ['pharma_sector_regulatory_landscape'],
    'antimicrobial stewardship': ['pharma_sector_regulatory_landscape', 'eu_pharmaceutical_legislation_reform'],

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
    # EU-China relations
    'eu china': ['eu_trade_policy'],
    'eu china relations': ['eu_trade_policy'],
    'china strategy': ['eu_trade_policy'],
    'strategy on china': ['eu_trade_policy'],
    'china and': ['eu_trade_policy'],
    'on china': ['eu_trade_policy'],
    'china trade': ['eu_trade_policy'],
    'china commission': ['eu_trade_policy'],
    'china debate': ['eu_trade_policy'],
    'china policy': ['eu_trade_policy'],
    'beijing': ['eu_trade_policy'],
    'relaciones ue china': ['eu_trade_policy'],
    'estrategia china': ['eu_trade_policy'],
    'respecto a china': ['eu_trade_policy'],
    'debate china': ['eu_trade_policy'],
    'china y': ['eu_trade_policy'],
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
    'combined transport': ['combined_transport_directive'],
    'combined transport directive': ['combined_transport_directive'],
    '92/106/EEC': ['combined_transport_directive'],
    '31992L0106': ['combined_transport_directive'],
    'directive 92/106': ['combined_transport_directive'],
    'multimodal transport': ['combined_transport_directive'],
    'intermodal transport': ['combined_transport_directive'],
    'intermodal logistics': ['combined_transport_directive'],
    'intermodal freight': ['combined_transport_directive'],
    '+FIRRST': ['combined_transport_directive'],
    'FIRRST': ['combined_transport_directive'],
    'rail-road transport': ['combined_transport_directive'],
    'rail road transport': ['combined_transport_directive'],
    'transporte combinado': ['combined_transport_directive'],
    'transport combinat': ['combined_transport_directive'],
    'transport combiné': ['combined_transport_directive'],
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

    # Spanish IBEX 35 companies: EU regulatory landscape
    'telefonica': ['spanish_ibex35_eu_regulation'],
    'telefonica regulation': ['spanish_ibex35_eu_regulation'],
    'bbva': ['spanish_ibex35_eu_regulation'],
    'bbva regulation': ['spanish_ibex35_eu_regulation'],
    'caixabank': ['spanish_ibex35_eu_regulation'],
    'santander': ['spanish_ibex35_eu_regulation'],
    'banco santander': ['spanish_ibex35_eu_regulation'],
    'repsol': ['spanish_ibex35_eu_regulation'],
    'iberdrola': ['spanish_ibex35_eu_regulation'],
    'endesa': ['spanish_ibex35_eu_regulation'],
    'naturgy': ['spanish_ibex35_eu_regulation'],
    'inditex': ['spanish_ibex35_eu_regulation'],
    'mercadona': ['spanish_ibex35_eu_regulation'],
    'indra': ['spanish_ibex35_eu_regulation'],
    'amadeus it': ['spanish_ibex35_eu_regulation'],
    'cellnex': ['spanish_ibex35_eu_regulation'],
    'ferrovial': ['spanish_ibex35_eu_regulation'],
    'grifols': ['spanish_ibex35_eu_regulation', 'pharma_sector_regulatory_landscape'],
    'ibex 35': ['spanish_ibex35_eu_regulation'],
    'ibex35': ['spanish_ibex35_eu_regulation'],
    'spanish companies eu': ['spanish_ibex35_eu_regulation'],
    'empresas espanolas ue': ['spanish_ibex35_eu_regulation'],
    'empreses espanyoles ue': ['spanish_ibex35_eu_regulation'],
    'regulacion empresas espanolas': ['spanish_ibex35_eu_regulation'],
    'aesia': ['spanish_ibex35_eu_regulation', 'ai_act_regulation'],
    'navantia': ['spanish_ibex35_eu_regulation'],
    'moeve': ['spanish_ibex35_eu_regulation'],
    'acciona': ['spanish_ibex35_eu_regulation'],
    'enagas': ['spanish_ibex35_eu_regulation'],
    'seat cupra': ['spanish_ibex35_eu_regulation'],
    'mapfre': ['spanish_ibex35_eu_regulation'],
    'el corte ingles': ['spanish_ibex35_eu_regulation'],
    'puig': ['spanish_ibex35_eu_regulation'],

    # Council Analysis and Research Team (ART) publications
    'council research': ['council_art_research'],
    'council research papers': ['council_art_research'],
    'art papers': ['council_art_research'],
    'council analysis': ['council_art_research'],
    'forward look': ['council_art_research'],
    'forward look 2026': ['council_art_research'],
    'council forward look': ['council_art_research'],
    'council secretariat research': ['council_art_research'],
    'council strategic analysis': ['council_art_research'],
    'prospects for 2026': ['council_art_research'],

    # AI Continent Action Plan (April 2025)
    'ai continent': ['ai_continent_action_plan'],
    'ai continent action plan': ['ai_continent_action_plan'],
    'ai action plan': ['ai_continent_action_plan'],
    'ai factory': ['ai_continent_action_plan'],
    'ai factories': ['ai_continent_action_plan'],
    'ai gigafactory': ['ai_continent_action_plan'],
    'ai gigafactories': ['ai_continent_action_plan'],
    'gigafactory ai': ['ai_continent_action_plan'],
    'investai': ['ai_continent_action_plan'],
    'invest ai': ['ai_continent_action_plan'],
    'eurohpc ai': ['ai_continent_action_plan'],
    'apply ai strategy': ['apply_ai_strategy_public_sector', 'ai_continent_action_plan'],
    'apply ai': ['apply_ai_strategy_public_sector', 'ai_continent_action_plan'],
    'ai public administration': ['apply_ai_strategy_public_sector'],
    'ai public sector': ['apply_ai_strategy_public_sector'],
    'govtech': ['apply_ai_strategy_public_sector'],
    'ai adoption public': ['apply_ai_strategy_public_sector'],
    'jrc ai': ['apply_ai_strategy_public_sector'],
    'jrc143539': ['apply_ai_strategy_public_sector'],
    'gpt@jrc': ['apply_ai_strategy_public_sector'],
    'ai registries': ['apply_ai_strategy_public_sector'],
    'public ai registry': ['apply_ai_strategy_public_sector'],
    'ai literacy public': ['apply_ai_strategy_public_sector'],
    'digital sovereignty ai': ['apply_ai_strategy_public_sector', 'ai_continent_action_plan'],
    'edih': ['apply_ai_strategy_public_sector', 'ai_continent_action_plan'],
    'european digital innovation hub': ['apply_ai_strategy_public_sector', 'ai_continent_action_plan'],
    'genai4eu': ['apply_ai_strategy_public_sector', 'ai_continent_action_plan'],
    'public sector tech watch': ['apply_ai_strategy_public_sector'],
    'pstw': ['apply_ai_strategy_public_sector'],
    'ia administracion publica': ['apply_ai_strategy_public_sector'],
    'ia administration publique': ['apply_ai_strategy_public_sector'],
    'ia pubblica amministrazione': ['apply_ai_strategy_public_sector'],
    'ia administracio publica': ['apply_ai_strategy_public_sector'],

    # SME / Self-employed / Business (Catalan trade associations)
    'self-employed': ['employment_future_of_work'],
    'freelance': ['employment_future_of_work'],
    'freelancer': ['employment_future_of_work'],
    'freelancers': ['employment_future_of_work'],
    'autonomous worker': ['employment_future_of_work'],
    'autonom': ['employment_future_of_work'],
    'autonoms': ['employment_future_of_work'],
    'autonomos': ['employment_future_of_work'],
    'auto-entrepreneur': ['employment_future_of_work'],
    'treballador autonom': ['employment_future_of_work'],
    'trabajador autonomo': ['employment_future_of_work'],
    'lavoratore autonomo': ['employment_future_of_work'],
    'platform worker': ['employment_future_of_work'],
    'platform workers directive': ['employment_future_of_work'],
    'eu funding sme': ['28th_regime_innovation_act', 'fp10_ecf_competitiveness'],
    'eu funding for smes': ['28th_regime_innovation_act', 'fp10_ecf_competitiveness'],
    'sme funding': ['28th_regime_innovation_act', 'fp10_ecf_competitiveness'],
    'finançament pimes': ['28th_regime_innovation_act', 'fp10_ecf_competitiveness'],
    'financiacion pymes': ['28th_regime_innovation_act', 'fp10_ecf_competitiveness'],
    'business succession': ['employment_future_of_work'],
    'business transfer': ['employment_future_of_work'],
    'company succession': ['employment_future_of_work'],
    'successio empresarial': ['employment_future_of_work'],
    'traspas empresa': ['employment_future_of_work'],
    'urban commerce': ['eu_product_safety_consumer', 'dsa_enforcement'],
    'retail regulation': ['eu_product_safety_consumer'],
    'proximity commerce': ['eu_product_safety_consumer'],
    'comerc de proximitat': ['eu_product_safety_consumer'],
    'comercio de proximidad': ['eu_product_safety_consumer'],
    'commercio di prossimita': ['eu_product_safety_consumer'],
    'comercio urbano': ['eu_product_safety_consumer'],
    'comerc urba': ['eu_product_safety_consumer'],
    'pimec': ['28th_regime_innovation_act', 'employment_future_of_work'],
    'foment del treball': ['28th_regime_innovation_act', 'eu_trade_policy'],
    'cecot': ['28th_regime_innovation_act', 'employment_future_of_work'],
    'barcelona comerc': ['eu_product_safety_consumer'],
    'eixos barcelona': ['eu_product_safety_consumer'],
    'ai skills academy': ['ai_continent_action_plan'],
    'cloud and ai development act': ['ai_continent_action_plan'],
    'cloud ai act': ['ai_continent_action_plan'],
    'ai act service desk': ['ai_continent_action_plan', 'ai_act_regulation'],
    'ai data centres': ['ai_continent_action_plan'],
    'ai data centers': ['ai_continent_action_plan'],
    'data union strategy': ['ai_continent_action_plan'],
    'european data union': ['ai_continent_action_plan'],
    'ai talent': ['ai_continent_action_plan'],
    'ai fellowship': ['ai_continent_action_plan'],
    'ai fellowships': ['ai_continent_action_plan'],
    'ai strategy eu': ['ai_continent_action_plan', 'ai_act_regulation'],
    'eu ai strategy': ['ai_continent_action_plan', 'ai_act_regulation'],
    'plan d\'action ia': ['ai_continent_action_plan'],
    'plan de accion ia': ['ai_continent_action_plan'],
    'pla d\'accio ia': ['ai_continent_action_plan'],
    'piano d\'azione ia': ['ai_continent_action_plan'],
    'ai actieplan': ['ai_continent_action_plan'],
    'triple data centre capacity': ['ai_continent_action_plan'],
    'data labs ai': ['ai_continent_action_plan'],

    # Lebanon Humanitarian Crisis
    'lebanon': ['lebanon_humanitarian_crisis'],
    'lebanon crisis': ['lebanon_humanitarian_crisis'],
    'lebanon humanitarian': ['lebanon_humanitarian_crisis'],
    'lebanon war': ['lebanon_humanitarian_crisis'],
    'lebanon israel': ['lebanon_humanitarian_crisis'],
    'liban': ['lebanon_humanitarian_crisis'],
    'libano': ['lebanon_humanitarian_crisis'],
    'libanon': ['lebanon_humanitarian_crisis'],
    'beirut': ['lebanon_humanitarian_crisis'],
    'hezbollah': ['lebanon_humanitarian_crisis'],
    'wfp lebanon': ['lebanon_humanitarian_crisis'],
    'deve lebanon': ['lebanon_humanitarian_crisis'],
    'humanitarian lebanon': ['lebanon_humanitarian_crisis'],
    'aide humanitaire liban': ['lebanon_humanitarian_crisis'],
    'crisis humanitaria libano': ['lebanon_humanitarian_crisis'],
    'crisi umanitaria libano': ['lebanon_humanitarian_crisis'],

    # EU Product Safety and Consumer Protection
    'gpsr': ['eu_product_safety_consumer'],
    'general product safety regulation': ['eu_product_safety_consumer'],
    'regulation 2023/988': ['eu_product_safety_consumer'],
    'temu': ['eu_product_safety_consumer'],
    'shein': ['eu_product_safety_consumer'],
    'aliexpress': ['eu_product_safety_consumer'],
    'unsafe products': ['eu_product_safety_consumer'],
    'dangerous products': ['eu_product_safety_consumer'],
    'product recall': ['eu_product_safety_consumer'],
    'product recalls': ['eu_product_safety_consumer'],
    'safety gate': ['eu_product_safety_consumer'],
    'rapex': ['eu_product_safety_consumer'],
    'consumer protection': ['eu_product_safety_consumer'],
    'consumer safety': ['eu_product_safety_consumer'],
    'online marketplace safety': ['eu_product_safety_consumer'],
    'marketplace product safety': ['eu_product_safety_consumer'],
    'imco temu': ['eu_product_safety_consumer'],
    'imco hearing': ['eu_product_safety_consumer'],
    'seguridad de productos': ['eu_product_safety_consumer'],
    'securite des produits': ['eu_product_safety_consumer'],
    'sicurezza dei prodotti': ['eu_product_safety_consumer'],
    'productveiligheid': ['eu_product_safety_consumer'],
    'seguretat dels productes': ['eu_product_safety_consumer'],
    'proteccion del consumidor': ['eu_product_safety_consumer'],
    'protection des consommateurs': ['eu_product_safety_consumer'],
    'protezione dei consumatori': ['eu_product_safety_consumer'],
    'consumentenbescherming': ['eu_product_safety_consumer'],
    'proteccio del consumidor': ['eu_product_safety_consumer'],

    # Occupational Health and Safety
    'occupational health': ['occupational_health_safety'],
    'occupational safety': ['occupational_health_safety'],
    'worker safety': ['occupational_health_safety'],
    'workplace safety': ['occupational_health_safety'],
    'health and safety at work': ['occupational_health_safety'],
    'osh directive': ['occupational_health_safety'],
    'carcinogens directive': ['occupational_health_safety'],
    'carcinogens and mutagens': ['occupational_health_safety'],
    'cmd directive': ['occupational_health_safety'],
    'occupational exposure limit': ['occupational_health_safety'],
    'occupational exposure limits': ['occupational_health_safety'],
    'oel': ['occupational_health_safety'],
    'oels': ['occupational_health_safety'],
    'eu-osha': ['occupational_health_safety'],
    'hazardous chemicals workers': ['occupational_health_safety'],
    'chemical exposure workers': ['occupational_health_safety'],
    'lead exposure': ['occupational_health_safety'],
    'diisocyanates': ['occupational_health_safety'],
    'asbestos directive': ['occupational_health_safety'],
    'work accidents': ['occupational_health_safety'],
    'occupational cancer': ['occupational_health_safety'],
    'directive 89/391': ['occupational_health_safety'],
    'directive 2004/37': ['occupational_health_safety'],
    'salud laboral': ['occupational_health_safety'],
    'sante au travail': ['occupational_health_safety'],
    'salute sul lavoro': ['occupational_health_safety'],
    'arbeidsveiligheid': ['occupational_health_safety'],
    'salut laboral': ['occupational_health_safety'],
    'seguridad en el trabajo': ['occupational_health_safety'],

    # UN Cybercrime Convention
    'cybercrime convention': ['un_cybercrime_convention'],
    'un cybercrime': ['un_cybercrime_convention'],
    'cybercrime treaty': ['un_cybercrime_convention'],
    'convention against cybercrime': ['un_cybercrime_convention'],
    'budapest convention': ['un_cybercrime_convention'],
    'cybercrime': ['un_cybercrime_convention'],
    'cyber crime': ['un_cybercrime_convention'],
    '2025/0231': ['un_cybercrime_convention'],
    'moritz korner': ['un_cybercrime_convention'],
    'convention cybercriminalite': ['un_cybercrime_convention'],
    'convencion ciberdelincuencia': ['un_cybercrime_convention'],
    'convenzione criminalita informatica': ['un_cybercrime_convention'],
    'cybercrimeverdrag': ['un_cybercrime_convention'],
    'conveni ciberdelinquencia': ['un_cybercrime_convention'],
    # Technology Transfer Block Exemption Regulation (TTBER) 2026
    'ttber': ['tech_transfer_block_exemption'],
    'technology transfer block exemption': ['tech_transfer_block_exemption'],
    'technology transfer regulation': ['tech_transfer_block_exemption'],
    'technology licensing agreements': ['tech_transfer_block_exemption'],
    'technology licensing eu': ['tech_transfer_block_exemption'],
    'technology transfer guidelines': ['tech_transfer_block_exemption'],
    'patent licensing eu': ['tech_transfer_block_exemption'],
    'cross licensing eu': ['tech_transfer_block_exemption'],
    'patent pool eu': ['tech_transfer_block_exemption'],
    'know-how licensing': ['tech_transfer_block_exemption'],
    '316/2014': ['tech_transfer_block_exemption'],
    'regulation 316/2014': ['tech_transfer_block_exemption'],
    'licence accords technologie': ['tech_transfer_block_exemption'],
    'acuerdos licencia tecnologia': ['tech_transfer_block_exemption'],
    'acordos de licencas': ['tech_transfer_block_exemption'],
    'technologielicentie': ['tech_transfer_block_exemption'],
    'ip licensing eu': ['tech_transfer_block_exemption'],
    'sep frand licensing': ['tech_transfer_block_exemption'],
    # Territorial Supply Constraints (TSC)
    'territorial supply constraint': ['eu_territorial_supply_constraints'],
    'territorial supply constraints': ['eu_territorial_supply_constraints'],
    'tsc single market': ['eu_territorial_supply_constraints'],
    'parallel trade eu': ['eu_territorial_supply_constraints'],
    'cross border sourcing': ['eu_territorial_supply_constraints'],
    'dual pricing eu': ['eu_territorial_supply_constraints'],
    'national-only supply': ['eu_territorial_supply_constraints'],
    'retailers cross border': ['eu_territorial_supply_constraints'],
    'vber vertical block exemption': ['eu_territorial_supply_constraints'],
    'vertical block exemption': ['eu_territorial_supply_constraints'],
    'vertical guidelines 2022': ['eu_territorial_supply_constraints'],
    'single market fragmentation': ['eu_territorial_supply_constraints'],
    'retailer national sourcing': ['eu_territorial_supply_constraints'],
    'eurocommerce tsc': ['eu_territorial_supply_constraints'],
    'letta report single market': ['eu_territorial_supply_constraints'],
    'contraintes approvisionnement territorial': ['eu_territorial_supply_constraints'],
    'restricciones suministro territorial': ['eu_territorial_supply_constraints'],
    'territoriale leveringsbeperkingen': ['eu_territorial_supply_constraints'],
    'restrizioni fornitura territoriale': ['eu_territorial_supply_constraints'],
    # Carbon Removal and Carbon Farming Regulation (CRCF)
    'crcf': ['eu_carbon_removals_farming'],
    'carbon removal regulation': ['eu_carbon_removals_farming'],
    'carbon farming regulation': ['eu_carbon_removals_farming'],
    'permanent carbon removal': ['eu_carbon_removals_farming'],
    'carbon dioxide removal': ['eu_carbon_removals_farming'],
    'cdr certification': ['eu_carbon_removals_farming'],
    'daccs': ['eu_carbon_removals_farming'],
    'beccs': ['eu_carbon_removals_farming'],
    'biochar': ['eu_carbon_removals_farming'],
    'enhanced weathering': ['eu_carbon_removals_farming'],
    'carbon sequestration eu': ['eu_carbon_removals_farming'],
    'carbon storage products': ['eu_carbon_removals_farming'],
    '2024/3012': ['eu_carbon_removals_farming'],
    '32024R3012': ['eu_carbon_removals_farming'],
    'elimination carbone': ['eu_carbon_removals_farming'],
    'agricultura de carbono': ['eu_carbon_removals_farming'],
    'captura carbono permanente': ['eu_carbon_removals_farming'],
    'koolstoflandbouw': ['eu_carbon_removals_farming'],
    'agricoltura del carbonio': ['eu_carbon_removals_farming'],
    'agricultura de carboni': ['eu_carbon_removals_farming'],
    # Single-Use Plastics Directive (SUPD)
    'supd': ['single_use_plastics_directive'],
    'single use plastics': ['single_use_plastics_directive'],
    'single-use plastics directive': ['single_use_plastics_directive'],
    '2019/904': ['single_use_plastics_directive'],
    '32019L0904': ['single_use_plastics_directive'],
    'plastic bottles collection': ['single_use_plastics_directive'],
    'tethered caps': ['single_use_plastics_directive'],
    'recycled content pet': ['single_use_plastics_directive'],
    'deposit return scheme eu': ['single_use_plastics_directive'],
    'drs deposit scheme': ['single_use_plastics_directive'],
    'oxo degradable plastics': ['single_use_plastics_directive'],
    'eps food containers': ['single_use_plastics_directive'],
    'epr plastics': ['single_use_plastics_directive'],
    'plastiques a usage unique': ['single_use_plastics_directive'],
    'plasticos de un solo uso': ['single_use_plastics_directive'],
    'plasticos un sol us': ['single_use_plastics_directive'],
    'wegwerpplastics': ['single_use_plastics_directive'],
    'plastica monouso': ['single_use_plastics_directive'],
    # European Public Prosecutor's Office (EPPO)
    'eppo': ['eppo_european_public_prosecutor'],
    'european public prosecutor': ['eppo_european_public_prosecutor'],
    'european chief prosecutor': ['eppo_european_public_prosecutor'],
    'chief prosecutor eu': ['eppo_european_public_prosecutor'],
    'kovesi': ['eppo_european_public_prosecutor'],
    'laura codruta kovesi': ['eppo_european_public_prosecutor'],
    'regulation 2017/1939': ['eppo_european_public_prosecutor'],
    '32017R1939': ['eppo_european_public_prosecutor'],
    'pif directive': ['eppo_european_public_prosecutor'],
    'pif crimes': ['eppo_european_public_prosecutor'],
    '2017/1371': ['eppo_european_public_prosecutor'],
    'european delegated prosecutor': ['eppo_european_public_prosecutor'],
    'vat fraud eu': ['eppo_european_public_prosecutor'],
    'rrf fraud': ['eppo_european_public_prosecutor'],
    'ngeu fraud': ['eppo_european_public_prosecutor'],
    'olaf eppo': ['eppo_european_public_prosecutor'],
    'parquet europeen': ['eppo_european_public_prosecutor'],
    'fiscalia europea': ['eppo_european_public_prosecutor'],
    'fiscalia europea prosecutor': ['eppo_european_public_prosecutor'],
    'europees openbaar ministerie': ['eppo_european_public_prosecutor'],
    'procura europea': ['eppo_european_public_prosecutor'],
    'fiscalia europea catalan': ['eppo_european_public_prosecutor'],
    'fiscalia europea espanola': ['eppo_european_public_prosecutor'],
    # Pact for Skills
    'pact for skills': ['pact_for_skills'],
    'european skills agenda': ['pact_for_skills'],
    'individual learning accounts': ['pact_for_skills'],
    'ila learning accounts': ['pact_for_skills'],
    'micro-credentials eu': ['pact_for_skills'],
    'micro credentials europe': ['pact_for_skills'],
    'skills partnerships eu': ['pact_for_skills'],
    'upskilling reskilling eu': ['pact_for_skills'],
    'skills portability': ['pact_for_skills'],
    'union of skills': ['pact_for_skills'],
    'european year of skills': ['pact_for_skills'],
    'minzatu skills': ['pact_for_skills'],
    '10 million trained': ['pact_for_skills'],
    'pacto por las competencias': ['pact_for_skills'],
    'pacte des competences': ['pact_for_skills'],
    'vaardighedenpact': ['pact_for_skills'],
    'patto competenze': ['pact_for_skills'],
    'pacte per les competencies': ['pact_for_skills'],
    # EU Demographic Change
    'eu demographic change': ['eu_demographic_change'],
    'europop': ['eu_demographic_change'],
    'europop 2026': ['eu_demographic_change'],
    'eu population projection': ['eu_demographic_change'],
    'eu population decline': ['eu_demographic_change'],
    'eu population 2100': ['eu_demographic_change'],
    'eu population 2070': ['eu_demographic_change'],
    'eu population ageing': ['eu_demographic_change'],
    'old-age dependency ratio': ['eu_demographic_change'],
    'fertility rate eu': ['eu_demographic_change'],
    'demography toolbox': ['eu_demographic_change'],
    'ageing report eu': ['eu_demographic_change'],
    'rural depopulation eu': ['eu_demographic_change'],
    'shrinking regions eu': ['eu_demographic_change'],
    'long term vision rural areas': ['eu_demographic_change'],
    'barcelona childcare targets': ['eu_demographic_change'],
    'eu care strategy': ['eu_demographic_change'],
    'cambio demografico eu': ['eu_demographic_change'],
    'changement demographique ue': ['eu_demographic_change'],
    'demografische verandering': ['eu_demographic_change'],
    'cambiamento demografico ue': ['eu_demographic_change'],
    'canvi demografic europeu': ['eu_demographic_change'],
    # Dark web + cybersecurity
    'dark web': ['dark_web_cybersecurity'],
    'darknet': ['dark_web_cybersecurity'],
    'tor network': ['dark_web_cybersecurity'],
    'tor project': ['dark_web_cybersecurity'],
    'i2p network': ['dark_web_cybersecurity'],
    'onion router': ['dark_web_cybersecurity'],
    'darknet market': ['dark_web_cybersecurity'],
    'archetyp market': ['dark_web_cybersecurity'],
    'kraken market': ['dark_web_cybersecurity'],
    'ransomware eu': ['dark_web_cybersecurity'],
    'europol ec3': ['dark_web_cybersecurity'],
    'j-cat': ['dark_web_cybersecurity'],
    'ransomware-as-a-service': ['dark_web_cybersecurity'],
    'lockbit': ['dark_web_cybersecurity'],
    'red oscura': ['dark_web_cybersecurity'],
    'web oscuro': ['dark_web_cybersecurity'],
    'dark net': ['dark_web_cybersecurity'],
    'internet profond': ['dark_web_cybersecurity'],
    # Cross-guide triggers for updates
    'google search data sharing': ['digital_markets_act'],
    'article 6(11) dma': ['digital_markets_act'],
    'article 6.11 dma': ['digital_markets_act'],
    'cernavoda': ['competition_law_enforcement'],
    'cernavoda state aid': ['competition_law_enforcement'],
    'romanian nuclear state aid': ['competition_law_enforcement'],
    'bulgarian state aid electricity': ['competition_law_enforcement', 'citizens_energy_package'],
    'german state aid electricity': ['competition_law_enforcement', 'citizens_energy_package'],
    'slovenian state aid electricity': ['competition_law_enforcement', 'citizens_energy_package'],
    'tctf state aid': ['competition_law_enforcement'],
    'temporary crisis transition framework': ['competition_law_enforcement'],
    'state aid state of play': ['competition_law_enforcement'],
    'fisheries emergency funding middle east': ['iran_strait_hormuz_eu_response'],
    'emfaf emergency middle east': ['iran_strait_hormuz_eu_response'],
    'renewable hydrogen review': ['eu_energy_policy'],
    'emergency plan energy price': ['eu_energy_policy', 'iran_strait_hormuz_eu_response'],
    'energy price surge': ['eu_energy_policy', 'iran_strait_hormuz_eu_response'],
    'special panel child online safety': ['csam_regulation_online'],
    'second meeting special panel': ['csam_regulation_online'],
    'von der leyen child safety panel': ['csam_regulation_online'],
    'conversion practices ban': ['csam_regulation_online'],
    'conversion therapy ban eu': ['csam_regulation_online'],
    'fractured reality jrc': ['ai_act_amendments_2026'],
    'algorithmic polarisation': ['ai_act_amendments_2026'],
    'algorithms polarisation democracy': ['ai_act_amendments_2026'],
    'jrc fractured reality': ['ai_act_amendments_2026'],
    # Food and Feed Simplification Omnibus ("Omnibus X")
    'omnibus x': ['eu_food_feed_simplification_omnibus'],
    'omnibus ix': ['eu_food_feed_simplification_omnibus'],
    'food feed omnibus': ['eu_food_feed_simplification_omnibus'],
    'food and feed omnibus': ['eu_food_feed_simplification_omnibus'],
    'agri-food omnibus': ['eu_food_feed_simplification_omnibus'],
    'food simplification omnibus': ['eu_food_feed_simplification_omnibus'],
    'food feed simplification': ['eu_food_feed_simplification_omnibus'],
    'food feed law simplification': ['eu_food_feed_simplification_omnibus'],
    'simplification food law': ['eu_food_feed_simplification_omnibus'],
    'simplification legislation alimentaire': ['eu_food_feed_simplification_omnibus'],
    'simplificacion legislacion alimentaria': ['eu_food_feed_simplification_omnibus'],
    'simplificacio legislacio alimentaria': ['eu_food_feed_simplification_omnibus'],
    'legislacio alimentaria pinsos': ['eu_food_feed_simplification_omnibus'],
    'legislazione alimentare semplificazione': ['eu_food_feed_simplification_omnibus'],
    'vereenvoudiging voedselwetgeving': ['eu_food_feed_simplification_omnibus'],
    'pinsos simplificacio': ['eu_food_feed_simplification_omnibus'],
    # --- 20 April 2026 news batch (9 new guides) ---
    # Omnibus VI -- chemicals simplification
    'omnibus vi': ['omnibus_vi_chemicals_simplification'],
    'omnibus 6': ['omnibus_vi_chemicals_simplification'],
    'omnibus chemicals': ['omnibus_vi_chemicals_simplification'],
    'chemicals omnibus': ['omnibus_vi_chemicals_simplification'],
    'chemicals simplification omnibus': ['omnibus_vi_chemicals_simplification'],
    'simplification chemicals eu': ['omnibus_vi_chemicals_simplification'],
    'reach simplification': ['omnibus_vi_chemicals_simplification'],
    'echa simplification': ['omnibus_vi_chemicals_simplification'],
    'clp simplification': ['omnibus_vi_chemicals_simplification'],
    'biocides simplification': ['omnibus_vi_chemicals_simplification'],
    'omnibus substances chimiques': ['omnibus_vi_chemicals_simplification'],
    'omnibus productos quimicos': ['omnibus_vi_chemicals_simplification'],
    'omnibus productes quimics': ['omnibus_vi_chemicals_simplification'],
    'omnibus sostanze chimiche': ['omnibus_vi_chemicals_simplification'],
    'vereenvoudiging chemische stoffen': ['omnibus_vi_chemicals_simplification'],
    # Generalised Scheme of Preferences (GSP) -- new generation
    'gsp new generation': ['eu_gsp_new_generation'],
    'generalised scheme of preferences': ['eu_gsp_new_generation'],
    'generalized scheme of preferences': ['eu_gsp_new_generation'],
    'new gsp regulation': ['eu_gsp_new_generation'],
    'gsp 2028': ['eu_gsp_new_generation'],
    'gsp post 2027': ['eu_gsp_new_generation'],
    'everything but arms': ['eu_gsp_new_generation'],
    'eba preferences': ['eu_gsp_new_generation'],
    'gsp plus': ['eu_gsp_new_generation'],
    'regulation 978/2012': ['eu_gsp_new_generation'],
    'sistema preferencias generalizadas': ['eu_gsp_new_generation'],
    'sistema preferences generalitzades': ['eu_gsp_new_generation'],
    'sistema preferenze generalizzate': ['eu_gsp_new_generation'],
    'systeme preferences generalisees': ['eu_gsp_new_generation'],
    'stelsel algemene preferenties': ['eu_gsp_new_generation'],
    # US 2026 National Defence Strategy
    'us 2026 national defence strategy': ['us_2026_national_defence_strategy'],
    'us 2026 national defense strategy': ['us_2026_national_defence_strategy'],
    'us national defence strategy': ['us_2026_national_defence_strategy'],
    'us national defense strategy': ['us_2026_national_defence_strategy'],
    'trump nds 2026': ['us_2026_national_defence_strategy'],
    'nds 2026': ['us_2026_national_defence_strategy'],
    'indo-pacific pivot': ['us_2026_national_defence_strategy'],
    'us pacing threat china': ['us_2026_national_defence_strategy'],
    'burden sharing nato': ['us_2026_national_defence_strategy'],
    '3% gdp nato': ['us_2026_national_defence_strategy'],
    'estrategia defensa eeuu 2026': ['us_2026_national_defence_strategy'],
    'estrategia defensa estats units': ['us_2026_national_defence_strategy'],
    'strategie defense etats unis': ['us_2026_national_defence_strategy'],
    'strategia difesa stati uniti': ['us_2026_national_defence_strategy'],
    'amerikaanse defensiestrategie': ['us_2026_national_defence_strategy'],
    # Maritime decarbonisation / IMO MEPC 84
    'maritime decarbonisation': ['maritime_decarbonisation_imo'],
    'maritime decarbonization': ['maritime_decarbonisation_imo'],
    'imo mepc 84': ['maritime_decarbonisation_imo'],
    'imo mepc': ['maritime_decarbonisation_imo'],
    'imo net zero framework': ['maritime_decarbonisation_imo'],
    'fueleu maritime': ['maritime_decarbonisation_imo'],
    'eu ets shipping': ['maritime_decarbonisation_imo'],
    'shipping emissions eu': ['maritime_decarbonisation_imo'],
    'mepc 84': ['maritime_decarbonisation_imo'],
    'regulation 2023/1805': ['maritime_decarbonisation_imo'],
    'descarbonizacion maritima': ['maritime_decarbonisation_imo'],
    'descarbonitzacio maritima': ['maritime_decarbonisation_imo'],
    'descarbonisation maritime': ['maritime_decarbonisation_imo'],
    'decarbonizzazione marittima': ['maritime_decarbonisation_imo'],
    'maritieme decarbonisatie': ['maritime_decarbonisation_imo'],
    # Emissions accounting in transport services
    'emissions accounting transport': ['emissions_accounting_transport_services'],
    'countemissions eu': ['emissions_accounting_transport_services'],
    'count emissions eu': ['emissions_accounting_transport_services'],
    'iso 14083': ['emissions_accounting_transport_services'],
    'ghg emissions transport services': ['emissions_accounting_transport_services'],
    'transport services emissions': ['emissions_accounting_transport_services'],
    '2023/0266(cod)': ['emissions_accounting_transport_services'],
    'com(2023) 441': ['emissions_accounting_transport_services'],
    'contabilidad emisiones transporte': ['emissions_accounting_transport_services'],
    'comptabilite emissions transport': ['emissions_accounting_transport_services'],
    'comptabilitzacio emissions transport': ['emissions_accounting_transport_services'],
    'contabilita emissioni trasporto': ['emissions_accounting_transport_services'],
    'emissieboekhouding vervoer': ['emissions_accounting_transport_services'],
    # High-Level Study Group on Connectivity and Digital Infrastructure
    'high level study group connectivity': ['connectivity_digital_infrastructure_hlsg'],
    'high-level study group connectivity': ['connectivity_digital_infrastructure_hlsg'],
    'connectivity hlsg': ['connectivity_digital_infrastructure_hlsg'],
    'digital infrastructure study group': ['connectivity_digital_infrastructure_hlsg'],
    'connectivity digital infrastructure': ['connectivity_digital_infrastructure_hlsg'],
    'dg cnect study group': ['connectivity_digital_infrastructure_hlsg'],
    'digital networks act study group': ['connectivity_digital_infrastructure_hlsg'],
    'grupo alto nivel conectividad': ['connectivity_digital_infrastructure_hlsg'],
    'grup alt nivell connectivitat': ['connectivity_digital_infrastructure_hlsg'],
    'groupe haut niveau connectivite': ['connectivity_digital_infrastructure_hlsg'],
    'gruppo alto livello connettivita': ['connectivity_digital_infrastructure_hlsg'],
    'hoge niveau studiegroep connectiviteit': ['connectivity_digital_infrastructure_hlsg'],
    # EU-NATO Southern Neighbourhood
    'eu nato southern neighbourhood': ['eu_nato_southern_neighbourhood'],
    'eu-nato southern neighbourhood': ['eu_nato_southern_neighbourhood'],
    'eu nato cooperation south': ['eu_nato_southern_neighbourhood'],
    'nato southern flank': ['eu_nato_southern_neighbourhood'],
    'mediterranean dialogue nato': ['eu_nato_southern_neighbourhood'],
    'eunavfor aspides': ['eu_nato_southern_neighbourhood'],
    'eunavfor irini': ['eu_nato_southern_neighbourhood'],
    'eu-nato joint declaration': ['eu_nato_southern_neighbourhood'],
    'sahel hybrid threats': ['eu_nato_southern_neighbourhood'],
    'africa corps wagner': ['eu_nato_southern_neighbourhood'],
    'relaciones ue otan sur': ['eu_nato_southern_neighbourhood'],
    'relacions ue otan sud': ['eu_nato_southern_neighbourhood'],
    'relations ue otan sud': ['eu_nato_southern_neighbourhood'],
    'relazioni ue nato sud': ['eu_nato_southern_neighbourhood'],
    'eu navo zuidelijk nabuurschap': ['eu_nato_southern_neighbourhood'],
    # Consent-based definition of rape
    'consent based rape definition': ['consent_based_rape_definition'],
    'consent-based rape': ['consent_based_rape_definition'],
    'rape definition eu': ['consent_based_rape_definition'],
    'violence against women directive': ['consent_based_rape_definition'],
    'directive (eu) 2024/1385': ['consent_based_rape_definition'],
    '2024/1385': ['consent_based_rape_definition'],
    'istanbul convention rape': ['consent_based_rape_definition'],
    'article 36 istanbul': ['consent_based_rape_definition'],
    'article 83(1) tfeu rape': ['consent_based_rape_definition'],
    'definicion consentimiento violacion': ['consent_based_rape_definition'],
    'definicio consentiment violacio': ['consent_based_rape_definition'],
    'definition consentement viol': ['consent_based_rape_definition'],
    'definizione consenso stupro': ['consent_based_rape_definition'],
    'definitie instemming verkrachting': ['consent_based_rape_definition'],
    # Maternity and paternity leave
    'maternity paternity leave': ['maternity_paternity_leave'],
    'maternity leave eu': ['maternity_paternity_leave'],
    'paternity leave eu': ['maternity_paternity_leave'],
    'parental leave directive': ['maternity_paternity_leave'],
    'work life balance directive': ['maternity_paternity_leave'],
    'directive 2019/1158': ['maternity_paternity_leave'],
    '2019/1158': ['maternity_paternity_leave'],
    'pregnant workers directive': ['maternity_paternity_leave'],
    '92/85/eec': ['maternity_paternity_leave'],
    'carers leave eu': ['maternity_paternity_leave'],
    'permiso maternidad paternidad': ['maternity_paternity_leave'],
    'permis maternitat paternitat': ['maternity_paternity_leave'],
    'conge maternite paternite': ['maternity_paternity_leave'],
    'congedo maternita paternita': ['maternity_paternity_leave'],
    'zwangerschapsverlof vaderschapsverlof': ['maternity_paternity_leave'],
    # Foreign Subsidies Regulation (new 22 April 2026)
    'foreign subsidies regulation': ['foreign_subsidies_regulation'],
    'fsr regulation': ['foreign_subsidies_regulation'],
    'regulation 2022/2560': ['foreign_subsidies_regulation'],
    '32022r2560': ['foreign_subsidies_regulation'],
    'foreign subsidies': ['foreign_subsidies_regulation'],
    'foreign financial contributions': ['foreign_subsidies_regulation'],
    'fsr notification': ['foreign_subsidies_regulation'],
    'lisbon railway foreign subsidies': ['foreign_subsidies_regulation'],
    'ip_26_853': ['foreign_subsidies_regulation'],
    'ip/26/853': ['foreign_subsidies_regulation'],
    'chinese subsidies eu': ['foreign_subsidies_regulation'],
    'sovereign wealth fund eu': ['foreign_subsidies_regulation'],
    'subvenciones extranjeras reglamento': ['foreign_subsidies_regulation'],
    'subvencions estrangeres reglament': ['foreign_subsidies_regulation'],
    'subventions etrangeres reglement': ['foreign_subsidies_regulation'],
    'sovvenzioni estere regolamento': ['foreign_subsidies_regulation'],
    'buitenlandse subsidies verordening': ['foreign_subsidies_regulation'],
    # EU Cardiovascular Health Plan (new 22 April 2026)
    'cardiovascular health plan': ['eu_cardiovascular_health_plan'],
    'cvd plan eu': ['eu_cardiovascular_health_plan'],
    'cardiovascular disease eu': ['eu_cardiovascular_health_plan'],
    'eu heart plan': ['eu_cardiovascular_health_plan'],
    'non communicable disease eu': ['eu_cardiovascular_health_plan'],
    'ncd eu strategy': ['eu_cardiovascular_health_plan'],
    'heart health eu': ['eu_cardiovascular_health_plan'],
    'plan salud cardiovascular': ['eu_cardiovascular_health_plan'],
    'pla salut cardiovascular': ['eu_cardiovascular_health_plan'],
    'plan sante cardiovasculaire': ['eu_cardiovascular_health_plan'],
    'piano salute cardiovascolare': ['eu_cardiovascular_health_plan'],
    'cardiovasculair gezondheidsplan': ['eu_cardiovascular_health_plan'],
    'sante call for evidence cvd': ['eu_cardiovascular_health_plan'],
    # Ukrainian children deportation (new 22 April 2026)
    'ukrainian children deportation': ['ukraine_children_deportation'],
    'return ukrainian children': ['ukraine_children_deportation'],
    'deported ukrainian children': ['ukraine_children_deportation'],
    'bring kids back ua': ['ukraine_children_deportation'],
    'lvova-belova': ['ukraine_children_deportation'],
    'lvova belova': ['ukraine_children_deportation'],
    'icc arrest warrant putin': ['ukraine_children_deportation'],
    'international coalition return ukrainian children': ['ukraine_children_deportation'],
    'ukraine canada children meeting': ['ukraine_children_deportation'],
    'ip_26_856': ['ukraine_children_deportation'],
    'ip/26/856': ['ukraine_children_deportation'],
    'yale humanitarian research lab ukraine': ['ukraine_children_deportation'],
    'genocide convention ukraine children': ['ukraine_children_deportation'],
    'forcible transfer children rome statute': ['ukraine_children_deportation'],
    'daria herasymchuk': ['ukraine_children_deportation'],
    'ninos ucranianos deportados': ['ukraine_children_deportation'],
    'nens ucraïnesos deportats': ['ukraine_children_deportation'],
    'enfants ukrainiens deportes': ['ukraine_children_deportation'],
    'bambini ucraini deportati': ['ukraine_children_deportation'],
    'oekraïense kinderen deportatie': ['ukraine_children_deportation'],
    # Data Retention / ePrivacy CSAM derogation extension (new 22 April 2026)
    'regulation 2021/1232': ['data_retention_extension_2021_1232'],
    '32021r1232': ['data_retention_extension_2021_1232'],
    'eprivacy derogation': ['data_retention_extension_2021_1232'],
    'csam derogation': ['data_retention_extension_2021_1232'],
    'temporary csam scanning': ['data_retention_extension_2021_1232'],
    'voluntary csam scanning': ['data_retention_extension_2021_1232'],
    'ott csam scanning': ['data_retention_extension_2021_1232'],
    'number-independent interpersonal communications': ['data_retention_extension_2021_1232'],
    '2025/0429(cod)': ['data_retention_extension_2021_1232'],
    '2025/0429 cod': ['data_retention_extension_2021_1232'],
    'vorratsdatenspeicherung': ['data_retention_extension_2021_1232'],
    'data retention extension eu': ['data_retention_extension_2021_1232'],
    'data retention directive successor': ['data_retention_extension_2021_1232'],
    'conservacion datos eu': ['data_retention_extension_2021_1232'],
    'conservacio dades ue': ['data_retention_extension_2021_1232'],
    'conservation donnees eu': ['data_retention_extension_2021_1232'],
    'conservazione dati ue': ['data_retention_extension_2021_1232'],
    'gegevensbewaring eu': ['data_retention_extension_2021_1232'],
    # Cohesion Policy Mid-Term Review (new 22 April 2026)
    'cohesion policy mid term review': ['cohesion_policy_midterm_review'],
    'cohesion policy mtr': ['cohesion_policy_midterm_review'],
    'cohesion policy reprogramming': ['cohesion_policy_midterm_review'],
    'cpr mid-term review': ['cohesion_policy_midterm_review'],
    'com(2025) 58': ['cohesion_policy_midterm_review'],
    'com 2025 58 cohesion': ['cohesion_policy_midterm_review'],
    'cohesion flexibility 2025': ['cohesion_policy_midterm_review'],
    'just transition mtr': ['cohesion_policy_midterm_review'],
    'pslf first call': ['cohesion_policy_midterm_review'],
    'public sector loan facility': ['cohesion_policy_midterm_review'],
    'revision media plazo cohesion': ['cohesion_policy_midterm_review'],
    'revisio mitja politica cohesio': ['cohesion_policy_midterm_review'],
    'revision mi parcours cohesion': ['cohesion_policy_midterm_review'],
    'revisione medio termine coesione': ['cohesion_policy_midterm_review'],
    'tussentijdse evaluatie cohesiebeleid': ['cohesion_policy_midterm_review'],
    # News-driven additions for existing guides (22 April 2026)
    'european capitals of inclusion and diversity': ['eu_equality_antidiscrimination'],
    'capitales de inclusion y diversidad': ['eu_equality_antidiscrimination'],
    'capitales de la inclusion et de la diversite': ['eu_equality_antidiscrimination'],
    'ip_26_857': ['eu_equality_antidiscrimination'],
    'ip/26/857': ['eu_equality_antidiscrimination'],
    'ai innovation health online safety': ['apply_ai_strategy_public_sector'],
    '63.2 million ai call': ['apply_ai_strategy_public_sector'],
    'digital europe programme ai health': ['apply_ai_strategy_public_sector'],
    'eprs_ata 2026 785723': ['mff_2028_2034'],
    '2028-2034 budget parliament position': ['mff_2028_2034'],
    '2028-34 budget': ['mff_2028_2034'],
    'antonio costa mff deadlock': ['mff_2028_2034'],
    'costa mff pressure': ['mff_2028_2034'],
    'afco defence union draft report': ['european_defence_union'],
    '2025/2212(ini)': ['european_defence_union'],
    'de meo defence union': ['european_defence_union'],
    'european chief prosecutor appointment': ['eppo_european_public_prosecutor'],
    '2025/0803(nle)': ['eppo_european_public_prosecutor'],
    'kovesi successor': ['eppo_european_public_prosecutor'],
    'kovesi term end': ['eppo_european_public_prosecutor'],
    'informal euco cyprus': ['iran_strait_hormuz_eu_response'],
    'euco cyprus 23-24 april': ['iran_strait_hormuz_eu_response'],
    'informal european council cyprus april 2026': ['iran_strait_hormuz_eu_response'],
    'final agenda 27-30 april plenary': ['ep_plenary_march_2026'],
    'conference of presidents 22 april 2026': ['ep_plenary_march_2026'],
    # euagenda.eu third-party events (new 22 April 2026)
    'euagenda': ['euagenda_brussels_events'],
    'euagenda.eu': ['euagenda_brussels_events'],
    'eu agenda': ['euagenda_brussels_events'],
    'brussels events': ['euagenda_brussels_events'],
    'brussels agenda': ['euagenda_brussels_events'],
    'think tank event': ['euagenda_brussels_events'],
    'think tank events': ['euagenda_brussels_events'],
    'think tank conference': ['euagenda_brussels_events'],
    'eu roundtable': ['euagenda_brussels_events'],
    'eu webinar': ['euagenda_brussels_events'],
    'eu training course': ['euagenda_brussels_events'],
    'brussels conference': ['euagenda_brussels_events'],
    'brussels webinar': ['euagenda_brussels_events'],
    'brussels roundtable': ['euagenda_brussels_events'],
    'policy event brussels': ['euagenda_brussels_events'],
    'third party event': ['euagenda_brussels_events'],
    'eu policy event': ['euagenda_brussels_events'],
    'eventos ue bruselas': ['euagenda_brussels_events'],
    'actes brussel·les': ['euagenda_brussels_events'],
    'esdeveniments ue': ['euagenda_brussels_events'],
    'evenements bruxelles': ['euagenda_brussels_events'],
    'eventi ue bruxelles': ['euagenda_brussels_events'],
    'evenementen eu brussel': ['euagenda_brussels_events'],
    # AccelerateEU Communication (22 April 2026, Ribera + Jorgensen)
    'accelerateeu': ['accelerateeu_fossil_energy_crisis'],
    'accelerate eu': ['accelerateeu_fossil_energy_crisis'],
    'accelerate-eu': ['accelerateeu_fossil_energy_crisis'],
    'fossil energy crisis': ['accelerateeu_fossil_energy_crisis'],
    'fossil crisis response': ['accelerateeu_fossil_energy_crisis'],
    'ribera jorgensen energy': ['accelerateeu_fossil_energy_crisis'],
    'ribera jørgensen energy': ['accelerateeu_fossil_energy_crisis'],
    'commission emergency energy plan': ['accelerateeu_fossil_energy_crisis', 'iran_strait_hormuz_eu_response'],
    'homegrown energy': ['accelerateeu_fossil_energy_crisis'],
    'clean homegrown energy': ['accelerateeu_fossil_energy_crisis'],
    'fs_26_631': ['accelerateeu_fossil_energy_crisis'],
    'qanda_26_630': ['accelerateeu_fossil_energy_crisis'],
    'electricity tax cuts': ['accelerateeu_fossil_energy_crisis', 'eu_energy_policy'],
    'grid tariff reform': ['accelerateeu_fossil_energy_crisis', 'eu_energy_policy'],
    'redII delegated act review': ['accelerateeu_fossil_energy_crisis'],
    'redIII delegated act': ['accelerateeu_fossil_energy_crisis', 'eu_energy_policy'],
    'power purchase agreements': ['accelerateeu_fossil_energy_crisis', 'eu_energy_policy', 'energy_grids_package'],
    'power purchase agreement': ['accelerateeu_fossil_energy_crisis', 'eu_energy_policy', 'energy_grids_package'],
    'ppa barriers': ['accelerateeu_fossil_energy_crisis', 'eu_energy_policy'],
    'swd(2026) 118': ['accelerateeu_fossil_energy_crisis', 'eu_energy_policy'],
    'swd 2026 118': ['accelerateeu_fossil_energy_crisis'],
    # Public Access to Documents -- Regulation 1049/2001
    'regulation 1049/2001': ['public_access_to_documents_1049_2001'],
    'regulation 1049': ['public_access_to_documents_1049_2001'],
    '1049/2001': ['public_access_to_documents_1049_2001'],
    '32001R1049': ['public_access_to_documents_1049_2001'],
    'public access to documents': ['public_access_to_documents_1049_2001'],
    'access to eu documents': ['public_access_to_documents_1049_2001'],
    'transparency regulation eu': ['public_access_to_documents_1049_2001'],
    '2011/0073': ['public_access_to_documents_1049_2001'],
    '2011/0073(cod)': ['public_access_to_documents_1049_2001'],
    'access info europe': ['public_access_to_documents_1049_2001'],
    'turco case': ['public_access_to_documents_1049_2001'],
    'clientearth c-612/13': ['public_access_to_documents_1049_2001'],
    'article 15 tfeu transparency': ['public_access_to_documents_1049_2001'],
    'article 42 charter': ['public_access_to_documents_1049_2001'],
    'peti 1049': ['public_access_to_documents_1049_2001'],
    'petition public access': ['public_access_to_documents_1049_2001'],
    'trilogue transparency': ['public_access_to_documents_1049_2001'],
    # Temporary Decarbonisation Fund (TDF)
    'temporary decarbonisation fund': ['temporary_decarbonisation_fund'],
    'temporary decarbonization fund': ['temporary_decarbonisation_fund'],
    'tdf fund': ['temporary_decarbonisation_fund'],
    'tdf regulation': ['temporary_decarbonisation_fund'],
    'salini decarbonisation': ['temporary_decarbonisation_fund'],
    'massimiliano salini': ['temporary_decarbonisation_fund'],
    'pe786.735': ['temporary_decarbonisation_fund'],
    'pe786735': ['temporary_decarbonisation_fund'],
    'decarbonisation capex': ['temporary_decarbonisation_fund'],
    'industrial electrification fund': ['temporary_decarbonisation_fund'],
    'industrial decarbonisation fund': ['temporary_decarbonisation_fund'],
    # Proxy voting MEPs during pregnancy -- AFCO 2025/2195(INL)
    'proxy voting pregnancy': ['eu_equality_antidiscrimination'],
    'proxy voting meps': ['eu_equality_antidiscrimination'],
    'pregnancy proxy voting': ['eu_equality_antidiscrimination'],
    'afco proxy vote': ['eu_equality_antidiscrimination'],
    '2025/2195': ['eu_equality_antidiscrimination'],
    'european electoral act amendment': ['eu_equality_antidiscrimination'],
    'mep maternity proxy': ['eu_equality_antidiscrimination'],
    # Virtual Worlds Observatory (22 April 2026, DG CNECT)
    'virtual worlds observatory': ['digital_networks_act'],
    'metaverse observatory': ['digital_networks_act'],
    'virtual worlds eu': ['digital_networks_act'],
    'xr observatory': ['digital_networks_act'],
    # Combined COVID-19 + influenza vaccine (22 April 2026, DG SANTE)
    'combined covid influenza vaccine': ['pharma_sector_regulatory_landscape'],
    'combined covid flu vaccine': ['pharma_sector_regulatory_landscape'],
    'combined covid-19 influenza vaccine': ['pharma_sector_regulatory_landscape'],
    'first combined covid influenza': ['pharma_sector_regulatory_landscape'],
    'dual covid flu vaccine': ['pharma_sector_regulatory_landscape'],
    # Petersberg Climate Dialogue (17th, 22 April 2026, Hoekstra)
    'petersberg climate dialogue': ['iran_strait_hormuz_eu_response', 'eu_energy_policy'],
    '17th petersberg climate': ['iran_strait_hormuz_eu_response'],
    'hoekstra petersberg': ['iran_strait_hormuz_eu_response', 'eu_energy_policy'],
    # EU-Mexico Partnership modernisation (AFET+INTA joint amendments, 21 April 2026)
    'eu-mexico partnership': ['eu_trade_policy', 'eu_trade_defence'],
    'eu mexico partnership': ['eu_trade_policy', 'eu_trade_defence'],
    'eu-mexico interim trade': ['eu_trade_policy', 'eu_trade_defence'],
    'mexico strategic partnership': ['eu_trade_policy', 'eu_trade_defence'],
    'gimenez larraz': ['eu_trade_policy', 'eu_trade_defence'],
    'giménez larraz': ['eu_trade_policy', 'eu_trade_defence'],
    'borja gimenez': ['eu_trade_policy', 'eu_trade_defence'],
    'javi lopez mexico': ['eu_trade_policy', 'eu_trade_defence'],
    'pe787.714': ['eu_trade_policy', 'eu_trade_defence'],
    'pe787.663': ['eu_trade_policy', 'eu_trade_defence'],
    # ECI Ban on conversion practices -- LIBE 2026/2539(RSP)
    'ban on conversion practices': ['eu_equality_antidiscrimination'],
    'conversion practices eci': ['eu_equality_antidiscrimination'],
    'conversion therapy ban': ['eu_equality_antidiscrimination'],
    '2026/2539': ['eu_equality_antidiscrimination'],
    'eci conversion practices': ['eu_equality_antidiscrimination'],
    # RRF ECA traceability (COM(2026) 179, 22 April 2026)
    'com(2026) 179': ['eu_recovery_resilience_facility'],
    'com 2026 179': ['eu_recovery_resilience_facility'],
    'rrf traceability': ['eu_recovery_resilience_facility', 'eu_budget_emu_law'],
    'rrf transparency': ['eu_recovery_resilience_facility', 'eu_budget_emu_law'],
    'eca rrf special report': ['eu_recovery_resilience_facility', 'eu_budget_emu_law'],
    # Pension costs addendum (SWD(2026) 124)
    'swd(2026) 124': ['eu_budget_emu_law'],
    'eurostat pension study': ['eu_budget_emu_law'],
    'long-term pension costs eu': ['eu_budget_emu_law'],
    'long term pension costs': ['eu_budget_emu_law'],
    # Google AI Summaries / Overviews publishers (22 April 2026, IUST_BRI 787211)
    'google ai summaries': ['dsa_enforcement'],
    'google ai overviews': ['dsa_enforcement'],
    'ai search publishers': ['dsa_enforcement'],
    'search generative experience': ['dsa_enforcement'],
    'iust_bri(2026)787211': ['dsa_enforcement'],
    'ai summaries publishers revenue': ['dsa_enforcement'],
    # China economic challenge briefing (22 April 2026)
    "china's economic challenge": ['eu_trade_policy', 'eu_competitiveness_council_debate'],
    'china economic challenge': ['eu_trade_policy', 'eu_competitiveness_council_debate'],
    # CO2 emission standards cars and vans (22 April 2026, EPRS_BRI 774751)
    'co2 emission standards cars': ['eu_energy_policy', 'eu_competitiveness_council_debate'],
    'co2 emission standards vans': ['eu_energy_policy', 'eu_competitiveness_council_debate'],
    'regulation 2019/631': ['eu_energy_policy', 'eu_competitiveness_council_debate'],
    'cars vans co2': ['eu_energy_policy', 'eu_competitiveness_council_debate'],
    # Natural disasters post-2027 MFF adequacy (BUDG_ATA 785762)
    'natural disasters mff': ['mff_2028_2034'],
    'budg_ata(2026)785762': ['mff_2028_2034'],
    'budget natural disasters': ['mff_2028_2034'],
    'solidarity fund post-2027': ['mff_2028_2034'],
    # European energy grids package briefing (EPRS_BRI(2026)774752)
    'eprs_bri(2026)774752': ['energy_grids_package'],
    'eprs_bri(2026)774751': ['eu_energy_policy', 'eu_competitiveness_council_debate'],
    # Eurostat drought 2024
    'drought 2024 eu': ['eurostat_statistics_production', 'common_agricultural_policy'],
    '156703 km drought': ['eurostat_statistics_production', 'common_agricultural_policy'],
    'eurostat drought': ['eurostat_statistics_production', 'common_agricultural_policy'],
    # Cyprus informal EUCO 23-24 April
    'cyprus informal euco': ['iran_strait_hormuz_eu_response', 'mff_2028_2034'],
    'cyprus informal european council': ['iran_strait_hormuz_eu_response', 'mff_2028_2034'],
    'informal leaders meeting cyprus': ['iran_strait_hormuz_eu_response', 'mff_2028_2034'],
    # Cohesion MTR DG REGIO 22 April
    'cohesion mtr results': ['cohesion_policy_midterm_review'],
    'mid-term review cohesion': ['cohesion_policy_midterm_review'],
    'mtr cohesion policy': ['cohesion_policy_midterm_review'],
    # FPI Great Lakes 22 April
    'great lakes region eu': ['eu_special_representatives'],
    'fpi great lakes': ['eu_special_representatives'],
    'johan borgstam': ['eu_special_representatives'],
    # Armenian parliamentary election EOM
    'armenian parliamentary election': ['eu_special_representatives'],
    'janez lenarcic armenia': ['eu_special_representatives'],
    'osce election observation armenia': ['eu_special_representatives'],
    # ========================================================================
    # 24 April 2026 -- Friday week-ahead + plenary 27-30 April verified items
    # ========================================================================
    # Better Regulation and Enforcement Communication (College 28 April + plenary item 109)
    'better regulation and enforcement': ['better_regulation_enforcement_communication'],
    'better regulation communication': ['better_regulation_enforcement_communication'],
    'better regulation enforcement': ['better_regulation_enforcement_communication'],
    'simplification communication': ['better_regulation_enforcement_communication'],
    'dombrovskis simplification': ['better_regulation_enforcement_communication'],
    'implementation and simplification portfolio': ['better_regulation_enforcement_communication'],
    'omnibus files simplification': ['better_regulation_enforcement_communication'],
    'reduccion cargas administrativas ue': ['better_regulation_enforcement_communication'],
    'simplification ue reglementaire': ['better_regulation_enforcement_communication'],
    'millora regulatoria ue': ['better_regulation_enforcement_communication'],
    # Commission Rule of Law Report 2025 (plenary item 88)
    'rule of law report 2025': ['commission_rule_of_law_report_2025'],
    'commission rule of law report': ['commission_rule_of_law_report_2025'],
    'arvanitis rule of law': ['commission_rule_of_law_report_2025'],
    'annual rule of law cycle': ['commission_rule_of_law_report_2025'],
    'rule of law country chapters': ['commission_rule_of_law_report_2025'],
    'rapport etat de droit 2025': ['commission_rule_of_law_report_2025'],
    'informe estado de derecho 2025': ['commission_rule_of_law_report_2025'],
    'informe estat dret 2025': ['commission_rule_of_law_report_2025'],
    # International Claims Commission Ukraine (plenary consent vote 28 April)
    'international claims commission for ukraine': ['international_claims_commission_ukraine'],
    'international claims commission ukraine': ['international_claims_commission_ukraine'],
    'iccu convention': ['international_claims_commission_ukraine'],
    'claims commission ukraine': ['international_claims_commission_ukraine'],
    'register of damage ukraine': ['international_claims_commission_ukraine'],
    'rd4u': ['international_claims_commission_ukraine'],
    'reykjavik declaration ukraine': ['international_claims_commission_ukraine'],
    'compensation fund ukraine': ['international_claims_commission_ukraine'],
    'hague convention ukraine claims': ['international_claims_commission_ukraine'],
    'comision reclamaciones ucrania': ['international_claims_commission_ukraine'],
    'commissio reclamacions ucraina': ['international_claims_commission_ukraine'],
    # EP Fundamental Rights Report 2024-2025 Strolenberg (plenary item 26)
    'strolenberg fundamental rights': ['fundamental_rights_report_ep_2024_2025'],
    'fundamental rights report 2024 2025': ['fundamental_rights_report_ep_2024_2025'],
    'ep fundamental rights report': ['fundamental_rights_report_ep_2024_2025'],
    'situation fundamental rights eu': ['fundamental_rights_report_ep_2024_2025'],
    'libe fundamental rights ini': ['fundamental_rights_report_ep_2024_2025'],
    'anna strolenberg': ['fundamental_rights_report_ep_2024_2025'],
    # EU Law Application Monitoring Zalimas (plenary item 111)
    'eu law application monitoring': ['eu_law_application_monitoring'],
    'monitoring application of union law': ['eu_law_application_monitoring'],
    'article 258 tfeu infringement': ['eu_law_application_monitoring'],
    'article 260 tfeu penalties': ['eu_law_application_monitoring'],
    'infringement procedures eu': ['eu_law_application_monitoring'],
    'zalimas eu law application': ['eu_law_application_monitoring'],
    'late transposition directives': ['eu_law_application_monitoring'],
    'single market scoreboard transposition': ['eu_law_application_monitoring'],
    'eu pilot infringement': ['eu_law_application_monitoring'],
    'procedure infractions ue': ['eu_law_application_monitoring'],
    'procedimientos infraccion ue': ['eu_law_application_monitoring'],
    'procediments infraccio ue': ['eu_law_application_monitoring'],
    # Farmed fish welfare (DG SANTE 23 April report)
    'farmed fish welfare': ['farmed_fish_welfare_eu'],
    'fish welfare aquaculture': ['farmed_fish_welfare_eu'],
    'fish slaughter welfare': ['farmed_fish_welfare_eu'],
    'fish sentience eu': ['farmed_fish_welfare_eu'],
    'dg sante farmed fish': ['farmed_fish_welfare_eu'],
    'bienestar peces granja': ['farmed_fish_welfare_eu'],
    'benestar peixos cultiu': ['farmed_fish_welfare_eu'],
    'bien-etre poissons elevage': ['farmed_fish_welfare_eu'],
    'aquaculture animal welfare eu': ['farmed_fish_welfare_eu'],
    'regulation 1099 2009 fish': ['farmed_fish_welfare_eu'],
    # EU Aviation + Aeronautics Strategy consultation (DG MOVE 24 April)
    'eu aviation aeronautics strategy': ['aviation_transport_policy'],
    'aviation and aeronautics strategy': ['aviation_transport_policy'],
    'dg move aviation strategy': ['aviation_transport_policy'],
    'aeronautics industrial policy eu': ['aviation_transport_policy'],
    'estrategia aviacion aeronautica ue': ['aviation_transport_policy'],
    'estrategia aviacio aeronautica ue': ['aviation_transport_policy'],
    # EU Interinstitutional Relations guide (AFCO package 24 April)
    'interinstitutional agreement eu': ['eu_interinstitutional_relations'],
    'iia better law making': ['eu_interinstitutional_relations'],
    'iia budgetary discipline': ['eu_interinstitutional_relations', 'eu_budget_emu_law'],
    'framework agreement ep commission': ['eu_interinstitutional_relations'],
    'rule 135 ep rules of procedure': ['eu_interinstitutional_relations'],
    'ep agency appointments': ['eu_interinstitutional_relations'],
    'article 19 teu judicial independence': ['eu_interinstitutional_relations', 'commission_rule_of_law_report_2025'],
    '2025/2159(aci)': ['eu_interinstitutional_relations', 'mff_2028_2034'],
    '2025/2243(aci)': ['eu_interinstitutional_relations'],
    '2025/2262(reg)': ['eu_interinstitutional_relations'],
    '2025/2263(ini)': ['eu_interinstitutional_relations'],
    'proxy voting pregnancy mep': ['eu_interinstitutional_relations'],
    '2025/2195(inl)': ['eu_interinstitutional_relations', 'eu_equality_antidiscrimination'],
    'european electoral act proxy voting': ['eu_interinstitutional_relations'],
    'acord interinstitucional ue': ['eu_interinstitutional_relations'],
    'acuerdo interinstitucional ue': ['eu_interinstitutional_relations'],
    'accord interinstitutionnel ue': ['eu_interinstitutional_relations'],
    # Ukraine Zelenskyy Brussels visit 23 April (Costa + VdL joint statement)
    'zelenskyy brussels 23 april': ['ukraine_children_deportation', 'iran_strait_hormuz_eu_response'],
    'costa von der leyen zelenskyy': ['ukraine_children_deportation', 'iran_strait_hormuz_eu_response'],
    'statement 26 868': ['ukraine_children_deportation'],
    'statement 26 875': ['ukraine_children_deportation'],
    'eu solidarity ukraine factsheet': ['ukraine_children_deportation'],
    # Discharge 2024 Freund (plenary item 66)
    'discharge 2024 ep': ['eu_budget_emu_law'],
    'daniel freund discharge': ['eu_budget_emu_law'],
    '2024 discharge commission': ['eu_budget_emu_law'],
    'joint debate discharge 2024': ['eu_budget_emu_law'],
    # Russia attacks Ukraine civilians accountability (plenary item 112)
    'russia attacks ukraine civilians': ['iran_strait_hormuz_eu_response', 'international_claims_commission_ukraine'],
    'russia ukraine civilians accountability': ['international_claims_commission_ukraine'],
    # DMA enforcement plenary debate (item 119)
    'dma enforcement plenary': ['dsa_enforcement'],
    'cavazzini schwab dma': ['dsa_enforcement'],
    'digital markets act enforcement debate': ['dsa_enforcement'],
    # Armenia democratic resilience (plenary item 8)
    'armenia democratic resilience': ['eu_special_representatives'],
    'armenia parliamentary election eu': ['eu_special_representatives'],
    # Poland 4th NGEU payment 23 April
    'poland fourth ngeu payment': ['eu_recovery_resilience_facility'],
    'poland 7.2 billion ngeu': ['eu_recovery_resilience_facility'],
    'poland rrf fourth instalment': ['eu_recovery_resilience_facility'],
    # Eurostat 23 April releases
    'eurostat digitalisation europe': ['eurostat_statistics_production'],
    'eu aquaculture 1 million tonnes': ['eurostat_statistics_production', 'farmed_fish_welfare_eu'],
    'girls digital skills coding': ['eurostat_statistics_production'],
    'e-books audio books 2025': ['eurostat_statistics_production'],
    # DG REGIO 23 April signals
    'bilbao cities forum 2027': ['cohesion_policy_midterm_review'],
    'euregionsweek 2026 call': ['cohesion_policy_midterm_review'],
    'youth4regions 2026': ['cohesion_policy_midterm_review'],
    'neb boost small municipalities': ['cohesion_policy_midterm_review'],
    'smart regions denmark drones': ['cohesion_policy_midterm_review'],
    'atlantic geological risks': ['cohesion_policy_midterm_review'],
    'fitto belgian government regions': ['cohesion_policy_midterm_review'],
    # === 29 April 2026 daily news additions ===
    # MFF 2028-2034 plenary vote + Serafin debate
    'mff 1.26 percent gni': ['mff_2028_2034'],
    'mff 1.27 percent gni': ['mff_2028_2034'],
    'serafin mff debate': ['mff_2028_2034'],
    'speech 26 922': ['mff_2028_2034'],
    'mff external border factor four': ['mff_2028_2034'],
    'mff plenary vote 29 april': ['mff_2028_2034'],
    'national regional partnership plans': ['mff_2028_2034', 'cohesion_policy_midterm_review'],
    'nrrp flexibility cohesion': ['mff_2028_2034'],
    # Better Regulation Communication 28 April
    'simplicity by design': ['better_regulation_enforcement_communication'],
    'enforcement by design': ['better_regulation_enforcement_communication'],
    'qanda 26 902': ['better_regulation_enforcement_communication'],
    'fs 26 903': ['better_regulation_enforcement_communication'],
    'speech 26 915': ['better_regulation_enforcement_communication'],
    'speech 26 916': ['better_regulation_enforcement_communication'],
    'simpler clearer better enforced eu rulebook': ['better_regulation_enforcement_communication'],
    'rulebook simplification': ['better_regulation_enforcement_communication'],
    'reglas mas simples eu': ['better_regulation_enforcement_communication'],
    'reglement plus simple ue': ['better_regulation_enforcement_communication'],
    'normativa europea mes simple': ['better_regulation_enforcement_communication'],
    'regole ue piu semplici': ['better_regulation_enforcement_communication'],
    'eenvoudigere eu regels': ['better_regulation_enforcement_communication'],
    # DMA Review 28 April
    'dma review fit for purpose': ['digital_markets_act'],
    'dma review 2026 commission': ['digital_markets_act'],
    'dma positive impact review': ['digital_markets_act'],
    'review highlights dma fit purpose': ['digital_markets_act'],
    'revision dma 2026 comision': ['digital_markets_act'],
    'revisione dma 2026': ['digital_markets_act'],
    'revisao dma 2026': ['digital_markets_act'],
    'dma herziening 2026': ['digital_markets_act'],
    # EU asylum applications 27% drop in 2025
    'eu asylum drop 27 percent 2025': ['eu_migration_asylum_pact'],
    '669400 asylum applicants 2025': ['eu_migration_asylum_pact'],
    'venezuela top asylum origin eu': ['eu_migration_asylum_pact'],
    'venezuela 89500 asylum applicants': ['eu_migration_asylum_pact'],
    'first time asylum applicants 2025': ['eu_migration_asylum_pact'],
    'unaccompanied minors asylum 2025': ['eu_migration_asylum_pact'],
    'spain top asylum destination 2025': ['eu_migration_asylum_pact'],
    'eu pact migration deadline 12 june 2026': ['eu_migration_asylum_pact'],
    'caida solicitudes asilo ue 2025': ['eu_migration_asylum_pact'],
    'baisse demandes asile ue 2025': ['eu_migration_asylum_pact'],
    'caiguda peticions asil ue 2025': ['eu_migration_asylum_pact'],
    'calo richieste asilo ue 2025': ['eu_migration_asylum_pact'],
    'daling asielaanvragen eu 2025': ['eu_migration_asylum_pact'],
    # Common Defence Union 2025/2212(INI)
    '2025/2212(ini)': ['european_defence_union'],
    'institutional aspects defence union': ['european_defence_union'],
    'niclas herbst sede rapporteur': ['european_defence_union'],
    'salvatore de meo afco defence': ['european_defence_union'],
    'common defence union institutional': ['european_defence_union'],
    'aspectos institucionales union defensa': ['european_defence_union'],
    'aspects institutionnels union defense': ['european_defence_union'],
    'aspetti istituzionali unione difesa': ['european_defence_union'],
    'aspectes institucionals unio defensa': ['european_defence_union'],
    'institutionele aspecten verdedigingsunie': ['european_defence_union'],
    # Cohesion Policy MTR / PSLF / EPRS REGI study
    'pslf first call results': ['cohesion_policy_midterm_review'],
    'public sector loan facility 19 projects': ['cohesion_policy_midterm_review'],
    'pslf 210 million grants': ['cohesion_policy_midterm_review'],
    'flexibility simplification cohesion policy': ['cohesion_policy_midterm_review'],
    'eprs regi flexibility cohesion': ['cohesion_policy_midterm_review'],
    'pslf primera convocatoria': ['cohesion_policy_midterm_review'],
    'pslf premier appel': ['cohesion_policy_midterm_review'],
    'pslf prima convocazione': ['cohesion_policy_midterm_review'],
    # CAP 2028-2034 sustainable farming guidance
    'cap 2028 2034 sustainable farming': ['common_agricultural_policy'],
    'driving sustainable farming guidance': ['common_agricultural_policy'],
    'pac 2028 2034 agricultura sostenible': ['common_agricultural_policy'],
    'pac 2028 2034 agriculture durable': ['common_agricultural_policy'],
    'pac 2028 2034 agricoltura sostenibile': ['common_agricultural_policy'],
    'pac 2028 2034 agricultura sostenible cat': ['common_agricultural_policy'],
    'glb 2028 2034 duurzame landbouw': ['common_agricultural_policy'],
    # Mercosur T-2 days
    'mercosur 1 mai 2026': ['eu_mercosur_trade_agreement'],
    'mercosur 1 may 2026': ['eu_mercosur_trade_agreement'],
    'mercosur t minus 2': ['eu_mercosur_trade_agreement'],
    'mercosur access2markets rosa': ['eu_mercosur_trade_agreement'],
    # DG MARE fishing fleet study
    'dg mare fleet capacity study': ['eu_fisheries_control'],
    'fishing fleet sustainability 2026': ['eu_fisheries_control'],
    'cfp evaluation fleet capacity': ['eu_fisheries_control'],
    'estudio flota pesquera ue': ['eu_fisheries_control'],
    'etude flotte peche ue': ['eu_fisheries_control'],
    'studio flotta pesca ue': ['eu_fisheries_control'],
    # Climate / Copernicus warming
    'copernicus europe warming 2026': ['european_climate_law'],
    'europe warming faster global trend': ['european_climate_law'],
    'european state of climate report': ['european_climate_law'],
    'calentamiento europa supera global': ['european_climate_law'],
    'rechauffement europe au-dela tendance mondiale': ['european_climate_law'],
    'riscaldamento europa supera tendenza globale': ['european_climate_law'],
    # Australia EPRS briefing 28 April
    'australia eu engagement briefing 2026': ['eu_australia_trade_agreement'],
    'eprs australia current landscape': ['eu_australia_trade_agreement'],
    # Firearms Trafficking 2026/0059(COD)
    '2026/0059(cod)': ['firearms_trafficking_eu'],
    'firearms trafficking eu regulation': ['firearms_trafficking_eu'],
    'combating firearms trafficking eu': ['firearms_trafficking_eu'],
    'evin incir libe firearms': ['firearms_trafficking_eu'],
    'com 2026 102': ['firearms_trafficking_eu'],
    'sec 2026 102': ['firearms_trafficking_eu'],
    'trafico armas fuego ue': ['firearms_trafficking_eu'],
    'trafic armes feu ue': ['firearms_trafficking_eu'],
    'traffico armi da fuoco ue': ['firearms_trafficking_eu'],
    'trafic armes foc ue': ['firearms_trafficking_eu'],
    'wapenhandel eu regelgeving': ['firearms_trafficking_eu'],
    # Consular Protection ETD 2023/0441(CNS)
    '2023/0441(cns)': ['consular_protection_eu_etd'],
    'consular protection unrepresented eu citizens': ['consular_protection_eu_etd'],
    'eu emergency travel document': ['consular_protection_eu_etd'],
    'directive 2015 637 consular': ['consular_protection_eu_etd'],
    'directive 2019 997 etd': ['consular_protection_eu_etd'],
    'proteccion consular ciudadanos ue': ['consular_protection_eu_etd'],
    'documento viaje provisional ue': ['consular_protection_eu_etd'],
    'protection consulaire citoyens ue': ['consular_protection_eu_etd'],
    'document voyage urgence ue': ['consular_protection_eu_etd'],
    'protezione consolare cittadini ue': ['consular_protection_eu_etd'],
    'documento viaggio emergenza ue': ['consular_protection_eu_etd'],
    'proteccio consular ciutadans ue': ['consular_protection_eu_etd'],
    'consulaire bescherming eu burgers': ['consular_protection_eu_etd'],
    # Proxy voting EP 2025/2195(INL)
    'lopez aguilar proxy voting ep': ['ep_proxy_voting_pregnancy'],
    'proxy voting plenary pregnancy': ['ep_proxy_voting_pregnancy'],
    'european electoral act amendment proxy': ['ep_proxy_voting_pregnancy'],
    'voto delegado embarazo eurocamara': ['ep_proxy_voting_pregnancy'],
    'vote procuration grossesse parlement europeen': ['ep_proxy_voting_pregnancy'],
    'voto delega gravidanza parlamento europeo': ['ep_proxy_voting_pregnancy'],
    'vot delegat embaras parlament europeu': ['ep_proxy_voting_pregnancy'],
    'volmacht stem ep zwangerschap': ['ep_proxy_voting_pregnancy'],
    # EP-EC Framework Agreement 2025/2243(ACI)
    '2025/2243(aci)': ['ep_ec_framework_agreement_2026'],
    'framework agreement ep commission': ['ep_ec_framework_agreement_2026'],
    'ep commission framework agreement 2010': ['ep_ec_framework_agreement_2026'],
    'acuerdo marco pe comision': ['ep_ec_framework_agreement_2026'],
    'accord cadre pe commission': ['ep_ec_framework_agreement_2026'],
    'accordo quadro pe commissione': ['ep_ec_framework_agreement_2026'],
    'acord marc pe comissio': ['ep_ec_framework_agreement_2026'],
    'kaderakkoord ep commissie': ['ep_ec_framework_agreement_2026'],
    # Passerelle 2026/2012(INI)
    '2026/2012(ini)': ['eu_decision_making_passerelle_clauses'],
    'passerelle clauses eu treaties': ['eu_decision_making_passerelle_clauses'],
    'article 48 7 teu passerelle': ['eu_decision_making_passerelle_clauses'],
    'enhanced eu decision making treaties': ['eu_decision_making_passerelle_clauses'],
    'qmv unanimity passerelle': ['eu_decision_making_passerelle_clauses'],
    'clausulas pasarela tratados ue': ['eu_decision_making_passerelle_clauses'],
    'clauses passerelles traites ue': ['eu_decision_making_passerelle_clauses'],
    'clausole passerella trattati ue': ['eu_decision_making_passerelle_clauses'],
    'clausules passarela tractats ue': ['eu_decision_making_passerelle_clauses'],
    'overbruggingsclausules eu verdragen': ['eu_decision_making_passerelle_clauses'],
    # Battery removability consultation
    'battery removability exemptions consultation': ['battery_regulation_removability_consultation'],
    'article 11 batteries regulation removability': ['battery_regulation_removability_consultation'],
    '32023r1542 article 11': ['battery_regulation_removability_consultation'],
    'lmt battery replaceability': ['battery_regulation_removability_consultation'],
    'consulta extraibilidad pilas ue': ['battery_regulation_removability_consultation'],
    'consultation amovibilite piles ue': ['battery_regulation_removability_consultation'],
    'consultazione rimovibilita batterie ue': ['battery_regulation_removability_consultation'],
    'consulta extraibilitat piles ue': ['battery_regulation_removability_consultation'],
    'consultatie verwijderbaarheid batterijen eu': ['battery_regulation_removability_consultation'],
    # === AI & Sustainability framework (added 29 April 2026, primed for 12 May daily brief) ===
    'ai sustainability eu framework': ['ai_sustainability_eu_framework'],
    'ai environmental impact eu': ['ai_sustainability_eu_framework'],
    'is ai and sustainability compatible': ['ai_sustainability_eu_framework'],
    'ai sustainability compatible eu': ['ai_sustainability_eu_framework'],
    'ai data centres energy reporting': ['ai_sustainability_eu_framework'],
    'data centre 1 mw threshold reporting': ['ai_sustainability_eu_framework'],
    'eed article 12 data centres': ['ai_sustainability_eu_framework'],
    'delegated regulation 2024 1364': ['ai_sustainability_eu_framework'],
    'eu code of conduct data centre energy efficiency': ['ai_sustainability_eu_framework'],
    'ai act recital 142 environmental': ['ai_sustainability_eu_framework'],
    'ai act article 95 codes of conduct sustainability': ['ai_sustainability_eu_framework'],
    'gpai energy water disclosure': ['ai_sustainability_eu_framework'],
    'cloud and ai development act 27 may 2026': ['ai_sustainability_eu_framework'],
    'tech sovereignty package 27 may': ['ai_sustainability_eu_framework'],
    'strategic roadmap digitalisation ai energy': ['ai_sustainability_eu_framework'],
    'csrd esrs e1 ai compute': ['ai_sustainability_eu_framework'],
    'critical raw materials gallium gpu ai': ['ai_sustainability_eu_framework'],
    'investai gigafactories sustainability': ['ai_sustainability_eu_framework'],
    'ai compliance compute footprint eu': ['ai_sustainability_eu_framework'],
    'pue wue ere data centre': ['ai_sustainability_eu_framework'],
    # ES
    'ia y sostenibilidad ue': ['ai_sustainability_eu_framework'],
    'huella ambiental ia ue': ['ai_sustainability_eu_framework'],
    'centros datos consumo energia ue': ['ai_sustainability_eu_framework'],
    'ley nube ia ue 27 mayo': ['ai_sustainability_eu_framework'],
    # FR
    'ia et durabilite ue': ['ai_sustainability_eu_framework'],
    'empreinte environnementale ia ue': ['ai_sustainability_eu_framework'],
    'centres donnees consommation energie ue': ['ai_sustainability_eu_framework'],
    'loi cloud et ia ue 27 mai': ['ai_sustainability_eu_framework'],
    # IT
    'ia e sostenibilita ue': ['ai_sustainability_eu_framework'],
    'impronta ambientale ia ue': ['ai_sustainability_eu_framework'],
    'centri dati consumo energia ue': ['ai_sustainability_eu_framework'],
    # CA
    'ia i sostenibilitat ue': ['ai_sustainability_eu_framework'],
    'petjada ambiental ia ue': ['ai_sustainability_eu_framework'],
    'centres dades consum energia ue': ['ai_sustainability_eu_framework'],
    # NL
    'ai en duurzaamheid eu': ['ai_sustainability_eu_framework'],
    'milieu impact ai eu': ['ai_sustainability_eu_framework'],
    'datacenters energie verbruik eu': ['ai_sustainability_eu_framework'],
    # === EC Transparency Register documents (29 April 2026) ===
    'sec 2026 2564': ['better_regulation_enforcement_communication', 'ai_sustainability_eu_framework'],
    'oj 2026 2564': ['better_regulation_enforcement_communication'],
    'commission age verification recommendation 28 april 2026': ['eu_age_verification_recommendation', 'csam_regulation_online', 'dsa_enforcement'],
    'eu wide age verification framework': ['eu_age_verification_recommendation', 'csam_regulation_online'],
    'eu age verification app': ['eu_age_verification_recommendation'],
    'eu age verification blueprint': ['eu_age_verification_recommendation'],
    'zero knowledge proof age verification': ['eu_age_verification_recommendation'],
    'eudi wallet age proof': ['eu_age_verification_recommendation'],
    'age 16 verification eu': ['eu_age_verification_recommendation'],
    'age 18 verification eu pornography': ['eu_age_verification_recommendation'],
    'dsa article 28 age verification': ['eu_age_verification_recommendation', 'dsa_enforcement'],
    'common framework age verification technologies': ['eu_age_verification_recommendation'],
    'verificacion edad ue': ['eu_age_verification_recommendation'],
    'verification age ue': ['eu_age_verification_recommendation'],
    'verifica eta ue': ['eu_age_verification_recommendation'],
    'verificacio edat ue': ['eu_age_verification_recommendation'],
    'leeftijdsverificatie eu': ['eu_age_verification_recommendation'],
    'fertilisers action plan 13 may 2026': ['fertilisers_action_plan_2026'],
    'fertilisers action plan eu': ['fertilisers_action_plan_2026'],
    'fertilizer action plan eu': ['fertilisers_action_plan_2026'],
    'eu fertiliser strategy hansen': ['fertilisers_action_plan_2026'],
    'high level dialogue fertilisers april 2026': ['fertilisers_action_plan_2026'],
    'green ammonia eu fertiliser': ['fertilisers_action_plan_2026'],
    'circular mineral fertilisers eu': ['fertilisers_action_plan_2026'],
    'nitrogen fertiliser cost spike iran war': ['fertilisers_action_plan_2026'],
    'plan accion fertilizantes ue': ['fertilisers_action_plan_2026'],
    'plan action fertilisants ue': ['fertilisers_action_plan_2026'],
    'piano azione fertilizzanti ue': ['fertilisers_action_plan_2026'],
    'pla accio fertilitzants ue': ['fertilisers_action_plan_2026'],
    'meststoffen actieplan eu': ['fertilisers_action_plan_2026'],
    'stop destroying videogames eci response': ['ai_sustainability_eu_framework'],
    # === Commission DG reshuffle 29 April 2026 (Trade/Energy/Adviser swap) ===
    'celine gauer dg ener': ['eu_energy_policy', 'accelerateeu_fossil_energy_crisis'],
    'ditte juul jorgensen dg trade': ['eu_trade_policy', 'eu_gsp_new_generation'],
    'ditte juul jorgensen dg energy': ['eu_energy_policy', 'accelerateeu_fossil_energy_crisis'],
    'sabine weyand special adviser': ['eu_trade_policy'],
    'sabine weyand reassigned': ['eu_trade_policy'],
    'commission dg reshuffle 29 april 2026': ['eu_trade_policy', 'eu_energy_policy'],
    'new director general dg trade': ['eu_trade_policy'],
    'new director general dg ener': ['eu_energy_policy'],
    'dg trade leadership change': ['eu_trade_policy'],
    'dg ener leadership change': ['eu_energy_policy'],
    'reorganisation comision dg ener dg trade': ['eu_energy_policy', 'eu_trade_policy'],
    'remaniement dg ener dg trade': ['eu_energy_policy', 'eu_trade_policy'],
    'rimpasto dg ener dg trade': ['eu_energy_policy', 'eu_trade_policy'],
    'reorganitzacio dg ener dg trade': ['eu_energy_policy', 'eu_trade_policy'],
    'herschikking dg ener dg trade': ['eu_energy_policy', 'eu_trade_policy'],
    # === CELEX number format (added 29 April 2026) ===
    'celex number format': ['celex_number_format'],
    'celex number structure': ['celex_number_format'],
    'what is a celex number': ['celex_number_format'],
    'celex sector year type number': ['celex_number_format'],
    'celex 12 sectors': ['celex_number_format'],
    'celex regex pattern': ['celex_number_format'],
    'celex document type descriptor': ['celex_number_format'],
    'celex sector 3 legal acts': ['celex_number_format'],
    'celex sector 5 preparatory': ['celex_number_format'],
    'celex sector 6 case law': ['celex_number_format'],
    'celex sector 7 national transposition': ['celex_number_format'],
    'consolidated text celex 0': ['celex_number_format'],
    'com to celex conversion': ['celex_number_format'],
    'cellar url celex': ['celex_number_format'],

    # --- EU data, identifiers & institutions cluster (added 25 May 2026 from api_leg.md + api_ep.md) ---
    'how to find eu law': ['finding_and_citing_eu_law'],
    'how to cite eu law': ['finding_and_citing_eu_law'],
    'how to cite a regulation': ['finding_and_citing_eu_law'],
    'where eu law is published': ['finding_and_citing_eu_law'],
    'eur-lex vs cellar': ['finding_and_citing_eu_law'],
    'machine readable eu law': ['finding_and_citing_eu_law'],
    'como citar legislacion europea': ['finding_and_citing_eu_law'],
    'comment citer le droit europeen': ['finding_and_citing_eu_law'],
    'eli identifier': ['eli_european_legislation_identifier'],
    'european legislation identifier': ['eli_european_legislation_identifier'],
    'what is eli': ['eli_european_legislation_identifier'],
    'eli uri': ['eli_european_legislation_identifier'],
    'data europa eli': ['eli_european_legislation_identifier'],
    'identificador europeo de legislacion': ['eli_european_legislation_identifier'],
    'ecli identifier': ['ecli_european_case_law_identifier'],
    'european case law identifier': ['ecli_european_case_law_identifier'],
    'what is ecli': ['ecli_european_case_law_identifier'],
    'how to cite a cjeu judgment': ['ecli_european_case_law_identifier'],
    'cite court of justice ruling': ['ecli_european_case_law_identifier'],
    'official journal explained': ['official_journal_explained'],
    'official journal series l and c': ['official_journal_explained'],
    'act by act publication': ['official_journal_explained'],
    'e-oj authentic': ['official_journal_explained'],
    'how eu law is published': ['official_journal_explained'],
    'diario oficial de la union europea': ['official_journal_explained'],
    'journal officiel union europeenne': ['official_journal_explained'],
    'ordinary legislative procedure': ['eu_legislative_procedures_explained'],
    'special legislative procedure': ['eu_legislative_procedures_explained'],
    'codecision procedure': ['eu_legislative_procedures_explained'],
    'consultation procedure': ['eu_legislative_procedures_explained'],
    'consent procedure': ['eu_legislative_procedures_explained'],
    'delegated acts vs implementing acts': ['eu_legislative_procedures_explained'],
    'non-legislative procedure': ['eu_legislative_procedures_explained'],
    'procedimiento legislativo ordinario': ['eu_legislative_procedures_explained'],
    'procedure legislative ordinaire': ['eu_legislative_procedures_explained'],
    'eurovoc': ['eurovoc_thesaurus'],
    'eurovoc thesaurus': ['eurovoc_thesaurus'],
    'eu subject thesaurus': ['eurovoc_thesaurus'],
    'eurovoc concept': ['eurovoc_thesaurus'],
    'eurovoc keywords': ['eurovoc_thesaurus'],
    'how the european parliament works': ['european_parliament_structure'],
    'european parliament structure': ['european_parliament_structure'],
    'parliament powers legislative budgetary': ['european_parliament_structure'],
    'estructura del parlamento europeo': ['european_parliament_structure'],
    'structure du parlement europeen': ['european_parliament_structure'],
    'list of european parliament committees': ['ep_committees_overview'],
    'european parliament committees list': ['ep_committees_overview'],
    'which committee handles': ['ep_committees_overview'],
    'ep committee remits': ['ep_committees_overview'],
    'comisiones del parlamento europeo': ['ep_committees_overview'],
    'commissions du parlement europeen': ['ep_committees_overview'],
    'european parliament political groups': ['ep_political_groups_overview'],
    'ep political groups': ['ep_political_groups_overview'],
    'political groups in the european parliament': ['ep_political_groups_overview'],
    'epp s&d renew ecr greens': ['ep_political_groups_overview'],
    'patriots for europe group': ['ep_political_groups_overview'],
    'grupos politicos del parlamento europeo': ['ep_political_groups_overview'],
    'groupes politiques parlement europeen': ['ep_political_groups_overview'],
    'european parliament open data': ['ep_documents_and_open_data'],
    'ep open data api': ['ep_documents_and_open_data'],
    'data europarl': ['ep_documents_and_open_data'],
    'where ep documents live': ['ep_documents_and_open_data'],
    'doceo documents': ['ep_documents_and_open_data'],
    'cite an eu regulation': ['finding_and_citing_eu_law'],
    'cite eu legislation': ['finding_and_citing_eu_law'],
    'how do i cite': ['finding_and_citing_eu_law'],
    'act by act': ['official_journal_explained'],
    'official journal series': ['official_journal_explained'],
    'how the ep plenary works': ['ep_plenary_how_it_works'],
    'european parliament plenary': ['ep_plenary_how_it_works'],
    'plenary session european parliament': ['ep_plenary_how_it_works'],
    'how does plenary voting work': ['ep_plenary_how_it_works'],
    'roll call vote': ['ep_plenary_how_it_works'],
    'strasbourg part-session': ['ep_plenary_how_it_works'],
    'how does the ep plenary work': ['ep_plenary_how_it_works'],
    'how does the plenary work': ['ep_plenary_how_it_works'],
    'what happens in plenary': ['ep_plenary_how_it_works'],
    'ep plenary work': ['ep_plenary_how_it_works'],
    'sesion plenaria del parlamento europeo': ['ep_plenary_how_it_works'],
    'session pleniere du parlement europeen': ['ep_plenary_how_it_works'],
    'european parliament intergroups': ['ep_intergroups_and_delegations'],
    'ep intergroups': ['ep_intergroups_and_delegations'],
    'european parliament delegations': ['ep_intergroups_and_delegations'],
    'interparliamentary delegations': ['ep_intergroups_and_delegations'],
    'which delegation handles': ['ep_intergroups_and_delegations'],
    'intergrupos del parlamento europeo': ['ep_intergroups_and_delegations'],
    'delegations du parlement europeen': ['ep_intergroups_and_delegations'],
    'powers of the european parliament': ['european_parliament_powers'],
    'what can the european parliament do': ['european_parliament_powers'],
    'european parliament powers': ['european_parliament_powers'],
    'can the european parliament block': ['european_parliament_powers'],
    'how does the ep control the commission': ['european_parliament_powers'],
    'poderes del parlamento europeo': ['european_parliament_powers'],
    'pouvoirs du parlement europeen': ['european_parliament_powers'],
    'european parliament elections': ['european_parliament_elections'],
    'how are meps elected': ['european_parliament_elections'],
    'european elections': ['european_parliament_elections'],
    'when are the next european elections': ['european_parliament_elections'],
    'how is the commission president elected': ['european_parliament_elections'],
    'spitzenkandidat': ['european_parliament_elections'],
    'elecciones al parlamento europeo': ['european_parliament_elections'],
    'elections europeennes': ['european_parliament_elections'],
    'eur-lex celex url': ['celex_number_format'],
    'celex 32024r1689 ai act': ['celex_number_format', 'ai_act_regulation'],
    'celex 32016r0679 gdpr': ['celex_number_format'],
    'oeil procedure vs celex': ['celex_number_format'],
    'pe number vs celex': ['celex_number_format'],
    'com number vs celex': ['celex_number_format'],
    # ES
    'numero celex formato': ['celex_number_format'],
    'estructura numero celex': ['celex_number_format'],
    'que es un celex': ['celex_number_format'],
    # FR
    'numero celex format': ['celex_number_format'],
    'structure numero celex': ['celex_number_format'],
    'qu est ce qu un celex': ['celex_number_format'],
    # IT
    'numero celex formato it': ['celex_number_format'],
    'che cos e un celex': ['celex_number_format'],
    # CA
    'numero celex format ca': ['celex_number_format'],
    'que es un numero celex catala': ['celex_number_format'],
    # NL
    'celex nummer formaat': ['celex_number_format'],
    'wat is een celex': ['celex_number_format'],

    # ============================================================
    # 30 April 2026 batch — METSAF + Meta DSA + Age Verification rollout + Better Regulation COM(2026)380 + WSR/DIWASS
    # ============================================================

    # METSAF (multilingual)
    'metsaf': ['metsaf_state_aid_middle_east'],
    'middle east crisis temporary state aid framework': ['metsaf_state_aid_middle_east'],
    'middle east state aid framework': ['metsaf_state_aid_middle_east'],
    'middle east temporary aid framework': ['metsaf_state_aid_middle_east'],
    'state aid middle east crisis': ['metsaf_state_aid_middle_east', 'accelerateeu_fossil_energy_crisis'],
    'temporary state aid framework iran war': ['metsaf_state_aid_middle_east'],
    'state aid fuel cost compensation': ['metsaf_state_aid_middle_east'],
    'state aid fertiliser cost compensation': ['metsaf_state_aid_middle_east'],
    'cisaf temporary adjustment': ['metsaf_state_aid_middle_east'],
    'eu state aid agriculture fisheries transport 2026': ['metsaf_state_aid_middle_east'],
    'ribera state aid framework': ['metsaf_state_aid_middle_east'],
    # ES
    'marco temporal ayudas estado oriente medio': ['metsaf_state_aid_middle_east'],
    'ayudas estado crisis oriente medio': ['metsaf_state_aid_middle_east'],
    'compensacion combustible fertilizantes ue': ['metsaf_state_aid_middle_east'],
    # FR
    'cadre temporaire aides etat moyen orient': ['metsaf_state_aid_middle_east'],
    'aides etat crise moyen orient': ['metsaf_state_aid_middle_east'],
    'metsaf cadre aides etat': ['metsaf_state_aid_middle_east'],
    # IT
    'quadro temporaneo aiuti stato medio oriente': ['metsaf_state_aid_middle_east'],
    'aiuti stato crisi medio oriente': ['metsaf_state_aid_middle_east'],
    # CA
    'marc temporal ajuts estat orient mitja': ['metsaf_state_aid_middle_east'],
    # NL
    'tijdelijk staatssteunkader midden oosten': ['metsaf_state_aid_middle_east'],

    # Meta DSA preliminary finding (multilingual)
    'meta dsa breach minors': ['dsa_enforcement', 'eu_age_verification_recommendation'],
    'meta instagram facebook minors under 13': ['dsa_enforcement', 'eu_age_verification_recommendation'],
    'commission preliminary finding meta': ['dsa_enforcement'],
    'ip 26 920': ['dsa_enforcement'],
    'meta digital services act under 13': ['dsa_enforcement', 'eu_age_verification_recommendation'],
    'instagram facebook age verification dsa': ['dsa_enforcement', 'eu_age_verification_recommendation'],
    # ES
    'meta menores 13 dsa': ['dsa_enforcement'],
    'instagram facebook menores europa': ['dsa_enforcement', 'eu_age_verification_recommendation'],
    # FR
    'meta mineurs 13 ans dsa': ['dsa_enforcement'],
    'instagram facebook mineurs union europeenne': ['dsa_enforcement', 'eu_age_verification_recommendation'],
    # IT
    'meta minori 13 anni dsa': ['dsa_enforcement'],
    # CA
    'meta menors 13 dsa': ['dsa_enforcement'],
    # NL
    'meta minderjarigen dsa': ['dsa_enforcement'],

    # Age Verification rollout (29 April 2026 push)
    'eu age verification rollout': ['eu_age_verification_recommendation'],
    'eu age verification scheme': ['eu_age_verification_recommendation'],
    'commission urges age verification rollout': ['eu_age_verification_recommendation'],
    'eu age verification coordination mechanism': ['eu_age_verification_recommendation'],
    'eu age verification provider list': ['eu_age_verification_recommendation'],
    'eudi wallet age verification integration': ['eu_age_verification_recommendation'],

    # Better Regulation COM(2026)380 (multilingual)
    'com 2026 380': ['better_regulation_enforcement_communication'],
    'simpler clearer better enforced eu rulebook': ['better_regulation_enforcement_communication'],
    'regulatory deep cleaning': ['better_regulation_enforcement_communication'],
    'regulatory deep cleaning action plan': ['better_regulation_enforcement_communication'],
    'simplicity by design': ['better_regulation_enforcement_communication'],
    'european product act': ['better_regulation_enforcement_communication'],
    'public procurement act': ['better_regulation_enforcement_communication'],
    'banking competitiveness report': ['better_regulation_enforcement_communication'],
    'state aid banking communication': ['better_regulation_enforcement_communication'],
    # ES
    'cleaning normativo profundo': ['better_regulation_enforcement_communication'],
    'simplicidad por diseno ue': ['better_regulation_enforcement_communication'],
    # FR
    'nettoyage reglementaire approfondi': ['better_regulation_enforcement_communication'],
    'simplicite par conception ue': ['better_regulation_enforcement_communication'],
    # IT
    'pulizia regolatoria profonda': ['better_regulation_enforcement_communication'],
    'semplicita per progettazione ue': ['better_regulation_enforcement_communication'],
    # CA
    'neteja regulatoria profunda': ['better_regulation_enforcement_communication'],
    # NL
    'diep regulerend opschoning': ['better_regulation_enforcement_communication'],

    # WSR / DIWASS (multilingual)
    'diwass': ['eu_waste_shipment_regulation_diwass'],
    'digital waste shipment system': ['eu_waste_shipment_regulation_diwass'],
    'eu waste shipment regulation 2024': ['eu_waste_shipment_regulation_diwass'],
    'wsr 2024 1157': ['eu_waste_shipment_regulation_diwass'],
    'regulation 2024 1157 waste shipment': ['eu_waste_shipment_regulation_diwass'],
    'waste shipment regulation 21 may 2026': ['eu_waste_shipment_regulation_diwass'],
    'annex vii waste shipment': ['eu_waste_shipment_regulation_diwass'],
    'plastic waste exports prohibition': ['eu_waste_shipment_regulation_diwass'],
    'roswall waste shipment': ['eu_waste_shipment_regulation_diwass'],
    'switzerland municipal waste exports': ['eu_waste_shipment_regulation_diwass'],
    # ES
    'reglamento traslados residuos ue': ['eu_waste_shipment_regulation_diwass'],
    'sistema digital traslados residuos': ['eu_waste_shipment_regulation_diwass'],
    # FR
    'reglement transferts dechets ue': ['eu_waste_shipment_regulation_diwass'],
    'systeme numerique transferts dechets': ['eu_waste_shipment_regulation_diwass'],
    # IT
    'regolamento spedizioni rifiuti ue': ['eu_waste_shipment_regulation_diwass'],
    # CA
    'reglament trasllats residus ue': ['eu_waste_shipment_regulation_diwass'],
    # NL
    'verordening overbrenging afvalstoffen': ['eu_waste_shipment_regulation_diwass'],

    # PCI-PMI Transparency Platform
    'pci pmi transparency platform': ['eu_energy_policy', 'accelerateeu_fossil_energy_crisis'],
    'projects of common interest second list': ['eu_energy_policy'],

    # MFF post-vote
    'ep mff position adopted': ['mff_2028_2034'],
    'ep mff plenary vote 29 april 2026': ['mff_2028_2034'],
    'mff trilogue 2028 2034': ['mff_2028_2034'],

    # ============================================================
    # 30 April 2026 batch 2 — FerrMed pitch package (TEN-T, CEF Transport, ERTMS, Military Mobility)
    # ============================================================

    # TEN-T Regulation 2024/1679 (multilingual)
    'ten t regulation 2024 1679': ['ten_t_regulation_2024_1679'],
    'ten-t regulation recast': ['ten_t_regulation_2024_1679'],
    'trans european transport network': ['ten_t_regulation_2024_1679'],
    'core network corridors': ['ten_t_regulation_2024_1679'],
    'european transport corridors': ['ten_t_regulation_2024_1679'],
    'mediterranean corridor rail': ['ten_t_regulation_2024_1679'],
    'rhine alpine corridor': ['ten_t_regulation_2024_1679'],
    '32024r1679': ['ten_t_regulation_2024_1679'],
    'ten t deadlines 2030 2040 2050': ['ten_t_regulation_2024_1679'],
    'iberian gauge migration 1435': ['ten_t_regulation_2024_1679'],
    'p400 loading gauge': ['ten_t_regulation_2024_1679'],
    '740 metres freight train': ['ten_t_regulation_2024_1679'],
    # ES
    'red transeuropea de transporte': ['ten_t_regulation_2024_1679'],
    'corredor mediterraneo ferroviario': ['ten_t_regulation_2024_1679'],
    'rten t reglamento 2024': ['ten_t_regulation_2024_1679'],
    # FR
    'reseau transeuropeen de transport': ['ten_t_regulation_2024_1679'],
    'corridor mediterraneen ferroviaire': ['ten_t_regulation_2024_1679'],
    'reglement rte t 2024': ['ten_t_regulation_2024_1679'],
    # IT
    'rete transeuropea trasporti': ['ten_t_regulation_2024_1679'],
    'corridoio mediterraneo ferroviario': ['ten_t_regulation_2024_1679'],
    # CA
    'xarxa transeuropea de transport': ['ten_t_regulation_2024_1679'],
    'corredor mediterrani ferroviari': ['ten_t_regulation_2024_1679'],
    # NL
    'transeuropees vervoersnetwerk': ['ten_t_regulation_2024_1679'],
    # DE
    'transeuropaeisches verkehrsnetz': ['ten_t_regulation_2024_1679'],

    # CEF Transport (multilingual)
    'connecting europe facility': ['cef_transport_funding'],
    'cef transport': ['cef_transport_funding'],
    'cef military mobility': ['cef_transport_funding', 'military_mobility_dual_use_logistics'],
    'cef cohesion envelope': ['cef_transport_funding'],
    '32021r1153': ['cef_transport_funding'],
    'cinea call transport': ['cef_transport_funding'],
    'cef 2021 1153': ['cef_transport_funding'],
    # ES
    'mecanismo conectar europa transporte': ['cef_transport_funding'],
    'mecanismo conectar europa': ['cef_transport_funding'],
    # FR
    'mecanisme pour interconnecter leurope': ['cef_transport_funding'],
    'mie transport': ['cef_transport_funding'],
    # IT
    'meccanismo per collegare leuropa': ['cef_transport_funding'],
    # NL
    'connecting europe faciliteit': ['cef_transport_funding'],

    # ERTMS deployment (multilingual)
    'ertms deployment plan': ['ertms_deployment_2030'],
    'european rail traffic management system': ['ertms_deployment_2030'],
    'etcs deployment': ['ertms_deployment_2030'],
    'tsi control command signalling': ['ertms_deployment_2030'],
    '32023d1095': ['ertms_deployment_2030'],
    '32023r1695': ['ertms_deployment_2030'],
    'frmcs future railway mobile communication': ['ertms_deployment_2030'],
    'baseline 4 etcs': ['ertms_deployment_2030'],
    'ertms master plan': ['ertms_deployment_2030'],
    # ES
    'sistema europeo gestion trafico ferroviario': ['ertms_deployment_2030'],
    'despliegue ertms': ['ertms_deployment_2030'],
    # FR
    'systeme europeen de gestion du trafic ferroviaire': ['ertms_deployment_2030'],
    'deploiement ertms': ['ertms_deployment_2030'],
    # IT
    'sistema europeo gestione del traffico ferroviario': ['ertms_deployment_2030'],
    # CA
    'sistema europeu gestio trafic ferroviari': ['ertms_deployment_2030'],

    # Military Mobility / dual-use (multilingual)
    'military mobility': ['military_mobility_dual_use_logistics'],
    'pesco military mobility': ['military_mobility_dual_use_logistics'],
    'dual use logistics': ['military_mobility_dual_use_logistics'],
    'action plan military mobility': ['military_mobility_dual_use_logistics'],
    'mil mob 3.0': ['military_mobility_dual_use_logistics'],
    'jojn 2024 38': ['military_mobility_dual_use_logistics'],
    'mobilite militaire': ['military_mobility_dual_use_logistics'],
    'movilidad militar ue': ['military_mobility_dual_use_logistics'],
    'mobilita militare ue': ['military_mobility_dual_use_logistics'],
    'mobilitat militar ue': ['military_mobility_dual_use_logistics'],
    'militaire mobiliteit': ['military_mobility_dual_use_logistics'],
    'militaerische mobilitaet': ['military_mobility_dual_use_logistics'],
    'plan accion movilidad militar': ['military_mobility_dual_use_logistics'],

    # EU Anti-Poverty Strategy 2026 (multilingual) — College 6 May 2026
    'anti-poverty strategy': ['eu_anti_poverty_strategy_2026'],
    'anti poverty strategy': ['eu_anti_poverty_strategy_2026'],
    'eu poverty strategy 2026': ['eu_anti_poverty_strategy_2026'],
    'minzatu anti-poverty': ['eu_anti_poverty_strategy_2026'],
    'minzatu poverty': ['eu_anti_poverty_strategy_2026'],
    'social package 6 may': ['eu_anti_poverty_strategy_2026'],
    'arope 2030 target': ['eu_anti_poverty_strategy_2026'],
    'pillar of social rights action plan 2': ['eu_anti_poverty_strategy_2026'],
    'pillar 2.0': ['eu_anti_poverty_strategy_2026'],
    # ES
    'estrategia europea contra pobreza': ['eu_anti_poverty_strategy_2026'],
    'lucha contra la pobreza ue': ['eu_anti_poverty_strategy_2026'],
    'paquete social mayo 2026': ['eu_anti_poverty_strategy_2026'],
    # FR
    'stratégie européenne pauvreté': ['eu_anti_poverty_strategy_2026'],
    'strategie europeenne pauvrete': ['eu_anti_poverty_strategy_2026'],
    'paquet social mai 2026': ['eu_anti_poverty_strategy_2026'],
    # IT
    'strategia europea contro la povertà': ['eu_anti_poverty_strategy_2026'],
    'strategia europea contro la poverta': ['eu_anti_poverty_strategy_2026'],
    'pacchetto sociale maggio 2026': ['eu_anti_poverty_strategy_2026'],
    # CA
    'estratègia europea contra la pobresa': ['eu_anti_poverty_strategy_2026'],
    'estrategia europea contra la pobresa': ['eu_anti_poverty_strategy_2026'],
    'paquet social maig 2026': ['eu_anti_poverty_strategy_2026'],
    # NL
    'eu armoedestrategie': ['eu_anti_poverty_strategy_2026'],

    # Strengthened Child Guarantee 2026 (multilingual)
    'child guarantee strengthened': ['eu_child_guarantee_strengthened_2026'],
    'strengthened child guarantee': ['eu_child_guarantee_strengthened_2026'],
    'european child guarantee 2026': ['eu_child_guarantee_strengthened_2026'],
    'child guarantee 2021/1004': ['eu_child_guarantee_strengthened_2026'],
    'council recommendation 2021/1004': ['eu_child_guarantee_strengthened_2026'],
    '32021h1004': ['eu_child_guarantee_strengthened_2026'],
    'arope children': ['eu_child_guarantee_strengthened_2026'],
    'esf+ child poverty earmark': ['eu_child_guarantee_strengthened_2026'],
    # ES
    'garantía infantil europea': ['eu_child_guarantee_strengthened_2026'],
    'garantia infantil europea': ['eu_child_guarantee_strengthened_2026'],
    'garantia infantil reforzada': ['eu_child_guarantee_strengthened_2026'],
    # FR
    'garantie pour l\'enfance': ['eu_child_guarantee_strengthened_2026'],
    'garantie enfance europeenne': ['eu_child_guarantee_strengthened_2026'],
    'garantie europeenne pour les enfants': ['eu_child_guarantee_strengthened_2026'],
    # IT
    'garanzia per l\'infanzia': ['eu_child_guarantee_strengthened_2026'],
    'garanzia infanzia europea': ['eu_child_guarantee_strengthened_2026'],
    # CA
    'garantia infantil europea reforçada': ['eu_child_guarantee_strengthened_2026'],
    'garantia infantil reforcada': ['eu_child_guarantee_strengthened_2026'],
    # NL
    'europese kindergarantie': ['eu_child_guarantee_strengthened_2026'],

    # Council Recommendation Fighting Housing Exclusion 2026 (multilingual)
    'housing exclusion recommendation': ['eu_housing_exclusion_recommendation_2026'],
    'fighting housing exclusion': ['eu_housing_exclusion_recommendation_2026'],
    'eu housing recommendation': ['eu_housing_exclusion_recommendation_2026'],
    'lisbon declaration homelessness': ['eu_housing_exclusion_recommendation_2026'],
    'european platform combatting homelessness': ['eu_housing_exclusion_recommendation_2026'],
    'ethos light': ['eu_housing_exclusion_recommendation_2026'],
    'ethos-light': ['eu_housing_exclusion_recommendation_2026'],
    'housing first eu': ['eu_housing_exclusion_recommendation_2026'],
    'principle 19 social rights': ['eu_housing_exclusion_recommendation_2026'],
    'housing cost overburden': ['eu_housing_exclusion_recommendation_2026'],
    # ES
    'exclusión habitacional': ['eu_housing_exclusion_recommendation_2026'],
    'exclusion habitacional': ['eu_housing_exclusion_recommendation_2026'],
    'sinhogarismo ue': ['eu_housing_exclusion_recommendation_2026'],
    'recomendación sinhogarismo': ['eu_housing_exclusion_recommendation_2026'],
    # FR
    'exclusion liée au logement': ['eu_housing_exclusion_recommendation_2026'],
    'exclusion liee au logement': ['eu_housing_exclusion_recommendation_2026'],
    'sans-abrisme ue': ['eu_housing_exclusion_recommendation_2026'],
    # IT
    'esclusione abitativa': ['eu_housing_exclusion_recommendation_2026'],
    'senzatetto ue': ['eu_housing_exclusion_recommendation_2026'],
    # CA
    'exclusió residencial': ['eu_housing_exclusion_recommendation_2026'],
    'exclusio residencial': ['eu_housing_exclusion_recommendation_2026'],
    'sensellarisme ue': ['eu_housing_exclusion_recommendation_2026'],
    # NL
    'dakloosheid eu': ['eu_housing_exclusion_recommendation_2026'],
    'huisvestingsuitsluiting': ['eu_housing_exclusion_recommendation_2026'],

    # Comparator (Brubru top-level feature) (multilingual)
    'comparator': ['comparator_feature'],
    'brubru comparator': ['comparator_feature'],
    'compare files': ['comparator_feature'],
    'compare these files': ['comparator_feature'],
    'side by side files': ['comparator_feature'],
    'side-by-side files': ['comparator_feature'],
    'extraction grid': ['comparator_feature'],
    'spreadsheet of legislative files': ['comparator_feature'],
    'rapporteurs of these': ['comparator_feature'],
    'across procedures': ['comparator_feature'],
    'across legislative files': ['comparator_feature'],
    'tabular review': ['comparator_feature'],
    'multi-file comparison': ['comparator_feature'],
    'multi file comparison': ['comparator_feature'],
    # ES
    'comparador brubru': ['comparator_feature'],
    'comparar expedientes': ['comparator_feature'],
    'comparar archivos legislativos': ['comparator_feature'],
    'tabla comparativa expedientes': ['comparator_feature'],
    # FR
    'comparateur brubru': ['comparator_feature'],
    'comparer dossiers': ['comparator_feature'],
    'tableau comparatif dossiers': ['comparator_feature'],
    'comparer plusieurs dossiers législatifs': ['comparator_feature'],
    # IT
    'comparatore brubru': ['comparator_feature'],
    'confrontare fascicoli': ['comparator_feature'],
    'tabella comparativa fascicoli': ['comparator_feature'],
    # CA
    'comparador brubru ca': ['comparator_feature'],
    'comparar expedients': ['comparator_feature'],
    'taula comparativa expedients': ['comparator_feature'],
    # NL
    'vergelijker brubru': ['comparator_feature'],
    'dossiers vergelijken': ['comparator_feature'],

    # CJEU Hungary Article 2 TEU Anti-LGBTI Judgment 2026 (multilingual)
    'cjeu hungary lgbti': ['cjeu_hungary_lgbti_article2_judgment'],
    'commission v hungary lgbti': ['cjeu_hungary_lgbti_article2_judgment'],
    'hungary anti-lgbti law': ['cjeu_hungary_lgbti_article2_judgment'],
    'hungary act lxxix 2021': ['cjeu_hungary_lgbti_article2_judgment'],
    'article 2 teu judgment': ['cjeu_hungary_lgbti_article2_judgment'],
    'article 2 teu hungary': ['cjeu_hungary_lgbti_article2_judgment'],
    'hungary child protection law cjeu': ['cjeu_hungary_lgbti_article2_judgment'],
    'eprs ata 785739': ['cjeu_hungary_lgbti_article2_judgment'],
    'eprs_ata(2026)785739': ['cjeu_hungary_lgbti_article2_judgment'],
    # ES
    'sentencia tjue hungria lgbti': ['cjeu_hungary_lgbti_article2_judgment'],
    'sentencia tjue hungría lgbti': ['cjeu_hungary_lgbti_article2_judgment'],
    'articulo 2 tue': ['cjeu_hungary_lgbti_article2_judgment'],
    'artículo 2 tue': ['cjeu_hungary_lgbti_article2_judgment'],
    # FR
    'arrêt cjue hongrie lgbti': ['cjeu_hungary_lgbti_article2_judgment'],
    'arret cjue hongrie lgbti': ['cjeu_hungary_lgbti_article2_judgment'],
    'article 2 tue': ['cjeu_hungary_lgbti_article2_judgment'],
    # IT
    'sentenza cgue ungheria lgbti': ['cjeu_hungary_lgbti_article2_judgment'],
    'articolo 2 tue': ['cjeu_hungary_lgbti_article2_judgment'],
    # CA
    'sentencia tjue hongria lgbti': ['cjeu_hungary_lgbti_article2_judgment'],
    # NL
    'hvj-eu hongarije lgbti': ['cjeu_hungary_lgbti_article2_judgment'],
    'arrest hongarije anti-lgbti': ['cjeu_hungary_lgbti_article2_judgment'],

    # ============================================================
    # AI Act simplification omnibus (7 May 2026 trilogue deal) -- 2025/0359(COD)
    # All triggers route to ai_act_amendments_2026 first (the proposal-specific guide),
    # with ai_act_regulation as secondary fallback for general AI Act questions.
    # ============================================================
    # EN
    'ai act simplification omnibus': ['ai_act_amendments_2026', 'digital_omnibus_package'],
    'ai act omnibus 2026': ['ai_act_amendments_2026', 'digital_omnibus_package'],
    'ai act omnibus deal': ['ai_act_amendments_2026'],
    'ai act simplification deal': ['ai_act_amendments_2026'],
    '2025/0359(cod)': ['ai_act_amendments_2026', 'digital_omnibus_package'],
    'ai act trilogue 7 may 2026': ['ai_act_amendments_2026'],
    'ai act provisional agreement': ['ai_act_amendments_2026', 'ai_act_regulation'],
    'arba kokalari ai act': ['ai_act_amendments_2026', 'politico_ai_tech_week_2026'],
    'mcnamara ai act': ['ai_act_amendments_2026'],
    'michael mcnamara renew': ['ai_act_amendments_2026'],
    'ai act roll back': ['ai_act_amendments_2026'],
    'ai non-consensual deepfake ban': ['ai_act_amendments_2026'],
    'ncii ban eu': ['ai_act_amendments_2026'],
    'csam ai prohibition': ['ai_act_amendments_2026', 'csam_regulation_online'],
    # FR
    "omnibus simplification ia": ['ai_act_amendments_2026', 'digital_omnibus_package'],
    "accord ai act omnibus": ['ai_act_amendments_2026'],
    "interdiction nudifier ia": ['ai_act_amendments_2026'],
    "trilogue ai act 7 mai 2026": ['ai_act_amendments_2026'],
    # ES
    'omnibus simplificacion ia': ['ai_act_amendments_2026', 'digital_omnibus_package'],
    'omnibus simplificación ia': ['ai_act_amendments_2026', 'digital_omnibus_package'],
    'reglamento simplificacion ia': ['ai_act_amendments_2026'],
    'reglamento simplificación ia': ['ai_act_amendments_2026'],
    'prohibicion nudifier ia': ['ai_act_amendments_2026'],
    'prohibición nudifier ia': ['ai_act_amendments_2026'],
    # CA
    'omnibus simplificacio ia': ['ai_act_amendments_2026', 'digital_omnibus_package'],
    'omnibus simplificació ia': ['ai_act_amendments_2026', 'digital_omnibus_package'],
    'reglament simplificacio ia': ['ai_act_amendments_2026'],
    'reglament simplificació ia': ['ai_act_amendments_2026'],
    'prohibicio nudifier ia': ['ai_act_amendments_2026'],
    'prohibició nudifier ia': ['ai_act_amendments_2026'],
    # IT
    'omnibus semplificazione ia': ['ai_act_amendments_2026', 'digital_omnibus_package'],
    'regolamento semplificazione ia': ['ai_act_amendments_2026'],
    'divieto nudifier ia': ['ai_act_amendments_2026'],
    # NL
    'ai act vereenvoudiging omnibus': ['ai_act_amendments_2026', 'digital_omnibus_package'],
    'verbod nudifier ai': ['ai_act_amendments_2026'],

    # ============================================================
    # European Affordable Housing Plan -- COM(2025) 1025
    # ============================================================
    # EN
    'european affordable housing plan': ['european_affordable_housing_plan'],
    'affordable housing plan': ['european_affordable_housing_plan'],
    'eu affordable housing plan': ['european_affordable_housing_plan'],
    'com 2025 1025': ['european_affordable_housing_plan'],
    'com(2025) 1025': ['european_affordable_housing_plan'],
    'housing simplification package': ['european_affordable_housing_plan', 'eu_housing_crisis'],
    'pan-european investment platform housing': ['european_affordable_housing_plan'],
    'housing summit eu': ['european_affordable_housing_plan'],
    'housing alliance eu': ['european_affordable_housing_plan'],
    'state aid social housing': ['european_affordable_housing_plan'],
    'jorgensen housing': ['european_affordable_housing_plan'],
    'commissioner jorgensen housing': ['european_affordable_housing_plan'],
    'short-term rentals eu legislation': ['european_affordable_housing_plan'],
    'short term rentals housing eu': ['european_affordable_housing_plan'],
    'citizens energy package': ['european_affordable_housing_plan', 'accelerateeu_fossil_energy_crisis'],
    # FR
    'plan europeen logement abordable': ['european_affordable_housing_plan'],
    'plan européen logement abordable': ['european_affordable_housing_plan'],
    "alliance pour le logement": ['european_affordable_housing_plan'],
    # ES
    'plan europeo vivienda asequible': ['european_affordable_housing_plan'],
    'alianza europea vivienda': ['european_affordable_housing_plan'],
    # CA
    'pla europeu habitatge assequible': ['european_affordable_housing_plan'],
    'alianca europea habitatge': ['european_affordable_housing_plan'],
    'aliança europea habitatge': ['european_affordable_housing_plan'],
    # IT
    'piano europeo alloggi accessibili': ['european_affordable_housing_plan'],
    'piano europeo abitazione accessibile': ['european_affordable_housing_plan'],
    # NL
    'europees plan betaalbare huisvesting': ['european_affordable_housing_plan'],
    'huisvestingsalliantie eu': ['european_affordable_housing_plan'],

    # ============================================================
    # Right to Stay Strategy (DG REGIO, 6 May 2026)
    # ============================================================
    # EN
    'right to stay strategy': ['eu_demographic_right_to_stay_strategy'],
    'eu right to stay': ['eu_demographic_right_to_stay_strategy'],
    'right to stay eu': ['eu_demographic_right_to_stay_strategy'],
    'fitto right to stay': ['eu_demographic_right_to_stay_strategy'],
    'dg regio right to stay': ['eu_demographic_right_to_stay_strategy'],
    'talent booster mechanism': ['eu_demographic_right_to_stay_strategy'],
    'depopulation eu strategy': ['eu_demographic_right_to_stay_strategy'],
    'brain drain regions eu': ['eu_demographic_right_to_stay_strategy'],
    'left-behind places eu': ['eu_demographic_right_to_stay_strategy'],
    'left behind places eu': ['eu_demographic_right_to_stay_strategy'],
    'cities forum 2027 bilbao': ['eu_demographic_right_to_stay_strategy'],
    # FR
    'strategie droit de rester': ['eu_demographic_right_to_stay_strategy'],
    'stratégie droit de rester': ['eu_demographic_right_to_stay_strategy'],
    # ES
    'estrategia derecho a quedarse': ['eu_demographic_right_to_stay_strategy'],
    'derecho a permanecer ue': ['eu_demographic_right_to_stay_strategy'],
    # CA
    'estrategia dret a quedarse': ['eu_demographic_right_to_stay_strategy'],
    'estratègia dret a quedar-se': ['eu_demographic_right_to_stay_strategy'],
    # IT
    'strategia diritto di restare': ['eu_demographic_right_to_stay_strategy'],
    # NL
    'recht om te blijven strategie': ['eu_demographic_right_to_stay_strategy'],

    # ============================================================
    # Product Liability Directive (Directive (EU) 2024/2853)
    # ============================================================
    # EN
    'product liability directive': ['product_liability_directive_2024_2853'],
    'directive 2024/2853': ['product_liability_directive_2024_2853'],
    '32024l2853': ['product_liability_directive_2024_2853'],
    'pld 2024': ['product_liability_directive_2024_2853'],
    'defective products directive': ['product_liability_directive_2024_2853'],
    'product liability ai': ['product_liability_directive_2024_2853', 'ai_act_regulation'],
    'product liability software': ['product_liability_directive_2024_2853'],
    'liability for defective products': ['product_liability_directive_2024_2853'],
    'no-fault liability ai': ['product_liability_directive_2024_2853'],
    '85/374/eec repeal': ['product_liability_directive_2024_2853'],
    'corrigendum directive 2024/2853': ['product_liability_directive_2024_2853'],
    # FR
    'directive responsabilite produits defectueux': ['product_liability_directive_2024_2853'],
    'directive responsabilité produits défectueux': ['product_liability_directive_2024_2853'],
    'responsabilite produits ia': ['product_liability_directive_2024_2853'],
    # ES
    'directiva responsabilidad productos defectuosos': ['product_liability_directive_2024_2853'],
    'responsabilidad productos defectuosos ia': ['product_liability_directive_2024_2853'],
    # CA
    'directiva responsabilitat productes defectuosos': ['product_liability_directive_2024_2853'],
    # IT
    'direttiva responsabilita prodotti difettosi': ['product_liability_directive_2024_2853'],
    'direttiva responsabilità prodotti difettosi': ['product_liability_directive_2024_2853'],
    # NL
    'productaansprakelijkheid richtlijn': ['product_liability_directive_2024_2853'],

    # ============================================================
    # Heavy-duty CO2 emission credits Reg (EU) 2026/1046 (29 April 2026)
    # ============================================================
    'heavy duty co2 credits': ['eu_automotive_omnibus'],
    'heavy-duty co2 credits': ['eu_automotive_omnibus'],
    'regulation 2026/1046': ['eu_automotive_omnibus'],
    '32026r1046': ['eu_automotive_omnibus'],
    'reg 2026/1046': ['eu_automotive_omnibus'],
    'amending 2019/1242': ['eu_automotive_omnibus'],
    'heavy duty vehicles emission credits': ['eu_automotive_omnibus'],
    'creditos emisiones vehiculos pesados': ['eu_automotive_omnibus'],
    'créditos emisiones vehículos pesados': ['eu_automotive_omnibus'],
    'crédits emissions vehicules lourds': ['eu_automotive_omnibus'],
    'crediti emissioni veicoli pesanti': ['eu_automotive_omnibus'],
    'emissiekredieten zware bedrijfsvoertuigen': ['eu_automotive_omnibus'],

    # 8 May 2026 — Basel III US implementation (EPRS ECTI BRI 784037)
    'basel iii us implementation': ['financial_supervision_eba'],
    'basel iii us': ['financial_supervision_eba'],
    'us basel iii': ['financial_supervision_eba'],
    'basel iii consultation paper': ['financial_supervision_eba'],
    'basilea iii estados unidos': ['financial_supervision_eba'],
    'basilea iii eeuu': ['financial_supervision_eba'],
    'bâle iii états-unis': ['financial_supervision_eba'],
    'basilea iii catalonia': ['financial_supervision_eba'],
    'basilea iii estats units': ['financial_supervision_eba'],
    'basilea iii stati uniti': ['financial_supervision_eba'],
    'basel iii verenigde staten': ['financial_supervision_eba'],
    'prudential requirements credit institutions 2025/0825': ['financial_supervision_eba'],
    'eu basel iii implementation 2025': ['financial_supervision_eba'],

    # 8 May 2026 — AgoraEU gender equality (EP IUST BRI 787154)
    'agoraeu': ['gender_equality_strategy'],
    'agoraeu regulation': ['gender_equality_strategy'],
    'agoraeu gender equality': ['gender_equality_strategy'],
    'agoraeu citizens equality rights values': ['gender_equality_strategy'],
    'agoraeu reglamento': ['gender_equality_strategy'],
    'agoraeu reglament': ['gender_equality_strategy'],
    'agoraeu règlement': ['gender_equality_strategy'],
    'agoraeu regolamento': ['gender_equality_strategy'],
    'agoraeu verordening': ['gender_equality_strategy'],

    # 8 May 2026 — fisheries and aquaculture statistics 2025/0246(COD)
    'european fisheries aquaculture statistics': ['eu_fisheries_control'],
    'fisheries aquaculture statistics regulation': ['eu_fisheries_control'],
    '2025/0246(cod)': ['eu_fisheries_control'],
    'estadisticas pesca acuicultura ue': ['eu_fisheries_control'],
    'estadísticas pesca acuicultura ue': ['eu_fisheries_control'],
    'estadistiques pesca aqüicultura ue': ['eu_fisheries_control'],
    'statistiques peche aquaculture ue': ['eu_fisheries_control'],
    'statistiche pesca acquacoltura ue': ['eu_fisheries_control'],
    'statistieken visserij aquacultuur eu': ['eu_fisheries_control'],

    # 8 May 2026 — DG CLIMA hydrogen + Brazil/China carbon markets coalition
    'eu hydrogen bank third auction': ['eu_energy_policy', 'european_climate_law'],
    'european hydrogen projects 1 billion': ['eu_energy_policy', 'european_climate_law'],
    'hydrogen bank auction round': ['eu_energy_policy'],
    'eu brazil china carbon markets coalition': ['eu_energy_policy', 'european_climate_law'],
    'open coalition carbon markets integrity': ['eu_energy_policy'],
    'subasta hidrogeno banco europeo': ['eu_energy_policy'],
    'subhasta hidrogen banc europeu': ['eu_energy_policy'],
    'enchère hydrogène banque européenne': ['eu_energy_policy'],
    'asta idrogeno banca europea': ['eu_energy_policy'],
    'waterstof veiling europese bank': ['eu_energy_policy'],
    'coalicion mercados carbono brasil china': ['eu_energy_policy'],
    'coalició mercats carboni brasil xina': ['eu_energy_policy'],
    'coalition marchés carbone brésil chine': ['eu_energy_policy'],
    'coalizione mercati carbonio brasile cina': ['eu_energy_policy'],
    'coalitie koolstofmarkten brazilië china': ['eu_energy_policy'],

    # 8 May 2026 — DG ENER jet fuel supply response
    'jet fuel supply response': ['iran_strait_hormuz_eu_response'],
    'eu jet fuel coordinated response': ['iran_strait_hormuz_eu_response'],
    'queroseno aviacion suministro ue': ['iran_strait_hormuz_eu_response'],
    'querosè aviació subministrament ue': ['iran_strait_hormuz_eu_response'],
    'kérosène aviation approvisionnement ue': ['iran_strait_hormuz_eu_response'],
    'cherosene approvvigionamento ue': ['iran_strait_hormuz_eu_response'],
    'kerosine luchtvaart bevoorrading eu': ['iran_strait_hormuz_eu_response'],

    # 8 May 2026 — German State aid 5bn industry decarbonisation
    'german state aid 5 billion industry decarbonisation': ['competition_law_enforcement'],
    'germany 5 billion industry decarbonisation aid': ['competition_law_enforcement'],
    'ayuda estado alemania 5000 millones descarbonizacion': ['competition_law_enforcement'],
    'ajut estat alemanya 5000 milions descarbonització': ['competition_law_enforcement'],
    'aide etat allemagne 5 milliards decarbonation industrie': ['competition_law_enforcement'],
    'aiuto stato germania 5 miliardi decarbonizzazione': ['competition_law_enforcement'],
    'staatssteun duitsland 5 miljard decarbonisatie': ['competition_law_enforcement'],

    # 8 May 2026 — Migration legal counselling (EPRS BRI 785745)
    'migration legal counselling pact': ['eu_migration_asylum_pact'],
    'asylum legal counselling assistance': ['eu_migration_asylum_pact'],
    'asesoramiento legal pacto migracion': ['eu_migration_asylum_pact'],
    'assessorament legal pacte migració': ['eu_migration_asylum_pact'],
    'conseil juridique pacte migration': ['eu_migration_asylum_pact'],
    'consulenza legale patto migrazione': ['eu_migration_asylum_pact'],
    'juridisch advies migratiepact': ['eu_migration_asylum_pact'],

    # 8 May 2026 — Social Package OEIL document numbers
    'com 2026 538': ['eu_anti_poverty_strategy_2026'],
    'com(2026)0538': ['eu_anti_poverty_strategy_2026'],
    'com 2026 539': ['eu_child_guarantee_strengthened_2026'],
    'com(2026)0539': ['eu_child_guarantee_strengthened_2026'],
    'com 2026 540': ['eu_housing_exclusion_recommendation_2026'],
    'com(2026)0540': ['eu_housing_exclusion_recommendation_2026'],
    'swd 2026 770': ['eu_anti_poverty_strategy_2026'],
    'swd 2026 772': ['eu_child_guarantee_strengthened_2026'],

    # ============================================================
    # Passenger Mobility Package (College 13 May 2026 — Fitto)
    # ============================================================
    # EN
    'mobility package': ['eu_passenger_mobility_package_2026'],
    'the mobility package': ['eu_passenger_mobility_package_2026'],
    'eu mobility package': ['eu_passenger_mobility_package_2026'],
    'commission mobility package': ['eu_passenger_mobility_package_2026'],
    'commission adopts mobility package': ['eu_passenger_mobility_package_2026'],
    'passenger mobility package': ['eu_passenger_mobility_package_2026'],
    'eu passenger mobility package': ['eu_passenger_mobility_package_2026'],
    'mobility package 2026': ['eu_passenger_mobility_package_2026'],
    'multimodal digital mobility services': ['eu_passenger_mobility_package_2026'],
    'multimodal digital mobility': ['eu_passenger_mobility_package_2026'],
    'mdms eu': ['eu_passenger_mobility_package_2026'],
    'single digital booking and ticketing': ['eu_passenger_mobility_package_2026'],
    'single digital booking ticketing': ['eu_passenger_mobility_package_2026'],
    'sdbt eu': ['eu_passenger_mobility_package_2026'],
    'rail passengers rights revision': ['eu_passenger_mobility_package_2026'],
    'rail passenger rights revision': ['eu_passenger_mobility_package_2026'],
    "regulation rail passengers' rights": ['eu_passenger_mobility_package_2026'],
    'reg 1371 2007': ['eu_passenger_mobility_package_2026'],
    'reg 2021 782 rail passengers': ['eu_passenger_mobility_package_2026'],
    'eu mobility as a service maas': ['eu_passenger_mobility_package_2026'],
    'mobility as a service maas': ['eu_passenger_mobility_package_2026'],
    'fitto passenger package': ['eu_passenger_mobility_package_2026'],
    'connection guarantee multimodal': ['eu_passenger_mobility_package_2026'],
    # FR
    'paquet mobilite passagers': ['eu_passenger_mobility_package_2026'],
    'paquet mobilité passagers': ['eu_passenger_mobility_package_2026'],
    'services de mobilite multimodale': ['eu_passenger_mobility_package_2026'],
    'services de mobilité multimodale': ['eu_passenger_mobility_package_2026'],
    'billetterie numerique unique': ['eu_passenger_mobility_package_2026'],
    'billetterie numérique unique': ['eu_passenger_mobility_package_2026'],
    'droits des voyageurs ferroviaires revision': ['eu_passenger_mobility_package_2026'],
    # ES
    'paquete movilidad pasajeros': ['eu_passenger_mobility_package_2026'],
    'paquete de movilidad': ['eu_passenger_mobility_package_2026'],
    'servicios de movilidad multimodal': ['eu_passenger_mobility_package_2026'],
    'reserva digital unica billetes': ['eu_passenger_mobility_package_2026'],
    'reserva digital única billetes': ['eu_passenger_mobility_package_2026'],
    'derechos pasajeros ferroviarios revision': ['eu_passenger_mobility_package_2026'],
    'derechos pasajeros ferroviarios revisión': ['eu_passenger_mobility_package_2026'],
    # IT
    'pacchetto mobilita passeggeri': ['eu_passenger_mobility_package_2026'],
    'pacchetto mobilità passeggeri': ['eu_passenger_mobility_package_2026'],
    'servizi mobilita multimodale': ['eu_passenger_mobility_package_2026'],
    'servizi mobilità multimodale': ['eu_passenger_mobility_package_2026'],
    'biglietteria digitale unica': ['eu_passenger_mobility_package_2026'],
    # NL
    'mobiliteitspakket passagiers': ['eu_passenger_mobility_package_2026'],
    'multimodale mobiliteitsdiensten': ['eu_passenger_mobility_package_2026'],
    'eenvoudige digitale ticketing': ['eu_passenger_mobility_package_2026'],
    # CA
    'paquet mobilitat passatgers': ['eu_passenger_mobility_package_2026'],
    'serveis mobilitat multimodal': ['eu_passenger_mobility_package_2026'],
    'serveis de mobilitat multimodal': ['eu_passenger_mobility_package_2026'],

    # ============================================================
    # 2025/0847(COD) Military Mobility Framework (SEDE/TRAN, COD)
    # ============================================================
    '2025/0847(cod)': ['military_mobility_dual_use_logistics'],
    '2025 0847 cod': ['military_mobility_dual_use_logistics'],
    'framework transport of military equipment': ['military_mobility_dual_use_logistics'],
    'framework for transport of military equipment': ['military_mobility_dual_use_logistics'],
    'transport military equipment goods personnel': ['military_mobility_dual_use_logistics'],
    'military equipment transport regulation eu': ['military_mobility_dual_use_logistics'],
    # 2025/2143(INI) Single Market for Defence INI
    '2025/2143(ini)': ['military_mobility_dual_use_logistics'],
    '2025 2143 ini': ['military_mobility_dual_use_logistics'],
    'tackling barriers single market defence': ['military_mobility_dual_use_logistics'],
    'single market for defence ini': ['military_mobility_dual_use_logistics'],
    'cremer single market defence': ['military_mobility_dual_use_logistics'],
    'barriers defence single market': ['military_mobility_dual_use_logistics'],
    # FR/ES/IT/NL/CA aliases
    'cadre transport equipement militaire': ['military_mobility_dual_use_logistics'],
    'cadre transport équipement militaire': ['military_mobility_dual_use_logistics'],
    'marche unique de la defense': ['military_mobility_dual_use_logistics'],
    'marché unique de la défense': ['military_mobility_dual_use_logistics'],
    'mercado unico defensa eu': ['military_mobility_dual_use_logistics'],
    'mercado único defensa eu': ['military_mobility_dual_use_logistics'],
    'mercato unico della difesa': ['military_mobility_dual_use_logistics'],
    'mercat unic defensa ue': ['military_mobility_dual_use_logistics'],

    # ============================================================
    # 19th Russia sanctions package + shadow fleet (8 May 2026)
    # ============================================================
    'russia sanctions package': ['eu_sanctions_implementation_framework'],
    'new eu sanctions package russia': ['eu_sanctions_implementation_framework'],
    'new sanctions package russia': ['eu_sanctions_implementation_framework'],
    'sanctions against russia': ['eu_sanctions_implementation_framework'],
    'eu sanctions russia': ['eu_sanctions_implementation_framework'],
    'next eu sanctions package': ['eu_sanctions_implementation_framework'],
    'shadow fleet sanctions': ['eu_sanctions_implementation_framework'],
    'putin shadow fleet': ['eu_sanctions_implementation_framework'],
    '19th sanctions package russia': ['eu_sanctions_implementation_framework'],
    'nineteenth sanctions package russia': ['eu_sanctions_implementation_framework'],
    'russia shadow fleet tankers': ['eu_sanctions_implementation_framework'],
    'flotte fantome russie sanctions': ['eu_sanctions_implementation_framework'],
    'flotte fantôme russie sanctions': ['eu_sanctions_implementation_framework'],
    'flota fantasma rusia sanciones': ['eu_sanctions_implementation_framework'],
    'flotta ombra russia sanzioni': ['eu_sanctions_implementation_framework'],
    'schaduwvloot rusland sancties': ['eu_sanctions_implementation_framework'],
    'flota fantasma russia sancions ue': ['eu_sanctions_implementation_framework'],
    # Reg (EU) 2021/821 dual-use export controls
    'dual use export controls': ['eu_sanctions_implementation_framework'],
    'dual-use export controls': ['eu_sanctions_implementation_framework'],
    'dual use export controls eu': ['eu_sanctions_implementation_framework'],
    'eu dual use exports': ['eu_sanctions_implementation_framework'],
    'reg 2021 821 dual use': ['eu_sanctions_implementation_framework'],
    '52026xc02595': ['eu_sanctions_implementation_framework'],
    'eu export controls regulation 2021 821': ['eu_sanctions_implementation_framework'],

    # ============================================================
    # 8th EPC Summit + EU-Armenia partnership (8 May 2026)
    # ============================================================
    '8th european political community summit': ['eu_special_representatives'],
    'eighth epc summit': ['eu_special_representatives'],
    'eu armenia partnership upgrade': ['eu_special_representatives'],
    'epc summit tirana': ['eu_special_representatives'],
    'ac 26 1046': ['eu_special_representatives'],
    'eu armenia cepa': ['eu_special_representatives'],
    'cumbre comunidad politica europea': ['eu_special_representatives'],
    'sommet communaute politique europeenne': ['eu_special_representatives'],
    'sommet communauté politique européenne': ['eu_special_representatives'],
    'vertice comunita politica europea': ['eu_special_representatives'],
    'top europese politieke gemeenschap': ['eu_special_representatives'],
    'cimera comunitat politica europea': ['eu_special_representatives'],

    # ============================================================
    # Pact on Migration progress report (8 May 2026)
    # ============================================================
    'pact migration progress report 2026': ['eu_migration_asylum_pact'],
    'ip 26 1011': ['eu_migration_asylum_pact'],
    'second annual pact progress report': ['eu_migration_asylum_pact'],
    'migration solidarity forum 2026': ['eu_migration_asylum_pact'],

    # ============================================================
    # ERA Living Guidelines on generative AI in research (8 May 2026)
    # ============================================================
    'era living guidelines generative ai': ['apply_ai_strategy_public_sector'],
    'era guidelines responsible use ai research': ['apply_ai_strategy_public_sector'],
    'european research area generative ai guidelines': ['apply_ai_strategy_public_sector'],
    'responsible use generative ai research': ['apply_ai_strategy_public_sector'],

    # ============================================================
    # EPRS briefing Health and wellbeing AI (11 May 2026)
    # ============================================================
    'health wellbeing artificial intelligence eprs': ['apply_ai_strategy_public_sector'],
    'ai health older adults loneliness': ['apply_ai_strategy_public_sector'],
    'eprs ai healthcare briefing 2026': ['apply_ai_strategy_public_sector'],

    # ============================================================
    # EHDS Implementation Dialogue with Várhelyi (12 May 2026)
    # ============================================================
    'ehds implementation dialogue varhelyi': ['european_health_data_space'],
    'ehds implementation dialogue várhelyi': ['european_health_data_space'],
    'european health data space implementation dialogue': ['european_health_data_space'],
    'myhealth eu implementation 2026': ['european_health_data_space'],

    # ============================================================
    # EU ETS Review High-Level Roundtable (12 May 2026)
    # ============================================================
    'eu ets review': ['european_climate_law'],
    'ets review': ['european_climate_law'],
    'ets review high-level stakeholder roundtable': ['european_climate_law'],
    'eu ets review roundtable 2026': ['european_climate_law'],
    'ets stakeholder roundtable': ['european_climate_law'],
    'von der leyen ets review': ['european_climate_law'],
    'emissions trading system review': ['european_climate_law'],
    'emissions trading system review 2026': ['european_climate_law'],

    # ============================================================
    # AFCO new draft reports (11 May 2026 wave)
    # ============================================================
    '2025/2042(ini)': ['afco_institutional_framework_review'],
    '2025 2042 ini': ['afco_institutional_framework_review'],
    'ehlers subsidiarity proportionality': ['afco_institutional_framework_review'],
    'national parliaments role legislative process': ['afco_institutional_framework_review'],
    'subsidiarity proportionality national parliaments eu': ['afco_institutional_framework_review'],
    '2026/2012(ini)': ['afco_institutional_framework_review'],
    '2026/2013(ini)': ['afco_institutional_framework_review'],
    '2026/2014(ini)': ['afco_institutional_framework_review'],
    'afco draft reports may 2026': ['afco_institutional_framework_review'],

    # ============================================================
    # EU Talent Pool Regulation (adopted 29 Apr 2026, OJ 11 May 2026)
    # ============================================================
    'eu talent pool': ['eu_talent_pool_regulation_2026'],
    'talent pool regulation': ['eu_talent_pool_regulation_2026'],
    'talent pool eu': ['eu_talent_pool_regulation_2026'],
    'talent pool platform': ['eu_talent_pool_regulation_2026'],
    'eu jobseeker platform': ['eu_talent_pool_regulation_2026'],
    'european talent pool': ['eu_talent_pool_regulation_2026'],
    '32026r1047': ['eu_talent_pool_regulation_2026'],
    '2026/1047': ['eu_talent_pool_regulation_2026'],
    'regulation 2026/1047': ['eu_talent_pool_regulation_2026'],
    '2023/0404(cod)': ['eu_talent_pool_regulation_2026'],
    '2023/0404': ['eu_talent_pool_regulation_2026'],
    'com(2023)716': ['eu_talent_pool_regulation_2026'],
    'com(2023) 716': ['eu_talent_pool_regulation_2026'],
    'skills and talent mobility package': ['eu_talent_pool_regulation_2026'],
    'shortage occupations eu': ['eu_talent_pool_regulation_2026'],
    'reservoir de talents': ['eu_talent_pool_regulation_2026'],
    'reservoir de talents ue': ['eu_talent_pool_regulation_2026'],
    'pool de talentos': ['eu_talent_pool_regulation_2026'],
    'pool de talentos ue': ['eu_talent_pool_regulation_2026'],
    'pool di talenti': ['eu_talent_pool_regulation_2026'],
    'talenten pool': ['eu_talent_pool_regulation_2026'],
    'talenten-pool': ['eu_talent_pool_regulation_2026'],
    'eu-talentenpool': ['eu_talent_pool_regulation_2026'],
    'pool de talents ue': ['eu_talent_pool_regulation_2026'],

    # ============================================================
    # EU Protection of Migrant Workers + Employer Sanctions (13 May 2026)
    # ============================================================
    'employer sanctions directive': ['eu_migrant_workers_employer_sanctions'],
    'employers sanctions directive': ['eu_migrant_workers_employer_sanctions'],
    '2009/52/ec': ['eu_migrant_workers_employer_sanctions'],
    '32009l0052': ['eu_migrant_workers_employer_sanctions'],
    'illegal employment eu': ['eu_migrant_workers_employer_sanctions'],
    'illegal employment migrant workers': ['eu_migrant_workers_employer_sanctions'],
    'irregularly employed migrant workers': ['eu_migrant_workers_employer_sanctions'],
    'fight illegal employment': ['eu_migrant_workers_employer_sanctions'],
    'migrant workers protection eu': ['eu_migrant_workers_employer_sanctions'],
    'protect migrant workers': ['eu_migrant_workers_employer_sanctions'],
    'seasonal workers directive': ['eu_migrant_workers_employer_sanctions'],
    '2014/36/eu': ['eu_migrant_workers_employer_sanctions'],
    '32014l0036': ['eu_migrant_workers_employer_sanctions'],
    'amif specific action': ['eu_migrant_workers_employer_sanctions'],
    'amif/2026/sa/2.4.1': ['eu_migrant_workers_employer_sanctions'],
    'asylum migration integration fund call': ['eu_migrant_workers_employer_sanctions'],
    'amif call 2026': ['eu_migrant_workers_employer_sanctions'],
    'employer sanctions evaluation': ['eu_migrant_workers_employer_sanctions'],
    'european labour authority mandate': ['eu_migrant_workers_employer_sanctions'],
    'ela mandate review': ['eu_migrant_workers_employer_sanctions'],
    'undeclared work eu': ['eu_migrant_workers_employer_sanctions'],
    'high-risk sectors migrants': ['eu_migrant_workers_employer_sanctions'],
    'agriculture construction care hospitality migrants': ['eu_migrant_workers_employer_sanctions'],
    'talent partnerships third countries': ['eu_migrant_workers_employer_sanctions'],
    # FR
    'directive sanctions employeurs': ['eu_migrant_workers_employer_sanctions'],
    'travailleurs migrants protection': ['eu_migrant_workers_employer_sanctions'],
    'emploi illegal ue': ['eu_migrant_workers_employer_sanctions'],
    'travailleurs saisonniers directive': ['eu_migrant_workers_employer_sanctions'],
    # IT
    'direttiva sanzioni datori di lavoro': ['eu_migrant_workers_employer_sanctions'],
    'lavoratori migranti protezione': ['eu_migrant_workers_employer_sanctions'],
    'lavoro illegale ue': ['eu_migrant_workers_employer_sanctions'],
    'lavoratori stagionali direttiva': ['eu_migrant_workers_employer_sanctions'],
    # ES
    'directiva sanciones empleadores': ['eu_migrant_workers_employer_sanctions'],
    'trabajadores migrantes proteccion': ['eu_migrant_workers_employer_sanctions'],
    'empleo ilegal ue': ['eu_migrant_workers_employer_sanctions'],
    'trabajadores temporeros directiva': ['eu_migrant_workers_employer_sanctions'],
    # CA
    'directiva sancions ocupadors': ['eu_migrant_workers_employer_sanctions'],
    'treballadors migrants proteccio': ['eu_migrant_workers_employer_sanctions'],
    'ocupacio illegal ue': ['eu_migrant_workers_employer_sanctions'],
    # NL
    'richtlijn sancties werkgevers': ['eu_migrant_workers_employer_sanctions'],
    'arbeidsmigranten bescherming': ['eu_migrant_workers_employer_sanctions'],
    'illegale tewerkstelling eu': ['eu_migrant_workers_employer_sanctions'],
    'seizoenarbeiders richtlijn': ['eu_migrant_workers_employer_sanctions'],

    # ============================================================
    # EU-Syria Cooperation Agreement re-activation (11 May 2026)
    # ============================================================
    'eu syria cooperation': ['eu_syria_cooperation_agreement_2026'],
    'eu-syria cooperation agreement': ['eu_syria_cooperation_agreement_2026'],
    'syria cooperation agreement': ['eu_syria_cooperation_agreement_2026'],
    'eu syria agreement': ['eu_syria_cooperation_agreement_2026'],
    'eu-syria relations': ['eu_syria_cooperation_agreement_2026'],
    'syria reconstruction eu': ['eu_syria_cooperation_agreement_2026'],
    'syria sanctions lifted': ['eu_syria_cooperation_agreement_2026'],
    'decision 2011/523': ['eu_syria_cooperation_agreement_2026'],
    '32011d0523': ['eu_syria_cooperation_agreement_2026'],
    '32026d1087': ['eu_syria_cooperation_agreement_2026'],
    '2026/1087': ['eu_syria_cooperation_agreement_2026'],
    'council decision 2026/1087': ['eu_syria_cooperation_agreement_2026'],
    'accord de cooperation syrie': ['eu_syria_cooperation_agreement_2026'],
    'accord de cooperation ue syrie': ['eu_syria_cooperation_agreement_2026'],
    'reconstruccion siria ue': ['eu_syria_cooperation_agreement_2026'],
    'acuerdo cooperacion siria': ['eu_syria_cooperation_agreement_2026'],
    'ricostruzione siria ue': ['eu_syria_cooperation_agreement_2026'],
    'samenwerkingsovereenkomst syrie': ['eu_syria_cooperation_agreement_2026'],
    'cooperacio ue siria': ['eu_syria_cooperation_agreement_2026'],

    # ============================================================
    # 11 May 2026 sanctions wave (CELEX hooks)
    # ============================================================
    '32026r1055': ['eu_sanctions_implementation_framework'],
    '2026/1055': ['eu_sanctions_implementation_framework'],
    '32026d1072': ['eu_sanctions_implementation_framework'],
    '2026/1072': ['eu_sanctions_implementation_framework'],
    '32026r1078': ['eu_sanctions_implementation_framework'],
    '2026/1078': ['eu_sanctions_implementation_framework'],
    '32026d1079': ['eu_sanctions_implementation_framework'],
    '2026/1079': ['eu_sanctions_implementation_framework'],
    '32026d1083': ['eu_sanctions_implementation_framework'],
    '2026/1083': ['eu_sanctions_implementation_framework'],
    'cyber sanctions extension': ['eu_sanctions_implementation_framework'],
    'cyber attacks restrictive measures': ['eu_sanctions_implementation_framework'],
    'cyber-attacks restrictive measures eu': ['eu_sanctions_implementation_framework'],
    'euam ukraine extension': ['eu_sanctions_implementation_framework'],
    'putin shadow fleet sanctions': ['eu_sanctions_implementation_framework'],
    'russia shadow fleet eu': ['eu_sanctions_implementation_framework'],

    # ============================================================
    # CountEmissions EU adopted as Reg 2026/1030 (29 Apr 2026)
    # ============================================================
    '32026r1030': ['emissions_accounting_transport_services'],
    '2026/1030': ['emissions_accounting_transport_services'],
    'regulation 2026/1030': ['emissions_accounting_transport_services'],
    'countemissions eu adopted': ['emissions_accounting_transport_services'],
    'ghg accounting transport services regulation': ['emissions_accounting_transport_services'],
    'iso 14083 eu regulation': ['emissions_accounting_transport_services'],

    # ============================================================
    # Anti-Corruption Directive adopted (29 Apr 2026)
    # ============================================================
    '32026l1021': ['anti_corruption_directive'],
    '2026/1021': ['anti_corruption_directive'],
    'directive 2026/1021': ['anti_corruption_directive'],
    'anti-corruption directive adopted': ['anti_corruption_directive'],
    'eu corruption directive in force': ['anti_corruption_directive'],

    # ============================================================
    # Critical Medicines Act political agreement (11 May 2026)
    # ============================================================
    'critical medicines act political agreement': ['critical_medicines_act'],
    'critical medicines act deal': ['critical_medicines_act'],
    'critical medicines act trilogue closed': ['critical_medicines_act'],
    'critical medicines act ip 26 1017': ['critical_medicines_act'],
    'ip/26/1017': ['critical_medicines_act'],

    # ============================================================
    # ETS benchmarks consultation (11 May 2026)
    # ============================================================
    'ets benchmarks consultation': ['european_climate_law'],
    'eu ets benchmarks revision': ['european_climate_law'],
    'updated ets benchmarks': ['european_climate_law'],
    'eu ets free allocation benchmarks': ['european_climate_law'],
    'ip/26/1044': ['european_climate_law'],
    'valeurs de reference seqe': ['european_climate_law'],
    'benchmarks regime sceqe': ['european_climate_law'],
    'valori di riferimento ets': ['european_climate_law'],
    'valores de referencia rceue': ['european_climate_law'],

    # ============================================================
    # Budapest Convention third-party accessions proposal (11 May 2026)
    # ============================================================
    '52026pc0186': ['un_cybercrime_convention'],
    'com(2026)186': ['un_cybercrime_convention'],
    'com(2026) 186': ['un_cybercrime_convention'],
    'budapest convention third party accessions': ['un_cybercrime_convention'],
    'eu position budapest convention': ['un_cybercrime_convention'],

    # ============================================================
    # 13 May 2026 College adoption + sweep
    # Passenger Package + Fertilisers + Global Health Resilience
    # CoE AI Framework Convention + CSDP missions + Seychelles SFPA
    # MMF Notice + Nature Directives consultation + EPRS pipeline gaps
    # ============================================================

    # Passenger Package (College 13 May 2026)
    'passenger mobility package adopted': ['eu_passenger_mobility_package_2026'],
    'passenger package adopted': ['eu_passenger_mobility_package_2026'],
    'multimodal digital mobility services': ['eu_passenger_mobility_package_2026'],
    'mdms regulation': ['eu_passenger_mobility_package_2026'],
    'single digital booking and ticketing': ['eu_passenger_mobility_package_2026'],
    'sdbt regulation': ['eu_passenger_mobility_package_2026'],
    'rail passengers rights revision': ['eu_passenger_mobility_package_2026'],
    'revision regulation 2021/782': ['eu_passenger_mobility_package_2026'],
    'fitto passenger package': ['eu_passenger_mobility_package_2026'],
    'paquet mobilite passagers': ['eu_passenger_mobility_package_2026'],
    'pacchetto mobilita passeggeri': ['eu_passenger_mobility_package_2026'],
    'paquete movilidad pasajeros': ['eu_passenger_mobility_package_2026'],
    'passatgers mobilitat ue': ['eu_passenger_mobility_package_2026'],
    'passagiersmobiliteit pakket': ['eu_passenger_mobility_package_2026'],

    # Fertilisers Action Plan (College 13 May 2026)
    'fertilisers action plan': ['fertilisers_action_plan_2026'],
    'fertiliser action plan': ['fertilisers_action_plan_2026'],
    'fertilisers action plan adopted': ['fertilisers_action_plan_2026'],
    'fertiliser action plan adopted': ['fertilisers_action_plan_2026'],
    'eu fertilisers action plan': ['fertilisers_action_plan_2026'],
    'communication fertilisers action plan': ['fertilisers_action_plan_2026'],
    'plan accion fertilizantes': ['fertilisers_action_plan_2026'],
    'plan engrais ue': ['fertilisers_action_plan_2026'],
    'plan dazione fertilizzanti': ['fertilisers_action_plan_2026'],
    'pla accio fertilitzants': ['fertilisers_action_plan_2026'],
    'meststoffenactieplan': ['fertilisers_action_plan_2026'],

    # Global Health Resilience Initiative (College 13 May 2026)
    'global health resilience initiative': ['eu_global_health_resilience_initiative_2026'],
    'eu global health resilience': ['eu_global_health_resilience_initiative_2026'],
    'kallas global health initiative': ['eu_global_health_resilience_initiative_2026'],
    'global health initiative 2026': ['eu_global_health_resilience_initiative_2026'],
    'iniciativa resiliencia salud mundial': ['eu_global_health_resilience_initiative_2026'],
    'initiative resilience sante mondiale': ['eu_global_health_resilience_initiative_2026'],
    'iniziativa resilienza salute globale': ['eu_global_health_resilience_initiative_2026'],
    'iniciativa resiliencia salut global': ['eu_global_health_resilience_initiative_2026'],
    'mondiale gezondheidsveerkracht initiatief': ['eu_global_health_resilience_initiative_2026'],
    'hera global health': ['eu_global_health_resilience_initiative_2026'],
    'who pandemic treaty eu': ['eu_global_health_resilience_initiative_2026'],
    'pandemic treaty implementation': ['eu_global_health_resilience_initiative_2026'],

    # CoE AI Framework Convention (CELEX 32026D1080)
    '32026d1080': ['ai_act_regulation'],
    '2026/1080': ['ai_act_regulation'],
    'council of europe framework convention on ai': ['ai_act_regulation'],
    'coe ai framework convention': ['ai_act_regulation'],
    'coe convention on ai human rights democracy rule of law': ['ai_act_regulation'],
    'eu accession coe ai convention': ['ai_act_regulation'],
    'first international ai treaty': ['ai_act_regulation'],
    'vilnius ai treaty': ['ai_act_regulation'],
    'convention cadre conseil europe intelligence artificielle': ['ai_act_regulation'],
    'convencion marco consejo europa inteligencia artificial': ['ai_act_regulation'],
    'convenzione quadro consiglio europa intelligenza artificiale': ['ai_act_regulation'],

    # CSDP missions + European Peace Facility (11-12 May 2026 CFSP wave)
    'eu csdp missions': ['eu_csdp_missions_2026'],
    'common security and defence policy missions': ['eu_csdp_missions_2026'],
    'eumam mozambique': ['eu_csdp_missions_2026'],
    '32026d1084': ['eu_csdp_missions_2026'],
    '2026/1084': ['eu_csdp_missions_2026'],
    'euam ukraine civilian security sector reform': ['eu_csdp_missions_2026'],
    'eu advisory mission ukraine': ['eu_csdp_missions_2026'],
    '32026d1083': ['eu_csdp_missions_2026'],
    '2026/1083': ['eu_csdp_missions_2026'],
    'epf bosnia herzegovina': ['eu_csdp_missions_2026'],
    'european peace facility bosnia': ['eu_csdp_missions_2026'],
    'bosnia armed forces eu assistance measure': ['eu_csdp_missions_2026'],
    '32026d1082': ['eu_csdp_missions_2026'],
    '2026/1082': ['eu_csdp_missions_2026'],
    'european peace facility assistance measure': ['eu_csdp_missions_2026'],
    'eufor althea': ['eu_csdp_missions_2026'],
    'eunavfor aspides': ['eu_csdp_missions_2026'],
    'eunavfor atalanta': ['eu_csdp_missions_2026'],
    'eunavfor med irini': ['eu_csdp_missions_2026'],
    'eumam ukraine': ['eu_csdp_missions_2026'],
    'eubam libya': ['eu_csdp_missions_2026'],
    'eubam rafah': ['eu_csdp_missions_2026'],
    'eumm georgia': ['eu_csdp_missions_2026'],
    'eucap sahel mali': ['eu_csdp_missions_2026'],
    'eucap somalia': ['eu_csdp_missions_2026'],
    'eutm somalia': ['eu_csdp_missions_2026'],
    'eupm moldova': ['eu_csdp_missions_2026'],
    'euam armenia': ['eu_csdp_missions_2026'],
    'missions psdc ue': ['eu_csdp_missions_2026'],
    'misiones pcsd ue': ['eu_csdp_missions_2026'],
    'missioni psdc ue': ['eu_csdp_missions_2026'],
    'missions pcsd ue': ['eu_csdp_missions_2026'],

    # Seychelles SFPA Protocol 2026-2030
    'seychelles sfpa protocol': ['eu_fisheries_control'],
    '52026pc0192': ['eu_fisheries_control'],
    '52026pc0193': ['eu_fisheries_control'],
    '52026pc0194': ['eu_fisheries_control'],
    '52026pc0195': ['eu_fisheries_control'],
    'sustainable fisheries partnership agreement seychelles': ['eu_fisheries_control'],
    'eu seychelles fisheries protocol 2026': ['eu_fisheries_control'],
    'acuerdo pesca sostenible seychelles': ['eu_fisheries_control'],
    'accord peche durable seychelles': ['eu_fisheries_control'],
    'accordo pesca sostenibile seychelles': ['eu_fisheries_control'],
    'protocollo seychelles pesca': ['eu_fisheries_control'],
    'cook islands fisheries protocol': ['eu_fisheries_control'],
    'sao tome principe fisheries protocol': ['eu_fisheries_control'],

    # MMF Notice (Money Market Funds Regulation)
    'money market funds regulation notice': ['financial_supervision_eba'],
    'commission notice money market funds': ['financial_supervision_eba'],
    'mmfr commission notice': ['financial_supervision_eba'],
    '52026xc02641': ['financial_supervision_eba'],
    'c/2026/02641': ['financial_supervision_eba'],
    'regulation 2017/1131 interpretation': ['financial_supervision_eba'],
    'mmf regulation guidance': ['financial_supervision_eba'],
    'private credit eu financial stability': ['financial_supervision_eba'],
    'ecti briefing private credit': ['financial_supervision_eba'],

    # Victims Rights Directive revision
    'victims rights directive': ['victims_rights_directive_revision'],
    'revised victims rights directive': ['victims_rights_directive_revision'],
    'directive 2012/29/eu revision': ['victims_rights_directive_revision'],
    'com(2023) 424': ['victims_rights_directive_revision'],
    '2023/0250(cod)': ['victims_rights_directive_revision'],
    'directiva derechos victimas': ['victims_rights_directive_revision'],
    'directive droits victimes': ['victims_rights_directive_revision'],
    'direttiva diritti vittime': ['victims_rights_directive_revision'],
    'slachtofferrichtlijn herziening': ['victims_rights_directive_revision'],
    '116 006 helpline': ['victims_rights_directive_revision'],

    # European Investigation Order
    'european investigation order': ['european_investigation_order'],
    'eio directive': ['european_investigation_order'],
    'directive 2014/41/eu': ['european_investigation_order'],
    '32014l0041': ['european_investigation_order'],
    'eu cross border evidence': ['european_investigation_order'],
    'orden europea de investigacion': ['european_investigation_order'],
    'decision enquete europeenne': ['european_investigation_order'],
    'ordine europeo di indagine': ['european_investigation_order'],
    'europees onderzoeksbevel': ['european_investigation_order'],
    'mutual legal assistance criminal eu': ['european_investigation_order'],

    # FDI Screening Regulation
    'foreign direct investment screening': ['eu_fdi_screening_regulation'],
    'fdi screening regulation': ['eu_fdi_screening_regulation'],
    'regulation 2019/452': ['eu_fdi_screening_regulation'],
    '32019r0452': ['eu_fdi_screening_regulation'],
    'com(2024) 23': ['eu_fdi_screening_regulation'],
    '2024/0017(cod)': ['eu_fdi_screening_regulation'],
    'screening inversion extranjera directa': ['eu_fdi_screening_regulation'],
    'controle investissements directs etrangers': ['eu_fdi_screening_regulation'],
    'screening investimenti diretti esteri': ['eu_fdi_screening_regulation'],
    'screening buitenlandse directe investeringen': ['eu_fdi_screening_regulation'],
    'economic security strategy eu': ['eu_fdi_screening_regulation'],
    'inbound investment screening': ['eu_fdi_screening_regulation'],

    # Stop Destroying Videogames ECI
    'stop destroying videogames eci': ['stop_destroying_videogames_eci'],
    'stop killing games eci': ['stop_destroying_videogames_eci'],
    'european citizens initiative videogames': ['stop_destroying_videogames_eci'],
    'eci(2024)000007': ['stop_destroying_videogames_eci'],
    'videogames preservation eu': ['stop_destroying_videogames_eci'],
    'live service games eu obligation': ['stop_destroying_videogames_eci'],
    'iniciativa ciudadana videojuegos': ['stop_destroying_videogames_eci'],
    'initiative citoyenne jeux video': ['stop_destroying_videogames_eci'],
    'iniziativa cittadini videogiochi': ['stop_destroying_videogames_eci'],
    'burgerinitiatief videogames': ['stop_destroying_videogames_eci'],

    # ETS Review 2026 + revised 2026 auction calendars
    'eu ets review 2026': ['eu_ets_review_2026'],
    'ets review college 7 july 2026': ['eu_ets_review_2026'],
    'ribera ets review': ['eu_ets_review_2026'],
    'eu ets auction calendar 2026': ['eu_ets_review_2026'],
    'revised 2026 auction calendars': ['eu_ets_review_2026'],
    'ets2 auctioning': ['eu_ets_review_2026'],
    'directive 2023/959': ['eu_ets_review_2026'],
    '32023l0959': ['eu_ets_review_2026'],
    'market stability reserve review': ['eu_ets_review_2026'],
    'linear reduction factor lrf': ['eu_ets_review_2026'],
    'free allocation phase out cbam': ['eu_ets_review_2026'],
    'revision sceqe 2026': ['eu_ets_review_2026'],
    'revision regimen ets 2026': ['eu_ets_review_2026'],

    # EU-UK Security and Defence Partnership
    'eu uk security and defence partnership': ['eu_uk_security_defence_partnership'],
    'eu uk sdp': ['eu_uk_security_defence_partnership'],
    'british defence industry': ['eu_uk_security_defence_partnership'],
    'british defense industry': ['eu_uk_security_defence_partnership'],
    'british defence industry eu cooperation': ['eu_uk_security_defence_partnership'],
    'eu uk defence cooperation': ['eu_uk_security_defence_partnership'],
    'eu uk defense cooperation': ['eu_uk_security_defence_partnership'],
    'uk participation safe edip': ['eu_uk_security_defence_partnership'],
    'uk pesco military mobility': ['eu_uk_security_defence_partnership'],
    'eu uk summit 2025 defence': ['eu_uk_security_defence_partnership'],
    'tca security defence': ['eu_uk_security_defence_partnership'],
    '32026d1069': ['eu_uk_security_defence_partnership'],
    'article 540 tca': ['eu_uk_security_defence_partnership'],
    'cooperacion defensa ue reino unido': ['eu_uk_security_defence_partnership'],
    'cooperation defense ue royaume uni': ['eu_uk_security_defence_partnership'],
    'cooperazione difesa ue regno unito': ['eu_uk_security_defence_partnership'],

    # Nature Directives consultation + corrigendum
    'nature directives consultation 2026': ['nature_restoration_law'],
    'consulta directivas naturaleza': ['nature_restoration_law'],
    'fitness check nature directives': ['nature_restoration_law'],
    'habitats directive review 2026': ['nature_restoration_law'],
    'birds directive review 2026': ['nature_restoration_law'],
    '32024r1991r(05)': ['nature_restoration_law'],
    'berichtigung naturwiederherstellung': ['nature_restoration_law'],

    # DSA + Eurobarometer 92% minors protection
    'eurobarometer children online protection': ['dsa_enforcement'],
    '92 percent europeans children online': ['dsa_enforcement'],
    'children online protection': ['dsa_enforcement'],
    '92 percent europeans': ['dsa_enforcement'],
    'european summit ai and children': ['dsa_enforcement'],
    'children online protection priority': ['dsa_enforcement'],
    'eu age verification minors': ['dsa_enforcement'],

    # Migration + Eurostat + Mînzatu
    'eu external border refusals 132600': ['eu_migration_asylum_pact'],
    'eurostat 132600 entries refused': ['eu_migration_asylum_pact'],
    '132600': ['eu_migration_asylum_pact'],
    'entries refused eu border': ['eu_migration_asylum_pact'],
    'entries refused eu borders': ['eu_migration_asylum_pact'],
    'refusals eu external border': ['eu_migration_asylum_pact'],
    'eu ukraine education dialogue': ['eu_migration_asylum_pact'],
    'minzatu eu ukraine education': ['eu_migration_asylum_pact'],

    # MFF + Draghi/Letta study
    'draghi letta investment needs eu budget': ['mff_2028_2034'],
    'investment needs draghi letta report': ['mff_2028_2034'],
    'draghi letta eprs study': ['mff_2028_2034'],

    # Apply AI Strategy + AI for Trade
    'comprehensive ai strategy for eu trade': ['apply_ai_strategy_public_sector'],
    'ai strategy eu trade': ['apply_ai_strategy_public_sector'],
    'ai for trade eu': ['apply_ai_strategy_public_sector'],

    # European Defence Union (AFCO INI surge today)
    '2025/2212(ini)': ['european_defence_union'],
    'institutional aspects common european defence union': ['european_defence_union'],
    'common european defence union': ['european_defence_union'],
    'salvatore de meo defence union': ['european_defence_union'],

    # Hantavirus EU response (gap - cross-link to existing health/security guides)
    'hantavirus outbreak eu response': ['eu_global_health_resilience_initiative_2026'],
    'andes hantavirus eu': ['eu_global_health_resilience_initiative_2026'],
    'health security committee opinion hantavirus': ['eu_global_health_resilience_initiative_2026'],
    'hsc opinion hantavirus': ['eu_global_health_resilience_initiative_2026'],

    # Fri 15 May 2026 — Right to Stay third-wave promotion (EURegionsWeek + PSLF + Bilbao Cities Forum + Fitto Czechia)
    'right to stay relaunch': ['eu_demographic_right_to_stay_strategy'],
    'right to stay third wave': ['eu_demographic_right_to_stay_strategy'],
    'euregionsweek 2026 call': ['eu_demographic_right_to_stay_strategy'],
    'pslf just transition platform results': ['eu_demographic_right_to_stay_strategy'],
    'cities forum 2027 bilbao': ['eu_demographic_right_to_stay_strategy'],
    'fitto czechia cohesion': ['eu_demographic_right_to_stay_strategy'],

    # Thu 14 May 2026 — Romania 4th NextGenerationEU payment EUR 2.62 billion
    'romania 4th nextgenerationeu payment': ['eu_recovery_resilience_facility'],
    'romania 2.62 billion rrf': ['eu_recovery_resilience_facility'],
    'romania ngeu payment may 2026': ['eu_recovery_resilience_facility'],
    'romania pago recuperacion ngeu': ['eu_recovery_resilience_facility'],
    'romania quarta richiesta ngeu': ['eu_recovery_resilience_facility'],
    'commission greenlights romania': ['eu_recovery_resilience_facility'],
    'commission approves romania payment': ['eu_recovery_resilience_facility'],
    'romania nrrp payment': ['eu_recovery_resilience_facility'],
    'romania recovery plan payment': ['eu_recovery_resilience_facility'],

    # Wed 13 May 2026 — MFF post-2027 EPRS Briefing (May 2026)
    'background information post 2027 mff': ['mff_2028_2034'],
    'eprs briefing mff may 2026': ['mff_2028_2034'],
    'post 2027 mff briefing': ['mff_2028_2034'],

    # Thu-Fri 14-15 May 2026 — EPRS Ask EP gender equality dual blog
    'european parliament action gender equality': ['gender_equality_strategy'],
    'eu action on gender equality ask ep': ['gender_equality_strategy'],
    'ask ep gender equality': ['gender_equality_strategy'],
    'ep action gender equality 2026': ['gender_equality_strategy'],

    # Sun 11 May 2026 — NEW guide: EU private credit market structure (EPRS Briefing 11 May)
    'private credit eu': ['eu_private_credit_market_structure'],
    'private credit market structure': ['eu_private_credit_market_structure'],
    'private credit financial stability eu': ['eu_private_credit_market_structure'],
    'private credit aifmd ii': ['eu_private_credit_market_structure'],
    'private credit eltif 2.0': ['eu_private_credit_market_structure'],
    'aifmd ii loan origination': ['eu_private_credit_market_structure'],
    'eltif 2.0 retail private credit': ['eu_private_credit_market_structure'],
    'nbfi private credit eu': ['eu_private_credit_market_structure'],
    'eprs briefing private credit': ['eu_private_credit_market_structure'],
    'private credit eprs may 2026': ['eu_private_credit_market_structure'],
    'mercado credito privado ue': ['eu_private_credit_market_structure'],
    'crédit privé union européenne': ['eu_private_credit_market_structure'],
    'credito privato unione europea': ['eu_private_credit_market_structure'],
    'private kredit eu markt': ['eu_private_credit_market_structure'],
    'crèdit privat unió europea': ['eu_private_credit_market_structure'],

    # ep_immunity_prosecution_2026 (NEW 18 May 2026 — Politico immunity-overreach story)
    'ep immunity': ['ep_immunity_prosecution_2026'],
    'mep immunity': ['ep_immunity_prosecution_2026'],
    'parliamentary immunity': ['ep_immunity_prosecution_2026'],
    'waiver of immunity': ['ep_immunity_prosecution_2026'],
    'defence of immunity': ['ep_immunity_prosecution_2026'],
    'fumus persecutionis': ['ep_immunity_prosecution_2026'],
    'protocol 7 privileges immunities': ['ep_immunity_prosecution_2026'],
    'juri immunity': ['ep_immunity_prosecution_2026'],
    'ep shielding lawmakers': ['ep_immunity_prosecution_2026'],
    'ep overreach prosecutors': ['ep_immunity_prosecution_2026'],
    'mep prosecution': ['ep_immunity_prosecution_2026'],
    'inmunidad eurodiputado': ['ep_immunity_prosecution_2026'],
    'inmunidad parlamentaria europea': ['ep_immunity_prosecution_2026'],
    'immunité député européen': ['ep_immunity_prosecution_2026'],
    'immunité parlementaire ue': ['ep_immunity_prosecution_2026'],
    'immunità parlamentare ue': ['ep_immunity_prosecution_2026'],
    'immunità eurodeputato': ['ep_immunity_prosecution_2026'],
    'immunitat eurodiputat': ['ep_immunity_prosecution_2026'],
    'parlementaire immuniteit ep': ['ep_immunity_prosecution_2026'],

    # EU-China WTO Article XXVIII (18 May 2026 — OJ L_202601077)
    'gatt article xxviii': ['eu_trade_policy'],
    'wto article xxviii': ['eu_trade_policy'],
    'eu china exchange of letters': ['eu_trade_policy'],
    'eu china wto concession': ['eu_trade_policy'],
    'oj l_202601077': ['eu_trade_policy'],
    'concesion arancelaria omc': ['eu_trade_policy'],
    'concession tarifaire omc': ['eu_trade_policy'],
    'concessione tariffaria omc': ['eu_trade_policy'],
    'concessie ue wto': ['eu_trade_policy'],
    'concessió aranzelària omc': ['eu_trade_policy'],

    # Single European Sky performance plan decisions (18 May 2026 — OJ 1031/1033/1034/1042)
    'single european sky performance plan': ['aviation_transport_policy'],
    'ses performance plan latvia': ['aviation_transport_policy'],
    'ses performance plan denmark': ['aviation_transport_policy'],
    'ses performance plan estonia': ['aviation_transport_policy'],
    'ses performance plan ireland': ['aviation_transport_policy'],
    'ansp performance plan': ['aviation_transport_policy'],
    'plan de rendimiento espacio aereo unico': ['aviation_transport_policy'],
    'plan performance ciel unique europeen': ['aviation_transport_policy'],
    'piano prestazioni cielo unico europeo': ['aviation_transport_policy'],
    'pla rendiment espai aeri unic': ['aviation_transport_policy'],
    'prestatieplan single european sky': ['aviation_transport_policy'],
    'un regulation 179 brake emissions': ['aviation_transport_policy'],
    'unece 179 brake emissions': ['aviation_transport_policy'],
    'oj l_202601044': ['aviation_transport_policy'],

    # Russia sanctions-evasion shell company (18 May 2026 — Politico)
    'russia sanctions evasion germany': ['eu_anti_money_laundering'],
    'moscow front company germany': ['eu_anti_money_laundering'],
    'russian military shell company eu': ['eu_anti_money_laundering'],
    'evasion sanciones rusia alemania': ['eu_anti_money_laundering'],
    'contournement sanctions russie allemagne': ['eu_anti_money_laundering'],
    'aggiramento sanzioni russia germania': ['eu_anti_money_laundering'],
    'ontwijking sancties rusland duitsland': ['eu_anti_money_laundering'],
    'evasió sancions rússia alemanya': ['eu_anti_money_laundering'],

    # Craft & Industrial Geographical Indications - Reg (EU) 2024/1143 (NEW guide 19 May 2026)
    'craft geographical indication': ['gi_craft_industrial_2024_1143'],
    'industrial geographical indication': ['gi_craft_industrial_2024_1143'],
    'craft gi': ['gi_craft_industrial_2024_1143'],
    'gi craft products eu': ['gi_craft_industrial_2024_1143'],
    'regulation 2024/1143': ['gi_craft_industrial_2024_1143'],
    '32024r1143': ['gi_craft_industrial_2024_1143'],
    'first craft gi registration eu': ['gi_craft_industrial_2024_1143'],
    'euipo craft register': ['gi_craft_industrial_2024_1143'],
    'indicacion geografica artesanal': ['gi_craft_industrial_2024_1143'],
    'indicación geográfica artesanal': ['gi_craft_industrial_2024_1143'],
    'indicacion geografica industrial': ['gi_craft_industrial_2024_1143'],
    'indicació geogràfica artesanal': ['gi_craft_industrial_2024_1143'],
    'indicació geogràfica industrial': ['gi_craft_industrial_2024_1143'],
    'indication geographique artisanale': ['gi_craft_industrial_2024_1143'],
    'indication geographique industrielle': ['gi_craft_industrial_2024_1143'],
    'indicazione geografica artigianale': ['gi_craft_industrial_2024_1143'],
    'indicazione geografica industriale': ['gi_craft_industrial_2024_1143'],
    'ambachtelijke geografische aanduiding': ['gi_craft_industrial_2024_1143'],

    # EIC Scaleup Europe Fund - EQT (NEW guide 19 May 2026)
    'scaleup europe fund': ['eic_scaleup_europe_fund_2026'],
    'scale up europe fund': ['eic_scaleup_europe_fund_2026'],
    'eic scaleup europe fund': ['eic_scaleup_europe_fund_2026'],
    'eqt scaleup europe': ['eic_scaleup_europe_fund_2026'],
    'eqt scaleup europe fund': ['eic_scaleup_europe_fund_2026'],
    'ip 26 1102': ['eic_scaleup_europe_fund_2026'],
    'eu venture capital fund of funds': ['eic_scaleup_europe_fund_2026'],
    'eu growth stage scale up financing': ['eic_scaleup_europe_fund_2026'],
    'fondo escalado europa': ['eic_scaleup_europe_fund_2026'],
    'fons d escalat europa': ['eic_scaleup_europe_fund_2026'],
    'fonds croissance europe eic': ['eic_scaleup_europe_fund_2026'],
    'fondo europeo scaleup': ['eic_scaleup_europe_fund_2026'],
    'europees scaleup fonds': ['eic_scaleup_europe_fund_2026'],

    # FDI Screening - 19 May 2026 plenary vote anchor
    'fdi screening vote may 2026': ['eu_fdi_screening_regulation'],
    'foreign investment screening plenary vote': ['eu_fdi_screening_regulation'],
    'recast fdi screening adopted': ['eu_fdi_screening_regulation'],

    # Steel safeguards 19 May 2026 plenary vote
    'steel safeguards vote 2026': ['eu_trade_defence'],
    'eu steel safeguards plenary vote': ['eu_trade_defence'],
    'salvaguardias acero ue': ['eu_trade_defence'],
    'salvaguardes acer ue': ['eu_trade_defence'],
    'sauvegardes acier ue': ['eu_trade_defence'],
    'salvaguardie acciaio ue': ['eu_trade_defence'],
    'vrijwaringsmaatregelen staal eu': ['eu_trade_defence'],

    # Syria sanctions package 18 May 2026
    'syria sanctions package may 2026': ['eu_sanctions_implementation_framework'],
    '32026d1105': ['eu_sanctions_implementation_framework'],
    '32026r1107': ['eu_sanctions_implementation_framework'],
    '32026d1106': ['eu_sanctions_implementation_framework'],
    'sancions siria maig 2026': ['eu_sanctions_implementation_framework'],
    'sanciones siria mayo 2026': ['eu_sanctions_implementation_framework'],
    'sanctions syrie mai 2026': ['eu_sanctions_implementation_framework'],
    'sanzioni siria maggio 2026': ['eu_sanctions_implementation_framework'],
    'sancties syrie mei 2026': ['eu_sanctions_implementation_framework'],

    # Schengen resilience report 18 May 2026
    'schengen resilience report': ['eu_migration_asylum_pact'],
    'commission schengen report 2026': ['eu_migration_asylum_pact'],
    'ip 26 1015': ['eu_migration_asylum_pact'],
    'informe resiliencia schengen': ['eu_migration_asylum_pact'],
    'informe resiliencia schengen ue': ['eu_migration_asylum_pact'],
    'informe resiliència schengen': ['eu_migration_asylum_pact'],
    'rapport resilience schengen': ['eu_migration_asylum_pact'],
    'rapporto resilienza schengen': ['eu_migration_asylum_pact'],
    'verslag schengen veerkracht': ['eu_migration_asylum_pact'],

    # === 20 May 2026: Strasbourg plenary day 3 + EU-US trade deal struck + Fertiliser Plan publication ===

    # EU-US trade deal closure (Council Presidency + EP provisional agreement)
    'eu us trade deal struck': ['eu_us_trade_deal_2026'],
    'eu us trade deal closed': ['eu_us_trade_deal_2026'],
    'eu us trade deal provisional agreement': ['eu_us_trade_deal_2026'],
    'council parliament strike trade deal': ['eu_us_trade_deal_2026'],
    'eu us tariff deal struck': ['eu_us_trade_deal_2026'],
    'trump tariff deal eu': ['eu_us_trade_deal_2026'],
    'joint statement tariff implementation': ['eu_us_trade_deal_2026'],
    'michael damianos': ['eu_us_trade_deal_2026'],
    'damianos trade minister': ['eu_us_trade_deal_2026'],
    'cypriot presidency trade': ['eu_us_trade_deal_2026'],
    'cyprus presidency eu us': ['eu_us_trade_deal_2026'],
    'sunrise clause removed': ['eu_us_trade_deal_2026'],
    'sunset clause 2029': ['eu_us_trade_deal_2026'],
    'sunset clause end 2029': ['eu_us_trade_deal_2026'],
    'lobster duty suspension extension': ['eu_us_trade_deal_2026'],
    'lobster tariff retroactive': ['eu_us_trade_deal_2026'],
    'processed lobster duty': ['eu_us_trade_deal_2026'],
    'industrial goods duty removal us': ['eu_us_trade_deal_2026'],
    'tariff rate quotas us': ['eu_us_trade_deal_2026'],
    'eu us deal more stable footing': ['eu_us_trade_deal_2026'],
    'acuerdo comercial ue eeuu cerrado': ['eu_us_trade_deal_2026'],
    'acord comercial ue eua tancat': ['eu_us_trade_deal_2026'],
    'accord commercial ue eu conclu': ['eu_us_trade_deal_2026'],
    'accordo commerciale ue usa concluso': ['eu_us_trade_deal_2026'],
    'handelsovereenkomst eu vs gesloten': ['eu_us_trade_deal_2026'],

    # Fertiliser Action Plan — formal publication 19 May
    'fertilisers action plan published': ['fertilisers_action_plan_2026'],
    'fertiliser action plan published': ['fertilisers_action_plan_2026'],
    'fertilisers supply food security plan': ['fertilisers_action_plan_2026'],
    'europe plan fertiliser supply': ['fertilisers_action_plan_2026'],
    'commission presents fertiliser plan': ['fertilisers_action_plan_2026'],
    'fitto hansen fertiliser': ['fertilisers_action_plan_2026'],
    'q&a fertiliser action plan': ['fertilisers_action_plan_2026'],
    'questions answers fertiliser action plan': ['fertilisers_action_plan_2026'],
    'eurostat fertilisers price q4 2025': ['fertilisers_action_plan_2026'],
    'fertilisers price 8 percent': ['fertilisers_action_plan_2026'],
    'fertilisers price increase': ['fertilisers_action_plan_2026'],
    'circular mineral fertilisers': ['fertilisers_action_plan_2026'],
    'recovered nutrients waste streams': ['fertilisers_action_plan_2026'],
    'green ammonia eu': ['fertilisers_action_plan_2026'],
    'electrified haber bosch': ['fertilisers_action_plan_2026'],
    'plan fertilizantes publicado': ['fertilisers_action_plan_2026'],
    'pla fertilitzants publicat': ['fertilisers_action_plan_2026'],
    'plan engrais publie': ['fertilisers_action_plan_2026'],
    'piano fertilizzanti pubblicato': ['fertilisers_action_plan_2026'],
    'meststoffenactieplan gepubliceerd': ['fertilisers_action_plan_2026'],

    # Right to Stay — rural stakeholder Call for Evidence info session
    'rural stakeholder call for evidence': ['eu_demographic_right_to_stay_strategy'],
    'right to stay call for evidence': ['eu_demographic_right_to_stay_strategy'],
    'rural stakeholders contribute right to stay': ['eu_demographic_right_to_stay_strategy'],
    'rural pact call for evidence': ['eu_demographic_right_to_stay_strategy'],
    'leader local action groups right to stay': ['eu_demographic_right_to_stay_strategy'],
    'consulta partes interesadas rurales': ['eu_demographic_right_to_stay_strategy'],
    'consulta parts interessades rurals': ['eu_demographic_right_to_stay_strategy'],
    'consultation parties rurales': ['eu_demographic_right_to_stay_strategy'],
    'consultazione parti interessate rurali': ['eu_demographic_right_to_stay_strategy'],
    'consultatie rurale belanghebbenden': ['eu_demographic_right_to_stay_strategy'],

    # AI Act high-risk classification guidelines consultation
    'ai act high risk classification guidelines': ['ai_act_regulation', 'ai_act_amendments_2026'],
    'high risk ai classification consultation': ['ai_act_regulation', 'ai_act_amendments_2026'],
    'annex iii high risk consultation': ['ai_act_regulation'],
    'cnect high risk ai consultation': ['ai_act_regulation'],
    'article 6 ai act guidelines': ['ai_act_regulation'],
    'draft guidelines high risk ai': ['ai_act_regulation'],
    'significant risk of harm ai': ['ai_act_regulation'],
    'de minimis ai high risk': ['ai_act_regulation'],
    'conformity assessment ai providers': ['ai_act_regulation'],
    'directrices clasificacion ia alto riesgo': ['ai_act_regulation'],
    'directius classificacio ia alt risc': ['ai_act_regulation'],
    'lignes directrices classification ia haut risque': ['ai_act_regulation'],
    'linee guida classificazione ia alto rischio': ['ai_act_regulation'],
    'richtsnoeren classificatie ai hoog risico': ['ai_act_regulation'],

    # Migrant returns deal — trilogue closing
    'migrant returns deal': ['eu_migration_asylum_pact'],
    'eu return regulation deal': ['eu_migration_asylum_pact'],
    'return regulation trilogue': ['eu_migration_asylum_pact'],
    'return regulation provisional agreement': ['eu_migration_asylum_pact'],
    'safe third country definition': ['eu_migration_asylum_pact'],
    'return hubs migrants': ['eu_migration_asylum_pact'],
    'return sponsorship arrangements': ['eu_migration_asylum_pact'],
    'mutual recognition return decisions': ['eu_migration_asylum_pact'],
    'com(2025)101': ['eu_migration_asylum_pact'],
    'com(2025) 101': ['eu_migration_asylum_pact'],
    '2025/0033(cod)': ['eu_migration_asylum_pact'],
    'pacto retornos migrantes': ['eu_migration_asylum_pact'],
    'pacte retorns migrants': ['eu_migration_asylum_pact'],
    'accord retours migrants': ['eu_migration_asylum_pact'],
    'accordo rimpatri migranti': ['eu_migration_asylum_pact'],
    'akkoord terugkeer migranten': ['eu_migration_asylum_pact'],

    # ECCC cybersecurity experts recruitment
    'eccc cybersecurity experts': ['cybersecurity_act'],
    'european cybersecurity competence centre experts': ['cybersecurity_act'],
    'eccc funding programmes': ['cybersecurity_act'],
    'eccc bucharest experts': ['cybersecurity_act'],
    'eccc seconded national experts': ['cybersecurity_act'],
    'cybersecurity industrial technology research competence centre': ['cybersecurity_act'],
    'national coordination centres cybersecurity': ['cybersecurity_act'],
    'expertos ciberseguridad eccc': ['cybersecurity_act'],
    'experts ciberseguretat eccc': ['cybersecurity_act'],
    'experts cybersecurite eccc': ['cybersecurity_act'],
    'esperti cybersicurezza eccc': ['cybersecurity_act'],
    'experts cyberbeveiliging eccc': ['cybersecurity_act'],

    # DG CNECT copyright consultation 18 May 2026
    'eu copyright consultation 2026': ['copyright_generative_ai'],
    'review eu copyright rules consultation': ['copyright_generative_ai'],
    'copyright omnibus consultation': ['copyright_generative_ai'],
    'consulta drets autor ue 2026': ['copyright_generative_ai'],
    'consulta derechos autor ue 2026': ['copyright_generative_ai'],
    'consultation droit auteur ue 2026': ['copyright_generative_ai'],
    'consultazione diritto autore ue 2026': ['copyright_generative_ai'],
    'raadpleging auteursrecht eu 2026': ['copyright_generative_ai'],

    # EU fertilisers strategy 19 May 2026 plenary
    'eu fertilisers strategy': ['common_agricultural_policy'],
    'eu fertilizers strategy': ['common_agricultural_policy'],
    'fertilisers action plan eu': ['common_agricultural_policy'],
    'cow manure recycling eu': ['common_agricultural_policy'],
    'estrategia fertilizantes ue': ['common_agricultural_policy'],
    'estrategia fertilitzants ue': ['common_agricultural_policy'],
    'strategie engrais ue': ['common_agricultural_policy'],
    'strategia fertilizzanti ue': ['common_agricultural_policy'],
    'meststoffenstrategie eu': ['common_agricultural_policy'],

    # EU Solidarity Fund 18 May 2026 EUR 144M Spain Romania Cyprus
    'eu solidarity fund spain romania cyprus': ['eu_budget_emu_law'],
    'eusf may 2026 144 million': ['eu_budget_emu_law'],
    'ip 26 1092': ['eu_budget_emu_law'],
    'fondo solidaridad ue espana rumania chipre': ['eu_budget_emu_law'],
    'fons solidaritat ue espanya romania xipre': ['eu_budget_emu_law'],
    'fonds solidarite ue espagne roumanie chypre': ['eu_budget_emu_law'],
    'fondo solidarieta ue spagna romania cipro': ['eu_budget_emu_law'],
    'solidariteitsfonds eu spanje roemenie cyprus': ['eu_budget_emu_law'],

    # Industrial biotech consultation DG GROW 18 May 2026
    'industrial biotech consultation eu': ['biotech_act'],
    'biomanufacturing consultation eu': ['biotech_act'],
    'biotech act ii consultation': ['biotech_act'],
    'consulta biotecnologia industrial ue': ['biotech_act'],
    'consultation biotechnologie industrielle ue': ['biotech_act'],
    'consultazione biotecnologia industriale ue': ['biotech_act'],
    'raadpleging industriele biotechnologie eu': ['biotech_act'],

    # HTA JCA update 18 May 2026 + new conformity Implementing Reg
    'joint clinical assessment update 2026': ['eu_pharmaceutical_framework'],
    'hta jca q and a update': ['eu_pharmaceutical_framework'],
    'conformity assessment notified bodies implementing reg 2026': ['eu_pharmaceutical_framework'],
    'evaluacion clinica conjunta actualizacion 2026': ['eu_pharmaceutical_framework'],
    'avaluació clínica conjunta actualització 2026': ['eu_pharmaceutical_framework'],
    'evaluation clinique conjointe mise a jour 2026': ['eu_pharmaceutical_framework'],
    'valutazione clinica congiunta aggiornamento 2026': ['eu_pharmaceutical_framework'],
    'gezamenlijke klinische beoordeling update 2026': ['eu_pharmaceutical_framework'],

    # Cyber-capable / frontier AI plenary debate 19 May 2026
    'cyber capable ai models': ['ai_act_amendments_2026'],
    'frontier ai cyber security plenary': ['ai_act_amendments_2026'],
    'advanced ai models security eu': ['ai_act_amendments_2026'],
    'modelos ia frontera seguridad': ['ai_act_amendments_2026'],
    'models ia frontera seguretat': ['ai_act_amendments_2026'],
    'modeles ia frontiere securite': ['ai_act_amendments_2026'],
    'modelli ia frontiera sicurezza': ['ai_act_amendments_2026'],
    'geavanceerde ai modellen veiligheid': ['ai_act_amendments_2026'],

    # Anti-Poverty plenary debate 20 May 2026
    'anti poverty strategy 2050 plenary': ['eu_anti_poverty_strategy_2026'],
    'end poverty eu 2050 debate': ['eu_anti_poverty_strategy_2026'],
    'estrategia antipobreza 2050 ue': ['eu_anti_poverty_strategy_2026'],
    'estrategia contra la pobreza ue 2050': ['eu_anti_poverty_strategy_2026'],
    'estratègia contra la pobresa ue 2050': ['eu_anti_poverty_strategy_2026'],
    'strategie contre la pauvrete ue 2050': ['eu_anti_poverty_strategy_2026'],
    'strategia contro la poverta ue 2050': ['eu_anti_poverty_strategy_2026'],
    'eu armoedebestrijdingsstrategie 2050': ['eu_anti_poverty_strategy_2026'],

    # Victims' rights revision plenary 20 May 2026
    'victims rights revision plenary 2026': ['victims_rights_directive_revision'],
    'directiva victimas crimen revision 2026': ['victims_rights_directive_revision'],
    'directiva víctimes delicte revisió 2026': ['victims_rights_directive_revision'],
    'directive victimes crime revision 2026': ['victims_rights_directive_revision'],
    'direttiva vittime reato revisione 2026': ['victims_rights_directive_revision'],
    'richtlijn slachtoffers misdrijven herziening 2026': ['victims_rights_directive_revision'],

    # Workplace safety plenary 20 May 2026
    'workplace safety plenary debate 2026': ['occupational_health_safety'],
    'reducing work accidents eu': ['occupational_health_safety'],
    'vision zero workplace deaths': ['occupational_health_safety'],
    'seguridad laboral debate plenario 2026': ['occupational_health_safety'],
    'seguretat laboral debat plenari 2026': ['occupational_health_safety'],
    'securite travail plenum 2026': ['occupational_health_safety'],
    'sicurezza lavoro plenaria 2026': ['occupational_health_safety'],
    'veiligheid op het werk plenair 2026': ['occupational_health_safety'],

    # Short-Term Rentals Transparency Regulation 2024/1028 (applies 20 May 2026)
    'short term rentals regulation': ['short_term_rentals_regulation'],
    'short term rentals transparency': ['short_term_rentals_regulation'],
    'short term rental data sharing': ['short_term_rentals_regulation'],
    'str regulation 2024 1028': ['short_term_rentals_regulation'],
    'reg 2024 1028': ['short_term_rentals_regulation'],
    'regulation eu 2024 1028': ['short_term_rentals_regulation'],
    '32024r1028': ['short_term_rentals_regulation'],
    'airbnb booking transparency rules': ['short_term_rentals_regulation'],
    'single digital entry point str': ['short_term_rentals_regulation'],
    'host registration number eu': ['short_term_rentals_regulation'],
    'sdep short term rental': ['short_term_rentals_regulation'],
    'str transparency rules eu apply': ['short_term_rentals_regulation'],
    'str host registration eu': ['short_term_rentals_regulation'],
    'platform random checks str': ['short_term_rentals_regulation'],
    'opt in str registration': ['short_term_rentals_regulation'],
    'alquileres corta duracion ue transparencia': ['short_term_rentals_regulation'],
    'reglamento alquileres turisticos ue 2024 1028': ['short_term_rentals_regulation'],
    'lloguers curta durada ue transparencia': ['short_term_rentals_regulation'],
    'reglament lloguers turistics ue 2024 1028': ['short_term_rentals_regulation'],
    'locations courte duree ue transparence': ['short_term_rentals_regulation'],
    'reglement locations touristiques ue 2024 1028': ['short_term_rentals_regulation'],
    'locazioni breve durata ue trasparenza': ['short_term_rentals_regulation'],
    'regolamento locazioni turistiche ue 2024 1028': ['short_term_rentals_regulation'],
    'kortetermijnverhuur eu transparantie': ['short_term_rentals_regulation'],
    'verordening korte termijn verhuur eu 2024 1028': ['short_term_rentals_regulation'],

    # ViDA: VAT in the Digital Age 2026 Work Programme
    'vat in the digital age': ['vat_in_the_digital_age_2026'],
    'vida directive': ['vat_in_the_digital_age_2026'],
    'vida 2026 work programme': ['vat_in_the_digital_age_2026'],
    'vida 2026 implementation': ['vat_in_the_digital_age_2026'],
    'directive eu 2025 516': ['vat_in_the_digital_age_2026'],
    '32025l0516': ['vat_in_the_digital_age_2026'],
    'reg eu 2025 517 vat': ['vat_in_the_digital_age_2026'],
    '32025r0517': ['vat_in_the_digital_age_2026'],
    'digital reporting requirements vat': ['vat_in_the_digital_age_2026'],
    'drr e-invoicing eu': ['vat_in_the_digital_age_2026'],
    'mandatory e-invoicing 2030': ['vat_in_the_digital_age_2026'],
    'platform deemed supplier vat': ['vat_in_the_digital_age_2026'],
    'single vat registration eu': ['vat_in_the_digital_age_2026'],
    'svr 2028 vat': ['vat_in_the_digital_age_2026'],
    'oss extension e charging': ['vat_in_the_digital_age_2026'],
    'en 16931 e-invoicing standard': ['vat_in_the_digital_age_2026'],
    'iva en la era digital': ['vat_in_the_digital_age_2026'],
    'iva era digital programa trabajo': ['vat_in_the_digital_age_2026'],
    'iva era digital ue': ['vat_in_the_digital_age_2026'],
    'iva a era digital ue': ['vat_in_the_digital_age_2026'],
    'iva era digitale ue programma lavoro': ['vat_in_the_digital_age_2026'],
    'iva era digital catala': ['vat_in_the_digital_age_2026'],
    'tva ere numerique ue': ['vat_in_the_digital_age_2026'],
    'tva ere numerique programme travail': ['vat_in_the_digital_age_2026'],
    'btw digitale tijdperk eu': ['vat_in_the_digital_age_2026'],
    'btw digitale tijdperk werkprogramma': ['vat_in_the_digital_age_2026'],

    # ETS Review Hoekstra plenary remarks 20 May 2026
    'ets review competitiveness debate': ['eu_ets_review_2026'],
    'hoekstra ets plenary remarks': ['eu_ets_review_2026'],
    'reviewing ets system support european competitiveness': ['eu_ets_review_2026'],
    'ets 7 july 2026 review': ['eu_ets_review_2026'],
    'revisione ets competitivita': ['eu_ets_review_2026'],
    'revision ets competitividad': ['eu_ets_review_2026'],
    'revisio ets competitivitat': ['eu_ets_review_2026'],
    'revision ets competitivite': ['eu_ets_review_2026'],
    'herziening ets concurrentievermogen': ['eu_ets_review_2026'],

    # Western Balkans EUR 158.9M Growth Plan disbursement 20 May 2026
    'western balkans growth plan 158 million': ['eu_funding_ipa_enlargement'],
    'reform growth facility tranche albania montenegro north macedonia': ['eu_funding_ipa_enlargement'],
    'rgf disbursement 158 9 million': ['eu_funding_ipa_enlargement'],
    'plan crecimiento balcanes occidentales 158 millones': ['eu_funding_ipa_enlargement'],
    'pla creixement balcans occidentals 158 milions': ['eu_funding_ipa_enlargement'],
    'plan croissance balkans occidentaux 158 millions': ['eu_funding_ipa_enlargement'],
    'piano crescita balcani occidentali 158 milioni': ['eu_funding_ipa_enlargement'],
    'groeiplan westelijke balkan 158 miljoen': ['eu_funding_ipa_enlargement'],

    # Gender care gap and care society (P10_TA(2026)0190 adopted 21 May 2026)
    'gender care gap': ['eu_gender_care_gap_society'],
    'care society eu': ['eu_gender_care_gap_society'],
    'european care strategy update': ['eu_gender_care_gap_society'],
    'formal informal carers eu': ['eu_gender_care_gap_society'],
    'long term care directive eu': ['eu_gender_care_gap_society'],
    'p10 ta 2026 0190': ['eu_gender_care_gap_society'],
    'advancing care society addressing gender care gap': ['eu_gender_care_gap_society'],
    'barcelona targets care eu': ['eu_gender_care_gap_society'],
    'work life balance directive carers leave': ['eu_gender_care_gap_society'],
    'brecha cuidados genero ue': ['eu_gender_care_gap_society'],
    'estrategia cuidados europea': ['eu_gender_care_gap_society'],
    'sociedad cuidados ue': ['eu_gender_care_gap_society'],
    'bretxa cures genere ue': ['eu_gender_care_gap_society'],
    'estrategia cures europea': ['eu_gender_care_gap_society'],
    'ecart de soins genre ue': ['eu_gender_care_gap_society'],
    'strategie europeenne soins': ['eu_gender_care_gap_society'],
    'societe care ue': ['eu_gender_care_gap_society'],
    'divario cura genere ue': ['eu_gender_care_gap_society'],
    'strategia europea assistenza': ['eu_gender_care_gap_society'],
    'societa cura ue': ['eu_gender_care_gap_society'],
    'genderkloof zorg eu': ['eu_gender_care_gap_society'],
    'europese zorgstrategie': ['eu_gender_care_gap_society'],
    'zorgsamenleving eu': ['eu_gender_care_gap_society'],

    # Periodic roadworthiness checks revision 2026 (TRAN trilogue mandate 21 May 2026)
    'periodic roadworthiness checks': ['eu_roadworthiness_periodic_checks_2026'],
    'roadworthiness directive revision': ['eu_roadworthiness_periodic_checks_2026'],
    'periodic vehicle checks eu': ['eu_roadworthiness_periodic_checks_2026'],
    'directive 2014 45 eu revision': ['eu_roadworthiness_periodic_checks_2026'],
    'directive 2014 46 eu revision': ['eu_roadworthiness_periodic_checks_2026'],
    'directive 2014 47 eu revision': ['eu_roadworthiness_periodic_checks_2026'],
    'roadside inspection commercial vehicles eu': ['eu_roadworthiness_periodic_checks_2026'],
    'odometer fraud eu directive': ['eu_roadworthiness_periodic_checks_2026'],
    'ev battery health roadworthiness': ['eu_roadworthiness_periodic_checks_2026'],
    'adas calibration roadworthiness eu': ['eu_roadworthiness_periodic_checks_2026'],
    'tran trilogue periodic checks': ['eu_roadworthiness_periodic_checks_2026'],
    'inspeccion tecnica vehiculos ue revision': ['eu_roadworthiness_periodic_checks_2026'],
    'itv revision europea': ['eu_roadworthiness_periodic_checks_2026'],
    'inspeccio tecnica vehicles revisio ue': ['eu_roadworthiness_periodic_checks_2026'],
    'controle technique vehicules ue revision': ['eu_roadworthiness_periodic_checks_2026'],
    'revisione periodica veicoli ue': ['eu_roadworthiness_periodic_checks_2026'],
    'revisione veicoli direttiva 2014 45': ['eu_roadworthiness_periodic_checks_2026'],
    'periodieke autokeuring eu herziening': ['eu_roadworthiness_periodic_checks_2026'],
    'apk herziening eu': ['eu_roadworthiness_periodic_checks_2026'],

    # Packaging and Packaging Waste Regulation PPWR (Reg (EU) 2025/40)
    'ppwr': ['eu_packaging_packaging_waste_2025_40'],
    'packaging and packaging waste regulation': ['eu_packaging_packaging_waste_2025_40'],
    'regulation eu 2025 40': ['eu_packaging_packaging_waste_2025_40'],
    'reg 2025 40 packaging': ['eu_packaging_packaging_waste_2025_40'],
    '32025r0040': ['eu_packaging_packaging_waste_2025_40'],
    'packaging conformity declaration annex vii': ['eu_packaging_packaging_waste_2025_40'],
    'epr packaging eu 2028': ['eu_packaging_packaging_waste_2025_40'],
    'recycled content plastic packaging 2030': ['eu_packaging_packaging_waste_2025_40'],
    'reuse targets packaging 2030 2040': ['eu_packaging_packaging_waste_2025_40'],
    'single use packaging bans annex v': ['eu_packaging_packaging_waste_2025_40'],
    'design for recycling packaging': ['eu_packaging_packaging_waste_2025_40'],
    'directive 94 62 ec repealed': ['eu_packaging_packaging_waste_2025_40'],
    'reglamento envases residuos envases ue': ['eu_packaging_packaging_waste_2025_40'],
    'declaracion conformidad envases anexo vii': ['eu_packaging_packaging_waste_2025_40'],
    'reglament envasos residus envasos ue': ['eu_packaging_packaging_waste_2025_40'],
    'declaracio conformitat envasos': ['eu_packaging_packaging_waste_2025_40'],
    'reglement emballages dechets emballages ue': ['eu_packaging_packaging_waste_2025_40'],
    'declaration conformite emballages annexe vii': ['eu_packaging_packaging_waste_2025_40'],
    'regolamento imballaggi rifiuti imballaggio ue': ['eu_packaging_packaging_waste_2025_40'],
    'dichiarazione conformita imballaggi allegato vii': ['eu_packaging_packaging_waste_2025_40'],
    'verordening verpakking verpakkingsafval eu': ['eu_packaging_packaging_waste_2025_40'],
    'conformiteitsverklaring verpakkingen bijlage vii': ['eu_packaging_packaging_waste_2025_40'],

    # Savings and Investment Union (SIU) - successor to CMU
    'savings and investment union': ['savings_and_investment_union'],
    'siu eu': ['savings_and_investment_union'],
    'capital markets union successor': ['savings_and_investment_union'],
    'siu commissioner albuquerque': ['savings_and_investment_union'],
    'maria luis albuquerque siu': ['savings_and_investment_union'],
    'pan eu personal investment savings accounts': ['savings_and_investment_union'],
    'securitisation review eu 2026': ['savings_and_investment_union'],
    'eltif 2 0 implementation': ['savings_and_investment_union'],
    'consolidated tape equities bonds eu': ['savings_and_investment_union'],
    'esma supervisory convergence eu': ['savings_and_investment_union'],
    'pepp review pension': ['savings_and_investment_union'],
    'iorp review eu': ['savings_and_investment_union'],
    'union ahorro inversion ue': ['savings_and_investment_union'],
    'union mercados capitales sucesor': ['savings_and_investment_union'],
    'unio estalvi inversio ue': ['savings_and_investment_union'],
    'union epargne investissement ue': ['savings_and_investment_union'],
    'unione risparmio investimento ue': ['savings_and_investment_union'],
    'spaar en investeringsunie eu': ['savings_and_investment_union'],

    # EU Spring 2026 Economic Forecast (DG ECFIN, 21 May 2026)
    'spring 2026 economic forecast': ['eu_spring_economic_forecast_2026'],
    'european economic forecast spring 2026': ['eu_spring_economic_forecast_2026'],
    'dombrovskis spring forecast': ['eu_spring_economic_forecast_2026'],
    'dg ecfin spring forecast': ['eu_spring_economic_forecast_2026'],
    'european semester spring package 2026': ['eu_spring_economic_forecast_2026'],
    'country specific recommendations 2026': ['eu_spring_economic_forecast_2026'],
    'article 126 reports 2026': ['eu_spring_economic_forecast_2026'],
    'macroeconomic imbalance procedure mip 2026': ['eu_spring_economic_forecast_2026'],
    'reformed stability growth pact spring forecast': ['eu_spring_economic_forecast_2026'],
    'pronostico economico primavera 2026 ue': ['eu_spring_economic_forecast_2026'],
    'previsiones economicas primavera ue 2026': ['eu_spring_economic_forecast_2026'],
    'previsions economiques primavera ue 2026': ['eu_spring_economic_forecast_2026'],
    'previsions economiques printemps 2026 ue': ['eu_spring_economic_forecast_2026'],
    'previsioni economiche primavera 2026 ue': ['eu_spring_economic_forecast_2026'],
    'economische voorjaarsraming 2026 eu': ['eu_spring_economic_forecast_2026'],

    # ePrivacy CSAM Derogation Extension (2025/0429(COD) — Reg 2021/1232 amendment)
    'eprivacy csam derogation extension': ['eu_eprivacy_csam_derogation_2025_0429'],
    'regulation 2021 1232 extension': ['eu_eprivacy_csam_derogation_2025_0429'],
    'reg 2021 1232 derogation': ['eu_eprivacy_csam_derogation_2025_0429'],
    '32021r1232': ['eu_eprivacy_csam_derogation_2025_0429'],
    'com 2025 797': ['eu_eprivacy_csam_derogation_2025_0429'],
    'birgit sippel csam': ['eu_eprivacy_csam_derogation_2025_0429'],
    'libe csam derogation extension': ['eu_eprivacy_csam_derogation_2025_0429'],
    'chat control derogation extension': ['eu_eprivacy_csam_derogation_2025_0429'],
    'voluntary csam scanning eu': ['eu_eprivacy_csam_derogation_2025_0429'],
    'derogacion eprivacy csam ue': ['eu_eprivacy_csam_derogation_2025_0429'],
    'derogacio eprivacy csam ue': ['eu_eprivacy_csam_derogation_2025_0429'],
    'derogation eprivacy csam ue': ['eu_eprivacy_csam_derogation_2025_0429'],
    'deroga eprivacy csam ue': ['eu_eprivacy_csam_derogation_2025_0429'],
    'eprivacy uitzondering csam eu': ['eu_eprivacy_csam_derogation_2025_0429'],

    # Consular Protection for Unrepresented Citizens 2023/0441(CNS)
    'consular protection unrepresented citizens': ['eu_consular_protection_unrepresented_citizens_2023_0441'],
    'consular protection eu third countries': ['eu_consular_protection_unrepresented_citizens_2023_0441'],
    'directive 2015 637 revision': ['eu_consular_protection_unrepresented_citizens_2023_0441'],
    '32015l0637': ['eu_consular_protection_unrepresented_citizens_2023_0441'],
    'com 2023 930 consular': ['eu_consular_protection_unrepresented_citizens_2023_0441'],
    'lena dupont consular': ['eu_consular_protection_unrepresented_citizens_2023_0441'],
    'article 23 tfeu consular protection': ['eu_consular_protection_unrepresented_citizens_2023_0441'],
    'protection consulaire citoyens ue': ['eu_consular_protection_unrepresented_citizens_2023_0441'],
    'proteccion consular ciudadanos ue': ['eu_consular_protection_unrepresented_citizens_2023_0441'],
    'proteccio consular ciutadans ue': ['eu_consular_protection_unrepresented_citizens_2023_0441'],
    'protezione consolare cittadini ue': ['eu_consular_protection_unrepresented_citizens_2023_0441'],
    'consulaire bescherming burgers eu': ['eu_consular_protection_unrepresented_citizens_2023_0441'],

    # Combating Firearms Trafficking 2026/0059(COD)
    'firearms trafficking eu': ['eu_firearms_trafficking_directive_2026_0059'],
    'combating firearms trafficking directive': ['eu_firearms_trafficking_directive_2026_0059'],
    'eu firearms criminal law harmonisation': ['eu_firearms_trafficking_directive_2026_0059'],
    'com 2026 102 firearms': ['eu_firearms_trafficking_directive_2026_0059'],
    'evin incir firearms trafficking': ['eu_firearms_trafficking_directive_2026_0059'],
    'ghost guns eu directive': ['eu_firearms_trafficking_directive_2026_0059'],
    '3d printed firearms eu': ['eu_firearms_trafficking_directive_2026_0059'],
    'directive 2021 555 complement': ['eu_firearms_trafficking_directive_2026_0059'],
    '32021l0555': ['eu_firearms_trafficking_directive_2026_0059'],
    'trafico armas fuego ue': ['eu_firearms_trafficking_directive_2026_0059'],
    'trafic armes feu ue': ['eu_firearms_trafficking_directive_2026_0059'],
    'trafic armes a feu directive': ['eu_firearms_trafficking_directive_2026_0059'],
    'traffico armi da fuoco ue': ['eu_firearms_trafficking_directive_2026_0059'],
    'wapenhandel eu richtlijn': ['eu_firearms_trafficking_directive_2026_0059'],

    # Drug Precursors Monitoring 2025/0384(COD)
    'drug precursors monitoring': ['eu_drug_precursors_monitoring_2025_0384'],
    'regulation 273 2004 revision drug precursors': ['eu_drug_precursors_monitoring_2025_0384'],
    'regulation 111 2005 revision': ['eu_drug_precursors_monitoring_2025_0384'],
    '32004r0273': ['eu_drug_precursors_monitoring_2025_0384'],
    '32005r0111': ['eu_drug_precursors_monitoring_2025_0384'],
    'com 2025 747 drug precursors': ['eu_drug_precursors_monitoring_2025_0384'],
    'sienkiewicz bay drug precursors': ['eu_drug_precursors_monitoring_2025_0384'],
    'synthetic drug precursors eu': ['eu_drug_precursors_monitoring_2025_0384'],
    'fentanyl precursors eu': ['eu_drug_precursors_monitoring_2025_0384'],
    'euda emcdda drug precursors': ['eu_drug_precursors_monitoring_2025_0384'],
    'precursores drogas ue regulacion': ['eu_drug_precursors_monitoring_2025_0384'],
    'precursors drogues ue regulacio': ['eu_drug_precursors_monitoring_2025_0384'],
    'precurseurs drogues ue reglement': ['eu_drug_precursors_monitoring_2025_0384'],
    'precursori droghe ue regolamento': ['eu_drug_precursors_monitoring_2025_0384'],
    'drugsprecursoren eu verordening': ['eu_drug_precursors_monitoring_2025_0384'],

    # European Globalisation Adjustment Fund EGF
    'european globalisation adjustment fund': ['eu_egf_european_globalisation_adjustment_fund'],
    'egf workers displaced': ['eu_egf_european_globalisation_adjustment_fund'],
    'regulation 2021 691 egf': ['eu_egf_european_globalisation_adjustment_fund'],
    '32021r0691': ['eu_egf_european_globalisation_adjustment_fund'],
    'mass redundancies eu fund': ['eu_egf_european_globalisation_adjustment_fund'],
    'workers at risk job loss eu': ['eu_egf_european_globalisation_adjustment_fund'],
    'eu workers and skills fund': ['eu_egf_european_globalisation_adjustment_fund'],
    'audi brussels closure egf': ['eu_egf_european_globalisation_adjustment_fund'],
    'fondo europeo adaptacion globalizacion': ['eu_egf_european_globalisation_adjustment_fund'],
    'fons europeu adaptacio globalitzacio': ['eu_egf_european_globalisation_adjustment_fund'],
    'fonds europeen ajustement mondialisation': ['eu_egf_european_globalisation_adjustment_fund'],
    'fondo europeo adeguamento globalizzazione': ['eu_egf_european_globalisation_adjustment_fund'],
    'europees fonds globalisering eu': ['eu_egf_european_globalisation_adjustment_fund'],

    # Just Transition Fund JTF
    'just transition fund eu': ['eu_just_transition_fund'],
    'jtf 17 5 billion': ['eu_just_transition_fund'],
    'just transition mechanism three pillars': ['eu_just_transition_fund'],
    'regulation 2021 1056 jtf': ['eu_just_transition_fund'],
    '32021r1056': ['eu_just_transition_fund'],
    'just transition platform 2026 beneficiaries': ['eu_just_transition_fund'],
    'territorial just transition plans tjtps': ['eu_just_transition_fund'],
    'coal mining regions eu transition': ['eu_just_transition_fund'],
    'fondo transicion justa ue': ['eu_just_transition_fund'],
    'fons transicio justa ue': ['eu_just_transition_fund'],
    'fonds transition juste ue': ['eu_just_transition_fund'],
    'fondo transizione giusta ue': ['eu_just_transition_fund'],
    'fonds rechtvaardige transitie eu': ['eu_just_transition_fund'],

    # Critical Raw Materials Act CRMA (Reg (EU) 2024/1252)
    'critical raw materials act': ['eu_critical_raw_materials_act'],
    'crma 2024 1252': ['eu_critical_raw_materials_act'],
    'regulation 2024 1252 crma': ['eu_critical_raw_materials_act'],
    '32024r1252': ['eu_critical_raw_materials_act'],
    'strategic raw materials eu 2030 targets': ['eu_critical_raw_materials_act'],
    'crma strategic projects': ['eu_critical_raw_materials_act'],
    'eu raw materials partnerships': ['eu_critical_raw_materials_act'],
    'recyclable raw materials net imports': ['eu_critical_raw_materials_act'],
    'rare earths processing eu': ['eu_critical_raw_materials_act'],
    'lithium cobalt nickel eu': ['eu_critical_raw_materials_act'],
    'materias primas criticas ue': ['eu_critical_raw_materials_act'],
    'materies primeres critiques ue': ['eu_critical_raw_materials_act'],
    'matieres premieres critiques ue': ['eu_critical_raw_materials_act'],
    'materie prime critiche ue': ['eu_critical_raw_materials_act'],
    'kritieke grondstoffen eu': ['eu_critical_raw_materials_act'],

    # EU Strategy for the Baltic Sea Region — Norway joins 21 May 2026
    'eu strategy baltic sea region': ['eu_baltic_sea_strategy'],
    'eusbsr norway full member': ['eu_baltic_sea_strategy'],
    'baltic sea macroregional strategy': ['eu_baltic_sea_strategy'],
    'norway joins eusbsr 21 may 2026': ['eu_baltic_sea_strategy'],
    'bemip baltic energy market': ['eu_baltic_sea_strategy'],
    'rail baltica ten t': ['eu_baltic_sea_strategy'],
    'baltic continental grid synchronisation': ['eu_baltic_sea_strategy'],
    'estrategia ue region mar baltico': ['eu_baltic_sea_strategy'],
    'estrategia ue mar baltic regio': ['eu_baltic_sea_strategy'],
    'strategie ue mer baltique': ['eu_baltic_sea_strategy'],
    'strategia ue mar baltico': ['eu_baltic_sea_strategy'],
    'eu strategie oostzeegebied': ['eu_baltic_sea_strategy'],

    # EU Solidarity Fund EUSF (€144M for Spain Romania Cyprus, 21 May 2026 proposal)
    'eu solidarity fund': ['eu_solidarity_fund_eusf'],
    'eusf 144 million spain romania cyprus': ['eu_solidarity_fund_eusf'],
    'fondo solidaridad ue 144 millones': ['eu_solidarity_fund_eusf'],
    'eusf disaster relief eu': ['eu_solidarity_fund_eusf'],
    'natural disaster eu solidarity fund': ['eu_solidarity_fund_eusf'],
    'fitto eusf 144 million': ['eu_solidarity_fund_eusf'],
    'regulation 2012 2002 solidarity fund': ['eu_solidarity_fund_eusf'],
    'sear solidarity emergency aid reserve': ['eu_solidarity_fund_eusf'],
    'fondo solidaridad union europea': ['eu_solidarity_fund_eusf'],
    'fons solidaritat unio europea': ['eu_solidarity_fund_eusf'],
    'fonds solidarite union europeenne': ['eu_solidarity_fund_eusf'],
    'fondo solidarieta unione europea': ['eu_solidarity_fund_eusf'],
    'solidariteitsfonds europese unie': ['eu_solidarity_fund_eusf'],
    'fons solidaritat 144 milions espanya romania xipre': ['eu_solidarity_fund_eusf'],
    'fondo solidarieta 144 milioni spagna romania cipro': ['eu_solidarity_fund_eusf'],
    'fonds solidarite 144 millions espagne roumanie chypre': ['eu_solidarity_fund_eusf'],
    'solidariteitsfonds 144 miljoen spanje roemenie cyprus': ['eu_solidarity_fund_eusf'],
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
        # Per-user / per-org bespoke knowledge bundles (gitignored tree).
        # Loaded on-demand via load_private_guides(slug), never via load_all().
        self.private_guides_dir = self.knowledge_base_dir / "private_guides"

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
    # Private Guides (per-user bespoke bundles, 20 May 2026)
    # =========================================================================

    def load_private_guides(self, slug: str) -> List[Dict[str, Any]]:
        """
        Load a user-specific knowledge bundle.

        Production path: query the private_guides DB table (filled by
        scripts/sync_private_guides_to_db.py). The markdown files in
        backend/knowledge_base/private_guides/{slug}/*.md are the local
        source of truth; the sync script pushes them to DB so Railway can
        serve them without including gitignored files in the image.

        Disk-fallback path: when no DB rows exist (or the query fails),
        fall back to reading the local markdown directly. Useful for local
        development and for tests.

        Args:
            slug: from users.private_guide_slug. Validated against a tight
                  pattern so callers cannot escape the private_guides root.

        Returns:
            List of {filename, title, content, mtime} dicts. Empty list
            when the slug has no content on either path.
        """
        if not slug:
            return []

        # Hard input validation: lowercase letters, digits, dash, underscore.
        # Forbids "..", "/", absolute paths, etc.
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,118}", slug):
            logger.warning("Rejected private_guide slug %r (invalid pattern)", slug)
            return []

        # --- DB-backed path (primary in production) ---
        try:
            from core.database import SessionLocal as _PG_SessionLocal
            from sqlalchemy import text as _sql_text
            db = _PG_SessionLocal()
            try:
                rows = db.execute(
                    _sql_text(
                        "SELECT filename, title, content, last_synced_at "
                        "FROM private_guides "
                        "WHERE slug = :slug AND is_test = FALSE "
                        "ORDER BY ordering, filename"
                    ),
                    {"slug": slug},
                ).fetchall()
            finally:
                db.close()
            if rows:
                # Skip non-content rows (e.g. _meta.json, which lives in
                # private_guides only so /api/tenders can read meta_json).
                return [
                    {
                        "filename": r[0],
                        "title": r[1] or r[0],
                        "content": r[2] or "",
                        "mtime": r[3],
                    }
                    for r in rows
                    if r[0] and r[0].endswith('.md')
                ]
        except Exception as e:
            logger.warning("[private-guide] DB lookup failed for slug=%s: %s (falling back to disk)", slug, e)

        # --- Disk-fallback path (local dev / pre-sync state) ---
        slug_dir = self.private_guides_dir / slug
        try:
            resolved = slug_dir.resolve()
            root = self.private_guides_dir.resolve()
            resolved.relative_to(root)
        except (ValueError, OSError):
            logger.warning("Rejected private_guide slug %r (path escape)", slug)
            return []

        if not slug_dir.is_dir():
            return []

        bundle: List[Dict[str, Any]] = []
        for md_file in sorted(slug_dir.glob("*.md")):
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()
                title = content.lstrip().split("\n", 1)[0].lstrip("# ").strip()
                bundle.append({
                    "filename": md_file.name,
                    "title": title or md_file.stem,
                    "content": content,
                    "mtime": datetime.fromtimestamp(md_file.stat().st_mtime),
                })
            except Exception as e:
                logger.error("Failed to load private guide %s: %s", md_file, e)

        return bundle

    def format_private_guides_block(
        self,
        slug: str,
        max_chars: int = 24000,
    ) -> Optional[str]:
        """
        Build the chat-context block for a user's private guides.

        Wraps the bundle in [PRIVATE USER CONTEXT] ... [/PRIVATE USER CONTEXT]
        markers so the system prompt rule can reference it. Soft cap at
        max_chars (default ~5k tokens) so it cannot starve the rest of the
        retrieval context.

        Returns None when there is nothing to render.
        """
        bundle = self.load_private_guides(slug)
        if not bundle:
            return None

        parts: List[str] = [
            "[PRIVATE USER CONTEXT]",
            (
                "The following information is specific to the authenticated user. "
                "Use it to ground answers in their organisation, tracked files, "
                "uploaded documents, and regulatory exposure. NEVER reveal that "
                "you have a 'private guide'; speak as if you already knew about "
                "the organisation. If asked how you know, say you have studied "
                "their public positions and the EU files they track."
            ),
            "",
        ]
        used = sum(len(p) + 1 for p in parts)

        for item in bundle:
            body = item["content"].strip()
            # Strip a leading "# Heading" line if it matches the title we
            # already render as "### title" — avoids duplicate headings.
            first_line, _, rest = body.partition("\n")
            if first_line.startswith("# "):
                stripped_h1 = first_line[2:].strip()
                if stripped_h1 == item["title"]:
                    body = rest.lstrip()
            chunk = f"### {item['title']}\n\n{body}\n"
            if used + len(chunk) + 32 > max_chars:
                # Truncate this chunk to fit, then stop adding further files.
                remaining = max_chars - used - 32
                if remaining > 400:
                    parts.append(chunk[:remaining] + "\n\n[TRUNCATED]")
                break
            parts.append(chunk)
            used += len(chunk) + 1

        parts.append("[/PRIVATE USER CONTEXT]")
        return "\n".join(parts)

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
        triggered_guides: List[str] = []  # Ordered: longer/more-specific triggers win first
        triggered_seen: set = set()
        matches = []
        seen_ids = set()

        # Pass 1: Keyword trigger matching (highest priority)
        # Check multi-word triggers first (longer = more specific), then single-word
        # Short triggers (<=4 chars) use word-boundary matching to avoid false positives
        # (e.g., "ects" in "insects", "ern" in "modern", "cap" in "capital")
        sorted_triggers = sorted(GUIDE_KEYWORD_TRIGGERS.keys(), key=len, reverse=True)
        for trigger in sorted_triggers:
            matched = False
            if len(trigger) <= 4:
                if re.search(r'(?<![a-z])' + re.escape(trigger) + r'(?![a-z])', query_lower):
                    matched = True
            else:
                if trigger in query_lower:
                    matched = True
            if matched:
                for guide_id in GUIDE_KEYWORD_TRIGGERS[trigger]:
                    if guide_id in self.guides and guide_id not in triggered_seen:
                        triggered_guides.append(guide_id)
                        triggered_seen.add(guide_id)

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
