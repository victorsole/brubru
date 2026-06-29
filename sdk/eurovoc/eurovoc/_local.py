"""Local EuroVoc classifier: a multilingual sentence-transformers model embeds
the text and the EuroVoc descriptor labels (cached once) and returns the top-K
by cosine, behind a confidence gate. Modern, multilingual (incl. Catalan), full
context: the open successor to the 2021 PyEuroVoc BERT package, which truncated
to 512 tokens and no longer loads under transformers 5.x.

This is a standalone port of Brubru's production classifier. It needs
``sentence-transformers`` (imported lazily, only when you actually classify).
The 7,029-label embedding matrix is computed once and cached under
``~/.cache/eurovoc/``.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- subject-set pruning (same rules as production) ------------------------ #
# EuroVoc also contains organisation NAMES, treaty NAMES and instrument TYPES.
# They are not subjects and their surface words outrank real topics, so the
# subject classifier excludes them. Geography is kept.
_ORG_MT = {"7606", "7611", "7616", "7621", "7626", "1006"}
_TREATY_IN_CONSTRUCTION = re.compile(r"\b(EAEC|ECSC|EEC)\b|\bTreaty\b|\bConstitution\b")
_TREATY_NAME = re.compile(r" Treaty$|^Treaty (on|of|establishing)\b|^European Constitution$")
_NOISE_EXACT = {"regulation (eu)", "directive (eu)", "decision (eu)", "regulatory committee (eu)",
                "ec regulation", "eaec regulation", "eu regulation", "eu directive",
                "european union law", "application of eu law", "eu law", "regulation",
                "directive", "decision", "proposal (eu)", "european union", "member state"}


def _keep(desc: dict) -> bool:
    label = desc.get("label", "")
    mt = desc.get("mt")
    if mt in _ORG_MT:
        return False
    if mt == "1016" and _TREATY_IN_CONSTRUCTION.search(label):
        return False
    if _TREATY_NAME.search(label):
        return False
    return label.strip().lower() not in _NOISE_EXACT


# --- config ---------------------------------------------------------------- #
def _envf(name, default, cast):
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return cast(raw)
    except (TypeError, ValueError):
        return default


_MODEL_NAME = os.environ.get("EUROVOC_ST_MODEL", "intfloat/multilingual-e5-base")
_DEFAULT_TOPK = _envf("EUROVOC_TOPK", 6, int)
_MIN_SCORE = _envf("EUROVOC_MIN_SCORE", 0.80, float)
# Confidence gate: keep tags only when a microthesaurus cluster OR a cosine
# margin clears the floor (rejects proper-noun-heavy noise; "no tags beats
# wrong tags"). Same calibration as production.
_MIN_MARGIN = _envf("EUROVOC_MIN_MARGIN", 0.024, float)
_MIN_CLUSTER = _envf("EUROVOC_MIN_CLUSTER", 4, int)
_GATE_K = _envf("EUROVOC_GATE_K", 6, int)
_CLUSTER_EXCLUDE_MT = {"1016"}

_DESC_PATH = Path(__file__).resolve().parent / "data" / "eurovoc_descriptors.json"
_CACHE_DIR = Path(os.environ.get("EUROVOC_CACHE_DIR", str(Path.home() / ".cache" / "eurovoc")))

_state: Dict[str, Any] = {}


def _init() -> bool:
    if "ok" in _state:
        return _state["ok"]
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer
        descs = [d for d in json.loads(_DESC_PATH.read_text()) if _keep(d)]
        labels = [d["label"] for d in descs]
        # cache key binds model + prefix + exact ordered label list, so any change
        # invalidates (a count match alone would mis-map embeddings to labels).
        sig = hashlib.sha1(("passage:" + _MODEL_NAME + "\n" + "\n".join(labels)).encode()).hexdigest()[:16]
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache = _CACHE_DIR / f"eurovoc_descriptors.{sig}.emb.npy"
        model = SentenceTransformer(_MODEL_NAME)
        emb = None
        if cache.exists():
            cached = np.load(cache)
            if cached.shape[0] == len(labels):
                emb = cached
        if emb is None:
            emb = model.encode(["passage: " + l for l in labels], normalize_embeddings=True,
                               batch_size=128, show_progress_bar=False)
            np.save(cache, emb)
        _state.update(model=model, descs=descs, emb=emb, np=np, ok=True)
    except Exception:
        _state["ok"] = False
    return _state["ok"]


def classify_local(text: Optional[str], lang: str = "en",
                   top_k: Optional[int] = None) -> List[Dict[str, Any]]:
    """Return raw [{id,label,score,mt}] descriptors, or [] when the match is not
    confident (or the model is unavailable). ``lang`` is informational; the model
    is multilingual. Enrichment to Descriptor objects happens one layer up."""
    if not text:
        return []
    if not _init():
        raise RuntimeError(
            "sentence-transformers is required for local classification. "
            "Install it with: pip install 'eurovoc[local]'  (or pip install sentence-transformers)")
    np = _state["np"]
    k = top_k or _DEFAULT_TOPK
    q = _state["model"].encode(["query: " + text[:2000]], normalize_embeddings=True)[0]
    scores = _state["emb"] @ q
    order = np.argsort(-scores)[: max(k, _GATE_K)]
    raw = [(float(scores[int(i)]), _state["descs"][int(i)]) for i in order]
    if len(raw) < 2:
        return []
    win = raw[:_GATE_K]
    gate_span = win[0][0] - win[-1][0]
    counts: Dict[str, int] = {}
    for _, d in win:
        mt = d.get("mt")
        if mt and mt not in _CLUSTER_EXCLUDE_MT:
            counts[mt] = counts.get(mt, 0) + 1
    max_cluster = max(counts.values()) if counts else 0
    if max_cluster < _MIN_CLUSTER and gate_span < _MIN_MARGIN:
        return []
    return [{"id": d["id"], "label": d["label"], "score": round(s, 4), "mt": d.get("mt")}
            for s, d in raw[:k] if s >= _MIN_SCORE]
