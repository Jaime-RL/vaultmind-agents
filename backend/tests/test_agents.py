"""Explorador, Investigador y orquestador con una bóveda pequeña y LLM falso."""

import pytest

from agents import Gap, explore, research, run_research
from agents.explorer import clean_title
from llm import LLMError, LLMResponse
from tests.conftest import PAPER_URL, calls_tool, fake_search_tool, final
from vault import parse_vault


@pytest.fixture
def vault(tmp_path):
    notes = {
        "SLM.md": "Ver [[LoRA]], [[Cuantización]] y [[Routing]].",
        "Agentes.md": "Usan [[Tool calling]] y [[Routing]].",
        "Clima.md": "Datos de [[ERA5]].",
    }
    for name, text in notes.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    return parse_vault(tmp_path)


# --- Explorador --------------------------------------------------------------


async def test_explorer_puts_the_topic_first_and_adds_related_gaps(
    make_router, emitter, sink, vault
):
    router, fake = make_router(
        [final({"topic_note": "Modelos pequeños", "selected": ["LoRA", "Routing"]})]
    )

    gaps = await explore(topic="SLMs", vault=vault, router=router, emitter=emitter)

    # El tema pedido va siempre primero; después, las lagunas relacionadas.
    assert [g.name for g in gaps] == ["Modelos pequeños", "LoRA", "Routing"]
    assert gaps[0].mentioned_in == []  # nota nueva: nadie la enlaza todavía
    assert gaps[2].mentioned_in == ["Agentes", "SLM"]
    assert fake.calls[0].model == "small"  # find_gaps va primero al SLM
    prompt = fake.calls[0].messages[-1]["content"]
    assert "Tema: SLMs" in prompt
    assert prompt.index("Routing") < prompt.index("LoRA")  # ordenadas por menciones
    assert sink.types()[:3] == ["agent_thought", "tool_call", "tool_result"]


async def test_explorer_does_not_force_unrelated_gaps(make_router, emitter, vault):
    """Regresión: con «multitoken prediction» investigaba lagunas sin relación."""
    router, _ = make_router([final({"topic_note": "Predicción multitoken", "selected": []})])

    gaps = await explore(topic="multitoken prediction", vault=vault, router=router, emitter=emitter)

    assert [g.name for g in gaps] == ["Predicción multitoken"]


async def test_explorer_ignores_invented_gaps_and_fixes_case(make_router, emitter, vault):
    router, _ = make_router(
        [final({"topic_note": "SLMs", "selected": ["lora", "Algo inventado", "LoRA"]})]
    )

    gaps = await explore(topic="SLMs", vault=vault, router=router, emitter=emitter)

    assert [g.name for g in gaps] == ["SLMs", "LoRA"]


async def test_explorer_reuses_a_gap_that_matches_the_topic(make_router, emitter, vault):
    router, _ = make_router([final({"topic_note": "routing", "selected": ["Routing", "LoRA"]})])

    gaps = await explore(topic="routing", vault=vault, router=router, emitter=emitter)

    # La laguna «Routing» ES el tema: no se duplica y conserva sus menciones.
    assert [g.name for g in gaps] == ["Routing", "LoRA"]
    assert gaps[0].mentioned_in == ["Agentes", "SLM"]


async def test_explorer_respects_max_gaps(make_router, emitter, vault):
    router, _ = make_router([final({"topic_note": "T", "selected": ["Routing", "LoRA", "ERA5"]})])

    gaps = await explore(topic="t", vault=vault, router=router, emitter=emitter, max_gaps=2)

    assert [g.name for g in gaps] == ["T", "Routing"]


async def test_explorer_skips_topic_that_already_has_a_note(make_router, emitter, vault):
    router, _ = make_router([final({"topic_note": "Clima", "selected": ["ERA5"]})])

    gaps = await explore(topic="clima", vault=vault, router=router, emitter=emitter)

    assert [g.name for g in gaps] == ["ERA5"]  # «Clima» ya existe en la bóveda


async def test_explorer_sanitizes_the_topic_title(make_router, emitter, vault):
    router, _ = make_router([final({"topic_note": "  [[Mixture|of]] #experts.  ", "selected": []})])

    gaps = await explore(topic="moe", vault=vault, router=router, emitter=emitter)

    assert [g.name for g in gaps] == ["Mixture of experts"]


def test_clean_title_never_produces_a_path():
    assert clean_title("../../etc/passwd") == "Etc passwd"
    assert "/" not in clean_title("a/b\\c") and "\\" not in clean_title("a/b\\c")


async def test_explorer_without_gaps_researches_the_topic_without_calling_the_model(
    make_router, emitter, tmp_path
):
    (tmp_path / "a.md").write_text("Sin enlaces.", encoding="utf-8")
    router, fake = make_router([])

    gaps = await explore(
        topic="mixture of experts", vault=parse_vault(tmp_path), router=router, emitter=emitter
    )

    assert gaps == [Gap(name="Mixture of experts", mentioned_in=[])]
    assert fake.calls == []


# --- Investigador ------------------------------------------------------------

LORA = Gap(name="LoRA", mentioned_in=["SLM"])
ROUTING = Gap(name="Routing", mentioned_in=["SLM", "Agentes"])


async def test_researcher_keeps_only_sources_returned_by_arxiv(make_router, emitter):
    answer = {
        "summary": "LoRA entrena matrices de bajo rango.",
        "sources": [
            {"title": "Real", "url": PAPER_URL},
            {"title": "Inventada", "url": "http://arxiv.org/abs/9999.99999"},
        ],
    }
    router, _ = make_router([calls_tool("search_arxiv", query="LoRA"), final(answer)])

    findings = await research(
        topic="SLMs", gaps=[LORA], router=router, emitter=emitter, search_tool=fake_search_tool()
    )

    assert len(findings) == 1
    assert findings[0].summary.startswith("LoRA")
    assert [s.url for s in findings[0].sources] == [PAPER_URL]


