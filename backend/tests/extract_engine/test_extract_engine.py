"""Offline regression tests for the EU extract engine.

Turns the pinned fixtures/*.html into a real safety net: parse() is asserted against
each fixture, the Item contract is checked on every produced item, and the Phase 0
config + the anti-hallucination/SSRF/date/junk guards are unit-tested. No network, no
model -> deterministic and CI-safe. Run:  pytest tests/extract_engine/test_extract_engine.py
"""
import json
import pathlib

import pytest

from services.extract import classifier, handlers
from services.extract.engine import _ERR_PAGE, _reg_domain
from services.extract.fetcher import _is_safe_url

_HERE = pathlib.Path(__file__).resolve().parent
_FIX = _HERE / "fixtures"
_CONFIG = json.loads((_HERE.parents[1] / "config" / "platform_profiles.json").read_text())

# Pinned baseline: fixture filename substring -> minimum item count parse() must yield
# from the SERVER html. JS-rendered listings (eismea, rail, chips publications, euipo)
# legitimately yield 0 from static html (they need a browser) -> baseline 0.
_BASELINE = {
    "cinea": 8, "hadea": 10, "eismea": 0, "clean_hydrogen": 1,        # ecl
    "echa": 6, "berec": 6, "easa": 8, "ema": 2, "eca": 6,             # drupal/sharepoint static
    "eur_lex": 5, "curia": 3,                                          # spa/jcms static
    "fusionforenergy": 3, "rail": 0,                                   # wordpress
    "chips_ju_europa_eu_events": 6, "chips_ju_europa_eu_publication": 0,  # dynamics
}


def _fixture_files():
    return sorted(f for f in _FIX.glob("*.html") if not f.name.startswith("rendered_"))


def _baseline_for(name: str):
    for key, n in _BASELINE.items():
        if key in name:
            return n
    return None


@pytest.mark.parametrize("fx", _fixture_files(), ids=lambda f: f.name[6:40])
def test_parse_meets_baseline_and_contract(fx):
    html = fx.read_text(errors="ignore")
    platform, _, body = classifier.classify("https://x.europa.eu/", html)
    items = handlers.parse(platform, html, f"https://{body or 'x'}.europa.eu/", item_type="news", limit=30)
    base = _baseline_for(fx.name)
    if base is not None:
        assert len(items) >= base, f"{fx.name}: {len(items)} items < baseline {base} (parse regressed?)"
    # Item contract on every produced item
    guids = []
    for it in items:
        assert it.title and it.title.strip(), f"{fx.name}: empty title"
        assert it.creation_date is not None, f"{fx.name}: creation_date must always be set"
        assert it.guid, f"{fx.name}: guid must be set (identity)"
        # public_url is best-effort: a REAL url or empty — never a non-http fake besides the synthetic guid anchor
        if it.public_url:
            assert it.public_url.startswith(("http://", "https://")), f"{fx.name}: non-http public_url {it.public_url!r}"
        guids.append(it.guid)
    assert len(guids) == len(set(guids)), f"{fx.name}: duplicate guids (dedup regressed)"


def test_no_junk_titles_leak_from_fixtures():
    """No fixture should yield a nav/CTA junk title as an item."""
    leaked = []
    for fx in _fixture_files():
        html = fx.read_text(errors="ignore")
        platform, _, body = classifier.classify("https://x.europa.eu/", html)
        for it in handlers.parse(platform, html, f"https://{body}.europa.eu/", item_type="news", limit=30):
            if handlers._is_junk_title(it.title):
                leaked.append((fx.name, it.title))
    assert not leaked, f"junk titles leaked: {leaked[:5]}"


# ---- Phase 0 config integrity ----------------------------------------------- #
def test_config_overrides_reference_real_platforms():
    profiles = _CONFIG["platform_profiles"]
    anti = _CONFIG["anti_bot_profiles"]
    for name, ov in _CONFIG["overrides"].items():
        assert ov.get("platform") in profiles, f"override {name}: bad platform {ov.get('platform')}"
    for p, prof in profiles.items():
        assert "anti_bot" in prof, f"profile {p}: missing anti_bot"
    for name, d in {**profiles, **_CONFIG["overrides"]}.items():
        ab = d.get("anti_bot")
        if ab:
            first = ab if isinstance(ab, str) else ab[0]
            assert first in anti, f"{name}: anti_bot {ab} not in anti_bot_profiles"


