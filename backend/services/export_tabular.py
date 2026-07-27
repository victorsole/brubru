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
from typing import Any, Optional

CELL_MAX = 32767            # Excel hard per-cell character limit
_TRUNC = "…[truncated]"


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


def to_csv(records: list[dict]) -> bytes:
    rows = [flatten(r) for r in records]
    cols = _columns(rows)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: _cell(r.get(k)) for k in cols})
    return buf.getvalue().encode("utf-8-sig")   # BOM so Excel opens UTF-8 cleanly


def to_xlsx(records: list[dict]) -> bytes:
    from openpyxl import Workbook
    rows = [flatten(r) for r in records]
    cols = _columns(rows)
    wb = Workbook(write_only=True)              # streaming writer, low memory
    ws = wb.create_sheet("data")
    ws.append(cols)
    for r in rows:
        ws.append([_cell(r.get(k)) for k in cols])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


CONTENT_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def serialize(records: list[dict], fmt: str) -> bytes:
    return to_csv(records) if fmt == "csv" else to_xlsx(records)
