"""Explorador: encuentra las lagunas de la bóveda y elige cuáles investigar.

Reparto de trabajo deliberado:
- Detectar lagunas es determinista (lo hace el parser): no gastamos tokens en ello.
- Elegir las más relevantes para el tema sí requiere criterio: eso lo hace el LLM.
Es una tarea acotada, así que SmartRoute la manda primero al modelo pequeño.
"""

import json
from dataclasses import dataclass

from agents.events import Emitter
from agents.prompts import EXPLORER
from router import SmartRoute, require_json_object
from router.validators import strip_code_fence
from vault import Vault


@dataclass(frozen=True)
class Gap:
    name: str  # texto del [[enlace]] sin nota, p. ej. "LoRA"
    mentioned_in: list[str]  # ids de las notas que lo enlazan


async def explore(
    *, topic: str, vault: Vault, router: SmartRoute, emitter: Emitter, max_gaps: int = 3
) -> list[Gap]:
    await emitter.thought(
        "explorer",
        f"Leo la bóveda: {len(vault.notes)} notas. Busco conceptos enlazados que no tienen nota.",
    )
    await emitter.tool_call("explorer", "find_gaps", {})
    gaps = {name: notes for name, notes in vault.unresolved_links().items()}
    await emitter.tool_result(
        "explorer",
        "find_gaps",
        f"{len(gaps)} lagunas: {', '.join(gaps)}" if gaps else "ninguna laguna",
    )
    if not gaps:
        await emitter.thought("explorer", "La bóveda no tiene lagunas: no hay nada que investigar.")
        return []

    # Más mencionadas primero: es el orden de respaldo si el modelo no elige bien.
    ranked = sorted(gaps, key=lambda name: (-len(gaps[name]), name))
    candidates = "\n".join(f"- {name} (mencionada en {len(gaps[name])} notas)" for name in ranked)

    outcome = await router.complete(
        run_id=emitter.run_id,
        agent="explorer",
        task="find_gaps",
        messages=[
            {"role": "system", "content": EXPLORER.format(max_gaps=max_gaps)},
            {"role": "user", "content": f"Tema: {topic}\n\nLagunas:\n{candidates}"},
        ],
        validate=require_json_object("selected"),
    )
    await emitter.route(outcome.decision_event())

    answer = json.loads(strip_code_fence(outcome.response.content or "{}"))
    chosen = match_existing(answer.get("selected", []), ranked)[:max_gaps]
    if not chosen:
        # El modelo eligió lagunas que no existen: usamos las más mencionadas.
        chosen = ranked[:max_gaps]

    reasoning = str(answer.get("reasoning", "")).strip()
    await emitter.thought(
        "explorer",
        f"Priorizo: {', '.join(chosen)}." + (f" {reasoning}" if reasoning else ""),
    )
    return [Gap(name=name, mentioned_in=gaps[name]) for name in chosen]


def match_existing(selected: list, existing: list[str]) -> list[str]:
    """Se queda solo con lagunas reales, sin distinguir mayúsculas y sin duplicados.

    Protege frente a un modelo que «inventa» lagunas o cambia su escritura.
    """
    by_lower = {name.lower(): name for name in existing}
    result: list[str] = []
    for item in selected:
        name = by_lower.get(str(item).strip().lower())
        if name and name not in result:
            result.append(name)
    return result
