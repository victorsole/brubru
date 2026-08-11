#!/usr/bin/env python3.12
"""
Backfill / refresh the economy_items table for the /api/v2/ecb folder
(ECB + ECB Banking Supervision) and, later, the other economy bodies.

Sources (verified — see services/scrapers/economy_ecb.py):
  ECB     news=RSS+HTML  publication=RSS+PDF/HTML  event=Playwright  legal=Cellar
  ECB SSM news=RSS+HTML  publication=Playwright    event=Playwright

Usage:
  python3.12 scripts/sync_economy.py --body ecb --type all
  python3.12 scripts/sync_economy.py --body ecb_ssm --type news
  python3.12 scripts/sync_economy.py --all-ecb            # ECB + SSM, every type
  python3.12 scripts/sync_economy.py --all-ecb --no-bodies   # skip detail-page fetch
"""
from __future__ import annotations

import argparse
from functools import partial
import sys
from pathlib import Path

import psycopg2  # noqa: E402
from psycopg2.extras import execute_values  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.scrapers import economy_ecb as e          # noqa: E402
from services.scrapers import economy_eba as eba        # noqa: E402
from services.scrapers import economy_esma as esma      # noqa: E402
from services.scrapers import economy_eiopa as eiopa     # noqa: E402
from services.scrapers import economy_esrb as esrb       # noqa: E402
from services.scrapers import economy_srb as srb         # noqa: E402
from services.scrapers import economy_eib as eib         # noqa: E402
from services.scrapers import economy_amla as amla       # noqa: E402
from services.scrapers import economy_eppo as eppo       # noqa: E402
from services.scrapers import economy_esm as esm         # noqa: E402
from services.scrapers import commission_sanctions as commission_sanctions  # noqa: E402
from services.scrapers import commission_funding as commission_funding  # noqa: E402
from services.scrapers import commission_research as commission_research  # noqa: E402
from services.scrapers import commission_tariff_rulings as commission_tariff_rulings  # noqa: E402
from services.scrapers import commission_taric as commission_taric  # noqa: E402
from services.scrapers import eambrosia as eambrosia  # noqa: E402
from services.scrapers import commission_agridata as commission_agridata  # noqa: E402
from services.scrapers import commission_cap_beneficiaries as commission_cap_beneficiaries  # noqa: E402
from services.scrapers import commission_trade_defence as commission_trade_defence  # noqa: E402
from services.scrapers import commission_comitology as commission_comitology  # noqa: E402
from services.scrapers import commission_expert_groups as commission_expert_groups  # noqa: E402
from services.scrapers import commission_competition_search as commission_competition_search  # noqa: E402
from services.scrapers import commission_rasff as commission_rasff  # noqa: E402
from services.scrapers import ep_mep_declarations as ep_mep_declarations  # noqa: E402
from services.scrapers import ep_mep_assistants as ep_mep_assistants  # noqa: E402
from services.scrapers import ep_supporting_analyses as ep_supporting_analyses  # noqa: E402
from services.scrapers import council_sanctions as council_sanctions  # noqa: E402
from services.scrapers import eea_indicators as eea_indicators  # noqa: E402
from services.scrapers import eea_content as eea_content  # noqa: E402
from services.scrapers import eige_content as eige_content  # noqa: E402
from services.scrapers import cedefop_content as cedefop_content  # noqa: E402
from services.scrapers import euaa_content as euaa_content  # noqa: E402
from services.scrapers import fra_databases as fra_databases  # noqa: E402
from services.scrapers import economy_eeas as eeas  # noqa: E402
from services.scrapers import economy_easa as easa  # noqa: E402
from services.scrapers import economy_emsa as emsa  # noqa: E402
from services.scrapers import economy_era as era_agency  # noqa: E402
from services.scrapers import economy_euspa as euspa  # noqa: E402
from services.scrapers import economy_ela as ela  # noqa: E402
from services.scrapers import economy_efca as efca_agency  # noqa: E402
from services.scrapers import economy_eurofound as eurofound  # noqa: E402
from services.scrapers import economy_etf as etf_agency  # noqa: E402
from services.scrapers import economy_eurojust as eurojust_agency  # noqa: E402
from services.scrapers import economy_cepol as cepol_agency  # noqa: E402
from services.scrapers import economy_europol as europol_agency  # noqa: E402
from services.scrapers import economy_frontex as frontex_agency  # noqa: E402
from services.scrapers import economy_cinea as cinea_agency  # noqa: E402
from services.scrapers import economy_eacea as eacea_agency  # noqa: E402
from services.scrapers import economy_hadea as hadea_agency  # noqa: E402
from services.scrapers import economy_eismea as eismea_agency  # noqa: E402
from services.scrapers import economy_ercea as ercea_agency  # noqa: E402
from services.scrapers import economy_rea as rea_agency  # noqa: E402
from services.scrapers import economy_epso as epso_agency  # noqa: E402
from services.scrapers import economy_eas as eas_agency  # noqa: E402
from services.scrapers import economy_cdt as cdt_agency  # noqa: E402
from services.scrapers import economy_cert_eu as cert_eu_agency  # noqa: E402
from services.scrapers import economy_cjeu as cjeu_agency  # noqa: E402
from services.scrapers import economy_eca as eca_agency  # noqa: E402
from services.scrapers import economy_eesc as eesc_agency  # noqa: E402
from services.scrapers import economy_cor as cor_agency  # noqa: E402
from services.scrapers import economy_ombudsman as ombudsman_agency  # noqa: E402
from services.scrapers import economy_edps as edps_agency  # noqa: E402
from services.scrapers import economy_edpb as edpb_agency  # noqa: E402
from services.scrapers import economy_eccc as eccc_agency  # noqa: E402
from services.scrapers import economy_euiss as euiss_agency  # noqa: E402
from services.scrapers import economy_eda as eda_agency  # noqa: E402
from services.scrapers import economy_satcen as satcen_agency  # noqa: E402
from services.scrapers import economy_esdc as esdc_agency  # noqa: E402
from services.scrapers import economy_ju as ju  # noqa: E402
from services.scrapers import economy_aviation as aviation_agency  # noqa: E402
from services.scrapers import economy_cbe as cbe_agency  # noqa: E402
from services.scrapers import economy_ihi as ihi_agency  # noqa: E402
from services.scrapers import economy_chips as chips_agency  # noqa: E402
from services.scrapers import economy_sesar as sesar_agency  # noqa: E402
from services.scrapers import economy_f4e as f4e_agency  # noqa: E402
from services.scrapers import economy_rail as rail_agency  # noqa: E402
from services.scrapers import economy_sns as sns_agency  # noqa: E402
from services.scrapers import agency_procurement as agency_procurement  # noqa: E402
from services.scrapers import agency_consultations as agency_consultations  # noqa: E402
from services.scrapers import echa_candidate_list as echa_candidate_list  # noqa: E402
from services.scrapers import echa_news as echa_news  # noqa: E402
from services.scrapers import euda_publications as euda_publications  # noqa: E402
from services.scrapers import euda_content as euda_content  # noqa: E402
from services.scrapers import economy_berec as berec     # noqa: E402
from services.scrapers import economy_acer as acer       # noqa: E402
from services.scrapers import economy_eit as eit         # noqa: E402
from services.scrapers import economy_enisa as enisa     # noqa: E402
from services.scrapers import economy_eulisa as eulisa   # noqa: E402
from services.scrapers import economy_euipo as euipo     # noqa: E402
from services.scrapers import economy_cpvo as cpvo       # noqa: E402
from services.scrapers import economy_ema as ema         # noqa: E402
from services.scrapers import economy_ecdc as ecdc       # noqa: E402
from services.scrapers import economy_efsa as efsa       # noqa: E402
from services.scrapers import economy_eu_osha as eu_osha # noqa: E402
from services.scrapers import economy_interoperable as interoperable  # noqa: E402
from services.scrapers import economy_eugovtech as eugovtech  # noqa: E402
from scripts._specialised_helpers import ChunkedDb       # noqa: E402

