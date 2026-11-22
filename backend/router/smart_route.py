"""SmartRoute: elige el modelo de cada llamada y escala si el pequeño falla.

Flujo de una llamada:

    tarea → política ─┬─ "large" ─────────────────────────────→ modelo grande
                      └─ "slm" → SLM → ¿válida? ── sí ──────────→ respuesta
                                           └── no (LLMError) ──→ modelo grande (escalada)

Respaldo: si el modelo grande no está disponible (error del proveedor, p. ej. el límite
diario de tokens del plan gratuito de Groq) y el pequeño aún no lo ha intentado, la tarea
la hace el pequeño. Peor nota que ninguna: antes, ese 429 detenía la investigación entera.

Cada llamada deja un registro (TaskMetric) con modelo, tokens, coste, latencia
y si hubo escalada. Con esos registros se calcula el ahorro frente a usar
siempre el modelo grande.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.contracts import Agent, MetricsTotals, RouteDecision, TaskMetric
from llm import LLMClient, LLMError, LLMResponse
from llm.base import Message, ToolSpec
from router.policy import RoutingPolicy
from router.pricing import ModelPrice
from router.validators import Validator


class RejectedResponse(LLMError):
    """El modelo respondió, pero el validador rechazó la respuesta.

    Guarda la respuesta para poder cobrar sus tokens aunque no sirviera.
    """

    def __init__(self, message: str, response: LLMResponse):
        super().__init__(message)
        self.response = response


@dataclass(frozen=True)
class RouteOutcome:
    response: LLMResponse
    metric: TaskMetric
    reason: str

    def decision_event(self, ts: datetime | None = None) -> RouteDecision:
        """Evento SSE `route_decision` listo para enviar a la interfaz."""
        return RouteDecision(
            run_id=self.metric.run_id,
            ts=ts or datetime.now(UTC),
            agent=self.metric.agent,
            task=self.metric.task,
            model=self.metric.model,
            tier=self.metric.tier,
            reason=self.reason,
            escalated=self.metric.escalated,
        )


@dataclass
class SmartRoute:
    client: LLMClient
    slm_model: str
    large_model: str
    slm_price: ModelPrice
    large_price: ModelPrice
    policy: RoutingPolicy = field(default_factory=RoutingPolicy)
    # Inyectable para que los tests controlen la latencia medida.
    clock: Callable[[], float] = time.perf_counter
    records: list[TaskMetric] = field(default_factory=list)
    # Se llama con cada métrica y su coste de referencia: así se persisten al momento.
    on_record: Callable[[TaskMetric, float], None] | None = None

    async def complete(
        self,
        *,
        run_id: str,
        agent: Agent,
        task: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        validate: Validator | None = None,
    ) -> RouteOutcome:
        tier, reason = self.policy.tier_for(task)
        start = self.clock()
        wasted_cost = 0.0  # coste del intento fallido del SLM, si lo hubo
        escalated = False

        if tier == "slm":
            try:
                response = await self._call(self.slm_model, messages, tools, validate)
            except LLMError as exc:
                # El SLM no dio una respuesta utilizable: lo repetimos con el grande.
                # Si el fallo fue de validación conocemos sus tokens y los cobramos;
                # si fue del proveedor no hay tokens que contar.
                if isinstance(exc, RejectedResponse):
                    wasted_cost = self.slm_price.cost(
                        exc.response.prompt_tokens, exc.response.completion_tokens
                    )
                escalated = True
                tier = "large"
                reason = f"el modelo pequeño falló ({exc}); se escala al modelo grande"

        if tier == "large":
            try:
                response = await self._call(self.large_model, messages, tools, validate)
            except RejectedResponse:
                raise  # respondió, pero mal: el pequeño no lo hará mejor
            except LLMError as exc:
                if escalated:
                    raise  # el pequeño ya falló: no hay más niveles
                # El grande no está disponible: respaldo con el pequeño.
                response = await self._call(self.slm_model, messages, tools, validate)
                tier = "slm"
                reason = f"el modelo grande no está disponible ({exc}); lo hace el pequeño"

        price = self.slm_price if tier == "slm" else self.large_price
        metric = TaskMetric(
            run_id=run_id,
            agent=agent,
            task=task,
            model=response.model or (self.slm_model if tier == "slm" else self.large_model),
            tier=tier,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            cost_usd=price.cost(response.prompt_tokens, response.completion_tokens) + wasted_cost,
            latency_ms=(self.clock() - start) * 1000,
            escalated=escalated,
        )
        self.records.append(metric)
        if self.on_record is not None:
            self.on_record(metric, self.baseline_cost(metric))
        return RouteOutcome(response=response, metric=metric, reason=reason)

    async def _call(
        self,
        model: str,
        messages: list[Message],
        tools: list[ToolSpec] | None,
        validate: Validator | None,
    ) -> LLMResponse:
        response = await self.client.complete(messages, model=model, tools=tools)
        if validate is not None:
            try:
                validate(response)
            except LLMError as exc:
                raise RejectedResponse(str(exc), response) from exc
        return response

    def baseline_cost(self, metric: TaskMetric) -> float:
        """Coste estimado de la misma tarea si la hubiera hecho siempre el modelo grande.

        Aproximación: se usan los tokens de la respuesta final. Los dos modelos
        tokenizan algo distinto, pero para comparar estrategias basta.
        """
        return self.large_price.cost(metric.prompt_tokens, metric.completion_tokens)

    def totals(self, run_id: str | None = None) -> MetricsTotals:
        records = [r for r in self.records if run_id is None or r.run_id == run_id]
        return summarize(records, [self.baseline_cost(r) for r in records])


def summarize(records: Sequence[TaskMetric], baselines: Sequence[float]) -> MetricsTotals:
    """Totales para /api/metrics y para el evento run_finished.

    `baselines[i]` es lo que habría costado `records[i]` con el modelo grande.
    Se pasa ya calculado para poder usarlo también con métricas leídas de la base de datos.
    """
    if len(records) != len(baselines):
        raise ValueError("records y baselines deben tener la misma longitud")
    cost = sum(r.cost_usd for r in records)
    baseline = sum(baselines)
    slm_tasks = sum(1 for r in records if r.tier == "slm")
    return MetricsTotals(
        tasks=len(records),
        cost_usd=round(cost, 8),
        baseline_cost_usd=round(baseline, 8),
        savings_usd=round(baseline - cost, 8),
        escalations=sum(1 for r in records if r.escalated),
        slm_share=slm_tasks / len(records) if records else 0.0,
    )
