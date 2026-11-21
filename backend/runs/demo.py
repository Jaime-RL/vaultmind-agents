"""Modo demo: reproduce una investigación grabada como si ocurriera ahora.

Es lo que sirve la URL pública. Pasa por el mismo camino que una investigación
real (RunSink → SQLite + SSE), así que la interfaz, la aprobación de notas y
las métricas funcionan igual, pero sin llamar a ningún modelo ni gastar saldo.

Cada reproducción es una investigación nueva: run_id e ids de propuestas nuevos,
y marcas de tiempo actuales, respetando el ritmo original (dividido por `speed`).
"""

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import TypeAdapter

from app.contracts import AgentEvent, AgentThought, Proposal, RunError, TaskMetric
from runs.sink import RunSink
from store import Store

EVENT_ADAPTER = TypeAdapter(AgentEvent)


@dataclass(frozen=True)
class DemoRun:
    topic: str
    events: list[dict]
    proposals: list[Proposal]
    metrics: list[tuple[TaskMetric, float]]  # (métrica, coste de referencia)
    speed: float = 1.0

    @classmethod
    def load(cls, path: Path, speed: float = 1.0) -> "DemoRun":
        path = Path(path)
        if not path.is_file():
            # Fallo típico al desplegar: la imagen no incluye fixtures/. Mejor decirlo claro
            # al arrancar que fallar en la primera investigación.
            raise FileNotFoundError(
                f"DEMO_MODE=true pero no existe {path}. "
                "Incluye la carpeta fixtures/ en la imagen o desactiva el modo demo."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            topic=data["topic"],
            events=data["events"],
            proposals=[Proposal.model_validate(p) for p in data["proposals"]],
            metrics=[
                (TaskMetric.model_validate(m["metric"]), m["baseline_cost_usd"])
                for m in data["metrics"]
            ],
            speed=speed,
        )


async def play_demo(
    demo: DemoRun, run_id: str, requested_topic: str, sink: RunSink, reason: str | None = None
) -> None:
    """Reproduce la demo. Como una investigación real, termina siempre con run_finished o error."""
    try:
        await _play(demo, run_id, requested_topic, sink, reason)
    except Exception as exc:  # noqa: BLE001 — el flujo SSE debe cerrarse pase lo que pase
        await sink.emit(
            RunError(
                run_id=run_id,
                ts=datetime.now(UTC),
                agent="system",
                message=f"La demostración se detuvo: {exc}",
            )
        )


async def _play(
    demo: DemoRun, run_id: str, requested_topic: str, sink: RunSink, reason: str | None
) -> None:
    store: Store = sink.store
    # Ids de propuesta nuevos: aprobar en una reproducción no afecta a las demás.
    new_ids = {p.id: f"p-{uuid.uuid4().hex[:8]}" for p in demo.proposals}
    proposals = {p.id: p for p in demo.proposals}
    metrics = iter(demo.metrics)

    # Transparencia: el usuario sabe que es una grabación y sobre qué tema era.
    await sink.emit(
        AgentThought(
            run_id=run_id,
            ts=datetime.now(UTC),
            agent="system",
            text=demo_notice(requested_topic, demo.topic, reason),
        )
    )

    previous_ts: datetime | None = None
    for raw in demo.events:
        original_ts = datetime.fromisoformat(raw["ts"])
        if previous_ts is not None and demo.speed > 0:
            await asyncio.sleep((original_ts - previous_ts).total_seconds() / demo.speed)
        previous_ts = original_ts

        data = {**raw, "run_id": run_id, "ts": datetime.now(UTC)}
        if data["type"] == "node_proposed":
            old_id = data["proposal_id"]
            data["proposal_id"] = new_ids[old_id]
            store.save_proposal(
                proposals[old_id].model_copy(
                    update={"id": new_ids[old_id], "run_id": run_id, "created_at": data["ts"]}
                )
            )
        if data["type"] == "tool_call" and "proposal_id" in data.get("args", {}):
            data["args"] = {**data["args"], "proposal_id": new_ids[data["args"]["proposal_id"]]}
        if data["type"] == "route_decision":
            metric, baseline = next(metrics)
            store.add_metric(metric.model_copy(update={"run_id": run_id}), baseline)

        await sink.emit(EVENT_ADAPTER.validate_python(data))


def demo_notice(requested: str, recorded: str, reason: str | None = None) -> str:
    """Aviso inicial: deja claro que es una grabación, sobre qué tema y, si procede, por qué."""
    tail = (
        f"se reproduce una investigación grabada sobre «{recorded}». No se llama a ningún modelo."
    )
    if reason is not None and "cupo" in reason:
        return f"Se ha agotado {reason}, así que en lugar de investigar «{requested}» {tail}"
    prefix = f"Modo demostración ({reason})" if reason else "Modo demostración"
    if requested.strip().lower() == recorded.strip().lower():
        return f"{prefix}: {tail}"
    return f"{prefix}: pediste «{requested}», pero {tail}"
