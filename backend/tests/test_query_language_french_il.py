"""The French pronoun "il" must not hand a French question to Italian (24 Sep 2026).

"Quelle majorite faut-il au Conseil pour suspendre le volet commercial de
l'accord d'association UE-Israel ?" was answered in Italian twice in
production: "il" is in _IT_DECISIVE, the decisive pass runs before the
bag-of-words scorer, and French had no decisive table to answer back.
"""
import pytest

from services.ai_service import _FR_DECISIVE, _CA_DECISIVE, _ES_DECISIVE, \
    _IT_DECISIVE, _NL_DECISIVE, _LANG_MARKERS, _detect_query_language


FRENCH = [
    "Quelle majorité faut-il au Conseil pour suspendre le volet commercial de l'accord d'association UE-Israël ?",
    "Faut-il une majorité qualifiée ?",
    "Existe-t-il une obligation de notification sous le RGPD ?",
    "Y a-t-il un délai pour transposer la directive NIS2 ?",
    "Doit-il respecter le règlement sur l'IA ?",
    "Le Conseil a-t-il adopté sa position sur la réserve de stabilité du marché ?",
    "Quand la Commission a-t-elle proposé le Customs Code ?",
    "Il faut savoir si le Parlement a voté.",
    "Qu'est-ce que le règlement sur l'IA ?",
]

ITALIAN = [
    "Il Consiglio ha adottato la posizione?",
    "Qual è il ruolo del Parlamento europeo?",
    "Cos'è il regolamento sull'IA?",
    "Quando entra in vigore il nuovo codice doganale?",
    "Il regolamento si applica alle PMI?",
    "Quale maggioranza serve al Consiglio per sospendere le disposizioni commerciali dell'accordo di associazione UE-Israele?",
    "Mi spieghi il Chips Act?",
]

OTHERS = [
    ("ES", "¿Qué mayoría necesita el Consejo para suspender la parte comercial del Acuerdo de Asociación UE-Israel?"),
    ("CA", "Quina majoria necessita el Consell per suspendre les disposicions comercials de l'Acord d'Associació UE-Israel?"),
    ("NL", "Welke meerderheid heeft de Raad nodig om de handelsbepalingen op te schorten?"),
    ("EN", "What voting rule does the Council need to suspend the trade provisions?"),
    ("EN", "Is IL a member of the EEA?"),
]


@pytest.mark.parametrize("q", FRENCH)
def test_french_with_il_is_french(q):
    assert _detect_query_language(q) == "FR"


@pytest.mark.parametrize("q", ITALIAN)
def test_italian_with_il_stays_italian(q):
    assert _detect_query_language(q) == "IT"


@pytest.mark.parametrize("lang,q", OTHERS)
def test_other_languages_unchanged(lang, q):
    assert _detect_query_language(q) == lang


def test_fr_decisive_is_french_exclusive():
    # Membership contract: no token may appear in another decisive table or in
    # another language's bag-of-words markers.
    for table in (_CA_DECISIVE, _ES_DECISIVE, _IT_DECISIVE, _NL_DECISIVE):
        assert not (_FR_DECISIVE & table)
    for lang, markers in _LANG_MARKERS.items():
        if lang != "FR":
            assert not (_FR_DECISIVE & markers), lang
