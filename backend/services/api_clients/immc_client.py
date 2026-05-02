"""
IMMC client — projects the IMMC-equivalent inter-institutional handoff
semantics from the public Cellar `cdm:event_legal_*` predicate family.

Phase 5 of docs/applications/euvoc.md. Background:

  IMMC ("Interinstitutional Management Material Configuration") is the
  EU's internal protocol for routing documents between Commission,
  Council, and EP. The public Cellar SPARQL graph does NOT expose
  predicates literally named `immc:*` — but it does expose the same
  concepts via `cdm:event_legal_*` predicates (initiated_by_institution,
  responsibility_of_institution, session_council, part_of_dossier,
  type, date, etc.).

  This client queries those events for a given CELEX-anchored work and
  returns a JSONB-ready shape that the legislative_carriages.immc_tags
  column carries. The Tracker UI + Predictions service then read this
  column to surface the handoff timeline.

  When the EU Publications Office eventually exposes IMMC predicates
  literally on Cellar (or when Brubru pulls IMMC tags from a different
  source), this client is the single place to update.

Public API:
    fetch_events_for_work(work_uri) -> dict
    fetch_events_for_celex(celex)    -> dict
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base_sparql_client import BaseSPARQLClient

logger = logging.getLogger(__name__)

CELLAR_SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
CDM_NS = "http://publications.europa.eu/ontology/cdm#"


class IMMCClient(BaseSPARQLClient):
    """SPARQL client scoped to the inter-institutional handoff event family."""

    def __init__(self, timeout: int = 60):
        super().__init__(endpoint_url=CELLAR_SPARQL, timeout=timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    # ------------------------------------------------------------------
    # Fetch events anchored to a Cellar work URI
    # ------------------------------------------------------------------

    async def fetch_events_for_work(self, work_uri: str) -> Dict[str, Any]:
        """Return the IMMC-equivalent event projection for one Cellar work."""
        if not work_uri:
            return {"events": [], "fetched_at": _now_iso()}

        query = f"""
        PREFIX cdm: <{CDM_NS}>
        SELECT DISTINCT ?event ?type ?date ?initiated_by ?responsibility_of
                        ?session_council ?dossier
        WHERE {{
            ?event cdm:event_legal_contains_work <{work_uri}> .
            OPTIONAL {{ ?event cdm:event_legal_type ?type . }}
            OPTIONAL {{ ?event cdm:event_legal_date ?date . }}
            OPTIONAL {{ ?event cdm:event_legal_initiated_by_institution ?initiated_by . }}
            OPTIONAL {{ ?event cdm:event_legal_responsibility_of_institution ?responsibility_of . }}
            OPTIONAL {{ ?event cdm:event_legal_session_council ?session_council . }}
            OPTIONAL {{ ?event cdm:event_legal_part_of_dossier ?dossier . }}
        }}
        ORDER BY ?date
        """
        try:
            rows = await self.select(query)
        except Exception as e:  # noqa: BLE001
            logger.warning("IMMCClient: SPARQL failed for %s: %s", work_uri, e)
            return {"events": [], "fetched_at": _now_iso(), "error": str(e)[:200]}

        events: List[Dict[str, Any]] = []
        for r in rows:
            event: Dict[str, Any] = {
                "event": r.get("event"),
                "type": r.get("type"),
                "date": r.get("date"),
                "initiated_by": r.get("initiated_by"),
                "responsibility_of": r.get("responsibility_of"),
                "session_council": r.get("session_council"),
                "dossier": r.get("dossier"),
            }
            # Drop empty keys for compactness
            events.append({k: v for k, v in event.items() if v})
        return {"events": events, "fetched_at": _now_iso(), "work_uri": work_uri}

    async def fetch_events_for_celex(self, celex: str) -> Dict[str, Any]:
        """Resolve CELEX -> work URI then fetch events."""
        if not celex:
            return {"events": [], "fetched_at": _now_iso()}
        # First resolve CELEX to its Cellar work URI.
        try:
            rows = await self.select(
                f"""
                PREFIX cdm: <{CDM_NS}>
                SELECT ?work WHERE {{
                    ?work cdm:resource_legal_id_celex ?lit .
                    FILTER(STR(?lit) = "{celex}")
                }} LIMIT 1
                """
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("IMMCClient: CELEX->work lookup failed for %s: %s", celex, e)
            return {"events": [], "fetched_at": _now_iso(), "error": str(e)[:200]}
        if not rows or not rows[0].get("work"):
            return {"events": [], "fetched_at": _now_iso(), "celex": celex, "note": "work_uri not found"}
        work_uri = rows[0]["work"]
        result = await self.fetch_events_for_work(work_uri)
        result["celex"] = celex
        return result

    # ------------------------------------------------------------------
    # Helper — turn the JSONB-ready dict into a chronological timeline
    # ------------------------------------------------------------------

    @staticmethod
    def to_timeline(immc_tags: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort `events` by date and return a flat list ready for the UI."""
        events = (immc_tags or {}).get("events") or []
        return sorted(events, key=lambda e: e.get("date") or "")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
