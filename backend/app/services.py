"""Construye los servicios de la aplicación a partir de la configuración.

Es el único sitio que conoce las implementaciones reales (OpenAI, arXiv,
SQLite). Los tests construyen sus propios Services con piezas falsas.
"""

from dataclasses import dataclass

import httpx

from agents import ArxivClient
from app.config import REPO_ROOT, Settings
from llm.openai_compat import OpenAICompatClient
from router import ModelPrice, SmartRoute
from runs import RunManager
from runs.demo import DemoRun
from store import Store

DEMO_FILE = REPO_ROOT / "fixtures" / "demo_run.json"


@dataclass
class Services:
    store: Store
    runs: RunManager


def build_services(
    settings: Settings,
    *,
    llm_http: httpx.AsyncClient | None = None,
    arxiv_http: httpx.AsyncClient | None = None,
    arxiv_min_interval: float = 3.0,
) -> Services:
    """Los parámetros con * solo se usan en tests de punta a punta, para simular la red."""
    store = Store(settings.database_path)
    return Services(
        store=store,
        runs=RunManager(
            store=store,
            vault_path=settings.vault_path,
            router_factory=router_factory(settings, llm_http),
            search_tool=ArxivClient(http=arxiv_http, min_interval=arxiv_min_interval).as_tool(),
            demo=(
                DemoRun.load(DEMO_FILE, speed=settings.demo_speed) if settings.demo_mode else None
            ),
            max_concurrent=settings.max_concurrent_runs,
            retention_s=settings.finished_run_retention_s,
        ),
    )


def router_factory(settings: Settings, http_client: httpx.AsyncClient | None = None):
    """Devuelve cómo crear un SmartRoute, o None si el LLM no está configurado."""
    api_key = settings.llm_api_key.get_secret_value()
    if not (api_key and settings.slm_model and settings.large_model):
        return None
    client = OpenAICompatClient(
        base_url=settings.llm_base_url, api_key=api_key, http_client=http_client
    )

    def factory() -> SmartRoute:
        # Un SmartRoute por investigación: sus registros solo contienen esa investigación.
        return SmartRoute(
            client=client,
            slm_model=settings.slm_model,
            large_model=settings.large_model,
            slm_price=ModelPrice(settings.slm_price_input, settings.slm_price_output),
            large_price=ModelPrice(settings.large_price_input, settings.large_price_output),
        )

    return factory
