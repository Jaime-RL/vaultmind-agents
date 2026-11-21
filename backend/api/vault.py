from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.contracts import VaultGraph
from vault import VaultNotFoundError, parse_vault

router = APIRouter(tags=["vault"])


@router.get("/vault", response_model=VaultGraph)
async def get_vault(settings: Annotated[Settings, Depends(get_settings)]) -> VaultGraph:
    """La bóveda como grafo (contracts/vault_graph.schema.json).

    Se parsea en cada petición: con bóvedas de decenas o cientos de notas tarda
    milisegundos y así siempre refleja las notas recién aprobadas. Si crece mucho,
    el siguiente paso sería cachear invalidando por fecha de modificación.
    """
    try:
        return parse_vault(settings.vault_path).to_graph()
    except VaultNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Bóveda no encontrada") from exc
