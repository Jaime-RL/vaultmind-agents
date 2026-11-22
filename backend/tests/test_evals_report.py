"""Tabla del README a partir de resultados de evals (sin llamar a ningún modelo)."""

from evals.report import readme_section, simulate


def r(case, task, tier, passed, cost):
    return {
        "case_id": case,
        "task": task,
        "tier": tier,
        "model": "small" if tier == "slm" else "big",
        "passed": passed,
        "detail": "",
        "cost_usd": cost,
        "latency_ms": 100,
    }


RESULTS = [
    # summarize_paper → SLM: acierta, no escala
    r("c1", "summarize_paper", "slm", True, 0.001),
    r("c1", "summarize_paper", "large", True, 0.010),
    # verify_claims → SLM: falla, escala y paga los dos
    r("c2", "verify_claims", "slm", False, 0.001),
    r("c2", "verify_claims", "large", True, 0.010),
    # write_note → grande directamente
    r("c3", "write_note", "slm", True, 0.002),
    r("c3", "write_note", "large", True, 0.020),
]


def test_simulation_counts_escalations_and_their_cost():
    sim = simulate(RESULTS)

    assert (sim.cases, sim.slm_resolved, sim.escalations) == (3, 1, 1)
    assert sim.smart_cost == 0.001 + (0.001 + 0.010) + 0.020
    assert sim.large_cost == 0.040
    assert sim.smart_passed == sim.large_passed == 3
    assert sim.unchecked_passed == 2  # sin detectar el fallo de verify_claims, se pierde
    assert round(sim.savings, 3) == round(1 - 0.032 / 0.040, 3)


def test_cases_without_large_model_are_skipped():
    sim = simulate([r("c1", "summarize_paper", "slm", True, 0.001)])
    assert sim.cases == 0 and sim.savings == 0.0


def test_readme_section_has_the_headline_and_per_task_table():
    md = readme_section(RESULTS)

    assert "**Ahorro: 20%**" in md
    assert "| `verify_claims` | slm | 0% | 100% |" in md
    assert "`small`" in md and "`big`" in md
