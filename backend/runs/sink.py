"""Destino de los eventos de una investigación: SQLite + suscriptores en directo."""

import asyncio

from agents.events import Event
from store import Store

TERMINAL = {"run_finished", "error"}


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
