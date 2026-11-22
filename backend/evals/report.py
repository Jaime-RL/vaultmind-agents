"""Tabla de SmartRoute para el README a partir de un resultado de las evals.

Uso (desde backend/), después de `PYTHONPATH=. uv run python -m evals.run`:

    PYTHONPATH=. uv run python -m evals.report            # el resultado más reciente
    PYTHONPATH=. uv run python -m evals.report evals/results/20261123-101500.json

Simula SmartRoute con los resultados reales de cada caso: si la política manda la tarea al
SLM y el SLM falla, se paga también el modelo grande (la escalada). Lo compara con usar
siempre el modelo grande. No llama a ningún modelo: solo lee el JSON.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from evals.run import RESULTS_DIR
from router import DEFAULT_POLICY


@dataclass(frozen=True)
class Simulation:
    cases: int
    smart_cost: float
    large_cost: float
    smart_passed: int
    large_passed: int
    escalations: int
    slm_resolved: int  # casos que resolvió el SLM sin escalar

    @property
    def savings(self) -> float:
        return 1 - self.smart_cost / self.large_cost if self.large_cost else 0.0


def simulate(results: list[dict], policy: dict[str, str] = DEFAULT_POLICY) -> Simulation:
    by_case: dict[str, dict[str, dict]] = {}
    for r in results:
        by_case.setdefault(r["case_id"], {})[r["tier"]] = r
    smart_cost = large_cost = 0.0
    smart_passed = large_passed = escalations = slm_resolved = cases = 0
    for case in by_case.values():
        large = case.get("large")
        if large is None:
            continue  # sin el modelo grande no hay con qué comparar
        cases += 1
        large_cost += large["cost_usd"]
        large_passed += large["passed"]
        slm = case.get("slm")
        if policy.get(large["task"], "large") == "slm" and slm is not None:
            smart_cost += slm["cost_usd"]
            if slm["passed"]:
                smart_passed += 1
                slm_resolved += 1
            else:  # escalada: se paga el intento del SLM y la respuesta del grande
                escalations += 1
                smart_cost += large["cost_usd"]
                smart_passed += large["passed"]
        else:
            smart_cost += large["cost_usd"]
            smart_passed += large["passed"]
    return Simulation(
        cases, smart_cost, large_cost, smart_passed, large_passed, escalations, slm_resolved
    )


def by_task_rows(results: list[dict]) -> list[str]:
    tasks = list(dict.fromkeys(r["task"] for r in results))
    rows = []
    for task in tasks:
        rate = {}
        for tier in ("slm", "large"):
            tier_rows = [r for r in results if r["task"] == task and r["tier"] == tier]
            rate[tier] = (
                f"{sum(r['passed'] for r in tier_rows) / len(tier_rows):.0%}" if tier_rows else "—"
            )
        rows.append(
            f"| `{task}` | {DEFAULT_POLICY.get(task, 'large')} | {rate['slm']} | {rate['large']} |"
        )
    return rows


def readme_section(results: list[dict]) -> str:
    sim = simulate(results)
    models = {r["tier"]: r["model"] for r in results}
    lines = [
        "### SmartRoute con datos reales",
        "",
        f"Evals con {sim.cases} casos fijos (`backend/evals/cases.py`), "
        f"SLM = `{models.get('slm', '—')}`, modelo grande = `{models.get('large', '—')}`.",
        "",
        "| | Solo modelo grande | SmartRoute |",
        "| --- | --- | --- |",
        f"| Casos resueltos | {sim.large_passed}/{sim.cases} | {sim.smart_passed}/{sim.cases} |",
        f"| Coste total (USD) | {sim.large_cost:.5f} | {sim.smart_cost:.5f} |",
        f"| Resueltos por el SLM sin escalar | — | {sim.slm_resolved} |",
        f"| Escaladas al modelo grande | — | {sim.escalations} |",
        "",
        f"**Ahorro: {sim.savings:.0%}** frente a usar siempre el modelo grande.",
        "",
        "| Tarea | Política | Acierto SLM | Acierto grande |",
        "| --- | --- | --- | --- |",
        *by_task_rows(results),
    ]
    return "\n".join(lines) + "\n"


def latest_result() -> Path:
    files = sorted(RESULTS_DIR.glob("*.json"))
    if not files:
        sys.exit("No hay resultados: ejecuta antes `PYTHONPATH=. uv run python -m evals.run`")
    return files[-1]


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_result()
    print(readme_section(json.loads(path.read_text(encoding="utf-8"))))
    print(f"(Calculado a partir de {path}. Copia la sección en el README.)")


if __name__ == "__main__":
    main()
