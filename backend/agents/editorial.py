"""Bucle editorial: Redactor → Revisor → (Redactor corrige → Revisor) → publicar.

Antes, cada nota se publicaba aunque el Revisor encontrara que casi nada tenía respaldo.
Ahora el Revisor actúa ANTES de publicar y, si encuentra alguna afirmación que no está
respaldada por la evidencia (resumen + abstracts), el Redactor reescribe la nota una vez
quitando lo dudoso. Una sola vuelta: acota el coste y evita bucles infinitos.

Si el Revisor falla, la nota se publica igualmente: perder una nota por un fallo de la
revisión sería peor que publicarla sin revisar (el usuario decide al aprobar).
"""

from dataclasses import dataclass

from agents.events import Emitter
from agents.researcher import Finding
from agents.reviewer import Review, needs_revision, review_note
from agents.writer import ProposalCallback, draft_note, publish
from app.contracts import Proposal
from llm import LLMError
from router import SmartRoute
from vault import Vault
from vault.parser import LinkResolver

MAX_TITLES_IN_PROMPT = 150


@dataclass
class EditorialResult:
    proposals: list[Proposal]
    reviews: list[Review]
    revisions: int = 0  # notas que el Redactor tuvo que reescribir


async def write_and_review(
    *,
    topic: str,
    findings: list[Finding],
    vault: Vault,
    router: SmartRoute,
    emitter: Emitter,
    on_proposal: ProposalCallback | None = None,
) -> EditorialResult:
    titles = sorted(note.title for note in vault.notes.values())[:MAX_TITLES_IN_PROMPT]
    resolver = LinkResolver(list(vault.notes))
    result = EditorialResult(proposals=[], reviews=[])

    for finding in findings:
        name = finding.gap.name
        try:
            proposal = await draft_note(topic, finding, titles, resolver, router, emitter)
        except LLMError as exc:
            await emitter.thought("writer", f"No pude redactar «{name}»: {exc}")
            continue

        review = await safe_review(proposal, finding, router, emitter)
        if needs_revision(review) and finding.sources:
            assert review is not None  # needs_revision ya lo garantiza; ayuda al tipado
            await emitter.thought(
                "writer",
                f"El Revisor solo respalda {review.supported} de {review.claims} afirmaciones: "
                f"corrijo «{name}».",
            )
            try:
                revised = await draft_note(
                    topic,
                    finding,
                    titles,
                    resolver,
                    router,
                    emitter,
                    previous=proposal,
                    issues=review.issues,
                )
            except LLMError as exc:
                await emitter.thought("writer", f"No pude corregir «{name}»: {exc}")
            else:
                result.revisions += 1
                proposal = revised
                review = await safe_review(revised, finding, router, emitter) or review

        await publish(proposal, emitter, on_proposal)
        result.proposals.append(proposal)
        if review is not None:
            result.reviews.append(review)
    return result


async def safe_review(
    proposal: Proposal, finding: Finding, router: SmartRoute, emitter: Emitter
) -> Review | None:
    try:
        return await review_note(proposal, finding, router, emitter)
    except LLMError as exc:
        await emitter.thought("reviewer", f"No pude revisar «{proposal.title}»: {exc}")
        return None
