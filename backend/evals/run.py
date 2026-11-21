"""Evals con modelos reales: ¿qué tareas puede hacer el SLM y cuánto se ahorra?

Ejecuta cada caso de `evals/cases.py` con el modelo pequeño y con el grande,
y genera un informe con la tasa de acierto, el coste y la latencia por tarea,
más la política de router que sugieren los datos.

NO se ejecuta en la CI (gasta dinero y depende de la red). Uso, desde backend/
y con LLM_API_KEY, SLM_MODEL y LARGE_MODEL en el entorno o en el .env:

    PYTHONPATH=. uv run python -m evals.run            # los dos modelos
    PYTHONPATH=. uv run python -m evals.run --only slm # solo el pequeño

El informe se guarda en evals/results/ (Markdown y JSON).
"""

import argparse
import asyncio
import json
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings
from app.contracts import Tier
from evals.cases import CASES, Case, safe_check
from llm import LLMClient, LLMError
from router import DEFAULT_POLICY, ModelPrice

PASS_THRESHOLD = 0.8  # el SLM «vale» para una tarea si acierta al menos el 80 %
RESULTS_DIR = Path(__file__).parent / "results"


@dataclass(frozen=True)
class Result:
    case_id: str
    task: str
    tier: Tier
    model: str
    passed: bool
    detail: str
    cost_usd: float
    latency_ms: float


async def run_evals(
    client: LLMClient,
    models: dict[Tier, str],
    prices: dict[Tier, ModelPrice],
    cases: list[Case] = CASES,
    clock: Callable[[], float] = time.perf_counter,
) -> list[Result]:
    results = []
    for case in cases:
        for tier, model in models.items():
            start = clock()
            try:
                response = await client.complete(case.messages, model=model, tools=case.tools)
            except LLMError as exc:
                results.append(
                    Result(case.id, case.task, tier, model, False, f"error: {exc}", 0.0, 0.0)
                )
                continue
            latency = (clock() - start) * 1000
            passed, detail = safe_check(case, response)
            cost = prices[tier].cost(response.prompt_tokens, response.completion_tokens)
            results.append(Result(case.id, case.task, tier, model, passed, detail, cost, latency))
            print(f"{'✓' if passed else '✗'} {case.id:28} {tier:5} {detail}", file=sys.stderr)
    return results


def summarize_by_task(results: list[Result]) -> dict[str, dict[Tier, dict[str, float]]]:
    summary: dict[str, dict[Tier, dict[str, float]]] = {}
    for task in dict.fromkeys(r.task for r in results):
        summary[task] = {}
        for tier in dict.fromkeys(r.tier for r in results if r.task == task):
            rows = [r for r in results if r.task == task and r.tier == tier]
            summary[task][tier] = {
                "cases": len(rows),
                "pass_rate": sum(r.passed for r in rows) / len(rows),
                "avg_cost_usd": sum(r.cost_usd for r in rows) / len(rows),
                "avg_latency_ms": sum(r.latency_ms for r in rows) / len(rows),
            }
    return summary


def recommend(by_tier: dict[Tier, dict[str, float]]) -> Tier:
    """Recomienda el SLM si llega al umbral de acierto; si no, el modelo grande."""
    slm = by_tier.get("slm")
    return "slm" if slm and slm["pass_rate"] >= PASS_THRESHOLD else "large"


def report(results: list[Result], models: dict[Tier, str]) -> str:
    summary = summarize_by_task(results)
    lines = [
        f"# Evals de VaultMind · {datetime.now(UTC):%Y-%m-%d %H:%M} UTC",
        "",
        "Modelos: " + ", ".join(f"`{tier}` = {model}" for tier, model in models.items()),
        f"Umbral para usar el SLM en una tarea: {PASS_THRESHOLD:.0%} de acierto.",
        "",
        "| Tarea | Modelo | Casos | Acierto | Coste medio (USD) | Latencia media (ms) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for task, by_tier in summary.items():
        for tier, s in by_tier.items():
            lines.append(
                f"| {task} | {tier} | {s['cases']:.0f} | {s['pass_rate']:.0%} | "
                f"{s['avg_cost_usd']:.6f} | {s['avg_latency_ms']:.0f} |"
            )

    lines += [
        "",
        "## Política sugerida",
        "",
        "| Tarea | Actual | Sugerida | |",
        "| --- | --- | --- | --- |",
    ]
    for task, by_tier in summary.items():
        current = DEFAULT_POLICY.get(task, "large")
        suggested = recommend(by_tier) if "slm" in by_tier else current
        flag = "" if suggested == current else "← revisar"
        lines.append(f"| {task} | {current} | {suggested} | {flag} |")

    lines += ["", "## Fallos", ""]
    failures = [r for r in results if not r.passed]
    lines += [f"- `{r.case_id}` ({r.tier}): {r.detail}" for r in failures] or ["- Ninguno"]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", choices=["slm", "large"], help="evaluar solo un modelo")
    args = parser.parse_args()

    settings = Settings()
    api_key = settings.llm_api_key.get_secret_value()
    if not (api_key and settings.slm_model and settings.large_model):
        sys.exit("Faltan LLM_API_KEY, SLM_MODEL o LARGE_MODEL: configúralos en el .env")

    from llm.openai_compat import OpenAICompatClient  # solo hace falta con modelos reales

    models: dict[Tier, str] = {"slm": settings.slm_model, "large": settings.large_model}
    if args.only:
        models = {args.only: models[args.only]}
    prices: dict[Tier, ModelPrice] = {
        "slm": ModelPrice(settings.slm_price_input, settings.slm_price_output),
        "large": ModelPrice(settings.large_price_input, settings.large_price_output),
    }
    client = OpenAICompatClient(base_url=settings.llm_base_url, api_key=api_key)

    results = asyncio.run(run_evals(client, models, prices))
    markdown = report(results, models)

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    (RESULTS_DIR / f"{stamp}.md").write_text(markdown, encoding="utf-8")
    (RESULTS_DIR / f"{stamp}.json").write_text(
        json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(markdown)
    print(f"Guardado en {RESULTS_DIR / stamp}.md")


if __name__ == "__main__":
    main()
