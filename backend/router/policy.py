"""Qué modelo intenta primero cada tipo de tarea.

MVP: reglas fijas por tipo de tarea. Es deliberadamente simple: las trazas que
genere SmartRoute (qué tareas escalan y cuáles no) son los datos con los que,
en el backlog, se podría entrenar un router aprendido.
"""

from dataclasses import dataclass, field

from app.contracts import Tier

DEFAULT_POLICY: dict[str, Tier] = {
    # Tareas acotadas y verificables: el SLM suele bastar, y si falla se escala.
    # Explorador: decidir qué lagunas están RELACIONADAS con el tema. Empezó en el SLM, pero
    # las evals con Groq (22-11-2026) dieron un 60 % de acierto frente al 100 % del grande:
    # el SLM añadía lagunas sin relación, un fallo que ningún validador detecta (el JSON es
    # correcto), así que SmartRoute nunca escalaría. Una llamada al grande cuesta ~0,0001 $.
    "find_gaps": "large",
    "summarize_paper": "slm",  # Investigador: resumir un abstract
    "verify_claims": "slm",  # Revisor: ¿cada afirmación tiene su fuente?
    "answer_question": "slm",  # Pregunta a tu bóveda: responder con notas ya seleccionadas
    # Tareas de redacción o razonamiento largo: directamente al modelo grande.
    "plan_research": "large",
    "write_note": "large",
}


@dataclass(frozen=True)
class RoutingPolicy:
    rules: dict[str, Tier] = field(default_factory=lambda: dict(DEFAULT_POLICY))
    # Una tarea sin regla va al modelo grande: ante la duda, preferimos calidad a ahorro.
    default: Tier = "large"

    def tier_for(self, task: str) -> tuple[Tier, str]:
        """Devuelve el nivel y el motivo legible que se mostrará en la interfaz."""
        if task in self.rules:
            tier = self.rules[task]
            reason = (
                "tarea acotada: se intenta primero con el modelo pequeño"
                if tier == "slm"
                else "tarea compleja: se asigna directamente al modelo grande"
            )
            return tier, reason
        return self.default, "tarea sin regla: por prudencia se usa el modelo grande"
