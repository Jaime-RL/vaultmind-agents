"""Genera fixtures/run_example.jsonl: una investigación de ejemplo, evento a evento.

La Persona B la reproduce con un servidor SSE falso para construir la interfaz
sin esperar al backend real. Se genera con los modelos del contrato, así que
cada línea es válida por construcción (y tests/test_run_fixture.py lo comprueba).

Uso (desde backend/):  PYTHONPATH=. uv run python scripts/make_run_fixture.py
"""

from datetime import UTC, datetime, timedelta

from app.config import REPO_ROOT, Settings
from app.contracts import (
    AgentThought,
    NodeProposed,
    RouteDecision,
    RunFinished,
    RunStats,
    TaskMetric,
    ToolCallEvent,
    ToolResultEvent,
)
from router import ModelPrice, summarize

RUN_ID = "run-demo-001"
START = datetime(2026, 11, 23, 10, 0, 0, tzinfo=UTC)
SLM, LARGE = "demo/slm", "demo/large"

settings = Settings(_env_file=None)
PRICES = {
    "slm": ModelPrice(settings.slm_price_input, settings.slm_price_output),
    "large": ModelPrice(settings.large_price_input, settings.large_price_output),
}


class Recorder:
    """Va acumulando eventos con marcas de tiempo crecientes y las métricas de cada tarea."""

    def __init__(self):
        self.events = []
        self.metrics: list[TaskMetric] = []
        self.clock = START

    def at(self, seconds: float) -> dict:
        self.clock += timedelta(seconds=seconds)
        return {"run_id": RUN_ID, "ts": self.clock}

    def thought(self, agent, text, after=1.0):
        self.events.append(AgentThought(**self.at(after), agent=agent, text=text))

    def tool(self, agent, tool, args, summary, after=0.5, took=2.0):
        self.events.append(ToolCallEvent(**self.at(after), agent=agent, tool=tool, args=args))
        self.events.append(
            ToolResultEvent(**self.at(took), agent=agent, tool=tool, summary=summary)
        )

    def route(self, agent, task, tier, reason, tokens, escalated=False, after=1.5):
        prompt, completion = tokens
        cost = PRICES[tier].cost(prompt, completion)
        if escalated:  # se cobra también el intento fallido del SLM
            cost += PRICES["slm"].cost(prompt, completion // 2)
        model = SLM if tier == "slm" else LARGE
        self.metrics.append(
            TaskMetric(
                run_id=RUN_ID,
                agent=agent,
                task=task,
                model=model,
                tier=tier,
                prompt_tokens=prompt,
                completion_tokens=completion,
                cost_usd=cost,
                latency_ms=after * 1000,
                escalated=escalated,
            )
        )
        self.events.append(
            RouteDecision(
                **self.at(after),
                agent=agent,
                task=task,
                model=model,
                tier=tier,
                reason=reason,
                escalated=escalated,
            )
        )

    def propose(self, proposal_id, title, links, after=1.0):
        self.events.append(
            NodeProposed(
                **self.at(after), agent="writer", proposal_id=proposal_id, title=title, links=links
            )
        )


SLM_REASON = "tarea acotada: se intenta primero con el modelo pequeño"
LARGE_REASON = "tarea compleja: se asigna directamente al modelo grande"

r = Recorder()

# --- Explorador: busca lagunas en la bóveda ---------------------------------
r.thought("explorer", "Leo la bóveda: 28 notas y 87 enlaces. Busco conceptos mencionados sin nota.")
r.tool(
    "explorer",
    "find_gaps",
    {},
    "7 lagunas: LoRA, Routing de modelos, Function calling en SLMs, "
    "Reanálisis, Evaluación de agentes, Llama, Qwen",
)
r.route("explorer", "find_gaps", "slm", SLM_REASON, (1800, 120))
r.thought(
    "explorer",
    "Para el tema pedido priorizo 3 lagunas: Function calling en SLMs, Routing de modelos y LoRA.",
)

# --- Investigador: busca y resume papers por laguna -------------------------
r.tool(
    "researcher",
    "search_arxiv",
    {"query": "function calling small language models"},
    "5 resultados de arXiv",
    took=3.0,
)
r.route("researcher", "summarize_paper", "slm", SLM_REASON, (2400, 300))
r.thought(
    "researcher",
    "Los resultados coinciden en que los SLM fallan sobre todo en el "
    "formato de los argumentos, no en elegir la herramienta.",
)

r.tool(
    "researcher",
    "search_arxiv",
    {"query": "LLM routing cost quality"},
    "4 resultados de arXiv",
    took=2.5,
)
r.route(
    "researcher",
    "summarize_paper",
    "large",
    "el modelo pequeño falló (La respuesta no es JSON válido); se escala al modelo grande",
    (2600, 320),
    escalated=True,
    after=4.0,
)
r.thought(
    "researcher",
    "Resumen listo tras escalar: el router decide por tarea y escala si "
    "la respuesta barata no pasa una validación.",
)

r.tool(
    "researcher",
    "search_arxiv",
    {"query": "LoRA low-rank adaptation fine-tuning"},
    "6 resultados de arXiv",
    took=2.0,
)
r.route("researcher", "summarize_paper", "slm", SLM_REASON, (2200, 280))

# --- Redactor: escribe las notas, enlazadas con la bóveda -------------------
r.thought(
    "writer", "Redacto la nota «Function calling en SLMs» enlazándola con Tool calling y SLM."
)
r.route("writer", "write_note", "large", LARGE_REASON, (3200, 900), after=6.0)
r.propose(
    "p-001",
    "Function calling en SLMs",
    ["agentes/Tool calling", "modelos/SLM", "proyecto/Diario de trabajo"],
)

r.thought("writer", "Redacto «Routing de modelos» y la conecto con Sistemas multiagente.")
r.route("writer", "write_note", "large", LARGE_REASON, (3000, 850), after=5.5)
r.propose(
    "p-002",
    "Routing de modelos",
    ["agentes/Sistemas multiagente", "proyecto/Objetivos del TFG", "modelos/LLM"],
)

r.thought("writer", "Redacto «LoRA» como técnica de fine-tuning eficiente para el SLM del TFG.")
r.route("writer", "write_note", "large", LARGE_REASON, (2800, 780), after=5.0)
r.propose("p-003", "LoRA", ["modelos/Fine-tuning", "modelos/SLM"])

# --- Revisor: comprueba que cada afirmación tiene fuente --------------------
r.tool("reviewer", "verify_claims", {"proposal_id": "p-001"}, "6 de 6 afirmaciones con fuente")
r.route("reviewer", "verify_claims", "slm", SLM_REASON, (2100, 150))
r.tool("reviewer", "verify_claims", {"proposal_id": "p-002"}, "4 de 5 afirmaciones con fuente")
r.route("reviewer", "verify_claims", "slm", SLM_REASON, (2000, 160))
r.thought(
    "reviewer",
    "En «Routing de modelos» una afirmación no tiene fuente: la marco para "
    "que la revises antes de aprobar.",
)
r.tool("reviewer", "verify_claims", {"proposal_id": "p-003"}, "5 de 5 afirmaciones con fuente")
r.route("reviewer", "verify_claims", "slm", SLM_REASON, (1900, 140))

# --- Fin ---------------------------------------------------------------------
totals = summarize(r.metrics, lambda m: PRICES["large"].cost(m.prompt_tokens, m.completion_tokens))
end = r.at(1.0)
r.events.append(
    RunFinished(
        **end,
        agent="system",
        stats=RunStats(
            notes_proposed=3,
            cost_usd=totals.cost_usd,
            baseline_cost_usd=totals.baseline_cost_usd,
            savings_usd=totals.savings_usd,
            escalations=totals.escalations,
            duration_s=(end["ts"] - START).total_seconds(),
        ),
    )
)

out = REPO_ROOT / "fixtures" / "run_example.jsonl"
out.parent.mkdir(exist_ok=True)
out.write_text("".join(e.model_dump_json() + "\n" for e in r.events), encoding="utf-8")
print(f"{len(r.events)} eventos → {out.relative_to(REPO_ROOT)}")
print(
    f"coste {totals.cost_usd:.5f} USD · sin router {totals.baseline_cost_usd:.5f} USD · "
    f"ahorro {totals.savings_usd:.5f} USD ({totals.savings_usd / totals.baseline_cost_usd:.0%})"
)
