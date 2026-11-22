"""Genera la investigación de ejemplo que usan el frontend y el modo demo.

- fixtures/run_example.jsonl: los eventos, uno por línea. La Persona B los reproduce
  con un servidor SSE falso para construir la interfaz sin el backend.
- fixtures/demo_run.json: eventos + notas propuestas + métricas. Lo reproduce el
  backend en modo demo (DEMO_MODE=true), la versión que se publica en la URL pública.

Se genera con los modelos del contrato y con las mismas funciones que el Redactor
real, así que es válido por construcción (tests/test_run_fixture.py y
tests/test_demo.py lo comprueban).

Uso (desde backend/):  PYTHONPATH=. uv run python scripts/make_run_fixture.py
"""

import json
from datetime import UTC, datetime, timedelta

from agents import Finding, Gap, Source
from agents.writer import mentioned_in_section, resolve_links, sources_section
from app.config import REPO_ROOT, Settings
from app.contracts import (
    AgentThought,
    NodeProposed,
    Proposal,
    ProposalReview,
    RouteDecision,
    RunFinished,
    RunStats,
    TaskMetric,
    ToolCallEvent,
    ToolResultEvent,
)
from router import ModelPrice, summarize
from vault import parse_vault
from vault.parser import LinkResolver

RUN_ID = "run-demo-001"
START = datetime(2026, 11, 23, 10, 0, 0, tzinfo=UTC)
SLM, LARGE = "qwen/qwen-2.5-7b-instruct", "qwen/qwen-2.5-72b-instruct"

settings = Settings(_env_file=None)
PRICES = {
    "slm": ModelPrice(settings.slm_price_input, settings.slm_price_output),
    "large": ModelPrice(settings.large_price_input, settings.large_price_output),
}

DEMO_TOPIC = "Function calling y routing de modelos para un chatbot de clima con SLMs"

# Notas que «propone» la demo. Fuentes reales, comprobadas en arxiv.org.
DEMO_NOTES = {
    "p-001": (
        "Function calling en SLMs",
        Source(
            "Gorilla: Large Language Model Connected with Massive APIs",
            "https://arxiv.org/abs/2305.15334",
        ),
        """# Function calling en SLMs

El *function calling* (o [[Tool calling]]) permite que un modelo pida ejecutar una función
externa devolviendo su nombre y sus argumentos en un formato estructurado. En el TFG es la pieza
que conecta el chatbot con datos climáticos reales.

En un [[SLM]] el reto principal es la fiabilidad: elegir la herramienta adecuada y generar los
argumentos con el formato exacto. Una línea de trabajo es ajustar el modelo específicamente para
escribir llamadas a APIs y darle acceso a la documentación de esas APIs, como propone Gorilla;
según sus autores, así las llamadas son más precisas y el modelo alucina menos.

Implicaciones para el TFG:
- Validar siempre los argumentos antes de ejecutar una herramienta.
- Medir por separado la elección de herramienta y la calidad de los argumentos
  (pendiente desde el [[Diario de trabajo]]).
""",
    ),
    "p-002": (
        "Routing de modelos",
        Source(
            "FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving "
            "Performance",
            "https://arxiv.org/abs/2305.05176",
        ),
        """# Routing de modelos

Un router de modelos decide qué modelo atiende cada petición: uno barato cuando basta y un
[[LLM]] grande para los casos difíciles. FrugalGPT propone una cascada que aprende qué modelos
consultar para cada entrada, con el objetivo de reducir el coste de usar APIs de LLMs
manteniendo o mejorando la precisión.

En un sistema de [[Sistemas multiagente]] cada agente hace tareas de dificultad distinta, así que
el router puede asignar un modelo diferente a cada una. Estudiarlo es uno de los
[[Objetivos del TFG]].

Unas reglas fijas por tipo de tarea son el punto de partida más sencillo; con las trazas de uso se
podría aprender después una política mejor.
""",
    ),
    "p-003": (
        "LoRA",
        Source(
            "LoRA: Low-Rank Adaptation of Large Language Models",
            "https://arxiv.org/abs/2106.09685",
        ),
        """# LoRA

LoRA (*Low-Rank Adaptation*) es una técnica de [[Fine-tuning]] eficiente: congela los pesos del
modelo preentrenado y entrena solo unas matrices de bajo rango que se añaden a algunas capas. Así
reduce mucho el número de parámetros entrenables y la memoria necesaria para el ajuste.

En el TFG permitiría especializar un [[SLM]] en preguntas sobre clima sin el coste de reentrenar
el modelo entero.
""",
    ),
}

