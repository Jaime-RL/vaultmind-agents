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
from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path

from agents import Emitter, Tool, run_research
from agents.asker import answer_question
from app.contracts import AskResponse
from router import SmartRoute
from runs.demo import DemoRun, play_demo
from runs.sink import LiveRun, RunSink
from store import Store
from vault import parse_vault
from vault.writer import COPILOT_DIR, safe_note_name

logger = logging.getLogger(__name__)


class RunNotFoundError(KeyError):
    pass


class TooManyRunsError(RuntimeError):
    """Se alcanzó el máximo de investigaciones simultáneas."""


class DailyQuotaExceededError(RuntimeError):
    """Se agotó el cupo diario de investigaciones reales y no hay demo a la que volver."""


class LLMNotConfiguredError(RuntimeError):
    """No hay clave de API o modelos configurados: no se puede investigar."""


class RunManager:
    def __init__(
        self,
        *,
        store: Store,
        vault_path: Path,
        router_factory: Callable[[], SmartRoute] | None,
        search_tool: Tool,
        extra_tools: Sequence[Tool] = (),
        max_gaps: int = 3,
        demo: DemoRun | None = None,
        force_demo: bool = False,
        max_concurrent: int = 3,
        retention_s: float = 300.0,
        max_runs_per_day: int | None = None,
        max_runs_per_ip_per_day: int | None = None,
        max_asks_per_day: int | None = None,
        max_asks_per_ip_per_day: int | None = None,
    ):
        # router_factory es None si falta configurar el LLM (sin clave o sin modelos).
        self.store = store
        self.vault_path = vault_path
        self.router_factory = router_factory
        self.search_tool = search_tool
        self.extra_tools = tuple(extra_tools)  # otras fuentes (Semantic Scholar)
        self.max_gaps = max_gaps
        # La demo se usa siempre si force_demo (DEMO_MODE=true); si no, solo como respaldo
        # cuando no hay LLM configurado o se agota el cupo diario.
        self.demo = demo
        self.force_demo = force_demo
        # Cupo de investigaciones REALES por día (UTC), en total y por IP. Con un proveedor
        # gratuito protege su límite diario; con uno de pago, el gasto. None = sin límite.
        self.max_runs_per_day = max_runs_per_day
        self.max_runs_per_ip_per_day = max_runs_per_ip_per_day
        self.max_asks_per_day = max_asks_per_day
        self.max_asks_per_ip_per_day = max_asks_per_ip_per_day
        # En una URL pública, sin límite cualquiera podría lanzar cientos de investigaciones.
        self.max_concurrent = max_concurrent
        # Tras terminar, una investigación sigue en memoria un rato (para suscriptores que
        # llegan justo al final) y luego se libera: después se reproduce desde SQLite.
        self.retention_s = retention_s
        self._live: dict[str, LiveRun] = {}
        self._tasks: set[asyncio.Task] = set()

    async def start(
        self, topic: str, client_ip: str | None = None, owner: str | None = None
    ) -> str:
        """Lanza una investigación. `owner` (modo público) es la sesión anónima del visitante:
        sus propuestas solo las ve él, y su bóveda incluye las notas que ya ha aprobado."""
        if len(self._tasks) >= self.max_concurrent:
            raise TooManyRunsError(
                f"Ya hay {self.max_concurrent} investigaciones en curso; inténtalo en un momento"
            )
        if self.force_demo and self.demo is not None:
            return self._start_demo(topic, client_ip, owner=owner)
        if self.router_factory is None:
            if self.demo is not None:
                return self._start_demo(
                    topic, client_ip, reason="sin modelo configurado", owner=owner
                )
            raise LLMNotConfiguredError(
                "Falta configurar el LLM: define LLM_API_KEY, SLM_MODEL y LARGE_MODEL"
            )
        quota = self._quota_problem(client_ip)
        if quota is not None:
            if self.demo is not None:
                return self._start_demo(topic, client_ip, reason=quota, owner=owner)
            raise DailyQuotaExceededError(f"Se ha agotado {quota}; vuelve mañana")
        vault = parse_vault(self.vault_path, self.approved_notes(owner))  # o VaultNotFoundError

        run_id = f"run-{uuid.uuid4().hex[:12]}"
        self.store.create_run(run_id, topic, client_ip=client_ip, mode="real", owner=owner)
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
                extra_tools=self.extra_tools,
                on_proposal=save_proposal,
                max_gaps=self.max_gaps,
            ),
            name=run_id,
        )
        self._track(task)
        return run_id

    def _quota_problem(self, client_ip: str | None) -> str | None:
        """Describe qué cupo se ha agotado, o None si aún queda."""
        if (
            self.max_runs_per_day is not None
            and self.store.count_runs_today("real") >= self.max_runs_per_day
        ):
            return "el cupo gratuito de investigaciones de hoy"
        if (
            self.max_runs_per_ip_per_day is not None
            and client_ip is not None
            and self.store.count_runs_today("real", client_ip) >= self.max_runs_per_ip_per_day
        ):
            return "tu cupo de investigaciones de hoy"
        return None

    async def ask(
        self, question: str, client_ip: str | None = None, owner: str | None = None
    ) -> AskResponse:
        """Responde una pregunta con las notas de la bóveda (y las aprobadas del visitante).

        Sin LLM configurado o con el cupo de preguntas agotado no da error: responde
        señalando las notas relevantes, sin redactar (no cuesta nada).
        """
        vault = parse_vault(self.vault_path, self.approved_notes(owner))
        use_llm = self.router_factory is not None and not self._ask_quota_exhausted(client_ip)
        run_id = f"ask-{uuid.uuid4().hex[:12]}"
        router = None
        if use_llm:
            assert self.router_factory is not None
            router = self.router_factory()
            router.on_record = (
                self.store.add_metric
            )  # las preguntas también cuentan en /api/metrics
            self.store.create_run(
                run_id, question[:200], client_ip=client_ip, mode="ask", owner=owner
            )
        try:
            return await answer_question(
                question=question, vault=vault, router=router, run_id=run_id
            )
        finally:
            if use_llm:
                self.store.finish_run(run_id, "finished")

    def _ask_quota_exhausted(self, client_ip: str | None) -> bool:
        if self.max_asks_per_day is not None and (
            self.store.count_runs_today("ask") >= self.max_asks_per_day
        ):
            return True
        return (
            self.max_asks_per_ip_per_day is not None
            and client_ip is not None
            and self.store.count_runs_today("ask", client_ip) >= self.max_asks_per_ip_per_day
        )

    def approved_notes(self, owner: str | None) -> dict[str, str]:
        """Notas aprobadas por un visitante (modo público), como ficheros virtuales de la bóveda."""
        if owner is None:
            return {}
        return {
            f"{COPILOT_DIR}/{safe_note_name(p.title)}.md": p.markdown
            for p in reversed(self.store.list_proposals("approved", owner=owner))
        }

    def _start_demo(
        self,
        topic: str,
        client_ip: str | None = None,
        reason: str | None = None,
        owner: str | None = None,
    ) -> str:
        # Una demo nueva sustituye a las notas pendientes de demos anteriores (son las mismas).
        self.store.delete_pending_demo_proposals(owner)
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        self.store.create_run(run_id, topic, client_ip=client_ip, mode="demo", owner=owner)
        live = self._live[run_id] = LiveRun()
        sink = RunSink(run_id, self.store, live)
        self._track(
            asyncio.create_task(play_demo(self.demo, run_id, topic, sink, reason), name=run_id)
        )
        return run_id

    def _track(self, task: asyncio.Task) -> None:
        # Guardamos la referencia: asyncio solo guarda referencias débiles a las tareas.
        self._tasks.add(task)
        task.add_done_callback(self._on_done)

    def _on_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        # Libera la memoria más tarde; los suscriptores activos conservan su referencia.
        asyncio.get_running_loop().call_later(
            self.retention_s, self._live.pop, task.get_name(), None
        )
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
