"""European Parliament eMeeting client + normaliser.

eMeeting (emeeting.europarl.europa.eu) is a SPA over an OPEN JSON API — NO WAF on
the API, NO WAF on the document PDFs (www.europarl.europa.eu/meetdocs/...). So
this is a pure-JSON integration (plain httpx), not a scrape.

Flow:
    GET /emeeting/plmrep/organs/committees?language=EN          -> 26 committees
    GET /emeeting/plmrep/agenda/agendaArchive?language=EN&organ={CODE}
                                                                -> timeline of OJs
    GET /emeeting/plmrep/OJ/oj?language=en&reference={ojRef}&securedContext=false
                                                                -> agenda + documents

Each committee OJ (agenda) -> one ``ep_emeeting_agendas`` row (migration 110). The
full item/document tree is normalised into ``items``; procedure refs + rapporteurs
are denormalised for filtering and MEUB anchor linking. Document taxonomy is the
built-in ``geproCode`` (OJ=Agenda, PR=Draft report, AM=Amendment, RR=report,
AD=opinion, DV=Miscellaneous incl. voting lists / compromise amendments).
"""

from __future__ import annotations

import html as _html
import logging
import re
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)

BASE = "https://emeeting.europarl.europa.eu/emeeting/plmrep"
SPA_TIMELINE = "https://emeeting.europarl.europa.eu/emeeting/committee/en/timeline"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BrubruBot/1.0)", "Accept": "application/json"}

# Structural (non-document) item type codes — not substantive agenda items.
_STRUCTURAL = {"SITT", "HEAD", "SEPA", "CMPR", "DTMT"}
_DDMMYYYY = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
_GROUP_RE = re.compile(r"\(([^)]+)\)\s*$")
# Clean OEIL procedure ref, e.g. 2026/2013(INI), 2025/0422(COD), 2025/0900(APP).
_OEIL_RE = re.compile(r"\b\d{4}/\d{3,4}\([A-Z]{2,4}\)")


def _clean_procedure_ref(raw: str) -> Optional[str]:
    """eMeeting packs OEIL ref + adopted-text + Council doc into one tab-separated
    string. Return the clean OEIL ref (the MEUB anchor); fall back to first token."""
    if not raw:
        return None
    m = _OEIL_RE.search(raw)
    if m:
        return m.group(0)
    first = raw.replace("\t", " ").split()[0] if raw.strip() else None
    return first or None


def _client(timeout: int = 30):
    import httpx
    return httpx.Client(timeout=timeout, headers=_HEADERS, follow_redirects=True)


def _get_json(c, path: str, params: dict):
    r = c.get(f"{BASE}/{path}", params=params)
    if r.status_code != 200 or "json" not in r.headers.get("content-type", "").lower():
        return None
    try:
        return r.json()
    except Exception:
        return None


def list_committees(c) -> list:
    """[{uid, code, name, fullName, type}] — the 26 EP committees."""
    return _get_json(c, "organs/committees", {"language": "EN"}) or []


def agenda_archive(c, organ: str) -> list:
    """Flattened, newest-first list of OJ stubs for a committee."""
    arch = _get_json(c, "agenda/agendaArchive", {"language": "EN", "organ": organ}) or []
    ojs = []
    for y in arch:
        for m in y.get("months", []):
            for oj in m.get("ojs", []):
                ojs.append(oj)
    return ojs


def get_oj(c, reference: str) -> Optional[dict]:
    """Full agenda + documents for an ojReference (e.g. 'AFCO(2026)0505_1')."""
    return _get_json(c, "OJ/oj", {"language": "en", "reference": reference, "securedContext": "false"})


# --------------------------------------------------------------------------- #
# Normalisation                                                               #
# --------------------------------------------------------------------------- #

