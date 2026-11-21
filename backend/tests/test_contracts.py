"""Vigila que los modelos Pydantic y los esquemas de contracts/ no se desincronicen.

Dos comprobaciones por modelo:
1. Mismos campos y mismos obligatorios que el esquema.
2. Un ejemplo serializado con el modelo valida contra el esquema.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import BaseModel, TypeAdapter, ValidationError

from app import contracts as c

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"
NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
BASE = {"run_id": "run-1", "ts": NOW, "agent": "researcher"}


def load(file: str) -> dict:
    return json.loads((CONTRACTS_DIR / file).read_text(encoding="utf-8"))


def schema_for(file: str, definition: str | None = None) -> dict:
    """Devuelve el esquema raíz o uno de sus $defs, conservando los $defs para resolver $ref."""
    root = load(file)
    if definition is None:
        return root
    return {"$defs": root.get("$defs", {}), "$ref": f"#/$defs/{definition}"}


def resolve(schema: dict) -> dict:
    if "$ref" in schema:
        return schema["$defs"][schema["$ref"].split("/")[-1]]
    return schema


# (modelo, fichero, definición, ejemplo válido)
CASES = [
    (
        c.VaultGraph,
        "vault_graph.schema.json",
        None,
        c.VaultGraph(
            nodes=[c.VaultNode(id="ml/slm", title="slm", path="ml/slm.md", tags=["ia"])],
            links=[c.VaultLink(source="ml/slm", target="ml/llm")],
        ),
    ),
    (
        c.ResearchRequest,
        "research.schema.json",
        "ResearchRequest",
        c.ResearchRequest(topic="SLMs para chatbots de clima"),
    ),
    (
        c.ResearchResponse,
        "research.schema.json",
        "ResearchResponse",
        c.ResearchResponse(run_id="run-1"),
    ),
    (
        c.AgentThought,
        "events.schema.json",
        "AgentThought",
        c.AgentThought(**BASE, text="Busco papers recientes"),
    ),
    (
        c.ToolCallEvent,
        "events.schema.json",
        "ToolCall",
        c.ToolCallEvent(**BASE, tool="search_arxiv", args={"query": "SLM"}),
    ),
    (
        c.ToolResultEvent,
        "events.schema.json",
        "ToolResult",
        c.ToolResultEvent(**BASE, tool="search_arxiv", summary="5 papers"),
    ),
    (
        c.RouteDecision,
        "events.schema.json",
        "RouteDecision",
        c.RouteDecision(
            **BASE,
            task="summarize_paper",
            model="small",
            tier="slm",
            reason="resumen corto",
            escalated=False,
        ),
    ),
    (
        c.NodeProposed,
        "events.schema.json",
        "NodeProposed",
        c.NodeProposed(**BASE, proposal_id="p-1", title="Tool calling en SLMs", links=["ml/slm"]),
    ),
    (
        c.RunFinished,
        "events.schema.json",
        "RunFinished",
        c.RunFinished(
            **{**BASE, "agent": "system"},
            stats=c.RunStats(
                notes_proposed=3,
                cost_usd=0.01,
                baseline_cost_usd=0.05,
                savings_usd=0.04,
                escalations=1,
                duration_s=42.0,
            ),
        ),
    ),
    (
        c.RunError,
        "events.schema.json",
        "RunError",
        c.RunError(**{**BASE, "agent": "system"}, message="arXiv no responde"),
    ),
    (
        c.Proposal,
        "proposal.schema.json",
        "Proposal",
        c.Proposal(
            id="p-1",
            run_id="run-1",
            title="Tool calling en SLMs",
            markdown="# Tool calling\n\nVer [[slm]].",
            sources=[c.Source(title="Paper", url="https://arxiv.org/abs/2401.00001")],
            links=["ml/slm"],
            agent="writer",
            model="large",
            status="pending",
            created_at=NOW,
        ),
    ),
    (
        c.ProposalAction,
        "proposal.schema.json",
        "ProposalAction",
        c.ProposalAction(action="approve"),
    ),
    (
        c.Metrics,
        "metrics.schema.json",
        None,
        c.Metrics(
            tasks=[
                c.TaskMetric(
                    run_id="run-1",
                    agent="reviewer",
                    task="verify_claims",
                    model="small",
                    tier="slm",
                    prompt_tokens=100,
                    completion_tokens=20,
                    cost_usd=0.0001,
                    latency_ms=350,
                    escalated=False,
                )
            ],
            totals=c.MetricsTotals(
                tasks=1,
                cost_usd=0.0001,
                baseline_cost_usd=0.001,
                savings_usd=0.0009,
                escalations=0,
                slm_share=1.0,
            ),
        ),
    ),
]

IDS = [case[0].__name__ for case in CASES]


@pytest.mark.parametrize(("model", "file", "definition", "example"), CASES, ids=IDS)
def test_model_fields_match_schema(model: type[BaseModel], file, definition, example):
    schema = resolve(schema_for(file, definition))

    assert set(model.model_fields) == set(schema["properties"])
    # "type" tiene valor por defecto en los eventos (Pydantic lo rellena solo),
    # pero el esquema lo exige: por eso se excluye de la comparación.
    required = {name for name, field in model.model_fields.items() if field.is_required()}
    assert required == set(schema["required"]) - {"type"}


@pytest.mark.parametrize(("model", "file", "definition", "example"), CASES, ids=IDS)
def test_example_validates_against_schema(model, file, definition, example):
    Draft202012Validator(schema_for(file, definition)).validate(example.model_dump(mode="json"))


def test_every_event_type_in_schema_has_a_model():
    definitions = load("events.schema.json")["$defs"]
    schema_types = {
        definitions[ref["$ref"].split("/")[-1]]["properties"]["type"]["const"]
        for ref in load("events.schema.json")["oneOf"]
    }
    model_types = {
        m.model_fields["type"].default
        for m in (
            c.AgentThought,
            c.ToolCallEvent,
            c.ToolResultEvent,
            c.RouteDecision,
            c.NodeProposed,
            c.RunFinished,
            c.RunError,
        )
    }
    assert schema_types == model_types


def test_event_union_picks_model_by_type():
    adapter = TypeAdapter(c.AgentEvent)
    event = adapter.validate_python({**BASE, "type": "agent_thought", "text": "hola"})
    assert isinstance(event, c.AgentThought)

    with pytest.raises(ValidationError):
        adapter.validate_python({**BASE, "type": "unknown", "text": "hola"})


def test_schemas_reject_extra_fields():
    data = c.ResearchResponse(run_id="r").model_dump(mode="json") | {"extra": 1}
    validator = Draft202012Validator(schema_for("research.schema.json", "ResearchResponse"))
    assert not validator.is_valid(data)
    with pytest.raises(ValidationError):
        c.ResearchResponse.model_validate(data)
