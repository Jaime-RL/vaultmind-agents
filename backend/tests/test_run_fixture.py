"""Vigila fixtures/run_example.jsonl, la investigación grabada que usa el frontend.

Si el contrato o la bóveda de demo cambian y el fixture se queda atrás, el
frontend estaría trabajando con datos imposibles: estos tests lo impiden.
Para regenerarlo: `PYTHONPATH=. uv run python scripts/make_run_fixture.py`.
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import TypeAdapter

from app.contracts import AgentEvent, NodeProposed, RouteDecision, RunFinished
from vault import parse_vault

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "fixtures" / "run_example.jsonl"
SCHEMA = json.loads((REPO_ROOT / "contracts" / "events.schema.json").read_text("utf-8"))


@pytest.fixture(scope="module")
def raw_events() -> list[dict]:
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


@pytest.fixture(scope="module")
def events(raw_events):
    adapter = TypeAdapter(AgentEvent)
    return [adapter.validate_python(e) for e in raw_events]


def test_every_line_matches_the_contract(raw_events):
    validator = Draft202012Validator(SCHEMA)
    for number, event in enumerate(raw_events, start=1):
        errors = list(validator.iter_errors(event))
        assert not errors, f"línea {number}: {errors[0].message}"


def test_single_run_in_chronological_order(events):
    assert {e.run_id for e in events} == {events[0].run_id}
    timestamps = [e.ts for e in events]
    assert timestamps == sorted(timestamps)


def test_ends_with_exactly_one_run_finished(events):
    assert isinstance(events[-1], RunFinished)
    assert sum(e.type in ("run_finished", "error") for e in events) == 1


def test_proposals_link_to_existing_demo_notes(events):
    # El frontend anima el nodo nuevo enlazado a nodos que ya están en el grafo.
    demo_ids = set(parse_vault(REPO_ROOT / "demo-vault").notes)
    proposals = [e for e in events if isinstance(e, NodeProposed)]

    assert len(proposals) >= 3
    assert len({p.proposal_id for p in proposals}) == len(proposals)
    for proposal in proposals:
        assert set(proposal.links) <= demo_ids, proposal.title


def test_covers_every_agent_and_an_escalation(events):
    # Así el frontend puede probar todos los colores y el caso de escalada.
    assert {"explorer", "researcher", "writer", "reviewer"} <= {e.agent for e in events}
    routes = [e for e in events if isinstance(e, RouteDecision)]
    assert {r.tier for r in routes} == {"slm", "large"}
    assert any(r.escalated for r in routes)


def test_final_stats_are_consistent(events):
    stats = events[-1].stats
    routes = [e for e in events if isinstance(e, RouteDecision)]

    assert stats.notes_proposed == sum(isinstance(e, NodeProposed) for e in events)
    assert stats.escalations == sum(r.escalated for r in routes)
    assert stats.savings_usd == pytest.approx(stats.baseline_cost_usd - stats.cost_usd)
    assert stats.savings_usd > 0
    assert stats.duration_s == pytest.approx((events[-1].ts - events[0].ts).total_seconds() + 1)
