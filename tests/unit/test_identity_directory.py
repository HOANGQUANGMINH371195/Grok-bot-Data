import pytest
from vda_platform.identity import IdentityDirectory, IdentityError, PrincipalType, WorkspaceRole


def _directory() -> IdentityDirectory:
    directory = IdentityDirectory()
    directory.register_principal("owner", PrincipalType.HUMAN)
    directory.register_principal("editor", PrincipalType.HUMAN)
    directory.register_principal("bot", PrincipalType.BOT)
    directory.register_principal("other", PrincipalType.HUMAN)
    directory.create_workspace("workspace-a", "owner")
    directory.add_member("workspace-a", "owner", "editor", WorkspaceRole.EDITOR)
    directory.add_member("workspace-a", "owner", "bot", WorkspaceRole.VIEWER)
    return directory


def test_resource_grant_is_tenant_scoped_and_revocation_changes_generation() -> None:
    directory = _directory()
    grant = directory.grant_resource(
        "workspace-a", "owner", "dataset-1", "dataset", "bot", read=True, write=False
    )
    assert directory.can_access("workspace-a", "bot", "dataset", "dataset-1")
    assert not directory.can_access("workspace-a", "bot", "dataset", "dataset-1", write=True)
    assert grant.generation == directory.workspace("workspace-a").policy_generation
    generation = directory.revoke_resource("workspace-a", "owner", "dataset", "dataset-1", "bot")
    assert generation > grant.generation
    assert not directory.can_access("workspace-a", "bot", "dataset", "dataset-1")
    assert not directory.can_access("workspace-other", "bot", "dataset", "dataset-1")


def test_only_human_owner_manages_members_and_last_owner_is_protected() -> None:
    directory = _directory()
    with pytest.raises(IdentityError, match="insufficient"):
        directory.add_member("workspace-a", "editor", "other", WorkspaceRole.VIEWER)
    with pytest.raises(IdentityError, match="owner"):
        directory.add_member("workspace-a", "owner", "bot", WorkspaceRole.OWNER)
    with pytest.raises(IdentityError, match="last workspace owner"):
        directory.remove_member("workspace-a", "owner", "owner")


def test_removed_member_cannot_retain_resource_access_or_be_granted() -> None:
    directory = _directory()
    directory.grant_resource(
        "workspace-a", "owner", "dataset-1", "dataset", "editor", read=True, write=True
    )
    directory.remove_member("workspace-a", "owner", "editor")
    assert not directory.can_access("workspace-a", "editor", "dataset", "dataset-1")
    with pytest.raises(IdentityError, match="active workspace member"):
        directory.grant_resource(
            "workspace-a", "owner", "dataset-2", "dataset", "editor", read=True, write=False
        )
