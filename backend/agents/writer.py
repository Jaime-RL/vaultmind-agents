"""Redactor: convierte cada hallazgo del Investigador en una nota propuesta.

Lo que se deja al modelo: redactar. Lo que NO se le deja:
- Los enlaces del grafo se calculan resolviendo sus [[wikilinks]] contra la
  bóveda real: un enlace a una nota inexistente no aparece en el grafo.
- La sección de fuentes la añade el código con las URLs verificadas, así no
  puede inventarse referencias.
"""

import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from agents.events import Emitter
from agents.prompts import WRITER, WRITER_NO_SOURCES, WRITER_REVISION
from agents.researcher import Finding, vault_usage
from app.contracts import Language, Proposal
from app.i18n import NOTE_SECTION_MARKERS, language_instruction, tr
from llm import LLMError, LLMResponse
from router import SmartRoute
from vault import Vault
from vault.parser import WIKILINK_RE, LinkResolver

MAX_TITLES_IN_PROMPT = 150

# Se llama con cada nota en cuanto está redactada, ANTES de emitir node_proposed:
# así, cuando la interfaz recibe el evento y pide /api/proposals, la nota ya está
# guardada (en el modo demo ya se hacía en este orden).
ProposalCallback = Callable[[Proposal], Awaitable[None]]


def require_markdown_note(response: LLMResponse) -> None:
    """Validador: la nota debe tener contenido real, no una frase suelta."""
    text = (response.content or "").strip()
    if len(text) < 120:
        raise LLMError("La nota es demasiado corta")
    if text.startswith("{") or text.startswith("["):
        raise LLMError("Se esperaba Markdown y llegó JSON")


async def write_notes(
    *,
    topic: str,
    findings: list[Finding],
    vault: Vault,
    router: SmartRoute,
    emitter: Emitter,
    on_proposal: ProposalCallback | None = None,
) -> list[Proposal]:
    titles = sorted(note.title for note in vault.notes.values())[:MAX_TITLES_IN_PROMPT]
    resolver = LinkResolver(list(vault.notes))
    proposals = []
    for finding in findings:
        try:
            proposals.append(
                await write_note(topic, finding, titles, resolver, router, emitter, on_proposal)
            )
        except LLMError as exc:
            await emitter.thought(
                "writer", tr(emitter.lang, "writer.failed", title=finding.gap.name, error=exc)
            )
    return proposals


async def write_note(
    topic: str,
    finding: Finding,
    titles: list[str],
    resolver: LinkResolver,
    router: SmartRoute,
    emitter: Emitter,
    on_proposal: ProposalCallback | None = None,
) -> Proposal:
    """Redacta y publica (guarda + node_proposed) una nota, sin pasar por el Revisor."""
    proposal = await draft_note(topic, finding, titles, resolver, router, emitter)
    await publish(proposal, emitter, on_proposal)
    return proposal


async def draft_note(
    topic: str,
    finding: Finding,
    titles: list[str],
    resolver: LinkResolver,
    router: SmartRoute,
    emitter: Emitter,
    *,
    previous: Proposal | None = None,
    issues: list[str] | None = None,
    lang: Language = "es",
) -> Proposal:
    """Redacta la nota (o la reescribe si se pasa `previous` + `issues`) sin publicarla."""
    title = finding.gap.name
    if previous is None:
        await emitter.thought("writer", tr(emitter.lang, "writer.start", title=title))
    system = WRITER.replace("{title}", title)
    if not finding.sources:
        system += WRITER_NO_SOURCES.format(warning=tr(lang, "note.warning"))
    system += language_instruction(lang)
    user = (
        f"Tema de la investigación: {topic}\n"
        f"Concepto: {title}{vault_usage(finding.gap)}\n\n"
        f"Resumen de la investigación:\n{finding.summary}\n\n"
        f"Fuentes (con su abstract):\n{evidence(finding)}\n\n"
        f"Notas existentes:\n" + "\n".join(f"- {t}" for t in titles)
    )
    if previous is not None:
        user += WRITER_REVISION.format(
            previous=note_body(previous.markdown),
            issues="\n".join(f"- {i}" for i in issues or []),
        )
    outcome = await router.complete(
        run_id=emitter.run_id,
        agent="writer",
        task="write_note",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        validate=require_markdown_note,
    )
    await emitter.route(outcome.decision_event())

    body = fix_heading(
        normalize_wikilinks(strip_markdown_fence(outcome.response.content or "")), title
    )
    markdown = (
        body.rstrip() + "\n" + sources_section(finding, lang) + mentioned_in_section(finding, lang)
    )
    return Proposal(
        # Una reescritura conserva el id: para la interfaz es la misma nota.
        id=previous.id if previous is not None else f"p-{uuid.uuid4().hex[:8]}",
        run_id=emitter.run_id,
        title=title,
        markdown=markdown,
        sources=[{"title": s.title, "url": s.url} for s in finding.sources],
        links=resolve_links(markdown, resolver),
        agent="writer",
        model=outcome.metric.model,
        status="pending",
        created_at=datetime.now(UTC),
        language=lang,
    )


