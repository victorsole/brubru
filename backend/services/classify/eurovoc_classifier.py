"""
EuroVoc classification step (Phase 2). One shared function every data writer calls
(extract engine, procedure snapshot, social) so every Item is tagged into the EU's
official subject space. Graceful empty on any failure so the pipeline never breaks.

Default backend `sbert`: a multilingual sentence-transformers model embeds the text
and the 7,029 EuroVoc descriptor labels (cached once), returns the top-K by cosine.
Modern, multilingual incl. Catalan, large context — the "updated PyEuroVoc" the
paper's author suggested (the 2021 BERT package no longer loads under transformers 5.x).
Env: EUROVOC_BACKEND (sbert|off), EUROVOC_ST_MODEL, EUROVOC_TOPK.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# EuroVoc also contains organisation NAMES, treaty NAMES and legal-instrument TYPES.
# They are not subjects, and their surface words ("regulation", "Forum", "Treaty")
# outrank the real topics, so they are excluded from the subject-classification set.
#
# The authoritative signal is EuroVoc's own domain structure: every descriptor carries
# its microthesaurus code (`mt`, enriched into the descriptor file from the official
# SPARQL endpoint). Organisation/institution names live in five "organisations"
# microthesauri + EU-institutions; treaty markers (EAEC/ECSC/EEC Treaty, EU
# Constitution) live inside "European construction" alongside legit subjects, so those
# are pruned by name. Geography (e.g. "Community of Madrid" in 7211 regions) is KEPT.
_ORG_MT = {"7606", "7611", "7616", "7621", "7626", "1006"}  # UN/European/extra-Eu/world/NGO orgs + EU institutions
# Within "European construction" (1016), prune the EAEC/ECSC instrument + treaty markers.
_TREATY_IN_CONSTRUCTION = re.compile(r"\b(EAEC|ECSC|EEC|EU|EC)\b|\bTreaty\b|\bConstitution\b")
# Treaty NAMES anywhere (mt-independent, precise: suffix "... Treaty", "Treaty of/on/...",
# "European Constitution"). Deliberately narrow so subject tags like "EU financing",
# "EU aid", "international treaty" are NEVER removed.
_TREATY_NAME = re.compile(r" Treaty$|^Treaty (on|of|establishing)\b|^European Constitution$")
_NOISE_EXACT = {"regulation (eu)", "directive (eu)", "decision (eu)", "regulatory committee (eu)",
                "ec regulation", "eaec regulation", "eu regulation", "eu directive",
                "european union law", "application of eu law", "eu law", "regulation",
                "directive", "decision", "proposal (eu)", "european union", "member state"}


def _keep(desc: dict) -> bool:
    """Keep a EuroVoc descriptor only if it is a genuine subject (not an organisation,
    institution, treaty or legal-instrument name). Uses the microthesaurus code."""
    label = desc.get("label", "")
    mt = desc.get("mt")
    if mt in _ORG_MT:
        return False
    if mt == "1016" and _TREATY_IN_CONSTRUCTION.search(label):  # treaty markers within European construction
        return False
    if _TREATY_NAME.search(label):  # named treaties filed in other microthesauri
        return False
    return label.strip().lower() not in _NOISE_EXACT

_BACKEND = os.environ.get("EUROVOC_BACKEND", "sbert")
# multilingual-e5-base: retrieval-tuned, ranks precise topic descriptors above generic
# terms (MiniLM did not), covers all 6 Brubru langs incl. Catalan. Uses query/passage
# prefixes. Cosines run high (~0.80 relevant), hence the higher floor.
_MODEL_NAME = os.environ.get("EUROVOC_ST_MODEL", "intfloat/multilingual-e5-base")
_DEFAULT_TOPK = int(os.environ.get("EUROVOC_TOPK", "6"))
_MIN_SCORE = float(os.environ.get("EUROVOC_MIN_SCORE", "0.80"))
_DESC_PATH = Path(__file__).resolve().parents[2] / "data" / "eu_vocabularies" / "eurovoc_descriptors.json"
_EMB_CACHE = _DESC_PATH.with_name(f"eurovoc_descriptors.{re.sub(r'[^a-z0-9]+','_',_MODEL_NAME.lower())}.emb.npy")

_state: dict = {}


def _init_sbert() -> bool:
    if "ok" in _state:
        return _state["ok"]
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer
        descs = [d for d in json.loads(_DESC_PATH.read_text()) if _keep(d)]
        labels = [d["label"] for d in descs]
        model = SentenceTransformer(_MODEL_NAME)
        emb = None
        if _EMB_CACHE.exists():
            cached = np.load(_EMB_CACHE)
            if cached.shape[0] == len(labels):
                emb = cached
        if emb is None:
            emb = model.encode(["passage: " + l for l in labels], normalize_embeddings=True,
                               batch_size=128, show_progress_bar=False)
            np.save(_EMB_CACHE, emb)
        _state.update(model=model, descs=descs, emb=emb, np=np, ok=True)
        logger.info("EuroVoc sbert backend ready: %d descriptors", len(descs))
    except Exception as e:
        logger.warning("EuroVoc sbert backend unavailable: %s", type(e).__name__)
        _state["ok"] = False
    return _state["ok"]


def classify(text: str | None, lang: str = "en", top_k: int | None = None) -> list[dict]:
    """Return [{id, label, score}] EuroVoc descriptors for the text (top-K by cosine),
    or [] on any failure. lang is informational (the model is multilingual)."""
    if not text or _BACKEND == "off":
        return []
    if _BACKEND != "sbert" or not _init_sbert():
        return []
    np = _state["np"]
    k = top_k or _DEFAULT_TOPK
    try:
        q = _state["model"].encode(["query: " + text[:2000]], normalize_embeddings=True)[0]
        scores = _state["emb"] @ q  # cosine (both normalized)
        order = np.argsort(-scores)[: k * 2]
        out = []
        for i in order:
            s = float(scores[i])
            if s < _MIN_SCORE:
                break
            d = _state["descs"][int(i)]
            out.append({"id": d["id"], "label": d["label"], "score": round(s, 4)})
            if len(out) >= k:
                break
        return out
    except Exception as e:
        logger.warning("EuroVoc classify failed: %s", type(e).__name__)
        return []


def classify_item(item, lang: str = "en", top_k: int | None = None) -> list[dict]:
    """Classify an extract Item from its title + summary + body."""
    text = " ".join(filter(None, [getattr(item, "title", None),
                                  getattr(item, "summary", None),
                                  (getattr(item, "body_txt", None) or "")[:2000]]))
    return classify(text, lang=lang, top_k=top_k)
