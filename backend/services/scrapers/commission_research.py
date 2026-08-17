"""
CORDIS — EU research projects under Horizon Europe — the database behind
/api/v2/commission/research-projects.

Source: the CORDIS Horizon Europe bulk dataset (EU Open Data Portal), a JSON zip
  https://cordis.europa.eu/data/cordis-HORIZONprojects-json.zip
containing project.json — every Horizon Europe (2021-2027) project with acronym,
title, objective, EC contribution, dates, topics, funding scheme and status.
~21k projects; the row IS the content (no per-row fetch, no LLM).
"""
from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean, norm_url, _iso_dt

_URL = "https://cordis.europa.eu/data/cordis-HORIZONprojects-json.zip"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_OBJ_CAP = 2000


def ingest_research_projects(*, fetch_bodies: bool = True, **_) -> list[Item]:
    try:
        raw = requests.get(_URL, headers={"User-Agent": _UA}, timeout=240).content
        z = zipfile.ZipFile(io.BytesIO(raw))
        # CORDIS restructured the bulk export (Aug 2026): one JSON file PER project,
        # named `project-rcn-NNNNNN_en.json` (flat project dict), instead of a single
        # `project.json` holding a list. Iterate the per-project members.
        members = [n for n in z.namelist()
                   if n.lower().endswith(".json") and "project-rcn-" in n.lower()]
    except (requests.RequestException, zipfile.BadZipFile, ValueError):
        return []
    projects = []
    for _name in members:
        try:
            obj = json.loads(z.read(_name).decode("utf-8", "replace"))
        except ValueError:
            continue
        if isinstance(obj, dict):
            projects.append(obj.get("project") if isinstance(obj.get("project"), dict) else obj)
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set[str] = set()
    for p in projects:
        pid = p.get("id") or p.get("rcn")
        if not pid or str(pid) in seen:
            continue
        seen.add(str(pid))
        acronym = clean(p.get("acronym"))
        title = clean(p.get("title")) or acronym or f"Project {pid}"
        objective = clean((p.get("objective") or "")[:_OBJ_CAP]) or None
        ec = p.get("ecMaxContribution")
        total = p.get("totalCost")
        start = p.get("startDate")
        doc_dt = _iso_dt(str(start)[:10]) if start else (
            _iso_dt(str(p.get("ecSignatureDate"))[:10]) if p.get("ecSignatureDate") else None)

        def money(v):
            try:
                return f"EUR {float(v):,.0f}" if v not in (None, "", "0", 0) else None
            except (TypeError, ValueError):
                return None

        url = norm_url(f"https://cordis.europa.eu/project/id/{pid}")
        lines = [
            f"Project: {title}",
            f"Acronym: {acronym}" if acronym else "",
            f"EC contribution: {money(ec)}" if money(ec) else "",
            f"Total cost: {money(total)}" if money(total) else "",
            f"Funding scheme: {p.get('fundingScheme')}" if p.get("fundingScheme") else "",
            f"Topic: {p.get('topics')}" if p.get("topics") else "",
            f"Call: {p.get('masterCall')}" if p.get("masterCall") else "",
            f"Status: {p.get('status')}" if p.get("status") else "",
            f"Start: {str(start)[:10]}" if start else "",
            f"End: {str(p.get('endDate'))[:10]}" if p.get("endDate") else "",
            f"Programme: {p.get('frameworkProgramme')}" if p.get("frameworkProgramme") else "",
            f"Grant DOI: {p.get('grantDoi')}" if p.get("grantDoi") else "",
            f"Keywords: {clean(p.get('keywords'))}" if p.get("keywords") else "",
            f"Objective: {objective}" if objective else "",
        ]
        lines = [l for l in lines if l]
        items.append(Item(
            body_code="commission", item_type="research_project",
            title=(f"{acronym} — {title}" if acronym and acronym.lower() not in title.lower() else title),
            public_url=url,
            summary=clean(" | ".join(x for x in [acronym or title, money(ec) or "",
                                                 str(p.get("status") or "")] if x)),
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
            document_date=doc_dt, creation_date=now, source_kind="cordis", guid=str(pid)))
    return items
