"""A news item's URL must be one a reader can open.

The EEA's RSS feed spent three months publishing its internal load-balancer address in
<link>: `http://10.140.139.135:3000/en/newsroom/news/...`, and a different IP on each run.
Two things followed, and neither raised anything (found 25 September 2026):

  * every `public_url` we served for EEA news pointed at a private address that resolves
    for nobody outside their network, and
  * identity is per URL, so the same article arrived as a new row on every run. 534 EEA
    rows held 60 articles, 19 copies of some.

The de-duplication guard in `same_story.py` (15 September) now catches the second, since
the title and date are stable. This catches the first, and it catches it at the door: an
address on a private range is not a public URL, whatever the feed says.

Deliberately narrow. It rewrites the host to the publisher's public host when we know it,
and otherwise leaves the URL alone and says so, because a URL we cannot make public is a
fact worth surfacing rather than quietly dropping.
"""
from __future__ import annotations

import re
from typing import Optional

# RFC1918 and loopback. A feed emitting one of these is describing its own network.
_PRIVATE_HOST = re.compile(
    r"^https?://(?:10\.|127\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)[^/]*", re.I)

# Publishers known to leak their internal address, and the host they actually serve on.
_PUBLIC_HOST = {
    "EEA": "https://www.eea.europa.eu",
}


def is_private(url: Optional[str]) -> bool:
    return bool(url) and bool(_PRIVATE_HOST.match(url))


def canonical_public_url(url: Optional[str], institution: Optional[str] = None) -> Optional[str]:
    """The URL a reader can open, or the original when we cannot say.

    Keeps the path and restores the publisher's real host. Returns the input unchanged
    when it is already public, or when the institution is not one we have a host for.
    """
    if not is_private(url):
        return url
    host = _PUBLIC_HOST.get((institution or "").upper())
    if not host:
        return url
    return _PRIVATE_HOST.sub(host, url, count=1)
