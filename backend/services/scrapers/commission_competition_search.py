"""
DG COMP / Europa Search case harvester - the database behind
/api/v2/commission/state-aid and /api/v2/commission/dma-cases.

The competition-cases and digital-markets-act-cases portals are the same Angular
app over the EU Search API (api.tech.ec.europa.eu/search-api, apiKey
CS_PROD_ODSE_PROD). That host throttles scripted `requests`, so we harvest the
SAME WAY THE APP DOES: from inside a real browser page (Playwright), calling the
search endpoint via page.evaluate fetch with the multipart query the app sends.

The query that returns one row per *case* (not per attachment) is:
  query (multipart blob):
    {"bool":{"must":[
       {"exists":{"field":"caseNumber"}},
       {"term":{"caseInstrument":"<SA|AT|M|InstrumentDMA>"}},
       {"term":{"metadataType":"METADATA_CASE"}}]}}
The engine hard-caps results at offset 10,000, so state aid (~60,873 cases) is
partitioned by member state (each <=10,269); the one member state above 10,000
(Germany) is covered by paging the partition ascending AND descending and taking
the union. Row IS the content.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from services.scrapers.economy_common import Item, clean

_SEARCH = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
_KEY = "CS_PROD_ODSE_PROD"
_ORIGIN = "https://digital-markets-act-cases.ec.europa.eu/search"
_CASE_URL = {
    "SA": "https://competition-cases.ec.europa.eu/cases/",
    "AT": "https://competition-cases.ec.europa.eu/cases/",
    "M": "https://competition-cases.ec.europa.eu/cases/",
    "InstrumentDMA": "https://digital-markets-act-cases.ec.europa.eu/cases/",
}
# State-aid member-state partition keys (Country<ISO3>); each partition <= 10,269,
# so all stay within the engine's 10,000-result window (Germany handled asc+desc).
_SA_MEMBER_STATES = [
    "CountryAUT", "CountryBEL", "CountryBGR", "CountryHRV", "CountryCYP", "CountryCZE",
    "CountryDNK", "CountryEST", "CountryFIN", "CountryFRA", "CountryDEU", "CountryGRC",
    "CountryHUN", "CountryIRL", "CountryITA", "CountryLVA", "CountryLTU", "CountryLUX",
    "CountryMLT", "CountryNLD", "CountryPOL", "CountryPRT", "CountryROM", "CountrySVK",
    "CountrySVN", "CountryESP", "CountrySWE", "CountryGBR",
]
_DISPLAY = ["metadataType", "metadataReference", "caseNumber", "caseInstrument", "caseType",
            "caseTitle", "caseOriginalTitle", "caseSectors", "caseInitiationDate", "caseDg",
            "caseAidCategory", "caseMemberState", "caseMeasureStartDate", "caseMeasureEndDate",
            "casePrimaryLaws", "caseCompanies", "caseCartel", "caseLastDecisionDate"]

_PAGE_JS = """
async ([instrument, msCode, order, pageNumber, pageSize, display]) => {
  const must = [{exists:{field:"caseNumber"}},
                {term:{caseInstrument:instrument}},
                {term:{metadataType:"METADATA_CASE"}}];
  if (msCode) must.push({term:{caseMemberState: msCode}});
  const fd = new FormData();
  fd.append('query', new Blob([JSON.stringify({bool:{must}})], {type:'application/json'}));
  fd.append('sort', new Blob([JSON.stringify([{field:"metadataReference", order:order}])], {type:'application/json'}));
  fd.append('displayFields', new Blob([JSON.stringify(display)], {type:'application/json'}));
  const url = 'https://api.tech.ec.europa.eu/search-api/prod/rest/search?text=*&pageNumber='
              + pageNumber + '&pageSize=' + pageSize + '&apiKey=' + 'CS_PROD_ODSE_PROD';
  const r = await fetch(url, {method:'POST', body:fd});
  const j = await r.json();
  const first = (m, k) => (m && m[k] && m[k].length ? m[k][0] : null);
  return {
    total: j.totalResults,
    results: (j.results || []).map(x => {
      const m = x.metadata || {};
      return {
        caseNumber: first(m, "caseNumber"),
        caseTitle: first(m, "caseTitle") || first(m, "caseOriginalTitle"),
        caseType: first(m, "caseType"),
        caseDg: first(m, "caseDg"),
        caseMemberState: first(m, "caseMemberState"),
        caseSectors: (m.caseSectors || []).join("; "),
        caseAidCategory: first(m, "caseAidCategory"),
        caseCompanies: (m.caseCompanies || []).join("; "),
        caseLastDecisionDate: first(m, "caseLastDecisionDate"),
        caseInitiationDate: first(m, "caseInitiationDate"),
      };
    })
  };
}
"""


async def _harvest(instrument: str, partitions: list[str | None]) -> dict:
    from playwright.async_api import async_playwright
    rows: dict[str, dict] = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"))
        page = await ctx.new_page()
        await page.goto(_ORIGIN, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(1500)
        size = 100
        for ms in partitions:
            for order in ("ASC", "DESC"):
                total = None
                for pageno in range(1, 101):  # engine caps at offset 10,000 (100 pages)
                    for attempt in range(3):
                        try:
                            res = await page.evaluate(_PAGE_JS, [instrument, ms, order, pageno, size, _DISPLAY])
                            break
                        except Exception:
                            if attempt == 2:
                                res = {"total": 0, "results": []}
                            await page.wait_for_timeout(1500)
                    total = res.get("total") or 0
                    batch = res.get("results") or []
                    for r in batch:
                        cn = r.get("caseNumber")
                        if cn:
                            rows[cn] = r
                    if len(batch) < size:
                        break
                # Only page DESC when the partition exceeds the 10,000 window.
                if (total or 0) <= 10000:
                    break
        await b.close()
    return rows


def _to_items(rows: dict, instrument: str, item_type: str) -> list[Item]:
    now = datetime.now(timezone.utc)
    base = _CASE_URL.get(instrument, "https://competition-cases.ec.europa.eu/cases/")
    items: list[Item] = []
    for cn, r in rows.items():
        title = clean(f"{cn} - {r.get('caseTitle')}") if r.get("caseTitle") else cn
        doc_dt = None
        ds = r.get("caseLastDecisionDate") or r.get("caseInitiationDate")
        if ds:
            try:
                doc_dt = datetime.fromisoformat(ds.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                doc_dt = None
        lines = [
            f"Case number: {cn}",
            f"Title: {clean(r.get('caseTitle'))}" if r.get("caseTitle") else "",
            f"Case type: {r.get('caseType')}" if r.get("caseType") else "",
            f"Member State: {r.get('caseMemberState')}" if r.get("caseMemberState") else "",
            f"Lead DG: {r.get('caseDg')}" if r.get("caseDg") else "",
            f"Sectors: {clean(r.get('caseSectors'))}" if r.get("caseSectors") else "",
            f"Aid category: {r.get('caseAidCategory')}" if r.get("caseAidCategory") else "",
            f"Companies: {clean(r.get('caseCompanies'))}" if r.get("caseCompanies") else "",
            f"Last decision: {(r.get('caseLastDecisionDate') or '')[:10]}" if r.get("caseLastDecisionDate") else "",
        ]
        lines = [l for l in lines if l]
        items.append(Item(
            body_code="commission", item_type=item_type, title=title[:120],
            public_url=base + cn,
            summary=clean(" | ".join(x for x in [cn, r.get("caseType"),
                                                 r.get("caseMemberState"), r.get("caseSectors", "")[:50]] if x)),
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
            document_date=doc_dt, creation_date=now, source_kind="odse", guid=cn))
    return items


def ingest_state_aid(*, fetch_bodies: bool = True, **_) -> list[Item]:
    rows = asyncio.run(_harvest("SA", _SA_MEMBER_STATES))
    return _to_items(rows, "SA", "state_aid_case")


def ingest_dma_cases(*, fetch_bodies: bool = True, **_) -> list[Item]:
    rows = asyncio.run(_harvest("InstrumentDMA", [None]))
    return _to_items(rows, "InstrumentDMA", "dma_case")
