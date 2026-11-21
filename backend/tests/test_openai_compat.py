"""Tests de la conversión de respuestas del SDK, sin red.

Se usan SimpleNamespace con la misma forma que los objetos del SDK de OpenAI.
"""

from types import SimpleNamespace as NS

import pytest

from llm import LLMError
from llm.openai_compat import to_response


def completion(content=None, tool_calls=None, usage=True):
    message = NS(content=content, tool_calls=tool_calls)
    return NS(
        choices=[NS(message=message)],
        model="provider/model-x",
        usage=NS(prompt_tokens=12, completion_tokens=5) if usage else None,
    )


def tool_call(name, arguments):
    return NS(id="call_1", function=NS(name=name, arguments=arguments))


def test_converts_text_response():
    response = to_response(completion(content="hola"))

    assert response.content == "hola"
    assert response.tool_calls == []
    assert response.model == "provider/model-x"
    assert (response.prompt_tokens, response.completion_tokens) == (12, 5)


def test_parses_tool_call_arguments():
    response = to_response(completion(tool_calls=[tool_call("search_arxiv", '{"query": "SLM"}')]))

    assert response.tool_calls[0].name == "search_arxiv"
    assert response.tool_calls[0].arguments == {"query": "SLM"}


def test_missing_usage_counts_as_zero_tokens():
    response = to_response(completion(content="hola", usage=False))

    assert (response.prompt_tokens, response.completion_tokens) == (0, 0)


@pytest.mark.parametrize("bad_arguments", ['{"query": ', '["no", "es", "objeto"]'])
def test_invalid_tool_arguments_raise_llm_error(bad_arguments):
    # Es el fallo típico de un SLM: SmartRoute lo convertirá en una escalada.
    with pytest.raises(LLMError, match="search_arxiv"):
        to_response(completion(tool_calls=[tool_call("search_arxiv", bad_arguments)]))


def test_empty_choices_raise_llm_error():
    with pytest.raises(LLMError):
        to_response(NS(choices=[], model="x", usage=None))
