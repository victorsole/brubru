"""The shape of a package's review table, declared as data.

Why
---
The findings table has eight hardcoded columns and all 58 packages are reviewed
through them. That is a good default and a bad ceiling. Reviewing a textile
Digital Product Passport, the questions next to each obligation are substance,
threshold and test method. Reviewing a countervailing-duty package they are the
duty rate and the TARIC code, and a deadline column is dead space. Neither case
needs different requirements; both need a different table.

Borrowed from Mike OSS, whose tabular review workflows ship a `table-columns.yaml`
instead of a bespoke table per workflow: fixed prompts, declared columns,
rendered as an interactive table.

Two kinds of column
-------------------
`builtin`   one of the eight the table already knows how to render. Declaring
            these lets a package reorder them, relabel them, or leave one out.
`extracted` a field the analyser is asked to fill for each obligation, stored on
            the finding in `gap_findings.extra_fields` under the column id.

An absent profile means the default eight, so nothing changes for a package that
does not opt in. That matters: the failure mode of a feature like this is a
half-declared profile silently hiding the status column, so `validate_profile`
refuses a profile that omits the columns a compliance review cannot be read
without.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# What the findings table can already render. Order here is the default order.
BUILTIN_COLUMNS = [
    "status", "article", "obligation", "criticality",
    "deadline", "confidence", "evidence", "action",
]

# A review that cannot show the verdict, the obligation or where it came from is
# not a compliance review. A profile may reorder and relabel these; it may not
# drop them.
REQUIRED_BUILTINS = {"status", "article", "obligation"}

VALID_KINDS = {"builtin", "extracted"}

# Extracted values are rendered in a table cell, not a document.
MAX_EXTRACTED_CHARS = 120

# Column ids travel into JSON keys and CSS class names.
COLUMN_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")

# More than this and the table stops being scannable, which is the whole point
# of tabular review.
MAX_COLUMNS = 12
MAX_EXTRACTED = 4


def default_profile() -> Dict[str, Any]:
    return {"columns": [{"id": c, "kind": "builtin"} for c in BUILTIN_COLUMNS]}


def validate_profile(profile: Optional[Dict[str, Any]]) -> List[str]:
    """Return a list of problems. Empty means usable.

    A profile is optional; None is always valid and means the default.
    """
    if profile is None:
        return []

    problems: List[str] = []

    if not isinstance(profile, dict):
        return ["review_profile must be an object"]

    columns = profile.get("columns")
    if not isinstance(columns, list) or not columns:
        return ["review_profile.columns must be a non-empty list"]

    if len(columns) > MAX_COLUMNS:
        problems.append(
            f"{len(columns)} columns declared; more than {MAX_COLUMNS} stops the "
            "table being scannable")

    seen: set = set()
    builtins_present: set = set()
    extracted_count = 0

    for i, col in enumerate(columns):
        where = f"columns[{i}]"
        if not isinstance(col, dict):
            problems.append(f"{where} must be an object")
            continue

        cid = col.get("id")
        if not isinstance(cid, str) or not COLUMN_ID_RE.match(cid):
            problems.append(
                f"{where}.id '{cid}' must be lower-case letters, digits and "
                "underscores, starting with a letter")
            continue

        if cid in seen:
            problems.append(f"{where}.id '{cid}' is declared twice")
        seen.add(cid)

        kind = col.get("kind")
        if kind not in VALID_KINDS:
            problems.append(f"{where}.kind '{kind}' must be one of {sorted(VALID_KINDS)}")
            continue

        if kind == "builtin":
            if cid not in BUILTIN_COLUMNS:
                problems.append(
                    f"{where}.id '{cid}' is not a builtin column. Known: "
                    f"{', '.join(BUILTIN_COLUMNS)}")
            else:
                builtins_present.add(cid)
        else:
            extracted_count += 1
            if cid in BUILTIN_COLUMNS:
                problems.append(
                    f"{where}.id '{cid}' shadows a builtin column; pick another id")
            if not (col.get("prompt") or "").strip():
                problems.append(
                    f"{where} is extracted and needs a `prompt` saying what to "
                    "read out of the obligation")
            if not (col.get("label") or "").strip():
                problems.append(f"{where} is extracted and needs a `label` for the header")

    missing = REQUIRED_BUILTINS - builtins_present
    if missing:
        problems.append(
            f"missing required columns: {', '.join(sorted(missing))}. A review "
            "without the verdict, the article or the obligation text cannot be read")

    if extracted_count > MAX_EXTRACTED:
        problems.append(
            f"{extracted_count} extracted columns; more than {MAX_EXTRACTED} makes "
            "each analysis materially slower and the prompt less reliable")

    return problems


def extracted_columns(profile: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The columns the analyser has to fill, in declared order."""
    if not profile:
        return []
    return [c for c in profile.get("columns", [])
            if isinstance(c, dict) and c.get("kind") == "extracted"]


def build_extraction_prompt(profile: Optional[Dict[str, Any]]) -> str:
    """The fragment appended to the gap-analysis prompt, or '' if nothing to add.

    Deliberately explicit that a field with no answer in the obligation must come
    back null. An extracted column that invents a threshold is worse than an
    empty one, and this is the prompt that decides which happens.
    """
    cols = extracted_columns(profile)
    if not cols:
        return ""

    lines = [
        "",
        "ADDITIONALLY, extract these fields for this obligation and return them "
        'in an "extra_fields" object keyed exactly as shown:',
    ]
    for c in cols:
        lines.append(f'  "{c["id"]}": {c["prompt"].strip()}')
    lines.append(
        f"Each value must be a short string of at most {MAX_EXTRACTED_CHARS} "
        "characters, or null. Return null when the obligation does not state it. "
        "Do NOT infer, estimate or carry a value over from another obligation."
    )
    return "\n".join(lines)


# A model asked for a field it cannot find answers in prose rather than with
# null, however plainly the prompt asks. Observed in the first production run of
# a profiled package: "none stated", "Not explicitly stated in the requirement
# text", "no specific date stated". Every one of those belongs in an empty cell,
# not in the table as though it were data.
_NON_ANSWER_RE = re.compile(
    r"^(n/?a|null|none|unknown|unspecified|not applicable"
    r"|(no|none|not)\b[^.]{0,60}\b(stated|specified|given|mentioned|provided|available|date|value)"
    r"|not\s+(explicitly\s+)?(stated|specified|mentioned|given|provided|determinable)"
    r"[^.]{0,60})$",
    re.IGNORECASE,
)


def _is_non_answer(text: str) -> bool:
    return bool(_NON_ANSWER_RE.match(text.strip().rstrip(".")))


def clean_extracted(profile: Optional[Dict[str, Any]],
                    raw: Any) -> Optional[Dict[str, Any]]:
    """Keep only declared keys, coerce to short strings, drop empties.

    The model is asked for a flat object of strings; it will sometimes return
    numbers, nested objects, or keys nobody declared. Anything unrecognised is
    dropped rather than stored, so a profile change cannot leave stale keys on
    old findings and a hallucinated key never reaches the table.
    """
    cols = extracted_columns(profile)
    if not cols or not isinstance(raw, dict):
        return None

    allowed = {c["id"] for c in cols}
    out: Dict[str, Any] = {}
    for key, value in raw.items():
        if key not in allowed or value is None:
            continue
        if isinstance(value, (dict, list)):
            continue
        text = str(value).strip()
        if not text or _is_non_answer(text):
            continue
        out[key] = text[:MAX_EXTRACTED_CHARS]
    return out or None
