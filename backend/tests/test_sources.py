"""Segunda fuente (Semantic Scholar) y caché de búsquedas, con httpx.MockTransport: sin red."""

from pathlib import Path

import httpx
import pytest

from agents import ArxivClient, Gap, ToolError, research
from agents.cache import TTLCache
from agents.semantic_scholar import SemanticScholarClient
from tests.conftest import PAPER_URL, calls_tool, fake_search_tool, final

FEED = (Path(__file__).parent / "fixtures" / "arxiv_feed.xml").read_text(encoding="utf-8")

S2_RESPONSE = {
    "data": [
        {
            "title": "Poco citado",
            "url": "https://www.semanticscholar.org/paper/aaa",
            "year": 2025,
            "venue": "",
            "citationCount": 3,
            "abstract": "A small study.",
            "externalIds": {},
        },
        {
            "title": "Better & Faster Large Language Models via Multi-token Prediction",
            "url": "https://www.semanticscholar.org/paper/bbb",
            "year": 2024,
            "venue": "ICML",
            "citationCount": 250,
            "abstract": "We train LLMs to predict multiple future tokens at once.",
            "externalIds": {"ArXiv": "2404.19737"},
        },
    ]
}


def s2_client(status=200, payload=S2_RESPONSE, seen=None) -> SemanticScholarClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=payload)

    return SemanticScholarClient(http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


# --- Caché ---------------------------------------------------------------------


def test_cache_expires_and_evicts_the_least_used():
    now = [0.0]
    cache: TTLCache[int] = TTLCache(ttl_s=10, max_items=2, clock=lambda: now[0])
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1  # «a» pasa a ser la más reciente
    cache.set("c", 3)  # sale «b», la menos usada
    assert (cache.get("b"), cache.get("c")) == (None, 3)
    now[0] = 11
    assert cache.get("a") is None  # caducada


async def test_arxiv_repeated_search_is_served_from_cache():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text=FEED)

    client = ArxivClient(
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)), min_interval=0
    )

    await client.search("function calling SLM")
    await client.search("  Function   calling SLM ")  # misma búsqueda, escrita distinto

    assert len(seen) == 1


# --- Semantic Scholar ----------------------------------------------------------


async def test_semantic_scholar_sorts_by_citations_and_prefers_arxiv_urls():
    papers = await s2_client().search("multi-token prediction")

    assert [p["citations"] for p in papers] == [250, 3]
    assert papers[0]["url"] == "https://arxiv.org/abs/2404.19737"
    assert papers[0]["venue"] == "ICML" and papers[0]["year"] == 2024
    assert papers[1]["url"].startswith("https://www.semanticscholar.org/")


async def test_semantic_scholar_rate_limit_is_a_readable_tool_error():
    with pytest.raises(ToolError, match="usa search_arxiv"):
        await s2_client(status=429).search("x y")


async def test_semantic_scholar_search_is_cached():
    seen: list[httpx.Request] = []
    client = s2_client(seen=seen)

    await client.search("multi-token prediction")
    await client.search("Multi-Token  prediction")

    assert len(seen) == 1
    assert seen[0].url.params["fields"].startswith("title,url")


async def test_researcher_verifies_sources_from_both_tools(make_router, emitter):
    """Una fuente de Semantic Scholar se verifica igual que una de arXiv; la misma fuente
    encontrada por las dos herramientas (misma id de arXiv) cuenta una sola vez."""
    s2_tool = s2_client().as_tool()
    answer = {
        "summary": "MTP predice varios tokens.",
        "sources": [
            {"title": "Meta", "url": "http://arxiv.org/abs/2404.19737v2"},
            {"title": "Example", "url": PAPER_URL},
            {"title": "Inventada", "url": "https://arxiv.org/abs/9999.99999"},
        ],
    }
    router, fake = make_router(
        [
            calls_tool("search_semantic_scholar", query="multi-token prediction"),
            calls_tool("search_arxiv", call_id="c2", query="multi-token prediction"),
            final(answer),
        ]
    )

    [finding] = await research(
        topic="mtp",
        gaps=[Gap("MTP", [], is_topic=True)],
        router=router,
        emitter=emitter,
        search_tool=fake_search_tool(),
        extra_tools=[s2_tool],
    )

    assert [s.url for s in finding.sources] == ["https://arxiv.org/abs/2404.19737", PAPER_URL]
    assert "predict multiple future tokens" in finding.sources[0].abstract
    offered = {t["function"]["name"] for t in fake.calls[0].tools}
    assert offered == {"search_arxiv", "search_semantic_scholar"}
