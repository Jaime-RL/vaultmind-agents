"""Investigador: busca en arXiv cada laguna y resume lo encontrado.

Es un agente ReAct de verdad: el modelo decide qué buscar, cuántas veces y
cuándo tiene suficiente. Cada laguna se investiga por separado, así un fallo
en una no tira la investigación entera.
"""

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from agents.events import Emitter
from agents.explorer import Gap
from agents.loop import run_agent
from agents.prompts import RESEARCHER
from agents.tools import Tool, ToolOutput
from app.i18n import tr
from llm import LLMError
from router import SmartRoute, require_json_object
from router.validators import strip_code_fence


@dataclass(frozen=True)
class Source:
    title: str
    url: str
    # Abstract tal como lo devolvió arXiv: el Redactor y el Revisor lo usan como evidencia,
    # para que la nota no dependa solo del resumen (que el modelo puede adornar).
    abstract: str = field(default="", compare=False)


@dataclass(frozen=True)
class Finding:
    gap: Gap
    summary: str
    sources: list[Source] = field(default_factory=list)


async def research(
    *,
    topic: str,
    gaps: list[Gap],
    router: SmartRoute,
    emitter: Emitter,
    search_tool: Tool,
    extra_tools: Sequence[Tool] = (),
) -> list[Finding]:
    findings = []
    for gap in gaps:
        try:
            finding = await research_gap(topic, gap, router, emitter, search_tool, extra_tools)
        except LLMError as exc:
            await emitter.thought(
                "researcher", tr(emitter.lang, "researcher.failed", gap=gap.name, error=exc)
            )
            continue
        if not finding.sources and not gap.is_topic:
            # Una laguna «relacionada» sin ningún paper que la respalde suele ser una relación
            # mal elegida por el Explorador: mejor no proponer una nota escrita de memoria.
            await emitter.thought(
                "researcher", tr(emitter.lang, "researcher.dropped", gap=gap.name)
            )
            continue
        findings.append(finding)
    return findings


async def research_gap(
    topic: str,
    gap: Gap,
    router: SmartRoute,
    emitter: Emitter,
    search_tool: Tool,
    extra_tools: Sequence[Tool] = (),
) -> Finding:
    # Envolvemos la herramienta para anotar qué papers devolvió de verdad arXiv:
    # así descartamos fuentes que el modelo se haya inventado.
    seen: dict[str, Source] = {}  # clave normalizada → fuente tal como la devolvió arXiv
    queries: set[str] = set()

    def tracked(search: Tool) -> Tool:
        async def handler(args: dict) -> ToolOutput:
            return await tracked_call(search, args)

        return Tool(search.name, search.description, search.parameters, handler)

    async def tracked_call(search: Tool, args: dict) -> ToolOutput:
        query = search.name + ":" + " ".join(str(args.get("query", "")).lower().split())
        if query and query in queries:
            # El modelo repite una búsqueda: se lo decimos en lugar de gastar otra petición.
            return ToolOutput(
                summary=tr(emitter.lang, "tool.repeated"),
                data={
                    "note": "Ya hiciste esta búsqueda: usa esos resultados o cambia los términos."
                },
            )
        queries.add(query)
        output = await search.handler(args)
        if search.name in TOOL_SUMMARY_KEYS and isinstance(output.data, list):
            # El resumen lo ve el usuario en el panel: en el idioma de la interfaz.
            output = ToolOutput(
                summary=tr(emitter.lang, TOOL_SUMMARY_KEYS[search.name], n=len(output.data)),
                data=output.data,
            )
        for item in output.data:
            if isinstance(item, dict) and item.get("url"):
                seen[source_key(item["url"])] = Source(
                    str(item.get("title", "")), item["url"], str(item.get("summary", ""))
                )
        return output

    tools = [tracked(t) for t in (search_tool, *extra_tools)]

    await emitter.thought(
        "researcher", tr(emitter.lang, "researcher.start", gap=gap.name, topic=topic)
    )
    response = await run_agent(
        agent="researcher",
        task="summarize_paper",
        messages=[
            {"role": "system", "content": RESEARCHER},
            {
                "role": "user",
                "content": f"Tema de la investigación: {topic}\nConcepto a investigar: {gap.name}"
                + vault_usage(gap),
            },
        ],
        tools=tools,
        router=router,
        emitter=emitter,
        final_validator=require_json_object("summary", "sources"),
    )

    answer = json.loads(strip_code_fence(response.content or "{}"))
    sources = verified_sources(answer.get("sources", []), seen)
    summary = str(answer.get("summary", "")).strip()
    await emitter.thought(
        "researcher", tr(emitter.lang, "researcher.done", gap=gap.name, n=len(sources))
    )
    return Finding(gap=gap, summary=summary, sources=sources)


# Resumen traducido de lo que devolvió cada herramienta de búsqueda.
TOOL_SUMMARY_KEYS = {
    "search_arxiv": "tool.arxiv",
    "search_semantic_scholar": "tool.semantic_scholar",
}

ARXIV_ID = re.compile(r"arxiv\.org/(?:abs|pdf)/([^\s?#]+?)(?:v\d+)?(?:\.pdf)?/?$", re.IGNORECASE)


def source_key(url: str) -> str:
    """Clave para comparar fuentes aunque el modelo escriba la URL de otra forma.

    En arXiv, http/https, abs/pdf y la versión (v1, v2…) apuntan al mismo paper:
    «https://arxiv.org/abs/2401.00001» y «http://arxiv.org/abs/2401.00001v1» son iguales.
    """
    url = url.strip()
    match = ARXIV_ID.search(url)
    if match:
        return f"arxiv:{match.group(1).lower()}"
    return re.sub(r"^https?://(www\.)?", "", url.lower()).rstrip("/")


def verified_sources(cited: list, seen: dict[str, Source]) -> list[Source]:
    """Fuentes citadas que arXiv devolvió de verdad, con la URL y el título de arXiv."""
    result: list[Source] = []
    if not isinstance(cited, list):
        return result
    for item in cited:
        if not isinstance(item, dict) or not item.get("url"):
            continue
        source = seen.get(source_key(str(item["url"])))
        if source is not None and source not in result:
            title = source.title or str(item.get("title", "")).strip()
            result.append(Source(title=title, url=source.url, abstract=source.abstract))
    return result


def vault_usage(gap: Gap) -> str:
    """Cómo aparece el concepto en las notas del estudiante (vacío si es un tema nuevo)."""
    if not gap.context:
        return ""
    return "\nAsí aparece en las notas del estudiante:\n" + "\n".join(
        f"- {line}" for line in gap.context
    )
