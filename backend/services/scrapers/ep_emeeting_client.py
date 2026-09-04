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


# Derived document kind — normalises the geproCode taxonomy into the categories
# people actually ask for. PR/AM/RR/AD/OJ/PV are clean codes; DV ("Miscellaneous")
# is the catch-all where voting lists + compromise amendments live, told apart by
# the reference/filename (the DV `reference` IS the descriptive filename).
# Code fallback for opaque descriptions (verified against /plmrep/document-types
# + live geproCodeDescription values).
_BASE_KIND = {
    "OJ": "agenda", "PR": "draft_report", "AM": "amendment", "VL": "voting_list",
    "PV": "minutes", "AD": "opinion", "PA": "draft_opinion", "RR": "report",
    "DT": "working_document", "NP": "reasoned_opinion", "TA_DEF": "adopted_text",
    "TA_PROV": "adopted_text", "TA_A8": "adopted_text",
    "COM": "commission_document", "SEC": "commission_document",
    "SWD": "commission_document", "JOIN": "commission_document",
    # CLS = a COUNCIL document transmitted to the committee, not (as the bare
    # code suggests) a legal-service opinion. Verified 4 Sep 2026 by reading the
    # rows: every PDF sits under AUTRES_INSTITUTIONS/CONS/CLS/ and the reference
    # is a Council document number (10643/2025, 06435/2026), typically the
    # Council's own text of an agreement or decision on an NLE consent file.
    # 198 rows across 72 procedures were landing in `miscellaneous` and had no
    # MEUB surface at all.
    "CLS": "council_document",
}
_VL_RE = re.compile(r"voting[ _]?list|\bvl[ _]|\bfinal vl\b|_voting_list\b", re.I)
_CA_RE = re.compile(r"compromise amendment|\bca[s]?\b|_ca[s]?[_ .]|\bca[s]?_", re.I)


def doc_kind(gepro_code: Optional[str], reference: Optional[str],
             title: Optional[str], description: Optional[str] = None) -> str:
    """Normalised document kind for filtering. Classifies from the authoritative
    geproCodeDescription first, then DV-filename heuristic, then code fallback."""
    code = (gepro_code or "").upper()
    # DV ("Miscellaneous") = catch-all; split voting lists vs compromise amendments
    # by the document's own filename (the DV reference IS the filename).
    if code == "DV":
        blob = f"{reference or ''} {title or ''}"
        if _VL_RE.search(blob):
            return "voting_list"
        if _CA_RE.search(blob):
            return "compromise_amendments"
        return "miscellaneous"
    desc = (description or "").lower()
    if desc:
        if "voting list" in desc:
            return "voting_list"
        if "compromise" in desc:
            return "compromise_amendments"
        if "draft report" in desc or "draft recommendation" in desc:
            return "draft_report"
        if "draft opinion" in desc:
            return "draft_opinion"
        if "reasoned opinion" in desc:
            return "reasoned_opinion"
        if "opinion" in desc:
            return "opinion"
        if "minutes" in desc:
            return "minutes"
        if "agenda" in desc:
            return "agenda"
        if "amendment" in desc:
            return "amendment"
        if "working document" in desc:
            return "working_document"
        if "draft motion for a resolution" in desc:
            return "draft_resolution"
        if "report" in desc or "recommendation" in desc:
            return "report"
        if "notice to members" in desc:
            return "notice_to_members"
        if "text agreed" in desc or "interinstitutional negotiation" in desc:
            return "agreed_text"
        if "letter confirming agreement" in desc or "letter of agreement" in desc:
            return "letter_of_agreement"
        if "presentation" in desc:
            return "presentation"
        if "oral question" in desc:
            return "oral_question"
        if "written question" in desc:
            return "written_question"
    if code in _BASE_KIND:
        return _BASE_KIND[code]
    # Fall-through, fixed 31 Aug 2026. This used to `return code.lower()`, which
    # emitted the RAW EP code as if it were a classified kind: 'cls', 'cr', 'a7',
    # 'com_2', 'stud', 're', 'aa', 'swd2', 'ab', 'qe' -- about 353 rows. Those
    # values are in no consumer's vocabulary, so such a document was invisible to
    # every surface and to the `doc_kind` filter on /api/v1/emeeting-documents:
    # a passthrough looks like a classification and behaves like a hole.
    # Nothing is lost by normalising, because the raw code is ALREADY persisted
    # in its own `gepro_code` column -- the passthrough was pure redundancy.
    # 'miscellaneous' is the documented catch-all (it is what DV already returns).
    return "miscellaneous"


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


