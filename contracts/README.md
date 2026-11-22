# Contrato de la API

Estos esquemas JSON (draft 2020-12) son la **fuente de verdad** entre backend y frontend.

- El backend los refleja en modelos Pydantic (`backend/app/contracts.py`) y un test comprueba que sus respuestas los cumplen.
- El frontend genera o escribe sus tipos TypeScript a partir de ellos.
- **No se cambian sin acordarlo entre las dos personas.** Cualquier cambio va en su propia PR, revisada por ambos.

## Endpoints

| Endpoint | Método | Petición | Respuesta |
| --- | --- | --- | --- |
| `/api/health` | GET | — | `{"status": "ok"}` |
| `/api/vault` | GET | — | `vault_graph.schema.json` |
| `/api/research` | POST | `research.schema.json#/$defs/ResearchRequest` | `research.schema.json#/$defs/ResearchResponse` |
| `/api/research/{run_id}/events` | GET (SSE) | — | Flujo de `events.schema.json` |
| `/api/proposals` | GET | `?status=pending` (opcional) | `proposal.schema.json#/$defs/ProposalList` |
| `/api/proposals/{id}` | POST | `proposal.schema.json#/$defs/ProposalAction` (`markdown` opcional: aprobar una versión editada) | `proposal.schema.json#/$defs/Proposal` (con `review` del Revisor si lo hay) |
| `/api/ask` | POST | `ask.schema.json#/$defs/AskRequest` | `ask.schema.json#/$defs/AskResponse` |
| `/api/metrics` | GET | `?run_id=...` (opcional) | `metrics.schema.json` |

## Eventos SSE

Cada mensaje SSE tiene `event: <type>` y en `data` el JSON del evento. Todos llevan `type`, `run_id`, `ts` (ISO 8601) y `agent`.

| `type` | Campos propios | Uso en la interfaz |
| --- | --- | --- |
| `agent_thought` | `text` | Línea en el panel de razonamiento |
| `tool_call` | `tool`, `args` | «Buscando en arXiv…» |
| `tool_result` | `tool`, `summary` | Resultado resumido |
| `route_decision` | `task`, `model`, `tier`, `reason`, `escalated` | Etiqueta SLM / grande y fila del panel del router |
| `node_proposed` | `proposal_id`, `title`, `links` | Nodo nuevo animado en el grafo |
| `run_finished` | `stats` | Resumen final: notas, coste y ahorro |
| `error` | `message` | Aviso en la interfaz |

El flujo siempre termina con un `run_finished` o un `error`.

`fixtures/run_example.jsonl` contiene una investigación de ejemplo, un evento por línea, para que el frontend trabaje sin el backend.

## Errores HTTP

Los errores siguen el formato por defecto de FastAPI: `{"detail": "..."}` con 404 (no existe), 409 (propuesta ya resuelta) o 422 (petición inválida).

## Idiomas

`es`, `en`, `fr`, `de` y `pt`. `ResearchRequest.language` y `AskRequest.language` eligen el idioma del contenido (notas y respuestas); `auto`, el valor por defecto, usa el idioma en que se escribió el tema o la pregunta. `ResearchRequest.ui_language` es el idioma de los mensajes de los agentes. Cada `Proposal` y cada `AskResponse` dicen en qué idioma están.

