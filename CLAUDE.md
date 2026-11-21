# VaultMind — instrucciones para agentes de código

Proyecto final de la microcredencial «Building Digital Products with Generative AI». Un equipo de agentes (Explorador, Investigador, Redactor, Revisor) investiga un tema y propone notas nuevas para una bóveda de Obsidian, enlazadas con `[[wikilinks]]`. **SmartRoute** decide para cada llamada a un LLM si basta un modelo pequeño (SLM) o hace falta uno grande, y escala si el SLM falla.

## Equipo y propiedad del código

| Persona | Rol | Carpetas que toca |
| --- | --- | --- |
| A | Agentes y backend | `backend/`, `fixtures/` |
| B | Frontend e infraestructura | `frontend/`, `.devcontainer/`, `.github/`, `Dockerfile*`, `docker-compose.yml` |

**Compartido** (`contracts/`, `CLAUDE.md`, `AGENTS.md`, `README.md`, `demo-vault/`): solo se cambia en una PR propia revisada por las dos personas. Si una tarea exige cambiar `contracts/`, **para y avisa** en lugar de cambiarlo.

## Estructura

```
backend/        API FastAPI, agentes, SmartRoute, parser de la bóveda
frontend/       React + Vite + TypeScript
contracts/      Esquemas JSON de la API (fuente de verdad) — ver contracts/README.md
fixtures/       Datos grabados para tests y para el modo mock del frontend
demo-vault/     Bóveda de Obsidian de demostración (la que usa la URL pública)
docs/ai-log.md  Registro de prompts y aprendizajes para el README
```

## Stack

- **Backend:** Python ≥ 3.12, FastAPI, Pydantic v2, pydantic-settings, sse-starlette, SQLite, cliente `openai` contra una API compatible (OpenRouter o Groq). Tests con pytest; lint y formato con ruff.
- **Frontend:** React + Vite + TypeScript, Vitest + Testing Library, `react-force-graph-3d`.

## Comandos

```bash
# Backend (desde backend/)
uv sync                          # o: pip install -e ".[dev]"
uv run uvicorn app.main:app --reload
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

```bash
# Frontend (desde frontend/)
npm ci
npm run dev                      # http://localhost:5173 (reenvía /api a localhost:8000)
npm test                         # Vitest, sin red
npm run lint && npm run build    # ESLint y comprobación de tipos + build
npm run gen:types                # regenera src/api/contract.gen.ts tras cambiar contracts/

# Docker (desde la raíz)
docker compose up --build                       # backend :8000 + frontend :5173
VAULT_DIR=/ruta/a/mi/boveda docker compose up   # con tu bóveda en lugar de la demo
docker compose --profile prod up --build prod   # imagen de producción en :8080
```

- **Tipos del frontend:** `frontend/src/api/contract.gen.ts` se genera desde `contracts/`; nunca se edita a mano. La CI falla si está desactualizado.
- **Producción = un solo servicio:** el target `prod` del `Dockerfile` compila el frontend y FastAPI lo sirve junto a la API. El frontend siempre llama a rutas relativas (`/api/...`).

## Flujo de Git

- `main`: solo versiones publicadas (con tag `vX.Y.Z`). Cada push despliega.
- `develop`: integración. Todo entra por PR revisada por la otra persona y con la CI en verde.
- `feature/huN-<descripcion>`: una rama por historia de usuario y persona (ej.: `feature/hu2-agents`).
- **Conventional Commits**: `feat(router): ...`, `fix(graph): ...`, `test(agents): ...`, `docs: ...`, `ci: ...`, `chore: ...`.
- **Nunca** añadas `Co-authored-by`, «Generated with» ni ninguna otra atribución a una IA en commits, PRs o código.

## Reglas

1. **Ningún test llama a un LLM ni a internet.** Usa `FakeLLMClient` y respuestas grabadas en `fixtures/`. Las evals con modelos reales son un script aparte que no corre en la CI.
2. **Nunca leas ni escribas `.env`.** Las variables nuevas se documentan en `.env.example`.
3. **Escritura en la bóveda:** solo dentro de `_copilot/` y solo tras aprobación del usuario. Rechaza rutas con `..` o absolutas.
4. **Cada historia de usuario lleva tests** antes de abrir la PR.
5. **Las respuestas de la API cumplen `contracts/`.** Hay un test que lo comprueba.
6. Comenta las partes importantes y explica las decisiones no obvias. Si algo es ambiguo, di qué has supuesto.
7. Antes de programar una tarea nueva, propón un plan corto (ficheros, tests, orden) y espera el OK.
