"""Two probes of 13 Oct 2026 were answered in the wrong language.

"Que es el repositori europeu de publicitat politica llancat el 12 d'octubre?" (Catalan) scored
ES, and "Quanto costa l'EUSM Lebanon e dove opera?" (Italian) scored EN, then FR once "l'EUSM"
became "la missione EUSM". Neither held a single decisive token; the new ones differ in all
five other Brubru languages after accent folding.
"""
import pytest

from services.ai_service import (_CA_DECISIVE, _ES_DECISIVE, _FR_DECISIVE,
                                 _IT_DECISIVE, _LANG_MARKERS, _NL_DECISIVE,
                                 _detect_query_language)

CASES = [
    ("Què és el repositori europeu de publicitat política llançat el 12 d'octubre?", "CA"),
    ("Quanto costa l'EUSM Lebanon e dove opera?", "IT"),
    ("Quanto costa la missione EUSM Lebanon e dove opera?", "IT"),
    # must NOT move
    ("¿Qué es el repositorio europeo de publicidad política lanzado el 12 de octubre?", "ES"),
    ("Qu'est-ce que le répertoire européen de la publicité politique lancé le 12 octobre ?", "FR"),
    ("Wat is de Europese databank voor politieke advertenties die op 12 oktober is gelanceerd?", "NL"),
    ("What is the European Repository for political advertising launched on 12 October?", "EN"),
    ("¿Cuánto cuesta la misión EUSM Lebanon y dónde opera?", "ES"),
    ("Combien coûte la mission EUSM Lebanon et où opère-t-elle ?", "FR"),
    ("Quant costa la missió EUSM Lebanon i on opera?", "CA"),
    ("How much does the EUSM Lebanon mission cost and where does it operate?", "EN"),
]


@pytest.mark.parametrize("query,lang", CASES)
def test_detects(query, lang):
    assert _detect_query_language(query) == lang


NEW = {
    "CA": {"repositori", "publicitat", "europeu", "europeus", "llancat", "llancada", "missio"},
    "IT": {"quanto", "quanta", "quanti", "quante", "dove", "missione", "missioni"},
}


@pytest.mark.parametrize("lang", ["CA", "IT"])
def test_new_tokens_are_exclusive(lang):
    others = {"CA": _CA_DECISIVE, "IT": _IT_DECISIVE, "ES": _ES_DECISIVE,
              "NL": _NL_DECISIVE, "FR": _FR_DECISIVE}
    for tok in NEW[lang]:
        assert tok in others[lang], tok
        for other, table in others.items():
            if other != lang:
                assert tok not in table, (tok, other)
        for other, markers in _LANG_MARKERS.items():
            if other != lang:
                assert tok not in markers, (tok, other)
