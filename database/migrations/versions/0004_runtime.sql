-- Runtime task/run/effect ledger. Application transactions must set
-- app.workspace_id and claim rows with FOR UPDATE SKIP LOCKED.
CREATE TABLE IF NOT EXISTS tasks (
  id text PRIMARY KEY,
  workspace_id text NOT NULL REFERENCES workspaces(id),
  kind text NOT NULL,
  idempotency_key text NOT NULL,
  payload_json jsonb NOT NULL,
  root_task_id text,
  parent_task_id text REFERENCES tasks(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS runs (
  id text PRIMARY KEY,
  workspace_id text NOT NULL REFERENCES workspaces(id),
  task_id text NOT NULL REFERENCES tasks(id),
  conversation_id text,
  bot_id text,
  state text NOT NULL CHECK (state IN ('queued', 'leased', 'running', 'waiting', 'completed', 'handed_off', 'failed', 'cancelled')),
  lease_owner text,
  lease_expires_at timestamptz,
  fence bigint NOT NULL DEFAULT 0 CHECK (fence >= 0),
  checkpoint_revision bigint NOT NULL DEFAULT 0 CHECK (checkpoint_revision >= 0),
  checkpoint_json jsonb,
  wait_reason text CHECK (wait_reason IS NULL OR wait_reason IN ('input', 'approval', 'children', 'tool', 'peer')),
  error_code text,
  result_ref text,
  supersedes_run_id text REFERENCES runs(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS runs_claim_idx
  ON runs(state, lease_expires_at, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS runs_one_main_active
  ON runs(conversation_id, bot_id)
  WHERE conversation_id IS NOT NULL AND bot_id IS NOT NULL
    AND state IN ('queued', 'leased', 'running', 'waiting');

CREATE TABLE IF NOT EXISTS attempts (
  id text PRIMARY KEY,
  workspace_id text NOT NULL REFERENCES workspaces(id),
  run_id text NOT NULL REFERENCES runs(id),
  attempt_number integer NOT NULL CHECK (attempt_number > 0),
  worker_id text NOT NULL,
  fence bigint NOT NULL CHECK (fence > 0),
  state text NOT NULL CHECK (state IN ('leased', 'running', 'waiting', 'completed', 'failed', 'cancelled')),
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  UNIQUE (run_id, attempt_number),
  UNIQUE (run_id, fence)
);

CREATE TABLE IF NOT EXISTS tool_executions (
  id text PRIMARY KEY,
  workspace_id text NOT NULL REFERENCES workspaces(id),
  run_id text NOT NULL REFERENCES runs(id),
  attempt_id text NOT NULL REFERENCES attempts(id),
  operation_key text NOT NULL,
  tool_id text NOT NULL,
  tool_version text NOT NULL,
  effect_class text NOT NULL CHECK (effect_class IN ('read', 'compute', 'write', 'external')),
  state text NOT NULL CHECK (state IN ('started', 'succeeded', 'failed', 'unknown')),
  input_json jsonb NOT NULL,
  output_json jsonb,
  error_code text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, operation_key)
);

CREATE TABLE IF NOT EXISTS effects (
  id text PRIMARY KEY,
  workspace_id text NOT NULL REFERENCES workspaces(id),
  run_id text NOT NULL REFERENCES runs(id),
  attempt_id text NOT NULL REFERENCES attempts(id),
  operation_key text NOT NULL,
  state text NOT NULL CHECK (state IN ('reserved', 'committed', 'unknown', 'reconciled')),
  result_ref text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, operation_key)
);

DO $$
DECLARE
  table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY['tasks', 'runs', 'attempts', 'tool_executions', 'effects'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
    EXECUTE format('DROP POLICY IF EXISTS %I_workspace_scope ON %I', table_name, table_name);
    EXECUTE format(
      'CREATE POLICY %I_workspace_scope ON %I USING (workspace_id = current_setting(''app.workspace_id'', true))',
      table_name, table_name
    );
  END LOOP;
END $$;
