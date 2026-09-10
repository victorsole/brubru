"""A Catalan act page must contain the act, not the EUR-Lex website.

INCIDENT, 10 September 2026
---------------------------
52 pages were generated for the day's Official Journal and 44 reached the live
site. NONE contained the act. 49 were the EUR-Lex website itself -- the cookie
notice, the language picker, "Inicia la sessio", a paragraph about EUR-Lex's
experimental features -- translated into Catalan and published under the banner
"Aquesta traduccio ha estat preparada per Brubru amb models d'intelligencia
artificial". The other 3 were correct-titled empty shells.

Two failures, and the second is the one this file exists for:

  * The pipeline ALREADY KNEW. `_eurlex_fallback` logs
    "Article=False (WAF challenge or empty)" when the fetched page has no
    article structure. The run logged exactly that, three times, and then
    printed "[OK] registered".
  * The verification that cleared it measured FILE SIZE ("no file under 6KB")
    and character count. A chrome page is ~15KB and 4,385 visible characters, so
    it sails through. Size can never distinguish an act from a cookie banner.

The gate reads the BODY. These tests use fixtures shaped like what actually
shipped, so the regression cannot come back quietly.
"""
import importlib.util
import pathlib
import sys

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "backend" / "scripts" / "translate_oj_daily_acts.py"
if str(_REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "backend"))

_spec = importlib.util.spec_from_file_location("_oj_daily", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
page_has_act_text = _mod._page_has_act_text


def _page(paragraphs) -> str:
    body = "\n".join(f'<p class="article-text">{p}</p>' for p in paragraphs)
    return f"<html><head><title>x | Brubru</title></head><body>{body}</body></html>"


def _write(tmp_path, paragraphs):
    f = tmp_path / "index.html"
    f.write_text(_page(paragraphs), encoding="utf-8")
    return f


# What actually shipped on 10 September: EUR-Lex furniture, in Catalan.
CHROME_PAGE = [
    "Totes les adreces web oficials de la Unió Europea estan en el domini europa.eu.",
    "Consulteu totes les institucions i òrgans de la UE",
    "Utilitzem cookies al nostre lloc web per oferir-vos l'experiència més rellevant recordant "
    "les vostres preferències i visites repetides.",
    "El meu EUR-Lex", "Inicia la sessió", "Registra", "Les meves cerques recents (0)",
    "bg български", "es Español", "cs Čeština", "EUR-Lex home", "Ajuda", "Imprimeix",
    "Voleu ajudar a millorar EUR-Lex ? Aquesta és una llista de característiques experimentals "
    "que podeu habilitar. Aquestes característiques encara estan en desenvolupament; no estan "
    "completament provades i podrien reduir l'estabilitat EUR-Lex.",
]

REAL_ACT = [
    "Vist el Tractat de Funcionament de la Unió Europea, i en particular l'article 114, " * 4,
    "Considerant que és necessari establir un marc harmonitzat que garanteixi el bon "
    "funcionament del mercat interior en aquest àmbit concret. " * 4,
    "Article 1. Objecte i àmbit d'aplicació. El present Reglament estableix les normes "
    "aplicables als operadors econòmics establerts a la Unió. " * 4,
    "Article 2. Definicions. A l'efecte del present Reglament s'entendrà per operador "
    "econòmic qualsevol persona física o jurídica. " * 4,
]


def test_rejects_the_eurlex_chrome_page_that_shipped(tmp_path):
    ok, why = page_has_act_text(_write(tmp_path, CHROME_PAGE))
    assert ok is False
    assert "chrome" in why.lower()


def test_rejects_an_empty_shell(tmp_path):
    """The other 3 of the 52: correct title, no body at all."""
    ok, why = page_has_act_text(_write(tmp_path, []))
    assert ok is False
    assert "thin" in why.lower()


def test_rejects_a_page_that_is_LARGE_but_has_no_act(tmp_path):
    """Size is not content. This fixture is far bigger than the 6KB threshold
    the original verification used, and must still be rejected."""
    # 20KB of furniture: the real chrome pages were ~15KB.
    big = CHROME_PAGE + ["Navegació " * 400] * 5
    f = _write(tmp_path, big)
    assert f.stat().st_size > 6000, "fixture must exceed the size threshold to be meaningful"
    ok, _ = page_has_act_text(f)
    assert ok is False


def test_accepts_a_real_act(tmp_path):
    ok, why = page_has_act_text(_write(tmp_path, REAL_ACT))
    assert ok is True, why


def test_accepts_a_real_act_on_disk_if_present():
    """The GDPR page from the acquis dump, if this checkout has it."""
    p = _REPO_ROOT / "data" / "legislacio-ue-catala" / "32016R0679" / "index.html"
    if not p.exists():
        pytest.skip("acquis corpus not present in this checkout")
    ok, why = page_has_act_text(p)
    assert ok is True, why


def test_missing_file_is_rejected_not_crashed(tmp_path):
    ok, why = page_has_act_text(tmp_path / "nope.html")
    assert ok is False and "unreadable" in why
