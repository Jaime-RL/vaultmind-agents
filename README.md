# VaultMind

Multi-agent research copilot that grows your Obsidian vault, routing each task between small and large LLMs to cut cost.

![Demo de VaultMind: se lanza un tema de ejemplo, los agentes investigan, el marcador de SmartRoute cuenta el ahorro, se abre una nota con su insignia de confianza y se pregunta a la bóveda](docs/demo.gif)

## 1. Qué es

**El problema:** escribir el estado del arte de un TFG lleva semanas, y la bóveda de Obsidian de un estudiante acaba llena de conceptos enlazados (`[[LoRA]]`, `[[Routing de modelos]]`) que nunca llegan a tener nota propia.

**Para quién:** estudiantes que toman sus apuntes en Obsidian y preparan un trabajo de investigación.

**Momento mínimo de valor:** escribes un tema y, en un minuto, un equipo de agentes te propone notas nuevas, con fuentes de arXiv y enlazadas a las que ya tenías, para que las apruebes con un clic. Cada nota dice cuántas de sus afirmaciones están respaldadas por las fuentes, y después puedes preguntarle a tu bóveda y ver qué notas usa para responder.

## 2. Funcionalidades

### MVP

| HU | Historia de usuario | Backend | Frontend |
| --- | --- | --- | --- |
| HU1 | Como estudiante, quiero ver mi bóveda como grafo para entender cómo se conectan mis notas. | `GET /api/vault` | Grafo 3D de la bóveda; las notas propuestas aparecen animadas, con un anillo verde (SLM) o azul (modelo grande) según quién las escribió |
| HU2 | Como estudiante, quiero lanzar una investigación sobre un tema y ver a los agentes trabajar en directo para ampliar mi estado del arte. | `POST /api/research` + SSE | Pestaña «Agentes» con el razonamiento, las búsquedas y las decisiones del router en directo; reconexión explícita si se corta la conexión |
| HU3 | Como estudiante, quiero revisar y aprobar las notas antes de que entren en mi bóveda para no llenarla de errores. | `GET/POST /api/proposals` | Pestaña «Notas»: la nota renderizada con sus `[[enlaces]]` marcados según existan en la bóveda, sus fuentes y aprobar / rechazar |
| HU4 | Como estudiante, quiero ver qué modelo hizo cada tarea y cuánto costó para saber cuánto ahorra el router. | `GET /api/metrics` | Pestaña «Router» y marcador en directo sobre el grafo: llamadas resueltas por el SLM y por el grande, escaladas y % de ahorro frente a «solo modelo grande» |
| HU5 | Como estudiante, quiero saber cuánto me puedo fiar de cada nota para no aprobar algo inventado. | Revisor antes de publicar + `Proposal.review` | Insignia «✓ 5/5 respaldadas», etiqueta «corregida» y lista de afirmaciones sin respaldo |
| HU6 | Como estudiante, quiero preguntar a mi bóveda y ver qué notas usa la respuesta. | `POST /api/ask` (BM25 + SmartRoute) | Pestaña «Preguntar»: respuesta con `[[citas]]`; cada cita lleva la cámara del grafo a esa nota |
| HU7 | Como estudiante, quiero retocar una nota antes de aprobarla y profundizar en un tema. | `ProposalAction.markdown` | «Editar» / «Aprobar con cambios» y «Profundizar», que lanza una investigación sobre la nota |

Las siete están hechas y con tests en backend y frontend.

Cómo trabajan los agentes en cada investigación:

1. **Explorador:** el tema que pides se investiga siempre. Además, detecta las *lagunas* de la bóveda (conceptos enlazados que no tienen nota) y añade solo las que de verdad están relacionadas con el tema.
2. **Investigador:** busca en arXiv y en Semantic Scholar con un bucle ReAct (decide qué buscar y cuándo tiene suficiente) y resume lo encontrado. Solo acepta fuentes que las herramientas devolvieron de verdad, comparadas por su id de arXiv. Una laguna sin fuentes se descarta.
3. **Redactor:** escribe una nota de Obsidian basada solo en el resumen y en los abstracts de las fuentes, enlazada con las notas existentes.
4. **Revisor:** antes de publicar, comprueba cada afirmación contra los abstracts. Si alguna no tiene respaldo, el Redactor reescribe la nota una vez quitando lo dudoso.

