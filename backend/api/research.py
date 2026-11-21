import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from api.deps import get_services
from app.contracts import ResearchRequest, ResearchResponse
from app.services import Services
from runs import LLMNotConfiguredError, RunNotFoundError
from vault import VaultNotFoundError

router = APIRouter(tags=["research"])

ServicesDep = Annotated[Services, Depends(get_services)]


@router.post("/research", response_model=ResearchResponse)
async def start_research(request: ResearchRequest, services: ServicesDep) -> ResearchResponse:
    """Lanza una investigación en segundo plano y devuelve su run_id al momento."""
    try:
        run_id = await services.runs.start(request.topic.strip())
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VaultNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Bóveda no encontrada") from exc
    return ResearchResponse(run_id=run_id)


@router.get("/research/{run_id}/events")
async def research_events(run_id: str, services: ServicesDep) -> EventSourceResponse:
    """Flujo SSE: eventos pasados y nuevos hasta run_finished o error."""
    if not services.runs.exists(run_id):
        raise HTTPException(status_code=404, detail="Investigación no encontrada")

    async def generate():
        try:
            async for event in services.runs.stream(run_id):
                # 'event:' lleva el tipo para que el navegador pueda filtrar con addEventListener.
                yield {"event": event["type"], "data": json.dumps(event, ensure_ascii=False)}
        except RunNotFoundError:
            return

    # ping cada 15 s: evita que proxies o plataformas de despliegue corten la conexión.
    return EventSourceResponse(generate(), ping=15)
