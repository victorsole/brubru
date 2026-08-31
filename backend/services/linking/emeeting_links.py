"""
eMeeting → MEUB linkage helper (shared, surface-not-ingest).

ONE query that every MEUB surface reuses to pull the EP committee-meeting
documents for a set of OEIL procedures, optionally filtered by doc_kind. No
duplication: the documents live only in `ep_emeeting_documents`; each surface
just SELECTs the kinds it owns (per the routing in
memory/reference_ep_emeeting.md):
  - File detail (My Tracked Files): opinion/draft_opinion (In committee),
    adopted_text, commission_document, notice_to_members/miscellaneous (catch-all)
  - Position Analysis: draft_report, amendment, compromise_amendments,
    opinion, draft_opinion, reasoned_opinion
  - Amendments: draft_report, amendment, compromise_amendments
  - Votes: voting_list   |   Transcripts: minutes
"""

import re
from typing import Dict, Iterable, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

# CELEX descriptor-letter pairs -> Commission document type. Proposals (PC),
# communications (DC), staff working docs (SC), joint docs (JC), etc.
_CELEX_TYPE = {"PC": "COM", "DC": "COM", "SC": "SWD", "JC": "JOIN",
               "FC": "COM", "XC": "COM"}


def canon_commission_ref(ref: Optional[str]) -> Optional[str]:
    """Canonical key `{TYPE}:{YEAR}:{NUM}` for a Commission-document reference,
    spanning the two encodings the two stores use:

      - CELEX form ``52026PC0052``  -> ``COM:2026:52``
      - human form ``COM(2025)0747`` -> ``COM:2025:747``
      - prefixed   ``COM_JOIN(2025)0026`` -> ``JOIN:2025:26``

    Returns None for adopted-act CELEX (``32026L0804``), notice refs, etc. —
    things that are not COM/SWD/JOIN proposals. Used to dedup the existing
    ``commission_documents`` feed against eMeeting ``commission_document`` rows.
    """
    if not ref:
        return None
    r = ref.upper().strip()
    # CELEX form: sector(1) YYYY XX NNNN  (only sector 5 = proposals/prep acts).
    m = re.match(r"^5(\d{4})([A-Z]{2})0*(\d+)", r)
    if m:
        t = _CELEX_TYPE.get(m.group(2))
        return f"{t}:{m.group(1)}:{int(m.group(3))}" if t else None
    # Strip a leading "XXX_" wrapper (eMeeting sometimes prefixes "COM_").
    r = re.sub(r"^[A-Z]+_", "", r)
    # Human form: TYPE(YYYY)NNN  or  TYPE(YYYY) NNN
    m = re.match(r"^([A-Z]+)\s*\((\d{4})\)\s*0*(\d+)", r)
    if m and m.group(1) in ("COM", "SWD", "JOIN", "SEC", "JC"):
        t = "JOIN" if m.group(1) == "JC" else m.group(1)
        return f"{t}:{m.group(2)}:{int(m.group(3))}"
    return None


def commission_doc_enrichment(db: Session) -> Dict[str, dict]:
    """Map canonical COM/SWD/JOIN ref -> the EP committee-referral context for it.

    Reads the eMeeting ``commission_document`` rows (the COM proposals as referred
    to committee, which carry procedure_ref + committee) and groups them by
    canonical reference. Lets the existing Commission-documents feed — which has
    almost no procedure_ref — gain the dossier + committee + referral-PDF anchors
    that make it PI/tracked filterable. Surface-not-ingest: nothing is written.
    """
    try:
        rows = db.execute(text(
            """
            SELECT reference, procedure_ref, committee_code, committee_name,
                   pdf_url, source_url, meeting_date::text AS meeting_date
            FROM ep_emeeting_documents
            WHERE doc_kind = 'commission_document'
            ORDER BY meeting_date DESC NULLS LAST
            """
        )).mappings().all()
    except Exception:
        db.rollback()
        return {}
    out: Dict[str, dict] = {}
    for r in rows:
        key = canon_commission_ref(r["reference"])
        if not key:
            continue
        e = out.get(key)
        if e is None:
            e = {"procedure_ref": r["procedure_ref"], "committee_code": r["committee_code"],
                 "committee_name": r["committee_name"], "pdf_url": r["pdf_url"],
                 "source_url": r["source_url"], "committees": set()}
            out[key] = e
        if r["committee_code"]:
            e["committees"].add(r["committee_code"])
        # Prefer a non-null procedure_ref / pdf from any referring committee.
        if not e["procedure_ref"] and r["procedure_ref"]:
            e["procedure_ref"] = r["procedure_ref"]
        if not e["pdf_url"] and r["pdf_url"]:
            e["pdf_url"] = r["pdf_url"]
    return out

