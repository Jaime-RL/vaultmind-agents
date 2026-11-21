"""Cupo diario de investigaciones reales, vuelta a la demo y protecciones de la URL pública."""

import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from api.research import client_ip
from app.config import Settings
from app.main import create_app
from app.services import DEMO_FILE, Services
from llm.openai_compat import OpenAICompatClient
from runs import DailyQuotaExceededError, RunManager
from runs.demo import DemoRun, demo_notice
from store import Store
from tests.test_runs import make_manager

FAST = 1e6


@pytest.fixture
def vault_dir(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "SLM.md").write_text("Ver [[LoRA]] y [[Routing]].", encoding="utf-8")
    return vault


def quota_manager(store, vault_dir, *, per_day=None, per_ip=None, with_demo=True) -> RunManager:
    manager = make_manager(store, vault_dir)  # LLM falso configurado: investigaciones reales
    manager.max_runs_per_day = per_day
    manager.max_runs_per_ip_per_day = per_ip
    manager.demo = DemoRun.load(DEMO_FILE, speed=FAST) if with_demo else None
    return manager


async def run_and_collect(manager, topic="SLMs", ip=None) -> list[dict]:
    run_id = await manager.start(topic, client_ip=ip)
    return [event async for event in manager.stream(run_id)]


def is_demo(events: list[dict]) -> bool:
    return events[0]["agent"] == "system" and "investigación grabada" in events[0]["text"]


# --- Cupo -----------------------------------------------------------------------


async def test_real_runs_until_daily_quota_then_demo(vault_dir):
    store = Store()
    manager = quota_manager(store, vault_dir, per_day=2)

    first = await run_and_collect(manager, ip="1.1.1.1")
    second = await run_and_collect(manager, ip="2.2.2.2")
    third = await run_and_collect(manager, ip="3.3.3.3")

    assert not is_demo(first) and not is_demo(second)
    assert is_demo(third)
    assert "cupo gratuito de investigaciones de hoy" in third[0]["text"]
    assert store.count_runs_today("real") == 2
    assert store.count_runs_today("demo") == 1


async def test_per_ip_quota_only_affects_that_ip(vault_dir):
    store = Store()
    manager = quota_manager(store, vault_dir, per_ip=1)

    assert not is_demo(await run_and_collect(manager, ip="1.1.1.1"))
    repeated = await run_and_collect(manager, ip="1.1.1.1")
    other = await run_and_collect(manager, ip="2.2.2.2")

    assert is_demo(repeated) and "tu cupo" in repeated[0]["text"]
    assert not is_demo(other)


async def test_quota_without_demo_raises(vault_dir):
    manager = quota_manager(Store(), vault_dir, per_day=1, with_demo=False)
    await run_and_collect(manager)

    with pytest.raises(DailyQuotaExceededError, match="cupo"):
        await manager.start("otra")


async def test_demo_runs_do_not_consume_the_quota(vault_dir):
    store = Store()
    manager = quota_manager(store, vault_dir, per_day=1)
    await run_and_collect(manager)  # real
    for _ in range(3):
        await run_and_collect(manager)  # demo por cupo agotado

    assert store.count_runs_today("real") == 1


def test_http_429_when_quota_exhausted_and_no_demo(vault_dir):
    store = Store()
    manager = quota_manager(store, vault_dir, per_day=1, with_demo=False)
    app = create_app(
        Settings(_env_file=None, vault_path=vault_dir), services=Services(store=store, runs=manager)
    )

    with TestClient(app) as client:
        assert client.post("/api/research", json={"topic": "uno"}).status_code == 200
        client.portal.call(manager.wait_all)  # que termine la primera antes de pedir otra
        response = client.post("/api/research", json={"topic": "dos"})

    assert response.status_code == 429
    assert "vuelve mañana" in response.json()["detail"]


# --- IP del cliente ---------------------------------------------------------------


class FakeRequest:
    def __init__(self, headers=None, host="10.0.0.1"):
        self.headers = headers or {}
        self.client = type("Client", (), {"host": host})() if host else None


def test_client_ip_uses_last_forwarded_entry():
    # La primera entrada la puede falsificar el cliente; la última la añade el proxy de Render.
    request = FakeRequest({"x-forwarded-for": "6.6.6.6, 203.0.113.7"})
    assert client_ip(request) == "203.0.113.7"


