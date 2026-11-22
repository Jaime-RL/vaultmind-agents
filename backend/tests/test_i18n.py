"""Idiomas: detección, instrucciones a los modelos y mensajes traducidos (sin red ni LLM)."""

import pytest

from agents import Emitter, explore
from agents.asker import answer_question
from agents.editorial import write_and_review
from agents.writer import note_body
from app.i18n import _T, LANGUAGES, NOTE_SECTION_MARKERS, detect_language, resolve_language, tr
from llm import LLMResponse
from runs.demo import demo_notice
from tests.conftest import final
from tests.test_editorial import FIXED, finding, note
from vault import parse_vault


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("¿Qué es la predicción de varios tokens?", "es"),
        ("What is multi-token prediction and how does it work?", "en"),
        ("Qu'est-ce que la prédiction multi-jetons et comment ça marche ?", "fr"),
        ("Was ist Multi-Token-Vorhersage und wie funktioniert das?", "de"),
        ("O que é a previsão de vários tokens e como funciona?", "pt"),
    ],
)
def test_detects_the_five_languages(text, lang):
    assert detect_language(text) == lang


def test_without_clues_uses_the_interface_language():
    # Solo términos técnicos: no hay forma de saberlo, así que manda la interfaz.
    assert detect_language("multi-token prediction", fallback="de") == "de"
    assert resolve_language("auto", "LoRA", ui="fr") == "fr"
    assert resolve_language("pt", "What is LoRA?", ui="es") == "pt"  # lo elegido manda


def test_every_message_exists_in_every_language():
    missing = [(key, lang) for key, texts in _T.items() for lang in LANGUAGES if lang not in texts]
    assert missing == []


def test_note_body_strips_the_generated_sections_in_any_language():
    for lang in LANGUAGES:
        md = f"# T\n\nCuerpo.\n\n## {tr(lang, 'note.sources')}\n\n- x\n"
        assert note_body(md) == "# T\n\nCuerpo."
    assert len(NOTE_SECTION_MARKERS) >= 5


def test_demo_notice_in_english():
    text = demo_notice("LoRA", "SLMs", "tu cupo de investigaciones de hoy", "en")
    assert "your research quota for today" in text and "“LoRA”" in text


@pytest.fixture
def vault(tmp_path):
    (tmp_path / "SLM.md").write_text("Ver [[LoRA]] y [[Routing]].", encoding="utf-8")
    return parse_vault(tmp_path)


async def test_agent_messages_follow_the_interface_language(make_router, sink, vault):
    emitter = Emitter("run-1", sink, lang="en")
    router, _ = make_router([final({"topic_note": "LoRA", "selected": []})])

    await explore(topic="LoRA", vault=vault, router=router, emitter=emitter)

    thoughts = [e.text for e in sink.events if e.type == "agent_thought"]
    assert thoughts[0].startswith("Reading the vault: 1 notes")


async def test_notes_are_written_in_the_content_language(make_router, emitter, vault):
    router, fake = make_router([note(FIXED), final({"claims": 2, "supported": 2, "issues": []})])
    saved = []

    async def save(p):
        saved.append(p)

    await write_and_review(
        topic="LoRA",
        findings=[finding()],
        vault=vault,
        router=router,
        emitter=emitter,
        on_proposal=save,
        lang="fr",
    )

    assert "OUTPUT LANGUAGE" in fake.calls[0].messages[0]["content"]
    assert "French" in fake.calls[0].messages[0]["content"]
    assert saved[0].language == "fr"
    assert "\n## Sources\n" in saved[0].markdown and "Mentionnée dans" in saved[0].markdown


async def test_question_in_english_gets_an_answer_in_english(make_router, tmp_path):
    """Regresión: una pregunta en inglés se respondía en español."""
    (tmp_path / "LoRA.md").write_text("LoRA trains low-rank matrices.", encoding="utf-8")
    router, fake = make_router(
        [LLMResponse(content="LoRA trains low-rank matrices [[LoRA]].", prompt_tokens=1)]
    )

    response = await answer_question(
        question="What is LoRA and how does it work?",
        vault=parse_vault(tmp_path),
        router=router,
        run_id="a",
    )

    assert response.language == "en"
    assert "English" in fake.calls[0].messages[0]["content"]


async def test_no_notes_message_in_the_question_language(tmp_path):
    (tmp_path / "A.md").write_text("Nada.", encoding="utf-8")
    response = await answer_question(
        question="Was ist Quantencomputing und wie funktioniert das?",
        vault=parse_vault(tmp_path),
        router=None,
        run_id="b",
    )
    assert response.language == "de" and response.answer.startswith("Dazu finde ich nichts")
