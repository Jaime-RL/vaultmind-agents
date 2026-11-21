from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_services
from app.contracts import Metrics
from app.services import Services

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_model=Metrics)
async def get_metrics(
    services: Annotated[Services, Depends(get_services)], run_id: str | None = None
) -> Metrics:
    """Qué modelo hizo cada tarea, cuánto costó y el ahorro frente a usar siempre el grande.

    Sin run_id: todas las investigaciones. Con run_id: solo esa (404 si no existe).
    Las métricas se leen de SQLite, así que sobreviven a reinicios del servidor.
    """
    if run_id is not None and services.store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Investigación no encontrada")
    tasks, totals = services.store.metrics(run_id)
    return Metrics(tasks=tasks, totals=totals)
