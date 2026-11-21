"""Validadores de respuesta: deciden si la salida de un modelo es utilizable.

Un validador lanza LLMError si la respuesta no sirve. SmartRoute lo trata
igual que un fallo del proveedor: si venía del SLM, escala al modelo grande.
Así detectamos los fallos típicos de un modelo pequeño (JSON mal formado,
no llamar a la herramienta esperada) sin depender de que el proveedor falle.
"""

import json
from collections.abc import Callable
from typing import Any

from llm import LLMError, LLMResponse

Validator = Callable[[LLMResponse], None]


def require_json_object(*required_keys: str) -> Validator:
    """El contenido debe ser un objeto JSON con, al menos, estas claves."""

    def validate(response: LLMResponse) -> None:
        text = strip_code_fence(response.content or "")
        try:
            data: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError("La respuesta no es JSON válido") from exc
        if not isinstance(data, dict):
            raise LLMError("La respuesta JSON no es un objeto")
        missing = [key for key in required_keys if key not in data]
        if missing:
            raise LLMError(f"Faltan claves en la respuesta: {', '.join(missing)}")

    return validate


def require_tool_call(*allowed: str) -> Validator:
    """El modelo debe pedir al menos una herramienta, y solo de las permitidas."""

    def validate(response: LLMResponse) -> None:
        if not response.tool_calls:
            raise LLMError("Se esperaba una llamada a herramienta y no hubo ninguna")
        unknown = [call.name for call in response.tool_calls if call.name not in allowed]
        if unknown:
            raise LLMError(f"Herramienta desconocida: {', '.join(unknown)}")

    return validate


def strip_code_fence(text: str) -> str:
    """Muchos modelos envuelven el JSON en ```json ... ```: lo quitamos antes de parsear."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()