# Resultado final del Revisor para cada nota (coincide con los eventos de más abajo).
DEMO_REVIEWS = {
    "p-001": ProposalReview(claims=6, supported=6, issues=[], revised=False),
    # Corregida: la primera versión decía que el routing «ahorra siempre más del 50 %».
    "p-002": ProposalReview(claims=4, supported=4, issues=[], revised=True),
    "p-003": ProposalReview(claims=5, supported=5, issues=[], revised=False),
}

demo_vault = parse_vault(REPO_ROOT / "demo-vault")
resolver = LinkResolver(list(demo_vault.notes))
gaps_in_vault = demo_vault.unresolved_links()
PROPOSALS: dict[str, Proposal] = {}
for proposal_id, (title, source, body) in DEMO_NOTES.items():
    finding = Finding(Gap(title, gaps_in_vault.get(title, [])), summary="", sources=[source])
    # Mismo ensamblado que el Redactor real: cuerpo + fuentes + «Mencionada en».
    markdown = body + sources_section(finding) + mentioned_in_section(finding)
    PROPOSALS[proposal_id] = Proposal(
        id=proposal_id,
        run_id=RUN_ID,
        title=title,
        markdown=markdown,
        sources=[{"title": source.title, "url": source.url}],
        links=resolve_links(markdown, resolver),
        agent="writer",
        model=LARGE,
        status="pending",
        created_at=START,
        review=DEMO_REVIEWS[proposal_id],
    )


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

    def propose(self, proposal_id, after=1.0):
        proposal = PROPOSALS[proposal_id]
        self.events.append(
            NodeProposed(
                **self.at(after),
                agent="writer",
                proposal_id=proposal_id,
                title=proposal.title,
                links=proposal.links,
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

# --- Redactor ⇄ Revisor: cada nota se revisa ANTES de publicarla -------------
# Igual que agents/editorial.py: si el Revisor encuentra algo sin respaldo, el Redactor
# corrige la nota una vez y se vuelve a revisar. En la demo le pasa a «Routing de modelos».
r.thought(
    "writer", "Redacto la nota «Function calling en SLMs» enlazándola con Tool calling y SLM."
)
r.route("writer", "write_note", "large", LARGE_REASON, (3200, 900), after=6.0)
r.tool("reviewer", "verify_claims", {"proposal_id": "p-001"}, "6 de 6 afirmaciones con respaldo")
r.route("reviewer", "verify_claims", "slm", SLM_REASON, (2100, 150))
r.propose("p-001")

r.thought("writer", "Redacto «Routing de modelos» y la conecto con Sistemas multiagente.")
r.route("writer", "write_note", "large", LARGE_REASON, (3000, 850), after=5.5)
r.tool("reviewer", "verify_claims", {"proposal_id": "p-002"}, "4 de 5 afirmaciones con respaldo")
r.route("reviewer", "verify_claims", "slm", SLM_REASON, (2000, 160))
r.thought(
    "writer",
    "El Revisor solo respalda 4 de 5 afirmaciones: corrijo «Routing de modelos».",
)
r.route("writer", "write_note", "large", LARGE_REASON, (3400, 820), after=5.0)
r.tool("reviewer", "verify_claims", {"proposal_id": "p-002"}, "4 de 4 afirmaciones con respaldo")
r.route("reviewer", "verify_claims", "slm", SLM_REASON, (2000, 140))
r.propose("p-002")

r.thought("writer", "Redacto «LoRA» como técnica de fine-tuning eficiente para el SLM del TFG.")
r.route("writer", "write_note", "large", LARGE_REASON, (2800, 780), after=5.0)
r.tool("reviewer", "verify_claims", {"proposal_id": "p-003"}, "5 de 5 afirmaciones con respaldo")
r.route("reviewer", "verify_claims", "slm", SLM_REASON, (1900, 140))
r.propose("p-003")

# --- Fin ---------------------------------------------------------------------
totals = summarize(
    r.metrics, [PRICES["large"].cost(m.prompt_tokens, m.completion_tokens) for m in r.metrics]
)
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

demo = {
    "topic": DEMO_TOPIC,
    "events": [e.model_dump(mode="json") for e in r.events],
    "proposals": [p.model_dump(mode="json") for p in PROPOSALS.values()],
    "metrics": [
        {"metric": m.model_dump(mode="json"), "baseline_cost_usd": baseline}
        for m, baseline in zip(
            r.metrics,
            [PRICES["large"].cost(m.prompt_tokens, m.completion_tokens) for m in r.metrics],
            strict=True,
        )
    ],
}
demo_out = REPO_ROOT / "fixtures" / "demo_run.json"
demo_out.write_text(json.dumps(demo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{len(PROPOSALS)} notas y {len(r.metrics)} métricas → {demo_out.relative_to(REPO_ROOT)}")
