"""Five baseline questions carried no decisive token and were answered in the wrong language.

Measured on the 120-question baseline of 26 Sep 2026 (production /api/chat/stream):
two Italian questions were answered in Catalan, two Catalan ones in Spanish and one
in French. Each held only shared function words ("la", "del", "per"), so the tie
fell to declaration order. Replaying 1,154 real user queries through the old and
new tables changed 6 verdicts, all six correct.
"""
import pytest

from services.ai_service import (_CA_DECISIVE, _ES_DECISIVE, _FR_DECISIVE,
                                 _IT_DECISIVE, _LANG_MARKERS, _NL_DECISIVE,
                                 _detect_query_language)

CASES = [
    ("Quale soglia di temperatura si applica all'asta calore industriale del Fondo per l'innovazione?", "IT"),
    ("Qual è una buona ricetta per la paella?", "IT"),
    ("ok struttura l'email di presentazione del progetto", "IT"),
    ("Quant proposa la Comissió del Fons de Solidaritat de la UE per a Espanya el setembre de 2026?", "CA"),
    ("Què va resoldre el Tribunal de Justícia en l'assumpte C-900/24 sobre clàusules abusives?", "CA"),
    ("Qui va guanyar l'última final de la Champions League?", "CA"),
    # must NOT move
    ("¿Cuánto propone la Comisión del Fondo de Solidaridad para España en septiembre?", "ES"),
    ("Combien la Commission propose-t-elle du Fonds de solidarité pour l'Espagne en septembre ?", "FR"),
    ("How much does the Commission propose from the Solidarity Fund for Spain?", "EN"),
    ("Hoeveel stelt de Commissie voor uit het Solidariteitsfonds voor Spanje?", "NL"),
    ("La información sobre la aplicación del reglamento", "ES"),
]


@pytest.mark.parametrize("query,lang", CASES)
def test_detects(query, lang):
    assert _detect_query_language(query) == lang


NEW = {
    "CA": {"proposa", "comissio", "fons", "setembre", "espanya", "resoldre",
           "assumpte", "clausules", "guanyar", "solidaritat", "recepta"},
    "IT": {"quale", "soglia", "applica", "calore", "industriale", "ricetta",
           "buona", "settembre"},
}


@pytest.mark.parametrize("lang", ["CA", "IT"])
def test_new_tokens_are_exclusive(lang):
    others = {"CA": _CA_DECISIVE, "IT": _IT_DECISIVE, "ES": _ES_DECISIVE,
              "NL": _NL_DECISIVE, "FR": _FR_DECISIVE}
    for tok in NEW[lang]:
        for other, table in others.items():
            if other != lang:
                assert tok not in table, (tok, other)
        for other, markers in _LANG_MARKERS.items():
            if other != lang:
                assert tok not in markers, (tok, other)


def test_deep_dive_label_follows_the_question_language():
    from services.ai_service import _DEEP_DIVE_LABEL
    assert set(_DEEP_DIVE_LABEL) == {"EN", "ES", "CA", "FR", "IT", "NL"}
    assert _DEEP_DIVE_LABEL[_detect_query_language(
        "Quant va multar la Comissió a Alphabet en virtut de la Llei de mercats digitals?")].startswith("Llegiu")
