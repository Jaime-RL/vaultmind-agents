"""Tests de SmartRoute con FakeLLMClient: ninguna llamada real a un modelo."""

import pytest

from llm import FakeLLMClient, LLMError, LLMResponse, ToolCall
from router import (
    ModelPrice,
    RoutingPolicy,
    SmartRoute,
    require_json_object,
    require_tool_call,
)

SLM_PRICE = ModelPrice(input_per_mtok=0.10, output_per_mtok=0.10)
LARGE_PRICE = ModelPrice(input_per_mtok=3.00, output_per_mtok=15.00)
MESSAGES = [{"role": "user", "content": "hola"}]


class FakeClock:
    """Cada lectura avanza 0,25 s: una llamada mide 250 ms de latencia."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        self.now += 0.25
        return self.now


def make_router(script) -> tuple[SmartRoute, FakeLLMClient]:
    fake = FakeLLMClient(script)
    router = SmartRoute(
        client=fake,
        slm_model="small",
        large_model="large",
        slm_price=SLM_PRICE,
        large_price=LARGE_PRICE,
        clock=FakeClock(),
    )
    return router, fake


def reply(content="ok", prompt=1000, completion=100):
    return LLMResponse(content=content, prompt_tokens=prompt, completion_tokens=completion)


async def route(router, task, validate=None):
    return await router.complete(
        run_id="run-1", agent="researcher", task=task, messages=MESSAGES, validate=validate
    )


# --- Política ----------------------------------------------------------------


async def test_simple_task_goes_to_slm():
    router, fake = make_router([reply()])

    outcome = await route(router, "summarize_paper")

    assert [call.model for call in fake.calls] == ["small"]
    assert outcome.metric.tier == "slm"
    assert outcome.metric.escalated is False


async def test_complex_task_goes_straight_to_large():
    router, fake = make_router([reply()])

    outcome = await route(router, "write_note")

    assert [call.model for call in fake.calls] == ["large"]
    assert outcome.metric.tier == "large"
    assert outcome.metric.escalated is False


async def test_unknown_task_defaults_to_large():
    router, fake = make_router([reply()])

    outcome = await route(router, "tarea_nueva")

    assert fake.calls[0].model == "large"
    assert "sin regla" in outcome.reason


async def test_custom_policy():
    router, fake = make_router([reply()])
    router.policy = RoutingPolicy(rules={"write_note": "slm"})

    await route(router, "write_note")

    assert fake.calls[0].model == "small"


# --- Escalada ----------------------------------------------------------------


async def test_escalates_when_slm_provider_fails():
    router, fake = make_router([LLMError("timeout"), reply()])

    outcome = await route(router, "summarize_paper")

    assert [call.model for call in fake.calls] == ["small", "large"]
    assert outcome.metric.tier == "large"
    assert outcome.metric.escalated is True
    assert "timeout" in outcome.reason


async def test_escalates_when_slm_returns_invalid_json():
    router, fake = make_router([reply("esto no es JSON"), reply('{"gaps": []}')])

    outcome = await route(router, "summarize_paper", validate=require_json_object("gaps"))

    assert [call.model for call in fake.calls] == ["small", "large"]
    assert outcome.response.content == '{"gaps": []}'
    assert outcome.metric.escalated is True


async def test_large_model_failure_propagates():
    router, _ = make_router([LLMError("caído"), LLMError("también caído")])

    with pytest.raises(LLMError, match="también caído"):
        await route(router, "summarize_paper")


async def test_large_task_is_not_retried():
    # Una tarea que ya va al grande no tiene a quién escalar.
    router, fake = make_router([reply("no JSON")])

    with pytest.raises(LLMError):
        await route(router, "write_note", validate=require_json_object())
    assert len(fake.calls) == 1


# --- Costes, latencia y totales ---------------------------------------------


async def test_slm_cost_and_latency():
    router, _ = make_router([reply(prompt=1000, completion=100)])

    outcome = await route(router, "summarize_paper")

    # 1000 × 0,10 + 100 × 0,10 = 110 USD por millón de tokens → 0,00011 USD
    assert outcome.metric.cost_usd == pytest.approx(0.00011)
    assert outcome.metric.latency_ms == pytest.approx(250)


async def test_escalation_pays_for_the_rejected_slm_answer():
    router, _ = make_router([reply("basura", 1000, 100), reply('{"a": 1}', 1000, 100)])

    outcome = await route(router, "summarize_paper", validate=require_json_object("a"))

    slm_wasted = 0.00011
    large = (1000 * 3.00 + 100 * 15.00) / 1_000_000
    assert outcome.metric.cost_usd == pytest.approx(large + slm_wasted)


async def test_totals_show_savings_against_always_large():
    router, _ = make_router([reply(), reply(), LLMError("x"), reply(), reply()])

    await route(router, "summarize_paper")  # SLM
    await route(router, "verify_claims")  # SLM
    await route(router, "summarize_paper")  # SLM falla → grande
    await route(router, "write_note")  # grande

    totals = router.totals()
    large_one = (1000 * 3.00 + 100 * 15.00) / 1_000_000
    slm_one = 0.00011
    assert totals.tasks == 4
    assert totals.escalations == 1
    assert totals.slm_share == 0.5
    assert totals.baseline_cost_usd == pytest.approx(4 * large_one)
    assert totals.cost_usd == pytest.approx(2 * slm_one + 2 * large_one)
    assert totals.savings_usd == pytest.approx(totals.baseline_cost_usd - totals.cost_usd)
    assert totals.savings_usd > 0


async def test_totals_filter_by_run():
    router, _ = make_router([reply(), reply()])
    await router.complete(run_id="a", agent="writer", task="write_note", messages=MESSAGES)
    await router.complete(run_id="b", agent="writer", task="write_note", messages=MESSAGES)

    assert router.totals("a").tasks == 1
    assert router.totals().tasks == 2


def test_empty_totals():
    router, _ = make_router([])
    assert router.totals().model_dump() == {
        "tasks": 0,
        "cost_usd": 0,
        "baseline_cost_usd": 0,
        "savings_usd": 0,
        "escalations": 0,
        "slm_share": 0,
    }


# --- Evento para la interfaz -------------------------------------------------


async def test_decision_event_matches_metric():
    router, _ = make_router([LLMError("x"), reply()])
    outcome = await route(router, "verify_claims")

    event = outcome.decision_event()

    assert event.type == "route_decision"
    assert (event.task, event.model, event.tier, event.escalated) == (
        "verify_claims",
        "large",
        "large",
        True,
    )


# --- Validadores -------------------------------------------------------------


def test_json_validator_accepts_code_fences():
    require_json_object("a")(LLMResponse(content='```json\n{"a": 1}\n```'))


@pytest.mark.parametrize("content", ["", "[1, 2]", '{"b": 1}', "{roto"])
def test_json_validator_rejects_bad_output(content):
    with pytest.raises(LLMError):
        require_json_object("a")(LLMResponse(content=content))


def test_tool_validator():
    ok = LLMResponse(tool_calls=[ToolCall(id="1", name="search_arxiv")])
    require_tool_call("search_arxiv")(ok)

    with pytest.raises(LLMError, match="ninguna"):
        require_tool_call("search_arxiv")(LLMResponse(content="respondo sin herramienta"))
    with pytest.raises(LLMError, match="desconocida"):
        bad = LLMResponse(tool_calls=[ToolCall(id="1", name="borrar_todo")])
        require_tool_call("search_arxiv")(bad)


# --- Respaldo si el modelo grande no está disponible -------------------------


async def test_large_unavailable_falls_back_to_slm():
    """Regresión: el límite diario de Groq (429) del modelo grande detenía la investigación."""
    router, fake = make_router([LLMError("429 rate limit (tokens per day)"), reply("nota")])

    outcome = await route(router, "write_note")

    assert [call.model for call in fake.calls] == ["large", "small"]
    assert outcome.response.content == "nota"
    assert outcome.metric.tier == "slm"
    assert outcome.metric.escalated is False
    assert "no está disponible" in outcome.reason


async def test_no_fallback_when_the_slm_already_failed():
    router, _ = make_router([LLMError("timeout"), LLMError("429")])

    with pytest.raises(LLMError, match="429"):
        await route(router, "summarize_paper")


async def test_no_fallback_when_the_large_answer_is_rejected():
    """Si el grande respondió pero el validador lo rechaza, no es un problema de cupo."""
    router, fake = make_router([reply("sin json")])

    with pytest.raises(LLMError):
        await route(router, "write_note", validate=require_json_object("x"))

    assert [call.model for call in fake.calls] == ["large"]
