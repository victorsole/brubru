"""A filter on an enum column, for a value a person typed. A value outside the enum used to reach PostgreSQL and answer 500
(13 fields on 4 Nov 2026, found by sending nonsense through the API Console)."""
from fastapi import HTTPException


def enum_choice(column, value: str, field: str) -> str:
    """The column's own label for what was typed, in any case, or a 400 that names the choices."""
    labels = list(getattr(column.type, "enums", None) or [])
    typed = value.strip()
    if not labels:
        return typed
    for label in labels:
        if label.casefold() == typed.casefold():
            return label
    raise HTTPException(status_code=400, detail=f"{field} must be one of {sorted(labels)}")