def _parse_date(s: str) -> Optional[date]:
    m = _DDMMYYYY.match((s or "").strip())
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _en_pdf(document_links) -> tuple:
    """Return (en_or_first_url, [lang_codes]) from a documentLinks list."""
    for link in document_links or []:
        langs = link.get("languages") or []
        if not langs:
            continue
        codes = [l.get("code") for l in langs if l.get("code")]
        en = next((l.get("url") for l in langs if (l.get("code") or "").upper() == "EN"), None)
        return en or langs[0].get("url"), codes
    return None, []


def _parse_actor(actor: dict) -> Optional[dict]:
    """{'name': 'Rapporteur:\\tLoránt Vincze (PPE)', 'codictPersonId': 98582, ...}."""
    raw = (actor.get("name") or "").replace("\t", " ").strip()
    if not raw:
        return None
    role, _, person = raw.partition(":")
    person = person.strip() or raw
    gm = _GROUP_RE.search(person)
    group = gm.group(1) if gm else None
    name = _GROUP_RE.sub("", person).strip()
    return {
        "role": role.strip().rstrip(":") or "Rapporteur",
        "name": name,
        "group": group,
        "mep_id": actor.get("codictPersonId"),
        "profile_url": actor.get("profileUrl"),
    }


def _normalise_item(it: dict) -> dict:
    proc = it.get("procedure") or {}
    proc_raw = (proc.get("reference") or "").strip() or None
    proc_ref = _clean_procedure_ref(proc_raw)
    sets = []
    for s in it.get("documentSets") or []:
        rapporteurs = [a for a in (_parse_actor(x) for x in (s.get("actors") or [])) if a]
        docs = []
        for d in s.get("documents") or []:
            url, codes = _en_pdf(d.get("documentLinks"))
            docs.append({
                "gepro_code": d.get("geproCode"),
                "description": d.get("geproCodeDescription"),
                "reference": d.get("reference"),
                "title": (d.get("title") or "").strip() or None,
                "pdf_url": url,
                "languages": codes,
            })
        sets.append({"type": s.get("type"), "rapporteurs": rapporteurs, "documents": docs})
    return {
        "number": it.get("number"),
        "type": it.get("type"),
        "title": (it.get("title") or "").strip(),
        "dossier_reference": it.get("dossierReference"),
        "procedure_ref": proc_ref,
        "procedure_ref_raw": proc_raw,
        "procedure_type": proc.get("subTypeDescription"),
        "document_sets": sets,
    }


def _compose_body(committee_name, code, meeting_date, items, agenda_pdf_url) -> tuple:
    date_str = meeting_date.isoformat() if meeting_date else "n/d"
    head = f"{committee_name or code} — committee meeting agenda, {date_str}"
    txt = [head]
    parts = [f"<h2>{_html.escape(head)}</h2>"]
    substantive = [it for it in items if not it.get("type") and it.get("title")]
    for it in substantive:
        line = f"\nItem {it['number']}: {it['title']}" if it.get("number") else f"\n{it['title']}"
        txt.append(line)
        parts.append(f"<h3>{_html.escape(('Item %s: ' % it['number']) if it.get('number') else '')}{_html.escape(it['title'])}</h3>")
        meta = []
        if it.get("procedure_ref"):
            meta.append(f"Procedure: {it['procedure_ref']}" + (f" ({it['procedure_type']})" if it.get("procedure_type") else ""))
        raps = [f"{r['name']} ({r['group']})" if r.get("group") else r["name"]
                for s in it["document_sets"] for r in s["rapporteurs"]]
        if raps:
            meta.append("Rapporteur(s): " + ", ".join(dict.fromkeys(raps)))
        for line2 in meta:
            txt.append("  " + line2)
        if meta:
            parts.append("<ul>" + "".join(f"<li>{_html.escape(x)}</li>" for x in meta) + "</ul>")
        docs = [d for s in it["document_sets"] for d in s["documents"]]
        if docs:
            txt.append("  Documents:")
            doc_lis = []
            for d in docs:
                label = f"{d['description'] or d['gepro_code']} {d['reference'] or ''}".strip()
                txt.append(f"    - {label}" + (f" — {d['pdf_url']}" if d.get("pdf_url") else ""))
                if d.get("pdf_url"):
                    doc_lis.append(f'<li>{_html.escape(label)}: <a href="{_html.escape(d["pdf_url"])}">PDF</a></li>')
                else:
                    doc_lis.append(f"<li>{_html.escape(label)}</li>")
            parts.append("<ul>" + "".join(doc_lis) + "</ul>")
    if agenda_pdf_url:
        txt.append(f"\nFull agenda (PDF): {agenda_pdf_url}")
        parts.append(f'<p><a href="{_html.escape(agenda_pdf_url)}">Full agenda (PDF)</a></p>')
    return "\n".join(txt), "<article>" + "".join(parts) + "</article>"


