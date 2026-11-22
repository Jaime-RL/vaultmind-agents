"""Redactor y Revisor con LLM falso."""

import pytest

from agents import Finding, Gap, Source, review_notes, write_notes
from agents.reviewer import unique_issues
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


async def test_reviewer_checks_against_abstracts_not_the_research_summary(
    make_router, emitter, vault
):
    """Regresión: el resumen del Investigador colaba ARIMA o GARCH (que ninguna fuente cita) y
    el Revisor los daba por respaldados. La evidencia son los abstracts."""
    finding = Finding(
        gap=Gap(name="LoRA", mentioned_in=[]),
        summary="LoRA, como ARIMA y GARCH, ...",
        sources=[Source(title="Example paper", url=PAPER_URL, abstract="Low-rank adapters.")],
    )
    proposal = await make_proposal(make_router, emitter, vault, finding)
    router, fake = make_router([final({"claims": 3, "supported": 1, "issues": ["ARIMA"]})])

    await review_notes(proposals=[proposal], findings=[finding], router=router, emitter=emitter)

    evidence = fake.calls[0].messages[-1]["content"].split("NOTA")[0]
    assert "Low-rank adapters." in evidence
    assert "ARIMA" not in evidence


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


async def test_writer_saves_each_proposal_before_emitting_node_proposed(
    make_router, emitter, sink, vault, finding
):
    """La interfaz pide /api/proposals al recibir node_proposed: la nota ya debe estar guardada."""
    router, _ = make_router([note()])
    events_when_saved: list[int] = []

    async def save(proposal):
        events_when_saved.append(sum(1 for e in sink.events if e.type == "node_proposed"))

    [proposal] = await write_notes(
        topic="SLMs",
        findings=[finding],
        vault=vault,
        router=router,
        emitter=emitter,
        on_proposal=save,
    )

    assert events_when_saved == [0]  # se guardó cuando aún no se había emitido el evento
    assert any(e.type == "node_proposed" and e.proposal_id == proposal.id for e in sink.events)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Regresión: el SLM repetía cinco veces la misma frase del ejemplo del prompt.
        (["afirmación sin respaldo"] * 5, ["afirmación sin respaldo"]),
        (
            ["La cifra del 40 %", "la  cifra del 40 %", " ", "El año 2019"],
            ["La cifra del 40 %", "El año 2019"],
        ),
        ([f"p{i}" for i in range(8)], [f"p{i}" for i in range(5)]),
        ("no es una lista", []),
    ],
)
def test_unique_issues(raw, expected):
    assert unique_issues(raw) == expected


def test_typographic_hyphens_inside_wikilinks_are_normalized():
    """Regresión (evals con Groq): [[Fine‑tuning]] con U+2011 no enlazaba con «Fine-tuning»."""
    from agents.writer import normalize_wikilinks

    text = "El ajuste [[Fine‑tuning]] y [[RAG|re–ranking]]; fuera del enlace, «auto‑regresivo»."

    assert normalize_wikilinks(text) == (
        "El ajuste [[Fine-tuning]] y [[RAG|re-ranking]]; fuera del enlace, «auto‑regresivo»."
    )
