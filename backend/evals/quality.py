"""Evaluación de calidad de punta a punta: investigaciones reales sobre la bóveda de demo.

Las evals de `evals.run` miden tareas sueltas (¿vale el SLM para X?). Esta mide el
producto entero: para varios temas lanza Explorador → Investigador → Redactor ⇄ Revisor
con modelos reales y arXiv, y guarda cada nota propuesta con datos para juzgarla:

- qué conceptos eligió el Explorador (el tema y las lagunas «relacionadas»),
- con qué notas de la bóveda enlaza cada nota y cuáles de esos enlaces existen,
- fuentes, revisión (afirmaciones respaldadas) y coste.

Los temas mezclan casos del dominio de la bóveda (LLMs, RAG, clima) y casos ajenos
(Raft, SLAM...), porque los ajenos son los que delatan lagunas forzadas.

NO corre en la CI (CLAUDE.md, regla 1). Se lanza a mano desde Actions → «Evals» con
mode=quality, o en local con la clave en el entorno:

    PYTHONPATH=. uv run python -m evals.quality
"""

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from agents.events import Emitter, ListSink
from agents.orchestrator import run_research
from app.config import Settings
from app.services import build_services
from vault import Vault, parse_vault
from vault.parser import LinkResolver

RESULTS_DIR = Path(__file__).parent / "results"

# (tema, ¿del dominio de la bóveda de demo?)
TOPICS: list[tuple[str, bool]] = [
    ("Mixture of Experts", True),
    ("Interpolación de datos meteorológicos", True),
    ("Speculative decoding", True),
    ("Raft consensus algorithm", False),
    ("SLAM en robótica", False),
    ("Q-learning", False),
    ("Criptografía de curva elíptica", False),
    ("previsión de bolsa Banco Santander", False),
]


@dataclass
class NoteReport:
    title: str
    is_topic: bool
    mentioned_in: list[str]
    links: list[str]
    links_existing: list[str]  # enlaces que apuntan a notas reales de la bóveda
    sources: list[str]
    claims: int | None
    supported: int | None
    model: str
    markdown: str


@dataclass
class TopicReport:
    topic: str
    in_domain: bool
    concepts: list[str] = field(default_factory=list)
    explorer_reasoning: list[str] = field(default_factory=list)
    notes: list[NoteReport] = field(default_factory=list)
    cost_usd: float = 0.0
    error: str | None = None


def existing_links(links: list[str], vault: Vault) -> list[str]:
    resolver = LinkResolver(list(vault.notes))
    return [link for link in links if resolver.resolve(link) is not None]


async def run_topic(topic: str, in_domain: bool, services, vault: Vault) -> TopicReport:
    report = TopicReport(topic=topic, in_domain=in_domain)
    runs = services.runs
    sink = ListSink()
    emitter = Emitter(f"quality-{abs(hash(topic)) % 10**8}", sink, lang="es")
    result = await run_research(
        topic=topic,
        vault=vault,
        router=runs.router_factory(),
        emitter=emitter,
        search_tool=runs.search_tool,
        extra_tools=runs.extra_tools,
        max_gaps=runs.max_gaps,
    )
    report.explorer_reasoning = [
        e.text for e in sink.events if e.type == "agent_thought" and e.agent == "explorer"
    ]
    if result is None:
        errors = [getattr(e, "message", "") for e in sink.events if e.type == "error"]
        report.error = "; ".join(errors) or "error"
        return report
    report.concepts = [g.name + (" (tema)" if g.is_topic else "") for g in result.gaps]
    gaps = {g.name.lower(): g for g in result.gaps}
    for proposal in result.proposals:
        gap = gaps.get(proposal.title.lower())
        review = proposal.review
        report.notes.append(
            NoteReport(
                title=proposal.title,
                is_topic=bool(gap and gap.is_topic),
                mentioned_in=list(gap.mentioned_in) if gap else [],
                links=proposal.links,
                links_existing=existing_links(proposal.links, vault),
                sources=[s.title for s in proposal.sources],
                claims=review.claims if review else None,
                supported=review.supported if review else None,
                model=proposal.model,
                markdown=proposal.markdown,
            )
        )
    report.cost_usd = result.stats.cost_usd if result.stats else 0.0
    return report


def to_markdown(reports: list[TopicReport]) -> str:
    lines = ["# Evaluación de calidad de punta a punta", ""]
    lines += [
        "| Tema | Dominio | Conceptos elegidos | Notas | Enlaces a la bóveda | Fuentes | Coste |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in reports:
        links = sum(len(n.links_existing) for n in r.notes)
        sources = ", ".join(str(len(n.sources)) for n in r.notes) or "–"
        lines.append(
            f"| {r.topic} | {'sí' if r.in_domain else 'no'} | {', '.join(r.concepts) or r.error} "
            f"| {len(r.notes)} | {links} | {sources} | ${r.cost_usd:.4f} |"
        )
    for r in reports:
        lines += ["", f"## {r.topic}", ""]
        lines += [f"> {t}" for t in r.explorer_reasoning]
        for n in r.notes:
            review = f"{n.supported}/{n.claims}" if n.claims is not None else "sin revisión"
            lines += [
                "",
                f"### {n.title} {'(tema)' if n.is_topic else '(laguna)'}",
                f"- Mencionada en: {', '.join(n.mentioned_in) or '—'}",
                f"- Enlaces: {', '.join(n.links) or '—'}",
                f"- Existen en la bóveda: {', '.join(n.links_existing) or '—'}",
                f"- Fuentes: {' | '.join(n.sources) or '—'}",
                f"- Revisión: {review} · modelo {n.model}",
                "",
                "<details><summary>Nota</summary>",
                "",
                n.markdown,
                "",
                "</details>",
            ]
    return "\n".join(lines) + "\n"


async def main(only: list[str] | None) -> int:
    settings = Settings()
    services = build_services(settings)
    if services.runs.router_factory is None:
        print("Falta LLM_API_KEY, SLM_MODEL o LARGE_MODEL", file=sys.stderr)
        return 1
    vault = parse_vault(settings.vault_path)
    topics = [t for t in TOPICS if not only or t[0] in only]
    reports = []
    for topic, in_domain in topics:
        print(f"→ {topic}", file=sys.stderr)
        try:
            reports.append(await run_topic(topic, in_domain, services, vault))
        except Exception as exc:  # noqa: BLE001 — un tema roto no debe tumbar el informe
            reports.append(TopicReport(topic=topic, in_domain=in_domain, error=str(exc)))

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    (RESULTS_DIR / f"quality-{stamp}.json").write_text(
        json.dumps([asdict(r) for r in reports], ensure_ascii=False, indent=2)
    )
    markdown = to_markdown(reports)
    (RESULTS_DIR / f"quality-{stamp}.md").write_text(markdown)
    print(markdown)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="temas concretos (por defecto, todos)")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.only)))
