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
from scripts._specialised_helpers import ChunkedDb       # noqa: E402

# (body_code, item_type) -> callable returning list[Item]
INGESTORS = {
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
    ("eige", "news"): eige_content.ingest_eige_news,
    ("eige", "event"): eige_content.ingest_eige_events,
    ("eige", "publication"): eige_content.ingest_eige_publications,
    ("cedefop", "news"): cedefop_content.ingest_cedefop_news,
    ("cedefop", "event"): cedefop_content.ingest_cedefop_events,
    ("cedefop", "publication"): cedefop_content.ingest_cedefop_publications,
    ("euaa", "news"): euaa_content.ingest_euaa_news,
    ("fra", "case_law"): fra_databases.ingest_fra_case_law,
    ("efca", "tender"): agency_procurement.ingest_efca_tenders,
    ("efca", "eoi_call"): agency_procurement.ingest_efca_calls,
    ("cedefop", "tender"): agency_procurement.ingest_cedefop_tenders,
    ("cedefop", "eoi_call"): agency_procurement.ingest_cedefop_calls,
    ("ema", "tender"): agency_procurement.ingest_ema_tenders,
    ("efsa", "tender"): agency_procurement.ingest_efsa_tenders,
    ("eurojust", "tender"): agency_procurement.ingest_eurojust_tenders,
    ("etf", "tender"): agency_procurement.ingest_etf_tenders,
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
    ("echa", "svhc_substance"): echa_candidate_list.ingest_echa_candidate_list,
    ("echa", "news"): echa_news.ingest_echa_news,
    ("euda", "publication"): euda_publications.ingest_euda_publications,
    ("euda", "news"): euda_content.ingest_euda_news,
    ("euda", "event"): euda_content.ingest_euda_events,
    ("berec", "news"):          berec.ingest_berec_news,
    ("berec", "publication"):   berec.ingest_berec_publications,
    ("berec", "event"):         berec.ingest_berec_events,
    ("acer", "news"):           acer.ingest_acer_news,
    ("acer", "publication"):    acer.ingest_acer_publications,
    ("eit", "news"):            eit.ingest_eit_news,
    ("eit", "event"):           eit.ingest_eit_events,
    ("enisa", "news"):          enisa.ingest_enisa_news,
    ("enisa", "publication"):   enisa.ingest_enisa_publications,
    ("eu_lisa", "news"):        eulisa.ingest_eulisa_news,
    ("eu_lisa", "publication"): eulisa.ingest_eulisa_publications,
    ("eu_lisa", "event"):       eulisa.ingest_eulisa_events,
    ("euipo", "news"):          euipo.ingest_euipo_news,
    ("euipo", "event"):         euipo.ingest_euipo_events,
    ("euipo", "trademark"):     euipo.ingest_euipo_trademarks,
    ("euipo", "geographical_indication"): euipo.ingest_euipo_giview,
    ("cpvo", "news"):           cpvo.ingest_cpvo_news,
    ("cpvo", "publication"):    cpvo.ingest_cpvo_publications,
    ("cpvo", "event"):          cpvo.ingest_cpvo_events,
    ("ema", "news"):            ema.ingest_ema_news,
    ("ema", "event"):           ema.ingest_ema_events,
    ("ema", "medicine"):        ema.ingest_ema_medicines,
    ("ecdc", "news"):           ecdc.ingest_ecdc_news,
    ("ecdc", "publication"):    ecdc.ingest_ecdc_publications,
    ("ecdc", "surveillance_topic"): ecdc.ingest_ecdc_surveillance,
    ("efsa", "news"):           efsa.ingest_efsa_news,
    ("efsa", "publication"):    efsa.ingest_efsa_publications,
    ("eu_osha", "news"):        eu_osha.ingest_eu_osha_news,
    ("eu_osha", "publication"): eu_osha.ingest_eu_osha_publications,
    ("eu_osha", "event"):       eu_osha.ingest_eu_osha_events,
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
    ap.add_argument("--body", choices=["ecb", "ecb_ssm", "eba", "esma", "eiopa", "esrb", "srb", "eib", "amla", "eppo", "esm", "berec", "acer", "eit", "enisa", "eu_lisa", "euipo", "cpvo",
                             "ema", "ecdc", "efsa", "eu_osha", "commission", "parliament", "council", "eea", "echa", "euda", "eige", "cedefop", "euaa", "fra", "efca", "eurojust", "etf", "easa", "era"])
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
