"""
File search + label resolution for the Comparator picker.

The Comparator's UX problem is that users do not write CELEX numbers from
memory — they write "GDPR", "AI Act", "the data act", or "2024/0079" without
the parens. This module gives the Comparator picker three capabilities:

1. `search(query, db, limit)` — fuzzy match across the alias resolver, the
    `eu_laws` table (FTS + CELEX), and the `legislative_carriages` table
    (OEIL ref, title, lookup_title). Returns ranked SearchHit dicts.

2. `my_files(user_id, db)` — user's tracked files (from `user_carriage_tracks`
    excluding archived). Same SearchHit shape so the picker can reuse one
    rendering path.

3. `resolve(refs, db)` — given a list of file_refs already in a saved grid,
    return their display labels. Used to enrich /grids/{id} responses.

All three return SearchHit-shaped dicts:
    {
      "file_ref": "32016R0679",
      "label": "GDPR",
      "subtitle": "Regulation (EU) 2016/679 on the protection of natural persons …",
      "type": "celex",
      "alias": "GDPR",
      "source": "alias"
    }
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.parsers.law_alias_resolver import _load_acronyms
from services.comparator.deep_dives import deep_dive_for_file_ref


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hit(
    *,
    file_ref: str,
    label: str,
    subtitle: Optional[str],
    type_: str,
    alias: Optional[str] = None,
    source: str,
    committee: Optional[str] = None,
    celex_candidates: Optional[List[str]] = None,
) -> Dict[str, Any]:
    dd = deep_dive_for_file_ref(file_ref, celex_candidates=celex_candidates)
    return {
        "file_ref": file_ref,
        "label": label,
        "subtitle": subtitle,
        "type": type_,
        "alias": alias,
        "source": source,
        # Lead EP committee when known — lets the picker group by committee and
        # flag PI matches, consistent with the other MEUB subfeatures.
        "committee": committee or None,
        "deep_dive_url": dd["url"] if dd else None,
        "deep_dive_short_title": dd["short_title"] if dd else None,
    }


def _is_oeil_ref(s: str) -> bool:
    return "(" in s and "/" in s


def _is_celex(s: str) -> bool:
    return bool(s) and s[0].isdigit() and len(s) >= 10


def _label_from_acronym_payload(alias: str, payload: Dict[str, Any]) -> str:
    """Pick the best short label: the acronym if it's distinct, else the full_name."""
    full_name = payload.get("full_name") or alias
    # If alias is short and ALL-CAPS (GDPR, DSA, DMA, AI Act exception below),
    # display it as the label and put the full_name in the subtitle.
    if alias.upper() == alias and len(alias) <= 6 and full_name and full_name != alias:
        return alias
    return full_name or alias


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_files(query: str, db: Session, *, limit: int = 20) -> List[Dict[str, Any]]:
    """Search across alias resolver + eu_laws + legislative_carriages.

    Ranking: alias-exact > carriage exact OEIL ref > CELEX exact > alias-substring
    > carriage title FTS > eu_laws title FTS. Return at most `limit` hits.
    """
    q = (query or "").strip()
    if not q:
        return []

    seen: set[str] = set()      # dedupe by file_ref
    out: List[Dict[str, Any]] = []

    def _push(hit: Dict[str, Any]) -> None:
        ref = hit["file_ref"]
        if ref in seen:
            return
        seen.add(ref)
        out.append(hit)

    # --- 1. Direct CELEX or OEIL match (user pasted the canonical key) ---
    if _is_celex(q):
        row = db.execute(
            text("SELECT celex, title FROM eu_laws WHERE celex = :celex LIMIT 1"),
            {"celex": q.upper()},
        ).fetchone()
        if row:
            title = (row[1] or "").strip()
            _push(_hit(
                file_ref=row[0],
                label=(title[:80] if title else row[0]),
                subtitle=(row[0] if title else None),
                type_="celex", source="celex",
            ))

    if _is_oeil_ref(q):
        row = db.execute(
            text("""
                SELECT oeil_procedure_ref, title, lead_committee
                FROM legislative_carriages
                WHERE oeil_procedure_ref = :ref LIMIT 1
            """),
            {"ref": q},
        ).fetchone()
        if row:
            title = (row[1] or "").strip()
            label = title[:80] if title else row[0]
            subtitle = row[0] + (f" · {row[2]}" if row[2] else "")
            _push(_hit(
                file_ref=row[0], label=label, subtitle=subtitle,
                type_="oeil", source="oeil", committee=row[2],
            ))

    # --- 2. Alias resolver (GDPR, DSA, AI Act, Data Act, ...) ---
    acronyms = _load_acronyms()
    q_lower = q.lower()
    # Exact alias hits first (case-sensitive for short acronyms, fold-case for the rest)
    for alias, payload in acronyms.items():
        if alias == q or alias.lower() == q_lower:
            celex = payload.get("celex")
            if not celex:
                continue
            label = _label_from_acronym_payload(alias, payload)
            subtitle = payload.get("full_title") or payload.get("full_name")
            if subtitle and len(subtitle) > 200:
                subtitle = subtitle[:200]
            _push(_hit(
                file_ref=celex, label=label, subtitle=subtitle,
                type_="celex", alias=alias if alias != label else None, source="alias",
            ))

    # Substring alias hits — only fire on letter-ish queries to avoid noise
    # (numeric "aliases" like "2024" / "32" / "20" exist in the auto-extracted
    # set and pollute results when the user pastes a CELEX or year fragment).
    looks_alphabetic = len(q) >= 3 and any(ch.isalpha() for ch in q)
    if len(out) < limit and looks_alphabetic:
        for alias, payload in acronyms.items():
            # Filter out trash aliases that are pure digits or too short
            if len(alias) < 3 or alias.isdigit():
                continue
            full_name = (payload.get("full_name") or "")
            haystacks = [alias.lower(), full_name.lower()]
            if not any(q_lower in h for h in haystacks):
                continue
            celex = payload.get("celex")
            if not celex:
                continue
            label = _label_from_acronym_payload(alias, payload)
            subtitle = payload.get("full_title") or payload.get("full_name")
            if subtitle and len(subtitle) > 200:
                subtitle = subtitle[:200]
            _push(_hit(
                file_ref=celex, label=label, subtitle=subtitle,
                type_="celex", alias=alias if alias != label else None, source="alias",
            ))
            if len(out) >= limit:
                break

    # --- 3. Carriage title / lookup_title FTS (OEIL refs, recent procedures) ---
    if len(out) < limit:
        like = f"%{q}%"
        rows = db.execute(
            text("""
                SELECT oeil_procedure_ref, title, lead_committee
                FROM legislative_carriages
                WHERE oeil_procedure_ref IS NOT NULL
                  AND (title ILIKE :like OR oeil_procedure_ref ILIKE :like)
                ORDER BY last_updated DESC NULLS LAST
                LIMIT :lim
            """),
            {"like": like, "lim": limit},
        ).fetchall()
        for r in rows:
            ref = r[0]
            if not ref:
                continue
            title = (r[1] or "")[:160]
            committee = r[2] or ""
            label = title or ref
            if len(label) > 70:
                label = label[:67] + "…"
            subtitle = ref + (f" · {committee}" if committee else "")
            _push(_hit(
                file_ref=ref, label=label, subtitle=subtitle,
                type_="oeil", source="oeil", committee=committee or None,
            ))
            if len(out) >= limit:
                break

    # --- 4. eu_laws title FTS (catch-all) ---
    if len(out) < limit:
        like = f"%{q}%"
        rows = db.execute(
            text("""
                SELECT celex, title, doc_type
                FROM eu_laws
                WHERE title ILIKE :like
                ORDER BY date DESC NULLS LAST
                LIMIT :lim
            """),
            {"like": like, "lim": limit},
        ).fetchall()
        for r in rows:
            celex = r[0]
            title = (r[1] or "")[:200]
            label = title[:70] + ("…" if len(title) > 70 else "")
            _push(_hit(
                file_ref=celex, label=label or celex, subtitle=f"{celex} · {r[2] or ''}",
                type_="celex", source="celex",
            ))
            if len(out) >= limit:
                break

    return out[:limit]


