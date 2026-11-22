from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import get_services
from api.session import owner_of
from app.config import Settings, get_settings
from app.contracts import VaultGraph
from vault import VaultNotFoundError, parse_vault

router = APIRouter(tags=["vault"])


@router.get("/vault", response_model=VaultGraph)
async def get_vault(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> VaultGraph:
    """La bóveda como grafo (contracts/vault_graph.schema.json).

    Se parsea en cada petición: con bóvedas de decenas o cientos de notas tarda
    milisegundos y así siempre refleja las notas recién aprobadas. Si crece mucho,
    el siguiente paso sería cachear invalidando por fecha de modificación.
    """
    try:
        # En modo público se añaden, solo para este visitante, las notas que ha aprobado.
        owner = owner_of(request, settings)
        extra = get_services(request).runs.approved_notes(owner) if owner else None
        return parse_vault(settings.vault_path, extra).to_graph()
    except VaultNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Bóveda no encontrada") from exc
