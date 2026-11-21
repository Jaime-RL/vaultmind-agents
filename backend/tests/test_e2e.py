"""Prueba de punta a punta con el cableado de PRODUCCIÓN.

Usa build_services, el cliente OpenAI real y el cliente de arXiv real; lo único
simulado es la red (httpx.MockTransport). Así se comprueba que todas las piezas
encajan: peticiones HTTP al proveedor, tool calling, SSE, SQLite, aprobación y
métricas, sin gastar dinero ni depender de internet.
"""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.config import Settings
from app.main import create_app
from app.services import build_services

TESTS = Path(__file__).parent
REPO_ROOT = TESTS.parent.parent
ARXIV_FEED = (TESTS / "fixtures" / "arxiv_feed.xml").read_text(encoding="utf-8")
EVENTS_SCHEMA = json.loads((REPO_ROOT / "contracts" / "events.schema.json").read_text("utf-8"))
PAPER_URL = "http://arxiv.org/abs/0000.00001v1"  # está en arxiv_feed.xml

NOTE = (
    "# LoRA\n\nLoRA adapta modelos entrenando matrices de bajo rango en lugar de todos los "
    "pesos. Es útil para ajustar un [[SLM]] con pocos recursos de cómputo y memoria, algo "
    "clave en el TFG.\n"
)


class FakeOpenAI:
    """Simula /chat/completions de un proveedor compatible con OpenAI.

    Responde según qué agente habla (lo deduce del prompt de sistema) y anota
    qué modelo se pidió en cada llamada.
    """

    def __init__(self):
        self.calls: list[tuple[str, str]] = []  # (agente, modelo)
        self.auth_headers: set[str] = set()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        self.auth_headers.add(request.headers["authorization"])
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        agent = system.split("Eres el ")[1].split(" ")[0]
        self.calls.append((agent, body["model"]))

        message: dict = {"role": "assistant", "content": None}
        if agent == "Explorador":
            message["content"] = json.dumps(
                {"topic_note": "LoRA", "selected": ["LoRA"], "reasoning": "clave"}
            )
        elif agent == "Investigador":
            if body["messages"][-1]["role"] == "tool":
                answer = {"summary": "LoRA entrena matrices de bajo rango.",
                          "sources": [{"title": "Example", "url": PAPER_URL}]}  # fmt: skip
                message["content"] = json.dumps(answer)
            else:
                message["tool_calls"] = [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "search_arxiv", "arguments": '{"query": "LoRA"}'},
                    }
                ]
        elif agent == "Redactor":
            message["content"] = NOTE
        elif agent == "Revisor":
            message["content"] = json.dumps({"claims": 2, "supported": 2, "issues": []})

        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 0,
                "model": body["model"],
                "choices": [{"index": 0, "finish_reason": "stop", "message": message}],
                "usage": {"prompt_tokens": 800, "completion_tokens": 120, "total_tokens": 920},
            },
        )


@pytest.fixture
def setup(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "SLM.md").write_text("Ajuste con [[LoRA]] y datos de [[ERA5]].", encoding="utf-8")
    settings = Settings(
        _env_file=None,
        vault_path=vault,
        database_path=tmp_path / "data" / "test.db",
        llm_base_url="https://llm.example/api/v1",
        llm_api_key="sk-test",
        slm_model="tiny-model",
        large_model="big-model",
    )
    provider = FakeOpenAI()
    services = build_services(
        settings,
        llm_http=httpx.AsyncClient(transport=httpx.MockTransport(provider)),
        arxiv_http=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, text=ARXIV_FEED))
        ),
        arxiv_min_interval=0,
    )
    return settings, services, provider, vault


def test_full_research_flow_with_production_wiring(setup):
    settings, services, provider, vault = setup

    with TestClient(create_app(settings, services=services)) as client:
        # 1. Lanzar la investigación y seguir sus eventos por SSE.
        run_id = client.post("/api/research", json={"topic": "SLMs para clima"}).json()["run_id"]
        with client.stream("GET", f"/api/research/{run_id}/events") as stream:
            events = [
                json.loads(line[len("data:") :])
                for line in stream.iter_lines()
                if line.startswith("data:")
            ]

        validator = Draft202012Validator(EVENTS_SCHEMA)
        for event in events:
            validator.validate(event)
        assert events[-1]["type"] == "run_finished", events[-1]
        assert events[-1]["stats"]["notes_proposed"] == 1

        # 2. Cada agente usó el modelo que marca la política.
        assert provider.calls == [
            ("Explorador", "tiny-model"),
            ("Investigador", "tiny-model"),
            ("Investigador", "tiny-model"),
            ("Redactor", "big-model"),
            ("Revisor", "tiny-model"),
        ]
        assert provider.auth_headers == {"Bearer sk-test"}

        # 3. Aprobar la nota propuesta la escribe en la bóveda y cubre la laguna.
        [proposal] = client.get("/api/proposals?status=pending").json()
        assert PAPER_URL in proposal["markdown"]
        assert (
            client.post(f"/api/proposals/{proposal['id']}", json={"action": "approve"}).json()[
                "status"
            ]
            == "approved"
        )
        assert (vault / "_copilot" / "LoRA.md").exists()
        graph = client.get("/api/vault").json()
        assert {"source": "SLM", "target": "_copilot/LoRA"} in graph["links"]

        # 4. Las métricas cuadran con el evento final y muestran ahorro.
        totals = client.get(f"/api/metrics?run_id={run_id}").json()["totals"]
        assert totals["tasks"] == 5
        assert totals["slm_share"] == 0.8
        assert totals["savings_usd"] == pytest.approx(events[-1]["stats"]["savings_usd"])
        assert totals["savings_usd"] > 0

    # 5. Todo quedó en SQLite en disco.
    assert settings.database_path.exists()