# ---------------------------------------------------------------------------
# My Files (Brubru-tracked) for the Comparator picker
# ---------------------------------------------------------------------------

def my_files_for_user(user_id: str, db: Session, *, limit: int = 50) -> List[Dict[str, Any]]:
    """User's `user_carriage_tracks` rows (excluding archived) joined to legislative_carriages.

    Any logged-in user can see their own tracked files; whether they can populate
    My Files in the first place is gated by their tier inside the My Files feature
    itself.
    """
    rows = db.execute(
        text("""
            SELECT t.id, c.oeil_procedure_ref, c.title, c.lead_committee,
                   c.celex_numbers, t.tracked_since
            FROM user_carriage_tracks t
            LEFT JOIN legislative_carriages c ON c.id = t.carriage_id
            WHERE t.user_id = :uid
              AND t.archived_at IS NULL
              AND c.oeil_procedure_ref IS NOT NULL
            ORDER BY t.tracked_since DESC NULLS LAST
            LIMIT :lim
        """),
        {"uid": user_id, "lim": limit},
    ).fetchall()
    out: List[Dict[str, Any]] = []
    for r in rows:
        ref = r[1]
        title = (r[2] or "")[:160]
        committee = r[3] or ""
        label = title or ref
        if len(label) > 80:
            label = label[:77] + "…"
        subtitle_bits: List[str] = [ref]
        if committee:
            subtitle_bits.append(committee)
        if r[4]:
            subtitle_bits.append(f"CELEX: {r[4][0]}")
        out.append(_hit(
            file_ref=ref, label=label, subtitle=" · ".join(subtitle_bits),
            type_="oeil", source="my_files", committee=committee or None,
            celex_candidates=list(r[4]) if r[4] else None,
        ))
    return out


