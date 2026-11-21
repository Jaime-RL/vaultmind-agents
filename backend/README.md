# Backend de VaultMind

API FastAPI con los agentes, SmartRoute y el parser de la bóveda. Reglas del proyecto en el [`CLAUDE.md`](../CLAUDE.md) de la raíz; contrato de la API en [`contracts/`](../contracts/README.md).

## Arrancar

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload      # http://localhost:8000/docs
uv run pytest                             # ningún test llama a un LLM ni a internet
uv run ruff check . && uv run ruff format --check .
```

Sin `.env` la API arranca con la bóveda de demostración: `/api/vault`, `/api/proposals` y `/api/metrics` funcionan, y `POST /api/research` responde **503** explicando qué falta. Para investigar de verdad hacen falta `LLM_API_KEY`, `SLM_MODEL` y `LARGE_MODEL` (ver [`.env.example`](../.env.example)).

### Modo demo (URL pública)

Con `DEMO_MODE=true`, `POST /api/research` no llama a ningún modelo: reproduce una investigación grabada (`fixtures/demo_run.json`) por el mismo camino que una real (SSE, SQLite, propuestas y métricas). No necesita clave de API y nadie puede gastar saldo. `DEMO_SPEED=2` la reproduce el doble de rápido. El primer evento avisa al usuario de que es una grabación.

```bash
DEMO_MODE=true DEMO_SPEED=2 uv run uvicorn app.main:app
```

### Límites de la API pública

- `MAX_CONCURRENT_RUNS` (3 por defecto): investigaciones a la vez; las siguientes reciben **429**.
- `FINISHED_RUN_RETENTION_S` (300): segundos que una investigación terminada sigue en memoria; después se reproduce desde SQLite.

## Endpoints

| Endpoint | Qué hace |
| --- | --- |
| `GET /api/health` | Comprobación de vida |
| `GET /api/vault` | La bóveda como grafo de notas y enlaces |
| `POST /api/research` | Lanza una investigación en segundo plano y devuelve su `run_id` |
| `GET /api/research/{run_id}/events` | Eventos SSE: los pasados y los nuevos, hasta `run_finished` o `error` |
| `GET /api/proposals?status=` | Notas propuestas (las más recientes primero) |
| `POST /api/proposals/{id}` | `approve` escribe la nota en `_copilot/`; `reject` la descarta |
| `GET /api/metrics?run_id=` | Modelo, coste y latencia de cada tarea, y el ahorro total |

## Estructura

```
agents/   Explorador, Investigador, Redactor y Revisor; bucle ReAct; herramienta arXiv; orquestador
api/      Endpoints
app/      FastAPI, configuración, servicios y modelos del contrato
evals/    Evals con modelos reales (fuera de la CI)
llm/      Interfaz LLMClient, cliente compatible con OpenAI y FakeLLMClient para tests
router/   SmartRoute: política por tarea, validadores, escalada y costes
runs/     Investigaciones en segundo plano, modo demo y reparto de eventos en directo
store/    Persistencia en SQLite
vault/    Parser de la bóveda y escritura segura de notas aprobadas
scripts/  Utilidades (regenerar fixtures/run_example.jsonl)
tests/    Tests unitarios y una prueba de punta a punta con la red simulada
```

## Cómo fluye una investigación

```
POST /api/research ──► RunManager crea una tarea asyncio y devuelve run_id
                          │
  Explorador ── lagunas de la bóveda (parser, sin LLM) → elige cuáles investigar   [SLM]
  Investigador ── por laguna, bucle ReAct: search_arxiv ⇄ LLM                       [SLM]
                  · solo conserva fuentes que arXiv devolvió de verdad
  Redactor ── escribe la nota; enlaces resueltos contra la bóveda real;             [grande]
              la sección de fuentes la añade el código
  Revisor ── cuenta afirmaciones respaldadas y señala las dudosas                    [SLM]
                          │
  Cada evento ──► SQLite + suscriptores SSE        Cada llamada al LLM ──► métrica en SQLite
                          │
  Fin: run_finished (estadísticas) o error
```

Entre corchetes, el modelo que intenta primero SmartRoute. Si el SLM falla o su respuesta no pasa la validación, la tarea se repite con el modelo grande (escalada) y se cobra también el intento fallido.

## Evals

```bash
PYTHONPATH=. uv run python -m evals.run            # SLM y modelo grande
PYTHONPATH=. uv run python -m evals.run --only slm
```

15 casos (4 tipos de tarea) con los mismos prompts que producción. El informe (en `evals/results/`) da la tasa de acierto, el coste y la latencia por tarea y modelo, y sugiere qué tareas puede hacer el SLM (umbral: 80 % de acierto).
