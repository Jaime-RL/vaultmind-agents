# Guion del vídeo (máximo 5 minutos)

Graba en la URL pública con una investigación real (cupo de 3 por IP y día). Antes de grabar:
abre la web un minuto antes (Render se duerme) y ten una pestaña en GitHub con el repo.
Tiempos aproximados; total ≈ 4:40.

## 0:00-0:30 · El problema (cámara o voz sobre la bienvenida)
- «Preparar el estado del arte del TFG lleva semanas, y en Obsidian acabas con conceptos
  enlazados que nunca llegan a tener nota.»
- «VaultMind es un equipo de cuatro agentes que investiga un tema y propone notas para tu
  bóveda, con fuentes reales. Y SmartRoute decide en cada paso si basta un modelo pequeño.»
- En pantalla: la bienvenida, que ya explica los cuatro agentes.

## 0:30-1:45 · Una investigación en directo
- Pulsa el ejemplo **multi-token prediction**.
- Señala la pestaña **Agentes**: el Explorador lee la bóveda; el Investigador busca en arXiv y
  Semantic Scholar; las decisiones del router (SLM en verde, grande en azul).
- Señala el **marcador de SmartRoute** sobre el grafo: «el modelo pequeño resuelve la mayoría
  de pasos; aquí va el ahorro frente a usar siempre el grande». Si hay una escalada, dilo.
- Los nodos nuevos aparecen en el grafo con su anillo de color.

## 1:45-2:45 · Confianza: el Revisor
- Pestaña **Notas**: insignia «✓ 5/5 respaldadas» y las fuentes (enlaces a arXiv).
- «El Revisor comprueba cada afirmación contra los abstracts. Si algo no se sostiene, el
  Redactor reescribe la nota: esta lleva la etiqueta "corregida".» (Si no sale ninguna
  corregida en la prueba real, enséñalo con una investigación de la demo.)
- **Editar** una frase → **Aprobar con cambios**. El nodo pasa a ser parte de tu grafo.
- Menciona «Profundizar» (no hace falta lanzarlo).

## 2:45-3:30 · Pregunta a tu bóveda
- Pestaña **Preguntar** → «¿Qué es la predicción multi-token?» (ya está en tu bóveda).
- La respuesta cita `[[notas]]`; pulsa una cita y la cámara vuela a ese nodo.
- Debajo: «respondió el SLM por X céntimos». «Si el modelo pequeño no cita tus notas,
  SmartRoute escala al grande.»

## 3:30-4:15 · Cómo se construyó con IA
- GitHub: `CLAUDE.md` (reglas para los agentes de código), `contracts/` (contrato primero),
  PRs revisadas y CI en verde.
- Un aprendizaje concreto: «La primera investigación real devolvió 0 fuentes: arXiv trataba
  "multitoken prediction" como palabras sueltas. Lo encontramos probando la app de verdad,
  no con los tests, y ahora es un test de regresión.»
- Si ya tienes la tabla de evals en el README: «con los casos de evaluación, SmartRoute
  ahorra un X % con el mismo acierto».

## 4:15-4:40 · Cierre
- Estado: siete historias de usuario, más de 380 tests, URL pública gratis y segura (cupos,
  cada visitante ve solo sus notas).
- Próximo paso: búsqueda semántica en «Preguntar» y un router aprendido de las trazas.
- «Repo y URL en la descripción.»