**SmartRoute** decide para cada llamada si basta un modelo pequeño (SLM) o hace falta uno grande, y escala al grande si el pequeño falla o su respuesta no pasa la validación.

### Backlog

- Simulador de tribunal: tres agentes que preguntan sobre las notas del TFG.
- Router aprendido a partir de las trazas y de las evals, en lugar de reglas fijas.
- Búsqueda semántica (embeddings) en «Preguntar»: BM25 no entiende sinónimos.
- Exportar las notas aprobadas como un .zip listo para Obsidian.
- Evals con búsquedas de arXiv grabadas y evals de calidad automáticas en cada cambio de prompt.
- Sincronización directa con la bóveda real (plugin de Obsidian o Google Drive).

## 3. Cómo ejecutarlo

**URL pública:** <https://vaultmind-xymm.onrender.com>. En el plan gratuito de Render se duerme tras 15 minutos sin visitas: la primera carga puede tardar alrededor de un minuto.

La URL pública hace **investigaciones reales, gratis y sin riesgo de gasto**:

- Usa los modelos `gpt-oss-20b` (SLM) y `gpt-oss-120b` (grande) en el **plan gratuito de Groq, sin tarjeta**: nunca hay cobro; como mucho se agota el cupo del día.
- **Cupo diario:** 10 investigaciones reales al día en total y 3 por IP (`MAX_RUNS_PER_DAY`, `MAX_RUNS_PER_IP_PER_DAY`), además de 3 simultáneas como máximo.
- Si se agota el cupo (o falta la clave), la web **no falla**: reproduce una investigación grabada y lo avisa en el primer mensaje. «Preguntar» tiene su propio cupo (20 preguntas por IP y día) y, sin cupo, señala las notas relevantes sin redactar.
- **Cada visitante ve solo sus notas** (cookie anónima, `PUBLIC_MODE=true`): lo que aprueba aparece en su grafo, pero no se escribe en la bóveda compartida.
- La clave solo vive en las variables de entorno de Render, nunca en el repositorio.

