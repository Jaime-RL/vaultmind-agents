import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.config import Settings
from app.contracts import Proposal
from app.main import create_app
from app.services import Services
from runs import RunManager
from store import Store
from tests.conftest import fake_search_tool

REPO_ROOT = Path(__file__).resolve().parents[2]
PROPOSAL_SCHEMA = json.loads((REPO_ROOT / "contracts" / "proposal.schema.json").read_text("utf-8"))
T0 = datetime(2026, 11, 26, 9, 0, tzinfo=UTC)


def schema(name: str) -> dict:
    return {"$defs": PROPOSAL_SCHEMA["$defs"], "$ref": f"#/$defs/{name}"}


def proposal(pid: str, title: str = "LoRA", minutes: int = 0) -> Proposal:
    return Proposal(
        id=pid,
        run_id="run-1",
        title=title,
        markdown=f"# {title}\n\nVer [[SLM]].",
        sources=[{"title": "Example", "url": "http://arxiv.org/abs/0000.00001v1"}],
        links=["SLM"],
        agent="writer",
        model="large",
        status="pending",
        created_at=T0 + timedelta(minutes=minutes),
    )


@pytest.fixture
def vault_dir(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "SLM.md").write_text("Ver [[LoRA]].", encoding="utf-8")
    return vault


@pytest.fixture
def client(vault_dir):
    store = Store()
    store.save_proposal(proposal("p-1", "LoRA", minutes=0))
    store.save_proposal(proposal("p-2", "Routing", minutes=1))
    runs = RunManager(
        store=store, vault_path=vault_dir, router_factory=None, search_tool=fake_search_tool()
    )
    app = create_app(
        Settings(_env_file=None, vault_path=vault_dir), services=Services(store=store, runs=runs)
    )
    with TestClient(app) as c:
        yield c


def test_lists_proposals_newest_first(client):
    response = client.get("/api/proposals")

    assert response.status_code == 200
    body = response.json()
    Draft202012Validator(schema("ProposalList")).validate(body)
    assert [p["id"] for p in body] == ["p-2", "p-1"]


def test_filters_by_status(client):
    client.post("/api/proposals/p-1", json={"action": "reject"})

    assert [p["id"] for p in client.get("/api/proposals?status=pending").json()] == ["p-2"]
    assert [p["id"] for p in client.get("/api/proposals?status=rejected").json()] == ["p-1"]
    assert client.get("/api/proposals?status=otro").status_code == 422


def test_approve_writes_note_and_updates_graph(client, vault_dir):
    response = client.post("/api/proposals/p-1", json={"action": "approve"})

    assert response.status_code == 200
    body = response.json()
    Draft202012Validator(schema("Proposal")).validate(body)
    assert body["status"] == "approved"
    note = vault_dir / "_copilot" / "LoRA.md"
    assert note.read_text(encoding="utf-8").startswith("# LoRA")
    # La nota nueva aparece en el grafo y la laguna queda cubierta.
    graph = client.get("/api/vault").json()
    assert {"source": "SLM", "target": "_copilot/LoRA"} in graph["links"]


def test_reject_does_not_touch_the_vault(client, vault_dir):
    response = client.post("/api/proposals/p-1", json={"action": "reject"})

    assert response.json()["status"] == "rejected"
    assert not (vault_dir / "_copilot").exists()


def test_cannot_resolve_twice(client):
    client.post("/api/proposals/p-1", json={"action": "approve"})

    response = client.post("/api/proposals/p-1", json={"action": "reject"})

    assert response.status_code == 409
    assert "approved" in response.json()["detail"]


def test_unknown_proposal_and_invalid_action(client):
    assert client.post("/api/proposals/p-nope", json={"action": "approve"}).status_code == 404
    assert client.post("/api/proposals/p-1", json={"action": "borrar"}).status_code == 422


def test_approve_with_edited_markdown_saves_the_users_version(client, vault_dir):
    edited = "# LoRA\n\nMi versión: entrena matrices de bajo rango. Sin enlaces."

    response = client.post("/api/proposals/p-1", json={"action": "approve", "markdown": edited})

    body = response.json()
    assert body["markdown"] == edited
    assert body["links"] == []  # los enlaces se recalculan con el texto editado
    assert (vault_dir / "_copilot" / "LoRA.md").read_text(encoding="utf-8").strip() == edited


def test_edited_markdown_cannot_be_empty_or_huge(client):
    empty = client.post("/api/proposals/p-1", json={"action": "approve", "markdown": ""})
    huge = client.post("/api/proposals/p-1", json={"action": "approve", "markdown": "x" * 20_001})

    assert (empty.status_code, huge.status_code) == (422, 422)
    assert client.get("/api/proposals?status=pending").json()[1]["id"] == "p-1"
