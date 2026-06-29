# eurovoc

A standalone, open-source **EuroVoc classifier**. It tags any text into the EU's official subject space: 7,029 descriptors (IDs) rolled up to 127 microthesauri (MT) and 21 domains (DO), multilingual including Catalan.

A modern, open successor to the 2021 [PyEuroVoc](https://github.com/racai-ai/pyeurovoc) package (which fine-tuned a per-language BERT, truncated documents to 512 tokens, and no longer loads under transformers 5.x), and the natural home for a retrained long-context model.

## How it works

Default backend is zero-shot retrieval: a multilingual sentence-transformers model (`intfloat/multilingual-e5-base`) embeds the text and the EuroVoc descriptor labels (cached once), and returns the top-K by cosine behind a confidence gate. The gate prefers returning nothing over wrong tags, so proper-noun-heavy or off-topic text yields `[]`. This is a port of Brubru's production classifier, not a trained multi-label model.

## Install

Until the package is published to PyPI, install from source:

```bash
pip install './sdk/eurovoc[local]'      # [local] pulls sentence-transformers
```

`eurovoc` itself only needs `numpy`; the `[local]` extra adds the model. The first `classify()` downloads the model (~1 GB) and computes the label-embedding matrix once, caching it under `~/.cache/eurovoc/`.

## Usage

```python
import eurovoc

for d in eurovoc.classify("Markets in crypto-assets regulation"):
    print(d.label, "|", d.domain, d.domain_label, "|", round(d.score, 3))
# financial instrument | 24 FINANCE | 0.88 ...

eurovoc.classify("Regulació de la protecció de dades personals")  # multilingual
eurovoc.classify("xyzzy plugh")   # -> []  (gate rejects noise)
```

Each result is a `Descriptor(id, label, score, mt, domain, domain_label)`. The 21 domains are in `eurovoc.DOMAINS`.

## Interop with the Brubru API

Enrich the raw descriptors the API (or the [`brubru`](../brubru) SDK) returns:

```python
import eurovoc
tags = eurovoc.from_descriptors(extract_item["eurovoc_descriptors"])
```

Or classify a live EU URL through Brubru's hosted extract engine (needs the `brubru` SDK and a key):

```bash
pip install 'eurovoc[brubru]'
```

```python
tags = eurovoc.classify_url("https://environment.ec.europa.eu/news_en", api_key="brubru_live_...")
```

## Configuration (env vars)

`EUROVOC_ST_MODEL`, `EUROVOC_TOPK`, `EUROVOC_MIN_SCORE`, `EUROVOC_MIN_MARGIN`, `EUROVOC_MIN_CLUSTER`, `EUROVOC_CACHE_DIR`.

## Tests

```bash
pip install -e '.[test,local]'
pytest -m "not model"     # fast: enrichment, pruning, packaging (no model)
pytest -m model           # loads the model and classifies real text
```

MIT licensed. Built by Beresol BV. EuroVoc is a trademark of the Publications Office of the European Union.
