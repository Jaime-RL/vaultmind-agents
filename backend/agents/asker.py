"""«Pregunta a tu bóveda»: responde con las notas del estudiante y las cita como [[nota]].

1. BM25 elige las notas más relevantes (determinista, sin tokens).
2. SmartRoute intenta con el SLM. El validador exige que la respuesta cite al menos una de
   las notas dadas: si el SLM no cita nada (o cita notas inventadas) se escala al grande.
3. Las citas se calculan resolviendo los [[wikilinks]] de la respuesta contra las notas que
   se le dieron: el modelo no puede «citar» una nota que no ha leído.
"""

from dataclasses import dataclass

from agents.prompts import ASKER
from app.contracts import AskCitation, AskResponse, ContentLanguage
from app.i18n import language_instruction, resolve_language, tr
from llm import LLMError, LLMResponse
from router import SmartRoute
from vault import Vault
from vault.parser import WIKILINK_RE, LinkResolver
from vault.search import Hit, search

MAX_NOTES = 5
MAX_NOTE_CHARS = 1500

NO_NOTES = tr("es", "ask.no_notes")


@dataclass(frozen=True)
class AskContext:
    hits: list[Hit]
    resolver: LinkResolver  # solo resuelve las notas que se le dieron al modelo


def context_for(vault: Vault, question: str) -> AskContext:
    hits = search(vault, question, k=MAX_NOTES)
    return AskContext(hits, LinkResolver([h.note_id for h in hits]))


def cited(answer: str, context: AskContext) -> list[AskCitation]:
    """Notas dadas que la respuesta cita, en orden de aparición y sin repetir."""
    titles = {h.note_id: h.title for h in context.hits}
    result: list[AskCitation] = []
    for match in WIKILINK_RE.finditer(answer):
        note_id = context.resolver.resolve(match.group(1).strip())
        if note_id and all(c.id != note_id for c in result):
            result.append(AskCitation(id=note_id, title=titles[note_id]))
    return result


def require_citation(context: AskContext):
    """Validador para SmartRoute: la respuesta debe citar al menos una de las notas dadas."""

    def validate(response: LLMResponse) -> None:
        text = (response.content or "").strip()
        if len(text) < 20:
            raise LLMError("La respuesta está vacía o es demasiado corta")
        if not cited(text, context):
            raise LLMError("La respuesta no cita ninguna de las notas de la bóveda")

    return validate


async def answer_question(
    *,
    question: str,
    vault: Vault,
    router: SmartRoute | None,
    run_id: str,
    language: ContentLanguage = "auto",
) -> AskResponse:
    """`language`: idioma de la respuesta; con «auto», el de la pregunta (o español)."""
    lang = resolve_language(language, question)
    context = context_for(vault, question)
    if not context.hits:
        return AskResponse(
            answer=tr(lang, "ask.no_notes"),
            citations=[],
            model=None,
            tier=None,
            escalated=False,
            cost_usd=0.0,
            language=lang,
        )
    if router is None:
        # Sin modelo configurado (o con el cupo agotado): al menos señalamos dónde mirar.
        links = ", ".join(f"[[{h.title}]]" for h in context.hits[:3])
        answer = tr(lang, "ask.no_llm", links=links)
        return AskResponse(
            answer=answer,
            citations=cited(answer, context),
            model=None,
            tier=None,
            escalated=False,
            cost_usd=0.0,
            language=lang,
        )

    notes = "\n\n".join(
        f"## [[{h.title}]]\n{vault.notes[h.note_id].content[:MAX_NOTE_CHARS]}" for h in context.hits
    )
    outcome = await router.complete(
        run_id=run_id,
        agent="researcher",
        task="answer_question",
        messages=[
            {"role": "system", "content": ASKER + language_instruction(lang)},
            {"role": "user", "content": f"Notas de la bóveda:\n\n{notes}\n\nPregunta: {question}"},
        ],
        validate=require_citation(context),
    )
    answer = (outcome.response.content or "").strip()
    return AskResponse(
        answer=answer,
        citations=cited(answer, context),
        model=outcome.metric.model,
        tier=outcome.metric.tier,
        escalated=outcome.metric.escalated,
        cost_usd=router.totals(run_id).cost_usd,
        language=lang,
    )
