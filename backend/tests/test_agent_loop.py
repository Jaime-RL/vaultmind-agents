"""Bucle ReAct con FakeLLMClient y herramientas falsas."""

import json

import pytest

from agents import AgentStepLimitError, ToolError, run_agent
from router import require_json_object
from tests.conftest import calls_tool, fake_search_tool, final


async def run(router, emitter, tool, max_steps=8):
    return await run_agent(
        agent="researcher",
        task="summarize_paper",
        messages=[{"role": "user", "content": "investiga SLMs"}],
        tools=[tool],
        router=router,
        emitter=emitter,
        final_validator=require_json_object("summary"),
        max_steps=max_steps,
    )


async def test_calls_tool_then_returns_final_answer(make_router, emitter, sink):
    tool = fake_search_tool()
    router, fake = make_router([calls_tool("search_arxiv", query="SLM"), final({"summary": "ok"})])

    response = await run(router, emitter, tool)

    assert json.loads(response.content) == {"summary": "ok"}
    assert tool.handler.queries == ["SLM"]
    assert sink.types() == ["route_decision", "tool_call", "tool_result", "route_decision"]
    # El segundo paso recibe la petición de herramienta y su resultado.
    second_call = fake.calls[1].messages
    assert second_call[-2]["tool_calls"][0]["function"]["name"] == "search_arxiv"
    assert second_call[-1]["role"] == "tool"
    assert second_call[-1]["tool_call_id"] == "c1"
    assert "Example paper" in second_call[-1]["content"]


async def test_reasoning_next_to_tool_call_becomes_a_thought(make_router, emitter, sink):
    router, _ = make_router(
        [
            calls_tool("search_arxiv", content="Primero busco papers recientes", query="SLM"),
            final({"summary": "ok"}),
        ]
    )

    await run(router, emitter, fake_search_tool())

    thoughts = [e.text for e in sink.events if e.type == "agent_thought"]
    assert thoughts == ["Primero busco papers recientes"]


async def test_tool_errors_are_returned_to_the_model(make_router, emitter, sink):
    tool = fake_search_tool(error=ToolError("arXiv no responde"))
    router, fake = make_router(
        [calls_tool("search_arxiv", query="x"), final({"summary": "sin datos"})]
    )

    await run(router, emitter, tool)

    result = next(e for e in sink.events if e.type == "tool_result")
    assert result.summary == "error: arXiv no responde"
    assert json.loads(fake.calls[1].messages[-1]["content"]) == {"error": "arXiv no responde"}


async def test_unknown_tool_from_slm_escalates(make_router, emitter, sink):
    # El SLM pide una herramienta que no existe → validación falla → escala al grande.
    router, fake = make_router([calls_tool("borrar_todo"), final({"summary": "ok"})])

    await run(router, emitter, fake_search_tool())

    assert [c.model for c in fake.calls] == ["small", "large"]
    route = next(e for e in sink.events if e.type == "route_decision")
    assert route.escalated is True


async def test_invalid_final_answer_from_slm_escalates(make_router, emitter):
    router, fake = make_router([final({"otra": "cosa"}), final({"summary": "ok"})])

    response = await run(router, emitter, fake_search_tool())

    assert [c.model for c in fake.calls] == ["small", "large"]
    assert json.loads(response.content)["summary"] == "ok"


async def test_step_limit_stops_endless_tool_calls(make_router, emitter):
    router, fake = make_router([calls_tool("search_arxiv", query="a")] * 2)

    with pytest.raises(AgentStepLimitError, match="2 pasos"):
        await run(router, emitter, fake_search_tool(), max_steps=2)
    assert len(fake.calls) == 2
