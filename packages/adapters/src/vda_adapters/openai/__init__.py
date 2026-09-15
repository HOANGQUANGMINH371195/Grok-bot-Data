"""Explicit OpenAI provider adapter; callers own live-call approval and budgets."""

from .provider import OpenAIProvider, ProviderProtocolError

__all__ = ["OpenAIProvider", "ProviderProtocolError"]