def files_by_committees(committees: List[str], db: Session, *, limit: int = 40) -> List[Dict[str, Any]]:
    """Ongoing legislative files whose lead committee is in `committees`.

    Powers the Comparator's "Suggested from your interests" on-ramp: a new grid
    can start from PI-relevant procedures (resolved from the user's Policy
    Interests) instead of a blank search. SearchHit shape, committee-annotated.
    """
    if not committees:
        return []
    rows = db.execute(
        text("""
            SELECT oeil_procedure_ref, title, lead_committee
            FROM legislative_carriages
            WHERE lead_committee = ANY(:committees)
              AND oeil_procedure_ref IS NOT NULL
              AND title IS NOT NULL
              AND length(title) > 10
              AND title NOT ILIKE 'Procedure File:%'
            ORDER BY last_updated DESC NULLS LAST
            LIMIT :lim
        """),
        {"committees": list(committees), "lim": limit},
    ).fetchall()
    out: List[Dict[str, Any]] = []
    for r in rows:
        ref = r[0]
        if not ref:
            continue
        title = (r[1] or "")[:160]
        committee = r[2] or ""
        label = title or ref
        if len(label) > 80:
            label = label[:77] + "…"
        subtitle = ref + (f" · {committee}" if committee else "")
        out.append(_hit(
            file_ref=ref, label=label, subtitle=subtitle,
            type_="oeil", source="suggested", committee=committee or None,
        ))
    return out


# ---------------------------------------------------------------------------
# Resolve labels for already-saved refs
# ---------------------------------------------------------------------------

def resolve_labels(refs: List[str], db: Session) -> Dict[str, Dict[str, Any]]:
    """For each ref, return the best display label so a saved grid shows
    "GDPR" instead of "32016R0679" in the row header.

    Strategy: for OEIL refs, look up legislative_carriages.title; for CELEX,
    look up eu_laws.title and prefer the alias resolver name when one fits.
    """
    if not refs:
        return {}
    acronyms = _load_acronyms()
    # Reverse map: celex -> [(alias, payload)]
    celex_to_aliases: Dict[str, List[tuple]] = {}
    for alias, payload in acronyms.items():
        celex = payload.get("celex")
        if not celex:
            continue
        celex_to_aliases.setdefault(celex, []).append((alias, payload))

    out: Dict[str, Dict[str, Any]] = {}
    for ref in refs:
        if _is_oeil_ref(ref):
            row = db.execute(
                text("""
                    SELECT oeil_procedure_ref, title, lead_committee, celex_numbers
                    FROM legislative_carriages
                    WHERE oeil_procedure_ref = :ref LIMIT 1
                """),
                {"ref": ref},
            ).fetchone()
            if row:
                title = (row[1] or "")[:160]
                committee = row[2] or ""
                label = title or ref
                if len(label) > 80:
                    label = label[:77] + "…"
                subtitle = ref + (f" · {committee}" if committee else "")
                out[ref] = _hit(
                    file_ref=ref, label=label, subtitle=subtitle,
                    type_="oeil", source="oeil",
                    celex_candidates=list(row[3]) if row[3] else None,
                )
            else:
                out[ref] = _hit(file_ref=ref, label=ref, subtitle=None, type_="oeil", source="oeil")
        elif _is_celex(ref):
            # Prefer alias label
            aliases = celex_to_aliases.get(ref, [])
            label: Optional[str] = None
            alias_used: Optional[str] = None
            subtitle: Optional[str] = None
            if aliases:
                # Prefer short ALL-CAPS acronym, else the longest full_name
                short = [a for a, _ in aliases if a.upper() == a and 2 <= len(a) <= 6]
                if short:
                    alias_used = short[0]
                    label = alias_used
                else:
                    alias_used, payload = aliases[0]
                    label = payload.get("full_name") or alias_used
                payload = dict(aliases[0][1])
                subtitle = payload.get("full_title") or payload.get("full_name")
                if subtitle and len(subtitle) > 200:
                    subtitle = subtitle[:200]
            if label is None:
                row = db.execute(
                    text("SELECT celex, title FROM eu_laws WHERE celex = :celex LIMIT 1"),
                    {"celex": ref},
                ).fetchone()
                if row:
                    title = (row[1] or "")[:200]
                    label = title[:70] + ("…" if len(title) > 70 else "") if title else ref
                    subtitle = ref + (f" · {row[1][:120]}" if row[1] and row[1] != title else "")
                else:
                    label = ref
            out[ref] = _hit(
                file_ref=ref, label=label, subtitle=subtitle,
                type_="celex", alias=alias_used if alias_used and alias_used != label else None,
                source="alias" if alias_used else "celex",
            )
        else:
            # Unknown shape — pass it through unmodified
            out[ref] = _hit(file_ref=ref, label=ref, subtitle=None, type_="oeil", source="oeil")
    return out
