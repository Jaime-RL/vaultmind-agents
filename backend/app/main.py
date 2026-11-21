"""Punto de entrada de la API: `uvicorn app.main:app --reload`."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.health import router as health_router
from api.vault import router as vault_router
from app.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Crea la aplicación.

    Usamos una función factoría en lugar de un objeto global para que los tests
    puedan construir apps con configuraciones distintas sin efectos secundarios.
    """
    app = FastAPI(title="VaultMind API", version="0.1.0")
    if settings is None:
        settings = get_settings()
    else:
        # Los endpoints piden la configuración con Depends(get_settings): si nos
        # pasan una concreta (tests), hacemos que todos los endpoints usen esa.
        app.dependency_overrides[get_settings] = lambda: settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(vault_router, prefix="/api")
    return app


app = create_app()
