"""Investigador: busca en arXiv cada laguna y resume lo encontrado.

Es un agente ReAct de verdad: el modelo decide qué buscar, cuántas veces y
cuándo tiene suficiente. Cada laguna se investiga por separado, así un fallo
en una no tira la investigación entera.
"""

import json
import re
from dataclasses import dataclass, field

from agents.events import Emitter
from agents.explorer import Gap
from agents.loop import run_agent
from agents.prompts import RESEARCHER
from agents.tools import Tool, ToolOutput
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
    *, topic: str, gaps: list[Gap], router: SmartRoute, emitter: Emitter, search_tool: Tool
) -> list[Finding]:
    findings = []
    for gap in gaps:
        try:
            findings.append(await research_gap(topic, gap, router, emitter, search_tool))
        except LLMError as exc:
            await emitter.thought("researcher", f"No pude investigar «{gap.name}»: {exc}")
    return findings


async def research_gap(
    topic: str, gap: Gap, router: SmartRoute, emitter: Emitter, search_tool: Tool
) -> Finding:
    # Envolvemos la herramienta para anotar qué papers devolvió de verdad arXiv:
    # así descartamos fuentes que el modelo se haya inventado.
    seen: dict[str, Source] = {}  # clave normalizada → fuente tal como la devolvió arXiv
    queries: set[str] = set()

    async def tracked(args: dict) -> ToolOutput:
        query = " ".join(str(args.get("query", "")).lower().split())
        if query and query in queries:
            # El modelo repite una búsqueda: se lo decimos en lugar de gastar otra petición.
            return ToolOutput(
                summary="búsqueda repetida",
                data={
                    "note": "Ya hiciste esta búsqueda: usa esos resultados o cambia los términos."
                },
            )
        queries.add(query)
        output = await search_tool.handler(args)
        for item in output.data:
            if isinstance(item, dict) and item.get("url"):
                seen[source_key(item["url"])] = Source(
                    str(item.get("title", "")), item["url"], str(item.get("summary", ""))
                )
        return output

    tool = Tool(search_tool.name, search_tool.description, search_tool.parameters, tracked)

    await emitter.thought("researcher", f"Investigo «{gap.name}» para el tema «{topic}».")
    response = await run_agent(
        agent="researcher",
        task="summarize_paper",
        messages=[
            {"role": "system", "content": RESEARCHER},
            {
                "role": "user",
                "content": f"Tema de la investigación: {topic}\nConcepto a investigar: {gap.name}",
            },
        ],
        tools=[tool],
        router=router,
        emitter=emitter,
        final_validator=require_json_object("summary", "sources"),
    )

    answer = json.loads(strip_code_fence(response.content or "{}"))
    sources = verified_sources(answer.get("sources", []), seen)
    summary = str(answer.get("summary", "")).strip()
    await emitter.thought(
        "researcher", f"«{gap.name}»: resumen listo con {len(sources)} fuentes verificadas."
    )
    return Finding(gap=gap, summary=summary, sources=sources)


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
