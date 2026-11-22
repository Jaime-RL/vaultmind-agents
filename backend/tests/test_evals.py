"""Las evals se ejecutan a mano con modelos reales; aquí se prueba su lógica sin red."""

import json

import pytest

from evals.cases import CASES, PAPERS, Case, safe_check
from evals.run import recommend, report, run_evals
from llm import FakeLLMClient, LLMError, LLMResponse, ToolCall
from router import ModelPrice

PRICES = {"slm": ModelPrice(0.1, 0.1), "large": ModelPrice(3.0, 15.0)}
MODELS = {"slm": "small", "large": "large"}


def case(case_id: str) -> Case:
    return next(c for c in CASES if c.id == case_id)


def text(content: str) -> LLMResponse:
    return LLMResponse(content=content, prompt_tokens=100, completion_tokens=50)


def as_json(data) -> LLMResponse:
    return text(json.dumps(data, ensure_ascii=False))


def test_there_are_enough_cases_for_every_task():
    tasks = [c.task for c in CASES]
    assert 15 <= len(CASES) <= 20
    for task in ("find_gaps", "summarize_paper", "write_note", "verify_claims"):
        assert tasks.count(task) >= 3
    assert len({c.id for c in CASES}) == len(CASES)


T = "Function calling en modelos pequeños"


@pytest.mark.parametrize(
    ("response", "passed"),
    [
        (as_json({"topic_note": T, "selected": ["Function calling en SLMs"]}), True),
        (text('```json\n{"topic_note": "FC", "selected": ["Evaluación de agentes"]}\n```'), True),
        (as_json({"topic_note": T, "selected": []}), False),  # había lagunas relacionadas
        (as_json({"topic_note": T, "selected": ["function calling en slms"]}), False),  # reescrita
        (as_json({"topic_note": T, "selected": ["Algo inventado"]}), False),
        (as_json({"topic_note": T, "selected": ["Function calling en SLMs", "LoRA"]}), False),
        (as_json({"selected": ["Function calling en SLMs"]}), False),  # sin título del tema
        (text("Elijo LoRA"), False),
    ],
)
def test_explorer_check(response, passed):
    assert safe_check(case("explorer-tfg"), response)[0] is passed


@pytest.mark.parametrize(
    ("selected", "passed"), [([], True), (["LoRA"], False), (["Reanálisis", "Qwen"], False)]
)
def test_explorer_check_without_related_gaps(selected, passed):
    response = as_json({"topic_note": "Predicción multitoken", "selected": selected})
    assert safe_check(case("explorer-sin-relacion"), response)[0] is passed


@pytest.mark.parametrize(
    ("response", "passed"),
    [
        (
            as_json({"summary": "Resumen", "sources": [{"title": "t", "url": PAPERS[0]["url"]}]}),
            True,
        ),
        (as_json({"summary": "Resumen", "sources": [{"title": "t", "url": "http://x/1"}]}), False),
        (as_json({"summary": "Resumen", "sources": []}), False),  # había fuentes disponibles
        (as_json({"summary": "", "sources": []}), False),
        (
            LLMResponse(
                tool_calls=[ToolCall(id="1", name="search_arxiv", arguments={"query": "q"})]
            ),
            True,
        ),
        (LLMResponse(tool_calls=[ToolCall(id="1", name="search_arxiv", arguments={})]), False),
    ],
)
def test_researcher_check(response, passed):
    assert safe_check(case("researcher-two-papers"), response)[0] is passed


def test_researcher_without_results_may_cite_nothing():
    response = as_json({"summary": "No encontré nada útil", "sources": []})
    assert safe_check(case("researcher-empty"), response)[0] is True


def test_researcher_case_replays_a_real_tool_conversation():
    messages = case("researcher-two-papers").messages
    assert messages[2]["tool_calls"][0]["function"]["name"] == "search_arxiv"
    assert messages[3]["role"] == "tool"
    assert case("researcher-two-papers").tools[0]["function"]["name"] == "search_arxiv"


GOOD_NOTE = (
    "# LoRA\n\n" + "LoRA entrena matrices de bajo rango. " * 25 + "Ver [[SLM]] y [[Fine-tuning]]."
)


@pytest.mark.parametrize(
    ("content", "passed"),
    [
        (GOOD_NOTE, True),
        (GOOD_NOTE.replace("# LoRA\n\n", ""), False),  # sin encabezado
        ("# LoRA\n\nCorta. [[SLM]] [[RAG]]", False),
        (GOOD_NOTE.replace("[[Fine-tuning]]", "[[Nota inventada]]"), False),
        # Un solo enlace es válido: el prompt pide no forzar enlaces sin relación.
        (GOOD_NOTE.replace(" y [[Fine-tuning]]", ""), True),
    ],
)
def test_writer_check(content, passed):
    assert safe_check(case("writer-lora"), text(content))[0] is passed


@pytest.mark.parametrize(
    ("case_id", "data", "passed"),
    [
        ("reviewer-clean", {"claims": 2, "supported": 2, "issues": []}, True),
        ("reviewer-clean", {"claims": 2, "supported": 1, "issues": ["x"]}, False),  # falso positivo
        ("reviewer-invented-number", {"claims": 3, "supported": 1, "issues": ["97 %"]}, True),
        ("reviewer-invented-number", {"claims": 3, "supported": 3, "issues": []}, False),
        ("reviewer-clean", {"claims": 2, "supported": 5, "issues": []}, False),  # incoherente
        ("reviewer-clean", {"total": 2}, False),
    ],
)
def test_reviewer_check(case_id, data, passed):
    assert safe_check(case(case_id), as_json(data))[0] is passed


async def test_run_evals_with_fake_models():
    cases = [case("explorer-tfg"), case("reviewer-clean")]
    fake = FakeLLMClient(
        [
            as_json({"topic_note": T, "selected": ["Function calling en SLMs"]}),  # slm ✓
            as_json({"topic_note": T, "selected": ["Function calling en SLMs"]}),  # large ✓
            text("no es JSON"),  # reviewer · slm ✗
            LLMError("timeout"),  # reviewer · large ✗ (error del proveedor)
        ]
    )

    results = await run_evals(fake, MODELS, PRICES, cases=cases)

    assert [(r.case_id, r.tier, r.passed) for r in results] == [
        ("explorer-tfg", "slm", True),
        ("explorer-tfg", "large", True),
        ("reviewer-clean", "slm", False),
        ("reviewer-clean", "large", False),
    ]
    assert results[3].detail == "error: timeout"
    assert results[0].cost_usd < results[1].cost_usd


def test_recommend_threshold():
    assert recommend({"slm": {"pass_rate": 0.8}}) == "slm"
    assert recommend({"slm": {"pass_rate": 0.79}}) == "large"
    assert recommend({"large": {"pass_rate": 1.0}}) == "large"


async def test_report_suggests_policy_changes():
    # find_gaps está en el grande; si el SLM acertara siempre, el informe sugeriría volver
    # a pasarla al SLM. Y los fallos se listan con su caso y modelo.
    good = as_json({"topic_note": "Ajuste fino", "selected": ["LoRA"]})
    fake = FakeLLMClient([good, good, text("mal"), good])
    results = await run_evals(
        fake, MODELS, PRICES, cases=[case("explorer-una"), case("explorer-tfg")]
    )

    markdown = report(results, MODELS)

    assert "| find_gaps | large | " in markdown
    assert "`explorer-tfg` (slm)" in markdown
