"""Protecciones de la API pública: límite de investigaciones simultáneas y liberación de memoria."""

import asyncio
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import DEMO_FILE, build_services
from runs import RunManager, TooManyRunsError
from runs.demo import DemoRun
from store import Store
from tests.conftest import fake_search_tool

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def vault_copy(tmp_path) -> Path:
    return Path(shutil.copytree(REPO_ROOT / "demo-vault", tmp_path / "vault"))


def demo_manager(store, vault, *, speed: float, max_concurrent=3, retention_s=300.0):
    return RunManager(
        store=store,
        vault_path=vault,
        router_factory=None,
        search_tool=fake_search_tool(),
        demo=DemoRun.load(DEMO_FILE, speed=speed),
        force_demo=True,
        max_concurrent=max_concurrent,
        retention_s=retention_s,
    )


async def test_rejects_runs_over_the_limit(vault_copy):
    manager = demo_manager(Store(), vault_copy, speed=1.0, max_concurrent=2)  # tarda ~60 s

    await manager.start("a")
    await manager.start("b")
    with pytest.raises(TooManyRunsError):
        await manager.start("c")

    await manager.cancel_all()


async def test_slot_is_freed_when_a_run_ends(vault_copy):
    manager = demo_manager(Store(), vault_copy, speed=1e6, max_concurrent=1)

    await manager.start("a")
    await manager.wait_all()

    assert await manager.start("b")  # ya no cuenta la anterior
    await manager.wait_all()


async def test_finished_runs_leave_memory_but_stay_replayable(vault_copy):
    store = Store()
    manager = demo_manager(store, vault_copy, speed=1e6, retention_s=0)

    run_id = await manager.start("a")
    await manager.wait_all()
    await asyncio.sleep(0.01)  # deja correr el call_later de la liberación

    assert run_id not in manager._live
    assert manager.exists(run_id)
    replay = [event async for event in manager.stream(run_id)]
    assert replay[-1]["type"] == "run_finished"


def test_http_returns_429_over_the_limit(vault_copy, tmp_path):
    settings = Settings(
        _env_file=None,
        demo_mode=True,
        demo_speed=1.0,  # lenta: las investigaciones siguen en curso durante el test
        max_concurrent_runs=1,
        vault_path=vault_copy,
        database_path=tmp_path / "x.db",
    )

    with TestClient(create_app(settings, services=build_services(settings))) as client:
        assert client.post("/api/research", json={"topic": "uno"}).status_code == 200
        response = client.post("/api/research", json={"topic": "dos"})

    assert response.status_code == 429
    assert "en curso" in response.json()["detail"]
