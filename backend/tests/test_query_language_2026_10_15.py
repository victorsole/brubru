"""Catalan "què"/"és" are decisive before accent folding (15 Oct 2026).

Short Catalan questions lost to ES, FR or EN because folding turns "què" into the
shared "que". Every Catalan case below was misdetected before the rule.
"""
import pytest

from services.ai_service import _detect_query_language

CATALAN = [
    "Què va aprovar el Consell a l'òmnibus de defensa?",
    "Què canvia a la reserva d'estabilitat del mercat de l'ETS2?",
    "Què es va acordar a les consultes comercials entre la UE i la Xina?",
    "Què és el «fre d'emergència» que demanen Alemanya, Itàlia i Bèlgica?",
    "Què és un número CELEX i com es construeix?",
    "Què significa R(01) al final d'un número CELEX?",
    "Què és l'acceleradora d'inversions en resiliència hídrica de la UE?",
    "Què va signar la UE sobre el Conveni de Varsòvia i la recuperació d'actius?",
]

NOT_CATALAN = [
    ("ES", "¿Qué es el reglamento de retorno?"),
    ("ES", "Qué es el Comité de las Regiones"),
    ("FR", "Qu'est-ce que le règlement sur le retour ?"),
    ("IT", "Che cos'è il regolamento sui rimpatri?"),
    ("IT", "Cos'è il Comitato delle regioni?"),
    ("EN", "What is the Return Regulation?"),
]


@pytest.mark.parametrize("q", CATALAN)
def test_catalan_que_es_is_catalan(q):
    assert _detect_query_language(q) == "CA"


@pytest.mark.parametrize("lang,q", NOT_CATALAN)
def test_other_languages_unchanged(lang, q):
    assert _detect_query_language(q) == lang
