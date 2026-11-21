import pytest

from llm import FakeLLMClient, LLMError, LLMResponse, ScriptExhaustedError, ToolCall


async def test_returns_scripted_responses_in_order():
    fake = FakeLLMClient([LLMResponse(content="uno"), LLMResponse(content="dos")])

    first = await fake.complete([{"role": "user", "content": "a"}], model="slm")
    second = await fake.complete([{"role": "user", "content": "b"}], model="slm")

    assert [first.content, second.content] == ["uno", "dos"]
    assert fake.remaining == 0


async def test_fills_model_with_requested_one():
    fake = FakeLLMClient([LLMResponse(content="hola")])

    response = await fake.complete([], model="tiny-model")

    assert response.model == "tiny-model"


async def test_records_every_call():
    tools = [{"type": "function", "function": {"name": "search_arxiv"}}]
    fake = FakeLLMClient([LLMResponse(tool_calls=[ToolCall(id="1", name="search_arxiv")])])
    messages = [{"role": "user", "content": "busca papers"}]

    await fake.complete(messages, model="large", tools=tools)
    messages.append({"role": "user", "content": "esto no debe aparecer en el registro"})

    assert len(fake.calls) == 1
    assert fake.calls[0].model == "large"
    assert fake.calls[0].tools == tools
    assert fake.calls[0].messages == [{"role": "user", "content": "busca papers"}]


async def test_raises_scripted_exceptions():
    fake = FakeLLMClient([LLMError("el SLM devolvió basura")])

    with pytest.raises(LLMError, match="basura"):
        await fake.complete([], model="slm")


async def test_fails_loudly_when_script_is_exhausted():
    fake = FakeLLMClient([])

    with pytest.raises(ScriptExhaustedError, match="llamada nº 1"):
        await fake.complete([], model="slm")


def test_script_exhausted_is_not_an_llm_error():
    # SmartRoute escala con LLMError; un guion agotado es un fallo del test y no debe escalar.
    assert not issubclass(ScriptExhaustedError, LLMError)