# (body_code, item_type) -> callable returning list[Item]
from services.scrapers import dpp as dpp_scraper

INGESTORS = {
    # Digital Product Passport — only the two feeds that change; the curated
    # acts/sectors/standards/data-points are rebuilt by backfill_dpp_folder.py.
    ("dpp", "news"):            dpp_scraper.ingest_dpp_news,
    ("dpp", "event"):           dpp_scraper.ingest_dpp_events,

    # EU Interoperable — Interoperable Europe Portal (Playwright; local refresh).
    ("interoperable", "news"):       interoperable.ingest_interoperable_news,
    ("interoperable", "event"):      interoperable.ingest_interoperable_events,
    ("interoperable", "solution"):   interoperable.ingest_interoperable_solutions,
    ("interoperable", "collection"): interoperable.ingest_interoperable_collections,
    # EC GovTech — EU GovTech sub-portal (Playwright; local refresh).
    ("eugovtech", "news"):           eugovtech.ingest_eugovtech_news,
    ("eugovtech", "event"):          eugovtech.ingest_eugovtech_events,
    ("eugovtech", "solution"):       eugovtech.ingest_eugovtech_solutions,
    ("eugovtech", "publication"):    eugovtech.ingest_eugovtech_publications,
    ("eugovtech", "topic"):          eugovtech.ingest_eugovtech_topics,
    ("ecb", "dataset"):         e.ingest_ecb_datasets,
    ("ecb", "news"):            e.ingest_ecb_news,
    ("ecb", "publication"):     e.ingest_ecb_publications,
    ("ecb", "event"):           e.ingest_ecb_events,
    ("ecb", "legal"):           e.fetch_ecb_legal_acts,
    ("ecb_ssm", "news"):        e.ingest_ssm_news,
    ("ecb_ssm", "publication"): e.ingest_ssm_publications,
    ("ecb_ssm", "event"):       e.ingest_ssm_events,
    ("eba", "news"):            eba.ingest_eba_news,
    ("eba", "publication"):     eba.ingest_eba_publications,
    ("eba", "event"):           eba.ingest_eba_events,
    ("eba", "credit_institution"): eba.ingest_eba_credit_institutions,
    ("esma", "news"):           esma.ingest_esma_news,
    ("esma", "publication"):    esma.ingest_esma_publications,
    ("esma", "financial_instrument"): esma.ingest_esma_financial_instruments,
    ("eiopa", "news"):          eiopa.ingest_eiopa_news,
    ("eiopa", "publication"):   eiopa.ingest_eiopa_publications,
    ("eiopa", "event"):         eiopa.ingest_eiopa_events,
    ("esrb", "news"):           esrb.ingest_esrb_news,
    ("esrb", "publication"):    esrb.ingest_esrb_publications,
    ("esrb", "event"):          esrb.ingest_esrb_events,
    ("srb", "news"):            srb.ingest_srb_news,
    ("srb", "publication"):     srb.ingest_srb_publications,
    ("srb", "event"):           srb.ingest_srb_events,
    ("eib", "news"):            eib.ingest_eib_news,
    ("eib", "publication"):     eib.ingest_eib_publications,
    ("eib", "event"):           eib.ingest_eib_events,
    ("eib", "project"):         eib.ingest_eib_projects,
    ("amla", "news"):           amla.ingest_amla_news,
    ("amla", "publication"):    amla.ingest_amla_publications,
    ("amla", "event"):          amla.ingest_amla_events,
    ("eppo", "news"):           eppo.ingest_eppo_news,
    ("eppo", "publication"):    eppo.ingest_eppo_publications,
    ("esm", "news"):            esm.ingest_esm_news,
    ("esm", "publication"):     esm.ingest_esm_publications,
    ("esm", "event"):           esm.ingest_esm_events,
    ("esm", "programme"):       esm.ingest_esm_programmes,
    # European Commission database folders.
    ("commission", "financial_sanction"): commission_sanctions.ingest_financial_sanctions,
    ("commission", "funding_recipient"): commission_funding.ingest_eu_funding_recipients,
    ("commission", "research_project"): commission_research.ingest_research_projects,
    ("commission", "tariff_ruling"): commission_tariff_rulings.ingest_tariff_rulings,
    ("commission", "tariff_code"): commission_taric.ingest_taric_tariffs,
    ("commission", "geographical_indication"): eambrosia.ingest_eambrosia_gis,
    ("commission", "third_country_gi"): eambrosia.ingest_eambrosia_third_country,
    ("commission", "agri_data_series"): commission_agridata.ingest_agridata_catalogue,
    ("commission", "cap_beneficiary_portal"): commission_cap_beneficiaries.ingest_cap_beneficiaries,
    ("commission", "trade_defence_case"): commission_trade_defence.ingest_trade_defence,
    ("commission", "comitology_committee"): commission_comitology.ingest_comitology,
    ("commission", "expert_group"): commission_expert_groups.ingest_expert_groups,
    ("commission", "dma_case"): commission_competition_search.ingest_dma_cases,
    ("commission", "state_aid_case"): commission_competition_search.ingest_state_aid,
    ("commission", "rasff_notification"): commission_rasff.ingest_rasff,
    ("parliament", "mep_declaration"): ep_mep_declarations.ingest_mep_declarations,
    ("parliament", "mep_assistant_register"): ep_mep_assistants.ingest_mep_assistants,
    ("parliament", "supporting_analysis"): ep_supporting_analyses.ingest_supporting_analyses,
    ("council", "sanctions_regime"): council_sanctions.ingest_council_sanctions,
    ("eea", "environmental_indicator"): eea_indicators.ingest_eea_indicators,
    ("eea", "news"): eea_content.ingest_eea_news,
    ("eea", "event"): eea_content.ingest_eea_events,
    ("eea", "topic"): eea_content.ingest_eea_topics,
    ("eige", "news"): eige_content.ingest_eige_news,
    ("eige", "event"): eige_content.ingest_eige_events,
    ("eige", "publication"): eige_content.ingest_eige_publications,
    ("eige", "topic"): eige_content.ingest_eige_topics,
    ("cedefop", "news"): cedefop_content.ingest_cedefop_news,
    ("cedefop", "event"): cedefop_content.ingest_cedefop_events,
    ("cedefop", "publication"): cedefop_content.ingest_cedefop_publications,
    ("cedefop", "topic"): cedefop_content.ingest_cedefop_topics,
    ("euaa", "news"): euaa_content.ingest_euaa_news,
    ("euaa", "topic"): euaa_content.ingest_euaa_topics,
    ("fra", "case_law"): fra_databases.ingest_fra_case_law,
    ("efca", "tender"): agency_procurement.ingest_efca_tenders,
    ("efca", "eoi_call"): agency_procurement.ingest_efca_calls,
    ("cedefop", "tender"): agency_procurement.ingest_cedefop_tenders,
    ("cedefop", "eoi_call"): agency_procurement.ingest_cedefop_calls,
    ("ema", "tender"): agency_procurement.ingest_ema_tenders,
    ("efsa", "tender"): agency_procurement.ingest_efsa_tenders,
    ("eurojust", "tender"): agency_procurement.ingest_eurojust_tenders,
    ("etf", "tender"): agency_procurement.ingest_etf_tenders,
    # Coverage-gap closers (15 Jun 2026): bring the labelled agencies in
    # line with the ingested ones so the Tenderator agency feed shows all
    # decentralised EU bodies, not just the original 6.
    ("euaa", "eoi_call"): agency_procurement.ingest_euaa_calls,
    ("euda", "tender"): agency_procurement.ingest_euda_tenders,
    ("enisa", "tender"): agency_procurement.ingest_enisa_tenders,
    ("enisa", "eoi_call"): agency_procurement.ingest_enisa_calls,
    ("era", "tender"): agency_procurement.ingest_era_tenders,
    ("ecdc", "tender"): agency_procurement.ingest_ecdc_tenders,
    ("echa", "tender"): agency_procurement.ingest_echa_tenders,
    ("echa", "eoi_call"): agency_procurement.ingest_echa_calls,
    ("eige", "tender"): agency_procurement.ingest_eige_tenders,
    ("fra", "tender"): agency_procurement.ingest_fra_tenders,
    ("eea", "tender"): agency_procurement.ingest_eea_tenders,
    ("eu_osha", "tender"): agency_procurement.ingest_eu_osha_tenders,
    ("eu_osha", "eoi_call"): agency_procurement.ingest_eu_osha_calls,
    ("eurofound", "tender"): agency_procurement.ingest_eurofound_tenders,
    ("eurofound", "eoi_call"): agency_procurement.ingest_eurofound_calls,
    # Move 3 (15 Jun 2026): EIB procurement via TED API v3
    ("eib", "tender"): agency_procurement.ingest_eib_procurement,
    # Move 5 (15 Jun 2026): EU-institution framework contracts via TED API v3.
    # One scraper call writes rows under multiple body_codes (commission/eib/
    # parliament/council/ecb/eeas) with item_type='framework'. Registered
    # against EIB (batch 1 in cron's _ECONOMY_BATCHES) so the daily sweep
    # fires it — commission is explicitly excluded from _ECONOMY_BATCHES so
    # keying off it would leave Move 5 invisible to cron.
    ("eib", "framework"): agency_procurement.ingest_eu_institution_frameworks,
    ("ema", "consultation"): agency_consultations.ingest_ema_consultations,
    ("berec", "consultation"): agency_consultations.ingest_berec_consultations,
    ("eiopa", "consultation"): agency_consultations.ingest_eiopa_consultations,
    ("amla", "consultation"): agency_consultations.ingest_amla_consultations,
    ("echa", "consultation"): agency_consultations.ingest_echa_consultations,
    ("acer", "consultation"): agency_consultations.ingest_acer_consultations,
    ("srb", "consultation"): agency_consultations.ingest_srb_consultations,
    ("ecb_ssm", "consultation"): agency_consultations.ingest_ecb_ssm_consultations,
    # EASA + ERA consultations are Playwright-rendered — run with system python3.12
    # (has Chromium), local only; not on Railway cron.
    ("easa", "consultation"): agency_consultations.ingest_easa_consultations,
    ("era", "consultation"): agency_consultations.ingest_era_consultations,
    ("fra", "charter_article"): fra_databases.ingest_fra_charterpedia,
    ("fra", "topic"): fra_databases.ingest_fra_topics,
    ("echa", "svhc_substance"): echa_candidate_list.ingest_echa_candidate_list,
    ("echa", "news"): echa_news.ingest_echa_news,
    ("echa", "topic"): echa_news.ingest_echa_topics,
    ("euda", "publication"): euda_publications.ingest_euda_publications,
    ("euda", "news"): euda_content.ingest_euda_news,
    ("euda", "event"): euda_content.ingest_euda_events,
    ("euda", "topic"): euda_content.ingest_euda_topics,
    ("berec", "news"):          berec.ingest_berec_news,
    ("berec", "publication"):   berec.ingest_berec_publications,
    ("berec", "event"):         berec.ingest_berec_events,
    ("berec", "topic"):         berec.ingest_berec_topics,
    ("acer", "news"):           acer.ingest_acer_news,
    ("acer", "publication"):    acer.ingest_acer_publications,
    ("acer", "topic"):          acer.ingest_acer_topics,
    ("eit", "news"):            eit.ingest_eit_news,
    ("eit", "event"):           eit.ingest_eit_events,
    ("eit", "topic"):           eit.ingest_eit_topics,
    ("enisa", "news"):          enisa.ingest_enisa_news,
    ("enisa", "publication"):   enisa.ingest_enisa_publications,
    ("enisa", "topic"):         enisa.ingest_enisa_topics,
    ("eu_lisa", "news"):        eulisa.ingest_eulisa_news,
    ("eu_lisa", "publication"): eulisa.ingest_eulisa_publications,
    ("eu_lisa", "event"):       eulisa.ingest_eulisa_events,
    ("eu_lisa", "topic"):       eulisa.ingest_eulisa_topics,
    ("euipo", "news"):          euipo.ingest_euipo_news,
    ("euipo", "event"):         euipo.ingest_euipo_events,
    ("euipo", "trademark"):     euipo.ingest_euipo_trademarks,
    ("euipo", "topic"):         euipo.ingest_euipo_topics,
    ("euipo", "geographical_indication"): euipo.ingest_euipo_giview,
    ("cpvo", "news"):           cpvo.ingest_cpvo_news,
    ("cpvo", "publication"):    cpvo.ingest_cpvo_publications,
    ("cpvo", "event"):          cpvo.ingest_cpvo_events,
    ("cpvo", "topic"):          cpvo.ingest_cpvo_topics,
    ("ema", "news"):            ema.ingest_ema_news,
    ("ema", "event"):           ema.ingest_ema_events,
    ("ema", "medicine"):        ema.ingest_ema_medicines,
    ("ema", "topic"):           ema.ingest_ema_topics,
    ("ecdc", "news"):           ecdc.ingest_ecdc_news,
    ("ecdc", "publication"):    ecdc.ingest_ecdc_publications,
    ("ecdc", "surveillance_topic"): ecdc.ingest_ecdc_surveillance,
    ("ecdc", "topic"):          ecdc.ingest_ecdc_topics,
    ("efsa", "news"):           efsa.ingest_efsa_news,
    ("efsa", "publication"):    efsa.ingest_efsa_publications,
    ("efsa", "topic"):          efsa.ingest_efsa_topics,
    ("eu_osha", "news"):        eu_osha.ingest_eu_osha_news,
    ("eu_osha", "publication"): eu_osha.ingest_eu_osha_publications,
    ("eu_osha", "event"):       eu_osha.ingest_eu_osha_events,
    ("eu_osha", "topic"):       eu_osha.ingest_eu_osha_topics,
    # European External Action Service (api_eeas.md) — Playwright-rendered, local
    # only (Chromium not on Railway cron), same as FRA / EASA / ERA.
    ("eeas", "news"):           eeas.ingest_eeas_news,
    ("eeas", "publication"):    eeas.ingest_eeas_publications,
    ("eeas", "event"):          eeas.ingest_eeas_events,
    ("eeas", "tender"):         eeas.ingest_eeas_tenders,
    ("eeas", "topic"):          eeas.ingest_eeas_topics,
    # Decentralised agencies (api_socjust.md) — server-rendered Drupal, plain requests.
    ("easa", "news"):           easa.ingest_easa_news,
    ("easa", "publication"):    easa.ingest_easa_publications,
    ("easa", "event"):          easa.ingest_easa_events,
    ("easa", "topic"):          easa.ingest_easa_topics,
    ("emsa", "news"):           emsa.ingest_emsa_news,
    ("emsa", "publication"):    emsa.ingest_emsa_publications,
    ("emsa", "topic"):          emsa.ingest_emsa_topics,
    ("era", "news"):            era_agency.ingest_era_news,
    ("era", "publication"):     era_agency.ingest_era_publications,
    ("era", "event"):           era_agency.ingest_era_events,
    ("era", "topic"):           era_agency.ingest_era_topics,
    ("euspa", "news"):          euspa.ingest_euspa_news,
    ("euspa", "publication"):   euspa.ingest_euspa_publications,
    ("euspa", "event"):         euspa.ingest_euspa_events,
    ("euspa", "topic"):         euspa.ingest_euspa_topics,
    ("ela", "news"):            ela.ingest_ela_news,
    ("ela", "topic"):           ela.ingest_ela_topics,
    ("efca", "news"):           efca_agency.ingest_efca_news,
    ("efca", "topic"):          efca_agency.ingest_efca_topics,
    ("eurofound", "publication"): eurofound.ingest_eurofound_publications,
    ("eurofound", "topic"):     eurofound.ingest_eurofound_topics,
    ("etf", "news"):            etf_agency.ingest_etf_news,
    ("etf", "event"):           etf_agency.ingest_etf_events,
    ("etf", "topic"):           etf_agency.ingest_etf_topics,
    ("eurojust", "news"):       eurojust_agency.ingest_eurojust_news,
    ("eurojust", "topic"):      eurojust_agency.ingest_eurojust_topics,
    ("cepol", "news"):          cepol_agency.ingest_cepol_news,
    ("cepol", "topic"):         cepol_agency.ingest_cepol_topics,
    ("europol", "news"):        europol_agency.ingest_europol_news,
    ("europol", "topic"):       europol_agency.ingest_europol_topics,
    ("frontex", "news"):        frontex_agency.ingest_frontex_news,
    ("frontex", "topic"):       frontex_agency.ingest_frontex_topics,
    ("cinea", "news"):          cinea_agency.ingest_cinea_news,
    ("cinea", "event"):         cinea_agency.ingest_cinea_events,
    ("cinea", "topic"):         cinea_agency.ingest_cinea_topics,
    ("eacea", "news"):          eacea_agency.ingest_eacea_news,
    ("eacea", "event"):         eacea_agency.ingest_eacea_events,
    ("eacea", "publication"):   eacea_agency.ingest_eacea_publications,
    ("eacea", "topic"):         eacea_agency.ingest_eacea_topics,
    ("hadea", "news"):          hadea_agency.ingest_hadea_news,
    ("hadea", "event"):         hadea_agency.ingest_hadea_events,
    ("hadea", "call"):          hadea_agency.ingest_hadea_calls,
    ("hadea", "tender"):        hadea_agency.ingest_hadea_tenders,
    ("hadea", "topic"):         hadea_agency.ingest_hadea_topics,
    ("eismea", "news"):         eismea_agency.ingest_eismea_news,
    ("eismea", "event"):        eismea_agency.ingest_eismea_events,
    ("eismea", "publication"):  eismea_agency.ingest_eismea_publications,
    ("eismea", "call"):         eismea_agency.ingest_eismea_calls,
    ("eismea", "topic"):        eismea_agency.ingest_eismea_topics,
    ("ercea", "news"):          ercea_agency.ingest_ercea_news,
    ("ercea", "event"):         ercea_agency.ingest_ercea_events,
    ("ercea", "publication"):   ercea_agency.ingest_ercea_publications,
    ("ercea", "topic"):         ercea_agency.ingest_ercea_topics,
    ("rea", "news"):            rea_agency.ingest_rea_news,
    ("rea", "event"):           rea_agency.ingest_rea_events,
    ("rea", "publication"):     rea_agency.ingest_rea_publications,
    ("rea", "topic"):           rea_agency.ingest_rea_topics,
    ("epso", "news"):           epso_agency.ingest_epso_news,
    ("epso", "topic"):          epso_agency.ingest_epso_topics,
    ("eas", "publication"):     eas_agency.ingest_eas_publications,
    ("eas", "topic"):           eas_agency.ingest_eas_topics,
    ("cdt", "news"):            cdt_agency.ingest_cdt_news,
    ("cdt", "topic"):           cdt_agency.ingest_cdt_topics,
    ("cert_eu", "news"):        cert_eu_agency.ingest_cert_eu_news,
    ("cert_eu", "advisory"):    cert_eu_agency.ingest_cert_eu_advisories,
    ("cert_eu", "publication"): cert_eu_agency.ingest_cert_eu_publications,
    ("cert_eu", "topic"):       cert_eu_agency.ingest_cert_eu_topics,
    ("cjeu", "press_release"):  cjeu_agency.ingest_cjeu_press_releases,
    ("cjeu", "case_law"):       cjeu_agency.ingest_cjeu_case_law,
    ("cjeu", "event"):          cjeu_agency.ingest_cjeu_events,
    ("cjeu", "topic"):          cjeu_agency.ingest_cjeu_topics,
    ("eca", "news"):            eca_agency.ingest_eca_news,
    ("eca", "publication"):     eca_agency.ingest_eca_publications,
    ("eca", "event"):           eca_agency.ingest_eca_events,
    ("eca", "topic"):           eca_agency.ingest_eca_topics,
    ("eesc", "news"):           eesc_agency.ingest_eesc_news,
    ("eesc", "press_release"):  eesc_agency.ingest_eesc_press_releases,
    ("eesc", "opinion"):        eesc_agency.ingest_eesc_opinions,
    ("eesc", "event"):          eesc_agency.ingest_eesc_events,
    ("eesc", "topic"):          eesc_agency.ingest_eesc_topics,
    ("cor", "news"):            cor_agency.ingest_cor_news,
    ("cor", "opinion"):         cor_agency.ingest_cor_opinions,
    ("cor", "topic"):           cor_agency.ingest_cor_topics,
    ("ombudsman", "news"):      ombudsman_agency.ingest_ombudsman_news,
    ("ombudsman", "topic"):     ombudsman_agency.ingest_ombudsman_topics,
    ("edps", "news"):           edps_agency.ingest_edps_news,
    ("edps", "press_release"):  edps_agency.ingest_edps_press_releases,
    ("edps", "publication"):    edps_agency.ingest_edps_publications,
    ("edps", "topic"):          edps_agency.ingest_edps_topics,
    ("edpb", "news"):           edpb_agency.ingest_edpb_news,
    ("edpb", "document"):       edpb_agency.ingest_edpb_documents,
    ("edpb", "public_consultation"): edpb_agency.ingest_edpb_public_consultations,
    ("edpb", "topic"):          edpb_agency.ingest_edpb_topics,
    ("eccc", "news"):           eccc_agency.ingest_eccc_news,
    ("eccc", "call"):           eccc_agency.ingest_eccc_calls,
    ("eccc", "governing_board"): eccc_agency.ingest_eccc_governing_board,
    ("eccc", "ncc"):            eccc_agency.ingest_eccc_nccs,
    ("eccc", "topic"):          eccc_agency.ingest_eccc_topics,
    ("euiss", "news"):          euiss_agency.ingest_euiss_news,
    ("euiss", "publication"):   euiss_agency.ingest_euiss_publications,
    ("euiss", "event"):         euiss_agency.ingest_euiss_events,
    ("euiss", "topic"):         euiss_agency.ingest_euiss_topics,
    ("eda", "news"):            eda_agency.ingest_eda_news,
    ("eda", "publication"):     eda_agency.ingest_eda_publications,
    ("eda", "event"):           eda_agency.ingest_eda_events,
    ("eda", "topic"):           eda_agency.ingest_eda_topics,
    ("satcen", "news"):         satcen_agency.ingest_satcen_news,
    ("satcen", "topic"):        satcen_agency.ingest_satcen_topics,
    ("esdc", "news"):           esdc_agency.ingest_esdc_news,
    ("esdc", "topic"):          esdc_agency.ingest_esdc_topics,
    ("hydrogen", "news"): partial(ju.ingest_ecl, "hydrogen", "news"),
    ("hydrogen", "event"): partial(ju.ingest_ecl, "hydrogen", "event"),
    ("hydrogen", "publication"): partial(ju.ingest_ecl, "hydrogen", "publication"),
    ("hydrogen", "topic"): partial(ju.ingest_topics, "hydrogen"),
    ("edctp3", "news"): partial(ju.ingest_ecl, "edctp3", "news"),
    ("edctp3", "event"): partial(ju.ingest_ecl, "edctp3", "event"),
    ("edctp3", "topic"): partial(ju.ingest_topics, "edctp3"),
    ("eurohpc", "news"): partial(ju.ingest_ecl, "eurohpc", "news"),
    ("eurohpc", "event"): partial(ju.ingest_ecl, "eurohpc", "event"),
    ("eurohpc", "topic"): partial(ju.ingest_topics, "eurohpc"),
    ("euratom", "publication"): partial(ju.ingest_ecl, "euratom", "publication"),
    ("euratom", "topic"): partial(ju.ingest_topics, "euratom"),
    ("aviation", "news"):       aviation_agency.ingest_aviation_news,
    ("aviation", "topic"):      aviation_agency.ingest_aviation_topics,
    ("cbe", "news"):            cbe_agency.ingest_cbe_news,
    ("cbe", "topic"):           cbe_agency.ingest_cbe_topics,
    ("ihi", "topic"):           ihi_agency.ingest_ihi_topics,
    ("chips", "news"):          chips_agency.ingest_chips_news,
    ("chips", "event"):         chips_agency.ingest_chips_events,
    ("chips", "topic"):         chips_agency.ingest_chips_topics,
    ("sesar", "news"):          sesar_agency.ingest_sesar_news,
    ("sesar", "publication"):   sesar_agency.ingest_sesar_publications,
    ("sesar", "event"):         sesar_agency.ingest_sesar_events,
    ("sesar", "topic"):         sesar_agency.ingest_sesar_topics,
    ("f4e", "press_release"):   f4e_agency.ingest_f4e_press_releases,
    ("f4e", "publication"):     f4e_agency.ingest_f4e_publications,
    ("f4e", "topic"):           f4e_agency.ingest_f4e_topics,
    ("rail", "news"):           rail_agency.ingest_rail_news,
    ("rail", "topic"):          rail_agency.ingest_rail_topics,
    ("sns", "publication"):     sns_agency.ingest_sns_publications,
    ("sns", "topic"):           sns_agency.ingest_sns_topics,
}

