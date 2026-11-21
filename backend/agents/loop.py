"""Bucle ReAct: razonar → actuar con herramientas → observar → repetir.

En cada paso el modelo (elegido por SmartRoute) decide entre:
  - pedir una o varias herramientas → se ejecutan y su resultado vuelve al modelo;
  - dar la respuesta final → termina el bucle.

El número de pasos está limitado: un modelo que se queda en bucle pidiendo
herramientas no puede gastar tokens sin fin.
"""

import json
from typing import Any

from agents.events import Emitter
from agents.tools import Tool, ToolError
from app.contracts import Agent
from llm import LLMError, LLMResponse
from llm.base import Message
from router import SmartRoute, require_tool_call
from router.validators import Validator

MAX_STEPS = 8


class AgentStepLimitError(LLMError):
    """El agente agotó sus pasos sin dar una respuesta final."""


async def run_agent(
    *,
    agent: Agent,
    task: str,
    messages: list[Message],
    tools: list[Tool],
    router: SmartRoute,
    emitter: Emitter,
    final_validator: Validator,
    max_steps: int = MAX_STEPS,
) -> LLMResponse:
    by_name = {tool.name: tool for tool in tools}
    specs = [tool.spec() for tool in tools] or None
    check_tools = require_tool_call(*by_name)

    def validate_step(response: LLMResponse) -> None:
        # Un paso es válido si pide herramientas conocidas o si da una respuesta
        # final válida. Si no, SmartRoute lo trata como fallo y escala.
        if response.tool_calls:
            check_tools(response)
        else:
            final_validator(response)

    for _ in range(max_steps):
        outcome = await router.complete(
            run_id=emitter.run_id,
            agent=agent,
            task=task,
            messages=messages,
            tools=specs,
            validate=validate_step,
        )
        await emitter.route(outcome.decision_event())
        response = outcome.response

        if not response.tool_calls:
            return response  # respuesta final, ya validada

        # Algunos modelos explican qué van a hacer junto a la llamada: es el
        # «razonamiento» que se ve en el panel de la interfaz.
        if response.content and response.content.strip():
            await emitter.thought(agent, response.content.strip())

        messages.append(assistant_message(response))
        for call in response.tool_calls:
            await emitter.tool_call(agent, call.name, call.arguments)
            content, summary = await execute(by_name[call.name], call.arguments)
            await emitter.tool_result(agent, call.name, summary)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

    raise AgentStepLimitError(f"El agente '{agent}' agotó sus {max_steps} pasos")


async def execute(tool: Tool, arguments: dict[str, Any]) -> tuple[str, str]:
    """Ejecuta una herramienta y devuelve (contenido para el modelo, resumen para la interfaz)."""
    try:
        output = await tool.handler(arguments)
    except ToolError as exc:
        # El error vuelve al modelo como resultado: puede reintentar o seguir sin el dato.
        return json.dumps({"error": str(exc)}, ensure_ascii=False), f"error: {exc}"
    return json.dumps(output.data, ensure_ascii=False), output.summary


def assistant_message(response: LLMResponse) -> Message:
    """Mensaje del asistente con sus tool_calls, en el formato que espera la API de OpenAI."""
    return {
        "role": "assistant",
        "content": response.content,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments, ensure_ascii=False),
                },
            }
            for call in response.tool_calls
        ],
    }
