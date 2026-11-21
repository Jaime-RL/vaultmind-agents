"""Modo demo: la versión de la URL pública, sin modelos ni clave de API."""

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import DEMO_FILE, build_services
from router import summarize
from runs import RunManager
from runs.demo import DemoRun
from store import Store
from tests.conftest import fake_search_tool
from vault import parse_vault
from vault.parser import LinkResolver

REPO_ROOT = Path(__file__).resolve().parents[2]
FAST = 1e6  # velocidad de reproducción en tests: sin esperas reales


@pytest.fixture(scope="module")
def demo() -> DemoRun:
    return DemoRun.load(DEMO_FILE, speed=FAST)


@pytest.fixture
def vault_copy(tmp_path) -> Path:
    # Copia de la bóveda de demo: aprobar notas no debe tocar el repo.
    return Path(shutil.copytree(REPO_ROOT / "demo-vault", tmp_path / "vault"))


def manager_for(store: Store, vault: Path, demo: DemoRun) -> RunManager:
    return RunManager(
        store=store,
        vault_path=vault,
        router_factory=None,  # sin LLM: la demo no lo necesita
        search_tool=fake_search_tool(),
        demo=demo,
    )


# --- El fichero de la demo es coherente -------------------------------------------


def test_demo_file_is_consistent(demo):
    from agents.writer import resolve_links

    resolver = LinkResolver(list(parse_vault(REPO_ROOT / "demo-vault").notes))
    proposed = {e["proposal_id"]: e for e in demo.events if e["type"] == "node_proposed"}

    assert set(proposed) == {p.id for p in demo.proposals}
    for proposal in demo.proposals:
        # Los enlaces del evento y de la nota salen del propio Markdown, como en producción.
        assert proposal.links == proposed[proposal.id]["links"]
        assert proposal.links == resolve_links(proposal.markdown, resolver)
        assert all(s.url.startswith("https://arxiv.org/abs/") for s in proposal.sources)
        assert proposal.sources[0].url in proposal.markdown

    routes = [e for e in demo.events if e["type"] == "route_decision"]
    assert len(demo.metrics) == len(routes)
    for (metric, _), route in zip(demo.metrics, routes, strict=True):
        assert (metric.task, metric.tier, metric.escalated) == (
            route["task"],
            route["tier"],
            route["escalated"],
        )

    stats = demo.events[-1]["stats"]
    totals = summarize([m for m, _ in demo.metrics], [b for _, b in demo.metrics])
    assert stats["cost_usd"] == pytest.approx(totals.cost_usd)
    assert stats["savings_usd"] == pytest.approx(totals.savings_usd)


# --- Reproducción ---------------------------------------------------------------


async def test_demo_run_replays_with_fresh_ids(demo, vault_copy):
    store = Store()
    manager = manager_for(store, vault_copy, demo)

    run_id = await manager.start("Mi tema")
    events = [e async for e in manager.stream(run_id)]

    assert events[0]["agent"] == "system"
    assert "Mi tema" in events[0]["text"] and "Modo demostración" in events[0]["text"]
    assert events[-1]["type"] == "run_finished"
    assert {e["run_id"] for e in events} == {run_id}
    assert store.get_run(run_id).status == "finished"

    # Propuestas guardadas con ids nuevos, los mismos que anuncian los eventos.
    saved = {p.id for p in store.list_proposals("pending")}
    announced = {e["proposal_id"] for e in events if e["type"] == "node_proposed"}
    reviewed = {e["args"]["proposal_id"] for e in events if e["type"] == "tool_call"
                if "proposal_id" in e["args"]}  # fmt: skip
    assert saved == announced == reviewed
    assert not saved & {"p-001", "p-002", "p-003"}

    # Las métricas cuadran con el evento final.
    _, totals = store.metrics(run_id)
    assert totals.savings_usd == pytest.approx(events[-1]["stats"]["savings_usd"])


async def test_each_demo_run_is_independent(demo, vault_copy):
    store = Store()
    manager = manager_for(store, vault_copy, demo)

    first = await manager.start("a")
    second = await manager.start("b")
    await manager.wait_all()

    ids = {
        run: {p.id for p in store.list_proposals() if p.run_id == run} for run in (first, second)
    }
    assert len(ids[first]) == len(ids[second]) == 3
    assert not ids[first] & ids[second]
    assert store.metrics()[1].tasks == 2 * len(demo.metrics)


async def test_broken_demo_ends_with_error(demo, vault_copy):
    broken = DemoRun(
        topic="x",
        events=[{**demo.events[0], "type": "tipo_inexistente"}],
        proposals=[],
        metrics=[],
        speed=FAST,
    )
    store = Store()
    manager = manager_for(store, vault_copy, broken)

    run_id = await manager.start("x")
    events = [e async for e in manager.stream(run_id)]

    assert events[-1]["type"] == "error"
    assert store.get_run(run_id).status == "error"


# --- Por HTTP, con el cableado real y sin clave -----------------------------------


def test_demo_mode_works_end_to_end_without_api_key(vault_copy, tmp_path):
    settings = Settings(
        _env_file=None,
        demo_mode=True,
        demo_speed=FAST,
        llm_api_key="",
        vault_path=vault_copy,
        database_path=tmp_path / "demo.db",
    )

    with TestClient(create_app(settings, services=build_services(settings))) as client:
        run_id = client.post("/api/research", json={"topic": "Lo que sea"}).json()["run_id"]
        with client.stream("GET", f"/api/research/{run_id}/events") as stream:
            events = [
                json.loads(line[len("data:") :])
                for line in stream.iter_lines()
                if line.startswith("data:")
            ]
        assert events[-1]["type"] == "run_finished"

        # Aprobar una nota de la demo la escribe en la bóveda y aparece en el grafo.
        proposal = next(p for p in client.get("/api/proposals").json() if p["title"] == "LoRA")
        approved = client.post(f"/api/proposals/{proposal['id']}", json={"action": "approve"})
        assert approved.json()["status"] == "approved"
        graph = client.get("/api/vault").json()
        assert {"source": "modelos/SLM", "target": "_copilot/LoRA"} in graph["links"]
        assert client.get(f"/api/metrics?run_id={run_id}").json()["totals"]["tasks"] == 10


def test_without_demo_mode_and_key_research_is_unavailable(tmp_path):
    settings = Settings(_env_file=None, llm_api_key="", database_path=tmp_path / "x.db")

    with TestClient(create_app(settings, services=build_services(settings))) as client:
        assert client.post("/api/research", json={"topic": "SLMs"}).status_code == 503


def test_missing_demo_file_fails_with_a_clear_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="fixtures/"):
        DemoRun.load(tmp_path / "no-existe.json")
