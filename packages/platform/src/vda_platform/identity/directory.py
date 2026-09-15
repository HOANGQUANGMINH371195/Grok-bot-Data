from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class IdentityError(PermissionError):
    """A principal, membership, role, or resource grant is invalid."""


class PrincipalType(StrEnum):
    HUMAN = "human"
    BOT = "bot"
    SERVICE = "service"


class WorkspaceRole(StrEnum):
    VIEWER = "viewer"
    EDITOR = "editor"
    OWNER = "owner"


@dataclass(frozen=True)
class Principal:
    principal_id: str
    principal_type: PrincipalType


@dataclass(frozen=True)
class Workspace:
    workspace_id: str
    policy_generation: int = 0


@dataclass(frozen=True)
class Membership:
    workspace_id: str
    principal_id: str
    role: WorkspaceRole
    active: bool = True


@dataclass(frozen=True)
class ResourceGrant:
    workspace_id: str
    resource_id: str
    resource_type: str
    principal_id: str
    read: bool
    write: bool
    generation: int


class IdentityDirectory:
    """Deterministic identity/ACL aggregate used by DB repositories and tests."""

    def __init__(self) -> None:
        self._principals: dict[str, Principal] = {}
        self._workspaces: dict[str, Workspace] = {}
        self._memberships: dict[tuple[str, str], Membership] = {}
        self._grants: dict[tuple[str, str, str, str], ResourceGrant] = {}

    def register_principal(self, principal_id: str, principal_type: PrincipalType) -> Principal:
        if not principal_id:
            raise IdentityError("principal_id is required")
        if principal_id in self._principals:
            raise IdentityError("principal already exists")
        principal = Principal(principal_id, principal_type)
        self._principals[principal_id] = principal
        return principal

    def create_workspace(self, workspace_id: str, owner_id: str) -> Workspace:
        if not workspace_id:
            raise IdentityError("workspace_id is required")
        if workspace_id in self._workspaces:
            raise IdentityError("workspace already exists")
        owner = self._principal(owner_id)
        if owner.principal_type is not PrincipalType.HUMAN:
            raise IdentityError("workspace owner must be human")
        workspace = Workspace(workspace_id)
        self._workspaces[workspace_id] = workspace
        self._memberships[(workspace_id, owner_id)] = Membership(
            workspace_id, owner_id, WorkspaceRole.OWNER
        )
        return workspace

    def add_member(
        self, workspace_id: str, actor_id: str, principal_id: str, role: WorkspaceRole
    ) -> Membership:
        self._require_role(workspace_id, actor_id, WorkspaceRole.OWNER)
        principal = self._principal(principal_id)
        if role is WorkspaceRole.OWNER and principal.principal_type is not PrincipalType.HUMAN:
            raise IdentityError("bot or service cannot be workspace owner")
        key = (workspace_id, principal_id)
        current = self._memberships.get(key)
        if current is not None and current.active:
            raise IdentityError("principal is already an active member")
        membership = Membership(workspace_id, principal_id, role)
        self._memberships[key] = membership
        self._bump(workspace_id)
        return membership

    def remove_member(self, workspace_id: str, actor_id: str, principal_id: str) -> None:
        self._require_role(workspace_id, actor_id, WorkspaceRole.OWNER)
        current = self._membership(workspace_id, principal_id)
        if not current.active:
            raise IdentityError("principal is not an active member")
        if current.role is WorkspaceRole.OWNER and self._active_owner_count(workspace_id) <= 1:
            raise IdentityError("cannot remove the last workspace owner")
        self._memberships[(workspace_id, principal_id)] = Membership(
            workspace_id, principal_id, current.role, active=False
        )
        self._bump(workspace_id)

    def grant_resource(
        self,
        workspace_id: str,
        actor_id: str,
        resource_id: str,
        resource_type: str,
        principal_id: str,
        *,
        read: bool,
        write: bool,
    ) -> ResourceGrant:
        self._require_role(workspace_id, actor_id, WorkspaceRole.OWNER)
        if not read and write:
            raise IdentityError("write grant requires read")
        self._require_active_member(workspace_id, principal_id)
        generation = self._bump(workspace_id)
        grant = ResourceGrant(
            workspace_id, resource_id, resource_type, principal_id, read, write, generation
        )
        self._grants[(workspace_id, resource_type, resource_id, principal_id)] = grant
        return grant

    def revoke_resource(
        self,
        workspace_id: str,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        principal_id: str,
    ) -> int:
        self._require_role(workspace_id, actor_id, WorkspaceRole.OWNER)
        self._grants.pop((workspace_id, resource_type, resource_id, principal_id), None)
        return self._bump(workspace_id)

    def can_access(
        self,
        workspace_id: str,
        principal_id: str,
        resource_type: str,
        resource_id: str,
        *,
        write: bool = False,
    ) -> bool:
        if not self._is_active_member(workspace_id, principal_id):
            return False
        grant = self._grants.get((workspace_id, resource_type, resource_id, principal_id))
        if grant is None or not grant.read:
            return False
        return not write or grant.write

    def membership(self, workspace_id: str, principal_id: str) -> Membership:
        return self._membership(workspace_id, principal_id)

    def workspace(self, workspace_id: str) -> Workspace:
        try:
            return self._workspaces[workspace_id]
        except KeyError as exc:
            raise IdentityError("workspace not found") from exc

    def _require_role(self, workspace_id: str, principal_id: str, required: WorkspaceRole) -> None:
        membership = self._membership(workspace_id, principal_id)
        rank = {WorkspaceRole.VIEWER: 1, WorkspaceRole.EDITOR: 2, WorkspaceRole.OWNER: 3}
        if not membership.active or rank[membership.role] < rank[required]:
            raise IdentityError("insufficient workspace role")

    def _require_active_member(self, workspace_id: str, principal_id: str) -> None:
        if not self._is_active_member(workspace_id, principal_id):
            raise IdentityError("principal is not an active workspace member")

    def _is_active_member(self, workspace_id: str, principal_id: str) -> bool:
        try:
            return self._memberships[(workspace_id, principal_id)].active
        except KeyError:
            return False

    def _membership(self, workspace_id: str, principal_id: str) -> Membership:
        self.workspace(workspace_id)
        try:
            return self._memberships[(workspace_id, principal_id)]
        except KeyError as exc:
            raise IdentityError("principal is not a workspace member") from exc

    def _principal(self, principal_id: str) -> Principal:
        try:
            return self._principals[principal_id]
        except KeyError as exc:
            raise IdentityError("principal not found") from exc

    def _active_owner_count(self, workspace_id: str) -> int:
        return sum(
            membership.active and membership.role is WorkspaceRole.OWNER
            for (member_workspace, _), membership in self._memberships.items()
            if member_workspace == workspace_id
        )

    def _bump(self, workspace_id: str) -> int:
        workspace = self.workspace(workspace_id)
        updated = Workspace(workspace.workspace_id, workspace.policy_generation + 1)
        self._workspaces[workspace_id] = updated
        return updated.policy_generation
