-- Workspace identity, membership and resource-grant contract. Apply through Alembic owner.
CREATE TABLE IF NOT EXISTS principals (
  id text PRIMARY KEY,
  principal_type text NOT NULL CHECK (principal_type IN ('human', 'bot', 'service')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workspace_memberships (
  id bigserial PRIMARY KEY,
  workspace_id text NOT NULL REFERENCES workspaces(id),
  principal_id text NOT NULL REFERENCES principals(id),
  role text NOT NULL CHECK (role IN ('viewer', 'editor', 'owner')),
  active boolean NOT NULL DEFAULT true,
  joined_at timestamptz NOT NULL DEFAULT now(),
  left_at timestamptz,
  CHECK (active OR left_at IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS workspace_memberships_one_active
  ON workspace_memberships(workspace_id, principal_id) WHERE active;

CREATE TABLE IF NOT EXISTS resource_grants (
  workspace_id text NOT NULL REFERENCES workspaces(id),
  resource_type text NOT NULL,
  resource_id text NOT NULL,
  principal_id text NOT NULL REFERENCES principals(id),
  can_read boolean NOT NULL,
  can_write boolean NOT NULL,
  policy_generation bigint NOT NULL,
  granted_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz,
  PRIMARY KEY (workspace_id, resource_type, resource_id, principal_id),
  CHECK (NOT can_write OR can_read)
);

CREATE TABLE IF NOT EXISTS sessions (
  id text PRIMARY KEY,
  principal_id text NOT NULL REFERENCES principals(id),
  issuer text NOT NULL,
  subject text NOT NULL,
  issued_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  UNIQUE (issuer, subject, id)
);

ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE resource_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspaces FORCE ROW LEVEL SECURITY;
ALTER TABLE workspace_memberships FORCE ROW LEVEL SECURITY;
ALTER TABLE resource_grants FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS workspaces_scope ON workspaces;
CREATE POLICY workspaces_scope ON workspaces
  USING (id = current_setting('app.workspace_id', true));
DROP POLICY IF EXISTS workspace_memberships_scope ON workspace_memberships;
CREATE POLICY workspace_memberships_scope ON workspace_memberships
  USING (workspace_id = current_setting('app.workspace_id', true));
DROP POLICY IF EXISTS resource_grants_scope ON resource_grants;
CREATE POLICY resource_grants_scope ON resource_grants
  USING (workspace_id = current_setting('app.workspace_id', true));