# EMA register datasets (downloadable .xlsx) — one resource per dataset.
INGESTORS.update({("ema", _c["item_type"]): ema.EMA_DATASET_INGESTORS[_c["item_type"]]
                  for _c in ema.EMA_DATASETS})
# EFSA scientific databases (Zenodo .xlsx).
INGESTORS.update({("efsa", _c["item_type"]): efsa.EFSA_DATASET_INGESTORS[_c["item_type"]]
                  for _c in efsa.EFSA_DATASETS})

_UPSERT = """
INSERT INTO economy_items
  (body_code, item_type, title, summary, public_url, body_txt, body_html,
   document_date, creation_date, source_kind, guid)
VALUES
  (%(body_code)s, %(item_type)s, %(title)s, %(summary)s, %(public_url)s, %(body_txt)s,
   %(body_html)s, %(document_date)s, %(creation_date)s, %(source_kind)s, %(guid)s)
ON CONFLICT (body_code, item_type, public_url) DO UPDATE SET
  title         = EXCLUDED.title,
  summary       = EXCLUDED.summary,
  body_txt      = EXCLUDED.body_txt,
  body_html     = EXCLUDED.body_html,
  document_date = EXCLUDED.document_date,
  source_kind   = EXCLUDED.source_kind,
  guid          = EXCLUDED.guid,
  creation_date = COALESCE(economy_items.creation_date, EXCLUDED.creation_date),
  fetched_at    = now();
"""


