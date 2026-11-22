"""Emisión de eventos hacia la interfaz.

Los agentes no saben si sus eventos acaban en un flujo SSE, en una lista
(tests) o en la base de datos: solo llaman a `Emitter`. El destino concreto
es un `EventSink`, que se elige al montar la investigación.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from app.contracts import (
    Agent,
    AgentThought,
    Language,
    NodeProposed,
    RouteDecision,
    RunError,
    RunFinished,
    RunStats,
    ToolCallEvent,
    ToolResultEvent,
)

Event = (
    AgentThought
    | ToolCallEvent
    | ToolResultEvent
    | RouteDecision
    | NodeProposed
    | RunFinished
    | RunError
)


class EventSink(Protocol):
    async def emit(self, event: Event) -> None: ...


class ListSink:
    """Guarda los eventos en una lista. Para tests y para depurar."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    async def emit(self, event: Event) -> None:
        self.events.append(event)

    def types(self) -> list[str]:
        return [e.type for e in self.events]


class Emitter:
    """Crea eventos del contrato con run_id y marca de tiempo, y los envía al sink."""

    def __init__(
        self,
        run_id: str,
        sink: EventSink,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        lang: Language = "es",
    ):
        self.run_id = run_id
        self.sink = sink
        self.now = now
        self.lang = lang  # idioma de la interfaz: el de los mensajes de los agentes

    def _base(self, agent: Agent) -> dict[str, Any]:
        return {"run_id": self.run_id, "ts": self.now(), "agent": agent}

    async def thought(self, agent: Agent, text: str) -> None:
        await self.sink.emit(AgentThought(**self._base(agent), text=text))

    async def tool_call(self, agent: Agent, tool: str, args: dict[str, Any]) -> None:
        await self.sink.emit(ToolCallEvent(**self._base(agent), tool=tool, args=args))

    async def tool_result(self, agent: Agent, tool: str, summary: str) -> None:
        await self.sink.emit(ToolResultEvent(**self._base(agent), tool=tool, summary=summary))

    async def route(self, decision: RouteDecision) -> None:
        # SmartRoute ya construye el evento; solo actualizamos la marca de tiempo.
        await self.sink.emit(decision.model_copy(update={"ts": self.now()}))

    async def proposed(self, proposal_id: str, title: str, links: list[str]) -> None:
        await self.sink.emit(
            NodeProposed(**self._base("writer"), proposal_id=proposal_id, title=title, links=links)
        )

    async def finished(self, stats: RunStats) -> None:
        await self.sink.emit(RunFinished(**self._base("system"), stats=stats))

    async def error(self, message: str) -> None:
        await self.sink.emit(RunError(**self._base("system"), message=message))