# Routing groups (the kinds each surface displays).
KINDS_IN_COMMITTEE = ("opinion", "draft_opinion")
# NOTE (31 Aug 2026): KINDS_ADOPTED_TEXT and KINDS_CATCHALL were declared here and
# imported by nothing -- a constant that looks like a route but is not one. Their
# kinds are now carried by KINDS_DOSSIER below. Kept only for backwards
# compatibility; do not add to them without also wiring a caller.
KINDS_ADOPTED_TEXT = ("adopted_text",)
KINDS_COMMISSION = ("commission_document",)
# DELIBERATELY NOT ROUTED to a dossier surface (decision recorded 31 Aug 2026):
#   miscellaneous (3,811) -- the DV catch-all. Genuinely heterogeneous; putting it
#     on a tracked file would bury the negotiating layer under background paper.
#     It stays queryable via /api/v1/emeeting-documents?doc_kind=miscellaneous.
#   presentation (23), oral_question (3) -- oral questions belong to the
#     Parliamentary Questions surface, not to the dossier view.
# This is a decision, not an oversight. Revisit only with a UI that can collapse it.
KINDS_CATCHALL = ("notice_to_members", "miscellaneous")
KINDS_POSITION = ("draft_report", "amendment", "compromise_amendments",
                  "opinion", "draft_opinion", "reasoned_opinion")
KINDS_AMENDMENTS = ("draft_report", "amendment", "compromise_amendments")
KINDS_VOTES = ("voting_list",)
KINDS_MINUTES = ("minutes",)

# The full substantive-dossier set shown on a tracked file (Position Analysis +
# file detail), in a sensible reading order: the rapporteur's report first, then
# the amendment/compromise layer, then the opinion-committee layer, then the
# legal-basis / trilogue-outcome / drafting documents. doc_kinds with real data
# only (see the ep_emeeting_documents distribution).
KINDS_DOSSIER = (
    "draft_report", "amendment", "compromise_amendments",
    "opinion", "draft_opinion", "reasoned_opinion",
    "agreed_text", "letter_of_agreement", "draft_resolution", "working_document",
    # Added 31 Aug 2026. Both were classified, stored with live PDF URLs, and
    # reachable from NO MEUB surface: `adopted_text` had a KINDS_ADOPTED_TEXT
    # constant that nothing ever imported, and `notice_to_members` sat in
    # KINDS_CATCHALL, likewise unimported. 2,526 documents were ingested and
    # invisible. They go at the END of the reading order: the committee's
    # adopted text closes the dossier, and notices to members are context
    # around it rather than the negotiating layer.
    "adopted_text", "notice_to_members", "report",
)

# Plain-language labels for each dossier kind (British English, no codes).
DOSSIER_LABELS = {
    "draft_report": "Draft report",
    "amendment": "Amendments",
    "compromise_amendments": "Compromise amendments",
    "opinion": "Opinion",
    "draft_opinion": "Draft opinion",
    "reasoned_opinion": "Reasoned opinion",
    "agreed_text": "Agreed text",
    "letter_of_agreement": "Letter of agreement",
    "draft_resolution": "Draft resolution",
    "working_document": "Working document",
    "adopted_text": "Text adopted in committee",
    "notice_to_members": "Notice to members",
    "report": "Committee report",
}


