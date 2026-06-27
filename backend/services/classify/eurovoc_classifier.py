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
# Within "European construction" (1016), prune the legacy EAEC/ECSC/EEC instrument +
# treaty markers ONLY. EU and EC are deliberately excluded: they prefix dozens of real
# subjects ("EU policy", "EU programme", "EU Charter of Fundamental Rights", "EC
# Directive") that must remain classifiable.
_TREATY_IN_CONSTRUCTION = re.compile(r"\b(EAEC|ECSC|EEC)\b|\bTreaty\b|\bConstitution\b")
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

def _env_num(name: str, default, cast):
    """Parse a numeric env var, falling back to the default on a bad value rather than
    crashing the whole import chain (the classify layer is imported by every writer)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return cast(raw)
    except (TypeError, ValueError):
        logger.warning("Bad %s=%r; using default %r", name, raw, default)
        return default


_BACKEND = os.environ.get("EUROVOC_BACKEND", "sbert")
if _BACKEND not in ("sbert", "off"):
    logger.warning("Unrecognised EUROVOC_BACKEND=%r; classification disabled (expected sbert|off)", _BACKEND)
# multilingual-e5-base: retrieval-tuned, ranks precise topic descriptors above generic
# terms (MiniLM did not), covers all 6 Brubru langs incl. Catalan. Uses query/passage
# prefixes. Cosines run high (~0.80 relevant), hence the higher floor.
_MODEL_NAME = os.environ.get("EUROVOC_ST_MODEL", "intfloat/multilingual-e5-base")
_DEFAULT_TOPK = _env_num("EUROVOC_TOPK", 6, int)
_MIN_SCORE = _env_num("EUROVOC_MIN_SCORE", 0.80, float)
_DESC_PATH = Path(__file__).resolve().parents[2] / "data" / "eu_vocabularies" / "eurovoc_descriptors.json"

_state: dict = {}


def _init_sbert() -> bool:
    if "ok" in _state:
        return _state["ok"]
    try:
        import hashlib
        import numpy as np
        from sentence_transformers import SentenceTransformer
        descs = [d for d in json.loads(_DESC_PATH.read_text()) if _keep(d)]
        labels = [d["label"] for d in descs]
        # Cache key is a content hash of (model, passage prefix, exact ordered label
        # list). emb[i] is aligned to descs[i] by position, so ANY change to the kept
        # set, its order, the model or the prefix must invalidate the cache — a count
        # match is not enough (would silently map embeddings to the wrong labels).
        sig = hashlib.sha1(("passage:" + _MODEL_NAME + "\n" + "\n".join(labels)).encode()).hexdigest()[:16]
        cache = _DESC_PATH.with_name(f"eurovoc_descriptors.{sig}.emb.npy")
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
        logger.info("EuroVoc sbert backend ready: %d descriptors", len(descs))
    except Exception as e:
        logger.warning("EuroVoc sbert backend unavailable: %s", type(e).__name__)
        _state["ok"] = False
    return _state["ok"]


# Confidence gate. Short proper-noun / acronym titles ("INSIDE Connect 2026", "Chips
# JU 6G") make the embedder grasp at fragments and emit garbage. The gate keeps a tag
# only when the cosine SPREAD over a fixed top-6 window clears _MIN_MARGIN.
#
# HONEST LIMIT (measured, not theory): e5 margins do NOT cleanly separate real-but-thin
# news from noise — a real funding headline ("...receives EUR 18m EU grant", span 0.012)
# scores a LOWER spread than gibberish ("xyzzy", 0.018), because proper nouns dilute the
# topical signal. So no threshold tags every real listing item without also admitting
# noise. The chosen point (0.018) reliably rejects the realistic adversarial input that
# actually reaches the classifier — proper-noun EVENT titles (INSIDE/2nd-EU-Japan, span
# <=0.013) — and keeps high-density topical text; it deliberately returns [] for
# proper-noun-heavy news rather than guess. For full, reliable tagging of those items
# use deep mode (?deep=true): the article BODY restores the topical signal. No tags
# beats wrong tags for a curated API. Tunable via EUROVOC_MIN_MARGIN.
#
# Two complementary signals over a fixed top-6 window, confident if EITHER fires:
#   - cluster: >= _MIN_CLUSTER of the top-6 share one microthesaurus (a coherent topic:
#     a funding story clusters in EU-finance, a standards story in technical regs). This
#     recovers real news headlines whose proper nouns flatten the margin (Joensuu grant,
#     Ukraine disbursement, EASA standards) — margin alone wrongly dropped them.
#   - margin: the top-6 cosine spread >= _MIN_MARGIN (a clean topical phrase with a sharp
#     peak: GDPR, AI transparency).
# Measured: real topics satisfy one (8/10), proper-noun-event noise satisfies neither
# (INSIDE / 2nd-EU-Japan / FIRST all dropped, 6/6). Plain "support >= 2" was too weak
# (noise shares a domain by chance); >= 4 is the discriminating cluster size.
_MIN_MARGIN = _env_num("EUROVOC_MIN_MARGIN", 0.024, float)
_MIN_CLUSTER = _env_num("EUROVOC_MIN_CLUSTER", 4, int)
_GATE_K = _env_num("EUROVOC_GATE_K", 6, int)  # fixed gate window; calibration anchor


def classify(text: str | None, lang: str = "en", top_k: int | None = None) -> list[dict]:
    """Return [{id, label, score, mt}] EuroVoc descriptors for the text, or [] when the
    match is not confident (or on any failure). lang is informational (multilingual)."""
    if not text or _BACKEND == "off":
        return []
    if _BACKEND != "sbert" or not _init_sbert():
        return []
    np = _state["np"]
    k = top_k or _DEFAULT_TOPK
    try:
        q = _state["model"].encode(["query: " + text[:2000]], normalize_embeddings=True)[0]
        scores = _state["emb"] @ q  # cosine (both normalized)
        order = np.argsort(-scores)[: max(k, _GATE_K)]
        raw = [(float(scores[int(i)]), _state["descs"][int(i)]) for i in order]
        if len(raw) < 2:
            return []
        # Confidence gate over the fixed top-_GATE_K window (stable regardless of k):
        # a tight microthesaurus cluster OR a sharp cosine margin.
        win = raw[:_GATE_K]
        gate_span = win[0][0] - win[-1][0]
        counts: dict = {}
        for _, d in win:
            mt = d.get("mt")
            if mt:
                counts[mt] = counts.get(mt, 0) + 1
        max_cluster = max(counts.values()) if counts else 0
        if max_cluster < _MIN_CLUSTER and gate_span < _MIN_MARGIN:
            return []
        out = [{"id": d["id"], "label": d["label"], "score": round(s, 4), "mt": d.get("mt")}
               for s, d in raw[:k] if s >= _MIN_SCORE]
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
