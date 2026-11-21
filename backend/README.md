# Backend de VaultMind

API FastAPI con los agentes, SmartRoute y el parser de la bóveda. Comandos y reglas en el [`CLAUDE.md`](../CLAUDE.md) de la raíz.

```
agents/   Agentes (Explorador, Investigador), bucle ReAct, herramienta arXiv y orquestador
app/      Aplicación FastAPI, configuración y modelos del contrato
api/      Endpoints
llm/      Interfaz LLMClient, cliente real (API compatible con OpenAI) y FakeLLMClient para tests
vault/    Parser de la bóveda de Obsidian: notas, [[wikilinks]], etiquetas y lagunas
router/   SmartRoute: política por tarea, validadores, escalada al modelo grande y costes
scripts/  Utilidades (p. ej. regenerar fixtures/run_example.jsonl)
tests/    Tests (ninguno llama a un LLM ni a internet)
```

## Cómo fluye una investigación

```
Explorador ── find_gaps (parser, sin LLM) → elige lagunas (LLM, tarea "find_gaps")
     │
Investigador ── por cada laguna, bucle ReAct: search_arxiv ⇄ LLM (tarea "summarize_paper")
     │            · solo conserva fuentes que arXiv devolvió de verdad
     │            · si una laguna falla, sigue con las demás
Orquestador ── cierra siempre con run_finished (estadísticas) o error
```

Pendiente: Redactor (propone notas) y Revisor (verifica fuentes).
