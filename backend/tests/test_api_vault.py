import json
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.config import Settings
from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((REPO_ROOT / "contracts" / "vault_graph.schema.json").read_text("utf-8"))


def client_for(vault_path: Path) -> TestClient:
    return TestClient(create_app(Settings(_env_file=None, vault_path=vault_path)))


def test_returns_graph_that_matches_contract(tmp_path):
    (tmp_path / "a.md").write_text("Ver [[b]] #tema\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("Nota b\n", encoding="utf-8")

    response = client_for(tmp_path).get("/api/vault")

    assert response.status_code == 200
    body = response.json()
    Draft202012Validator(SCHEMA).validate(body)
    assert body["links"] == [{"source": "a", "target": "b"}]
    assert body["nodes"][0] == {"id": "a", "title": "a", "path": "a.md", "tags": ["tema"]}


def test_missing_vault_returns_404(tmp_path):
    response = client_for(tmp_path / "no-existe").get("/api/vault")

    assert response.status_code == 404
    assert response.json() == {"detail": "Bóveda no encontrada"}


def test_demo_vault_is_served_and_valid():
    # La bóveda de demostración es la que verá la URL pública: debe tener
    # suficientes notas para la demo y ningún enlace a una nota inexistente.
    response = client_for(REPO_ROOT / "demo-vault").get("/api/vault")

    assert response.status_code == 200
    body = response.json()
    Draft202012Validator(SCHEMA).validate(body)
    ids = {node["id"] for node in body["nodes"]}
    assert len(ids) >= 20
    assert all(link["source"] in ids and link["target"] in ids for link in body["links"])


def test_demo_vault_has_gaps_for_the_explorer():
    # El Explorador necesita lagunas que detectar: si alguien «arregla» la bóveda
    # de demo y desaparecen, la demo pierde su punto de partida.
    from vault import parse_vault

    vault = parse_vault(REPO_ROOT / "demo-vault")
    assert len(vault.unresolved_links()) >= 3
