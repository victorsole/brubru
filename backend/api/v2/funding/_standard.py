"""The funding standard's shared pieces (proposal of 23 Oct 2026, Phase 2: one name and one parameter
set for every funding list).

Victor's decisions of 23 Oct 2026: bodies included by default (`include_body=true`), 50 items per
page, at most 200 (a list that allowed more keeps its maximum until the legacy date).
"""
from __future__ import annotations

from fastapi import Query

INCLUDE_BODY_DOC = "Return body_txt / body_html on every item of the list (default true)."


def include_body_param():
    """The `include_body` query parameter of a funding list: on unless the caller turns it off."""
    return Query(True, description=INCLUDE_BODY_DOC)


def without_bodies(envelope, include_body: bool):
    """A list answered with include_body=false: its items without body_txt / body_html. For the lists
    whose handler always composes the body (the v1 handlers behind the F&T and TED routes)."""
    if include_body:
        return envelope
    for item in getattr(envelope, "data", None) or []:
        for field in ("body_txt", "body_html"):
            if isinstance(item, dict):
                if field in item:
                    item[field] = None
            elif hasattr(item, field):
                setattr(item, field, None)
    return envelope
