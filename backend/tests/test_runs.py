"""Investigaciones en segundo plano, persistencia de eventos y flujo SSE."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.config import Settings
from app.main import create_app
from app.services import Services
from llm import FakeLLMClient, LLMResponse
from router import ModelPrice, SmartRoute
from runs import LLMNotConfiguredError, RunManager, RunNotFoundError
from store import Store
from tests.conftest import PAPER_URL, calls_tool, fake_search_tool, final

REPO_ROOT = Path(__file__).resolve().parents[2]
EVENTS_SCHEMA = json.loads((REPO_ROOT / "contracts" / "events.schema.json").read_text("utf-8"))
NOTE = "# LoRA\n\n" + "LoRA ajusta modelos con matrices de bajo rango. " * 5 + "Ver [[SLM]]."


def happy_script():
    """Guion de una investigación completa con una laguna."""
    return [
        final({"selected": ["LoRA"]}),
        calls_tool("search_arxiv", query="LoRA"),
        final({"summary": "Resumen", "sources": [{"title": "P", "url": PAPER_URL}]}),
        LLMResponse(content=NOTE, prompt_tokens=900, completion_tokens=300),
        final({"claims": 3, "supported": 3, "issues": []}),
    ]


@pytest.fixture
def vault_dir(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "SLM.md").write_text("Ver [[LoRA]] y [[Routing]].", encoding="utf-8")
    return vault


def make_manager(store, vault_dir, script=None, configured=True) -> RunManager:
    def factory():
        return SmartRoute(
            client=FakeLLMClient(script if script is not None else happy_script()),
            slm_model="small",
            large_model="large",
            slm_price=ModelPrice(0.1, 0.1),
            large_price=ModelPrice(3.0, 15.0),
        )

    return RunManager(
        store=store,
        vault_path=vault_dir,
        router_factory=factory if configured else None,
        search_tool=fake_search_tool(),
    )


# --- RunManager ----------------------------------------------------------------


async def test_run_persists_events_proposals_and_metrics(vault_dir):
    store = Store()
    manager = make_manager(store, vault_dir)

    run_id = await manager.start("SLMs")
    await manager.wait_all()

    events = store.list_events(run_id)
    assert events[-1]["type"] == "run_finished"
    assert store.get_run(run_id).status == "finished"
    [proposal] = store.list_proposals("pending")
    assert proposal.title == "LoRA" and proposal.run_id == run_id
    records, totals = store.metrics(run_id)
    # Una métrica por llamada al LLM: explorador, investigador ×2 (buscar + responder),
    # redactor y revisor.
    assert totals.tasks == 5
    assert totals.savings_usd > 0


async def test_stream_replays_past_events_and_follows_live_ones(vault_dir):
    store = Store()
    manager = make_manager(store, vault_dir)
    run_id = await manager.start("SLMs")

    # Nos suscribimos mientras corre: debe recibir todo y terminar solo.
    received = [event async for event in manager.stream(run_id)]
    await manager.wait_all()

    assert received == store.list_events(run_id)
    assert received[-1]["type"] == "run_finished"


async def test_two_subscribers_get_the_same_events(vault_dir):
    manager = make_manager(Store(), vault_dir)
    run_id = await manager.start("SLMs")

    async def collect():
        return [event async for event in manager.stream(run_id)]

    first, second = await asyncio.gather(collect(), collect())

    assert first == second
    assert first[-1]["type"] == "run_finished"


async def test_finished_run_is_replayed_from_the_database(vault_dir):
    store = Store()
    run_id = await (manager := make_manager(store, vault_dir)).start("SLMs")
    await manager.wait_all()

    # Un gestor nuevo (como tras reiniciar el servidor) no la tiene en memoria.
    restarted = make_manager(store, vault_dir)
    replay = [event async for event in restarted.stream(run_id)]

    assert replay == store.list_events(run_id)


async def test_failed_run_ends_with_error_status(vault_dir):
    store = Store()
    manager = make_manager(store, vault_dir, script=[final({"selected": ["LoRA"]})])
    manager.search_tool = fake_search_tool(error=RuntimeError("bug"))
    manager.router_factory = lambda: SmartRoute(
        client=FakeLLMClient([final({"selected": ["LoRA"]}), calls_tool("search_arxiv", q="x")]),
        slm_model="small",
        large_model="large",
        slm_price=ModelPrice(0.1, 0.1),
        large_price=ModelPrice(3.0, 15.0),
    )

    run_id = await manager.start("SLMs")
    await manager.wait_all()

    assert store.get_run(run_id).status == "error"
    assert store.list_events(run_id)[-1]["type"] == "error"


async def test_unknown_run_raises(vault_dir):
    manager = make_manager(Store(), vault_dir)
    with pytest.raises(RunNotFoundError):
        [event async for event in manager.stream("run-no-existe")]


async def test_start_without_llm_configuration_fails(vault_dir):
    manager = make_manager(Store(), vault_dir, configured=False)
    with pytest.raises(LLMNotConfiguredError):
        await manager.start("SLMs")


# --- HTTP ----------------------------------------------------------------------


def make_client(vault_dir, configured=True) -> TestClient:
    store = Store()
    services = Services(store=store, runs=make_manager(store, vault_dir, configured=configured))
    settings = Settings(_env_file=None, vault_path=vault_dir)
    return TestClient(create_app(settings, services=services))


def parse_sse(lines) -> list[dict]:
    """Extrae los JSON de las líneas 'data:' de un flujo SSE."""
    return [json.loads(line[len("data:") :]) for line in lines if line.startswith("data:")]


def test_post_research_then_stream_events(vault_dir):
    with make_client(vault_dir) as client:
        response = client.post("/api/research", json={"topic": "SLMs para clima"})
        assert response.status_code == 200
        run_id = response.json()["run_id"]

        with client.stream("GET", f"/api/research/{run_id}/events") as stream:
            assert stream.headers["content-type"].startswith("text/event-stream")
            lines = list(stream.iter_lines())

    events = parse_sse(lines)
    validator = Draft202012Validator(EVENTS_SCHEMA)
    for event in events:
        validator.validate(event)
    assert events[-1]["type"] == "run_finished"
    assert f"event: {events[0]['type']}" in lines  # el tipo va también en 'event:'


def test_post_research_validates_topic(vault_dir):
    with make_client(vault_dir) as client:
        assert client.post("/api/research", json={"topic": "x"}).status_code == 422
        assert client.post("/api/research", json={}).status_code == 422


def test_post_research_without_llm_returns_503(vault_dir):
    with make_client(vault_dir, configured=False) as client:
        response = client.post("/api/research", json={"topic": "SLMs"})

    assert response.status_code == 503
    assert "LLM_API_KEY" in response.json()["detail"]


def test_post_research_with_missing_vault_returns_404(tmp_path):
    with make_client(tmp_path / "no-existe") as client:
        response = client.post("/api/research", json={"topic": "SLMs"})

    assert response.status_code == 404


def test_events_of_unknown_run_return_404(vault_dir):
    with make_client(vault_dir) as client:
        assert client.get("/api/research/run-nope/events").status_code == 404
