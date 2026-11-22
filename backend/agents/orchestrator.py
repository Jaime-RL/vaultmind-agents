"""Orquestador: encadena los agentes de una investigación y cierra con un evento final.

Explorador → Investigador → Redactor ⇄ Revisor

Pase lo que pase, el flujo de eventos termina con `run_finished` o con `error`:
la interfaz siempre sabe cuándo ha acabado la investigación.
"""

import time
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field

from agents.editorial import write_and_review
from agents.events import Emitter
from agents.explorer import Gap, explore
from agents.researcher import Finding, research
from agents.reviewer import Review
from agents.tools import Tool
from agents.writer import ProposalCallback
from app.contracts import ContentLanguage, Proposal, RunStats
from app.i18n import note_language, tr
from router import SmartRoute
from vault import Vault


@dataclass
class ResearchResult:
    gaps: list[Gap] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    proposals: list[Proposal] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
    stats: RunStats | None = None


async def run_research(
    *,
    topic: str,
    vault: Vault,
    router: SmartRoute,
    emitter: Emitter,
    search_tool: Tool,
    extra_tools: Sequence[Tool] = (),
    on_proposal: ProposalCallback | None = None,
    max_gaps: int = 3,
    clock: Callable[[], float] = time.monotonic,
    language: ContentLanguage = "auto",
    pending_titles: Collection[str] = (),
) -> ResearchResult | None:
    """`pending_titles`: propuestas sin revisar del usuario; no se vuelven a investigar."""
    start = clock()
    result = ResearchResult()
    # Idioma de las notas: el elegido o, con «auto», el de la bóveda (salvo que el tema sea
    # claramente una frase en otro idioma). Los mensajes del panel van en emitter.lang.
    vault_texts = [note.content for note in vault.notes.values()]
    lang = note_language(language, topic, vault_texts, ui=emitter.lang)
    try:
        result.gaps = await explore(
            topic=topic,
            vault=vault,
            router=router,
            emitter=emitter,
            max_gaps=max_gaps,
            lang=lang,
            pending_titles=pending_titles,
        )
        result.findings = await research(
            topic=topic,
            gaps=result.gaps,
            router=router,
            emitter=emitter,
            search_tool=search_tool,
            extra_tools=extra_tools,
        )
        # Redactor y Revisor trabajan nota a nota: el Revisor actúa ANTES de publicar y, si
        # la nota no se sostiene, el Redactor la corrige una vez (ver agents/editorial.py).
        # Cada nota se guarda (on_proposal) antes de emitir su node_proposed.
        editorial = await write_and_review(
            topic=topic,
            findings=result.findings,
            vault=vault,
            router=router,
            emitter=emitter,
            on_proposal=on_proposal,
            lang=lang,
        )
        result.proposals, result.reviews = editorial.proposals, editorial.reviews
    except AssertionError:
        raise  # fallo de un test (p. ej. guion de FakeLLMClient agotado): que se vea
    except Exception as exc:  # noqa: BLE001 — cualquier fallo debe cerrar el flujo con 'error'
        await emitter.error(tr(emitter.lang, "run.stopped", error=exc))
        return None

    totals = router.totals(emitter.run_id)
    result.stats = RunStats(
        notes_proposed=len(result.proposals),
        cost_usd=totals.cost_usd,
        baseline_cost_usd=totals.baseline_cost_usd,
        savings_usd=totals.savings_usd,
        escalations=totals.escalations,
        duration_s=round(clock() - start, 3),
    )
    await emitter.finished(result.stats)
    return result
