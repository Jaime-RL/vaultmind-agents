"""Investigador: busca en arXiv cada laguna y resume lo encontrado.

Es un agente ReAct de verdad: el modelo decide qué buscar, cuántas veces y
cuándo tiene suficiente. Cada laguna se investiga por separado, así un fallo
en una no tira la investigación entera.
"""

import json
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
    # Envolvemos la herramienta para anotar qué URLs devolvió de verdad arXiv:
    # así descartamos fuentes que el modelo se haya inventado.
    seen_urls: set[str] = set()

    async def tracked(args: dict) -> ToolOutput:
        output = await search_tool.handler(args)
        seen_urls.update(item["url"] for item in output.data if "url" in item)
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
                "content": f"Tema del TFG: {topic}\nConcepto a investigar: {gap.name}",
            },
        ],
        tools=[tool],
        router=router,
        emitter=emitter,
        final_validator=require_json_object("summary", "sources"),
    )

    answer = json.loads(strip_code_fence(response.content or "{}"))
    sources = [
        Source(title=str(s.get("title", "")).strip(), url=s["url"])
        for s in answer.get("sources", [])
        if isinstance(s, dict) and s.get("url") in seen_urls
    ]
    summary = str(answer.get("summary", "")).strip()
    await emitter.thought(
        "researcher", f"«{gap.name}»: resumen listo con {len(sources)} fuentes verificadas."
    )
    return Finding(gap=gap, summary=summary, sources=sources)
