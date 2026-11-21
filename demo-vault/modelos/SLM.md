---
tags: [modelos, tfg]
---
# SLM (Small Language Model)

Modelo de lenguaje con pocos parámetros (aproximadamente de cientos de millones a unos pocos miles de millones). Comparte arquitectura con un [[LLM]] ([[Transformer]]) pero es mucho más barato de ejecutar e incluso cabe en un portátil.

Técnicas para que rindan bien:
- [[Destilación de conocimiento]] desde un modelo grande.
- [[Fine-tuning]] en el dominio concreto (aquí, clima), por ejemplo con [[LoRA]].
- [[Cuantización]] para reducir memoria.

Pregunta abierta para el TFG: ¿son fiables con [[Tool calling]]?
