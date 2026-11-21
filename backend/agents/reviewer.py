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
    summary = finding.summary if finding else "(sin resumen)"
    outcome = await router.complete(
        run_id=emitter.run_id,
        agent="reviewer",
        task="verify_claims",
        messages=[
            {"role": "system", "content": REVIEWER},
            {
                "role": "user",
                "content": f"Resumen de la investigación:\n{summary}\n\nNota:\n{proposal.markdown}",
            },
        ],
        validate=require_json_object("claims", "supported"),
    )
    await emitter.route(outcome.decision_event())

    data = json.loads(strip_code_fence(outcome.response.content or "{}"))
    claims = max(as_int(data.get("claims")), 0)
    # Un modelo pequeño puede devolver más «respaldadas» que afirmaciones: lo acotamos.
    supported = min(max(as_int(data.get("supported")), 0), claims)
    issues = [str(i) for i in data.get("issues", []) if str(i).strip()][:5]
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
