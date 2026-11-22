from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import get_services
from api.research import client_ip
from api.session import owner_of
from app.config import Settings, get_settings
from app.contracts import AskRequest, AskResponse
from app.services import Services
from llm import LLMError
from vault import VaultNotFoundError

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    request: Request,
    services: Annotated[Services, Depends(get_services)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AskResponse:
    """Responde una pregunta con las notas de la bóveda y las cita como [[nota]]."""
    try:
        return await services.runs.ask(
            body.question.strip(),
            client_ip=client_ip(request),
            owner=owner_of(request, settings),
            language=body.language,
        )
    except VaultNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Bóveda no encontrada") from exc
    except LLMError as exc:
        # El SLM y el modelo grande fallaron: no es culpa del usuario.
        raise HTTPException(status_code=502, detail=f"El modelo no pudo responder: {exc}") from exc
