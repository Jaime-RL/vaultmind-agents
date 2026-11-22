from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import get_services
from api.session import owner_of
from app.config import Settings, get_settings
from app.contracts import Proposal, ProposalAction
from app.services import Services
from vault.writer import UnsafeWriteError, write_copilot_note

router = APIRouter(tags=["proposals"])

ServicesDep = Annotated[Services, Depends(get_services)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/proposals", response_model=list[Proposal])
async def list_proposals(
    request: Request,
    services: ServicesDep,
    settings: SettingsDep,
    status: Literal["pending", "approved", "rejected"] | None = None,
) -> list[Proposal]:
    """Notas propuestas, las más recientes primero. ?status=pending: las que faltan por revisar.

    En modo público, solo las del visitante que pregunta.
    """
    return services.store.list_proposals(status, owner=owner_of(request, settings))


@router.post("/proposals/{proposal_id}", response_model=Proposal)
async def resolve_proposal(
    proposal_id: str,
    action: ProposalAction,
    request: Request,
    services: ServicesDep,
    settings: SettingsDep,
) -> Proposal:
    """Aprueba (escribe la nota en _copilot/) o rechaza una propuesta pendiente."""
    proposal = services.store.get_proposal(proposal_id)
    owner = owner_of(request, settings)
    # En modo público, la propuesta de otro visitante «no existe» para ti (404, no 403:
    # así no se puede averiguar qué ids existen).
    if proposal is None or (
        owner is not None and services.store.proposal_owner(proposal_id) != owner
    ):
        raise HTTPException(status_code=404, detail="Propuesta no encontrada")
    if proposal.status != "pending":
        raise HTTPException(status_code=409, detail=f"La propuesta ya está {proposal.status}")

    if action.action == "reject":
        return services.store.set_proposal_status(proposal_id, "rejected")
    if settings.public_mode:
        # No se escribe en la bóveda compartida: la nota aprobada queda en la base de datos
        # y /api/vault la añade al grafo solo para este visitante.
        return services.store.set_proposal_status(proposal_id, "approved")

    try:
        path = write_copilot_note(settings.vault_path, proposal.title, proposal.markdown)
    except (UnsafeWriteError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo guardar la nota: {exc}") from exc
    return services.store.set_proposal_status(proposal_id, "approved", file_path=path)
