import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from api.deps import get_services
from api.session import owner_of
from app.config import Settings, get_settings
from app.contracts import ResearchRequest, ResearchResponse
from app.services import Services
from runs import (
    DailyQuotaExceededError,
    LLMNotConfiguredError,
    RunNotFoundError,
    TooManyRunsError,
)
from vault import VaultNotFoundError

router = APIRouter(tags=["research"])

ServicesDep = Annotated[Services, Depends(get_services)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def client_ip(request: Request) -> str | None:
    """IP real de quien hace la petición, para el cupo por IP.

    Detrás del proxy de Render (o de cualquier plataforma), la IP de la conexión es la del
    proxy, y la del cliente llega en X-Forwarded-For. Se toma la ÚLTIMA entrada: es la que
    añade el proxy de la plataforma. Las anteriores las puede escribir el propio cliente
    para hacerse pasar por otra IP y saltarse el cupo.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        last = forwarded.split(",")[-1].strip()
        if last:
            return last
    return request.client.host if request.client else None


@router.post("/research", response_model=ResearchResponse)
async def start_research(
    body: ResearchRequest, request: Request, services: ServicesDep, settings: SettingsDep
) -> ResearchResponse:
    """Lanza una investigación en segundo plano y devuelve su run_id al momento."""
    try:
        run_id = await services.runs.start(
            body.topic.strip(), client_ip=client_ip(request), owner=owner_of(request, settings)
        )
    except (TooManyRunsError, DailyQuotaExceededError) as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
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
