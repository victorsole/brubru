"""Closing next step and off-topic guard (28 Sep 2026, 120-question baseline re-run).

7 answers named no Brubru feature or offered no follow-up; the fix is deterministic
and only adds what is missing, in the question's language. Replayed on the 120
stored answers it amended 11 and left 109 untouched.
"""
from services.ai.context_builder import ContextBuilder
from services.ai_service import AIService

svc = AIService.__new__(AIService)
LONG = "La Llei d'IA estableix normes harmonitzades per a la intel·ligència artificial. " * 6


def test_adds_pointer_and_question_in_the_question_language():
    out = svc._ensure_next_step(LONG, "Què és la Llei d'IA i què regula?")
    tail = out[len(LONG.rstrip()):]
    assert "Els meus expedients en seguiment" in tail and "Voleu que" in tail


def test_leaves_a_complete_answer_alone():
    msg = LONG + "\n\nPodeu seguir-ho a My EU Bubble > Els meus expedients en seguiment. Voleu que aprofundeixi?"
    assert svc._ensure_next_step(msg, "Què és la Llei d'IA?") == msg


def test_drafting_points_to_my_documents():
    out = svc._ensure_next_step("Dear Commission, " * 30, "Draft a short response to the consultation on quality jobs")
    assert "My Documents" in out


def test_consultation_deadline_points_to_consultations():
    out = svc._ensure_next_step("The consultation runs to 13 November 2026. " * 10,
                                "¿Hasta cuándo puedo comentar las Directrices 04/2026 del CEPD?")
    assert "Consultas Públicas de la UE" in out


def test_off_topic_and_short_answers_untouched():
    msg = "Brubru is an assistant for EU policy and does not cover recipes. " * 6
    assert svc._ensure_next_step(msg, "What is a good recipe for paella?") == msg
    assert svc._ensure_next_step("OK.", "Say OK") == "OK."


def test_off_topic_guard_scope():
    cb = ContextBuilder.__new__(ContextBuilder)
    assert cb._build_off_topic_guard_block("¿Quién ganó la última final de la Champions League?")
    assert cb._build_off_topic_guard_block("Wat is een goed recept voor paella?")
    for q in ("Who won the EP elections in 2024?", "EU rules on football broadcasting rights",
              "What is the Critical Medicines Act?", "CAP support for olive oil producers"):
        assert cb._build_off_topic_guard_block(q) is None, q
    assert "NO act name" in cb._build_off_topic_guard_block("Write me a haiku about Julius Caesar")
