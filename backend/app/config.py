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
    slm_model: str = ""
    large_model: str = ""

    vault_path: Path = REPO_ROOT / "demo-vault"
    database_path: Path = Path("data/vaultmind.db")

    # Orígenes que pueden llamar a la API desde el navegador (el dev server de Vite por defecto).
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    """Devuelve una única instancia de Settings (sustituible en tests con dependency_overrides)."""
    return Settings()
