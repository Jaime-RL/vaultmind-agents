from pathlib import Path

from app.config import Settings


def test_starts_without_env_file(monkeypatch):
    # Simula una máquina limpia: ninguna variable definida y sin .env.
    for var in ("LLM_BASE_URL", "LLM_API_KEY", "SLM_MODEL", "LARGE_MODEL", "VAULT_PATH"):
        monkeypatch.delenv(var, raising=False)

    settings = Settings(_env_file=None)

    assert settings.llm_base_url.startswith("https://")
    assert settings.vault_path == Path("demo-vault")
    assert settings.llm_api_key.get_secret_value() == ""


def test_reads_environment_variables(monkeypatch):
    monkeypatch.setenv("SLM_MODEL", "small-model")
    monkeypatch.setenv("LARGE_MODEL", "large-model")
    monkeypatch.setenv("VAULT_PATH", "/vaults/mine")

    settings = Settings(_env_file=None)

    assert settings.slm_model == "small-model"
    assert settings.large_model == "large-model"
    assert settings.vault_path == Path("/vaults/mine")


def test_api_key_is_not_leaked_in_repr(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-super-secret")

    settings = Settings(_env_file=None)

    assert "sk-super-secret" not in repr(settings)
