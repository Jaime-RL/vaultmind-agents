"""Herramientas que un agente puede pedir con tool calling."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


class ToolError(Exception):
    """Fallo al ejecutar una herramienta (red caída, argumentos inválidos...).

    No rompe la investigación: el bucle devuelve el mensaje al modelo como
    resultado de la herramienta y el modelo decide qué hacer (reintentar,
    cambiar la búsqueda o seguir sin ese dato).
    """


@dataclass(frozen=True)
class ToolOutput:
    summary: str  # frase corta para el panel de la interfaz
    data: Any  # lo que recibe el modelo (se serializa a JSON)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema de los argumentos
    handler: Callable[[dict[str, Any]], Awaitable[ToolOutput]] = field(repr=False)

    def spec(self) -> dict[str, Any]:
        """Formato de herramienta de la API de OpenAI (lo entienden OpenRouter y Groq)."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
