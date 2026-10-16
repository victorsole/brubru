"""Detector fixes from the 16 Oct 2026 run over every trigger-matrix question (9 -> 1 misdetections).

The Italian Hungary question was answered in Catalan on a local probe: Catalan and
Italian tied on "la" and "per" and Catalan won the tie. Every case below was
misdetected before the fix.
"""
import pytest

from services.ai_service import _detect_query_language

FIXED = [
    ("IT", "La Corte di giustizia ha condannato l'Ungheria per aver liberato i trafficanti?"),
    ("IT", "È stata pubblicata la prima norma armonizzata per l'AI Act?"),
    ("IT", "Cosa dice l'EDPB sugli occhiali intelligenti?"),
    ("IT", "Cosa significa R(01) alla fine di un numero CELEX?"),
    ("IT", "Cosa significa la prima cifra di un numero CELEX, ad esempio 3, 5 o 6?"),
    ("CA", "El límit de passatgers de l'aeroport de Dublín pot reduir les franges horàries?"),
    ("CA", "Encara se celebra la cimera UE-CCG de Riad?"),
    ("NL", "Gaat de top EU-GCC in Riyad nog door?"),
]

UNCHANGED = [
    ("ES", "¿Se celebra todavía la cumbre UE-CCG de Riad?"),
    ("FR", "Le sommet UE-CCG de Riyad a-t-il toujours lieu ?"),
    ("EN", "Is the EU-GCC summit in Riyadh still happening?"),
    ("FR", "Le plafond de passagers de l'aéroport de Dublin peut-il réduire les créneaux des compagnies ?"),
    ("ES", "¿Puede el límite de pasajeros del aeropuerto de Dublín reducir las franjas horarias?"),
    ("IT", "Che cos'è il regolamento sui rimpatri?"),
    ("CA", "Què és un número CELEX i com es construeix?"),
]


@pytest.mark.parametrize("expected,question", FIXED + UNCHANGED)
def test_detected_language(expected, question):
    assert _detect_query_language(question) == expected
