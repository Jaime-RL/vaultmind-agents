# Plan de mejoras de VaultMind (tras la auditoría del 22-11-2026)

Prompt para un agente de código (Persona A, backend). Sigue `CLAUDE.md`: tests sin red ni LLM,
Conventional Commits, **sin ninguna atribución a una IA** en commits ni PRs, y no cambies
`contracts/` sin avisar (necesita la PR compartida con la Persona B).

## Contexto: lo que mostró la prueba real en la URL pública

Tema: «que es multitoken prediction» (Groq, gpt-oss-20b / gpt-oss-120b).

- ✅ El Explorador investiga solo el tema pedido; el Revisor da problemas concretos.
- ❌ **0 fuentes verificadas.** `all:multitoken prediction` hace que arXiv trate las palabras
  como alternativas y devuelva papers sin relación (cáncer, tráfico…). Con
  `all:"multi-token prediction"` salen los papers correctos (Meta, *Better & Faster LLMs via
  Multi-token Prediction*).
- ❌ Sin fuentes, la nota sale de la memoria del modelo: definición imprecisa y una mención a
  «consulta climática» que viene del prompt («Tema del TFG») y no del tema.
- ❌ La nota se propone aunque el Revisor diga «0 de 5 afirmaciones con respaldo».
- ❌ En la URL pública cualquiera ve y aprueba todas las propuestas, y lo aprobado se escribe en la
  bóveda de demostración compartida.

## Bloque A — calidad y seguridad (solo backend)

1. **Búsqueda en arXiv por niveles.** Si la consulta no trae sintaxis de arXiv (`ti:`, `AND`…):
   frase exacta `all:"…"` → todas las palabras con `AND` → consulta original. Se pasa al nivel
   siguiente si el anterior no devuelve nada. Prompt: términos técnicos en inglés con su forma
   habitual («multi-token», no «multitoken»).
2. **Notas basadas en los abstracts.** El Investigador guarda el abstract de cada fuente
   verificada; el Redactor y el Revisor lo reciben. El Revisor comprueba contra los abstracts.
3. **Bucle Revisor → Redactor.** Si menos del 80 % de las afirmaciones tienen respaldo, el
   Redactor reescribe la nota una vez quitando lo que no se sostiene, y se vuelve a revisar. Sin
   fuentes, la nota se escribe en modo prudente (definición breve y aviso visible).
4. **Quitar la fuga del TFG.** «Tema del TFG» → «Tema de la investigación».
5. **URL pública segura.** Cada visitante (cookie de sesión anónima) ve y resuelve solo sus
   propuestas. Con `VAULT_WRITES_ENABLED=false`, aprobar marca la nota como aprobada pero no
   escribe en la bóveda compartida.
6. Tests de regresión para cada punto. Después: ruff, pytest, rama y enlace de PR para que la cree
   la persona (desde GitHub, sin pie de IA).

## Bloque B — necesita `contracts/` (PR compartida con la Persona B)

- Añadir a `Proposal` el resultado de la revisión (`review: {claims, supported, issues}`) y
  mostrarlo en la tarjeta de la nota con un indicador de color.
- Mostrar la versión reescrita por el bucle de corrección («revisada 1 vez»).

## Bloque C — funcionalidad que aporta valor

- **Pregunta a tu bóveda:** chat que responde con tus notas (búsqueda léxica + embeddings
  opcionales), cita `[[nota]]` y usa SmartRoute (pregunta sencilla → SLM). Es casi el mismo
  problema que el TFG (chatbot con SLMs).
- **Editar la nota antes de aprobarla.**
- **Más fuentes:** Semantic Scholar u OpenAlex (citas, año, venue) y Wikipedia para conceptos
  generales; el Investigador elige la herramienta.
- **Evals con Groq en el README:** tabla «% de tareas resueltas por el SLM, coste frente a solo
  modelo grande, escaladas». Es la prueba de que SmartRoute funciona.
- **Persistencia en Render:** las métricas se pierden en cada deploy; usar un disco o aceptar el
  reinicio y decirlo en el README.
- **Streaming del texto** de la nota mientras se redacta.
