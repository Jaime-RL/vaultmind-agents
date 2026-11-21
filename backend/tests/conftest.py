"""Utilidades compartidas por los tests de agentes."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from agents import Emitter, ListSink, Tool, ToolOutput
from llm import FakeLLMClient, LLMResponse, ToolCall
from router import ModelPrice, SmartRoute


class TickingClock:
    """Reloj de eventos que avanza un segundo por lectura: marcas de tiempo deterministas."""

    def __init__(self):
        self.now = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(seconds=1)
        return self.now


@pytest.fixture
def make_router():
    def factory(script) -> tuple[SmartRoute, FakeLLMClient]:
        fake = FakeLLMClient(script)
        router = SmartRoute(
            client=fake,
            slm_model="small",
            large_model="large",
            slm_price=ModelPrice(0.1, 0.1),
            large_price=ModelPrice(3.0, 15.0),
        )
        return router, fake

    return factory


@pytest.fixture
def sink() -> ListSink:
    return ListSink()


@pytest.fixture
def emitter(sink) -> Emitter:
    return Emitter("run-test", sink, now=TickingClock())


def final(data: dict, tokens=(500, 50)) -> LLMResponse:
    """Respuesta final del modelo con JSON en el contenido."""
    return LLMResponse(
        content=json.dumps(data, ensure_ascii=False),
        prompt_tokens=tokens[0],
        completion_tokens=tokens[1],
    )


def calls_tool(name: str, call_id: str = "c1", content: str | None = None, **arguments):
    """Respuesta del modelo que pide una herramienta."""
    return LLMResponse(
        content=content,
        tool_calls=[ToolCall(id=call_id, name=name, arguments=arguments)],
        prompt_tokens=400,
        completion_tokens=30,
    )


PAPER_URL = "http://arxiv.org/abs/0000.00001v1"


def fake_search_tool(results=None, error: Exception | None = None) -> Tool:
    """Herramienta search_arxiv falsa: devuelve resultados fijos o lanza un error."""
    queries: list[str] = []

    async def handler(args: dict) -> ToolOutput:
        queries.append(args.get("query", ""))
        if error is not None:
            raise error
        data = results if results is not None else [{"title": "Example paper", "url": PAPER_URL}]
        return ToolOutput(summary=f"{len(data)} resultados de arXiv", data=data)

    # Tool es inmutable: las consultas recibidas se guardan en la propia función
    # (tool.handler.queries) para poder inspeccionarlas en los tests.
    handler.queries = queries  # type: ignore[attr-defined]
    return Tool(
        name="search_arxiv",
        description="Busca en arXiv",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}},
        handler=handler,
    )
