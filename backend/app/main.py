"""Punto de entrada de la API: `uvicorn app.main:app --reload`."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.health import router as health_router
from api.research import router as research_router
from api.vault import router as vault_router
from app.config import Settings, get_settings
from app.services import Services, build_services


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    """Crea la aplicación.

    Usamos una función factoría en lugar de un objeto global para que los tests
    puedan construir apps con configuraciones y servicios distintos.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Los servicios reales se crean al arrancar (abre SQLite) y se cierran al parar.
        if not hasattr(app.state, "services"):
            app.state.services = build_services(settings)
        yield
        await app.state.services.runs.cancel_all()
        app.state.services.store.close()

    app = FastAPI(title="VaultMind API", version="0.1.0", lifespan=lifespan)
    if settings is None:
        settings = get_settings()
    else:
        # Los endpoints piden la configuración con Depends(get_settings): si nos
        # pasan una concreta (tests), hacemos que todos los endpoints usen esa.
        app.dependency_overrides[get_settings] = lambda: settings
    if services is not None:
        app.state.services = services

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(vault_router, prefix="/api")
    app.include_router(research_router, prefix="/api")
    return app


app = create_app()
