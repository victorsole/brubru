"""
Stance extraction for consultation feedback (Tier-1 positions layer).

Given an organisation's Have-Your-Say feedback text, classify its STATED position
(support / oppose / amend / mixed / unclear) and, where possible, a one-line grounded
summary. All open-source / non-Anthropic. Three providers, tried in order:

  1. Qwen direct API (when QWEN_API_KEY is set) - OpenAI-compatible, e.g. Alibaba
     Model Studio / DashScope. Gives stance + grounded summary.
  2. HF Inference router (Qwen) - same, subject to HF credits.
  3. LOCAL zero-shot classifier (multilingual mDeBERTa-xnli) - free, offline, no
     credits. Gives stance only (no generated summary; the UI shows the source excerpt).

Grounded only: the LLM prompts forbid inventing positions; the local model is pure
classification. On total failure we return "pending" so it can be retried later.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Dict, Optional

import httpx

from services.ai.huggingface_service import get_huggingface_service

logger = logging.getLogger(__name__)

HF_MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507:featherless-ai"
# Qwen-direct (set QWEN_API_KEY to enable). Defaults to Alibaba Model Studio intl.
QWEN_BASE_URL = os.environ.get("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL = os.environ.get("QWEN_MODEL", "qwen-plus")
# Local instruct LLM (Apache-2.0, run offline via transformers; stance + grounded summary).
LOCAL_LLM_MODEL = os.environ.get("LOCAL_LLM_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
# Local multilingual zero-shot NLI model (MIT; stance only). Lighter fallback.
LOCAL_MODEL = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"

VALID = {"support", "oppose", "amend", "mixed", "unclear"}

_SYSTEM = (
    "You classify an organisation's stated position on an EU legislative consultation, "
    "using ONLY the feedback text provided. Never infer a position that is not stated. "
    "Output strict JSON: {\"stance\": one of support|oppose|amend|mixed|unclear, "
    "\"summary\": a single factual sentence (max 30 words) describing what the organisation "
    "asks for, grounded in the text}. If no clear position is stated, use \"unclear\". "
    "Do not add caveats or invented detail."
)

# Zero-shot hypotheses (multi_label=True -> independent scores). Decision logic below
# checks oppose/amend BEFORE support, because consultation boilerplate ("we welcome the
# opportunity, we support the objective, however...") otherwise inflates "support".
_ZS = {
    "oppose": "This organisation opposes or rejects the proposal.",
    "amend": "This organisation asks for amendments, changes, exemptions or stronger safeguards.",
    "support": "This organisation fully supports the proposal as drafted.",
}

_zs_pipeline = None     # lazy local zero-shot pipeline singleton
_llm = None             # lazy local instruct LLM singleton: (tokenizer, model, device) or False


def _parse_llm(out: Optional[str]) -> Optional[Dict]:
    if not out:
        return None
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except Exception:
        return None
    stance = str(d.get("stance", "")).lower().strip()
    if stance not in VALID:
        return None
    summary = d.get("summary")
    summary = summary.strip()[:300] if isinstance(summary, str) and summary.strip() else None
    return {"stance": stance, "summary": summary}


def _build_user(feedback_text: str, organisation: str, title: Optional[str]) -> str:
    return (
        f"Organisation: {organisation}\n"
        f"Consultation: {title or '(unknown)'}\n"
        f"Feedback text:\n\"\"\"\n{feedback_text[:4000]}\n\"\"\"\n\nReturn the JSON now."
    )


async def _qwen_direct(feedback_text: str, organisation: str, title: Optional[str]) -> Optional[Dict]:
    key = os.environ.get("QWEN_API_KEY")
    if not key:
        return None
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{QWEN_BASE_URL.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": QWEN_MODEL,
                    "messages": [{"role": "system", "content": _SYSTEM},
                                 {"role": "user", "content": _build_user(feedback_text, organisation, title)}],
                    "max_tokens": 200, "temperature": 0.1,
                },
            )
        if r.status_code != 200:
            logger.info("[stance] qwen-direct HTTP %s: %s", r.status_code, r.text[:160])
            return None
        return _parse_llm(r.json()["choices"][0]["message"]["content"])
    except Exception as e:
        logger.warning("[stance] qwen-direct failed: %s", e)
        return None


async def _hf_router(feedback_text: str, organisation: str, title: Optional[str]) -> Optional[Dict]:
    if os.environ.get("SKIP_HF_STANCE") == "1":   # skip when HF credits are known-depleted
        return None
    try:
        hf = get_huggingface_service()
        out = await hf.chat_completion(
            model=HF_MODEL,
            messages=[{"role": "system", "content": _SYSTEM},
                      {"role": "user", "content": _build_user(feedback_text, organisation, title)}],
            max_tokens=200, temperature=0.1,
        )
        return _parse_llm(out)
    except Exception as e:
        logger.warning("[stance] HF router failed: %s", e)
        return None


def _load_local_llm():
    """Lazy-load the local instruct LLM (Apache-2.0). Returns (tok, model, device) or False."""
    global _llm
    if _llm is not None:
        return _llm
    if os.environ.get("DISABLE_LOCAL_LLM") == "1":
        _llm = False
        return _llm
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        dtype = torch.float16 if device in ("mps", "cuda") else torch.float32
        token = os.environ.get("HUGGINGFACE_API_KEY")
        logger.info("[stance] loading local LLM %s on %s (first run downloads it)", LOCAL_LLM_MODEL, device)
        tok = AutoTokenizer.from_pretrained(LOCAL_LLM_MODEL, token=token)
        model = AutoModelForCausalLM.from_pretrained(
            LOCAL_LLM_MODEL, token=token, torch_dtype=dtype, low_cpu_mem_usage=True)
        model.to(device)
        _llm = (tok, model, device)
    except Exception as e:
        logger.warning("[stance] local LLM load failed (%s) - falling back to zero-shot", str(e)[:160])
        _llm = False
    return _llm


def _local_llm(feedback_text: str, organisation: str, title: Optional[str]) -> Optional[Dict]:
    """Free, offline instruct LLM -> stance + grounded summary."""
    llm = _load_local_llm()
    if not llm:
        return None
    try:
        import torch
        tok, model, device = llm
        prompt = tok.apply_chat_template(
            [{"role": "user", "content": _SYSTEM + "\n\n" + _build_user(feedback_text, organisation, title)}],
            tokenize=False, add_generation_prompt=True)
        inputs = tok(prompt, return_tensors="pt", truncation=True, max_length=4096).to(device)
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=200, do_sample=False,
                                 pad_token_id=tok.eos_token_id)
        text = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        return _parse_llm(text)
    except Exception as e:
        logger.warning("[stance] local LLM gen failed: %s", str(e)[:120])
        return None


def _local_stance(feedback_text: str) -> Optional[Dict]:
    """Free, offline multilingual zero-shot classification (stance only). Checks
    oppose/amend before support to counter the boilerplate support-skew."""
    global _zs_pipeline
    try:
        if _zs_pipeline is None:
            from transformers import pipeline
            logger.info("[stance] loading local zero-shot model %s (first run downloads it)", LOCAL_MODEL)
            _zs_pipeline = pipeline("zero-shot-classification", model=LOCAL_MODEL)
        res = _zs_pipeline(feedback_text[:1500], list(_ZS.values()), multi_label=True)
        score = {lbl: sc for lbl, sc in zip(res["labels"], res["scores"])}
        s = {k: score.get(_ZS[k], 0.0) for k in _ZS}
        if s["oppose"] >= 0.55 and s["oppose"] >= s["amend"]:
            stance = "oppose"
        elif s["amend"] >= 0.5:
            stance = "amend"
        elif s["support"] >= 0.65:
            stance = "support"
        elif s["support"] >= 0.4 and s["amend"] >= 0.4:
            stance = "mixed"
        else:
            stance = "unclear"
        return {"stance": stance, "summary": None}
    except Exception as e:
        logger.warning("[stance] local zero-shot failed: %s", e)
        return None


async def extract_stance(feedback_text: str, organisation: str, consultation_title: Optional[str] = None) -> Dict:
    """Return {stance, summary}. ('attachment_only', None) when there is no text;
    'pending' when every provider failed (so it can be retried later)."""
    text = (feedback_text or "").strip()
    if not text:
        return {"stance": "attachment_only", "summary": None}

    # Hosted LLMs first (only if keys/credits) for stance + grounded summary.
    for provider in (_qwen_direct, _hf_router):
        res = await provider(text, organisation, consultation_title)
        if res:
            return res
    # Local instruct LLM (free, offline) - stance + grounded summary.
    res = _local_llm(text, organisation, consultation_title)
    if res:
        return res
    # Lighter local zero-shot (free, offline) - stance only.
    res = _local_stance(text)
    if res:
        return res
    return {"stance": "pending", "summary": None}
