"""URL -> platform classifier (Phase 1, step 1.2).

Pre-fetch guess from the domain + the config overrides; an optional post-fetch
confirm from HTML signatures. Returns (platform_type, anti_bot, body_code).
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

_CONFIG = json.loads((Path(__file__).resolve().parents[2] / "config" / "platform_profiles.json").read_text())
_PROFILES = _CONFIG["platform_profiles"]
_OVERRIDES = _CONFIG["overrides"]

# Domains whose first label is not the body code.
_DOMAIN_BODY = {
    "fusionforenergy.europa.eu": "f4e", "rail-research.europa.eu": "rail",
    "smart-networks.europa.eu": "sns", "chips-ju.europa.eu": "chips",
    "curia.europa.eu": "cjeu", "clean-aviation.eu": "aviation",
}
# HTML signatures for post-fetch confirmation (first match wins).
_SIGNATURES = [
    (".ecl-content-item", "ecl"),
    (".group-content", "drupal"), (".views-row", "drupal"), (".teaser", "drupal"),
    ("article.node", "drupal"),
]


def _body_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    host = host[4:] if host.startswith("www.") else host  # NOT lstrip: "webgate"->"ebgate"
    if host in _DOMAIN_BODY:
        return _DOMAIN_BODY[host]
    # eur-lex.europa.eu -> eur-lex ; ema.europa.eu -> ema
    first = host.split(".")[0]
    return "eur-lex" if host.startswith("eur-lex") else first


def classify(url: str, html: str | None = None) -> tuple[str, object, str]:
    """Return (platform_type, anti_bot, body_code). anti_bot may be a str or list."""
    body = _body_of(url)
    host = urlparse(url).netloc.lower()
    if body in _OVERRIDES:
        ov = _OVERRIDES[body]
        platform = ov["platform"] if ov.get("platform") in _PROFILES else "drupal"
        anti_bot = ov.get("anti_bot") or _PROFILES[platform]["anti_bot"]
        return platform, anti_bot, body
    # post-fetch HTML signature confirmation
    if html:
        for sel, plat in _SIGNATURES:
            if (sel.lstrip(".") in html or sel in html) and plat in _PROFILES:
                return plat, _PROFILES[plat]["anti_bot"], body
    # domain heuristic: *.ec.europa.eu = ECL (DG / executive agency); else agency Drupal
    platform = "ecl" if host.endswith(".ec.europa.eu") else "drupal"
    return platform, _PROFILES[platform]["anti_bot"], body

