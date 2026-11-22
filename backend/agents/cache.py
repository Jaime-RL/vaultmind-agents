"""Caché en memoria con caducidad para las búsquedas de los agentes.

Varias investigaciones (o varios visitantes) buscan a menudo lo mismo: «multi-token
prediction» dos veces en una hora no debería hacer dos peticiones a arXiv. Ahorra tiempo
(arXiv pide 3 s entre peticiones) y es más respetuoso con APIs públicas y gratuitas.
"""

import time
from collections import OrderedDict
from collections.abc import Callable


class TTLCache[T]:
    def __init__(
        self,
        ttl_s: float = 24 * 3600,
        max_items: int = 256,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.ttl_s, self.max_items, self.clock = ttl_s, max_items, clock
        self._items: OrderedDict[str, tuple[float, T]] = OrderedDict()

    def get(self, key: str) -> T | None:
        item = self._items.get(key)
        if item is None:
            return None
        stored_at, value = item
        if self.clock() - stored_at > self.ttl_s:
            del self._items[key]
            return None
        self._items.move_to_end(key)  # usada hace poco: la última en salir
        return value

    def set(self, key: str, value: T) -> None:
        self._items[key] = (self.clock(), value)
        self._items.move_to_end(key)
        while len(self._items) > self.max_items:
            self._items.popitem(last=False)  # se descarta la menos usada
