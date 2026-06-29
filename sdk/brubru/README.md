# brubru

The official Python client for the **Brubru EU Data API**: the whole EU institutional data estate behind one key. Legislation, procedures, institutions, the social directory and the input-first extract engine, all on the same five-datapoint contract.

## Install

Until the package is published to PyPI, install from source:

```bash
pip install ./sdk/brubru          # from a checkout of the Brubru repo
# or from a built wheel:
pip install brubru-0.1.0-py3-none-any.whl
```

Only dependency: `requests`.

## Quickstart

```python
import brubru

bru = brubru.Client(api_key="brubru_live_...")

# Extract structured items from any EU institutional URL (optionally EuroVoc-tagged)
res = bru.extract("https://cinea.ec.europa.eu/news-events/news_en", classify=True)
for item in res:
    print(item.document_date, item.title, item.public_url)

# The social directory: recent posts from a mapped entity
page = bru.social.posts(entity_type="commissioner", platform="x", limit=20)
for post in page:
    print(post.entity_name, post.public_url)

# Stream across all pages, capped
for post in bru.social.iter_posts(entity_type="mep", max_items=200):
    ...
```

## Authentication

Your key is sent as the `X-API-Key` header. Get one on the Professional subscription (`hello@beresol.eu`).

## Base URL

The client defaults to the API host (`brubru-production.up.railway.app`). The brand domain `brubru.beresol.eu` serves the website and the static docs, not the API, so do not point the client there. Override `base_url=` once a dedicated API domain is in place.

## Errors

Every non-2xx response raises a typed exception, all subclasses of `brubru.BrubruError`:

| Status | Exception |
| --- | --- |
| 401 | `AuthError` |
| 402 | `PaymentRequiredError` |
| 403 | `ScopeError` |
| 404 | `NotFoundError` |
| 422 | `ValidationError` |
| 429 | `RateLimitError` |
| 5xx | `ServerError` |

Each carries `.status` and `.payload`.

## The five datapoints

Every list/detail item exposes `public_url`, `body_txt`, `body_html`, `document_date`, `creation_date` (plus `title`/`summary`). On list calls `body_txt`/`body_html` are `None`; fetch the detail (`bru.social.post(id)`) for the full body. The original JSON is always on `item.raw`.

## EuroVoc

To turn the `eurovoc_descriptors` an extract item carries into typed, domain-enriched objects, use the companion [`eurovoc`](../eurovoc) package: `eurovoc.from_descriptors(item.eurovoc_descriptors)`.

## Tests

```bash
pip install -e '.[test]'
pytest -m "not live"                         # offline, no network
BRUBRU_API_KEY=brubru_live_... pytest -m live  # hits production read-only
```

MIT licensed. Built by Beresol BV.
