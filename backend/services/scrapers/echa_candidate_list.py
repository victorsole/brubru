"""European Chemicals Agency database — REACH Candidate List of Substances of
Very High Concern (SVHC). Backs /api/v2/echa/candidate-list.

The Candidate List is the set of substances of very high concern that may be
placed on the Authorisation List under REACH. ECHA publishes it on a Liferay
portlet behind a legal-notice gate; the table is paginated 50 rows per page.
We accept the disclaimer in a real browser, then walk the pages, parsing one row
per substance: name, EC and CAS numbers, date of inclusion, the reason for
inclusion (SVHC property) and the substance-information link. Row IS the content.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

from services.scrapers.economy_common import Item, clean

_URL = "https://echa.europa.eu/candidate-list-table"
_SUBSTANCE = "https://echa.europa.eu/substance-information/-/substanceinfo/{sid}"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")
_ROW = re.compile(
    r'id="_disslists_WAR_disslistsportlet_dislistSearchResultVOsSearchContainer_\d+"')


def _txt(x: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x)).strip()


def _parse_date(d: str) -> datetime | None:
    d = (d or "").strip()
    for fmt in ("%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(d, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse_rows(html: str, now: datetime) -> list[Item]:
    items: list[Item] = []
    for seg in _ROW.split(html)[1:]:
        seg = seg.split("</tr>")[0]
        cells = [_txt(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", seg, re.S)]
        if not cells or not cells[0] or cells[0] == "-":
            continue
        name = cells[0]
        ec = cells[1] if len(cells) > 1 else ""
        cas = cells[2] if len(cells) > 2 else ""
        date_s = cells[3] if len(cells) > 3 else ""
        reason = cells[4] if len(cells) > 4 else ""
        decision = cells[5] if len(cells) > 5 else ""
        href = re.search(r"substanceinfo/([0-9.]+)", seg)
        sid = href.group(1) if href else None
        url = _SUBSTANCE.format(sid=sid) if sid else f"{_URL}#{ec or name}"
        ec_clean = ec if ec and ec != "-" else ""
        cas_clean = cas if cas and cas != "-" else ""
        lines = [f"SVHC: {name}",
                 f"EC number: {ec_clean}" if ec_clean else "",
                 f"CAS number: {cas_clean}" if cas_clean else "",
                 f"Date of inclusion: {date_s}" if date_s and date_s != "-" else "",
                 f"Reason for inclusion: {reason}" if reason and reason != "-" else "",
                 f"Decision: {decision}" if decision and decision != "-" else ""]
        lines = [l for l in lines if l]
        items.append(Item(
            body_code="echa", item_type="svhc_substance",
            title=clean(name)[:120], public_url=url,
            summary=clean(" | ".join(x for x in [ec_clean, cas_clean, reason] if x)) or clean(name)[:120],
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
            document_date=_parse_date(date_s), creation_date=now,
            source_kind="echa_candidate_list", guid=sid or (ec_clean or name)))
    return items


async def _scrape(max_pages: int = 12) -> list[Item]:
    from playwright.async_api import async_playwright
    now = datetime.now(timezone.utc)
    out: dict[str, Item] = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        await page.goto(_URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(2000)
        for sel in ("text=I have read", "text=I accept", "text=Accept"):
            try:
                await page.click(sel, timeout=4000)
                break
            except Exception:
                pass
        await page.wait_for_timeout(2500)
        for _ in range(max_pages):
            rows = _parse_rows(await page.content(), now)
            new = 0
            for it in rows:
                if it.guid not in out:
                    out[it.guid] = it
                    new += 1
            # advance to next page; stop when no next or no new rows
            advanced = False
            for sel in ('a:has-text("Next")', 'a[rel="next"]', 'a[href*="_cur="]:has-text("Next")'):
                try:
                    el = page.locator(sel).first
                    if await el.is_visible():
                        await el.click(timeout=4000)
                        await page.wait_for_timeout(2500)
                        advanced = True
                        break
                except Exception:
                    pass
            if not advanced or new == 0:
                break
        await b.close()
    return list(out.values())


def ingest_echa_candidate_list(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return asyncio.run(_scrape())
