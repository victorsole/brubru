"""The quality evaluator must measure the answer, not its own blind spots.

25 Sep 2026: before the 120-question baseline, the evaluator called a chat path
the UI never uses, sent no probe header, passed Catalan answered in Spanish,
knew follow-ups only in English, and failed correct legal citations (a Commission
decision number). These cases pin each fix.
"""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("eval_quality", HERE.parent / "scripts" / "eval_quality.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)


def test_stream_endpoint():
    assert ev.CHAT_ENDPOINT == "/api/chat/stream"


def test_legal_anchor_variants():
    for t in ["decision C(2026) 5358", "Regulation (EU) 2024/1689", "Directive 93/13/EEC",
              "case C-900/24", "case DMA.100193", "COM(2026) 321", "32024R1689"]:
        assert ev.check_mentions_celex_or_com(t, {}).passed, t
    assert not ev.check_mentions_celex_or_com("no legal text here", {}).passed


def test_follow_up_in_six_languages():
    for t in ["Would you like me to draft it?", "Próximo paso: puede consultar el calendario",
              "Pròxim pas: podeu consultar el calendari", "Prochaines étapes : vous pouvez consulter",
              "Prossimo passo: puoi consultare", "Volgende stap: u kunt raadplegen"]:
        assert ev.check_actionable_followup(t, {}).passed, t
    assert not ev.check_actionable_followup("The act applies from 2026.", {}).passed


def test_catalan_answered_in_spanish_fails():
    es = ("La Comisión Europea propone movilizar ciento cuarenta y nueve millones de euros del "
          "Fondo de Solidaridad para España tras las inundaciones, y el Parlamento debe aprobarlo.")
    assert not ev.check_responds_in_query_language(es, {"language": "CA"}).passed
    ca = ("La Comissió Europea proposa mobilitzar cent quaranta-nou milions d'euros del Fons de "
          "Solidaritat per a Espanya després de les inundacions, i el Parlament ho ha d'aprovar.")
    assert ev.check_responds_in_query_language(ca, {"language": "CA"}).passed


def test_expected_facts_and_number_formats():
    ga = {"expected_facts": [["40.5", "40,5"], ["67.1", "67,1"]]}
    assert ev.check_contains_expected_facts("dazi del 40,5 % e del 67,1 %", ga).passed
    assert not ev.check_contains_expected_facts("dazi del 40,5 %", ga).passed
    assert ev.check_contains_expected_facts("1 159 organisations", {"expected_facts": [["1159"]]}).passed


def test_off_topic():
    assert ev.check_declines_off_topic("I only cover EU policy.", {}).passed
    assert not ev.check_declines_off_topic("See Regulation 32024R1689 for paella.", {}).passed
