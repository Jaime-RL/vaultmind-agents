"""Cliente LLM falso y guionizado para tests.

Se le da una lista de respuestas (o excepciones) y las devuelve en orden.
Además registra cada llamada, para que los tests comprueben qué modelo se
usó y con qué mensajes.
"""

import copy
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from llm.base import LLMResponse, Message, ToolSpec


class ScriptExhaustedError(AssertionError):
    """El código bajo test hizo más llamadas de las previstas en el guion.

    Hereda de AssertionError a propósito: es un fallo del test, no un error
    del modelo, así que SmartRoute NO debe tratarlo como un motivo para escalar
    (solo escala con LLMError). Si devolviéramos una respuesta vacía, un test
    mal escrito podría pasar en verde por casualidad.
    """


@dataclass
class RecordedCall:
    messages: list[Message]
    model: str
    tools: list[ToolSpec] | None


class FakeLLMClient:
    def __init__(self, script: Iterable[LLMResponse | Exception]):
        # Cada elemento es lo que devolverá la siguiente llamada. Una excepción
        # (p. ej. LLMError) se lanza en lugar de responder: sirve para simular
        # que el SLM falla y probar la escalada.
        self._script: deque[LLMResponse | Exception] = deque(script)
        self.calls: list[RecordedCall] = []

    @property
    def remaining(self) -> int:
        return len(self._script)

    async def complete(
        self,
        messages: list[Message],
        model: str,
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        # deepcopy: si el llamador modifica la lista después, el registro no cambia.
        self.calls.append(RecordedCall(copy.deepcopy(messages), model, copy.deepcopy(tools)))

        if not self._script:
            raise ScriptExhaustedError(
                f"FakeLLMClient: llamada nº {len(self.calls)} (modelo '{model}') "
                "sin respuesta en el guion"
            )

        item = self._script.popleft()
        if isinstance(item, Exception):
            raise item
        # Si el guion no fija el modelo, se rellena con el pedido, como haría el proveedor.
        return item if item.model else item.model_copy(update={"model": model})