def normalise_oj(stub: dict, raw: dict, committee_code: str, committee_name: Optional[str]) -> dict:
    """Turn an agendaArchive stub + OJ/oj detail into an ep_emeeting_agendas row dict."""
    items = [_normalise_item(it) for it in (raw.get("items") or [])]
    agenda_pdf_url, _ = _en_pdf((raw.get("ojDocument") or {}).get("documentLinks"))
    meeting_date = _parse_date(stub.get("date"))

    procedure_refs = sorted({it["procedure_ref"] for it in items if it.get("procedure_ref")})
    rapporteurs = []
    for it in items:
        for s in it["document_sets"]:
            for r in s["rapporteurs"]:
                disp = f"{r['name']} ({r['group']})" if r.get("group") else r["name"]
                if disp not in rapporteurs:
                    rapporteurs.append(disp)
    doc_count = sum(len(s["documents"]) for it in items for s in it["document_sets"])

    body_txt, body_html = _compose_body(committee_name, committee_code, meeting_date, items, agenda_pdf_url)
    oj_reference = stub.get("ojReference")
    title = f"{committee_name or committee_code}: committee meeting agenda, {meeting_date.isoformat() if meeting_date else oj_reference}"

    return {
        "oj_reference": oj_reference,
        "committee_code": committee_code,
        "committee_name": committee_name,
        "meeting_date": meeting_date,
        "meeting_reference": raw.get("meetingReference"),
        "title": title,
        "public_url": agenda_pdf_url or SPA_TIMELINE,
        "body_txt": body_txt,
        "body_html": body_html,
        "agenda_pdf_url": agenda_pdf_url,
        "items": items,
        "procedure_refs": procedure_refs,
        "rapporteurs": rapporteurs,
        "document_count": doc_count,
        "event_reference": stub.get("eventReference"),
        "source_url": f"{BASE}/OJ/oj?reference={oj_reference}",
    }


def fetch_agendas(per_committee: int = 6, committees: Optional[list] = None) -> list:
    """Fetch + normalise the most recent `per_committee` agendas for each committee."""
    out = []
    with _client() as c:
        coms = list_committees(c)
        if committees:
            want = {x.upper() for x in committees}
            coms = [x for x in coms if x.get("code") in want]
        name_by_code = {x.get("code"): x.get("name") for x in coms}
        for com in coms:
            code = com.get("code")
            try:
                stubs = agenda_archive(c, code)[:per_committee]
            except Exception as exc:
                logger.warning("[emeeting] %s archive error: %s", code, exc)
                continue
            for stub in stubs:
                ref = stub.get("ojReference")
                if not ref:
                    continue
                raw = get_oj(c, ref)
                if not raw:
                    continue
                # An OJ's timeline can include another committee's joint OJ; tag by
                # the OJ reference prefix so the row is filed under the right body.
                prefix = re.match(r"^([A-Z]+)\(", ref)
                row_code = prefix.group(1) if prefix else code
                out.append(normalise_oj(stub, raw, row_code, name_by_code.get(row_code, com.get("name"))))
            logger.info("[emeeting] %s -> %d agendas", code, len(stubs))
    return out
