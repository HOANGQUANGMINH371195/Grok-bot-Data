-- PostgreSQL core messaging contract. Apply through the single Alembic owner.
CREATE TABLE IF NOT EXISTS workspaces (
  id text PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversations (
  id text PRIMARY KEY,
  workspace_id text NOT NULL REFERENCES workspaces(id),
  kind text NOT NULL CHECK (kind IN ('direct', 'group')),
  policy_generation bigint NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS conversation_members (
  id bigserial PRIMARY KEY,
  conversation_id text NOT NULL REFERENCES conversations(id),
  principal_id text NOT NULL,
  joined_sequence bigint NOT NULL,
  left_sequence bigint,
  active boolean NOT NULL DEFAULT true,
  UNIQUE (conversation_id, principal_id, joined_sequence)
);

CREATE UNIQUE INDEX IF NOT EXISTS conversation_members_one_active
  ON conversation_members(conversation_id, principal_id) WHERE active;

CREATE TABLE IF NOT EXISTS messages (
  id text PRIMARY KEY,
  conversation_id text NOT NULL REFERENCES conversations(id),
  sender_id text NOT NULL,
  sequence bigint NOT NULL,
  client_message_id text NOT NULL,
  body text NOT NULL,
  policy_generation bigint NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (conversation_id, sequence),
  UNIQUE (conversation_id, sender_id, client_message_id)
);

CREATE TABLE IF NOT EXISTS outbox_events (
  id text PRIMARY KEY,
  workspace_id text NOT NULL,
  conversation_id text NOT NULL,
  event_sequence bigint NOT NULL,
  event_type text NOT NULL,
  payload_json jsonb NOT NULL,
  published_at timestamptz,
  UNIQUE (conversation_id, event_sequence)
);

-- RLS is defense in depth; application transactions must SET LOCAL app.workspace_id.
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations FORCE ROW LEVEL SECURITY;
ALTER TABLE conversation_members FORCE ROW LEVEL SECURITY;
ALTER TABLE messages FORCE ROW LEVEL SECURITY;
ALTER TABLE outbox_events FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS conversations_workspace_scope ON conversations;
CREATE POLICY conversations_workspace_scope ON conversations
  USING (workspace_id = current_setting('app.workspace_id', true));
DROP POLICY IF EXISTS messages_workspace_scope ON messages;
CREATE POLICY messages_workspace_scope ON messages
  USING (conversation_id IN (SELECT id FROM conversations));
DROP POLICY IF EXISTS outbox_workspace_scope ON outbox_events;
CREATE POLICY outbox_workspace_scope ON outbox_events
  USING (workspace_id = current_setting('app.workspace_id', true));
