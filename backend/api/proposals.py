from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_services
from app.config import Settings, get_settings
from app.contracts import Proposal, ProposalAction
from app.services import Services
from vault.writer import UnsafeWriteError, write_copilot_note

router = APIRouter(tags=["proposals"])

ServicesDep = Annotated[Services, Depends(get_services)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/proposals", response_model=list[Proposal])
async def list_proposals(
    services: ServicesDep,
    status: Literal["pending", "approved", "rejected"] | None = None,
) -> list[Proposal]:
    """Notas propuestas, las más recientes primero. ?status=pending: las que faltan por revisar."""
    return services.store.list_proposals(status)


@router.post("/proposals/{proposal_id}", response_model=Proposal)
async def resolve_proposal(
    proposal_id: str, action: ProposalAction, services: ServicesDep, settings: SettingsDep
) -> Proposal:
    """Aprueba (escribe la nota en _copilot/) o rechaza una propuesta pendiente."""
    proposal = services.store.get_proposal(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Propuesta no encontrada")
    if proposal.status != "pending":
        raise HTTPException(status_code=409, detail=f"La propuesta ya está {proposal.status}")

    if action.action == "reject":
        return services.store.set_proposal_status(proposal_id, "rejected")

    try:
        path = write_copilot_note(settings.vault_path, proposal.title, proposal.markdown)
    except (UnsafeWriteError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo guardar la nota: {exc}") from exc
    return services.store.set_proposal_status(proposal_id, "approved", file_path=path)