def test_config_selectors_no_drift():
    """The config's REFERENCE selectors for the server-rendered platforms must each
    appear in handlers.parse() source, so the documented taxonomy can't silently drift
    from the implementation (the config _doc promises this test keeps them in sync)."""
    src = (_HERE.parents[1] / "services" / "extract" / "handlers.py").read_text()
    profiles = _CONFIG["platform_profiles"]
    for plat in ("ecl", "drupal"):  # the requests-served platforms whose selectors are hardcoded
        for sel in profiles[plat].get("selectors", []):
            assert sel in src, f"config selector {sel!r} for {plat} not implemented in handlers.parse()"


def test_classifier_never_keyerrors_on_edge_urls():
    for u in ["not a url", "https://", "ftp://x", "https://webgate.ec.europa.eu/x",
              "https://www.acer.europa.eu/news", "https://random.example.com/"]:
        plat, anti, body = classifier.classify(u)
        assert plat in _CONFIG["platform_profiles"], f"{u} -> bad platform {plat}"


def test_www_prefix_strip_not_charset():
    # regression: lstrip('www.') mangled 'webgate' -> 'ebgate'
    _, _, body = classifier.classify("https://webgate.ec.europa.eu/x")
    assert body.startswith("webgate")


# ---- guards ------------------------------------------------------------------ #
@pytest.mark.parametrize("u", [
    "http://169.254.169.254/latest/meta-data/", "http://metadata.google.internal/",
    "http://localhost:8000/", "http://127.0.0.1/", "http://10.0.0.5/", "http://[::1]/",
    "file:///etc/passwd", "ftp://x/", "http://0.0.0.0/"])
def test_ssrf_blocks_internal(u):
    assert _is_safe_url(u) is False


@pytest.mark.parametrize("u", [
    "https://cinea.ec.europa.eu/news-events/news_en", "http://curia.europa.eu/site/jcms/d2_5157/en/news"])
def test_ssrf_allows_eu(u):
    assert _is_safe_url(u) is True


@pytest.mark.parametrize("txt", [
    "Page introuvable", "Seite nicht gefunden", "página no encontrada", "Pagina niet gevonden",
    "Pagina non trovata", "The page you requested could not be found", "404 not found"])
def test_error_page_detection(txt):
    assert _ERR_PAGE.search(txt)


@pytest.mark.parametrize("txt", [
    "EASA publishes new technical standards", "Common fisheries policy reform"])
def test_error_page_no_false_positive(txt):
    assert not _ERR_PAGE.search(txt)


def test_reg_domain_blocks_offsite_keeps_eu():
    assert _reg_domain("youtube.com") != _reg_domain("agriculture.ec.europa.eu")
    assert _reg_domain("www.eige.europa.eu") == _reg_domain("ec.europa.eu") == "europa.eu"


@pytest.mark.parametrize("s,expect", [
    ("24th June 2026", "2026-06-24"), ("24 June 2026", "2026-06-24"),
    ("June 24, 2026", "2026-06-24"), ("2026-06-24", "2026-06-24"),
    ("24/06/2026", "2026-06-24"), ("no date here", None)])
def test_date_parser(s, expect):
    d = handlers._parse_date_text(s)
    assert (d.strftime("%Y-%m-%d") if d else None) == expect


@pytest.mark.parametrize("t,junk", [
    ("Subscribe to F4E News", True), ("Newsletter", True), ("Registration", True),
    ("Bringing manufacturing back to Europe", False), ("Go to market strategy", False),
    ("Commission proposes new catch quotas", False)])
def test_junk_title_filter(t, junk):
    assert handlers._is_junk_title(t) is junk
