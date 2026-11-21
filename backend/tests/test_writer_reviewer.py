"""Redactor y Revisor con LLM falso."""

import pytest

from agents import Finding, Gap, Source, review_notes, write_notes
from llm import LLMError, LLMResponse
from tests.conftest import PAPER_URL, final
from vault import parse_vault

NOTE = """# LoRA

LoRA adapta modelos grandes entrenando matrices de bajo rango en lugar de todos los pesos.
Es útil para ajustar un [[SLM]] con pocos recursos y se combina con [[Cuantización]].
También se menciona en [[Nota que no existe]], que no debe aparecer en el grafo.
"""


def note(text: str = NOTE) -> LLMResponse:
    return LLMResponse(content=text, prompt_tokens=900, completion_tokens=300)


@pytest.fixture
def vault(tmp_path):
    (tmp_path / "modelos").mkdir()
    (tmp_path / "modelos" / "SLM.md").write_text("Ver [[LoRA]].", encoding="utf-8")
    (tmp_path / "modelos" / "Cuantización.md").write_text("Reduce bits.", encoding="utf-8")
    return parse_vault(tmp_path)


@pytest.fixture
def finding():
    return Finding(
        gap=Gap(name="LoRA", mentioned_in=["modelos/SLM"]),
        summary="LoRA entrena matrices de bajo rango.",
        sources=[Source(title="Example paper", url=PAPER_URL)],
    )


# --- Redactor ----------------------------------------------------------------


async def test_writer_builds_pending_proposal(make_router, emitter, sink, vault, finding):
    router, fake = make_router([note()])

    [proposal] = await write_notes(
        topic="SLMs", findings=[finding], vault=vault, router=router, emitter=emitter
    )

    assert fake.calls[0].model == "large"  # write_note va al modelo grande
    assert proposal.status == "pending"
    assert proposal.title == "LoRA"
    assert proposal.model == "large"
    assert proposal.id.startswith("p-")
    # Solo enlaces a notas que existen; el inventado se descarta.
    assert proposal.links == ["modelos/SLM", "modelos/Cuantización"]
    event = next(e for e in sink.events if e.type == "node_proposed")
    assert (event.proposal_id, event.links) == (proposal.id, proposal.links)


async def test_writer_adds_verified_sources_and_backlinks(make_router, emitter, vault, finding):
    router, _ = make_router([note()])

    [proposal] = await write_notes(
        topic="SLMs", findings=[finding], vault=vault, router=router, emitter=emitter
    )

    assert f"[Example paper]({PAPER_URL})" in proposal.markdown
    assert "Mencionada en: [[modelos/SLM]]" in proposal.markdown
    assert proposal.sources[0].url == PAPER_URL


async def test_writer_warns_when_there_are_no_sources(make_router, emitter, vault, finding):
    router, _ = make_router([note()])
    no_sources = Finding(gap=finding.gap, summary=finding.summary, sources=[])

    [proposal] = await write_notes(
        topic="SLMs", findings=[no_sources], vault=vault, router=router, emitter=emitter
    )

    assert "Sin fuentes verificadas" in proposal.markdown


async def test_writer_strips_markdown_fence(make_router, emitter, vault, finding):
    router, _ = make_router([note(f"```markdown\n{NOTE}\n```")])

    [proposal] = await write_notes(
        topic="SLMs", findings=[finding], vault=vault, router=router, emitter=emitter
    )

    assert proposal.markdown.startswith("# LoRA")


async def test_writer_skips_finding_when_model_fails(make_router, emitter, sink, vault, finding):
    router, _ = make_router([note("demasiado corta")])

    proposals = await write_notes(
        topic="SLMs", findings=[finding], vault=vault, router=router, emitter=emitter
    )

    assert proposals == []
    assert any("No pude redactar" in e.text for e in sink.events if e.type == "agent_thought")


# --- Revisor -----------------------------------------------------------------


async def make_proposal(make_router, emitter, vault, finding):
    router, _ = make_router([note()])
    [proposal] = await write_notes(
        topic="SLMs", findings=[finding], vault=vault, router=router, emitter=emitter
    )
    return proposal


async def test_reviewer_reports_support_and_issues(make_router, emitter, sink, vault, finding):
    proposal = await make_proposal(make_router, emitter, vault, finding)
    router, fake = make_router(
        [final({"claims": 4, "supported": 3, "issues": ["cifra sin fuente"]})]
    )

    [review] = await review_notes(
        proposals=[proposal], findings=[finding], router=router, emitter=emitter
    )

    assert fake.calls[0].model == "small"  # verify_claims va primero al SLM
    assert (review.claims, review.supported, review.issues) == (4, 3, ["cifra sin fuente"])
    result = [e for e in sink.events if e.type == "tool_result"][-1]
    assert result.summary == "3 de 4 afirmaciones con respaldo"
    assert "cifra sin fuente" in sink.events[-1].text


async def test_reviewer_clamps_inconsistent_numbers(make_router, emitter, vault, finding):
    proposal = await make_proposal(make_router, emitter, vault, finding)
    router, _ = make_router([final({"claims": 2, "supported": 7, "issues": []})])

    [review] = await review_notes(
        proposals=[proposal], findings=[finding], router=router, emitter=emitter
    )

    assert review.supported == 2


async def test_reviewer_failure_does_not_lose_the_proposal(
    make_router, emitter, sink, vault, finding
):
    proposal = await make_proposal(make_router, emitter, vault, finding)
    router, _ = make_router([LLMError("x"), LLMError("y")])

    reviews = await review_notes(
        proposals=[proposal], findings=[finding], router=router, emitter=emitter
    )

    assert reviews == []
    assert "No pude revisar" in sink.events[-1].text
