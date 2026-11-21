# Arquitectura del chatbot

Primer boceto:

- El usuario pregunta en lenguaje natural.
- Un [[Agente de IA]] decide si necesita datos y llama a herramientas ([[Tool calling]]).
- Las herramientas consultan [[Open-Meteo]] (previsión e histórico) o el [[Copernicus Climate Data Store]].
- Para preguntas conceptuales se usa [[RAG]] sobre documentación climática.
- El modelo base será un [[SLM]] cuantizado ([[Cuantización]]).

Pendiente: decidir entre [[Llama]] y [[Qwen]] como familia de modelos.

#tfg #arquitectura
