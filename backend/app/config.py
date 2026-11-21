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
    # SLM elegido: Qwen2.5 7B Instruct (admite tool calling y salida JSON en OpenRouter).
    slm_model: str = "qwen/qwen-2.5-7b-instruct"
    large_model: str = ""

    # Precios en USD por millón de tokens (entrada / salida) para calcular coste y ahorro.
    # SLM: precio publicado en OpenRouter para Qwen2.5 7B Instruct (consultado el 21-11-2026).
    # Modelo grande: valores ORIENTATIVOS hasta elegirlo; pon los publicados del que uses.
    slm_price_input: float = 0.10
    slm_price_output: float = 0.20
    large_price_input: float = 3.00
    large_price_output: float = 15.00

    vault_path: Path = REPO_ROOT / "demo-vault"
    database_path: Path = REPO_ROOT / "data" / "vaultmind.db"

    # Modo demo: POST /api/research reproduce una investigación grabada (fixtures/demo_run.json)
    # en lugar de llamar a modelos reales. Es lo que se publica en la URL pública: funciona sin
    # clave de API y nadie puede gastar saldo. demo_speed > 1 la reproduce más rápido.
    demo_mode: bool = False
    demo_speed: float = 1.0

    # Orígenes que pueden llamar a la API desde el navegador (el dev server de Vite por defecto).
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    """Devuelve una única instancia de Settings (sustituible en tests con dependency_overrides)."""
    return Settings()
