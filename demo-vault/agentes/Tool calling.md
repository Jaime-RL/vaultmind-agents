---
tags: [agentes, tfg]
---
# Tool calling

Capacidad de un modelo para pedir la ejecución de una función externa devolviendo su nombre y sus argumentos en un formato estructurado (normalmente JSON). El programa ejecuta la función y le devuelve el resultado.

Es la base de cualquier [[Agente de IA]]. Riesgo con un [[SLM]]: que genere JSON inválido o elija mal la herramienta. Hace falta estudiar más [[Function calling en SLMs]].

Ejemplo de herramienta para el TFG: `get_forecast(lat, lon)` sobre [[Open-Meteo]].
