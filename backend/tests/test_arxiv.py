"""Cliente de arXiv con httpx.MockTransport: ninguna petición sale a internet."""

from pathlib import Path

import httpx
import pytest

from agents import ArxivClient, ToolError
from agents.arxiv import parse_feed, query_tiers

FEED = (Path(__file__).parent / "fixtures" / "arxiv_feed.xml").read_text(encoding="utf-8")

ERROR_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/api/errors#incorrect_id_format</id>
    <title>Error</title>
    <summary>incorrect id format</summary>
  </entry>
</feed>"""


def client_returning(text: str, status: int = 200, seen: list | None = None) -> ArxivClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, text=text)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ArxivClient(http=http, min_interval=0)


def test_parses_feed_and_normalizes_whitespace():
    papers = parse_feed(FEED)

    assert len(papers) == 2
    first = papers[0]
    assert first.title == "An Example Study of Function Calling in Small Language Models"
    assert first.arxiv_id == "0000.00001v1"
    assert first.url == "http://arxiv.org/abs/0000.00001v1"
    assert first.authors == ["Ada Example", "Alan Sample"]
    assert first.published == "2025-03-14"
    assert first.summary.startswith("We evaluate how small language models")
    assert "\n" not in first.summary


async def test_search_sends_expected_query():
    seen: list[httpx.Request] = []
    client = client_returning(FEED, seen=seen)

    papers = await client.search("function calling SLM")

    assert len(papers) == 2
    params = seen[0].url.params
    assert params["search_query"] == 'all:"function calling SLM"'  # primero, la frase exacta
    assert params["max_results"] == "5"


async def test_http_error_becomes_tool_error():
    with pytest.raises(ToolError, match="arXiv"):
        await client_returning("caído", status=503).search("x")


async def test_api_error_entry_becomes_tool_error():
    with pytest.raises(ToolError, match="incorrect id format"):
        await client_returning(ERROR_FEED).search("x")


async def test_invalid_xml_becomes_tool_error():
    with pytest.raises(ToolError, match="XML"):
        await client_returning("<feed>").search("x")


async def test_empty_query_is_rejected_without_request():
    seen: list = []
    with pytest.raises(ToolError, match="vacía"):
        await client_returning(FEED, seen=seen).search("   ")
    assert seen == []


async def test_tool_wraps_results_for_the_model():
    tool = client_returning(FEED).as_tool()

    output = await tool.handler({"query": "SLM"})

    assert tool.spec()["function"]["name"] == "search_arxiv"
    assert output.summary == "2 resultados de arXiv"
    assert output.data[1]["url"] == "http://arxiv.org/abs/0000.00002v2"
    assert set(output.data[0]) == {"title", "url", "published", "summary"}


async def test_waits_between_requests(monkeypatch):
    # arXiv pide 3 s entre peticiones: comprobamos que se espera sin esperar de verdad.
    waits: list[float] = []

    async def fake_sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr("agents.arxiv.asyncio.sleep", fake_sleep)
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=FEED))
    )
    client = ArxivClient(http=http, min_interval=3.0)

    await client.search("a")
    await client.search("b")

    assert len(waits) == 1
    assert 2.5 < waits[0] <= 3.0


EMPTY_FEED = (
    '<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
)


async def test_falls_back_to_looser_queries_until_something_is_found():
    """Regresión: «multitoken prediction» devolvía papers sin relación (OR implícito)."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.params["search_query"])
        return httpx.Response(200, text=FEED if "AND" in seen[-1] else EMPTY_FEED)

    client = ArxivClient(
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)), min_interval=0
    )

    papers = await client.search("multi-token prediction")

    assert len(papers) == 2
    assert seen == ['all:"multi-token prediction"', "all:multi-token AND all:prediction"]


async def test_returns_empty_when_no_tier_finds_anything():
    seen: list[httpx.Request] = []
    papers = await client_returning(EMPTY_FEED, seen=seen).search("nada que encontrar")

    assert papers == []
    assert len(seen) == 3


@pytest.mark.parametrize(
    ("query", "tiers"),
    [
        ("LoRA", ["all:LoRA"]),
        (
            "mixture of experts",
            [
                'all:"mixture of experts"',
                "all:mixture AND all:of AND all:experts",
                "all:mixture of experts",
            ],
        ),
        ('ti:"multi-token prediction"', ['ti:"multi-token prediction"']),  # sintaxis del modelo
        ("lora AND quantization", ["lora AND quantization"]),
    ],
)
def test_query_tiers(query, tiers):
    assert query_tiers(query) == tiers


def test_long_queries_skip_the_exact_phrase():
    tiers = query_tiers("small language models function calling evaluation benchmark")
    assert not tiers[0].startswith('all:"')
