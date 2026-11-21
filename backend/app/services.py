"""Construye los servicios de la aplicación a partir de la configuración.

Es el único sitio que conoce las implementaciones reales (OpenAI, arXiv,
SQLite). Los tests construyen sus propios Services con piezas falsas.
"""

from dataclasses import dataclass

from agents import ArxivClient
from app.config import Settings
from llm.openai_compat import OpenAICompatClient
from router import ModelPrice, SmartRoute
from runs import RunManager
from store import Store


@dataclass
class Services:
    store: Store
    runs: RunManager


def build_services(settings: Settings) -> Services:
    store = Store(settings.database_path)
    return Services(
        store=store,
        runs=RunManager(
            store=store,
            vault_path=settings.vault_path,
            router_factory=router_factory(settings),
            search_tool=ArxivClient().as_tool(),
        ),
    )


def router_factory(settings: Settings):
    """Devuelve cómo crear un SmartRoute, o None si el LLM no está configurado."""
    api_key = settings.llm_api_key.get_secret_value()
    if not (api_key and settings.slm_model and settings.large_model):
        return None
    client = OpenAICompatClient(base_url=settings.llm_base_url, api_key=api_key)

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
