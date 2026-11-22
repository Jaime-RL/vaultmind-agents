"""Explorador: decide qué conceptos investigar a partir del tema y de la bóveda.

1. El TEMA que pide el estudiante se investiga siempre: es lo que ha pedido.
2. Además, las LAGUNAS de la bóveda (conceptos enlazados sin nota) que estén
   directamente relacionadas con el tema. Si ninguna lo está, no se fuerza ninguna.

Reparto de trabajo deliberado:
- Detectar lagunas es determinista (lo hace el parser): no gastamos tokens en ello.
- Titular la nota del tema y decidir qué lagunas están relacionadas requiere criterio:
  eso lo hace el LLM, y su respuesta se contrasta con la bóveda real.
Es una tarea acotada, así que SmartRoute la manda primero al modelo pequeño.
"""

import json
import re
from dataclasses import dataclass, field

from agents.events import Emitter
from agents.prompts import EXPLORER
from router import SmartRoute, require_json_object
from router.validators import strip_code_fence
from vault import Vault
from vault.parser import LinkResolver

MAX_TITLE_LENGTH = 80


@dataclass(frozen=True)
class Gap:
    """Un concepto a investigar: el tema pedido o una laguna de la bóveda."""

    name: str  # título de la nota que se propondrá, p. ej. "LoRA"
    mentioned_in: list[str]  # ids de las notas que lo enlazan (vacío para el tema nuevo)
    # True para el tema que pidió el usuario; False para las lagunas añadidas por relación.
    # Una laguna sin fuentes se descarta; el tema se investiga siempre (ver researcher.py).
    is_topic: bool = field(default=False, compare=False)


async def explore(
    *, topic: str, vault: Vault, router: SmartRoute, emitter: Emitter, max_gaps: int = 3
) -> list[Gap]:
    await emitter.thought(
        "explorer",
        f"Leo la bóveda: {len(vault.notes)} notas. Busco conceptos enlazados que no tienen nota.",
    )
    await emitter.tool_call("explorer", "find_gaps", {})
    gaps = dict(vault.unresolved_links())
    await emitter.tool_result(
        "explorer",
        "find_gaps",
        f"{len(gaps)} lagunas: {', '.join(gaps)}" if gaps else "ninguna laguna",
    )
    ranked = sorted(gaps, key=lambda name: (-len(gaps[name]), name))  # más mencionadas primero

    if not gaps:
        # Sin lagunas no hay nada que elegir: se investiga solo el tema, sin gastar una llamada.
        topic_title, related, reasoning = clean_title(topic), [], ""
    else:
        candidates = "\n".join(
            f"- {name} (mencionada en {len(gaps[name])} notas)" for name in ranked
        )
        outcome = await router.complete(
            run_id=emitter.run_id,
            agent="explorer",
            task="find_gaps",
            messages=[
                {"role": "system", "content": EXPLORER.format(max_related=max(max_gaps - 1, 0))},
                {"role": "user", "content": f"Tema: {topic}\n\nLagunas:\n{candidates}"},
            ],
            validate=require_json_object("selected"),
        )
        await emitter.route(outcome.decision_event())
        answer = json.loads(strip_code_fence(outcome.response.content or "{}"))
        topic_title = clean_title(str(answer.get("topic_note") or "")) or clean_title(topic)
        # Solo lagunas reales: el modelo no puede inventarlas ni cambiar su escritura.
        related = match_existing(answer.get("selected", []), ranked)
        reasoning = str(answer.get("reasoning", "")).strip()

    concepts = topic_concept(topic_title, gaps, vault)
    for name in related:
        if len(concepts) >= max_gaps:
            break
        if all(name.lower() != c.name.lower() for c in concepts):
            concepts.append(Gap(name=name, mentioned_in=gaps[name]))

    await emitter.thought("explorer", explanation(topic_title, concepts, reasoning))
    return concepts


def topic_concept(title: str, gaps: dict[str, list[str]], vault: Vault) -> list[Gap]:
    """La nota del tema: reutiliza una laguna si coincide; si ya existe una nota, no se repite."""
    for name, mentions in gaps.items():
        if name.lower() == title.lower():
            return [Gap(name=name, mentioned_in=mentions, is_topic=True)]
    if LinkResolver(list(vault.notes)).resolve(title) is not None:
        return []  # ya hay una nota con ese título: proponer otra la duplicaría
    return [Gap(name=title, mentioned_in=[], is_topic=True)] if title else []


def explanation(topic_title: str, concepts: list[Gap], reasoning: str) -> str:
    names = [c.name for c in concepts]
    if not names:
        return f"Ya tienes una nota sobre «{topic_title}» y no hay lagunas relacionadas."
    text = f"Investigo: {', '.join(names)}."
    if not any(c.name.lower() == topic_title.lower() for c in concepts):
        text = f"Ya tienes una nota sobre «{topic_title}». " + text
    return text + (f" {reasoning}" if reasoning else "")


def clean_title(text: str) -> str:
    """Título seguro para una nota: sin caracteres de enlace de Obsidian ni de ruta.

    El título se convierte en nombre de fichero: quitamos «/», «\\» y «..» para que un modelo
    no pueda colar una ruta (el escritor de la bóveda también las rechaza, por partida doble).
    """
    title = re.sub(r"[\[\]|#^/\\:*?\"<>]", " ", text).replace("..", " ")
    title = re.sub(r"\s+", " ", title).strip(" .\"'«»")
    if len(title) > MAX_TITLE_LENGTH:
        title = title[:MAX_TITLE_LENGTH].rsplit(" ", 1)[0]
    return title[:1].upper() + title[1:]


def match_existing(selected: list, existing: list[str]) -> list[str]:
    """Se queda solo con lagunas reales, sin distinguir mayúsculas y sin duplicados.

    Protege frente a un modelo que «inventa» lagunas o cambia su escritura.
    """
    if not isinstance(selected, list):
        return []
    by_lower = {name.lower(): name for name in existing}
    result: list[str] = []
    for item in selected:
        name = by_lower.get(str(item).strip().lower())
        if name and name not in result:
            result.append(name)
    return result
