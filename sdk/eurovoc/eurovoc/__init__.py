"""eurovoc: a standalone, open-source EuroVoc classifier.

Tags any text into the EU's official subject space: 7,029 descriptors (IDs)
rolled up to 127 microthesauri (MT) and 21 domains (DO), multilingual including
Catalan. A modern, open successor to the 2021 PyEuroVoc package (which truncated
documents to 512 tokens and no longer loads under transformers 5.x), and the
natural home for a retrained long-context model.

    import eurovoc
    for d in eurovoc.classify("Markets in crypto-assets regulation"):
        print(d.label, d.domain_label, round(d.score, 3))

Interop with the Brubru API / the brubru SDK:
    # enrich the raw descriptors an extract item already carries
    tags = eurovoc.from_descriptors(item["eurovoc_descriptors"])
    # or classify a live EU URL through Brubru's hosted engine
    tags = eurovoc.classify_url("https://cinea.ec.europa.eu/news_en", api_key="brubru_live_...")
"""
from __future__ import annotations

from typing import List, Optional

from ._enrich import DOMAINS, Descriptor, from_descriptors
from ._local import classify_local

__version__ = "0.1.0"

__all__ = ["classify", "classify_url", "from_descriptors", "Descriptor", "DOMAINS", "__version__"]


def classify(text: str, lang: str = "en", top_k: Optional[int] = None) -> List[Descriptor]:
    """Classify text locally into EuroVoc descriptors (domain-enriched, scored).

    Returns [] when no confident match (the gate prefers no tags over wrong tags).
    Needs ``sentence-transformers`` (``pip install 'eurovoc[local]'``); the model
    and the label-embedding matrix are downloaded/computed once and cached.
    """
    return from_descriptors(classify_local(text, lang=lang, top_k=top_k))


def classify_url(url: str, *, api_key: str, base_url: Optional[str] = None,
                 item_type: str = "news", limit: int = 30) -> List[Descriptor]:
    """Classify a live EU URL through Brubru's hosted extract engine and return
    the de-duplicated, domain-enriched descriptors across the page's items.

    Needs the ``brubru`` SDK (``pip install 'eurovoc[brubru]'``) and an API key.
    This is the hosted alternative to local ``classify`` for whole pages.
    """
    try:
        import brubru
    except ImportError as e:  # pragma: no cover - import guard
        raise RuntimeError("classify_url needs the brubru SDK: pip install 'eurovoc[brubru]'") from e
    client = brubru.Client(api_key, base_url=base_url) if base_url else brubru.Client(api_key)
    try:
        res = client.extract(url, item_type=item_type, limit=limit, classify=True)
    finally:
        client.close()
    seen, merged = set(), []
    for item in res.items:
        for raw in item.eurovoc_descriptors:
            key = str(raw.get("id"))
            if key not in seen:
                seen.add(key)
                merged.append(raw)
    return from_descriptors(merged)
