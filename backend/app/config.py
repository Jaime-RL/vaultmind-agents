"""Configuración de la aplicación, leída de variables de entorno.

Todas las variables tienen un valor por defecto para que la app (y los tests)
arranquen sin `.env`. Las variables están documentadas en `.env.example`.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raíz del repo (backend/app/config.py → dos niveles arriba). Así la bóveda de
# demostración se encuentra igual arranques el servidor desde la raíz o desde backend/.
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Proveedor de modelos: cualquier API compatible con OpenAI (OpenRouter, Groq...).
    llm_base_url: str = "https://openrouter.ai/api/v1"
    # SecretStr evita que la clave aparezca en logs o en repr(settings).
    llm_api_key: SecretStr = SecretStr("")
    # Misma familia en los dos niveles (Qwen2.5 7B frente a 72B): la comparación mide el efecto
    # del tamaño, no el de cambiar de modelo. Ambos admiten tool calling en OpenRouter.
    slm_model: str = "qwen/qwen-2.5-7b-instruct"
    # Solo para modelos de razonamiento (p. ej. gpt-oss en Groq): "low" gasta menos tokens
    # del cupo gratuito. Vacío = no se envía (los modelos que no lo admiten lo rechazarían).
    llm_reasoning_effort: str | None = None
    large_model: str = "qwen/qwen-2.5-72b-instruct"

    # Precios en USD por millón de tokens (entrada / salida), publicados en OpenRouter
    # (consultados el 21-11-2026). Si cambian, actualízalos para que el ahorro sea real.
    slm_price_input: float = 0.10
    slm_price_output: float = 0.20
    large_price_input: float = 0.36
    large_price_output: float = 0.40

    vault_path: Path = REPO_ROOT / "demo-vault"
    database_path: Path = REPO_ROOT / "data" / "vaultmind.db"

    # Modo demo: POST /api/research reproduce una investigación grabada (fixtures/demo_run.json)
    # en lugar de llamar a modelos reales. Es lo que se publica en la URL pública: funciona sin
    # clave de API y nadie puede gastar saldo. demo_speed > 1 la reproduce más rápido.
    demo_mode: bool = False
    demo_speed: float = 1.0

    # Protección de la API pública: investigaciones a la vez como máximo (las demás reciben 429)
    # y segundos que una investigación terminada sigue en memoria (después se lee de SQLite).
    max_concurrent_runs: int = 3
    finished_run_retention_s: float = 300.0
    # Cupo de investigaciones REALES por día (UTC): en total y por IP. Al agotarse, si existe
    # la grabación, se sirve el modo demo en su lugar. 0 = sin límite.
    max_runs_per_day: int = 10
    max_runs_per_ip_per_day: int = 3
    # Usar la demo como respaldo (sin clave configurada o cupo agotado) en lugar de dar error.
    demo_fallback: bool = True
    # URL pública: cada visitante (cookie anónima) ve y resuelve solo SUS propuestas, y lo que
    # aprueba se guarda en la base de datos para él, sin escribir en la bóveda compartida.
    public_mode: bool = False

    # Carpeta con el frontend compilado (dist/ de Vite). Si existe, FastAPI la sirve en "/"
    # junto a la API: en producción todo es un solo servicio, sin CORS. La define el Dockerfile.
    frontend_dist: Path | None = None

    # Orígenes que pueden llamar a la API desde el navegador (el dev server de Vite por defecto).
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    """Devuelve una única instancia de Settings (sustituible en tests con dependency_overrides)."""
    return Settings()
