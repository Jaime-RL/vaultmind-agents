"""Bucle editorial Redactor ⇄ Revisor, con LLM falso."""

import pytest

from agents import Finding, Gap, Source
from agents.editorial import write_and_review
from agents.reviewer import Review, needs_revision
from llm import LLMError, LLMResponse
from tests.conftest import PAPER_URL, final
from vault import parse_vault

ABSTRACT = "We propose LoRA, which freezes the weights and trains low-rank matrices."
DRAFT = "# LoRA\n\n" + "LoRA fue creado por Baidu en 2015 y reduce el coste un 90 %. " * 4
FIXED = "# LoRA\n\n" + "LoRA congela los pesos y entrena matrices de bajo rango. " * 4


def note(text: str) -> LLMResponse:
    return LLMResponse(content=text, prompt_tokens=900, completion_tokens=300)


@pytest.fixture
def vault(tmp_path):
    (tmp_path / "SLM.md").write_text("Ver [[LoRA]].", encoding="utf-8")
    return parse_vault(tmp_path)


def finding(sources: bool = True) -> Finding:
    return Finding(
        gap=Gap(name="LoRA", mentioned_in=["SLM"]),
        summary="LoRA entrena matrices de bajo rango.",
        sources=[Source("LoRA paper", PAPER_URL, ABSTRACT)] if sources else [],
    )


async def run(router, emitter, vault, f=None, saved=None):
    async def save(p):
        saved.append(p)

    return await write_and_review(
        topic="SLMs",
        findings=[f or finding()],
        vault=vault,
        router=router,
        emitter=emitter,
        on_proposal=save if saved is not None else None,
    )


async def test_weak_note_is_rewritten_once_and_reviewed_again(make_router, emitter, sink, vault):
    router, fake = make_router(
        [
            note(DRAFT),  # Redactor
            final({"claims": 3, "supported": 0, "issues": ["Baidu", "2015", "90 %"]}),  # Revisor
            note(FIXED),  # Redactor corrige
            final({"claims": 2, "supported": 2, "issues": []}),  # Revisor otra vez
        ]
    )
    saved = []

    result = await run(router, emitter, vault, saved=saved)

    assert result.revisions == 1
    [proposal] = result.proposals
    assert "Baidu" not in proposal.markdown and "congela los pesos" in proposal.markdown
    assert saved == [proposal]  # solo se publica la versión corregida
    assert [r.supported for r in result.reviews] == [2]
    # La reescritura recibe la versión anterior y los problemas concretos.
    rewrite_prompt = fake.calls[2].messages[-1]["content"]
    assert "Baidu" in rewrite_prompt and "- 90 %" in rewrite_prompt
    assert [e.type for e in sink.events].count("node_proposed") == 1


async def test_good_note_is_published_without_rewriting(make_router, emitter, vault):
    router, fake = make_router([note(FIXED), final({"claims": 4, "supported": 4, "issues": []})])

    result = await run(router, emitter, vault)

    assert result.revisions == 0
    assert len(fake.calls) == 2


async def test_writer_and_reviewer_receive_the_abstracts(make_router, emitter, vault):
    router, fake = make_router([note(FIXED), final({"claims": 4, "supported": 4, "issues": []})])

    await run(router, emitter, vault)

    assert ABSTRACT in fake.calls[0].messages[-1]["content"]  # Redactor
    reviewer_prompt = fake.calls[1].messages[-1]["content"]
    assert ABSTRACT in reviewer_prompt
    assert "## Fuentes" not in reviewer_prompt  # revisa el cuerpo, no las secciones del código


async def test_without_sources_the_writer_is_cautious_and_does_not_rewrite(
    make_router, emitter, vault
):
    router, fake = make_router([note(DRAFT), final({"claims": 3, "supported": 0, "issues": ["x"]})])

    result = await run(router, emitter, vault, f=finding(sources=False))

    assert "no hay fuentes verificadas" in fake.calls[0].messages[0]["content"]
    assert result.revisions == 0  # sin evidencia, reescribir no arreglaría nada
    assert len(result.proposals) == 1


async def test_reviewer_failure_still_publishes_the_note(make_router, emitter, vault):
    router, _ = make_router([note(FIXED), LLMError("caído"), LLMError("también")])
    saved = []

    result = await run(router, emitter, vault, saved=saved)

    assert len(saved) == 1 and result.reviews == []


async def test_failed_rewrite_keeps_the_first_draft(make_router, emitter, vault):
    router, _ = make_router(
        [
            note(DRAFT),
            final({"claims": 3, "supported": 0, "issues": ["Baidu"]}),
            LLMError("caído"),
            LLMError("también"),
        ]
    )

    result = await run(router, emitter, vault)

    assert "Baidu" in result.proposals[0].markdown
    assert result.revisions == 0


@pytest.mark.parametrize(
    ("claims", "supported", "expected"),
    [(5, 4, False), (5, 3, True), (0, 0, False), (2, 0, True)],
)
def test_needs_revision(claims, supported, expected):
    assert needs_revision(Review("p", claims, supported)) is expected
    assert needs_revision(None) is False
