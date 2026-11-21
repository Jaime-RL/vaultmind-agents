from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Comprobación de vida para Docker y la plataforma de despliegue."""
    return {"status": "ok"}
