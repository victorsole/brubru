"""brubru: the official Python client for the Brubru EU Data API.

The whole EU institutional data estate behind one key: legislation, procedures,
institutions, the social directory, and the input-first extract engine, all on
the same five-datapoint contract.

    import brubru
    bru = brubru.Client(api_key="brubru_live_...")
    res = bru.extract("https://cinea.ec.europa.eu/news_en", classify=True)
    for post in bru.social.iter_posts(entity_type="commissioner", max_items=50):
        print(post.entity_name, post.public_url)
"""
from __future__ import annotations

from ._client import Client
from ._errors import (
    AuthError,
    BrubruError,
    NotFoundError,
    PaymentRequiredError,
    RateLimitError,
    ScopeError,
    ServerError,
    ValidationError,
)
from ._models import (
    ExtractedItem,
    ExtractResult,
    Item,
    Page,
    SocialAccount,
    SocialPlatform,
    SocialPost,
)

__version__ = "0.1.0"

__all__ = [
    "Client",
    "BrubruError", "AuthError", "PaymentRequiredError", "ScopeError",
    "NotFoundError", "ValidationError", "RateLimitError", "ServerError",
    "Item", "ExtractedItem", "ExtractResult", "Page",
    "SocialPost", "SocialAccount", "SocialPlatform",
    "__version__",
]
