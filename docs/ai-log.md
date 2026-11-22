# Registro de desarrollo con IA

Materia prima para la sección «Cómo se construyó con IA» del README. Apunta aquí, con fecha y persona, los prompts que funcionaron, los que fallaron y lo que aprendiste.

## Plantilla

### AAAA-MM-DD · Persona A/B · Tema
- **Prompt:** (copia el prompt o su parte importante)
- **Qué funcionó:**
- **Qué costó o falló:**
- **Qué cambiaría:**

---

### 2026-11-21 · Persona A · Arranque del repo
- **Prompt:** prompt de arranque de la Persona A (rol, stack, arquitectura, reglas y tarea del día), pidiendo un plan antes de programar.
- **Qué funcionó:** pedir el plan primero permitió fijar decisiones antes de escribir código (esquemas JSON como fuente de verdad del contrato; `FakeLLMClient` que falla si se acaba el guion).
- **Qué costó o falló:**
- **Qué cambiaría:**

### 2026-11-21 · Persona A · HU1: parser de la bóveda
- **Prompt:** «Parser de la bóveda (Markdown + wikilinks) → /api/vault, con tests. Crear la bóveda de demostración».
- **Qué funcionó:** escribir primero una bóveda mínima con todos los casos límite de Obsidian (alias, secciones, embebidos, nombres repetidos, código). Los tests encontraron un bug real: el `#` de `[[#Encabezado]]` se leía como etiqueta.
- **Qué costó o falló:** al arrancar el servidor a mano, la ruta por defecto `demo-vault` era relativa al directorio actual y fallaba desde `backend/`; los tests no lo detectaron porque pasaban la ruta explícita. Además, la regla `vault/` del `.gitignore` ignoraba en silencio `backend/vault/` y el código no se subía. Lección: probar la app real y revisar `git status` antes de dar algo por subido.
- **Qué cambiaría:** —

### 2026-11-21 · Persona A · SmartRoute y fixture de eventos
- **Prompt:** «SmartRoute: reglas por tipo de tarea, escalada si el SLM falla o devuelve un JSON inválido; registro de coste y latencia. Grabar fixtures/run_example.jsonl».
- **Qué funcionó:** tratar «respuesta rechazada por un validador» igual que «fallo del proveedor» (ambos son `LLMError`) simplificó la escalada a un solo `try/except`. Generar el fixture con los propios modelos del contrato en lugar de escribir JSON a mano: es válido por construcción y un test vigila que sus enlaces existan en la bóveda de demo.
- **Qué costó o falló:** decidir cómo contar el coste de una escalada; se cobra también el intento fallido del SLM, para que el ahorro mostrado no sea optimista.
- **Qué cambiaría:** los precios por defecto son orientativos; hay que fijarlos a los modelos reales antes de publicar cifras de ahorro.

### 2026-11-21 · Persona A · Explorador, Investigador y orquestador
- **Prompt:** «Agentes Explorador e Investigador (herramienta arXiv) y orquestador con límite de pasos».
- **Qué funcionó:** separar lo determinista de lo que necesita criterio. Detectar lagunas lo hace el parser (gratis y exacto); el LLM solo elige cuáles investigar, y su elección se filtra contra la lista real para que no pueda inventarse lagunas. Igual con las fuentes: el Investigador solo conserva URLs que arXiv devolvió de verdad.
- **Qué costó o falló:** el helper de tests intentaba añadir un atributo a `Tool`, que es inmutable (`frozen`). Se resolvió guardando el registro en la función manejadora.
- **Qué cambiaría:** los prompts están pensados para modelos pequeños (un solo formato de salida con ejemplo), pero falta probarlos con modelos reales en las evals.

### 2026-11-21 · Persona A · Redactor, Revisor, SQLite y SSE (plan del miércoles)
- **Prompt:** «HU2: agentes Redactor y Revisor; endpoint SSE real; persistencia de trazas en SQLite».
- **Qué funcionó:** no confiar al LLM lo que se puede garantizar con código. El Redactor solo redacta: los enlaces del grafo se calculan resolviendo sus `[[wikilinks]]` contra la bóveda real y la sección de fuentes la añade el código con las URLs verificadas. Para el SSE, guardar cada evento en SQLite y en memoria permite que un navegador que se conecta tarde (o recarga) reciba primero lo pasado y luego lo nuevo.
- **Qué costó o falló:** un test esperaba 4 métricas por investigación y había 5: el Investigador hace dos llamadas al LLM (buscar y responder). El test estaba mal, no el código; se dejó comentado por qué son 5. Ruff avisó de una lambda definida dentro de un bucle (B023), un error clásico de cierres en Python.
- **Qué cambiaría:** las investigaciones terminadas se quedan en memoria hasta reiniciar; con mucho uso habría que liberarlas.

