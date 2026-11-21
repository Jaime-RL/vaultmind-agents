# VaultMind

Multi-agent research copilot that grows your Obsidian vault, routing each task between small and large LLMs to cut cost.

> **Borrador.** Secciones 2, 4 (agentes) y 5 escritas por la Persona A; las marcadas con *[Persona B]* están pendientes.

## 1. Qué es

*[Persona B: problema, para quién y el momento mínimo de valor en una frase, con el GIF de la demo.]*

## 2. Funcionalidades

### MVP

| HU | Historia de usuario | Estado (backend) |
| --- | --- | --- |
| HU1 | Como estudiante, quiero ver mi bóveda como grafo para entender cómo se conectan mis notas. | `GET /api/vault` · hecho |
| HU2 | Como estudiante, quiero lanzar una investigación sobre un tema y ver a los agentes trabajar en directo para ampliar mi estado del arte. | `POST /api/research` + SSE · hecho |
| HU3 | Como estudiante, quiero revisar y aprobar las notas antes de que entren en mi bóveda para no llenarla de errores. | `GET/POST /api/proposals` · hecho |
| HU4 | Como estudiante, quiero ver qué modelo hizo cada tarea y cuánto costó para saber cuánto ahorra el router. | `GET /api/metrics` · hecho |

Cómo trabajan los agentes en cada investigación:

1. **Explorador:** detecta las *lagunas* de la bóveda (conceptos enlazados que no tienen nota) y elige las más útiles para el tema.
2. **Investigador:** busca cada laguna en arXiv con un bucle ReAct (decide qué buscar y cuándo tiene suficiente) y resume lo encontrado.
3. **Redactor:** escribe una nota de Obsidian por laguna, enlazada con las notas existentes.
4. **Revisor:** cuenta qué afirmaciones están respaldadas y señala las dudosas antes de que el estudiante apruebe.

**SmartRoute** decide para cada llamada si basta un modelo pequeño (SLM) o hace falta uno grande, y escala al grande si el pequeño falla o su respuesta no pasa la validación.

### Backlog

- Simulador de tribunal: tres agentes que preguntan sobre las notas del TFG.
- Router aprendido a partir de las trazas y de las evals, en lugar de reglas fijas.
- Más fuentes de papers (Semantic Scholar) y evals de calidad automáticas en cada cambio de prompt.
- Sincronización directa con la bóveda real (plugin de Obsidian o Google Drive).

## 3. Cómo ejecutarlo

*[Persona B: requisitos, variables de entorno, Docker, tests del frontend y URL pública.]*

Backend por separado: ver [`backend/README.md`](backend/README.md). Variables de entorno documentadas en [`.env.example`](.env.example).

La URL pública funciona en **modo demo** (`DEMO_MODE=true`): reproduce una investigación grabada, así no necesita clave de API y ningún visitante puede gastar saldo. Para investigaciones reales, ejecútalo en local con tu clave.

## 4. Cómo se construyó con IA

*[Persona B: flujo de trabajo con ramas, Conventional Commits y DevContainer.]*

### Agentes de código y reglas

- **`CLAUDE.md` / `AGENTS.md`:** propiedad del código por persona, flujo de Git, comandos y reglas que el agente debe cumplir (ningún test llama a un LLM ni a internet; nunca tocar `.env`; escritura en la bóveda solo en `_copilot/` y tras aprobación; las respuestas de la API deben cumplir `contracts/`).
- **Contrato primero:** los esquemas JSON de `contracts/` se acordaron el primer día. Backend y frontend avanzaron en paralelo sin esperarse: el frontend trabajó con `fixtures/run_example.jsonl`, una investigación grabada que un test mantiene coherente con el contrato.
- **Plan antes de programar:** cada tarea empezaba pidiendo al agente un plan corto (ficheros, tests, orden).

### Un prompt real

```text
Soy la Persona A: agentes y backend. Solo toco backend/, tests de backend y fixtures/.
No modifico frontend/ ni contracts/ sin avisar: si el contrato tiene que cambiar, para y dímelo.
[...]
REGLAS
- Ningún test llama a un LLM ni a internet: usa FakeLLMClient y respuestas grabadas en fixtures.
- Cada historia de usuario en su rama feature/huN-..., con tests, antes de abrir PR a develop.
[...]
TAREA DE HOY
HU2: agentes Explorador e Investigador (herramienta arXiv) y orquestador con límite de pasos.
Empieza con un plan corto (ficheros a crear, tests que escribirás y orden). Espera mi OK antes de programar.
```

### Lo que funcionó

- **No confiar al LLM lo que el código puede garantizar.** Las lagunas las detecta el parser; el LLM solo elige entre ellas. Las fuentes solo se aceptan si arXiv las devolvió. Los enlaces de una nota se resuelven contra la bóveda real.
- **Un `FakeLLMClient` guionizado** que falla si se acaba el guion: los tests de agentes son deterministas, gratis y no pasan en verde por casualidad.
- **Validar para escalar:** una respuesta del SLM con JSON roto o una herramienta inexistente se trata como un fallo y se repite con el modelo grande.
- **Una prueba de punta a punta** con el cableado de producción y la red simulada detectó que todas las piezas encajan antes de gastar un céntimo en APIs.

### Lo que costó

- Errores que los tests no veían: una ruta relativa que solo fallaba al arrancar el servidor desde otra carpeta y una regla del `.gitignore` que ignoraba en silencio `backend/vault/`. Lección: arrancar la app real y revisar `git status` además de pasar los tests.
- Decidir cómo contar el coste de una escalada (se cobra también el intento fallido del SLM, para no inflar el ahorro).

El registro completo está en [`docs/ai-log.md`](docs/ai-log.md).

## 5. Estado y próximos pasos

**Estado del backend:** las cuatro historias del MVP están implementadas y probadas (tests unitarios y una prueba de punta a punta con la red simulada).

**Pendiente antes de la entrega:**

- Modelos: Qwen2.5 7B Instruct como SLM y Qwen2.5 72B Instruct como modelo grande (misma familia, para que la comparación mida el efecto del tamaño), con sus precios de OpenRouter. Falta ejecutar las evals (`backend/evals`) con una clave para obtener la tasa de acierto y el ahorro reales. Sus resultados decidirán qué tareas puede hacer el SLM y darán la cifra de ahorro real; hasta entonces el ahorro del fixture (40 %) es solo ilustrativo.
- *[Persona B: estado del frontend y del despliegue.]*

**Próximos pasos:** ver el backlog de la sección 2.
