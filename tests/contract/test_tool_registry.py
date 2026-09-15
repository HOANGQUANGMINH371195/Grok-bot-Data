import json
from pathlib import Path


def test_registry_has_exact_v1_tool_count() -> None:
    registry = json.loads(
        (Path(__file__).parents[2] / "packages/contracts/tools/v1/registry.json").read_text()
    )
    assert registry["version"] == "v1"
    assert len(registry["tools"]) == 44


def test_registry_does_not_contain_human_authority_tools() -> None:
    registry = json.loads(
        (Path(__file__).parents[2] / "packages/contracts/tools/v1/registry.json").read_text()
    )
    forbidden = ("shell", "sql", "kubectl", "secret", "approve", "publish")
    assert not any(
        any(tool == word or tool.endswith(f".{word}") for word in forbidden)
        for tool in registry["tools"]
    )


def test_every_tool_has_closed_input_profile_and_bounded_output_statuses() -> None:
    root = Path(__file__).parents[2]
    schemas = json.loads((root / "packages/contracts/tools/v1/schemas.json").read_text())
    assert set(schemas["tools"]) == set(
        json.loads((root / "packages/contracts/tools/v1/registry.json").read_text())["tools"]
    )
    assert all(schema["additionalProperties"] is False for schema in schemas["profiles"].values())
    assert schemas["output"]["properties"]["status"]["enum"] == [
        "ok", "queued", "needs_approval", "needs_input", "denied", "failed"
    ]