_UPSERT_BATCH = """
INSERT INTO economy_items
  (body_code, item_type, title, summary, public_url, body_txt, body_html,
   document_date, creation_date, source_kind, guid)
VALUES %s
ON CONFLICT (body_code, item_type, public_url) DO UPDATE SET
  title         = EXCLUDED.title,
  summary       = EXCLUDED.summary,
  body_txt      = EXCLUDED.body_txt,
  body_html     = EXCLUDED.body_html,
  document_date = EXCLUDED.document_date,
  source_kind   = EXCLUDED.source_kind,
  guid          = EXCLUDED.guid,
  creation_date = COALESCE(economy_items.creation_date, EXCLUDED.creation_date),
  fetched_at    = now();
"""


def _run_one(db: ChunkedDb, body: str, itype: str, *, fetch_bodies: bool, legal_limit: int) -> int:
    fn = INGESTORS[(body, itype)]
    if itype == "legal":
        items = fn(limit=legal_limit)
    else:
        items = fn(fetch_bodies=fetch_bodies)
    # Dedupe within this run by the conflict target so a single multi-row INSERT
    # never tries to upsert the same (body_code, item_type, public_url) twice
    # (ON CONFLICT DO UPDATE cannot affect one row twice in the same statement).
    by_url: dict = {}
    for it in items:
        if it.public_url:
            by_url[(it.body_code, it.item_type, it.public_url)] = it
    rows = [(it.body_code, it.item_type, it.title, it.summary, it.public_url, it.body_txt,
             it.body_html, it.document_date, it.creation_date, it.source_kind, it.guid)
            for it in by_url.values()]
    # Batched multi-row upsert via execute_values — orders of magnitude fewer
    # round-trips than row-by-row (essential for large datasets like FTS ~118k).
    batch = 500
    n = 0
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        for attempt in range(3):
            try:
                execute_values(db.cur, _UPSERT_BATCH, chunk, page_size=batch)
                db.commit()
                break
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                # Supabase dropped the connection — reconnect and retry the chunk.
                try:
                    db.cur.close(); db.conn.close()
                except Exception:
                    pass
                db.conn = psycopg2.connect(db._dsn, connect_timeout=15)
                db.conn.autocommit = db._autocommit
                db.cur = db.conn.cursor()
                if attempt == 2:
                    raise
        n += len(chunk)
        if n % 5000 == 0 or i + batch >= len(rows):
            print(f"    {body}/{itype}: {n}/{len(rows)} upserted", flush=True)
    print(f"[OK] {body}/{itype}: upserted {n} items", flush=True)
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description="Backfill economy_items (ECB folder).")
    ap.add_argument("--body", choices=["dpp", "ecb", "ecb_ssm", "eba", "esma", "eiopa", "esrb", "srb", "eib", "amla", "eppo", "esm", "berec", "acer", "eit", "enisa", "eu_lisa", "euipo", "cpvo",
                             "ema", "ecdc", "efsa", "eu_osha", "commission", "parliament", "council", "eea", "echa", "emsa", "euda", "eige", "cedefop", "euaa", "fra", "eeas", "efca", "eurojust", "etf", "easa", "era", "euspa", "ela", "eurofound", "cepol", "europol", "frontex", "cinea", "eacea", "hadea", "eismea", "ercea", "rea", "epso", "eas", "cdt", "cert_eu", "cjeu", "eca", "eesc", "cor", "ombudsman", "edps", "edpb", "eccc", "euiss", "eda", "satcen", "esdc", "hydrogen", "edctp3", "eurohpc", "euratom", "aviation", "cbe", "ihi", "chips", "sesar", "f4e", "rail", "sns", "interoperable", "eugovtech"])
    ap.add_argument("--type", default="all",
                    help="'all' (every resource registered for the body) or a specific item_type.")
    ap.add_argument("--all-ecb", action="store_true", help="ECB + SSM, every available type")
    ap.add_argument("--no-bodies", action="store_true", help="skip detail-page body fetch (faster)")
    ap.add_argument("--legal-limit", type=int, default=200)
    args = ap.parse_args()

    if args.all_ecb:
        targets = [k for k in INGESTORS]
    elif args.body:
        if args.type == "all":
            targets = [(b, t) for (b, t) in INGESTORS if b == args.body]
        else:
            targets = [(args.body, args.type)] if (args.body, args.type) in INGESTORS else []
        if not targets:
            ap.error(f"no ingestor for body={args.body} type={args.type}")
    else:
        ap.error("pass --body or --all-ecb")

    db = ChunkedDb(autocommit=False)
    total = 0
    try:
        for body, itype in targets:
            try:
                total += _run_one(db, body, itype, fetch_bodies=not args.no_bodies,
                                  legal_limit=args.legal_limit)
            except Exception as exc:  # one resource failing must not abort the rest
                db.rollback()
                print(f"[ERROR] {body}/{itype}: {exc}", flush=True)
        print(f"[DONE] total upserted: {total}", flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
