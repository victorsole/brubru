"""19 of 258 natural questions written for the AgRI 2040 guides were answered in the wrong language.

Found 13 Oct 2026 while probing production: "Quando si tiene la conferenza europea AgRI 2040 e chi
la apre?" tied IT "chi" against ES "tiene" and fell to French, so an Italian user was answered in
French; "Cosa dice Food 2040 su ..." held no Italian decisive token and scored English. Catalan
questions scored ES, FR, NL or EN. Every new token differs in all five other Brubru languages
after accent folding; "cosa", "dice" (Spanish), "come" (English), "animale" (French), "informe",
"invertir", "taller" (shared with Spanish) were left out on purpose.
"""
import pytest

from services.ai_service import (_CA_DECISIVE, _FR_DECISIVE, _IT_DECISIVE,
                                 _detect_query_language)

CASES = [
    # Italian
    ("Quando si tiene la conferenza europea AgRI 2040 e chi la apre?", "IT"),
    ("Cosa dice AgRI 2040 sull'allevamento e la salute animale?", "IT"),
    ("Cosa dice Food 2040 su sistemi alimentari locali e diete sane?", "IT"),
    ("Cosa dice Food 2040 su alimenti acquatici, pesca e acquacoltura?", "IT"),
    ("Di cosa trattano i progetti SafeHabitus e FLIARA?", "IT"),
    # Catalan
    ("Què diu AgRI 2040 sobre la ramaderia i la sanitat animal?", "CA"),
    ("Quantes persones van respondre a l'enquesta Food 2040 i quines van ser les prioritats principals?", "CA"),
    ("Què és el nou enfocament estratègic de la UE per a la recerca i la innovació agroalimentàries, AgRI 2040 i Food 2040?", "CA"),
    # French
    ("Combien de domaines d'action AgRI 2040 compte-t-il et lesquels ?", "FR"),
    ("De combien d'argent dispose l'entreprise commune CBE-JU et que fait EIT Food ?", "FR"),
    # the same questions in the other languages must NOT move
    ("¿Cuándo es la conferencia europea AgRI 2040 y quién la inaugura?", "ES"),
    ("¿Qué dice AgRI 2040 sobre la ganadería y la sanidad animal?", "ES"),
    ("Que dit AgRI 2040 sur l'élevage et la santé animale ?", "FR"),
    ("Wat zegt AgRI 2040 over de veehouderij en de dierlijke gezondheid?", "NL"),
    ("What does AgRI 2040 say about livestock systems and animal health?", "EN"),
]


@pytest.mark.parametrize("query,lang", CASES)
def test_detects(query, lang):
    assert _detect_query_language(query) == lang


def test_new_tokens_are_in_the_tables_they_belong_to():
    assert {"enfocament", "recerca", "innovacio", "ramaderia", "sanitat", "segons"} <= _CA_DECISIVE
    assert {"quando", "conferenza", "allevamento", "salute", "fertilizzanti"} <= _IT_DECISIVE
    assert {"combien", "lesquels", "argent", "entreprise"} <= _FR_DECISIVE


def test_ambiguous_words_stay_out():
    """'cosa' and 'dice' are Spanish too; 'animale' is French; 'invertir' is Spanish and Catalan."""
    for word in ("cosa", "dice", "come", "animale", "europea", "pesca"):
        assert word not in _IT_DECISIVE
    for word in ("informe", "invertir", "taller", "quant", "centre"):
        assert word not in _CA_DECISIVE
    assert "compte" not in _FR_DECISIVE