async def test_researcher_matches_sources_by_arxiv_id(make_router, emitter):
    """Regresión: «0 fuentes verificadas» porque el modelo escribía la URL de otra forma."""
    variants = ["https://arxiv.org/abs/0000.00001", "https://arxiv.org/pdf/0000.00001v2.pdf"]
    answer = {"summary": "Resumen.", "sources": [{"title": "A", "url": u} for u in variants]}
    router, _ = make_router([calls_tool("search_arxiv", query="LoRA"), final(answer)])

    findings = await research(
        topic="SLMs", gaps=[LORA], router=router, emitter=emitter, search_tool=fake_search_tool()
    )

    # Las dos variantes son el mismo paper: una sola fuente, con la URL que dio arXiv.
    assert [s.url for s in findings[0].sources] == [PAPER_URL]


async def test_researcher_does_not_repeat_identical_searches(make_router, emitter):
    tool = fake_search_tool()
    router, fake = make_router(
        [
            calls_tool("search_arxiv", query="LoRA"),
            calls_tool("search_arxiv", query="  lora "),  # la misma búsqueda
            final({"summary": "Resumen.", "sources": []}),
        ]
    )

    await research(topic="SLMs", gaps=[LORA], router=router, emitter=emitter, search_tool=tool)

    assert tool.handler.queries == ["LoRA"]  # arXiv solo recibe la primera
    assert "Ya hiciste esta búsqueda" in fake.calls[2].messages[-1]["content"]


async def test_related_gap_without_sources_is_dropped_but_the_topic_is_kept(
    make_router, emitter, sink
):
    """Regresión: «Function calling en SLMs» se elegía para «multi-token prediction» y se
    escribía de memoria, sin ninguna fuente."""
    topic = Gap(name="Multi-token prediction", mentioned_in=[], is_topic=True)
    no_sources = {"summary": "Nada útil.", "sources": []}
    router, _ = make_router([final(no_sources), final(no_sources)])

    findings = await research(
        topic="mtp",
        gaps=[topic, LORA],
        router=router,
        emitter=emitter,
        search_tool=fake_search_tool(),
    )

    assert [f.gap.name for f in findings] == ["Multi-token prediction"]
    assert any("Descarto «LoRA»" in e.text for e in sink.events if e.type == "agent_thought")


async def test_researcher_continues_when_one_gap_fails(make_router, emitter, sink):
    router, _ = make_router(
        [
            LLMError("caído"),  # LoRA: falla el SLM...
            LLMError("también"),  # ...y el grande
            calls_tool("search_arxiv", query="routing"),
            final(
                {"summary": "Routing elige modelo.", "sources": [{"title": "R", "url": PAPER_URL}]}
            ),
        ]
    )

    findings = await research(
        topic="SLMs",
        gaps=[LORA, ROUTING],
        router=router,
        emitter=emitter,
        search_tool=fake_search_tool(),
    )

    assert [f.gap.name for f in findings] == ["Routing"]
    assert any(
        "No pude investigar «LoRA»" in e.text for e in sink.events if e.type == "agent_thought"
    )


# --- Orquestador -------------------------------------------------------------


class StepClock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        self.t += 30.0
        return self.t


NOTE_MD = "# LoRA\n\n" + "LoRA ajusta modelos con matrices de bajo rango. " * 5 + "Ver [[SLM]]."


async def test_full_run_ends_with_run_finished(make_router, emitter, sink, vault):
    router, fake = make_router(
        [
            final({"topic_note": "LoRA", "selected": ["LoRA"]}),  # Explorador (SLM)
            calls_tool("search_arxiv", query="LoRA"),  # Investigador (SLM)
            final({"summary": "Resumen", "sources": [{"title": "P", "url": PAPER_URL}]}),
            LLMResponse(content=NOTE_MD, prompt_tokens=900, completion_tokens=300),  # Redactor
            final({"claims": 3, "supported": 3, "issues": []}),  # Revisor (SLM)
        ]
    )
    saved = []

    async def on_proposal(proposal):
        saved.append(proposal)

    result = await run_research(
        topic="SLMs",
        vault=vault,
        router=router,
        emitter=emitter,
        search_tool=fake_search_tool(),
        on_proposal=on_proposal,
        clock=StepClock(),
    )

    assert fake.remaining == 0
    assert sink.types()[-1] == "run_finished"
    assert "error" not in sink.types()
    assert {"explorer", "researcher", "writer", "reviewer"} <= {e.agent for e in sink.events}
    assert [f.gap.name for f in result.findings] == ["LoRA"]
    assert saved == result.proposals
    assert result.proposals[0].links == ["SLM"]
    stats = result.stats
    assert stats.notes_proposed == 1
    assert stats.duration_s == 30.0
    assert stats.cost_usd > 0
    assert stats.baseline_cost_usd > stats.cost_usd  # 3 de 4 tareas en el SLM: hay ahorro
    assert all(e.run_id == "run-test" for e in sink.events)


async def test_unexpected_failure_ends_with_error_event(make_router, emitter, sink, vault):
    router, _ = make_router(
        [
            final({"topic_note": "LoRA", "selected": ["LoRA"]}),
            calls_tool("search_arxiv", query="LoRA"),
        ]
    )
    broken_tool = fake_search_tool(error=RuntimeError("bug inesperado"))

    result = await run_research(
        topic="SLMs", vault=vault, router=router, emitter=emitter, search_tool=broken_tool
    )

    assert result is None
    assert sink.types()[-1] == "error"
    assert "bug inesperado" in sink.events[-1].message
    assert "run_finished" not in sink.types()