def voting_list_documents(
    db: Session,
    *,
    committees: Optional[Iterable[str]] = None,
    tracked_procs: Optional[Iterable[str]] = None,
    tracked_committees: Optional[Iterable[str]] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Committee voting-list documents (the amendment order papers), filterable.

    Standalone listing for the Votes 'Voting lists' view — independent of the
    roll-call store. ``committees`` is the PI lens (lead committee in the user's
    PI set); ``tracked_procs``/``tracked_committees`` is the My-Files lens (the
    voting list is on a dossier/committee the user tracks). Returns
    ``{"items": [...], "total": n}``.
    """
    where = ["doc_kind = 'voting_list'"]
    params: dict = {}

    committees = [c for c in (committees or []) if c]
    if committees:
        keys = ", ".join(f":c{i}" for i in range(len(committees)))
        params.update({f"c{i}": c for i, c in enumerate(committees)})
        where.append(f"committee_code IN ({keys})")

    tp = sorted({p for p in (tracked_procs or []) if p})
    tc = [c for c in (tracked_committees or []) if c]
    if tp or tc:
        ors = []
        if tp:
            tk = ", ".join(f":tp{i}" for i in range(len(tp)))
            params.update({f"tp{i}": p for i, p in enumerate(tp)})
            ors.append(f"procedure_ref IN ({tk})")
        if tc:
            ck = ", ".join(f":tc{i}" for i in range(len(tc)))
            params.update({f"tc{i}": c for i, c in enumerate(tc)})
            ors.append(f"committee_code IN ({ck})")
        where.append("(" + " OR ".join(ors) + ")")

    if search:
        params["q"] = f"%{search}%"
        where.append("(item_title ILIKE :q OR title ILIKE :q OR procedure_ref ILIKE :q)")

    where_sql = " AND ".join(where)
    try:
        total = db.execute(
            text(f"SELECT count(*) FROM ep_emeeting_documents WHERE {where_sql}"), params
        ).scalar() or 0
        params["lim"] = limit
        params["off"] = offset
        rows = db.execute(text(
            f"""
            SELECT reference, title, item_title, committee_code, committee_name,
                   meeting_date::text AS meeting_date, procedure_ref,
                   rapporteurs, pdf_url, source_url, languages
            FROM ep_emeeting_documents
            WHERE {where_sql}
            ORDER BY meeting_date DESC NULLS LAST
            LIMIT :lim OFFSET :off
            """
        ), params).mappings().all()
    except Exception:
        db.rollback()
        return {"items": [], "total": 0}
    return {"items": [dict(r) for r in rows], "total": int(total)}


def docs_by_committee_date(db: Session, doc_kind: str) -> Dict[tuple, List[dict]]:
    """eMeeting docs of one kind grouped by (committee_code, meeting_date).

    Used where the only join is committee + date (the two id spaces don't
    overlap): agendas -> calendar, minutes -> transcripts. Keys are
    ``(committee_code, 'YYYY-MM-DD')``. Surface-not-ingest.
    """
    try:
        rows = db.execute(text(
            """
            SELECT committee_code, meeting_date::text AS meeting_date,
                   item_title, title, pdf_url, source_url
            FROM ep_emeeting_documents
            WHERE doc_kind = :k AND committee_code IS NOT NULL
              AND meeting_date IS NOT NULL
            ORDER BY meeting_date DESC NULLS LAST
            """
        ), {"k": doc_kind}).mappings().all()
    except Exception:
        db.rollback()
        return {}
    out: Dict[tuple, List[dict]] = {}
    for r in rows:
        out.setdefault((r["committee_code"], r["meeting_date"]), []).append(dict(r))
    return out


def agendas_by_committee_date(db: Session) -> Dict[tuple, List[dict]]:
    """eMeeting committee agendas grouped by (committee_code, meeting_date)."""
    return docs_by_committee_date(db, "agenda")


def attach_calendar_agendas(db: Session, events: List) -> None:
    """Attach matching eMeeting agendas to a list of CalendarEventResponse objects
    in place (by ep_committee_code + start_date). Cheap: one query, dict lookup."""
    agendas = agendas_by_committee_date(db)
    if not agendas:
        return
    for e in events:
        cc = getattr(e, "ep_committee_code", None)
        sd = getattr(e, "start_date", None)
        if not cc or not sd:
            continue
        hit = agendas.get((cc, sd.isoformat() if hasattr(sd, "isoformat") else str(sd)))
        if hit:
            e.emeeting_agendas = hit
            if not getattr(e, "agenda_url", None):
                # surface a usable agenda link where the event had none
                e.agenda_url = hit[0].get("pdf_url") or hit[0].get("source_url")


def docs_by_proc_committee(db: Session, kinds: Iterable[str]) -> Dict[tuple, List[dict]]:
    """All eMeeting docs of the given kinds, grouped by (procedure_ref, committee_code).

    One query; the caller attaches the relevant list to each per-(procedure,
    committee) row (the In-committee tab, Transcripts) without N+1. Newest first.
    """
    kinds = list(kinds)
    if not kinds:
        return {}
    kk = ", ".join(f":k{i}" for i in range(len(kinds)))
    params = {f"k{i}": k for i, k in enumerate(kinds)}
    try:
        rows = db.execute(text(
            f"""
            SELECT doc_kind, reference, title, item_title, committee_code,
                   committee_name, meeting_date::text AS meeting_date,
                   procedure_ref, pdf_url, source_url
            FROM ep_emeeting_documents
            WHERE doc_kind IN ({kk}) AND procedure_ref IS NOT NULL
              AND committee_code IS NOT NULL
            ORDER BY meeting_date DESC NULLS LAST
            """
        ), params).mappings().all()
    except Exception:
        db.rollback()
        return {}
    out: Dict[tuple, List[dict]] = {}
    for r in rows:
        out.setdefault((r["procedure_ref"], r["committee_code"]), []).append(dict(r))
    return out


def grouped_dossier_docs(db: Session, procedure_refs: Iterable[str], limit: int = 300) -> dict:
    """Substantive committee documents for a tracked file, grouped by doc_kind.

    Returns an ordered list of groups (skipping empty kinds), each with a
    plain-language label, the doc_kind key, and its documents. Shared by the
    tracked-file detail view and Position Analysis so both render identically.
    """
    docs = emeeting_docs_for(db, procedure_refs, kinds=KINDS_DOSSIER, limit=limit)
    by_kind: dict = {}
    for d in docs:
        by_kind.setdefault(d["doc_kind"], []).append(d)
    groups = [
        {"kind": k, "label": DOSSIER_LABELS.get(k, k.replace("_", " ").title()),
         "documents": by_kind[k]}
        for k in KINDS_DOSSIER if by_kind.get(k)
    ]
    return {"groups": groups, "total": len(docs)}


def emeeting_docs_for(
    db: Session,
    procedure_refs: Iterable[str],
    kinds: Optional[Iterable[str]] = None,
    limit: int = 200,
) -> List[dict]:
    """EP committee documents for the given OEIL procedures (optionally by kind)."""
    procs = sorted({p for p in (procedure_refs or []) if p})
    if not procs:
        return []
    keys = ", ".join(f":p{i}" for i in range(len(procs)))
    params = {f"p{i}": p for i, p in enumerate(procs)}
    kind_sql = ""
    if kinds:
        kinds = list(kinds)
        kk = ", ".join(f":k{i}" for i in range(len(kinds)))
        params.update({f"k{i}": k for i, k in enumerate(kinds)})
        kind_sql = f" AND doc_kind IN ({kk})"
    params["lim"] = limit
    try:
        rows = db.execute(text(
            f"""
            SELECT doc_kind, gepro_code, reference, title, item_title,
                   committee_code, committee_name, meeting_date::text AS meeting_date,
                   procedure_ref, rapporteurs, pdf_url, languages, source_url
            FROM ep_emeeting_documents
            WHERE procedure_ref = ANY(ARRAY[{keys}]){kind_sql}
            ORDER BY meeting_date DESC NULLS LAST LIMIT :lim
            """
        ), params).mappings().all()
    except Exception:
        db.rollback()
        return []
    return [dict(r) for r in rows]
