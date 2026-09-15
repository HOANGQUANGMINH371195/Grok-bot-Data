import pytest
from vda_adapters.fake_model import FakeModelProvider, ModelResponse, ProviderError, ToolCall


def test_fake_provider_is_deterministic_and_does_not_call_network() -> None:
    provider = FakeModelProvider((ModelResponse("grounded", (ToolCall("profile.get", {}),)),))
    response = provider.complete(context=("private text",), tool_ids=("profile.get",))
    assert response.text == "grounded"
    assert provider.calls == 1


def test_fake_provider_exposes_recoverable_failure_modes() -> None:
    provider = FakeModelProvider()
    provider.fail_once("timeout")
    with pytest.raises(ProviderError, match="provider_timeout"):
        provider.complete(context=(), tool_ids=())
