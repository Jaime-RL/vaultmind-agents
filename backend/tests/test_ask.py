"""Pregunta a tu bóveda: BM25, agente y endpoint, con LLM falso y sin red."""

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from agents.asker import NO_NOTES, answer_question, cited, context_for
from app.config import Settings
from app.main import create_app
from app.services import Services
from llm import LLMError, LLMResponse
from runs import RunManager
from store import Store
from tests.conftest import fake_search_tool
from tests.test_contracts import schema_for
from vault import parse_vault
from vault.search import search, tokenize


def text(content: str) -> LLMResponse:
    return LLMResponse(content=content, prompt_tokens=800, completion_tokens=120)


@pytest.fixture
def vault_dir(tmp_path):
    notes = {
        "modelos/LoRA.md": "LoRA congela los pesos y entrena matrices de bajo rango. Ver [[SLM]].",
        "modelos/SLM.md": "Un SLM es un modelo de lenguaje pequeño, barato de ejecutar.",
        "clima/ERA5.md": "ERA5 es el reanálisis climático del ECMWF con datos horarios.",
        "Diario.md": "Hoy he leído sobre matrices y sobre el clima.",
    }
    for path, content in notes.items():
        file = tmp_path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")
    return tmp_path


@pytest.fixture
def vault(vault_dir):
    return parse_vault(vault_dir)


# --- BM25 --------------------------------------------------------------------


def test_tokenize_ignores_accents_case_and_stopwords():
    assert tokenize("¿Qué es el Reanálisis CLIMÁTICO?") == ["reanalisis", "climatico"]


def test_search_ranks_the_note_about_the_question_first(vault):
    hits = search(vault, "¿Cómo funciona LoRA con matrices de bajo rango?")

    assert hits[0].note_id == "modelos/LoRA"  # el título pesa más que una mención de pasada
    assert "clima/ERA5" not in [h.note_id for h in hits]


def test_search_without_matches_returns_nothing(vault):
    assert search(vault, "computación cuántica") == []
    assert search(vault, "¿qué es?") == []  # solo palabras vacías


# --- Agente --------------------------------------------------------------------


async def test_slm_answer_with_citations_is_returned(make_router, vault):
    router, fake = make_router(
        [text("LoRA entrena matrices de bajo rango [[LoRA]] en un [[SLM]].")]
    )

    response = await answer_question(
        question="¿Cómo se usa LoRA en un SLM?", vault=vault, router=router, run_id="a1"
    )

    assert fake.calls[0].model == "small"  # answer_question va primero al SLM
    assert [c.id for c in response.citations] == ["modelos/LoRA", "modelos/SLM"]
    assert (response.tier, response.escalated) == ("slm", False)
    assert response.cost_usd > 0
    prompt = fake.calls[0].messages[-1]["content"]
    assert "congela los pesos" in prompt  # el modelo recibe el contenido de las notas


async def test_answer_without_citations_escalates_to_the_large_model(make_router, vault):
    router, fake = make_router(
        [
            text("LoRA es una técnica muy conocida de ajuste fino de modelos."),  # SLM: sin citas
            text("Según tu nota [[LoRA]], congela los pesos del modelo."),  # grande
        ]
    )

    response = await answer_question(
        question="¿Qué es LoRA?", vault=vault, router=router, run_id="a2"
    )

    assert [call.model for call in fake.calls] == ["small", "large"]
    assert (response.tier, response.escalated) == ("large", True)


async def test_citations_to_notes_not_given_are_ignored(vault):
    context = context_for(vault, "LoRA matrices")
    answer = "Ver [[LoRA]], [[Nota inventada]] y otra vez [[lora]]."

    assert [c.title for c in cited(answer, context)] == ["LoRA"]


async def test_no_relevant_notes_does_not_call_the_model(make_router, vault):
    router, fake = make_router([])

    response = await answer_question(
        question="computación cuántica", vault=vault, router=router, run_id="a3"
    )

    assert response.answer == NO_NOTES
    assert fake.calls == [] and response.model is None


