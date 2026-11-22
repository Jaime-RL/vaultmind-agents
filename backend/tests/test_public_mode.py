"""Modo público: cada visitante (cookie anónima) solo ve y resuelve sus propuestas, y lo que
aprueba no se escribe en la bóveda compartida. Dos TestClient = dos navegadores distintos."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import Services
from runs import RunManager
from store import Store
from tests.conftest import fake_search_tool
from tests.test_api_proposals import proposal


@pytest.fixture
def vault_dir(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "SLM.md").write_text("Ver [[LoRA]].", encoding="utf-8")
    return vault


def build(vault_dir, public: bool):
    store = Store()
    runs = RunManager(
        store=store, vault_path=vault_dir, router_factory=None, search_tool=fake_search_tool()
    )
    app = create_app(
        Settings(_env_file=None, vault_path=vault_dir, public_mode=public),
        services=Services(store=store, runs=runs),
    )
    return app, store


def owned_proposal(store: Store, owner: str, pid: str, title: str) -> None:
    run_id = f"run-{pid}"
    store.create_run(run_id, "tema", owner=owner)
    store.save_proposal(proposal(pid, title).model_copy(update={"run_id": run_id}))


def session_of(client: TestClient) -> str:
    client.get("/api/health")
    return client.cookies["vm_session"]


def test_each_visitor_only_sees_and_resolves_their_proposals(vault_dir):
    app, store = build(vault_dir, public=True)
    with TestClient(app) as ana, TestClient(app) as bea:
        owned_proposal(store, session_of(ana), "p-ana", "LoRA")
        owned_proposal(store, session_of(bea), "p-bea", "Routing")

        assert [p["id"] for p in ana.get("/api/proposals").json()] == ["p-ana"]
        assert [p["id"] for p in bea.get("/api/proposals").json()] == ["p-bea"]
        # Bea no puede aprobar la nota de Ana: para ella no existe.
        assert bea.post("/api/proposals/p-ana", json={"action": "approve"}).status_code == 404
        assert store.get_proposal("p-ana").status == "pending"


def test_approving_in_public_mode_does_not_touch_the_shared_vault(vault_dir):
    app, store = build(vault_dir, public=True)
    with TestClient(app) as ana, TestClient(app) as bea:
        owned_proposal(store, session_of(ana), "p-ana", "LoRA")

        response = ana.post("/api/proposals/p-ana", json={"action": "approve"})

        assert response.status_code == 200 and response.json()["status"] == "approved"
        assert not (vault_dir / "_copilot").exists()  # nada escrito en disco
        # Ana ve su nota en el grafo (y enlazada); Bea ve la bóveda original.
        ana_graph = ana.get("/api/vault").json()
        assert "_copilot/LoRA" in {n["id"] for n in ana_graph["nodes"]}
        assert {"source": "_copilot/LoRA", "target": "SLM"} in ana_graph["links"]
        assert "_copilot/LoRA" not in {n["id"] for n in bea.get("/api/vault").json()["nodes"]}


def test_local_mode_keeps_writing_to_the_vault_and_sharing_proposals(vault_dir):
    app, store = build(vault_dir, public=False)
    with TestClient(app) as ana, TestClient(app) as bea:
        owned_proposal(store, "otra-sesion", "p-1", "LoRA")

        assert [p["id"] for p in bea.get("/api/proposals").json()] == ["p-1"]
        assert ana.post("/api/proposals/p-1", json={"action": "approve"}).status_code == 200
        assert (vault_dir / "_copilot" / "LoRA.md").exists()


def test_session_cookie_is_opaque_httponly_and_tampering_is_replaced(vault_dir):
    app, _ = build(vault_dir, public=True)
    with TestClient(app) as client:
        response = client.get("/api/health")
        cookie = response.headers["set-cookie"]
        assert "HttpOnly" in cookie and "SameSite=lax" in cookie
        first = client.cookies["vm_session"]

        client.get("/api/health")  # con cookie válida no se renueva
        assert client.cookies["vm_session"] == first

        client.cookies.clear()
        client.cookies.set("vm_session", "<script>")  # manipulada → sesión nueva
        renewed = client.get("/api/health").headers["set-cookie"]
        assert renewed.startswith("vm_session=") and first not in renewed


def test_demo_cleanup_only_removes_the_same_visitors_pending_demo_notes():
    store = Store()
    for owner, pid in (("ana", "p-ana"), ("bea", "p-bea")):
        store.create_run(f"run-{pid}", "tema", mode="demo", owner=owner)
        store.save_proposal(proposal(pid).model_copy(update={"run_id": f"run-{pid}"}))

    assert store.delete_pending_demo_proposals("ana") == 1
    assert [p.id for p in store.list_proposals()] == ["p-bea"]


def test_parse_vault_adds_virtual_notes_without_overriding_disk(vault_dir):
    from vault import parse_vault

    vault = parse_vault(vault_dir, {"_copilot/LoRA.md": "Ver [[SLM]].", "SLM.md": "pisado"})

    assert vault.notes["_copilot/LoRA"].links == ("SLM",)
    assert vault.notes["SLM"].content == "Ver [[LoRA]]."  # el disco manda
    assert "LoRA" not in vault.unresolved_links()  # la laguna queda cubierta
