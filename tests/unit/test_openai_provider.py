import httpx
import pytest
from pydantic import SecretStr
from vda_adapters.openai import OpenAIProvider, ProviderProtocolError


@pytest.mark.asyncio
async def test_openai_adapter_parses_mocked_response_without_real_network() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-secret"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "grounded", "tool_calls": []}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    response = await OpenAIProvider(SecretStr("test-secret"), "test-model").complete(
        context=("hello",),
        tool_ids=(),
        transport=httpx.MockTransport(handler),
    )
    assert response.text == "grounded"
    assert response.usage_input_tokens == 3


@pytest.mark.asyncio
async def test_openai_adapter_rejects_unavailable_tool() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "function": {"name": "shell.exec", "arguments": "{}"},
                                }
                            ],
                        }
                    }
                ],
            },
        )

    with pytest.raises(ProviderProtocolError, match="unavailable_tool"):
        await OpenAIProvider(SecretStr("test-secret"), "test-model").complete(
            context=("hello",),
            tool_ids=("profile.get",),
            transport=httpx.MockTransport(handler),
        )
