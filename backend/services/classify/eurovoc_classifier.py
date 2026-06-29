"""EuroVoc classification step (Phase 2). One shared function every data writer
calls (extract engine, procedure snapshot, social) so every Item is tagged into
the EU's official subject space. Graceful empty on any failure so the pipeline
never breaks.

Single source of truth (June 2026): the classification logic now lives in the
standalone open-source ``eurovoc`` package under ``sdk/eurovoc`` (the modern
PyEuroVoc successor). This module is a thin shim that other writers import; it
keeps the historical ``[{id, label, score, mt}]`` return shape and the
graceful-empty contract, and delegates the actual classifying to ``eurovoc``.

The package is the same multilingual sentence-transformers zero-shot classifier
this module used to contain, with identical descriptor set, gate calibration and
env knobs (EUROVOC_BACKEND, EUROVOC_ST_MODEL, EUROVOC_TOPK, EUROVOC_MIN_SCORE,
EUROVOC_MIN_MARGIN, EUROVOC_MIN_CLUSTER, EUROVOC_GATE_K), so behaviour is
unchanged.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_OFF = os.environ.get("EUROVOC_BACKEND", "sbert") == "off"

# Make the in-repo ``eurovoc`` package importable without requiring a separate
# pip install in every environment (Railway, CI, local). Its only dependencies
# beyond the backend's own are numpy + sentence-transformers, which the backend
# already ships. A real ``pip install eurovoc`` (once on PyPI) takes precedence
# if it is already importable.
_SDK_DIR = Path(__file__).resolve().parents[3] / "sdk" / "eurovoc"
if _SDK_DIR.is_dir() and str(_SDK_DIR) not in sys.path:
    sys.path.append(str(_SDK_DIR))

try:
    import eurovoc as _eurovoc
except Exception as e:  # pragma: no cover - import guard
    _eurovoc = None
    logger.warning("eurovoc package unavailable (classification disabled): %s", type(e).__name__)


def classify(text: str | None, lang: str = "en", top_k: int | None = None) -> list[dict]:
    """Return [{id, label, score, mt}] EuroVoc descriptors for the text, or []
    when the match is not confident (or on any failure). ``lang`` is
    informational (the model is multilingual)."""
    if _OFF or _eurovoc is None or not text:
        return []
    try:
        descs = _eurovoc.classify(text, lang=lang, top_k=top_k)
        return [{"id": d.id, "label": d.label, "score": d.score, "mt": d.mt} for d in descs]
    except Exception as e:
        logger.warning("EuroVoc classify failed: %s", type(e).__name__)
        return []


def classify_item(item, lang: str = "en", top_k: int | None = None) -> list[dict]:
    """Classify an extract Item from its title + summary + body."""
    text = " ".join(filter(None, [getattr(item, "title", None),
                                  getattr(item, "summary", None),
                                  (getattr(item, "body_txt", None) or "")[:2000]]))
    return classify(text, lang=lang, top_k=top_k)
