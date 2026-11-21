from datetime import UTC, datetime, timedelta

import pytest

from app.contracts import Proposal, TaskMetric
from store import Store

T0 = datetime(2026, 11, 25, 10, 0, tzinfo=UTC)


@pytest.fixture
def store():
    s = Store()  # :memory:
    yield s
    s.close()


def proposal(pid: str, minutes: int = 0, status="pending") -> Proposal:
    return Proposal(
        id=pid,
        run_id="run-1",
        title=f"Nota {pid}",
        markdown="# Nota",
        sources=[],
        links=[],
        agent="writer",
        model="large",
        status=status,
        created_at=T0 + timedelta(minutes=minutes),
    )


def metric(run_id: str, tier="slm", cost=0.001, escalated=False) -> TaskMetric:
    return TaskMetric(
        run_id=run_id,
        agent="researcher",
        task="summarize_paper",
        model=tier,
        tier=tier,
        prompt_tokens=100,
        completion_tokens=10,
        cost_usd=cost,
        latency_ms=50,
        escalated=escalated,
    )


def test_run_lifecycle(store):
    store.create_run("run-1", "SLMs")
    assert store.get_run("run-1").status == "running"

    store.finish_run("run-1", "finished")

    run = store.get_run("run-1")
    assert (run.topic, run.status) == ("SLMs", "finished")
    assert run.finished_at is not None
    assert store.get_run("no-existe") is None


def test_events_keep_order(store):
    store.create_run("run-1", "x")
    for i in range(3):
        store.add_event("run-1", f'{{"n": {i}}}')

    assert store.list_events("run-1") == [{"n": 0}, {"n": 1}, {"n": 2}]
    assert store.list_events("otro") == []


def test_proposals_roundtrip_and_filters(store):
    store.save_proposal(proposal("p-1", minutes=0))
    store.save_proposal(proposal("p-2", minutes=5))

    assert store.get_proposal("p-1") == proposal("p-1")
    assert [p.id for p in store.list_proposals()] == ["p-2", "p-1"]  # más recientes primero

    updated = store.set_proposal_status("p-1", "approved", file_path="_copilot/Nota p-1.md")

    assert updated.status == "approved"
    assert [p.id for p in store.list_proposals("pending")] == ["p-2"]
    assert [p.id for p in store.list_proposals("approved")] == ["p-1"]


def test_metrics_totals_use_stored_baseline(store):
    store.add_metric(metric("run-1", "slm", cost=0.001), baseline_cost_usd=0.010)
    store.add_metric(metric("run-1", "large", cost=0.010, escalated=True), baseline_cost_usd=0.010)
    store.add_metric(metric("run-2", "slm", cost=0.002), baseline_cost_usd=0.020)

    records, totals = store.metrics("run-1")

    assert len(records) == 2
    assert totals.tasks == 2
    assert totals.cost_usd == pytest.approx(0.011)
    assert totals.baseline_cost_usd == pytest.approx(0.020)
    assert totals.savings_usd == pytest.approx(0.009)
    assert totals.escalations == 1
    assert totals.slm_share == 0.5
    assert store.metrics()[1].tasks == 3


def test_persists_on_disk(tmp_path):
    path = tmp_path / "datos" / "vaultmind.db"  # la carpeta se crea sola
    first = Store(path)
    first.create_run("run-1", "x")
    first.close()

    second = Store(path)
    assert second.get_run("run-1") is not None
    second.close()
