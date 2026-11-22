"""Búsqueda en Semantic Scholar: segunda fuente del Investigador.

arXiv solo tiene preprints y no dice qué papers son importantes. Semantic Scholar añade
el año, la revista o congreso y el número de citas, y cubre también papers publicados
fuera de arXiv. Se ordenan por citas para que el modelo vea primero los más influyentes.

Sin clave de API el límite es compartido y bajo: si responde 429, la herramienta devuelve
un error legible y el Investigador sigue con arXiv. Con SEMANTIC_SCHOLAR_API_KEY el
límite es propio.
"""

import httpx

from agents.cache import TTLCache
from agents.tools import Tool, ToolError, ToolOutput

API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,url,year,venue,citationCount,abstract,externalIds"


class SemanticScholarClient:
    def __init__(
        self,
        http: httpx.AsyncClient | None = None,
        api_key: str | None = None,
        max_results: int = 5,
        cache: TTLCache[list[dict]] | None = None,
    ):
        self._http = http or httpx.AsyncClient(timeout=20.0)
        self._headers = {"x-api-key": api_key} if api_key else {}
        self._max_results = max_results
        self._cache = cache or TTLCache()

    async def search(self, query: str) -> list[dict]:
        query = " ".join(query.split())
        if not query:
            raise ToolError("La búsqueda está vacía")
        cached = self._cache.get(query.lower())
        if cached is not None:
            return cached
        try:
            response = await self._http.get(
                API_URL,
                params={"query": query, "limit": self._max_results, "fields": FIELDS},
                headers=self._headers,
            )
        except httpx.HTTPError as exc:
            raise ToolError(f"Semantic Scholar no respondió: {exc}") from exc
        if response.status_code == 429:
            raise ToolError("Semantic Scholar está saturado ahora mismo: usa search_arxiv")
        if response.status_code >= 400:
            raise ToolError(f"Semantic Scholar respondió {response.status_code}")
        papers = [paper_item(p) for p in response.json().get("data") or [] if p.get("title")]
        papers.sort(key=lambda p: -p["citations"])  # los más citados primero
        self._cache.set(query.lower(), papers)
        return papers

    def as_tool(self) -> Tool:
        async def handler(args: dict) -> ToolOutput:
            papers = await self.search(str(args.get("query", "")))
            return ToolOutput(summary=f"{len(papers)} resultados de Semantic Scholar", data=papers)

        return Tool(
            name="search_semantic_scholar",
            description=(
                "Busca papers en Semantic Scholar, con año, revista y número de citas (los más "
                "citados primero). Úsala para saber qué trabajos son los más influyentes."
            ),
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Términos en inglés"}},
                "required": ["query"],
            },
            handler=handler,
        )


def paper_item(paper: dict) -> dict:
    """Un resultado listo para el modelo. Si el paper está en arXiv se usa su URL de arXiv:
    así la misma fuente encontrada por las dos herramientas se reconoce como una sola."""
    arxiv_id = (paper.get("externalIds") or {}).get("ArXiv")
    url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else paper.get("url") or ""
    return {
        "title": " ".join(str(paper["title"]).split()),
        "url": url,
        "year": paper.get("year"),
        "venue": paper.get("venue") or "",
        "citations": paper.get("citationCount") or 0,
        "summary": (paper.get("abstract") or "")[:800],
    }
