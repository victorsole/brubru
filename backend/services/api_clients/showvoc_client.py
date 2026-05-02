"""
ShowVoc deep-link client.

Phase 13 of docs/applications/euvoc.md. Brubru integrates with the public
ShowVoc instance (the Publications Office's vocabulary browser) by emitting
deep-link URLs for any authority concept we resolve. We do NOT host a
ShowVoc instance — pure outbound reference.

Reference:
    https://op.europa.eu/de/web/eu-vocabularies/showvoc

Public API:
    deep_link(uri)             -> str | None
    deep_link_for_eurovoc(id)  -> str
    deep_link_for_authority(uri)-> str | None

The public ShowVoc base URL is configurable via the SHOWVOC_BASE_URL env
var so we can flip to staging / a different instance without a code
change.
"""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import quote

DEFAULT_SHOWVOC_BASE = "https://showvoc.op.europa.eu"


def _base() -> str:
    return os.environ.get("SHOWVOC_BASE_URL", DEFAULT_SHOWVOC_BASE).rstrip("/")


def deep_link(uri: str) -> Optional[str]:
    """Return a ShowVoc URL pointing at the concept identified by `uri`.

    Returns None for non-recognised URIs. Recognises:
      - http://eurovoc.europa.eu/{id}
      - http://publications.europa.eu/resource/authority/{name}/{code}
    """
    if not uri:
        return None
    if uri.startswith("http://eurovoc.europa.eu/"):
        return deep_link_for_eurovoc(uri.rsplit("/", 1)[-1])
    if "/resource/authority/" in uri:
        return deep_link_for_authority(uri)
    return None


def deep_link_for_eurovoc(concept_id: str) -> str:
    """Deep-link to a EuroVoc concept on ShowVoc.

    Args:
        concept_id: numeric or string concept ID (e.g. "5460" for data protection).
    """
    cid = str(concept_id).strip()
    if cid.startswith("http"):
        cid = cid.rsplit("/", 1)[-1]
    return f"{_base()}/#/datasets/EuroVoc/data?resId={quote(f'http://eurovoc.europa.eu/{cid}', safe='')}"


def deep_link_for_authority(uri: str) -> Optional[str]:
    """Deep-link to an authority-table concept on ShowVoc.

    Args:
        uri: full URI starting with http://publications.europa.eu/resource/authority/...
    """
    if "/resource/authority/" not in uri:
        return None
    # ShowVoc names authority datasets after the NAL key (e.g.
    # "corporate-body" -> dataset name "Corporate Body" or similar). The
    # public instance exposes them with the NAL slug; we encode the URI
    # as the resId.
    return f"{_base()}/#/datasets/CommonAuthorityTables/data?resId={quote(uri, safe='')}"
