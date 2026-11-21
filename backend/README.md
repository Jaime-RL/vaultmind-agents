# Backend de VaultMind

API FastAPI con los agentes, SmartRoute y el parser de la bóveda. Comandos y reglas en el [`CLAUDE.md`](../CLAUDE.md) de la raíz.

```
app/      Aplicación FastAPI, configuración y modelos del contrato
api/      Endpoints
llm/      Interfaz LLMClient, cliente real (API compatible con OpenAI) y FakeLLMClient para tests
vault/    Parser de la bóveda de Obsidian: notas, [[wikilinks]], etiquetas y lagunas
tests/    Tests (ninguno llama a un LLM ni a internet)
```

Próximas carpetas: `router/` (SmartRoute) y `agents/`.
