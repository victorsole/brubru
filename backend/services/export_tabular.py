"""
Tabular export for the Brubru Data API — turn a JSON list response into CSV or XLSX.

Design (agreed with Victor):
- AUTO-FLATTEN EVERYTHING: union all keys across the page's records; nested objects become
  dot-columns ("competent_authority.authority"); lists become JSON-in-cell. No curation.
- Excel caps a cell at 32,767 chars, so every cell is truncated to that with a marker —
  the file never corrupts even when a record carries a huge body_html or GeoJSON geometry.
- The primary array is found under `data` (v1/v2 envelope), `items`, `records`, or `features`
  (a GeoJSON FeatureCollection -> flatten each feature's properties + geometry type).

Pure functions, no FastAPI import here — the middleware wires it to responses.
"""
from __future__ import annotations

import csv
import io
import json
import re
from typing import Any, Optional

CELL_MAX = 32767            # Excel hard per-cell character limit
_TRUNC = "…[truncated]"
# openpyxl rejects these XML-illegal control chars (common in scraped body_html/body_txt)
# with IllegalCharacterError; strip them for the xlsx path (CSV tolerates them fine).
_ILLEGAL_XLSX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _cell(v: Any) -> Any:
    """Scalar for a spreadsheet cell; strings truncated to the Excel limit."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return s if len(s) <= CELL_MAX else s[: CELL_MAX - len(_TRUNC)] + _TRUNC


def flatten(rec: dict, prefix: str = "") -> dict:
    """Nested dict -> dot-keyed flat dict; lists serialised to a JSON string cell."""
    flat: dict[str, Any] = {}
    for k, v in (rec or {}).items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            flat.update(flatten(v, key + "."))
        elif isinstance(v, list):
            flat[key] = json.dumps(v, ensure_ascii=False)
        else:
            flat[key] = v
    return flat


def _columns(rows: list[dict]) -> list[str]:
    """Union of all keys across rows, in first-seen order (stable, sparse-safe)."""
    cols, seen = [], set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                cols.append(k)
    return cols


def extract_records(body: Any) -> Optional[list[dict]]:
    """Find the primary list of records in a parsed JSON body. None if not a list endpoint."""
    if isinstance(body, list):
        return [r for r in body if isinstance(r, dict)]
    if isinstance(body, dict):
        for key in ("data", "items", "records"):
            arr = body.get(key)
            if isinstance(arr, list):
                return [r for r in arr if isinstance(r, dict)]
        # Endpoints that name their own envelope (`carriages`, `events`,
        # `tracked_files`, `dates`, ...) were silently passed through as JSON.
        # Fall back to the longest list of objects rather than maintaining a
        # list of every key any endpoint might invent.
        candidates = {
            k: v for k, v in body.items()
            if isinstance(v, list) and v and all(isinstance(r, dict) for r in v)
        }
        if candidates:
            best = max(candidates, key=lambda k: len(candidates[k]))
            return candidates[best]
        feats = body.get("features")           # GeoJSON FeatureCollection
        if isinstance(feats, list):
            out = []
            for f in feats:
                props = dict((f.get("properties") or {}))
                geom = f.get("geometry") or {}
                props["geometry_type"] = geom.get("type")
                out.append(props)
            return out
    return None


def to_csv(records: list[dict], path: str | None = None) -> bytes:
    rows = [flatten(r) for r in records]
    spec = columns_for(path)
    if spec:
        cols, rows = _curate(rows, spec)
    else:
        cols = _columns(rows)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: _cell(r.get(k)) for k in cols})
    return buf.getvalue().encode("utf-8-sig")   # BOM so Excel opens UTF-8 cleanly


def _xlsx_cell(v: Any) -> Any:
    c = _cell(v)
    return _ILLEGAL_XLSX.sub("", c) if isinstance(c, str) else c


def to_xlsx(records: list[dict], path: str | None = None) -> bytes:
    from openpyxl import Workbook
    rows = [flatten(r) for r in records]
    spec = columns_for(path)
    if spec:
        cols, rows = _curate(rows, spec)
    else:
        cols = _columns(rows)
    wb = Workbook(write_only=True)              # streaming writer, low memory
    ws = wb.create_sheet("data")
    ws.append([_xlsx_cell(c) for c in cols])
    for r in rows:
        ws.append([_xlsx_cell(r.get(k)) for k in cols])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


CONTENT_TYPES = {
    "csv": "text/csv",   # Starlette appends charset=utf-8 for text/* (avoids a doubled param)
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


# ---------------------------------------------------------------------------
# Curated columns for the My EU Bubble downloads
# ---------------------------------------------------------------------------
# The module contract above is auto-flatten-everything, and the Data API's 934
# endpoints depend on it: an API customer wants every field, uncurated. These
# maps are an OPT-IN OVERLAY for the handful of paths behind MEUB's download
# button, where the audience is a policy officer opening the file in Excel
# rather than a developer parsing it.
#
# A mapped path emits ONLY these columns, in this order, with these headers.
# That is the point -- it drops internal plumbing (`matches_tracked`,
# `search_vector`, ids) that means nothing in a spreadsheet. Any path without
# an entry keeps the uncurated behaviour untouched.
#
# Longest matching prefix wins, so "/api/ep-votes/plenary" can differ from
# "/api/ep-votes".
COLUMN_MAPS: dict[str, list[tuple[str, str]]] = {
    "/api/parliamentary-questions": [
        ("reference", "Reference"),
        ("type", "Type"),
        ("subject", "Subject"),
        ("submitted_date", "Submitted"),
        ("answered_date", "Answered"),
        ("meps", "MEPs"),
        ("answering_institution", "Answering institution"),
        ("answering_commissioner", "Commissioner"),
        ("related_celex", "Related law (CELEX)"),
        ("url", "Link"),
    ],
    "/api/ep-votes": [
        ("title", "File"),
        ("procedure_ref", "Procedure"),
        ("vote_date", "Date"),
        ("committee", "Committee"),
        ("result", "Result"),
        ("votes_for", "For"),
        ("votes_against", "Against"),
        ("votes_abstain", "Abstentions"),
        ("url", "Link"),
    ],
    "/api/lobby-meetings": [
        ("meeting_date", "Date"),
        ("organisation_met", "Organisation"),
        ("org_category", "Organisation type"),
        ("org_country", "Country"),
        ("host_name", "Met with"),
        ("host_role", "Role"),
        ("host_dg_name|host_dg", "DG"),
        ("host_cabinet", "Cabinet"),
        ("subject", "Subject"),
        ("representatives", "Representatives"),
        ("location", "Location"),
        ("transparency_register_id", "Transparency Register ID"),
        ("source_url", "Link"),
    ],
    "/api/eu-calendar/events": [
        ("start_date", "Date"),
        ("start_time", "Time"),
        ("title", "Event"),
        ("institution", "Institution"),
        ("event_type", "Type"),
        ("ep_committee_code", "Committee"),
        ("council_configuration", "Council configuration"),
        ("location", "Location"),
        ("procedure_refs", "Procedures"),
        ("source_url", "Link"),
    ],
    "/api/legislative-train/carriages": [
        ("short_title|title", "File"),
        ("oeil_procedure_ref", "Procedure"),
        ("current_status", "Status"),
        ("committee", "Committee"),
        ("rapporteur", "Rapporteur"),
        ("days_in_current_status", "Days in status"),
        ("is_blocked", "Blocked"),
        ("policy_areas", "Policy areas"),
    ],
    "/api/consultations": [
        ("short_title|title", "Consultation"),
        ("status", "Status"),
        ("consultation_type", "Type"),
        ("start_date", "Opens"),
        ("end_date", "Deadline"),
        ("days_remaining", "Days left"),
        ("dg_name|dg_responsible", "Directorate-General"),
        ("policy_areas", "Policy areas"),
        ("feedback_count", "Feedback received"),
        ("portal_url", "Link"),
    ],
    "/api/oj/entries": [
        ("oj_date", "OJ date"),
        ("series", "Series"),
        ("oj_number", "OJ number"),
        ("title", "Act"),
        ("act_type", "Act type"),
        ("institution", "Institution"),
        ("celex", "CELEX"),
        ("theme", "Theme"),
        ("change_kind", "Change"),
        ("plain_explanation", "In plain terms"),
        ("matched_procedure_ref", "Procedure"),
        ("eurlex_url", "EUR-Lex"),
    ],
    "/api/eu-news/items": [
        ("news_date", "Date"),
        ("title", "Headline"),
        ("summary", "Summary"),
        ("institution", "Institution"),
        ("dg_name|commission_dg", "DG"),
        ("item_type", "Type"),
        ("policy_areas", "Policy areas"),
        ("interest_reason", "Why it matched"),
        ("source_url", "Link"),
    ],
    "/api/plenary-agenda": [
        ("adoption_date", "Date"),
        ("title", "Item"),
        ("ta_reference", "Adopted text"),
        ("procedure_ref", "Procedure"),
        ("committees", "Committees"),
        ("document_url", "Document"),
        ("oeil_url", "Procedure file"),
    ],
    "/api/legislative-train/tracked": [
        ("title", "File"),
        ("oeil_procedure_ref", "Procedure"),
        ("current_status", "Status"),
        ("lead_committee", "Lead committee"),
        ("days_in_current_status", "Days in status"),
        ("is_blocked", "Blocked"),
        ("celex_numbers", "CELEX"),
        ("tracked_since", "Tracking since"),
        ("last_updated", "Last change"),
    ],
    "/api/transcripts": [
        ("meeting_date", "Date"),
        ("title", "Meeting"),
        ("institution", "Institution"),
        ("committee_code", "Committee"),
        ("status", "Status"),
        ("language", "Language"),
        ("duration_minutes", "Minutes"),
        ("word_count", "Words"),
        ("procedure_refs", "Procedures"),
    ],
    "/api/council-watch": [
        ("date", "Date"),
        ("title", "Item"),
        ("kind", "Type"),
        ("institution", "Institution"),
        ("configuration", "Council configuration"),
        ("summary", "Summary"),
        ("url", "Link"),
    ],
    "/api/mep-watch": [
        ("name", "MEP"),
        ("question_count", "Questions"),
        ("latest_date", "Latest question"),
        ("sample_subjects", "Recent subjects"),
        ("profile_url", "Profile"),
    ],
    # --- Tenderator -------------------------------------------------------
    # The feed normalises six sources (TED, F&T proposals, F&T tenders, F&T
    # funded projects, agency procurement, FTS awards) onto one shape, so one
    # map covers every chip. `match_score` only appears in the "your matches"
    # view; _curate drops a column absent from every row, so the sheet does not
    # carry an empty "Match" for the other views.
    "/api/tenders/unified-feed": [
        ("title", "Opportunity"),
        ("source", "Source"),
        ("external_id", "Reference"),
        ("programme", "Programme"),
        ("organisation", "Organisation"),
        ("country", "Country"),
        ("deadline", "Deadline"),
        ("budget", "Budget"),
        ("currency", "Currency"),
        ("status", "Status"),
        ("match_score", "Match score"),
        ("published_at", "Published"),
        ("translated_from", "Translated from"),
        ("description", "Description"),
        ("source_url", "Link"),
    ],
    "/api/tenders/calendar-deadlines": [
        ("deadline", "Deadline"),
        ("title", "Opportunity"),
        ("source", "Source"),
        ("ref", "Reference"),
        ("programme", "Programme"),
        ("country", "Country"),
        ("budget", "Budget"),
        ("currency", "Currency"),
        ("source_url", "Link"),
    ],
    "/api/tenders/pipeline": [
        ("title", "Opportunity"),
        ("status", "Stage"),
        ("next_step", "Next step"),
        ("next_step_due", "Next step due"),
        ("pm_assignee", "Owner"),
        ("deadline", "Deadline"),
        ("budget", "Budget"),
        ("currency", "Currency"),
        ("organisation", "Organisation"),
        ("country", "Country"),
        ("programme", "Programme"),
        ("source", "Source"),
        ("notes", "Notes"),
        ("source_url", "Link"),
    ],
    "/api/tenders/matches": [
        ("tender.title", "Tender"),
        ("tender.publication_number", "Reference"),
        ("match_score", "Match score"),
        ("tender.buyer_country", "Country"),
        ("tender.official_name", "Contracting authority"),
        ("tender.submission_deadline", "Deadline"),
        ("tender.estimated_value", "Value"),
        ("tender.procedure_type", "Procedure"),
        ("tender.cpv_main", "CPV"),
        ("match_details", "Why it matched"),
        ("is_saved", "Saved"),
        ("is_applied", "Applied"),
        ("tender.ted_url", "Link"),
    ],
}


def columns_for(path: str | None) -> Optional[list[tuple[str, str]]]:
    """Curated (field, header) pairs for an API path, longest prefix wins."""
    if not path:
        return None
    best: Optional[str] = None
    for prefix in COLUMN_MAPS:
        if path.startswith(prefix) and (best is None or len(prefix) > len(best)):
            best = prefix
    return COLUMN_MAPS[best] if best else None


def _pick(row: dict, field: str) -> Any:
    """Value for a field spec; "a|b" takes the first candidate with a value."""
    for cand in field.split("|"):
        v = row.get(cand)
        if v not in (None, ""):
            return v
    return ""


def _curate(rows: list[dict], spec: list[tuple[str, str]]) -> tuple[list[str], list[dict]]:
    """Reduce flattened rows to the mapped fields, renamed and reordered.

    A mapped field absent from every row is dropped rather than emitted as a
    blank column, so a sheet never advertises data the endpoint does not return.
    A spec may list fallbacks as "short_title|title": the AI-written short name
    is the better column heading, but it is still being backfilled, so a file
    without one must show its full title rather than an empty first cell.
    """
    present = [
        (f, h) for f, h in spec
        if any(any(c in r for c in f.split("|")) for r in rows)
    ]
    headers = [h for _, h in present]
    out = [{h: _pick(r, f) for f, h in present} for r in rows]
    return headers, out


def serialize(records: list[dict], fmt: str, path: str | None = None) -> bytes:
    return to_csv(records, path) if fmt == "csv" else to_xlsx(records, path)
