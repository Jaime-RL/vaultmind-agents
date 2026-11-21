"""Interfaz común para hablar con un LLM.

Los agentes y SmartRoute dependen solo de `LLMClient`, nunca de un proveedor
concreto. Así en producción se inyecta `OpenAICompatClient` y en los tests
`FakeLLMClient`, sin cambiar una línea de la lógica.
"""

from typing import Any, Protocol

from pydantic import BaseModel, Field

# Los mensajes y herramientas siguen el formato de la API de OpenAI
# ({"role": "user", "content": "..."}), que es el que hablan OpenRouter y Groq.
Message = dict[str, Any]
ToolSpec = dict[str, Any]


class LLMError(Exception):
    """Fallo al obtener una respuesta utilizable del modelo.

    SmartRoute captura este error para decidir si escala al modelo grande.
    """


class ToolCall(BaseModel):
    """Una llamada a herramienta pedida por el modelo, con los argumentos ya parseados."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """Respuesta normalizada, igual venga del proveedor real o del falso."""

    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMClient(Protocol):
    """Lo único que el resto del backend sabe de un LLM."""

    async def complete(
        self,
        messages: list[Message],
        model: str,
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse: ...