def test_client_ip_without_proxy_uses_connection():
    assert client_ip(FakeRequest()) == "10.0.0.1"
    assert client_ip(FakeRequest(host=None)) is None


def test_endpoint_passes_the_client_ip(vault_dir):
    store = Store()
    manager = quota_manager(store, vault_dir, per_ip=1, with_demo=False)
    app = create_app(
        Settings(_env_file=None, vault_path=vault_dir), services=Services(store=store, runs=manager)
    )
    headers = {"x-forwarded-for": "198.51.100.4"}

    with TestClient(app) as client:
        client.post("/api/research", json={"topic": "uno"}, headers=headers)
        client.portal.call(manager.wait_all)
        blocked = client.post("/api/research", json={"topic": "dos"}, headers=headers)
        other = client.post(
            "/api/research", json={"topic": "tres"}, headers={"x-forwarded-for": "198.51.100.5"}
        )

    assert blocked.status_code == 429
    assert other.status_code == 200


# --- Base de datos ----------------------------------------------------------------


def test_old_database_is_migrated(tmp_path):
    path = tmp_path / "old.db"
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE runs (id TEXT PRIMARY KEY, topic TEXT NOT NULL, status TEXT NOT NULL, "
        "created_at TEXT NOT NULL, finished_at TEXT)"
    )
    db.execute("INSERT INTO runs VALUES ('run-old', 'x', 'finished', '2026-11-20T10:00:00', NULL)")
    db.commit()
    db.close()

    store = Store(path)
    store.create_run("run-new", "y", client_ip="1.2.3.4", mode="demo")

    assert store.get_run("run-old").mode == "real"
    assert store.get_run("run-new").client_ip == "1.2.3.4"
    assert store.count_runs_today("demo") == 1
    store.close()


# --- Aviso de la demo ---------------------------------------------------------------


def test_demo_notice_variants():
    assert "pediste «A»" in demo_notice("A", "B")
    assert "pediste" not in demo_notice("b", "B")
    assert "(sin modelo configurado)" in demo_notice("A", "B", "sin modelo configurado")
    quota = demo_notice("A", "B", "el cupo gratuito de investigaciones de hoy")
    assert quota.startswith("Se ha agotado el cupo") and "investigar «A»" in quota


# --- reasoning_effort -----------------------------------------------------------------


@pytest.mark.parametrize(("effort", "expected"), [("low", {"reasoning_effort": "low"}), (None, {})])
async def test_reasoning_effort_is_sent_only_when_set(effort, expected):
    bodies: list[dict] = []

    def provider(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": "m",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "ok"},
                    }
                ],
            },
        )

    client = OpenAICompatClient(
        base_url="https://llm.example/v1",
        api_key="k",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(provider)),
        reasoning_effort=effort,
    )
    await client.complete([{"role": "user", "content": "hola"}], model="m")

    assert {k: v for k, v in bodies[0].items() if k == "reasoning_effort"} == expected


def test_settings_defaults_protect_the_public_url():
    settings = Settings(_env_file=None)
    assert settings.max_runs_per_day > 0
    assert settings.max_runs_per_ip_per_day > 0
    assert settings.demo_fallback is True


def test_render_blueprint_never_contains_the_api_key():
    render = (Path(__file__).resolve().parents[2] / "render.yaml").read_text(encoding="utf-8")
    assert "sk-" not in render and "gsk_" not in render


async def test_new_demo_replaces_pending_demo_proposals_but_keeps_real_ones(vault_dir):
    store = Store()
    manager = quota_manager(store, vault_dir, per_day=1)
    await run_and_collect(manager)  # real: 1 propuesta (LoRA)
    await run_and_collect(manager)  # demo: 3 propuestas
    [approved] = [p for p in store.list_proposals("pending") if p.title == "Routing de modelos"]
    store.set_proposal_status(approved.id, "approved")

    await run_and_collect(manager)  # otra demo

    titles = sorted(p.title for p in store.list_proposals("pending"))
    assert titles == ["Function calling en SLMs", "LoRA", "LoRA", "Routing de modelos"]
    assert store.get_proposal(approved.id).status == "approved"