async def publish(
    proposal: Proposal, emitter: Emitter, on_proposal: ProposalCallback | None = None
) -> None:
    """Guarda la nota y DESPUÉS emite node_proposed (la interfaz la pide al recibir el evento)."""
    if on_proposal is not None:
        await on_proposal(proposal)
    await emitter.proposed(proposal.id, proposal.title, proposal.links)


def evidence(finding: Finding, max_chars: int = 800) -> str:
    """Fuentes verificadas con su abstract: es la evidencia con la que se escribe y se revisa."""
    if not finding.sources:
        return "- (ninguna)"
    return "\n".join(
        f"- {s.title} ({s.url})" + (f"\n  Abstract: {s.abstract[:max_chars]}" if s.abstract else "")
        for s in finding.sources
    )


def fix_heading(body: str, title: str) -> str:
    """El encabezado es siempre el título de la propuesta.

    Regresión (evals/quality.py): el modelo escribió «# SLAN en robótica» en la nota
    «SLAM en robótica». El título ya lo decidió el Explorador; el modelo no lo cambia.
    """
    lines = body.lstrip().splitlines()
    if lines and lines[0].startswith("# "):
        lines[0] = f"# {title}"
    else:
        lines = [f"# {title}", ""] + lines
    return "\n".join(lines)


def note_body(markdown: str) -> str:
    """La nota sin las secciones que añade el código (fuentes y «Mencionada en»), en
    cualquiera de los idiomas."""
    cut = len(markdown)
    for marker in NOTE_SECTION_MARKERS:
        found = markdown.find(marker)
        if found != -1:
            cut = min(cut, found)
    return markdown[:cut].strip()


def sources_section(finding: Finding, lang: Language = "es") -> str:
    heading = f"\n## {tr(lang, 'note.sources')}\n\n"
    if not finding.sources:
        return heading + f"- {tr(lang, 'note.no_sources')}\n"
    lines = "\n".join(f"- [{s.title}]({s.url})" for s in finding.sources)
    return heading + lines + "\n"


def mentioned_in_section(finding: Finding, lang: Language = "es") -> str:
    """Enlaza la nota nueva con las notas que la mencionaban: así queda conectada en el grafo."""
    notes = ", ".join(f"[[{note_id}]]" for note_id in finding.gap.mentioned_in)
    return f"\n*{tr(lang, 'note.mentioned', notes=notes)}*\n" if notes else ""


def resolve_links(markdown: str, resolver: LinkResolver) -> list[str]:
    """ids de notas existentes enlazadas desde la nota, sin duplicados y en orden."""
    found: list[str] = []
    for match in WIKILINK_RE.finditer(markdown):
        target = resolver.resolve(match.group(1).strip()) if match.group(1).strip() else None
        if target and target not in found:
            found.append(target)
    return found


# Guiones tipográficos que los modelos usan a veces: ‐ ‑ ‒ – — y el signo menos.
TYPOGRAPHIC_HYPHENS = str.maketrans({c: "-" for c in "\u2010\u2011\u2012\u2013\u2014\u2212"})


def normalize_wikilinks(markdown: str) -> str:
    """Cambia los guiones tipográficos por «-» dentro de los [[enlaces]].

    En las evals con Groq, el modelo grande escribió [[Fine‑tuning]] con U+2011: se ve igual,
    pero no enlaza con la nota «Fine-tuning». Solo se toca el interior de los enlaces.
    """
    return WIKILINK_RE.sub(lambda m: m.group(0).translate(TYPOGRAPHIC_HYPHENS), markdown)


def strip_markdown_fence(text: str) -> str:
    """Quita un ```markdown ... ``` envolvente si el modelo lo añade."""
    text = text.strip()
    match = re.match(r"^```(?:markdown|md)?\s*\n(.*)\n```$", text, re.DOTALL)
    return match.group(1).strip() if match else text
