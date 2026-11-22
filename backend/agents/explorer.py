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
from collections.abc import Collection
from dataclasses import dataclass, field

from agents.events import Emitter
from agents.prompts import EXPLORER
from app.contracts import Language
from app.i18n import language_instruction, tr
from router import SmartRoute, require_json_object
from router.validators import strip_code_fence
from vault import Vault
from vault.parser import LinkResolver
from vault.search import search

NEARBY_NOTES = 5  # notas de la bóveda más parecidas al tema entre las que buscar lagunas

MAX_TITLE_LENGTH = 80


@dataclass(frozen=True)
class Gap:
    """Un concepto a investigar: el tema pedido o una laguna de la bóveda."""

    name: str  # título de la nota que se propondrá, p. ej. "LoRA"
    mentioned_in: list[str]  # ids de las notas que lo enlazan (vacío para el tema nuevo)
    # True para el tema que pidió el usuario; False para las lagunas añadidas por relación.
    # Una laguna sin fuentes se descarta; el tema se investiga siempre (ver researcher.py).
    is_topic: bool = field(default=False, compare=False)
    # Cómo usa la bóveda el concepto: frases de las notas que lo enlazan. Sin esto, una laguna
    # como «Routing de modelos» (en la bóveda: elegir entre SLM y LLM) se investigaba con el
    # significado del tema (el routing interno de Mixture of Experts). Ver evals/quality.py.
    context: tuple[str, ...] = field(default=(), compare=False)


async def explore(
    *,
    topic: str,
    vault: Vault,
    router: SmartRoute,
    emitter: Emitter,
    max_gaps: int = 3,
    lang: Language = "es",
    pending_titles: Collection[str] = (),
) -> list[Gap]:
    """`lang`: idioma del contenido; el título de la nota del tema se escribe en él.

    `pending_titles`: títulos de las propuestas que el usuario aún no ha revisado. No se
    vuelven a investigar: lanzar dos veces el mismo tema duplicaba notas (y gastaba tokens).
    """
    pending = {title.lower() for title in pending_titles}
    await emitter.thought("explorer", tr(emitter.lang, "explorer.reading", n=len(vault.notes)))
    await emitter.tool_call("explorer", "find_gaps", {})
    # Las lagunas que ya tienen una propuesta pendiente no se ofrecen al modelo.
    gaps = {
        name: notes
        for name, notes in vault.unresolved_links().items()
        if name.lower() not in pending
    }
    await emitter.tool_result(
        "explorer",
        "find_gaps",
        tr(emitter.lang, "explorer.gaps", n=len(gaps), names=", ".join(gaps))
        if gaps
        else tr(emitter.lang, "explorer.no_gaps"),
    )
    # Solo se ofrecen al modelo las lagunas de la «vecindad» del tema: las mencionadas en las
    # notas que más se le parecen (BM25). El modelo, aun con instrucciones, enlazaba lagunas
    # sin relación («LoRA» para la previsión de bolsa, «Evaluación de agentes» para
    # Q-learning); con un tema ajeno a la bóveda ahora no hay ninguna candidata.
    near = nearby(vault, topic, gaps)
    ranked = sorted(near, key=lambda name: (-len(gaps[name]), name))  # más mencionadas primero

    if not gaps:
        # Sin lagunas no hay nada que elegir: se investiga solo el tema, sin gastar una llamada.
        topic_title, related, reasoning = clean_title(topic), [], ""
    else:
        candidates = (
            "\n".join(
                f"- {name} (mencionada en {len(gaps[name])} notas)"
                + "".join(f"\n    · {line}" for line in mention_context(vault, name, gaps[name]))
                for name in ranked
            )
            or "(ninguna cerca del tema: no elijas ninguna)"
        )
        outcome = await router.complete(
            run_id=emitter.run_id,
            agent="explorer",
            task="find_gaps",
            messages=[
                {
                    "role": "system",
                    "content": EXPLORER.format(max_related=max(max_gaps - 1, 0))
                    + language_instruction(lang)
                    + " Translate only the topic_note title; copy gap names exactly.",
                },
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
    skipped = [c.name for c in concepts if c.name.lower() in pending]
    concepts = [c for c in concepts if c.name.lower() not in pending]
    for name in related:
        if len(concepts) >= max_gaps:
            break
        if all(name.lower() != c.name.lower() for c in concepts):
            context = mention_context(vault, name, gaps[name])
            concepts.append(Gap(name=name, mentioned_in=gaps[name], context=context))

    if skipped:
        names = ", ".join(f"«{name}»" for name in skipped)
        await emitter.thought("explorer", tr(emitter.lang, "explorer.pending", names=names))
    if concepts or not skipped:
        await emitter.thought(
            "explorer", explanation(topic_title, concepts, reasoning, emitter.lang)
        )
    return concepts


def nearby(vault: Vault, topic: str, gaps: dict[str, list[str]]) -> list[str]:
    """Lagunas mencionadas en las notas más parecidas al tema, o cuyo nombre aparece en él."""
    close = {hit.note_id for hit in search(vault, topic, k=NEARBY_NOTES, stems=False)}
    lower = topic.lower()
    return [
        name
        for name, mentions in gaps.items()
        if close.intersection(mentions) or name.lower() in lower
    ]


def topic_concept(title: str, gaps: dict[str, list[str]], vault: Vault) -> list[Gap]:
    """La nota del tema: reutiliza una laguna si coincide; si ya existe una nota, no se repite."""
    for name, mentions in gaps.items():
        if name.lower() == title.lower():
            context = mention_context(vault, name, mentions)
            return [Gap(name=name, mentioned_in=mentions, is_topic=True, context=context)]
    if LinkResolver(list(vault.notes)).resolve(title) is not None:
        return []  # ya hay una nota con ese título: proponer otra la duplicaría
    return [Gap(name=title, mentioned_in=[], is_topic=True)] if title else []


def explanation(
    topic_title: str, concepts: list[Gap], reasoning: str, lang: Language = "es"
) -> str:
    names = [c.name for c in concepts]
    if not names:
        return tr(lang, "explorer.nothing", title=topic_title)
    text = tr(lang, "explorer.investigating", names=", ".join(names))
    if not any(c.name.lower() == topic_title.lower() for c in concepts):
        text = tr(lang, "explorer.already", title=topic_title) + " " + text
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


def mention_context(
    vault: Vault, name: str, note_ids: list[str], limit: int = 2, max_chars: int = 220
) -> tuple[str, ...]:
    """Frases de la bóveda donde aparece [[name]], con el título de la nota delante.

    Es barato (sin LLM) y le da al Explorador, al Investigador y al Redactor el SIGNIFICADO
    que el estudiante le da al concepto, no solo su nombre.
    """
    link = re.compile(r"\[\[" + re.escape(name) + r"(?:[|#\]])", re.IGNORECASE)
    lines: list[str] = []
    for note_id in note_ids:
        note = vault.notes.get(note_id)
        if note is None:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", note.content):
            if link.search(sentence):
                text = " ".join(sentence.split())
                if len(text) > max_chars:
                    text = text[: max_chars - 1].rsplit(" ", 1)[0] + "…"
                lines.append(f"{note.title}: «{text}»")
                break  # una frase por nota basta
        if len(lines) >= limit:
            break
    return tuple(lines)
