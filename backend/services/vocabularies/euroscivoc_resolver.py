"""
EuroSciVoc resolver — research-science-taxonomy companion to EuroVoc.

Phase 8 of docs/applications/euvoc.md.

EuroSciVoc ("European Science Vocabulary") is a multilingual taxonomy
covering all main fields of science. ~1,000+ concepts in 6 languages
(EN, FR, DE, IT, PL, ES — note: NOT Catalan, NOT Dutch). Maintained by
the Publications Office, aligned with Linked Open Data standards.

  URI base   : http://data.europa.eu/8mn/euroscivoc/{concept_id}
  Hub page   : https://op.europa.eu/en/web/eu-vocabularies/euroscivoc
  Local dump : data/eu_vocabularies/euroscivoc.ttl  (gitignored when present)

Public API:
    resolve(uri, lang)              -> Optional[str]
    search(keyword, lang, limit)    -> list[dict]
    is_loaded()                      -> bool

Honesty disclaimer (May 2026): the EuroSciVoc Turtle dump is downloaded
manually from `op.europa.eu` (the SPARQL discovery path was flaky during
implementation). The resolver loads from
`data/eu_vocabularies/euroscivoc.ttl` if present; otherwise returns
empty results gracefully. To activate live data:

    1. Visit https://op.europa.eu/en/web/eu-vocabularies/dataset/-/resource?uri=http://publications.europa.eu/resource/dataset/euroscivoc
    2. Download the Turtle distribution to data/eu_vocabularies/euroscivoc.ttl
    3. Restart the backend.

Catalan fallback: EuroSciVoc has no Catalan labels. resolve(uri, "ca")
falls back through the same CA → ES → EN chain that
authority_label_cache uses.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

# Brubru repo root — file at <repo>/data/eu_vocabularies/euroscivoc.ttl.
_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DUMP_PATH = _ROOT / "data" / "eu_vocabularies" / "euroscivoc.ttl"

EUROSCIVOC_URI_PREFIX = "http://data.europa.eu/8mn/euroscivoc/"
SUPPORTED_LANGS = ("en", "fr", "de", "it", "pl", "es")

# CA → ES → EN fallback chain (mirrors authority_label_cache).
DEFAULT_LANG_FALLBACK_CHAIN: Sequence[str] = ("ca", "es", "en")


class EuroSciVocResolver:
    """Loads the EuroSciVoc Turtle dump (when present) into rdflib and
    answers resolution / search queries."""

    def __init__(self, dump_path: Optional[Path] = None):
        self._dump_path = dump_path or DEFAULT_DUMP_PATH
        self._graph = None  # type: Optional[Any]
        self._index_pref_label_by_uri_lang: Dict[tuple, str] = {}
        self._index_uri_by_label_lang: Dict[tuple, str] = {}
        self._loaded = False
        self._load_attempted = False

    # ------------------------------------------------------------------
    # Lazy load — keep startup cheap when the dump isn't present.
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True
        if not self._dump_path.exists():
            logger.info(
                "EuroSciVoc dump not found at %s — resolver returning empty results. "
                "See service docstring for download instructions.",
                self._dump_path,
            )
            return
        try:
            from rdflib import Graph
            from rdflib.namespace import SKOS

            g = Graph()
            g.parse(str(self._dump_path), format="turtle")
            for s, _p, o in g.triples((None, SKOS.prefLabel, None)):
                lang = getattr(o, "language", None)
                if lang and str(s).startswith(EUROSCIVOC_URI_PREFIX):
                    self._index_pref_label_by_uri_lang[(str(s), lang)] = str(o)
                    self._index_uri_by_label_lang[(str(o).lower(), lang)] = str(s)
            self._graph = g
            self._loaded = True
            logger.info(
                "EuroSciVoc loaded: %d (uri, lang) entries from %s",
                len(self._index_pref_label_by_uri_lang),
                self._dump_path,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("EuroSciVoc load failed (%s) — resolver returning empty results", e)

    def is_loaded(self) -> bool:
        self._ensure_loaded()
        return self._loaded

    # ------------------------------------------------------------------
    # Resolve URI -> label
    # ------------------------------------------------------------------

    def resolve(
        self,
        uri: str,
        lang: str = "en",
        *,
        fallback_chain: Optional[Sequence[str]] = None,
    ) -> Optional[str]:
        """URI -> skos:prefLabel in `lang`, with CA → ES → EN fallback."""
        self._ensure_loaded()
        if not self._loaded or not uri:
            return None
        chain = self._build_chain(lang, fallback_chain)
        for ln in chain:
            label = self._index_pref_label_by_uri_lang.get((uri, ln))
            if label:
                return label
        return None

    # ------------------------------------------------------------------
    # Search keyword -> URI
    # ------------------------------------------------------------------

    def search(
        self,
        keyword: str,
        lang: str = "en",
        limit: int = 20,
    ) -> List[Dict[str, str]]:
        """Free-text search the prefLabels in `lang`."""
        self._ensure_loaded()
        if not self._loaded or not keyword or len(keyword.strip()) < 2:
            return []
        kw_lower = keyword.lower().strip()
        hits: List[Dict[str, str]] = []
        for (label_lower, label_lang), uri in self._index_uri_by_label_lang.items():
            if label_lang != lang:
                continue
            if kw_lower in label_lower:
                hits.append({"uri": uri, "lang": lang, "pref_label": self._index_pref_label_by_uri_lang.get((uri, lang), "")})
                if len(hits) >= limit:
                    break
        return hits

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_chain(primary: str, fallback_chain: Optional[Sequence[str]] = None) -> Sequence[str]:
        chain: List[str] = []
        primary = (primary or "en").lower()
        chain.append(primary)
        for ln in fallback_chain or DEFAULT_LANG_FALLBACK_CHAIN:
            if ln not in chain:
                chain.append(ln)
        if "en" not in chain:
            chain.append("en")
        return chain
