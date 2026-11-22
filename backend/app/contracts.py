"""Modelos Pydantic que reflejan los esquemas de `contracts/`.

La fuente de verdad son los esquemas JSON; estos modelos son su copia en Python.
`tests/test_contracts.py` comprueba que no se desincronizan: si cambias un
campo aquí sin cambiar el esquema (o al revés), ese test falla.
"""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Agent = Literal["explorer", "researcher", "writer", "reviewer", "system"]
Tier = Literal["slm", "large"]


class Contract(BaseModel):
    # extra="forbid" = additionalProperties: false en los esquemas.
    model_config = ConfigDict(extra="forbid")


# --- vault_graph.schema.json ---------------------------------------------------


class VaultNode(Contract):
    id: str
    title: str
    path: str
    tags: list[str]


class VaultLink(Contract):
    source: str
    target: str


class VaultGraph(Contract):
    nodes: list[VaultNode]
    links: list[VaultLink]


# --- research.schema.json ------------------------------------------------------


class ResearchRequest(Contract):
    topic: str = Field(min_length=3, max_length=200)


class ResearchResponse(Contract):
    run_id: str


# --- events.schema.json --------------------------------------------------------


class EventBase(Contract):
    run_id: str
    ts: datetime
    agent: Agent


class AgentThought(EventBase):
    type: Literal["agent_thought"] = "agent_thought"
    text: str


class ToolCallEvent(EventBase):
    type: Literal["tool_call"] = "tool_call"
    tool: str
    args: dict[str, Any]


class ToolResultEvent(EventBase):
    type: Literal["tool_result"] = "tool_result"
    tool: str
    summary: str


class RouteDecision(EventBase):
    type: Literal["route_decision"] = "route_decision"
    task: str
    model: str
    tier: Tier
    reason: str
    escalated: bool


class NodeProposed(EventBase):
    type: Literal["node_proposed"] = "node_proposed"
    proposal_id: str
    title: str
    links: list[str]


class RunStats(Contract):
    notes_proposed: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    baseline_cost_usd: float = Field(ge=0)
    savings_usd: float
    escalations: int = Field(ge=0)
    duration_s: float = Field(ge=0)


class RunFinished(EventBase):
    type: Literal["run_finished"] = "run_finished"
    stats: RunStats


class RunError(EventBase):
    type: Literal["error"] = "error"
    message: str


# Unión discriminada por "type": Pydantic elige el modelo correcto al validar.
AgentEvent = Annotated[
    AgentThought
    | ToolCallEvent
    | ToolResultEvent
    | RouteDecision
    | NodeProposed
    | RunFinished
    | RunError,
    Field(discriminator="type"),
]


# --- proposal.schema.json ------------------------------------------------------


class Source(Contract):
    title: str
    url: str


class ProposalReview(Contract):
    claims: int = Field(ge=0)
    supported: int = Field(ge=0)
    issues: list[str]
    revised: bool


class Proposal(Contract):
    id: str
    run_id: str
    title: str
    markdown: str
    sources: list[Source]
    links: list[str]
    agent: Agent
    model: str
    status: Literal["pending", "approved", "rejected"]
    created_at: datetime
    review: ProposalReview | None = None


class ProposalAction(Contract):
    action: Literal["approve", "reject"]
    markdown: str | None = Field(default=None, min_length=1)


# --- metrics.schema.json -------------------------------------------------------


class TaskMetric(Contract):
    run_id: str
    agent: Agent
    task: str
    model: str
    tier: Tier
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    latency_ms: float = Field(ge=0)
    escalated: bool


class MetricsTotals(Contract):
    tasks: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    baseline_cost_usd: float = Field(ge=0)
    savings_usd: float
    escalations: int = Field(ge=0)
    slm_share: float = Field(ge=0, le=1)


class Metrics(Contract):
    tasks: list[TaskMetric]
    totals: MetricsTotals
