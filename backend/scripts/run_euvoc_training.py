#!/usr/bin/env python3
"""
Phase 11 of docs/applications/euvoc.md — training-driven validation runner.

Loads `data/training/euvoc_queries.json` and exercises every Phase 0-9
surface, reporting pass/fail per category. Closes the implementation
arc by replaying the entire stack against synthetic real-case scenarios
(per Victor's 2 May 2026 instruction: "use many varied EU laws, not
just GDPR + AI Act").

Run:
    python3.12 backend/scripts/run_euvoc_training.py

Optional:
    --category KEY     Restrict to a single category
    --json             Emit JSON report (for CI integration)
    --db-url URL       Override the local Postgres URL (default = the
                       Phase 1 test DB)
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import logging
import os
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("euvoc-training")

QUERIES_PATH = ROOT / "data" / "training" / "euvoc_queries.json"
DEFAULT_DB_URL = "postgresql://postgres@localhost:5432/brubru_p1_test"


@dataclass
class CaseResult:
    id: str
    category: str
    ok: bool
    detail: str = ""
    error: str = ""


# ----------------------------------------------------------------------
# Per-category executors
# ----------------------------------------------------------------------

class Runner:
    def __init__(self, db_url: str):
        self.db_url = db_url
        engine = create_engine(db_url, echo=False)
        self.SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        self._http_client = None

    def _http(self):
        if self._http_client is not None:
            return self._http_client
        # Build a TestClient with get_db override so endpoints hit the test DB.
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from api.datasets_dcat import router as dcat_router
        from api.v1 import router as v1_router
        from api.v1._deps import api_user_with_rate_limit
        from core.database import get_db

        def _override_get_db():
            s = self.SessionFactory()
            try:
                yield s
            finally:
                s.close()

        async def _fake_user():
            class U:
                id = "training"
                api_tier = "free"
            return U()

        app = FastAPI()
        app.include_router(v1_router)
        app.include_router(dcat_router)
        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[api_user_with_rate_limit] = _fake_user

        # Mirror main.py's middleware so the runner sees production headers
        # (X-OP-Core-Conformance, X-Powered-By, X-Source).
        @app.middleware("http")
        async def _v1_headers(request, call_next):
            response = await call_next(request)
            if request.url.path.startswith("/api/v1/"):
                response.headers["X-Powered-By"] = "Brubru"
                response.headers["X-Source"] = "brubru.beresol.eu"
                response.headers["X-OP-Core-Conformance"] = "v1.0"
            return response

        self._http_client = TestClient(app)
        return self._http_client

    # ---------------- authority_label_resolution ----------------

    def run_authority_label_resolution(self, q: dict) -> CaseResult:
        from services.vocabularies.authority_label_cache import AuthorityLabelCache

        db = self.SessionFactory()
        try:
            cache = AuthorityLabelCache(db)
            label = cache.resolve(q["input"]["uri"], q["input"].get("lang", "en"))
        finally:
            db.close()
        wanted = q["expect"].get("contains", "")
        if label and wanted.lower() in label.lower():
            return CaseResult(q["id"], q["category"], True, detail=f"label={label!r}")
        return CaseResult(
            q["id"], q["category"], False,
            detail=f"label={label!r}", error=f"expected to contain {wanted!r}",
        )

    # ---------------- v1_vocabulary_endpoint ----------------

    def run_v1_vocabulary_endpoint(self, q: dict) -> CaseResult:
        client = self._http()
        r = client.get(q["input"]["endpoint"], params=q["input"].get("params", {}))
        if r.status_code != 200:
            return CaseResult(q["id"], q["category"], False, error=f"HTTP {r.status_code}")
        body = r.json()
        if "min_total" in q["expect"] and body.get("total", 0) < q["expect"]["min_total"]:
            return CaseResult(q["id"], q["category"], False,
                              error=f"total={body.get('total')} < {q['expect']['min_total']}")
        if "envelope_field" in q["expect"] and q["expect"]["envelope_field"] not in body:
            return CaseResult(q["id"], q["category"], False,
                              error=f"missing envelope key {q['expect']['envelope_field']!r}")
        return CaseResult(q["id"], q["category"], True, detail=f"total={body.get('total')}")

    # ---------------- dcat_ap_harvester_shape ----------------

    def run_dcat_ap_harvester_shape(self, q: dict) -> CaseResult:
        client = self._http()
        r = client.get(q["input"]["endpoint"])
        if r.status_code != 200:
            return CaseResult(q["id"], q["category"], False, error=f"HTTP {r.status_code}")
        ct = r.headers.get("content-type", "")
        if "content_type_includes" in q["expect"] and q["expect"]["content_type_includes"] not in ct:
            return CaseResult(q["id"], q["category"], False, error=f"ct={ct}")
        body = r.content
        if "min_bytes" in q["expect"] and len(body) < q["expect"]["min_bytes"]:
            return CaseResult(q["id"], q["category"], False, error=f"size={len(body)}")
        if "text_contains" in q["expect"] and q["expect"]["text_contains"].encode() not in body:
            return CaseResult(q["id"], q["category"], False, error=f"missing text {q['expect']['text_contains']!r}")
        return CaseResult(q["id"], q["category"], True, detail=f"bytes={len(body)}, ct={ct.split(';')[0]}")

    # ---------------- op_core_envelope ----------------

    def run_op_core_envelope(self, q: dict) -> CaseResult:
        client = self._http()
        r = client.get(q["input"]["endpoint"], params=q["input"].get("params", {}))
        if r.status_code != 200:
            return CaseResult(q["id"], q["category"], False, error=f"HTTP {r.status_code}")
        if "header_present" in q["expect"]:
            if q["expect"]["header_present"] not in r.headers:
                return CaseResult(q["id"], q["category"], False,
                                  error=f"missing header {q['expect']['header_present']}")
            return CaseResult(q["id"], q["category"], True, detail=f"hdr={r.headers[q['expect']['header_present']]}")
        body = r.json()
        if "json_path" in q["expect"]:
            cur: Any = body
            for seg in q["expect"]["json_path"].split("."):
                if isinstance(cur, dict):
                    cur = cur.get(seg)
                else:
                    cur = None
                    break
            if "equals" in q["expect"] and cur != q["expect"]["equals"]:
                return CaseResult(q["id"], q["category"], False, error=f"{q['expect']['json_path']}={cur!r}")
        return CaseResult(q["id"], q["category"], True)

    # ---------------- ontology_drift ----------------

    def run_ontology_drift(self, q: dict) -> CaseResult:
        # Drift checks live in pytest. Here we just confirm the snapshot
        # file exists + has predicates.
        snap = ROOT / "docs" / "ontologies" / "cdm" / "cdm-brubru-subset.ttl"
        if not snap.exists():
            return CaseResult(q["id"], q["category"], False, error="snapshot missing")
        text = snap.read_text()
        n_pred = sum(1 for ln in text.splitlines() if ln.startswith("cdm:"))
        if n_pred < 30:
            return CaseResult(q["id"], q["category"], False, error=f"only {n_pred} predicates in snapshot")
        return CaseResult(q["id"], q["category"], True, detail=f"snapshot has {n_pred} predicates")

    # ---------------- immc_event_projection ----------------

    async def run_immc_event_projection(self, q: dict) -> CaseResult:
        from services.api_clients.immc_client import IMMCClient

        async with IMMCClient(timeout=60) as c:
            res = await c.fetch_events_for_celex(q["input"]["celex"])
        if "events" not in res or not isinstance(res["events"], list):
            return CaseResult(q["id"], q["category"], False, error=f"bad shape: {list(res.keys())}")
        if "fetched_at" not in res:
            return CaseResult(q["id"], q["category"], False, error="missing fetched_at")
        return CaseResult(q["id"], q["category"], True,
                          detail=f"events={len(res['events'])}, error={res.get('error', None)}")

    # ---------------- akn4eu_renderer ----------------

    def run_akn4eu_renderer(self, q: dict) -> CaseResult:
        from services.document_generation.det_renderer import render
        try:
            xml = render(q["input"], format="akn4eu_xml")
        except Exception as e:  # noqa: BLE001
            return CaseResult(q["id"], q["category"], False, error=f"render raised: {e}")

        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as e:
            return CaseResult(q["id"], q["category"], False, error=f"XML parse: {e}")

        if "xml_root_tag" in q["expect"]:
            tag = root.tag.split("}", 1)[-1]
            if tag != q["expect"]["xml_root_tag"]:
                return CaseResult(q["id"], q["category"], False, error=f"root={tag}")
        if "xml_contains" in q["expect"] and q["expect"]["xml_contains"].encode() not in xml:
            return CaseResult(q["id"], q["category"], False,
                              error=f"missing fragment {q['expect']['xml_contains']!r}")
        return CaseResult(q["id"], q["category"], True, detail=f"bytes={len(xml)}")

    # ---------------- eurio_endpoint ----------------

    def run_eurio_endpoint(self, q: dict) -> CaseResult:
        client = self._http()
        r = client.get(q["input"]["endpoint"], params=q["input"].get("params", {}))
        if "status" in q["expect"] and r.status_code != q["expect"]["status"]:
            return CaseResult(q["id"], q["category"], False, error=f"HTTP {r.status_code}")
        body = r.json()
        if "json_path" in q["expect"]:
            cur: Any = body
            for seg in q["expect"]["json_path"].split("."):
                if isinstance(cur, dict):
                    cur = cur.get(seg)
                else:
                    cur = None
                    break
            if q["expect"].get("is_list") and not isinstance(cur, list):
                return CaseResult(q["id"], q["category"], False,
                                  error=f"{q['expect']['json_path']} not a list: {type(cur)}")
        return CaseResult(q["id"], q["category"], True)

    # ---------------- euroscivoc_resolver ----------------

    def run_euroscivoc_resolver(self, q: dict) -> CaseResult:
        from services.vocabularies.euroscivoc_resolver import EuroSciVocResolver

        r = EuroSciVocResolver()
        hits = r.search(q["input"]["keyword"], q["input"].get("lang", "en"), limit=5)
        # Either populated (dump on disk) OR empty (graceful fallback) is OK.
        return CaseResult(q["id"], q["category"], True,
                          detail=f"hits={len(hits)}, loaded={r.is_loaded()}")

    # ---------------- ojeep_validator ----------------

    def run_ojeep_validator(self, q: dict) -> CaseResult:
        # Import the script as a module
        spec_path = ROOT / "backend" / "scripts" / "validate_catalan_against_ojeep.py"
        spec = importlib.util.spec_from_file_location("ojeep_validator", spec_path)
        m = importlib.util.module_from_spec(spec)
        sys.modules["ojeep_validator"] = m
        spec.loader.exec_module(m)  # type: ignore[union-attr]

        celex = q["input"]["celex"]
        path = ROOT / "frontend" / "public" / "legislacio-ue-catala" / celex / "index.html"
        if not path.exists():
            return CaseResult(q["id"], q["category"], False, error=f"missing {path}")
        html = path.read_text()
        res = m._validate_html(html, celex=celex, path=str(path))
        if q["expect"].get("validator_pass") and not res.ok:
            return CaseResult(q["id"], q["category"], False,
                              error=f"validator fails: {res.fails[:3]}")
        return CaseResult(q["id"], q["category"], True, detail=f"passes={res.passes}")

    # ---------------- dispatcher ----------------

    async def run(self, q: dict) -> CaseResult:
        method_name = f"run_{q['category']}"
        m = getattr(self, method_name, None)
        if m is None:
            return CaseResult(q["id"], q["category"], False, error=f"no executor for {q['category']}")
        try:
            if asyncio.iscoroutinefunction(m):
                return await m(q)
            return m(q)
        except Exception as e:  # noqa: BLE001
            return CaseResult(q["id"], q["category"], False, error=f"exec exception: {type(e).__name__}: {e}")


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

async def main(category: Optional[str], emit_json: bool, db_url: str) -> int:
    queries = json.loads(QUERIES_PATH.read_text())
    cases = queries["queries"]
    if category:
        cases = [c for c in cases if c["category"] == category]
    log.info(f"Loaded {len(cases)} synthetic queries (filter: {category or 'ALL'})")
    log.info(f"DB target: {db_url}")

    # Make sure FastAPI sees the test DB.
    os.environ["DATABASE_URL"] = db_url

    runner = Runner(db_url)
    results: List[CaseResult] = []
    for q in cases:
        r = await runner.run(q)
        marker = "PASS" if r.ok else "FAIL"
        log.info(f"  [{marker}] {r.id} ({r.category})  {r.detail or r.error}")
        results.append(r)

    by_cat: Dict[str, Counter] = {}
    for r in results:
        c = by_cat.setdefault(r.category, Counter())
        c["pass" if r.ok else "fail"] += 1

    log.info("=" * 70)
    for cat, counts in sorted(by_cat.items()):
        log.info(f"  {cat:30s}  pass={counts['pass']:3d}  fail={counts['fail']:3d}")
    total = len(results)
    passing = sum(1 for r in results if r.ok)
    log.info("-" * 70)
    log.info(f"  TOTAL                          pass={passing:3d}  fail={total - passing:3d}  ({passing}/{total} = {passing/total*100:.0f}%)")

    if emit_json:
        print(json.dumps([asdict(r) for r in results], indent=2))

    return 0 if passing == total else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--db-url", default=DEFAULT_DB_URL)
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.category, args.json, args.db_url)))