async def test_without_llm_points_to_the_relevant_notes(vault):
    response = await answer_question(
        question="¿Qué es LoRA?", vault=vault, router=None, run_id="a4"
    )

    assert "[[LoRA]]" in response.answer
    assert response.citations[0].id == "modelos/LoRA"
    assert (response.model, response.cost_usd) == (None, 0.0)


# --- Endpoint ------------------------------------------------------------------


def build_client(vault_dir, make_router, script, **manager_kwargs):
    store = Store()

    def factory():
        router, _ = make_router(list(script))
        return router

    runs = RunManager(
        store=store,
        vault_path=vault_dir,
        router_factory=factory if script is not None else None,
        search_tool=fake_search_tool(),
        **manager_kwargs,
    )
    app = create_app(
        Settings(_env_file=None, vault_path=vault_dir), services=Services(store=store, runs=runs)
    )
    return TestClient(app), store


def test_endpoint_answers_following_the_contract_and_records_metrics(vault_dir, make_router):
    client, store = build_client(
        vault_dir, make_router, [text("Tu nota [[LoRA]] lo explica bien.")]
    )

    with client:
        response = client.post("/api/ask", json={"question": "¿Qué es LoRA?"})
        metrics = client.get("/api/metrics").json()

    assert response.status_code == 200
    Draft202012Validator(schema_for("ask.schema.json", "AskResponse")).validate(response.json())
    assert metrics["totals"]["tasks"] == 1  # la pregunta cuenta en las métricas de SmartRoute


def test_endpoint_rejects_too_short_questions(vault_dir, make_router):
    client, _ = build_client(vault_dir, make_router, [])
    with client:
        assert client.post("/api/ask", json={"question": "?"}).status_code == 422


def test_quota_exhausted_falls_back_to_pointing_at_notes(vault_dir, make_router):
    script = [text("Tu nota [[LoRA]] lo explica."), text("Tu nota [[LoRA]] lo explica.")]
    client, _ = build_client(vault_dir, make_router, script, max_asks_per_ip_per_day=1)

    with client:
        first = client.post("/api/ask", json={"question": "¿Qué es LoRA?"}).json()
        second = client.post("/api/ask", json={"question": "¿Qué es LoRA?"}).json()

    assert first["model"] == "small"
    assert second["model"] is None and "[[LoRA]]" in second["answer"]


def test_model_failure_is_a_502(vault_dir, make_router):
    client, _ = build_client(vault_dir, make_router, [LLMError("caído"), LLMError("también")])
    with client:
        response = client.post("/api/ask", json={"question": "¿Qué es LoRA?"})
    assert response.status_code == 502


@pytest.mark.parametrize(
    "question",
    [
        "Comment fonctionne le routage de modèles ?",
        "Wie funktioniert das Routing von Modellen?",
        "Como funciona o roteamento de modelos?",
    ],
)
def test_questions_in_other_languages_find_spanish_notes(tmp_path, question):
    """Regresión (URL pública): una pregunta en francés no encontraba nada en una bóveda
    escrita en español, porque la búsqueda solo comparaba palabras exactas."""
    (tmp_path / "Routing de modelos.md").write_text(
        "El routing decide qué modelo atiende cada petición.", encoding="utf-8"
    )
    (tmp_path / "ERA5.md").write_text("Reanálisis climático horario.", encoding="utf-8")

    hits = search(parse_vault(tmp_path), question)

    assert hits and hits[0].note_id == "Routing de modelos"


def test_exact_matches_win_over_stems(vault):
    # Con coincidencias exactas no se usan raíces: «LoRA» no arrastra notas que solo
    # compartan las 4 primeras letras.
    assert [h.note_id for h in search(vault, "LoRA")] == ["modelos/LoRA"]
