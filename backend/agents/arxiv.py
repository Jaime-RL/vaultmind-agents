"""Búsqueda de papers en arXiv (API pública, sin clave).

Documentación de la API: https://info.arxiv.org/help/api/user-manual.html
Devuelve un feed Atom (XML). arXiv pide no hacer más de una petición cada
3 segundos, así que el cliente espaciará las llamadas automáticamente.
"""

import asyncio
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx

from agents.tools import Tool, ToolError, ToolOutput

API_URL = "https://export.arxiv.org/api/query"
ATOM = {"atom": "http://www.w3.org/2005/Atom"}


@dataclass(frozen=True)
class Paper:
    arxiv_id: str
    title: str
    summary: str
    url: str
    authors: list[str]
    published: str  # fecha ISO (AAAA-MM-DD)


class ArxivClient:
    def __init__(
        self,
        http: httpx.AsyncClient | None = None,
        min_interval: float = 3.0,
        max_results: int = 5,
    ):
        # En tests se pasa un AsyncClient con httpx.MockTransport: cero red.
        self._http = http or httpx.AsyncClient(timeout=20.0)
        self._min_interval = min_interval
        self._max_results = max_results
        self._lock = asyncio.Lock()
        self._last_call = -float("inf")

    async def search(self, query: str) -> list[Paper]:
        query = query.strip()
        if not query:
            raise ToolError("La búsqueda está vacía")

        async with self._lock:  # una petición a la vez, espaciadas min_interval
            wait = self._min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                response = await self._http.get(
                    API_URL,
                    params={
                        "search_query": f"all:{query}",
                        "start": 0,
                        "max_results": self._max_results,
                        "sortBy": "relevance",
                    },
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise ToolError(f"arXiv no respondió correctamente: {exc}") from exc
            finally:
                self._last_call = time.monotonic()

        return parse_feed(response.text)

    def as_tool(self) -> Tool:
        async def handler(args: dict) -> ToolOutput:
            papers = await self.search(str(args.get("query", "")))
            return ToolOutput(
                summary=f"{len(papers)} resultados de arXiv",
                data=[
                    {
                        "title": p.title,
                        "url": p.url,
                        "published": p.published,
                        # Recortamos el abstract: ahorra tokens y un SLM se pierde menos.
                        "summary": p.summary[:800],
                    }
                    for p in papers
                ],
            )

        return Tool(
            name="search_arxiv",
            description="Busca papers científicos en arXiv. Úsala con consultas cortas en inglés.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Términos de búsqueda en inglés"}
                },
                "required": ["query"],
            },
            handler=handler,
        )


def parse_feed(xml_text: str) -> list[Paper]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ToolError("arXiv devolvió un XML que no se puede leer") from exc

    papers = []
    for entry in root.findall("atom:entry", ATOM):
        title = clean(entry.findtext("atom:title", "", ATOM))
        url = entry.findtext("atom:id", "", ATOM).strip()
        # Ante una consulta inválida, arXiv devuelve una única entrada llamada "Error".
        if title == "Error" and "api/errors" in url:
            raise ToolError(clean(entry.findtext("atom:summary", "", ATOM)))
        papers.append(
            Paper(
                arxiv_id=url.rsplit("/abs/", 1)[-1],
                title=title,
                summary=clean(entry.findtext("atom:summary", "", ATOM)),
                url=url,
                authors=[
                    clean(a.findtext("atom:name", "", ATOM))
                    for a in entry.findall("atom:author", ATOM)
                ],
                published=entry.findtext("atom:published", "", ATOM)[:10],
            )
        )
    return papers


def clean(text: str) -> str:
    """arXiv parte títulos y abstracts en varias líneas: los dejamos en una."""
    return re.sub(r"\s+", " ", text).strip()
