"""Cliente real contra cualquier API compatible con OpenAI (OpenRouter, Groq...)."""

import json
from typing import Any

import httpx
from openai import APIError, AsyncOpenAI

from llm.base import LLMError, LLMResponse, Message, ToolCall, ToolSpec


class OpenAICompatClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 60.0,
        http_client: httpx.AsyncClient | None = None,
        reasoning_effort: str | None = None,
    ):
        # http_client permite inyectar un transporte simulado en los tests de punta a punta.
        self._reasoning_effort = reasoning_effort
        self._client = AsyncOpenAI(
            base_url=base_url, api_key=api_key, timeout=timeout, http_client=http_client
        )

    async def complete(
        self,
        messages: list[Message],
        model: str,
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if tools:  # algunos proveedores rechazan tools=[]: solo se envía si hay herramientas
            kwargs["tools"] = tools
        if self._reasoning_effort:
            # Parámetro de los modelos de razonamiento; va en extra_body para que el SDK
            # no lo valide contra su lista de parámetros conocidos.
            kwargs["extra_body"] = {"reasoning_effort": self._reasoning_effort}
        try:
            completion = await self._client.chat.completions.create(**kwargs)
        except APIError as exc:
            raise LLMError(f"Error del proveedor con '{model}': {exc}") from exc
        return to_response(completion)


def to_response(completion: Any) -> LLMResponse:
    """Convierte la respuesta del SDK en un LLMResponse.

    Está separada del cliente para poder testearla sin red. Si el modelo
    devuelve argumentos de herramienta que no son JSON válido, lanza LLMError:
    es justo el fallo típico de un SLM que SmartRoute debe resolver escalando.
    """
    if not completion.choices:
        raise LLMError("El proveedor devolvió una respuesta sin 'choices'")

    message = completion.choices[0].message
    tool_calls = []
    for call in message.tool_calls or []:
        try:
            arguments = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError as exc:
            raise LLMError(
                f"Argumentos no válidos en la herramienta '{call.function.name}'"
            ) from exc
        if not isinstance(arguments, dict):
            raise LLMError(f"Los argumentos de '{call.function.name}' no son un objeto JSON")
        tool_calls.append(ToolCall(id=call.id, name=call.function.name, arguments=arguments))

    usage = completion.usage
    return LLMResponse(
        content=message.content,
        tool_calls=tool_calls,
        model=completion.model or "",
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
    )
