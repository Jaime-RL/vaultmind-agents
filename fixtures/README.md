# Fixtures

## `run_example.jsonl`

Una investigación completa grabada evento a evento (36 eventos, un JSON por línea, en orden), con el formato de `contracts/events.schema.json`. Sirve para que el frontend construya y pruebe toda la interfaz en directo **sin el backend ni ningún LLM**.

Qué contiene, para que la interfaz pueda probar todos los casos:

- Los cuatro agentes (`explorer`, `researcher`, `writer`, `reviewer`) y un `run_finished` final de `system`.
- Decisiones del router con `tier` `slm` y `large`, y **una escalada** (`escalated: true`).
- Tres `node_proposed` (`p-001`, `p-002`, `p-003`) cuyos `links` apuntan a notas que existen en `demo-vault/`, así que se pueden animar unidos al grafo real.
- Marcas de tiempo reales a lo largo de unos 60 s: para reproducirlo con su ritmo, espera entre eventos la diferencia entre `ts` consecutivos (o divídela para ir más rápido).

Lo genera `backend/scripts/make_run_fixture.py` con los modelos del contrato y lo vigila `backend/tests/test_run_fixture.py`. **No lo edites a mano:** cambia el script y regenera desde `backend/` con:

```bash
PYTHONPATH=. uv run python scripts/make_run_fixture.py
```
