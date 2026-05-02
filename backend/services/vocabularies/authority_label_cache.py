"""
Authority-label cache.

DB-backed cache for skos:prefLabel + skos:altLabel rows pulled from the
EU Publications Office Cellar SPARQL endpoint. Filled nightly by
scripts/sync_eu_authority_labels.py.

Design contract:
  - Cache hit  -> single indexed Postgres lookup (target p95 < 5 ms).
  - Cache miss -> fall back to live SPARQL (CellarSPARQLClient).
  - DB outage  -> log warning, return None — never raise.

Public API:
    resolve(uri, lang)              -> Optional[str]
    resolve_batch(uris, lang)       -> dict[str, str]
    lookup_by_label(text, lang)     -> Optional[str]
    refresh(uri, lang, ...)         -> None  (used by sync script)

Phase 1 of docs/applications/euvoc.md.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Brubru speaks 6 languages. We resolve labels in the user's language
# preference, falling back through this chain.
DEFAULT_LANG_FALLBACK_CHAIN: Sequence[str] = ("ca", "es", "en")


class AuthorityLabelCache:
    """
    Resolve EU authority-table URIs to human-readable labels.

    Construction is cheap — pass a SQLAlchemy Session per request via
    `Depends(get_db)`. The cache itself is the underlying Postgres table
    `eu_authority_labels` (PK uri,lang).
    """

    def __init__(
        self,
        db: Session,
        sparql_fallback: Optional[Any] = None,
    ):
        """
        Args:
            db: SQLAlchemy session.
            sparql_fallback: optional CellarSPARQLClient instance used on
                cache miss. If None, misses just return None.
        """
        self.db = db
        self._sparql_fallback = sparql_fallback

    # ------------------------------------------------------------------
    # Single resolution
    # ------------------------------------------------------------------

    def resolve(
        self,
        uri: str,
        lang: str = "en",
        *,
        fallback_chain: Optional[Sequence[str]] = None,
    ) -> Optional[str]:
        """
        URI -> skos:prefLabel in `lang`.

        Walks `fallback_chain` (default ca → es → en) if the requested
        language isn't cached. Returns None when the URI is unknown
        and SPARQL fallback also yields nothing.
        """
        if not uri:
            return None

        chain = self._build_chain(lang, fallback_chain)
        # 1. DB lookup across the fallback chain in one shot
        try:
            rows = self.db.execute(
                text(
                    """
                    SELECT lang, pref_label
                    FROM eu_authority_labels
                    WHERE uri = :uri AND lang = ANY(:langs)
                    """
                ),
                {"uri": uri, "langs": list(chain)},
            ).all()
        except SQLAlchemyError as e:
            logger.warning("authority_label_cache: DB query failed for %s: %s", uri, e)
            rows = []

        if rows:
            by_lang = {r.lang: r.pref_label for r in rows}
            for ln in chain:
                if ln in by_lang and by_lang[ln]:
                    return by_lang[ln]

        # 2. SPARQL fallback if configured
        if self._sparql_fallback is not None:
            try:
                # SPARQL endpoint speaks only a 2-letter code; pass the head
                # of the chain (the user's primary preference).
                label = self._call_sparql_resolver(uri, chain[0])
                if label:
                    return label
            except Exception as e:  # noqa: BLE001  (fallback must never raise)
                logger.warning("authority_label_cache: SPARQL fallback failed for %s: %s", uri, e)

        return None

    def resolve_batch(
        self,
        uris: Iterable[str],
        lang: str = "en",
        *,
        fallback_chain: Optional[Sequence[str]] = None,
    ) -> Dict[str, str]:
        """Bulk-resolve. Single SQL round trip + per-miss SPARQL only if configured."""
        seen: List[str] = list({u for u in uris if u})
        if not seen:
            return {}

        chain = self._build_chain(lang, fallback_chain)
        result: Dict[str, str] = {}

        try:
            stmt = text(
                """
                SELECT uri, lang, pref_label
                FROM eu_authority_labels
                WHERE uri = ANY(:uris) AND lang = ANY(:langs)
                """
            )
            rows = self.db.execute(stmt, {"uris": seen, "langs": list(chain)}).all()
        except SQLAlchemyError as e:
            logger.warning("authority_label_cache: batch DB query failed: %s", e)
            rows = []

        # Group rows by URI then pick the highest-priority lang
        by_uri: Dict[str, Dict[str, str]] = {}
        for r in rows:
            by_uri.setdefault(r.uri, {})[r.lang] = r.pref_label

        for uri in seen:
            langs = by_uri.get(uri, {})
            for ln in chain:
                if ln in langs and langs[ln]:
                    result[uri] = langs[ln]
                    break

        # SPARQL fallback for misses (only if configured AND batch is small;
        # we don't want to fan out 1000 SPARQL calls on a cold cache).
        if self._sparql_fallback is not None and len(seen) <= 25:
            for uri in seen:
                if uri in result:
                    continue
                try:
                    label = self._call_sparql_resolver(uri, chain[0])
                    if label:
                        result[uri] = label
                except Exception as e:  # noqa: BLE001
                    logger.warning("authority_label_cache: SPARQL fallback failed for %s: %s", uri, e)

        return result

    # ------------------------------------------------------------------
    # Reverse lookup — text -> URI (alt-label aware)
    # ------------------------------------------------------------------

    def lookup_by_label(
        self,
        text_query: str,
        lang: str = "en",
        *,
        limit: int = 5,
    ) -> List[Dict[str, str]]:
        """
        Reverse lookup. "DG GROW" -> the corporate-body URI for DG GROW.

        Searches both pref_label (case-insensitive equality) and alt_labels
        (array containment, case-insensitive via lowercase index). Returns up
        to `limit` matches, ordered by exactness.
        """
        if not text_query or len(text_query.strip()) < 2:
            return []

        q = text_query.strip()
        q_lower = q.lower()

        try:
            rows = self.db.execute(
                text(
                    """
                    SELECT uri, lang, pref_label, alt_labels, source_dataset_uri,
                           CASE
                               WHEN LOWER(pref_label) = :ql THEN 0
                               WHEN :q = ANY(alt_labels) THEN 1
                               WHEN LOWER(pref_label) LIKE :ql_prefix THEN 2
                               WHEN LOWER(pref_label) LIKE :ql_anywhere THEN 3
                               ELSE 4
                           END AS rank
                    FROM eu_authority_labels
                    WHERE lang = :lang
                      AND (
                          LOWER(pref_label) = :ql
                          OR :q = ANY(alt_labels)
                          OR LOWER(pref_label) LIKE :ql_prefix
                          OR LOWER(pref_label) LIKE :ql_anywhere
                      )
                    ORDER BY rank, LENGTH(pref_label)
                    LIMIT :lim
                    """
                ),
                {
                    "q": q,
                    "ql": q_lower,
                    "ql_prefix": f"{q_lower}%",
                    "ql_anywhere": f"%{q_lower}%",
                    "lang": lang,
                    "lim": limit,
                },
            ).all()
        except SQLAlchemyError as e:
            logger.warning("authority_label_cache: lookup_by_label failed for %r: %s", q, e)
            return []

        return [
            {
                "uri": r.uri,
                "lang": r.lang,
                "pref_label": r.pref_label,
                "alt_labels": list(r.alt_labels or []),
                "source_dataset_uri": r.source_dataset_uri,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Write API (used by sync script)
    # ------------------------------------------------------------------

    def upsert(
        self,
        uri: str,
        lang: str,
        pref_label: str,
        *,
        alt_labels: Optional[Sequence[str]] = None,
        source_dataset_uri: str,
    ) -> None:
        """Idempotent upsert. Used by the nightly sync."""
        if not pref_label:
            return
        self.db.execute(
            text(
                """
                INSERT INTO eu_authority_labels(uri, lang, pref_label, alt_labels, source_dataset_uri, fetched_at)
                VALUES (:uri, :lang, :pref_label, :alt_labels, :source, :now)
                ON CONFLICT (uri, lang) DO UPDATE SET
                    pref_label = EXCLUDED.pref_label,
                    alt_labels = EXCLUDED.alt_labels,
                    source_dataset_uri = EXCLUDED.source_dataset_uri,
                    fetched_at = EXCLUDED.fetched_at
                """
            ),
            {
                "uri": uri,
                "lang": lang,
                "pref_label": pref_label,
                "alt_labels": list(alt_labels or []),
                "source": source_dataset_uri,
                "now": datetime.now(timezone.utc),
            },
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _build_chain(
        primary: str,
        fallback_chain: Optional[Sequence[str]] = None,
    ) -> Sequence[str]:
        chain: List[str] = []
        primary = (primary or "en").lower()
        chain.append(primary)
        for ln in fallback_chain or DEFAULT_LANG_FALLBACK_CHAIN:
            if ln not in chain:
                chain.append(ln)
        # Always end with English as a guaranteed fallback.
        if "en" not in chain:
            chain.append("en")
        return chain

    def _call_sparql_resolver(self, uri: str, lang: str) -> Optional[str]:
        """Bridge to CellarSPARQLClient.resolve_authority_label.

        The Cellar client is async; this method runs synchronously inside a
        FastAPI request handler. We accept the cost (only fires on cache miss
        which should be rare) and use asyncio.run via a thread executor when
        an event loop is already running.
        """
        if self._sparql_fallback is None:
            return None
        import asyncio

        coro = self._sparql_fallback.resolve_authority_label(uri, language=lang)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        # Already inside an event loop — schedule and wait.
        # In practice the caller should pass an already-resolved label;
        # this branch is a defensive catch-all.
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result(timeout=10)
        except Exception as e:  # noqa: BLE001
            logger.warning("authority_label_cache: SPARQL bridge timed out for %s: %s", uri, e)
            return None