### 2026-11-21 · Persona A · Propuestas, métricas, evals y prueba de punta a punta (jueves a sábado)
- **Prompt:** «HU3: /api/proposals, aprobar o rechazar, escritura segura en _copilot/», «HU4: /api/metrics», «Evals: 15-20 casos y % de acierto».
- **Qué funcionó:** tratar el título que da el LLM como entrada no confiable (limpieza de caracteres, nada de `..`, ni enlaces simbólicos fuera de la bóveda) y crear el fichero en modo exclusivo para no sobrescribir nunca. Una prueba de punta a punta con el cableado de producción y la red simulada (`httpx.MockTransport`) verificó de una vez el cliente OpenAI real, el tool calling, el SSE, SQLite, la aprobación y las métricas.
- **Qué costó o falló:** los tests del cliente OpenAI usaban objetos imitados; se comprobó aparte que `to_response` funciona con los objetos reales del SDK antes de fiarse.
- **Qué cambiaría:** las evals están listas pero no se han ejecutado: falta elegir los modelos y poner una clave. Sus resultados son los que deberían fijar la política del router, en lugar de las reglas escritas a mano.

### 2026-11-21 · Persona A · Modelo SLM y modo demo
- **Prompt:** «Usa Qwen de unos 7B de parámetros; hacemos una demo».
- **Qué funcionó:** comprobar el identificador y el precio del modelo en OpenRouter (y que admite tool calling) antes de configurarlo, y verificar en arxiv.org los papers que citan las notas de la demo para no publicar fuentes inventadas. La demo reutiliza el camino real (SSE, SQLite, propuestas, métricas): solo cambia de dónde salen los eventos.
- **Qué costó o falló:** un reemplazo con expresión regular en el script del fixture borró de más (tres llamadas que el formateador había partido en varias líneas). Se detectó revisando el diff antes de seguir. Lección: tras una edición automática, mirar el diff.
- **Qué cambiaría:** si la reproducción fallara a mitad, el flujo SSE quedaría abierto; se añadió que la demo cierre siempre con `error`, igual que una investigación real.

### 2026-11-21 · Persona A · Modelo grande y límites de la API pública
- **Prompt:** «Continúa» (con lo que no necesitaba decisión).
- **Qué funcionó:** elegir el modelo grande de la misma familia que el SLM (Qwen2.5 72B frente a 7B) y comprobar en OpenRouter su precio y que admite tool calling, imprescindible porque el Investigador puede escalar a él en mitad del bucle de herramientas.
- **Qué costó o falló:** con precios reales el ahorro de la demo bajó del 40 % al 31 %: el 72B es barato. Es la cifra honesta; el ahorro real lo dirán las evals.
- **Qué cambiaría:** el límite de investigaciones simultáneas es global; con usuarios reales convendría un límite por IP.

### 2026-11-21 · Persona B · Esqueleto del frontend e infraestructura
- **Prompt:** prompt de arranque de la Persona B con la tarea del sábado (esqueleto React + Vite, DevContainer, Dockerfile y docker-compose), pidiendo revisar `CLAUDE.md` y `contracts/` antes de proponer nada.
- **Qué funcionó:** pedir al agente que comprobara las dependencias entre paquetes antes de instalar: detectó que TypeScript 7 (la última) no es compatible con `typescript-eslint`, y se fijó `~6.0.3`. Generar los tipos TypeScript desde los esquemas JSON (`npm run gen:types`) en lugar de escribirlos a mano.
- **Qué costó o falló:** el entorno del agente no podía descargar imágenes de Docker, así que el Dockerfile se valida en la CI (build + arranque de la imagen + `/api/health`) y no en local.
- **Qué cambiaría:** decidir desde el día 1 que producción es un solo servicio (FastAPI sirve el frontend compilado): evita CORS y una URL distinta por entorno.

### 2026-11-21 · Persona B · Interfaz de HU1-HU4
- **Prompt:** tarea «avanza según el roadmap hasta estar a la par con el backend», con el modo demo de la Persona A (`DEMO_MODE=true`) como backend de desarrollo y `fixtures/run_example.jsonl` para los tests.
- **Qué funcionó:** poner toda la lógica de la investigación en directo en un reductor puro (`runReducer`): el test reproduce el fixture evento a evento y comprueba nodos y líneas sin red ni temporizadores. Probar cada historia con Playwright contra el backend real en modo demo destapó fallos que los tests no veían (cámara pegada a la última nota, fuentes duplicadas, botón cortado en móvil).
- **Qué costó o falló:** el SSE no pintaba nada en la primera idea porque el backend envía `event: <tipo>` y `EventSource.onmessage` solo recibe mensajes sin tipo: hay que escuchar cada tipo con `addEventListener`. Los colores «uno por agente» del roadmap no superan el validador de daltonismo junto al verde/azul del modelo (ninguna combinación de 4 tonos lo consigue): se sustituyeron por un único acento para las notas propuestas y el nombre del agente en texto.
- **Qué cambiaría:** validar la paleta con el script antes de escribir el primer componente, no después.