**Requisitos:** Docker, o bien Python ≥ 3.12 con [uv](https://docs.astral.sh/uv/) y Node ≥ 22. También hay un DevContainer (Python 3.12, Node 24 y uv) para abrir el proyecto listo en VS Code.

**Variables de entorno:** copia [`.env.example`](.env.example) a `.env`. Para investigar de verdad basta con `LLM_API_KEY` (OpenRouter); los modelos por defecto son Qwen2.5 7B y 72B Instruct. `SEMANTIC_SCHOLAR_API_KEY` es opcional: con ella, el Investigador usa también Semantic Scholar (año, revista y citas); sin ella, solo arXiv, porque la API pública sin clave responde casi siempre «Too Many Requests». Sin clave, pon `DEMO_MODE=true` (con `docker compose` es el valor por defecto).

```bash
# Con Docker (desarrollo): backend en :8000 y frontend en :5173
docker compose up --build
VAULT_DIR=/ruta/a/tu/boveda docker compose up      # con tu bóveda en lugar de la de demo

# Imagen de producción (un solo servicio: FastAPI sirve la API y el frontend) en :8080
docker compose --profile prod up --build prod

# Sin Docker
cd backend && uv sync && uv run uvicorn app.main:app --reload    # :8000
cd frontend && npm ci && npm run dev                              # :5173 (reenvía /api al backend)
```

**Tests:**

```bash
cd backend && uv run pytest && uv run ruff check .      # ningún test llama a un LLM ni a internet
cd frontend && npm test && npm run lint && npm run build
```

La CI (GitHub Actions) ejecuta todo lo anterior en cada PR y construye la imagen de producción comprobando que responde en `/api/health`. Más detalle del backend en [`backend/README.md`](backend/README.md).

## 4. Cómo se construyó con IA

Dos personas, cada una con su agente de código (Claude Code), siguiendo el flujo del curso: `main` y `develop`, una rama `feature/...` por historia de usuario, Conventional Commits y PR a `develop` revisada por la otra persona con la CI en verde.

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
- **Tipos del frontend generados desde `contracts/`** (`npm run gen:types`) en lugar de escritos a mano; la CI falla si se desincronizan.
- **Producción como un solo servicio** (FastAPI sirve el frontend compilado): sin CORS ni una URL distinta por entorno.
- **Probar la interfaz en un navegador real** (Chromium sin interfaz, con Playwright) además de los tests: destapó fallos que los tests no veían (la cámara pegada a la última nota, fuentes duplicadas, un botón cortado en móvil) y sirvió para grabar el GIF de la demo.
- **Validar los colores con un script en lugar de a ojo:** «un color por agente» no superaba la separación para daltonismo junto al verde y el azul del modelo, así que las notas propuestas usan un único acento y los agentes se identifican por su nombre.
- **Probar con una investigación real en la URL pública** y juzgar el resultado, no solo los tests en verde. Así salieron fallos que ningún test veía: arXiv trataba `all:multitoken prediction` como palabras alternativas y devolvía papers de cáncer o de tráfico (ahora se busca primero la frase exacta), el Explorador añadía lagunas sin relación y una nota con una variante de modelo inventada («Qwen-3D») pasaba el umbral del Revisor. Cada fallo acabó en un test de regresión.
- **Revisor antes de publicar y con evidencia:** el Redactor y el Revisor reciben los abstracts reales, y una sola afirmación sin respaldo basta para que la nota se reescriba. La insignia de confianza hace visible ese trabajo.

### Lo que costó

- Errores que los tests no veían: una ruta relativa que solo fallaba al arrancar el servidor desde otra carpeta y una regla del `.gitignore` que ignoraba en silencio `backend/vault/`. Lección: arrancar la app real y revisar `git status` además de pasar los tests.
- Decidir cómo contar el coste de una escalada (se cobra también el intento fallido del SLM, para no inflar el ahorro).
- El SSE no pintaba nada al principio: el backend envía `event: <tipo>` y `EventSource.onmessage` solo recibe mensajes sin tipo, así que hay que escuchar cada tipo con `addEventListener`.
- Compatibilidad de versiones: TypeScript 7 no es compatible con `typescript-eslint`, así que se fijó la 6.0. Y la regla de React que prohíbe actualizar estado de forma síncrona dentro de un efecto obligó a reorganizar la carga de datos de los paneles.
- La URL pública al principio era compartida: cualquiera podía aprobar notas en la bóveda de todos. Se resolvió con una sesión anónima por visitante.
- Un agente ejecutó Prettier sin la configuración del proyecto y reformateó ficheros enteros. Hubo que rehacer las ramas aplicando solo los cambios reales, para no ensuciar las PRs de la otra persona.

El registro completo está en [`docs/ai-log.md`](docs/ai-log.md).

## 5. Estado y próximos pasos

**Estado:** las siete historias están implementadas en backend y frontend, con más de 380 tests (cerca de 300 en el backend y 88 en el frontend, incluida una prueba de punta a punta con la red simulada). La app se ha verificado en un navegador real en modo demo y con investigaciones reales en la URL pública.

**Modelos:** en la URL pública, `gpt-oss-20b` y `gpt-oss-120b` en el plan gratuito de Groq; en local, por defecto, Qwen2.5 7B y 72B Instruct en OpenRouter. En ambos casos un modelo pequeño y uno grande de la misma familia, para que la comparación mida el efecto del tamaño.

### SmartRoute con datos reales

Evals con 16 casos fijos (`backend/evals/cases.py`), lanzadas desde GitHub Actions (**Actions → Evals → Run workflow**) con el plan gratuito de Groq: SLM = `openai/gpt-oss-20b`, modelo grande = `openai/gpt-oss-120b`.

| | Solo modelo grande | SmartRoute |
| --- | --- | --- |
| Casos resueltos | 15/16 | 15/16 |
| Coste total (USD) | 0.00356 | 0.00310 |
| Resueltos por el SLM sin escalar | — | 8 |

**Mismo acierto con un 13 % menos de coste.** El ahorro es modesto porque en Groq el modelo grande solo cuesta el doble que el pequeño; con precios como los de OpenRouter (Qwen 7B frente a 72B, unas 3 veces más caro) la diferencia crece.

| Tarea | Política | Acierto SLM | Acierto grande |
| --- | --- | --- | --- |
| `find_gaps` | large | 60 % / 100 % | 100 % |
| `summarize_paper` | slm | 100 % | 100 % |
| `write_note` | large | 100 % | 67 % |
| `verify_claims` | slm | 100 % | 100 % |

**Lo que cambiaron las evals:**

- **El Explorador pasó al modelo grande.** En la primera ejecución el SLM solo acertó el 60 % de `find_gaps`, añadiendo lagunas sin relación (lo mismo que se había visto en la URL pública). En la segunda acertó el 100 %: con 5 casos hay mucha varianza. Se quedó en el grande porque ese error no lo detecta ningún validador (el JSON es correcto), así que SmartRoute nunca escalaría, y la llamada cuesta unos 0,0001 $ más.
- **Un enlace roto que no se veía:** el modelo grande escribió `[[Fine‑tuning]]` con un guion tipográfico (U+2011) y no enlazaba con la nota `Fine-tuning`. El Redactor ahora normaliza los guiones dentro de los enlaces.
- **Un test de las evals estaba mal:** exigía 2 enlaces por nota cuando el prompt pide no forzarlos.

### Calidad de las notas: evaluación de punta a punta

`backend/evals/quality.py` lanza investigaciones reales (Explorador → Investigador → Redactor ⇄ Revisor, con arXiv y Groq) sobre la bóveda de demo. Usa temas del dominio de la bóveda (Mixture of Experts, interpolación meteorológica, tool calling) y temas ajenos (Raft, SLAM, Q-learning, criptografía, previsión de bolsa). Guarda cada nota con sus enlaces, fuentes y revisión. Se lanza desde **Actions → Evals → Run workflow** con `mode = quality`.

Lo que destapó la primera ejecución y cómo se corrigió:

| Problema | Ejemplo | Arreglo |
| --- | --- | --- |
| Lagunas sin relación | «Q-learning» arrastraba «Evaluación de agentes» y la bolsa, «LoRA» | Solo se ofrecen al modelo las lagunas mencionadas en las notas más parecidas al tema (BM25) |
| Lagunas con otro significado | «Routing de modelos» (en la bóveda: SLM frente a LLM) se escribió como el routing interno de Mixture of Experts | Cada laguna lleva las frases de la bóveda que la mencionan; Explorador, Investigador y Redactor las usan |
| Notas en el idioma equivocado | «Mixture of Experts» daba una nota en inglés en una bóveda en español | Con «auto», el idioma de la bóveda; un término técnico en inglés no lo cambia |
| Revisor demasiado generoso | La nota de bolsa citaba ARIMA, GARCH y LSTM (ninguna fuente los nombra) y sacaba 5/5 | El Revisor comprueba contra los abstracts, no contra el resumen del Investigador, y cuenta una afirmación por frase |
| Notas duplicadas | Lanzar dos veces «CNNs» dejaba dos propuestas de cada nota | No se investiga lo que ya tiene una propuesta pendiente |
| Título cambiado | «# SLAN en robótica» | El encabezado es siempre el título |
| Investigación detenida | El límite diario de tokens de Groq del modelo grande (429) paraba todo | SmartRoute usa el modelo pequeño como respaldo cuando el grande no está disponible |

Con el Revisor más estricto, las puntuaciones bajaron (por ejemplo, 2/5 o 0/5 en notas de clima). Las notas no empeoraron: el Revisor ya no da por buenas afirmaciones que las fuentes no dicen. Sigue habiendo un límite claro: VaultMind solo busca en arXiv, así que con temas como una empresa concreta o datos en tiempo real la nota es genérica.

**Próximos pasos:** ver el backlog de la sección 2.
