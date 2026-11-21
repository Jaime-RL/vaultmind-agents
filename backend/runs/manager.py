"""Lanza investigaciones en segundo plano y reparte sus eventos en directo.

POST /api/research no espera a que termine la investigación (tarda minutos):
crea una tarea asyncio y devuelve el run_id al momento. El navegador se
suscribe después a /api/research/{run_id}/events y recibe:

1. los eventos que ya ocurrieron (por si se conecta tarde o recarga), y
2. los nuevos según llegan, hasta `run_finished` o `error`.

Cada evento se guarda también en SQLite, así una investigación terminada se
puede volver a reproducir aunque el servidor se haya reiniciado.
"""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from pathlib import Path

from agents import Emitter, Tool, run_research
from agents.events import Event
from router import SmartRoute
from store import Store
from vault import parse_vault

logger = logging.getLogger(__name__)

TERMINAL = {"run_finished", "error"}


class RunNotFoundError(KeyError):
    pass


class LLMNotConfiguredError(RuntimeError):
    """No hay clave de API o modelos configurados: no se puede investigar."""


class LiveRun:
    """Eventos de una investigación en curso, con aviso a los suscriptores."""

    def __init__(self) -> None:
        self.events: list[dict] = []
        self.done = False
        self.changed = asyncio.Condition()


class RunSink:
    """Destino de eventos: SQLite + suscriptores en directo."""

    def __init__(self, run_id: str, store: Store, live: LiveRun):
        self.run_id, self.store, self.live = run_id, store, live

    async def emit(self, event: Event) -> None:
        data = event.model_dump(mode="json")
        self.store.add_event(self.run_id, event.model_dump_json())
        if event.type in TERMINAL:
            self.store.finish_run(
                self.run_id, "finished" if event.type == "run_finished" else "error"
            )
        async with self.live.changed:
            self.live.events.append(data)
            self.live.done = event.type in TERMINAL
            self.live.changed.notify_all()


class RunManager:
    def __init__(
        self,
        *,
        store: Store,
        vault_path: Path,
        router_factory: Callable[[], SmartRoute] | None,
        search_tool: Tool,
        max_gaps: int = 3,
    ):
        # router_factory es None si falta configurar el LLM (sin clave o sin modelos).
        self.store = store
        self.vault_path = vault_path
        self.router_factory = router_factory
        self.search_tool = search_tool
        self.max_gaps = max_gaps
        self._live: dict[str, LiveRun] = {}
        self._tasks: set[asyncio.Task] = set()

    async def start(self, topic: str) -> str:
        if self.router_factory is None:
            raise LLMNotConfiguredError(
                "Falta configurar el LLM: define LLM_API_KEY, SLM_MODEL y LARGE_MODEL"
            )
        vault = parse_vault(self.vault_path)  # VaultNotFoundError si no existe

        run_id = f"run-{uuid.uuid4().hex[:12]}"
        self.store.create_run(run_id, topic)
        live = self._live[run_id] = LiveRun()

        router = self.router_factory()
        # Cada métrica se guarda en cuanto se produce (para /api/metrics).
        router.on_record = self.store.add_metric
        emitter = Emitter(run_id, RunSink(run_id, self.store, live))

        async def save_proposal(proposal) -> None:
            self.store.save_proposal(proposal)

        task = asyncio.create_task(
            run_research(
                topic=topic,
                vault=vault,
                router=router,
                emitter=emitter,
                search_tool=self.search_tool,
                on_proposal=save_proposal,
                max_gaps=self.max_gaps,
            ),
            name=run_id,
        )
        # Guardamos la referencia: asyncio solo guarda referencias débiles a las tareas.
        self._tasks.add(task)
        task.add_done_callback(self._on_done)
        return run_id

    def _on_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.error("La investigación %s falló", task.get_name(), exc_info=task.exception())

    async def wait_all(self) -> None:
        """Espera a que acaben las investigaciones en curso (tests y apagado ordenado)."""
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def cancel_all(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        await self.wait_all()

    async def stream(self, run_id: str) -> AsyncIterator[dict]:
        """Eventos de una investigación: primero los pasados, luego los nuevos."""
        live = self._live.get(run_id)
        if live is None:
            # No está en memoria: o terminó antes de un reinicio, o no existe.
            if self.store.get_run(run_id) is None:
                raise RunNotFoundError(run_id)
            for event in self.store.list_events(run_id):
                yield event
            return

        sent = 0
        while True:
            async with live.changed:
                # Espera hasta que haya eventos nuevos o la investigación termine.
                # (n=sent fija el valor actual dentro de la lambda definida en el bucle)
                await live.changed.wait_for(lambda n=sent: len(live.events) > n or live.done)
                pending = live.events[sent:]
                done = live.done
            for event in pending:
                yield event
            sent += len(pending)
            if done and sent == len(live.events):
                return

    def exists(self, run_id: str) -> bool:
        return run_id in self._live or self.store.get_run(run_id) is not None