### 2026-11-21 · Persona A · URL pública con investigaciones reales, gratis y seguras
- **Prompt:** «¿Cuál es la mejor opción para que sea funcional, gratis y seguro que esté público?».
- **Qué funcionó:** comparar proveedores con datos actuales antes de decidir: los modelos `:free` de OpenRouter se quedaban en 50 peticiones al día, y Groq sin tarjeta no puede cobrar nada (solo limita). Proteger en capas: sin tarjeta (coste 0), clave solo en Render, cupo diario total y por IP, máximo de investigaciones simultáneas y vuelta automática a la demo cuando se agota el cupo.
- **Qué costó o falló:** elegir la IP para el cupo: la primera entrada de `X-Forwarded-For` la controla el cliente, así que se usa la última, la que añade el proxy de Render. Y comprobar en la documentación de Groq que gpt-oss devuelve el razonamiento en un campo aparte, para que no rompa el JSON que esperan los agentes.
- **Qué cambiaría:** el cupo se cuenta en SQLite, que en el plan gratuito de Render se borra al reiniciar; un reinicio repone el cupo. Para un uso serio haría falta un disco persistente o un almacén externo.

### 2026-11-22 · Persona A · Auditoría con una investigación real y mejoras de calidad
- **Prompt:** «Comprueba todo de forma exhaustiva, realiza pruebas, evalúa sus resultados de forma crítica y sugiere mejoras».
- **Qué funcionó:** probar en la URL pública con un tema real en lugar de fiarse de los tests verdes. Destapó un fallo que ningún test veía: arXiv trata `all:multitoken prediction` como palabras alternativas y devolvía papers de cáncer o de tráfico, así que el Investigador hacía bien en no citar nada. Contrastarlo con consultas directas a arXiv dio la solución: buscar primero la frase exacta y relajar la consulta solo si no hay resultados. También poner al Revisor antes de publicar y darle los abstracts como evidencia: una nota que dice «Qwen es de Baidu» ya no pasa porque el dato no está en ninguna fuente.
- **Qué costó o falló:** los tests usaban siempre un arXiv falso que devolvía el paper correcto, así que la calidad de las búsquedas nunca se probaba. Y en la URL pública cualquiera podía aprobar notas en la bóveda compartida: se resolvió con una cookie anónima por visitante y notas aprobadas que viven solo en su grafo.
- **Qué cambiaría:** incluir en las evals casos con la búsqueda real grabada (fixtures de respuestas de arXiv), no solo las respuestas del LLM.

### 2026-11-22 · Persona A (agente autónomo) · Fase 1: contrato de la revisión
- **Prompt:** roadmap autónomo (`docs/roadmap-autonomo.md`), fase 1.
- **Qué funcionó:** juntar en una sola PR de `contracts/` los dos cambios de `Proposal` que necesitan las fases siguientes (la revisión y la edición antes de aprobar). Así Iván revisa el contrato una vez. Los dos campos son opcionales: los clientes y datos antiguos siguen siendo válidos.
- **Qué costó o falló:** el test de deriva valida los ejemplos con `model_dump()`, que incluye los `None`; por eso los campos opcionales admiten `null` en el esquema (`anyOf` con `null`) en lugar de ser solo «no requeridos».
- **Qué cambiaría:** nada por ahora.

### 2026-11-22 · Persona A (agente autónomo) · Fase 2: revisión guardada en cada nota
- **Prompt:** roadmap autónomo, fase 2.
- **Qué funcionó:** adjuntar la revisión final a la `Proposal` justo antes de publicarla: la nota y su «5/5 respaldadas» viajan juntas a la base de datos y a la API, sin endpoints nuevos. La demo se regeneró con el mismo flujo que el código real (escribir → revisar → corregir → publicar), incluida una corrección en «Routing de modelos» para que el vídeo la enseñe.
- **Qué costó o falló:** un test de la demo contaba 10 tareas exactas; con la corrección son 12. Era una cifra mágica: ahora el comentario explica de dónde sale.
- **Qué cambiaría:** generar ese número desde el propio fixture en lugar de escribirlo a mano.

### 2026-11-22 · Persona A (agente autónomo) · Fase 3: confianza visible en cada nota
- **Prompt:** roadmap autónomo, fase 3 (frontend, para revisión de Iván).
- **Qué funcionó:** una insignia en la cabecera de cada tarjeta («✓ 5/5 respaldadas · corregida») que se ve sin abrir la nota. El color nunca va solo: lleva también icono y texto, para que se entienda con daltonismo. Reutiliza los colores de estado que ya tenía la interfaz (verde, ámbar, rojo). Comprobado con capturas de Playwright contra el servidor real en modo demo, no solo con tests.
- **Qué costó o falló:** react-markdown muestra los avisos de Obsidian (`> [!warning]`) como una cita con el texto «[!warning]» literal. Se resolvió con un componente `blockquote` propio que detecta el marcador, sin añadir dependencias ni HTML sin sanear.
- **Qué cambiaría:** el aviso se muestra como texto plano (pierde negritas o enlaces dentro del aviso); para avisos largos haría falta un plugin de remark.
