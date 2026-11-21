import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.config import Settings
from app.main import create_app
from app.services import Services
from store import Store
from tests.test_runs import make_manager

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((REPO_ROOT / "contracts" / "metrics.schema.json").read_text("utf-8"))


@pytest.fixture
def vault_dir(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "SLM.md").write_text("Ver [[LoRA]] y [[Routing]].", encoding="utf-8")
    return vault


@pytest.fixture
def client(vault_dir):
    store = Store()
    services = Services(store=store, runs=make_manager(store, vault_dir))
    app = create_app(Settings(_env_file=None, vault_path=vault_dir), services=services)
    with TestClient(app) as c:
        yield c


def run_to_completion(client) -> str:
    run_id = client.post("/api/research", json={"topic": "SLMs"}).json()["run_id"]
    with client.stream("GET", f"/api/research/{run_id}/events") as stream:
        list(stream.iter_lines())  # consumir hasta run_finished
    return run_id


def test_empty_metrics(client):
    body = client.get("/api/metrics").json()

    Draft202012Validator(SCHEMA).validate(body)
    assert body["tasks"] == []
    assert body["totals"]["tasks"] == 0


def test_metrics_after_a_run_match_run_finished(client):
    run_id = run_to_completion(client)

    body = client.get(f"/api/metrics?run_id={run_id}").json()

    Draft202012Validator(SCHEMA).validate(body)
    assert len(body["tasks"]) == 5
    assert {t["tier"] for t in body["tasks"]} == {"slm", "large"}
    assert body["totals"]["savings_usd"] > 0
    # Las cifras del panel coinciden con las del evento final de la investigación.
    with client.stream("GET", f"/api/research/{run_id}/events") as stream:
        last = [line for line in stream.iter_lines() if line.startswith("data:")][-1]
    stats = json.loads(last[len("data:") :])["stats"]
    assert body["totals"]["cost_usd"] == pytest.approx(stats["cost_usd"])
    assert body["totals"]["savings_usd"] == pytest.approx(stats["savings_usd"])


def test_metrics_aggregate_all_runs_by_default(client):
    first = run_to_completion(client)
    run_to_completion(client)

    assert client.get("/api/metrics").json()["totals"]["tasks"] == 10
    assert client.get(f"/api/metrics?run_id={first}").json()["totals"]["tasks"] == 5


def test_unknown_run_returns_404(client):
    assert client.get("/api/metrics?run_id=run-nope").status_code == 404
