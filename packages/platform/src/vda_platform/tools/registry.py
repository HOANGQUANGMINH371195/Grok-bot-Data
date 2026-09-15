from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ToolDenied(PermissionError):
    """The current actor/template cannot invoke the requested tool."""


class ToolValidationError(ValueError):
    """The model payload does not satisfy the machine contract."""


@dataclass(frozen=True)
class ToolContext:
    actor_id: str
    bot_template: str
    workspace_id: str
    conversation_id: str
    grant_version: int
    policy_generation: int
    fence: int
    idempotency_key: str


@dataclass(frozen=True)
class _ToolSpec:
    tool_id: str
    grants: frozenset[str]
    input_profile: dict[str, Any]
    effect: str


class ToolRegistry:
    def __init__(self, specs: dict[str, _ToolSpec]) -> None:
        self._specs = specs
        self._effects: dict[tuple[str, str, str], Any] = {}

    @classmethod
    def from_contract_root(cls, root: Path) -> ToolRegistry:
        registry = json.loads((root / "packages/contracts/tools/v1/registry.json").read_text())
        schemas = json.loads((root / "packages/contracts/tools/v1/schemas.json").read_text())
        specs = {
            tool_id: _ToolSpec(
                tool_id,
                frozenset(spec["grants"]),
                schemas["profiles"][schemas["tools"][tool_id]["input"]],
                schemas["tools"][tool_id]["effect"],
            )
            for tool_id, spec in registry["tools"].items()
        }
        return cls(specs)

    def invoke(
        self,
        tool_id: str,
        context: ToolContext,
        payload: dict[str, Any],
        handler: Callable[[ToolContext, dict[str, Any]], Any],
    ) -> Any:
        spec = self._specs.get(tool_id)
        if spec is None or context.bot_template not in spec.grants:
            raise ToolDenied(f"tool denied: {tool_id}")
        self._validate(spec, payload)
        key = (context.actor_id, tool_id, context.idempotency_key)
        if spec.effect != "read" and key in self._effects:
            return self._effects[key]
        result = handler(context, payload)
        if spec.effect != "read":
            self._effects[key] = result
        return result

    def allowed_tools(self, bot_template: str) -> tuple[str, ...]:
        """Return the closed tool catalog visible to one template."""
        return tuple(
            sorted(spec.tool_id for spec in self._specs.values() if bot_template in spec.grants)
        )

    @staticmethod
    def _validate(spec: _ToolSpec, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            raise ToolValidationError("tool input must be an object")
        properties = spec.input_profile.get("properties", {})
        required = set(spec.input_profile.get("required", []))
        unknown = set(payload) - set(properties)
        missing = required - set(payload)
        if unknown:
            raise ToolValidationError(f"unknown tool fields: {','.join(sorted(unknown))}")
        if missing:
            raise ToolValidationError(f"missing tool fields: {','.join(sorted(missing))}")
        for name, value in payload.items():
            schema = properties[name]
            if schema.get("type") == "string" and not isinstance(value, str):
                raise ToolValidationError(f"{name} must be a string")
            if schema.get("type") == "integer" and (
                not isinstance(value, int) or isinstance(value, bool)
            ):
                raise ToolValidationError(f"{name} must be an integer")
            if schema.get("type") == "array" and not isinstance(value, list):
                raise ToolValidationError(f"{name} must be an array")
            if "enum" in schema and value not in schema["enum"]:
                raise ToolValidationError(f"{name} is not an allowed value")
