"""Redactor: convierte cada hallazgo del Investigador en una nota propuesta.

Lo que se deja al modelo: redactar. Lo que NO se le deja:
- Los enlaces del grafo se calculan resolviendo sus [[wikilinks]] contra la
  bóveda real: un enlace a una nota inexistente no aparece en el grafo.
- La sección de fuentes la añade el código con las URLs verificadas, así no
  puede inventarse referencias.
"""

import re
import uuid
from datetime import UTC, datetime

from agents.events import Emitter
from agents.prompts import WRITER
from agents.researcher import Finding
from app.contracts import Proposal
from llm import LLMError, LLMResponse
from router import SmartRoute
from vault import Vault
from vault.parser import WIKILINK_RE, LinkResolver

MAX_TITLES_IN_PROMPT = 150


def require_markdown_note(response: LLMResponse) -> None:
    """Validador: la nota debe tener contenido real, no una frase suelta."""
    text = (response.content or "").strip()
    if len(text) < 120:
        raise LLMError("La nota es demasiado corta")
    if text.startswith("{") or text.startswith("["):
        raise LLMError("Se esperaba Markdown y llegó JSON")


async def write_notes(
    *, topic: str, findings: list[Finding], vault: Vault, router: SmartRoute, emitter: Emitter
) -> list[Proposal]:
    titles = sorted(note.title for note in vault.notes.values())[:MAX_TITLES_IN_PROMPT]
    resolver = LinkResolver(list(vault.notes))
    proposals = []
    for finding in findings:
        try:
            proposals.append(await write_note(topic, finding, titles, resolver, router, emitter))
        except LLMError as exc:
            await emitter.thought("writer", f"No pude redactar «{finding.gap.name}»: {exc}")
    return proposals


async def write_note(
    topic: str,
    finding: Finding,
    titles: list[str],
    resolver: LinkResolver,
    router: SmartRoute,
    emitter: Emitter,
) -> Proposal:
    title = finding.gap.name
    await emitter.thought("writer", f"Redacto la nota «{title}».")
    sources = "\n".join(f"- {s.title} ({s.url})" for s in finding.sources) or "- (ninguna)"
    outcome = await router.complete(
        run_id=emitter.run_id,
        agent="writer",
        task="write_note",
        messages=[
            {"role": "system", "content": WRITER.replace("{title}", title)},
            {
                "role": "user",
                "content": (
                    f"Tema del TFG: {topic}\n"
                    f"Concepto: {title}\n\n"
                    f"Resumen de la investigación:\n{finding.summary}\n\n"
                    f"Fuentes:\n{sources}\n\n"
                    f"Notas existentes:\n" + "\n".join(f"- {t}" for t in titles)
                ),
            },
        ],
        validate=require_markdown_note,
    )
    await emitter.route(outcome.decision_event())

    body = strip_markdown_fence(outcome.response.content or "")
    markdown = body.rstrip() + "\n" + sources_section(finding) + mentioned_in_section(finding)
    links = resolve_links(markdown, resolver)

    proposal = Proposal(
        id=f"p-{uuid.uuid4().hex[:8]}",
        run_id=emitter.run_id,
        title=title,
        markdown=markdown,
        sources=[{"title": s.title, "url": s.url} for s in finding.sources],
        links=links,
        agent="writer",
        model=outcome.metric.model,
        status="pending",
        created_at=datetime.now(UTC),
    )
    await emitter.proposed(proposal.id, proposal.title, proposal.links)
    return proposal


def sources_section(finding: Finding) -> str:
    if not finding.sources:
        return "\n## Fuentes\n\n- Sin fuentes verificadas: revisa esta nota con cuidado.\n"
    lines = "\n".join(f"- [{s.title}]({s.url})" for s in finding.sources)
    return f"\n## Fuentes\n\n{lines}\n"


def mentioned_in_section(finding: Finding) -> str:
    """Enlaza la nota nueva con las notas que la mencionaban: así queda conectada en el grafo."""
    notes = ", ".join(f"[[{note_id}]]" for note_id in finding.gap.mentioned_in)
    return f"\n*Mencionada en: {notes}. Propuesta por VaultMind.*\n" if notes else ""


def resolve_links(markdown: str, resolver: LinkResolver) -> list[str]:
    """ids de notas existentes enlazadas desde la nota, sin duplicados y en orden."""
    found: list[str] = []
    for match in WIKILINK_RE.finditer(markdown):
        target = resolver.resolve(match.group(1).strip()) if match.group(1).strip() else None
        if target and target not in found:
            found.append(target)
    return found


def strip_markdown_fence(text: str) -> str:
    """Quita un ```markdown ... ``` envolvente si el modelo lo añade."""
    text = text.strip()
    match = re.match(r"^```(?:markdown|md)?\s*\n(.*)\n```$", text, re.DOTALL)
    return match.group(1).strip() if match else text
