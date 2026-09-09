"""The Softcatala character guard, and the two ways it failed in production.

1. The guard was a hand-typed ALLOW-LIST (34 symbols + 13 diacritics). Measured
   against the model on 9 September 2026, it can emit only 26 non-ASCII
   characters and destroys the other ~208 probed. The list missed roughly 200,
   including Romanian and Polish letters, so the PGI name
   "Branza framantata de Teaca" shipped corrupted.

2. The My OJ path then did `out.replace('⁇', '·')`, laundering the
   unknown marker into a Catalan interpunct. That made destroyed text look like
   ordinary punctuation and made a search for the marker return zero.

Run: cd backend && python -m pytest tests/test_softcatala_character_guard.py -v
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

import pytest

_BACKEND = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "catalan_translate_mod", _BACKEND / "scripts" / "catalan_translate.py")
ct = importlib.util.module_from_spec(_spec)
sys.modules["catalan_translate_mod"] = ct
_spec.loader.exec_module(ct)

MARKER = "⁇"
# A legitimate Catalan interpunct is ALWAYS between two l's (Brussel·les).
BAD_INTERPUNCT = re.compile(r"(?<![lL])·|·(?![lL])")


def _echo(text: str) -> str:
    """Stand in for the model: it can only emit what the model can emit.

    Anything outside the measured repertoire becomes the unknown marker, which
    is exactly what the real model does. No model download, no network.
    """
    return "".join(c if c in ct._SC_EMITTABLE else MARKER for c in text)


class TestCharacterGuard:
    @pytest.mark.parametrize("name,text", [
        ("Romanian PGI", "the geographical indication Brânză frământată de Teaca"),
        ("Polish PGI", "the geographical indication Kiełbasa pradziada z Dukli"),
        ("Polish apples", "the geographical indication Jabłka krajeńskie"),
        ("Spanish acute", "the illicit tráfico of firearms"),
        ("German umlaut", "signed by Wölken and Müller"),
        ("Slovak court", "Sociálna poisťovňa pension case"),
        ("Portuguese", "Gestão de Produção de Energia"),
        ("Hungarian/Czech", "rapporteurs Győri, Dvořák and Kučera"),
        ("botanical hybrid", "peppermint tincture from Mentha × piperita L."),
        ("paper size", "maximum format A4 (210 × 297 mm)"),
        ("euro and tolerance", "a tolerance of ±2 % and a budget of €1.5 billion"),
    ])
    def test_no_character_is_destroyed(self, name, text):
        out = ct._sc_protected(text, _echo)
        assert MARKER not in out, f"{name}: marker leaked -> {out!r}"

    def test_the_exact_production_failure(self):
        src = "Registration of the geographical indication Brânză frământată de Teaca (PGI)"
        out = ct._sc_protected(src, _echo)
        assert "Brânză frământată de Teaca" in out
        assert MARKER not in out

    def test_urls_survive_intact(self):
        url = "https://brubru.beresol.eu/legislacio-ue-catala/32026R2017/"
        out = ct._sc_protected(f"See {url} for the act", _echo)
        assert url in out

    def test_plain_ascii_is_left_for_the_model(self):
        # Nothing to protect: the text must reach the translator whole, so the
        # echo returns it unchanged rather than a string of placeholders.
        src = "The Commission adopted the implementing regulation"
        assert ct._sc_protected(src, _echo) == src

    def test_catalan_output_characters_are_emittable(self):
        # Everything Catalan actually needs must be inside the repertoire, or the
        # guard would protect ordinary Catalan words and leave them in English.
        for ch in "àçèéíïòóúü·":
            assert ch in ct._SC_EMITTABLE, f"Catalan character {ch!r} treated as unemittable"

    def test_the_repertoire_is_small_and_measured(self):
        non_ascii = {c for c in ct._SC_EMITTABLE if ord(c) > 127}
        assert len(non_ascii) <= 30, "the repertoire grew: re-measure against the model"
        assert "ñ" not in non_ascii, "n-tilde is destroyed by the model; it must be protected"
        assert "á" not in non_ascii, "a-acute is destroyed by the model; it must be protected"


class TestNoLaundering:
    def test_the_marker_is_never_swapped_for_an_interpunct(self):
        """The My OJ backfill must not disguise damage as Catalan punctuation."""
        src = (_BACKEND / "scripts" / "backfill_oj_translations.py").read_text()
        assert f"replace('{MARKER}', '·')" not in src
        assert f'replace("{MARKER}", "·")' not in src

    def test_the_oj_path_applies_the_character_guard(self):
        src = (_BACKEND / "scripts" / "backfill_oj_translations.py").read_text()
        assert "_sc_protected" in src, "the My OJ path must use the character guard"

    def test_detector_accepts_legitimate_catalan(self):
        for good in ("Brussel·les", "sol·licitud", "il·lícit", "intel·ligència"):
            assert not BAD_INTERPUNCT.search(good), f"{good} wrongly flagged"

    def test_detector_catches_the_laundered_damage(self):
        for bad in ("H · ldermann", "Soci · lna pois · ov · a", "Br·nz·"):
            assert BAD_INTERPUNCT.search(bad), f"{bad} not detected"