def _all_pdfs(document_links) -> tuple:
    """Return ({LANG: url} for every language, [lang_codes]) across all links."""
    urls = {}
    for link in document_links or []:
        for l in link.get("languages") or []:
            code = (l.get("code") or "").upper()
            if code and l.get("url") and code not in urls:
                urls[code] = l.get("url")
    return urls, list(urls.keys())


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
            all_urls, all_codes = _all_pdfs(d.get("documentLinks"))
            docs.append({
                "gepro_code": d.get("geproCode"),
                "description": d.get("geproCodeDescription"),
                "reference": d.get("reference"),
                "visual_reference": d.get("visualReference"),
                "title": (d.get("title") or "").strip() or None,
                "pdf_url": url,
                "pdf_urls": all_urls,
                "languages": all_codes or codes,
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


def _compose_doc_body(doc: dict) -> tuple:
    label = f"{doc['gepro_description'] or doc['gepro_code']}"
    lines = [f"{label}: {doc['title'] or doc['reference'] or ''}".strip()]
    meta = [
        ("Type", f"{doc['gepro_description']} ({doc['gepro_code']})" if doc.get("gepro_description") else doc.get("gepro_code")),
        ("Reference", doc.get("reference")),
        ("Committee", f"{doc.get('committee_name') or ''} ({doc.get('committee_code')})".strip()),
        ("Meeting date", doc["meeting_date"].isoformat() if doc.get("meeting_date") else None),
        ("Procedure", doc.get("procedure_ref")),
        ("Rapporteur(s)", ", ".join(doc.get("rapporteurs") or []) or None),
        ("Agenda item", doc.get("item_title")),
    ]
    for k, v in meta:
        if v:
            lines.append(f"{k}: {v}")
    if doc.get("pdf_url"):
        lines.append(f"PDF (EN): {doc['pdf_url']}")
    if doc.get("languages"):
        lines.append(f"Available languages: {', '.join(doc['languages'])}")
    txt = "\n".join(lines)
    li = "".join(f"<li><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</li>" for k, v in meta if v)
    pdf_lis = "".join(
        f'<li>{_html.escape(lang)}: <a href="{_html.escape(url)}">PDF</a></li>'
        for lang, url in (doc.get("pdf_urls") or {}).items())
    html = (f"<article><h2>{_html.escape(lines[0])}</h2><ul>{li}</ul>"
            + (f"<h3>Document PDFs ({len(doc.get('pdf_urls') or {})} languages)</h3><ul>{pdf_lis}</ul>" if pdf_lis else "")
            + "</article>")
    return txt, html


def documents_from_agenda(agenda: dict) -> list:
    """Flatten a normalised agenda into one row per attached document (all
    languages). Each carries the agenda's linking anchors."""
    out = []
    seen = set()
    oj = agenda.get("oj_reference")
    base = {
        "committee_code": agenda.get("committee_code"),
        "committee_name": agenda.get("committee_name"),
        "meeting_date": agenda.get("meeting_date"),
        "oj_reference": oj,
    }
    for it in agenda.get("items") or []:
        item_title = it.get("title")
        dossier = it.get("dossier_reference")
        proc = it.get("procedure_ref")
        for s in it.get("document_sets") or []:
            set_type = s.get("type")
            raps = [f"{r['name']} ({r['group']})" if r.get("group") else r["name"]
                    for r in s.get("rapporteurs") or []]
            for d in s.get("documents") or []:
                vref = d.get("visual_reference") or f"{d.get('gepro_code')}:{d.get('reference')}"
                key = f"{oj}::{vref}"
                if key in seen:
                    continue
                seen.add(key)
                row = dict(base)
                row.update({
                    "document_key": key,
                    "gepro_code": d.get("gepro_code"),
                    "gepro_description": d.get("description"),
                    "doc_kind": doc_kind(d.get("gepro_code"), d.get("reference"), d.get("title") or item_title, d.get("description")),
                    "reference": d.get("reference"),
                    "visual_reference": d.get("visual_reference"),
                    "title": d.get("title") or item_title,
                    "dossier_reference": dossier,
                    "procedure_ref": proc,
                    "item_title": item_title,
                    "document_set_type": set_type,
                    "rapporteurs": raps,
                    "pdf_url": d.get("pdf_url"),
                    "pdf_urls": d.get("pdf_urls") or {},
                    "languages": d.get("languages") or [],
                    "source_url": f"{BASE}/OJ/oj?reference={oj}",
                })
                row["body_txt"], row["body_html"] = _compose_doc_body(row)
                out.append(row)
    return out


def committee_index(committees: Optional[list] = None) -> list:
    """Return [(code, name)] for the requested committees (all 26 by default)."""
    with _client() as c:
        coms = list_committees(c)
    if committees:
        want = {x.upper() for x in committees}
        coms = [x for x in coms if x.get("code") in want]
    return [(x.get("code"), x.get("name")) for x in coms]


def fetch_committee(code: str, name: Optional[str], per_committee: int,
                    name_by_code: Optional[dict] = None) -> list:
    """Fetch + normalise the most recent `per_committee` agendas for ONE committee.
    Lets the caller write/commit per committee so a long run streams to the DB."""
    out = []
    name_by_code = name_by_code or {}
    with _client() as c:
        try:
            stubs = agenda_archive(c, code)[:per_committee]
        except Exception as exc:
            logger.warning("[emeeting] %s archive error: %s", code, exc)
            return out
        for stub in stubs:
            ref = stub.get("ojReference")
            if not ref:
                continue
            raw = get_oj(c, ref)
            if not raw:
                continue
            import re as _re
            prefix = _re.match(r"^([A-Z]+)\(", ref)
            row_code = prefix.group(1) if prefix else code
            out.append(normalise_oj(stub, raw, row_code, name_by_code.get(row_code, name)))
    return out


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
