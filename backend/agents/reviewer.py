"""Revisor: comprueba si las afirmaciones de cada nota están respaldadas.

No bloquea ninguna nota: la decisión final es del estudiante. Su trabajo es
dejar a la vista los problemas antes de que apruebe. Es una tarea acotada,
así que va primero al modelo pequeño.
"""

import json
from dataclasses import dataclass, field

from agents.events import Emitter
from agents.prompts import REVIEWER
from agents.researcher import Finding
from agents.writer import evidence, note_body
from app.contracts import Proposal
from llm import LLMError
from router import SmartRoute, require_json_object
from router.validators import strip_code_fence


@dataclass(frozen=True)
class Review:
    proposal_id: str
    claims: int
    supported: int
    issues: list[str] = field(default_factory=list)


async def review_notes(
    *,
    proposals: list[Proposal],
    findings: list[Finding],
    router: SmartRoute,
    emitter: Emitter,
) -> list[Review]:
    by_title = {f.gap.name: f for f in findings}
    reviews = []
    for proposal in proposals:
        finding = by_title.get(proposal.title)
        try:
            reviews.append(await review_note(proposal, finding, router, emitter))
        except LLMError as exc:
            await emitter.thought("reviewer", f"No pude revisar «{proposal.title}»: {exc}")
    return reviews


async def review_note(
    proposal: Proposal, finding: Finding | None, router: SmartRoute, emitter: Emitter
) -> Review:
    await emitter.tool_call("reviewer", "verify_claims", {"proposal_id": proposal.id})
    if finding is not None:
        proof = f"Resumen de la investigación:\n{finding.summary}\n\nFuentes:\n{evidence(finding)}"
    else:
        proof = "(sin evidencia)"
    outcome = await router.complete(
        run_id=emitter.run_id,
        agent="reviewer",
        task="verify_claims",
        messages=[
            {"role": "system", "content": REVIEWER},
            {
                "role": "user",
                "content": f"EVIDENCIA\n{proof}\n\nNOTA\n{note_body(proposal.markdown)}",
            },
        ],
        validate=require_json_object("claims", "supported"),
    )
    await emitter.route(outcome.decision_event())

    data = json.loads(strip_code_fence(outcome.response.content or "{}"))
    claims = max(as_int(data.get("claims")), 0)
    # Un modelo pequeño puede devolver más «respaldadas» que afirmaciones: lo acotamos.
    supported = min(max(as_int(data.get("supported")), 0), claims)
    issues = unique_issues(data.get("issues", []))
    review = Review(proposal.id, claims, supported, issues)

    await emitter.tool_result(
        "reviewer", "verify_claims", f"{supported} de {claims} afirmaciones con respaldo"
    )
    if issues:
        await emitter.thought(
            "reviewer",
            f"En «{proposal.title}» revisa antes de aprobar: " + "; ".join(issues),
        )
    return review


def as_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def unique_issues(raw, limit: int = 5) -> list[str]:
    """Problemas sin duplicados (un modelo pequeño tiende a repetir la misma frase)."""
    if not isinstance(raw, list):
        return []
    result: list[str] = []
    for item in raw:
        text = " ".join(str(item).split())
        if text and text.lower() not in {r.lower() for r in result}:
            result.append(text)
    return result[:limit]


def needs_revision(review: Review | None) -> bool:
    """¿Reescribir? Si el Revisor encontró CUALQUIER afirmación sin respaldo.

    Empezamos con un umbral del 80 %, pero en la prueba real una nota con «Qwen-3D» (una
    variante que no existe) sacó 4 de 5 y pasaba. Una afirmación inventada ya es motivo para
    corregir: cuesta una llamada más al modelo grande y solo se hace una vez.
    """
    if review is None or review.claims == 0:
        return False
    return review.supported < review.claims
