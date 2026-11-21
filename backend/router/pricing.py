from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    """Precio de un modelo en USD por millón de tokens, como lo publican los proveedores."""

    input_per_mtok: float
    output_per_mtok: float

    def cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (
            prompt_tokens * self.input_per_mtok + completion_tokens * self.output_per_mtok
        ) / 1_000_000
