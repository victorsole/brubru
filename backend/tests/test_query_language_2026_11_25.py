"""Detector fix from the 25 Nov 2026 local probe (Italian question answered in Spanish).

"L'UE ha firmato l'accordo con l'Indonesia?" carried one marker word, "con", shared with
Spanish, and the IT/ES tie-break counted it for Spanish. Italian-only participles and
"accordo" were added to _IT_DECISIVE; the run over every trigger-matrix question went
from 20 to 19 misdetections with no new one.
"""
import pytest

from services.ai_service import _detect_query_language

FIXED = [
    ("IT", "L'UE ha firmato l'accordo con l'Indonesia?"),
    ("IT", "Il Consiglio ha approvato l'accordo con l'Indonesia?"),
    ("IT", "La Commissione ha adottato il pacchetto?"),
]

UNCHANGED = [
    ("ES", "La UE ha firmado el acuerdo con Indonesia?"),
    ("CA", "Ha signat la UE l'acord amb Indonèsia?"),
    ("FR", "L'UE a-t-elle signé l'accord avec l'Indonésie ?"),
    ("EN", "Has the EU signed its trade agreement with Indonesia?"),
    ("ES", "¿Ha aprobado el Consejo el acuerdo con Indonesia?"),
]


@pytest.mark.parametrize("lang,question", FIXED + UNCHANGED)
def test_detected_language(lang, question):
    assert _detect_query_language(question) == lang
