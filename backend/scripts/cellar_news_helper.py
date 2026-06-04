"""Cellar SPARQL helpers for the /news routine.

Three /news-facing capabilities on top of
`services.api_clients.cellar_sparql_client.CellarSPARQLClient` — all read-only,
no auth, no WAF (the Publications Office SPARQL endpoint, not eur-lex HTML which
returns 202 + empty body to non-JS clients):

  --oj-today [--days N | --hours N] [--sectors 3,5] [--limit N]
      P1: EU acts dated in the recent window ("Official Journal today"), straight
      from Cellar SPARQL. Replaces the fragile eur-lex.europa.eu/oj HTML check in
      /news Step 0. Default sectors = legislation + proposals (3,5).

  --xref CELEX
      P3 / P4: resolve a CELEX to its ELI permalink, title, in-force status,
      EuroVoc concepts and related acts (the cross-reference graph). The ELI is
      the stable link to emit in the brief (it dereferences to the consolidated
      version and survives the 1 Oct 2023 act-by-act OJ split).

  --plain CELEX
      P5: the act's official title — a plain-language alias for hero text, so the
      brief can avoid raw institutional codes (feedback_daily_brief_no_institutional_codes).

Output is JSON on stdout. Used by news/SKILL.md Steps 0, 1f and 2.

Examples:
    python3.12 scripts/cellar_news_helper.py --oj-today --days 2 --sectors 3
    python3.12 scripts/cellar_news_helper.py --xref 32016R0679
    python3.12 scripts/cellar_news_helper.py --plain 32000L0060
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, timedelta
from pathlib import Path

# backend/ on path so `services...` imports resolve when run as a script.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.api_clients.cellar_sparql_client import CellarSPARQLClient  # noqa: E402


async def oj_today(days: int | None, hours: int | None, sectors: str | None, limit: int) -> dict:
    date_to = date.today()
    span_days = days if days else max(1, ((hours or 24) + 23) // 24)
    date_from = date_to - timedelta(days=span_days)
    sec = [s.strip() for s in sectors.split(",")] if sectors else None
    async with CellarSPARQLClient() as client:
        rows = await client.discover_by_date_range(
            date_from, date_to, sectors=sec, limit=limit
        )
    return {
        "query": "oj-today",
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "sectors": sec or "ALL",
        "count": len(rows),
        "acts": rows,
    }


async def xref(celex: str) -> dict:
    async with CellarSPARQLClient() as client:
        meta = await client.get_celex_metadata(celex)
        eli = (meta or {}).get("eli") or await client.get_eli(celex)
        concepts = await client.get_eurovoc_concepts(celex)
        related = await client.get_related_acts(celex)
    return {
        "query": "xref",
        "celex": celex,
        "eli": eli,
        "title": (meta or {}).get("title"),
        "in_force": (meta or {}).get("in_force"),
        "date": (meta or {}).get("date"),
        "eurovoc_concepts": concepts,
        "related_acts": related,
        "found": meta is not None or eli is not None,
    }


async def plain(celex: str) -> dict:
    async with CellarSPARQLClient() as client:
        meta = await client.get_celex_metadata(celex)
    return {"query": "plain", "celex": celex, "title": (meta or {}).get("title")}


def main() -> int:
    p = argparse.ArgumentParser(description="Cellar SPARQL helpers for /news (P1/P3/P4/P5).")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--oj-today", action="store_true", help="Recent EU acts (P1)")
    g.add_argument("--xref", metavar="CELEX", help="CELEX -> ELI + EuroVoc + related (P3/P4)")
    g.add_argument("--plain", metavar="CELEX", help="CELEX -> plain-language title (P5)")
    p.add_argument("--days", type=int, default=None, help="oj-today: look back N days")
    p.add_argument("--hours", type=int, default=None, help="oj-today: look back N hours (rounded up to days)")
    p.add_argument("--sectors", default="3,5", help="oj-today: comma CELEX sectors (default 3,5)")
    p.add_argument("--limit", type=int, default=200, help="oj-today: max results")
    args = p.parse_args()

    if args.oj_today:
        result = asyncio.run(oj_today(args.days, args.hours, args.sectors, args.limit))
    elif args.xref:
        result = asyncio.run(xref(args.xref.strip()))
    else:
        result = asyncio.run(plain(args.plain.strip()))

    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    # Exit 1 if an xref/plain lookup found nothing — lets /news flag dead refs.
    if args.xref and not result.get("found"):
        return 1
    if args.plain and not result.get("title"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
